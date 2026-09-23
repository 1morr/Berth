"""媒體庫：Jellyfin 的整面牆與 Berth 經手的作品在上面的樣子（M1.5 票 03、票 13）。

**名字叫 inventory 不叫 library**：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端的
媒體庫，而這一支盤點的是「那個媒體庫裡有什麼、Berth 經手的那幾部走到哪了」（UI 顯示「媒體庫」）。

同一件事有兩種切法，所以兩個入口住在一起、共用同一組分類：

- **一個 Jellyfin 媒體庫的牆**（`read_wall`，`.scratch/m1.5/library-shape.md`）：牆上是
  Jellyfin 那一頁的每一部作品，包括不是 Berth 入庫的；分頁與排序照 Jellyfin。Berth 經手的作品
  （指向這個媒體庫的每一條 Route 上有 Job 的，加上帳本落在它們底下的）疊到牆上那一格；
  Jellyfin 裡還沒有的另列一份。讀 Jellyfin 一律經過權限閘門（`services/jellyfin_access.py`）。
- **一部作品的內容**（`read_holdings`，Media 詳情頁）：各集狀態、帳本裡的每一個檔案、對不到的
  檔案與多版本並存。**跨 Route**：詳情頁回答的是一部作品的事。

**判定規則全部在這裡**，前端只照畫（`JobOut.retryable` 的同一個規矩）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin import JellyfinItem
from berth.domain import (
    REMATCH_ACTIONS,
    SETTLED_PLANS,
    EpisodeSnapshot,
    EpisodeStatus,
    FileKind,
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
from berth.models import Job, JobFile, LedgerEntry, Media, Plan, PlanItem, Route, media_id
from berth.models.types import utcnow
from berth.services.jellyfin_access import (
    BrowsableLibrary,
    JellyfinAccess,
    WallQuery,
)
from berth.services.routes import owning_route, target_prefix
from berth.services.watch import WatchState, watch_state

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


# --- 一個 Jellyfin 媒體庫的牆 -------------------------------------------------

#: 牆一頁幾部；前端不能指定。原本照 jellyfin-web 的預設 `libraryPageSize` 取 100
#: （研究 library-browsing.md §7），M2 票 13 減半：100 格的牆量到 1,700 個 DOM 節點、
#: 222 個 Tab 停留點，而每一格帶著兩三個控制項。
PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class Tracking:
    """Berth 經手的一部作品在這個媒體庫上的入庫狀態：疊在牆上那一格的那一層（票 13 的判定）。"""

    status: InventoryStatus
    #: 劇集：已經播出的正片入庫了幾集（S00 不算）。電影：正片在不在（0 / 1）。
    imported: int
    #: 劇集：TMDB 上已經播出的正片集數（S00 不算，還沒播的不算）。電影一律是 1。
    aired: int
    #: 電影的正片有幾個版本（brief §7.7）。劇集的版本在詳情頁逐集列，這裡是 0。
    versions: int
    #: medium 自動入庫、掛著 audit 的檔案數，這部作品在這個媒體庫的每一筆 Job 加總
    #: （brief §6.5、票 15）。
    audits: int


@dataclass(frozen=True, slots=True)
class InventoryCard:
    """牆上（或「還沒進 Jellyfin」那一份裡）的一格。"""

    #: `/media/:id` 要開的那一部。Jellyfin 的作品沒有 TMDB id、Berth 也不認得它時是空字串——
    #: 那一格只有 Jellyfin 的深連結（票 03）。
    media_id: str
    kind: MediaKind
    #: 顯示用標題。在 Jellyfin 裡的作品是 **Jellyfin 的名稱，兩格相同**（使用者拍板，brief §7.5）；
    #: 還沒進的是 TMDB `zh-TW` 那一輪與英文那一輪，畫面照 UI 語言挑（票 02）。
    title: str
    title_en: str
    year: int | None
    #: 還沒進 Jellyfin 的作品的 TMDB 海報，`zh-Hant` 與 `en` 兩輪（TMDB 的海報分語言，票 11）；
    #: 在 Jellyfin 裡的是空字串，海報看 `poster_tag`。
    poster_url: str
    poster_url_en: str
    #: 在 Jellyfin 裡的作品的 `ImageTags.Primary`：海報由 Berth 代理 Jellyfin 的圖，
    #: 網址由 API 那一層組（`api/jellyfin.image_url`，票 04）。還沒進 Jellyfin、或 Jellyfin
    #: 沒有圖時是空字串。
    poster_tag: str
    #: 在 Jellyfin 裡就是 `found`；還沒進的說得出還在找、找不到、沒有東西可以找。
    presence: JellyfinPresence
    #: 深連結要開的 Jellyfin 作品（Series 或 Movie）。還沒進 Jellyfin 時是空字串。
    jellyfin_item_id: str
    #: Berth 沒經手的作品是 `None`：牆上那一格不印任何狀態。
    tracking: Tracking | None
    #: 這位使用者看到哪了（票 05）。**只有 Jellyfin 那一頁的卡片有**：還沒進 Jellyfin 的沒有紀錄，
    #: `tracked` 裡在 Jellyfin 的那幾格來自整份清單，它不帶觀看紀錄（`library_index`）。
    watch: WatchState | None


@dataclass(frozen=True, slots=True)
class InventoryWall:
    library: BrowsableLibrary
    #: 1 起算。
    page: int
    page_size: int
    #: Jellyfin 說這個媒體庫一共有幾部（整份查詢的，不是這一頁的）。
    total: int
    #: Jellyfin 的這一頁。
    titles: tuple[InventoryCard, ...]
    #: 這個媒體庫上 Berth 經手的**每一部**，不分頁：畫面從這裡取「還沒進 Jellyfin」那一份
    #: （`presence` 不是 `found` 的）。「待審」「對不到」兩個篩選不在這裡：它們是審核佇列的子集
    #: （`services/review.library_queue`，M2 票 14）。
    tracked: tuple[InventoryCard, ...]


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
    #: 「修正」改得成哪幾種（brief §9.4，M2 票 08）：正片與特典是改指派 / 標記 extra / 忽略；
    #: 字幕跟著它的影片走，自己沒有修正入口（空的）。
    actions: tuple[PlanAction, ...]


@dataclass(frozen=True, slots=True)
class UnmatchedFileView:
    """對不到任何一集的檔案，與把它帶進來的那一筆 Job。"""

    rel_path: str
    job_hash: str
    job_name: str
    #: `POST /files/rematch` 的 `job_file_id`——與 Review Queue 的 `unmatched` 列指向同一個東西。
    job_file_id: int | None
    #: 改得成哪幾種（`REMATCH_ACTIONS`，依分類）。那一份 Plan 還沒定案（等審核）時是空的：
    #: 那時候改它是 Plan 編輯的事。
    actions: tuple[PlanAction, ...]


@dataclass(frozen=True, slots=True)
class VersionView:
    """同一集（或同一部電影）的一個版本。"""

    #: Jellyfin 版本選單上的名字（帳本的 `jellyfin_version_name`，同一個東西同一個詞）。
    #: **由 Jellyfin 算**（brief §7.7），反查到的那一刻抄進帳本；還沒收錄就是空字串。
    name: str
    #: 這個檔案的 Tags。還沒有 `name` 時畫面顯示它，並說明那是檔名的 tags 而不是版本名。
    tags: str
    #: 這個版本是哪一筆下載帶進來的（M2 票 04）。版本清單上的刪除按的就是那一筆——
    #: 多版本並存時「刪掉哪一個」在畫面上一定要指得明確。重新入庫那種沒有 Job 的是空字串。
    job_hash: str


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
    #: 這部作品停在 `review` 的下載筆數。`user` 碰到它只能等，畫面要說「等管理員審核」
    #: （plan §6、brief §11，M2 票 06）。
    awaiting_review: int


class Covers(Protocol):
    """帳本一筆或計劃一列：兩者都用 `season` / `episode_start` / `episode_end` 說它蓋到哪幾集。"""

    @property
    def season(self) -> int | None: ...

    @property
    def episode_start(self) -> int | None: ...

    @property
    def episode_end(self) -> int | None: ...


async def read_wall(
    session: AsyncSession,
    access: JellyfinAccess,
    library_id: str,
    *,
    page: int,
    query: WallQuery,
) -> InventoryWall:
    """一個媒體庫的一頁牆。媒體庫不在這個人的允許清單上時丟 `LibraryNotVisibleError`，
    而且在問 Jellyfin 或讀 Berth 的任何東西之前。

    `query` 只套在 Jellyfin 那一頁（票 06）：`tracked` 是 Berth 的清單，
    沒有 Jellyfin 的類型可以篩。
    """
    library = access.library(library_id)
    tracked = await _survey(session, library, await _routes(session), today=utcnow().date())
    start = (page - 1) * PAGE_SIZE
    # 拒絕（排序鍵不在選單上）在這一行就丟出，兩個請求都還沒送出去。
    page_request = access.page(library.id, start=start, limit=PAGE_SIZE, query=query)
    if tracked:
        jellyfin_page, index = await asyncio.gather(page_request, access.index(library.id))
    else:
        # 整份清單只為了比對 Berth 經手的作品；一部都沒有時一頁一個請求就夠。
        jellyfin_page, index = await page_request, ()

    match = _Matcher(tracked)
    in_jellyfin: dict[str, JellyfinItem] = {}
    for item in index:
        mine = match(item)
        if mine is not None:
            in_jellyfin.setdefault(mine.media.id, item)
    return InventoryWall(
        library=library,
        page=page,
        page_size=PAGE_SIZE,
        total=jellyfin_page.total,
        titles=tuple(_jellyfin_card(item, library, match(item)) for item in jellyfin_page.items),
        tracked=tuple(
            sorted(
                (_tracked_card(row, library, in_jellyfin.get(row.media.id)) for row in tracked),
                key=lambda card: (card.title.casefold(), card.media_id),
            )
        ),
    )


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
    items = list(
        await session.scalars(
            select(PlanItem).where(PlanItem.plan_id.in_(list(plans))).order_by(PlanItem.id)
        )
    )

    stuck: set[tuple[int, int]] = set()
    under_way: set[tuple[int, int]] = set()
    unmatched: list[UnmatchedFileView] = []
    kinds = await _file_kinds(
        session, [item.job_file_id for item in items if item.action is PlanAction.UNMATCHED]
    )
    for item in items:
        plan = plans[item.plan_id]
        job = jobs.get(plan.job_hash or "")
        if job is None:
            continue
        # 預估沒讀過檔案本身（brief §5.1），下載完成之後會重算一份。
        if item.action is PlanAction.UNMATCHED and plan.status is not PlanStatus.PREPLAN:
            decidable = (
                item.job_file_id is not None
                and plan.status in SETTLED_PLANS
                and job.state is not JobState.REMOVED
            )
            unmatched.append(
                UnmatchedFileView(
                    rel_path=item.rel_path,
                    job_hash=job.hash,
                    job_name=job.name,
                    job_file_id=item.job_file_id,
                    actions=(
                        REMATCH_ACTIONS[kinds.get(item.job_file_id, FileKind.OTHER)]
                        if decidable
                        else ()
                    ),
                )
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
        awaiting_review=sum(job.state is JobState.REVIEW for job in jobs.values()),
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


def _presence(features: Sequence[LedgerEntry]) -> JellyfinPresence:
    """一部**還沒在 Jellyfin 牆上找到**的作品，那一行說什麼（票 13 shape §5）。

    反查找到了某一集、甚至帳本記著 Series id，Jellyfin 的清單上卻沒有它，仍然是「還在找」：
    那一集的 id 不是作品的連結，而一條會 404 的連結比一句「還在掃描」更糟。
    """
    if not features:
        return JellyfinPresence.NONE
    if any(entry.resolve_after is not None or entry.jellyfin_item_id for entry in features):
        return JellyfinPresence.SEARCHING
    return JellyfinPresence.LOST


def _aired(episode: EpisodeSnapshot, today: date) -> bool:
    """以伺服器的 UTC 日期判定。TMDB 還沒有播出日的一集不算播出了。"""
    return episode.air_date is not None and episode.air_date <= today


async def _routes(session: AsyncSession) -> list[Route]:
    return list(await session.scalars(select(Route).order_by(Route.id)))


@dataclass(frozen=True, slots=True)
class _Tracked:
    """Berth 經手的一部作品，在一個媒體庫上。"""

    media: Media
    tracking: Tracking
    #: 帳本記下的 Jellyfin 作品 id：劇集是 Series，電影是 Movie。
    links: frozenset[str]
    #: 它不在 Jellyfin 牆上時那一行說什麼。
    presence: JellyfinPresence


class _Matcher:
    """Jellyfin 的一部作品是不是 Berth 經手的那一部。

    **不只看帳本的 Series id**（票 03）：反查找到了集卻還沒有 Series id 的作品，Jellyfin 那一端
    本來就帶著 TMDB id。帳本的 id 先比——Jellyfin 認錯 TMDB id 時，Berth 自己寫下的那一個才是對的。
    """

    def __init__(self, tracked: Sequence[_Tracked]) -> None:
        self._by_link = {link: row for row in tracked for link in row.links}
        self._by_tmdb = {str(row.media.tmdb_id): row for row in tracked}

    def __call__(self, item: JellyfinItem) -> _Tracked | None:
        found = self._by_link.get(item.id)
        if found is None and item.tmdb_id:
            found = self._by_tmdb.get(item.tmdb_id)
        return found


async def _survey(
    session: AsyncSession, library: BrowsableLibrary, routes: Sequence[Route], *, today: date
) -> list[_Tracked]:
    """這個媒體庫上 Berth 經手的作品：指向它的每一條 Route 上有 Job 的，加上帳本落在它們底下的。

    一個媒體庫可以有兩條 Route（brief §4.3），同一部作品合成一份。
    """
    mine = [row for row in routes if row.jellyfin_library_id == library.id]
    if not mine:
        return []
    jobs = list(
        await session.scalars(
            select(Job).where(Job.route_id.in_([row.id for row in mine]), Job.media_id.is_not(None))
        )
    )
    entries: dict[int, LedgerEntry] = {}
    for row in mine:
        for entry in await session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.media_id.is_not(None),
                LedgerEntry.target_path.startswith(target_prefix(row), autoescape=True),
            )
        ):
            # 前綴只是粗篩：`/data/library/tv/anime` 可能是另一條更深的 Route 的目標。
            if owning_route(entry.target_path, routes) in mine:
                entries[entry.id] = entry
    audits = await _audits(session, [job.hash for job in jobs])
    # **先分組、一次走完**：逐部作品去篩整張帳本是作品數 × 帳本列數，1,000 部 × 12 集在
    # 容器裡要 3 秒，一頁牆超過門檻的就是它（M2 票 11，研究 large-library.md）。
    jobs_of: dict[str, list[Job]] = {}
    for job in jobs:
        if job.media_id is not None:
            jobs_of.setdefault(job.media_id, []).append(job)
    entries_of: dict[str, list[LedgerEntry]] = {}
    for entry in sorted(entries.values(), key=lambda entry: entry.id):
        if entry.media_id is not None:
            entries_of.setdefault(entry.media_id, []).append(entry)
    titles = await session.scalars(select(Media).where(Media.id.in_(jobs_of.keys() | entries_of)))
    return [
        _tracked(
            media,
            jobs_of.get(media.id, []),
            entries_of.get(media.id, []),
            audits=audits,
            today=today,
        )
        for media in titles
    ]


def _jellyfin_card(
    item: JellyfinItem, library: BrowsableLibrary, mine: _Tracked | None
) -> InventoryCard:
    if mine is not None:
        target = mine.media.id
    elif item.tmdb_id.isdigit():
        target = media_id(library.kind, int(item.tmdb_id))
    else:
        target = ""
    return InventoryCard(
        media_id=target,
        kind=library.kind,
        title=item.name,
        title_en=item.name,
        year=item.year,
        poster_url="",
        poster_url_en="",
        poster_tag=item.primary_tag,
        presence=JellyfinPresence.FOUND,
        jellyfin_item_id=item.id,
        tracking=None if mine is None else mine.tracking,
        watch=None if item.user_data is None else watch_state(item.user_data),
    )


def _tracked_card(
    row: _Tracked, library: BrowsableLibrary, item: JellyfinItem | None
) -> InventoryCard:
    """Berth 經手的一部：在 Jellyfin 裡就是牆上那一格的樣子，還沒進就用 TMDB 的快照。"""
    if item is not None:
        return _jellyfin_card(item, library, row)
    snapshot = row.media.snapshot()
    return InventoryCard(
        media_id=row.media.id,
        kind=row.media.kind,
        title=snapshot.title or row.media.title_en,
        title_en=row.media.title_en,
        year=row.media.year,
        poster_url=snapshot.poster_url,
        # 舊快照沒有這一欄，落回另一輪（`services/media.py` 同一個理由）。
        poster_url_en=snapshot.poster_url_en or snapshot.poster_url,
        poster_tag="",
        presence=row.presence,
        jellyfin_item_id="",
        tracking=row.tracking,
        watch=None,
    )


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


def _tracked(
    media: Media,
    jobs: Sequence[Job],
    entries: Sequence[LedgerEntry],
    *,
    audits: dict[str, int],
    today: date,
) -> _Tracked:
    snapshot = media.snapshot()
    features = [entry for entry in entries if entry.action is PlanAction.IMPORT]
    if media.kind is MediaKind.MOVIE:
        imported, aired, versions = min(len(features), 1), 1, len(features)
    else:
        aired_set = aired_episodes(snapshot, today)
        covered = {pair for entry in features for pair in episodes_of(entry)}
        imported, aired, versions = len(covered & aired_set), len(aired_set), 0
    states = {job.state for job in jobs}
    links = {jellyfin_link(entry, media.kind) for entry in features}
    return _Tracked(
        media=media,
        tracking=Tracking(
            status=_status(states, has_features=bool(features), imported=imported, aired=aired),
            imported=imported,
            aired=aired,
            versions=versions,
            audits=sum(audits.get(job.hash, 0) for job in jobs),
        ),
        links=frozenset(link for link in links if link),
        presence=_presence(features),
    )


def jellyfin_link(entry: LedgerEntry, kind: MediaKind) -> str:
    """一筆帳本記下的、這部作品在 Jellyfin 的 id：劇集連 Series、電影連 Movie（票 13）。還沒反查到
    是空字串。媒體庫牆與 Media 詳情的觀看區（票 08）拿它比對 Jellyfin 的作品。"""
    return entry.jellyfin_series_id if kind is MediaKind.TV else entry.jellyfin_item_id


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
        actions=_LINKED_ACTIONS.get(entry.action, ()),
    )


#: 已入庫的檔案「修正」得成哪幾種（依它現在的處置）。正片與特典都是一個影片檔（`REMATCH_ACTIONS`
#: 對影片的那一格）；字幕跟著它的影片走（`services/rematch._sidecars`），自己沒有入口。
_LINKED_ACTIONS: dict[PlanAction, tuple[PlanAction, ...]] = {
    PlanAction.IMPORT: REMATCH_ACTIONS[FileKind.VIDEO],
    PlanAction.EXTRA: REMATCH_ACTIONS[FileKind.VIDEO],
}


async def _file_kinds(
    session: AsyncSession, ids: Sequence[int | None]
) -> dict[int | None, FileKind]:
    """`job_files` 上的分類（規劃時寫回去的）。沒有的當 `other`：寧可少一個選項，也不要讓一個
    不知道是什麼的檔案被指派成一集（同 `plan_view._kinds`）。"""
    wanted = [file_id for file_id in ids if file_id is not None]
    if not wanted:
        return {}
    found = await session.execute(select(JobFile.id, JobFile.kind).where(JobFile.id.in_(wanted)))
    return {file_id: kind for file_id, kind in found.tuples() if kind is not None}


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
                job_hash=entry.job_hash or "",
            )
        )
    return tuple(
        VersionGroupView(
            season=season, episode_start=start, episode_end=end, versions=tuple(versions)
        )
        for (_, season, start, end), versions in groups.items()
        if len(versions) > 1
    )
