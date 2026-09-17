"""媒體庫：Berth 經手的作品在媒體庫與管線裡的樣子（票 13、`.scratch/m1/library-shape.md`）。

**名字叫 inventory 不叫 library**：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端的
媒體庫，而這一支盤點的是 Library Route 上的東西（UI 顯示「媒體庫」）。

同一件事有兩種切法，所以兩個入口住在一起、共用同一組分類：

- **一條 Route 的牆**（`read_inventory`）：牆上是這條 Route 上有 Job 的作品——包含一個檔案都還沒
  入庫的（使用者拍板，否則「有待審」找不到從沒入庫過的作品）——加上帳本裡目標落在這條 Route
  底下的：帳本自己站得住，Job 被刪了檔案仍然在（`models/ledger.py`）。一格說得出入庫了幾集、
  哪一部需要你、Jellyfin 找到了沒。
- **一部作品的內容**（`read_holdings`，Media 詳情頁）：各集狀態、帳本裡的每一個檔案、對不到的
  檔案與多版本並存。**跨 Route**：詳情頁回答的是一部作品的事。

**判定規則全部在這裡**，前端只照畫（`JobOut.retryable` 的同一個規矩）。
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    CollectionType,
    EpisodeSnapshot,
    EpisodeStatus,
    InventoryStatus,
    JellyfinPresence,
    JobState,
    LedgerStatus,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanStatus,
    Tags,
)
from berth.models import Job, LedgerEntry, Media, Plan, PlanItem, Route
from berth.models.types import utcnow
from berth.services.routes import owning_route, target_prefix

#: 卡在失敗、在你動手之前不會自己好的狀態——下載列表上塗紅的那四個（`jobs/jobState.ts`）。
FAILED_STATES: frozenset[JobState] = frozenset(
    {
        JobState.SUBMIT_FAILED,
        JobState.MISSING_FILES,
        JobState.CLIENT_ERROR,
        JobState.IMPORT_FAILED,
    }
)

#: 還在路上：送單到入庫之間的每一站。`stalled` 也算——做種的人回來它就會自己動。
UNDER_WAY_STATES: frozenset[JobState] = frozenset(
    {
        JobState.REQUESTED,
        JobState.SUBMITTED,
        JobState.METADATA_READY,
        JobState.DOWNLOADING,
        JobState.STALLED,
        JobState.COMPLETED,
        JobState.PLANNING,
        JobState.IMPORTING,
    }
)

#: 停下來等人的 Job：它的計劃蓋到的集數算「卡住」。送單失敗不在裡面——那一包連檔案清單
#: 都還沒有，蓋不到任何一集。
STUCK_STATES: frozenset[JobState] = frozenset({JobState.REVIEW, JobState.IMPORT_FAILED})

#: 計劃裡說得出「這個檔案衝著哪一集來」的處置。`review` 也算：季集是猜的，但它確實是那一集的檔案。
_CLAIMING: frozenset[PlanAction] = frozenset({PlanAction.IMPORT, PlanAction.REVIEW})


# --- 一條 Route 的牆 ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InventoryItem:
    """牆上的一格。"""

    media_id: str
    kind: MediaKind
    #: `zh-Hant` 介面的顯示用標題（`zh-TW` 那一輪）；`en` 介面用 `title_en`（brief §7.5）。
    #: 牆的排序照這一個，EN 介面上看起來不是字母序——這面牆由 M1.5 票 03 換掉。
    title: str
    title_en: str
    year: int | None
    poster_url: str
    status: InventoryStatus
    #: 劇集：已經播出的正片入庫了幾集（S00 不算）。電影：正片在不在（0 / 1）。
    imported: int
    #: 劇集：TMDB 上已經播出的正片集數（S00 不算，還沒播的不算）。電影一律是 1。
    aired: int
    #: 電影的正片有幾個版本（brief §7.7）。劇集的版本在詳情頁逐集列，這裡是 0。
    versions: int
    #: 這條 Route 上有一份計劃停下來等人。
    needs_review: bool
    #: 這條 Route 上有 Job 現在那一份計劃裡有對不到的檔案（預估不算）。
    has_unmatched: bool
    #: medium 自動入庫、掛著 audit 的檔案數，這部作品在這條 Route 上的每一筆 Job 加總
    #: （brief §6.5）。卡片的狀態是「已入庫」時，這個數字是唯一說得出「還要看一眼」的地方（票 15）。
    audits: int
    presence: JellyfinPresence
    #: 深連結要開的那一個 item：劇集是 Series，電影是 Movie。沒找到時是空字串。
    jellyfin_item_id: str


@dataclass(frozen=True, slots=True)
class InventoryRoute:
    """切換列上的一條 Route，與它兩個篩選的數字。"""

    slug: str
    name: str
    collection_type: CollectionType
    #: 停用的 Route 仍然列出來：已經入庫的東西還在它底下。
    enabled: bool
    titles: int
    review: int
    unmatched: int


@dataclass(frozen=True, slots=True)
class InventoryView:
    route: InventoryRoute
    items: tuple[InventoryItem, ...]


# --- 一部作品的內容 -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EpisodeView:
    """集表的一集：快照那幾格，加上它在媒體庫裡的狀態。"""

    episode_number: int
    name: str
    air_date: date | None
    runtime: int | None
    absolute_number: int | None
    status: EpisodeStatus


@dataclass(frozen=True, slots=True)
class SeasonView:
    season_number: int
    name: str
    episode_count: int
    air_date: date | None
    #: 這一季播出了的集數裡入庫了幾集，與它的分母。與牆上那一格同一個定義：還沒播卻先入庫
    #: 的那一集不算進去（code-review 抓到前端自己算時分母不一致）。
    imported: int
    aired: int
    episodes: tuple[EpisodeView, ...]


@dataclass(frozen=True, slots=True)
class LedgerFileView:
    """檔案清單的一列：一筆帳本（CONTEXT.md 的 Ledger Entry）。"""

    id: int
    action: PlanAction
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: `Tags.render()` 的那一串——與檔名裡的那一段是同一個東西。
    tags: str
    #: 容器裡的完整路徑，也就是 Jellyfin 回報 `Path` 的形狀。
    target_path: str
    status: LedgerStatus
    #: 正片才查 Jellyfin；字幕與特典一律是 `none`。
    presence: JellyfinPresence
    #: 下一次反查的時間與已經問過幾次（「還在掃描」那一行說得出下一次是什麼時候）。
    resolve_after: datetime | None
    resolve_attempts: int
    job_hash: str | None


@dataclass(frozen=True, slots=True)
class UnmatchedFileView:
    """對不到任何一集的檔案，與把它帶進來的那一筆 Job。"""

    rel_path: str
    job_hash: str
    job_name: str


@dataclass(frozen=True, slots=True)
class VersionView:
    """同一集（或同一部電影）的一個版本。"""

    #: Jellyfin 版本選單上的名字（帳本的 `jellyfin_version_name`，同一個東西同一個詞）。
    #: **由 Jellyfin 算**（brief §7.7），反查到的那一刻抄進帳本；還沒收錄就是空字串。
    name: str
    #: 這個檔案的 Tags。還沒有 `name` 時畫面顯示它，並說明那是檔名的 tags 而不是版本名。
    tags: str


@dataclass(frozen=True, slots=True)
class VersionGroupView:
    """同一集（或同一部電影）的幾個版本。"""

    season: int | None
    episode_start: int | None
    episode_end: int | None
    versions: tuple[VersionView, ...]


@dataclass(frozen=True, slots=True)
class Holdings:
    seasons: tuple[SeasonView, ...]
    files: tuple[LedgerFileView, ...]
    unmatched: tuple[UnmatchedFileView, ...]
    versions: tuple[VersionGroupView, ...]


class Covers(Protocol):
    """帳本一筆或計劃一列：兩者都用 `season` / `episode_start` / `episode_end` 說它蓋到哪幾集。"""

    @property
    def season(self) -> int | None: ...

    @property
    def episode_start(self) -> int | None: ...

    @property
    def episode_end(self) -> int | None: ...


async def list_inventories(session: AsyncSession) -> tuple[InventoryRoute, ...]:
    """切換列：每一條 Route 與它的作品數。一條一條盤，Route 是個位數。"""
    routes = await _routes(session)
    return tuple([(await _survey(session, route, routes)).route for route in routes])


async def read_inventory(session: AsyncSession, slug: str) -> InventoryView | None:
    routes = await _routes(session)
    route = next((row for row in routes if row.slug == slug), None)
    return None if route is None else await _survey(session, route, routes)


async def read_holdings(session: AsyncSession, media: Media, snapshot: MediaSnapshot) -> Holdings:
    """這部作品在媒體庫與管線裡的樣子（Media 詳情頁）。

    一集算不算已入庫看帳本，算不算卡住或在路上看 Job 與它現在那一份計劃——與牆上那一格
    同一組分類。
    """
    entries = sorted(
        await session.scalars(select(LedgerEntry).where(LedgerEntry.media_id == media.id)),
        key=_in_episode_order,
    )
    jobs = {
        job.hash: job
        for job in await session.scalars(
            select(Job).where(Job.media_id == media.id).order_by(Job.added_at, Job.hash)
        )
    }
    plans = {
        plan.id: plan
        for plan in await session.scalars(select(Plan).where(Plan.job_hash.in_(list(jobs))))
    }
    items = await session.scalars(
        select(PlanItem).where(PlanItem.plan_id.in_(list(plans))).order_by(PlanItem.id)
    )

    stuck: set[tuple[int, int]] = set()
    under_way: set[tuple[int, int]] = set()
    unmatched: list[UnmatchedFileView] = []
    for item in items:
        plan = plans[item.plan_id]
        job = jobs.get(plan.job_hash or "")
        if job is None:
            continue
        # 預估沒讀過檔案本身（brief §5.1），下載完成之後會重算一份。
        if item.action is PlanAction.UNMATCHED and plan.status is not PlanStatus.PREPLAN:
            unmatched.append(
                UnmatchedFileView(rel_path=item.rel_path, job_hash=job.hash, job_name=job.name)
            )
        if item.action not in _CLAIMING:
            continue
        if job.state in STUCK_STATES:
            stuck.update(episodes_of(item))
        elif job.state in UNDER_WAY_STATES:
            under_way.update(episodes_of(item))

    features = [entry for entry in entries if entry.action is PlanAction.IMPORT]
    imported = {pair for entry in features for pair in episodes_of(entry)}
    today = utcnow().date()

    def status(season: int, episode: EpisodeSnapshot) -> EpisodeStatus:
        pair = (season, episode.episode_number)
        if pair in imported:
            return EpisodeStatus.IMPORTED
        if pair in stuck:
            return EpisodeStatus.STUCK
        if pair in under_way:
            return EpisodeStatus.DOWNLOADING
        if _aired(episode, today):
            return EpisodeStatus.MISSING
        return EpisodeStatus.UNAIRED

    seasons = []
    for season in snapshot.seasons:
        aired = [row for row in season.episodes if _aired(row, today)]
        seasons.append(
            SeasonView(
                season_number=season.season_number,
                name=season.name,
                episode_count=season.episode_count,
                air_date=season.air_date,
                imported=sum(
                    (season.season_number, row.episode_number) in imported for row in aired
                ),
                aired=len(aired),
                episodes=tuple(
                    EpisodeView(
                        episode_number=episode.episode_number,
                        name=episode.name,
                        air_date=episode.air_date,
                        runtime=episode.runtime,
                        absolute_number=episode.absolute_number,
                        status=status(season.season_number, episode),
                    )
                    for episode in season.episodes
                ),
            )
        )

    return Holdings(
        seasons=tuple(seasons),
        files=tuple(_file(entry) for entry in entries),
        unmatched=tuple(unmatched),
        versions=_versions(features),
    )


def episodes_of(row: Covers) -> Iterator[tuple[int, int]]:
    """這個檔案蓋到哪幾集：`S01E01-E02` 是兩集（brief §6.6）。電影與特典什麼都不蓋。"""
    if row.season is None or row.episode_start is None:
        return
    for episode in range(row.episode_start, (row.episode_end or row.episode_start) + 1):
        yield (row.season, episode)


def aired_episodes(snapshot: MediaSnapshot, today: date) -> set[tuple[int, int]]:
    """TMDB 上已經播出的正片。**S00 不算**：TMDB 自己報的季數集數也不算它（票 04）。"""
    return {
        (season.season_number, episode.episode_number)
        for season in snapshot.seasons
        if season.season_number > 0
        for episode in season.episodes
        if _aired(episode, today)
    }


def presence_of(kind: MediaKind, features: Sequence[LedgerEntry]) -> tuple[JellyfinPresence, str]:
    """這部作品在 Jellyfin 裡找到了沒，與深連結要開的那一個 item（shape brief §5）。

    **劇集要連 Series**：連到某一集的連結不是「該作品」，所以只找到集、還不知道 Series 時
    算「還在找」（shape brief §7）。一個檔案自己找到了沒是另一個問題（`_file_presence`）。
    """
    if not features:
        return JellyfinPresence.NONE, ""
    for entry in features:
        link = entry.jellyfin_series_id if kind is MediaKind.TV else entry.jellyfin_item_id
        if link:
            return JellyfinPresence.FOUND, link
    if any(entry.resolve_after is not None or entry.jellyfin_item_id for entry in features):
        return JellyfinPresence.SEARCHING, ""
    return JellyfinPresence.LOST, ""


def _aired(episode: EpisodeSnapshot, today: date) -> bool:
    """以伺服器的 UTC 日期判定。TMDB 還沒有播出日的一集不算播出了。"""
    return episode.air_date is not None and episode.air_date <= today


async def _routes(session: AsyncSession) -> list[Route]:
    return list(await session.scalars(select(Route).order_by(Route.id)))


async def _survey(session: AsyncSession, route: Route, routes: Sequence[Route]) -> InventoryView:
    jobs = list(
        await session.scalars(
            select(Job).where(Job.route_id == route.id, Job.media_id.is_not(None))
        )
    )
    entries = [
        entry
        for entry in await session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.media_id.is_not(None),
                LedgerEntry.target_path.startswith(target_prefix(route), autoescape=True),
            )
            .order_by(LedgerEntry.id)
        )
        # 前綴只是粗篩：`/data/library/tv/anime` 可能是另一條更深的 Route 的目標。
        if owning_route(entry.target_path, routes) is route
    ]
    flagged = await _unmatched_jobs(session, [job.hash for job in jobs])
    audits = await _audits(session, [job.hash for job in jobs])
    media_ids = {job.media_id for job in jobs if job.media_id is not None} | {
        entry.media_id for entry in entries if entry.media_id is not None
    }
    titles = await session.scalars(select(Media).where(Media.id.in_(media_ids)))
    today = utcnow().date()

    items = sorted(
        (
            _item(
                media,
                [job for job in jobs if job.media_id == media.id],
                [entry for entry in entries if entry.media_id == media.id],
                flagged=flagged,
                audits=audits,
                today=today,
            )
            for media in titles
        ),
        key=lambda item: (item.title.casefold(), item.media_id),
    )
    return InventoryView(
        route=InventoryRoute(
            slug=route.slug,
            name=route.name,
            collection_type=route.collection_type,
            enabled=route.enabled,
            titles=len(items),
            review=sum(item.needs_review for item in items),
            unmatched=sum(item.has_unmatched for item in items),
        ),
        items=tuple(items),
    )


async def _unmatched_jobs(session: AsyncSession, job_hashes: Iterable[str]) -> set[str]:
    """現在那一份計劃裡有對不到的檔案的 Job。

    **預估不算**：pre-plan 沒讀過檔案本身（brief §5.1），下載完成之後會重算一份。
    """
    rows = await session.scalars(
        select(Plan.job_hash)
        .join(PlanItem, PlanItem.plan_id == Plan.id)
        .where(
            Plan.job_hash.in_(list(job_hashes)),
            Plan.status != PlanStatus.PREPLAN,
            PlanItem.action == PlanAction.UNMATCHED,
        )
        .distinct()
    )
    return {job_hash for job_hash in rows if job_hash is not None}


async def _audits(session: AsyncSession, job_hashes: Sequence[str]) -> dict[str, int]:
    """每一筆 Job 現在那一份計劃裡掛著 audit 的檔案數。audit 只在真的自動入庫時才掛
    （`services/plan._audit`），所以不必再排除預估。"""
    rows = await session.execute(
        select(Plan.job_hash, func.count(PlanItem.id))
        .join(PlanItem, PlanItem.plan_id == Plan.id)
        .where(Plan.job_hash.in_(list(job_hashes)), PlanItem.audit)
        .group_by(Plan.job_hash)
    )
    return {job_hash: count for job_hash, count in rows if job_hash is not None}


def _item(
    media: Media,
    jobs: Sequence[Job],
    entries: Sequence[LedgerEntry],
    *,
    flagged: set[str],
    audits: dict[str, int],
    today: date,
) -> InventoryItem:
    snapshot = media.snapshot()
    features = [entry for entry in entries if entry.action is PlanAction.IMPORT]
    if media.kind is MediaKind.MOVIE:
        imported, aired, versions = min(len(features), 1), 1, len(features)
    else:
        aired_set = aired_episodes(snapshot, today)
        covered = {pair for entry in features for pair in episodes_of(entry)}
        imported, aired, versions = len(covered & aired_set), len(aired_set), 0
    presence, link = presence_of(media.kind, features)
    states = {job.state for job in jobs}
    return InventoryItem(
        media_id=media.id,
        kind=media.kind,
        title=snapshot.title or media.title_en,
        title_en=media.title_en,
        year=media.year,
        poster_url=snapshot.poster_url,
        status=_status(states, has_features=bool(features), imported=imported, aired=aired),
        imported=imported,
        aired=aired,
        versions=versions,
        needs_review=JobState.REVIEW in states,
        has_unmatched=any(job.hash in flagged for job in jobs),
        audits=sum(audits.get(job.hash, 0) for job in jobs),
        presence=presence,
        jellyfin_item_id=link,
    )


def _status(
    states: set[JobState], *, has_features: bool, imported: int, aired: int
) -> InventoryStatus:
    """依 `InventoryStatus` 的宣告順序取第一個成立的：需要人的那一件排前面。"""
    if states & FAILED_STATES:
        return InventoryStatus.FAILED
    if JobState.REVIEW in states:
        return InventoryStatus.REVIEW
    if states & UNDER_WAY_STATES:
        return InventoryStatus.DOWNLOADING
    if not has_features:
        return InventoryStatus.EMPTY
    return InventoryStatus.COMPLETE if imported >= aired else InventoryStatus.PARTIAL


def _in_episode_order(entry: LedgerEntry) -> tuple[bool, int, int, str]:
    """季集在前（S00 先），電影與沒有季集的檔案殿後；同一集的版本照路徑排，每次都一樣。"""
    return (
        entry.season is None,
        entry.season or 0,
        entry.episode_start or 0,
        entry.target_path,
    )


def _file(entry: LedgerEntry) -> LedgerFileView:
    return LedgerFileView(
        id=entry.id,
        action=entry.action,
        season=entry.season,
        episode_start=entry.episode_start,
        episode_end=entry.episode_end,
        tags=Tags.model_validate(entry.tags_json).render() if entry.tags_json else "",
        target_path=entry.target_path,
        status=entry.status,
        presence=_file_presence(entry),
        resolve_after=entry.resolve_after,
        resolve_attempts=entry.resolve_attempts,
        job_hash=entry.job_hash,
    )


def _file_presence(entry: LedgerEntry) -> JellyfinPresence:
    """一個檔案找到了沒。與牆上那一格不同：這裡問的是**這一集**，所以不必等 Series。"""
    if entry.action is not PlanAction.IMPORT:
        return JellyfinPresence.NONE
    if entry.jellyfin_item_id:
        return JellyfinPresence.FOUND
    if entry.resolve_after is not None:
        return JellyfinPresence.SEARCHING
    return JellyfinPresence.LOST


def _versions(features: list[LedgerEntry]) -> tuple[VersionGroupView, ...]:
    """同一集兩個以上正片的那幾組。

    **以所在的資料夾分組**，不只看季集：兩條 Route 是兩個 Jellyfin 媒體庫、兩個條目，版本選單
    只合併同一個資料夾裡的（code-review 抓到的）。

    版本名讀 Jellyfin 回的 `MediaSources[].Name`（反查時抄進帳本，`services/resolver.py`）。
    **不自己重算**：12.0 起那個名字是「去掉各版本檔名的共同前綴」剩下的部分，算法跟標題的
    標點有關，12.0 與 12.1 還不一樣（brief §7.7、§20.9）。Jellyfin 還沒收錄的那幾個沒有名字，
    畫面照實說。
    """
    groups: dict[tuple[str, int | None, int | None, int | None], list[VersionView]] = {}
    for entry in features:
        folder = str(PurePosixPath(entry.target_path).parent)
        key = (folder, entry.season, entry.episode_start, entry.episode_end)
        groups.setdefault(key, []).append(
            VersionView(
                name=entry.jellyfin_version_name,
                tags=Tags.model_validate(entry.tags_json).render() if entry.tags_json else "",
            )
        )
    return tuple(
        VersionGroupView(
            season=season, episode_start=start, episode_end=end, versions=tuple(versions)
        )
        for (_, season, start, end), versions in groups.items()
        if len(versions) > 1
    )
