"""「為什麼沒入庫」：一部作品（或其中一集）的答案收在一份（M5 票 10，plan §11.6〈分段〉第 4 段）。

答案原本散在五張表：季表（播了沒、入庫沒）、Job 與它的事件、開著的 Issue、RSS 那一側（綁了沒、
被排除了沒）、帳本（Jellyfin 認到了沒）。這一支一次讀齊，每一集收成 `EpisodeFacts`，結論交給
`domain.conclude`——**規則只在那裡一份**，這裡只負責「誰蓋到哪一集」。

**誰蓋到哪一集**：
- Job：它的計劃（含下載中的預估）說的季集，與季表同一個來源；計劃說不出（剛送單、送單失敗、
  待審而季集未定）就照發佈名猜（`plan.guess_from_title`，RSS 送單前比帳本用的同一支）。
- 猜不出集時退一步：發佈名只寫了季（整季合集）是那幾季播出了的每一集；連季都沒寫、或寫的季
  TMDB 沒有（Re:Zero 的第二季在 TMDB 併進了第一季）是整部作品播出了的每一集，第 0 季除外
  （`_Episodes.cover`）。說不出它不是哪一集，就不能說那一集沒人在處理，也不能讓它從回答裡消失。
- Feed Item：同一支猜法；它的 RSS Series 綁好了就帶著 Series 的季號與偏移去猜。
- 電影沒有季集：這部作品的每一筆 Job、每一筆 Feed Item 都蓋到它。
- 已入庫與已刪除的 Job 也算蓋到，列在回答裡（「有人送過、後來刪了」也是答案），結論不看它們。

**一般使用者看得到的範圍**（brief §19「M5 的方向」⑦）：只有自己送的 Job；Issue 與 RSS 那一側
是管理員的頁面（`api/gate.py`），對他是 `None`。**結論照全部的事實算**：季表本來就對每個人說
「下載中」「卡住」，結論只是同一件事說得更細，不會多洩漏哪一筆 Job 是誰的。RSS 那一側推出的
結論（待綁定、被排除）在季表上只是「缺」，一般使用者因此多知道一個類別，但看不到是哪個 Feed、
哪一條規則。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    CLAIMING_ACTIONS,
    SUBJECT_OF,
    EpisodeFacts,
    EpisodeStatus,
    FeedItemStatus,
    IssueStatus,
    IssueSubject,
    IssueType,
    JellyfinPresence,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    Role,
    WhyNot,
    WhyNotRefusal,
    conclude,
    overall,
)
from berth.domain import (
    PlanItem as PlannedFile,
)
from berth.models import Issue, Job, Media, Plan, PlanItem, RssItem, RssSeries, parse_media_id
from berth.models import media_id as build_media_id
from berth.models.types import utcnow
from berth.parser import parse_release
from berth.services.commands import Effect, command
from berth.services.inventory import Covers, Holdings, LedgerFileView, episodes_of, read_holdings
from berth.services.jobs import JobEventView, read_job_events, series_id_of
from berth.services.plan import guess_from_title

#: 每一筆 Job 帶最後幾筆事件。整條時間線在 `GET /jobs/{hash}/events`。
EVENTS_PER_JOB = 5
#: 一份答案最多列幾筆 Job、幾筆 Feed Item（最新的在前）。上百集的作品每一集一筆時不把整份塞進去。
JOB_LIMIT = 50
ITEM_LIMIT = 50
#: 往回看幾筆 Feed Item。每一筆要猜一次季集，追了好幾年的 Series 不必全部猜過。
ITEM_SCAN = 500

#: 電影那一格的鍵：它沒有季集。
_MOVIE = None

type _Key = tuple[int, int] | None


class WhyNotRejectedError(Exception):
    """「為什麼沒入庫」在讀任何東西之前就停下來了（`explain` 的兩種，加上 API 的季集檢查）。"""

    def __init__(self, reason: WhyNotRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class EpisodeVerdict:
    """一集（電影是整部）的結論與蓋到它的那幾筆。"""

    #: 電影是 `None`。
    season: int | None
    episode: int | None
    #: 季表上那一格（作品頁的五種）。電影是 `None`。
    status: EpisodeStatus | None
    conclusion: WhyNot
    #: 蓋到它的 Job（這個人看得到的那幾筆）。
    jobs: tuple[str, ...]
    #: 蓋到它的 Feed Item id。看不到 RSS 那一側的人是空的。
    items: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SeasonTally:
    """季表的一季：播出了幾集、其中入庫了幾集（與作品頁同一個分母）。"""

    season_number: int
    aired: int
    imported: int


@dataclass(frozen=True, slots=True)
class WhyNotJob:
    hash: str
    name: str
    state: JobState
    trigger: JobTrigger
    #: 失敗時服務回的原文。
    error: str
    #: qBittorrent 自己的狀態字串，原樣。
    client_state: str
    progress: float
    added_at: datetime
    #: 最後幾筆事件，最舊的在前（`EVENTS_PER_JOB`）。
    events: tuple[JobEventView, ...]


@dataclass(frozen=True, slots=True)
class WhyNotIssue:
    id: int
    type: IssueType
    job_hash: str | None
    detected_at: datetime


@dataclass(frozen=True, slots=True)
class WhyNotSeries:
    """與這部作品有關的 RSS Series：綁到它的，或待綁定而候選裡有它的。"""

    id: int
    #: 長出它的那一筆 Item 的標題，原樣。
    title: str
    #: 綁到這部作品了；`False` 是還在待綁定。
    bound: bool
    #: 第一批確認過了沒。
    confirmed: bool
    #: 這一層的排除條件。
    exclude: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WhyNotItem:
    id: int
    series_id: int | None
    title: str
    status: FeedItemStatus
    #: 照發佈名猜的季集；猜不出是 `None`。
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 上一次送單被拒的原文。
    error: str
    #: `excluded` / `duplicate` 的那一條理由（`domain.SkipReason` 的 JSON）。
    #: 值的型別逐條不同，所以是 Any。
    skip: dict[str, Any] | None
    job_hash: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class WhyNotRss:
    series: tuple[WhyNotSeries, ...]
    items: tuple[WhyNotItem, ...]


@dataclass(frozen=True, slots=True)
class WhyNotView:
    media_id: str
    kind: MediaKind
    title: str
    #: 問的是哪一集；問整部作品時兩個都是 `None`。
    season: int | None
    episode: int | None
    #: 問一集時是那一集的；問整部時是各集裡最前面的那一種（`domain.overall`）。
    conclusion: WhyNot
    seasons: tuple[SeasonTally, ...]
    #: 問一集時就是那一集。問整部時是**有事的**那幾集：已入庫、還沒播的不列（季表的數字說了），
    #: 特別篇（第 0 季）連「沒有來源」也不列——沒有人預期 Berth 自己去找它。
    episodes: tuple[EpisodeVerdict, ...]
    #: 蓋到 `episodes` 的 Job（含已入庫、已刪除的），最新的在前。一般使用者只有自己送的。
    jobs: tuple[WhyNotJob, ...]
    #: 開著的 Issue。一般使用者是 `None`（看不到）。
    issues: tuple[WhyNotIssue, ...] | None
    #: RSS 那一側。一般使用者是 `None`（看不到）。
    rss: WhyNotRss | None


@dataclass(slots=True)
class _Claims[T]:
    """每一個鍵（集，或電影的 `None`）被哪幾筆蓋到。"""

    by_key: dict[_Key, list[T]] = field(default_factory=dict)

    def add(self, keys: Iterable[_Key], row: T) -> None:
        for key in dict.fromkeys(keys):
            self.by_key.setdefault(key, []).append(row)

    def of(self, key: _Key) -> list[T]:
        return self.by_key.get(key, [])


@dataclass(frozen=True, slots=True)
class _Episodes:
    """這部作品認得的集，與「蓋到哪幾集」的退路（模組說明的那幾條）。"""

    movie: bool
    #: TMDB 快照上的每一集，播了沒都算。
    known: frozenset[tuple[int, int]]
    #: 每一季播出了的那幾集。
    aired_by_season: dict[int, list[tuple[int, int]]]

    def cover(
        self, planned: Iterable[Covers], title: str, guess: Callable[[], PlannedFile]
    ) -> list[_Key]:
        """計劃 → 照發佈名猜的集 → 發佈名寫的季 → 整部作品，取第一個說得出認得的集的。"""
        if self.movie:
            return [_MOVIE]
        # 猜要跑一次解析器：計劃說得出認得的集時就不猜。
        known = self._known(planned) or self._known([guess()])
        if known:
            return known
        release = parse_release(title)
        if release.season is not None:
            last = release.season_end or release.season
            numbers = range(release.season, last + 1)
            seasons = [self.aired_by_season.get(number, []) for number in numbers]
            if any(seasons):
                return [pair for season in seasons for pair in season]
        return [
            pair for number, season in self.aired_by_season.items() if number > 0 for pair in season
        ]

    def _known(self, rows: Iterable[Covers]) -> list[_Key]:
        """幾列季集裡 TMDB 認得的那幾集。"""
        return [pair for row in rows for pair in episodes_of(row) if pair in self.known]


@command(Effect.READ)
async def explain(
    session: AsyncSession,
    media_id: str,
    *,
    role: Role,
    user_id: int,
    episode: tuple[int, int] | None = None,
) -> WhyNotView:
    """這部作品（或 `episode` 那一集）為什麼沒入庫。只讀資料庫，不問 TMDB、不問任何服務。

    拒絕：`media_missing`（Berth 沒有這部作品）、`not_a_series`（問電影的一集）。
    """
    parsed = parse_media_id(media_id)
    media = await session.get(Media, build_media_id(*parsed)) if parsed is not None else None
    if media is None:
        raise WhyNotRejectedError(WhyNotRefusal.MEDIA_MISSING, media_id)
    if episode is not None and media.kind is MediaKind.MOVIE:
        raise WhyNotRejectedError(WhyNotRefusal.NOT_A_SERIES, media_id)

    snapshot = media.snapshot()
    # 解析器要的是真的從 TMDB 抓過的那一份（`Media.stored_snapshot`），沒抓過是 `None`。
    fetched = media.stored_snapshot()
    holdings = await read_holdings(session, media, snapshot)
    keys = _keys(media, snapshot, episode)
    today = utcnow().date()
    episodes = _episodes(media, snapshot, today)

    jobs = list(
        await session.scalars(
            select(Job).where(Job.media_id == media.id).order_by(Job.added_at.desc(), Job.hash)
        )
    )
    series = await _series(session, media.id)
    job_claims = await _job_claims(session, media, fetched, jobs, series, episodes)
    items = await _items(session, series)
    item_claims, guesses = _item_claims(media, fetched, items, series, episodes)

    admin = role is Role.ADMIN
    visible = {job.hash for job in jobs if admin or job.user_id == user_id}
    statuses = _statuses(holdings)
    aired = _aired(snapshot, today)

    verdicts: list[EpisodeVerdict] = []
    for key in keys:
        claimed_jobs = job_claims.of(key)
        claimed_items = item_claims.of(key)
        found = conclude(
            EpisodeFacts(
                imported=_imported(holdings, key),
                in_jellyfin=_in_jellyfin(holdings, key),
                jobs=frozenset(job.state for job in claimed_jobs),
                items=frozenset(item.status for item in claimed_items if not _rejected(item)),
                send_rejected=any(_rejected(item) for item in claimed_items),
                aired=aired(key),
            )
        )
        if episode is None and not _worth_listing(key, found):
            continue
        verdicts.append(
            EpisodeVerdict(
                season=None if key is None else key[0],
                episode=None if key is None else key[1],
                status=None if key is None else statuses.get(key),
                conclusion=found,
                jobs=tuple(job.hash for job in claimed_jobs if job.hash in visible),
                items=tuple(item.id for item in claimed_items) if admin else (),
            )
        )

    conclusion = overall(verdict.conclusion for verdict in verdicts) or _all_settled(
        snapshot, today
    )
    shown_jobs = _pick(jobs, verdicts, visible)
    return WhyNotView(
        media_id=media.id,
        kind=media.kind,
        title=snapshot.title,
        season=None if episode is None else episode[0],
        episode=None if episode is None else episode[1],
        conclusion=conclusion,
        seasons=tuple(
            SeasonTally(season_number=row.season_number, aired=row.aired, imported=row.imported)
            for row in holdings.seasons
        ),
        episodes=tuple(verdicts),
        jobs=tuple([await _job(session, job) for job in shown_jobs]),
        issues=(
            await _issues(session, holdings, verdicts, shown_jobs, series, items) if admin else None
        ),
        rss=_rss(series, items, guesses, verdicts) if admin else None,
    )


# --- 哪幾集 ---------------------------------------------------------------------


def _keys(media: Media, snapshot: MediaSnapshot, episode: tuple[int, int] | None) -> list[_Key]:
    if media.kind is MediaKind.MOVIE:
        return [_MOVIE]
    if episode is not None:
        return [episode]
    return [
        (season.season_number, row.episode_number)
        for season in snapshot.seasons
        for row in season.episodes
    ]


def _on_air(day: date | None, today: date) -> bool:
    """以伺服器的 UTC 日期判定（與季表同一個規矩）。TMDB 還沒有日期的不算播出了。"""
    return day is not None and day <= today


def _episodes(media: Media, snapshot: MediaSnapshot, today: date) -> _Episodes:
    """整季合集蓋到的是那一季播出了的集——還沒播的那一集不會在合集裡。"""
    return _Episodes(
        movie=media.kind is MediaKind.MOVIE,
        known=frozenset(
            (season.season_number, row.episode_number)
            for season in snapshot.seasons
            for row in season.episodes
        ),
        aired_by_season={
            season.season_number: [
                (season.season_number, row.episode_number)
                for row in season.episodes
                if _on_air(row.air_date, today)
            ]
            for season in snapshot.seasons
        },
    )


def _worth_listing(key: _Key, found: WhyNot) -> bool:
    """問整部時列不列這一集。電影只有一格，永遠列。"""
    if key is None:
        return True
    if found in {WhyNot.IMPORTED, WhyNot.UNAIRED}:
        return False
    return not (key[0] == 0 and found is WhyNot.NO_SOURCE)


def _all_settled(snapshot: MediaSnapshot, today: date) -> WhyNot:
    """整部劇集沒有一集有事：播出了的都在（或一集都還沒播）。"""
    anything_aired = any(
        _on_air(row.air_date, today)
        for season in snapshot.seasons
        if season.season_number > 0
        for row in season.episodes
    )
    return WhyNot.IMPORTED if anything_aired else WhyNot.UNAIRED


def _aired(snapshot: MediaSnapshot, today: date) -> Callable[[_Key], bool]:
    dates = {
        (season.season_number, row.episode_number): row.air_date
        for season in snapshot.seasons
        for row in season.episodes
    }

    def aired(key: _Key) -> bool:
        if key is None:
            # 電影：TMDB 沒給上映日的當作已上映——問的人多半就是因為它出了。
            return snapshot.first_air_date is None or _on_air(snapshot.first_air_date, today)
        return _on_air(dates.get(key), today)

    return aired


# --- 帳本與季表 ---------------------------------------------------------------------


def _statuses(holdings: Holdings) -> dict[tuple[int, int], EpisodeStatus]:
    return {
        (season.season_number, row.episode_number): row.status
        for season in holdings.seasons
        for row in season.episodes
    }


def _features(holdings: Holdings, key: _Key) -> list[LedgerFileView]:
    features = [entry for entry in holdings.files if entry.action is PlanAction.IMPORT]
    if key is None:
        return features
    return [entry for entry in features if key in set(episodes_of(entry))]


def _imported(holdings: Holdings, key: _Key) -> bool:
    return bool(_features(holdings, key))


def _in_jellyfin(holdings: Holdings, key: _Key) -> bool:
    return any(entry.presence is JellyfinPresence.FOUND for entry in _features(holdings, key))


# --- 誰蓋到哪一集 ---------------------------------------------------------------------


async def _job_claims(
    session: AsyncSession,
    media: Media,
    fetched: MediaSnapshot | None,
    jobs: Sequence[Job],
    series: Sequence[RssSeries],
    episodes: _Episodes,
) -> _Claims[Job]:
    planned: dict[str, list[PlanItem]] = {}
    if jobs:
        rows = await session.execute(
            select(Plan.job_hash, PlanItem)
            .join(PlanItem, PlanItem.plan_id == Plan.id)
            .where(
                Plan.job_hash.in_([job.hash for job in jobs]),
                PlanItem.action.in_(CLAIMING_ACTIONS),
            )
        )
        for job_hash, item in rows.tuples():
            planned.setdefault(job_hash or "", []).append(item)
    by_id = {row.id: row for row in series}
    claims = _Claims[Job]()
    for job in jobs:
        found = series_id_of(job)

        def guess(job: Job = job, found: int | None = found) -> PlannedFile:
            return guess_from_title(
                job.name,
                snapshot=fetched,
                series=by_id.get(found) if found is not None else None,
                published=job.published_at,
            )

        claims.add(episodes.cover(planned.get(job.hash, ()), job.name, guess), job)
    return claims


async def _series(session: AsyncSession, media_id: str) -> list[RssSeries]:
    """綁到這部作品的，加上待綁定而候選裡有它的。"""
    rows = await session.scalars(
        select(RssSeries)
        .where(or_(RssSeries.media_id == media_id, RssSeries.media_id.is_(None)))
        .order_by(RssSeries.id)
    )
    return [
        row for row in rows if row.media_id == media_id or media_id in (row.candidates_json or [])
    ]


async def _items(session: AsyncSession, series: Sequence[RssSeries]) -> list[RssItem]:
    if not series:
        return []
    return list(
        await session.scalars(
            select(RssItem)
            .where(RssItem.series_id.in_([row.id for row in series]))
            .order_by(RssItem.seen_at.desc(), RssItem.id.desc())
            .limit(ITEM_SCAN)
        )
    )


def _item_claims(
    media: Media,
    fetched: MediaSnapshot | None,
    items: Sequence[RssItem],
    series: Sequence[RssSeries],
    episodes: _Episodes,
) -> tuple[_Claims[RssItem], dict[int, PlannedFile]]:
    by_id = {row.id: row for row in series}
    claims = _Claims[RssItem]()
    guesses: dict[int, PlannedFile] = {}
    for item in items:
        owner = by_id.get(item.series_id) if item.series_id is not None else None
        guess = guess_from_title(
            item.title,
            snapshot=fetched,
            # 待綁定的 Series 還沒有季號與偏移：那是綁定時才定的。
            series=owner if owner is not None and owner.media_id == media.id else None,
            published=item.published_at,
        )
        guesses[item.id] = guess
        claims.add(episodes.cover((), item.title, _given(guess)), item)
    return claims, guesses


# --- 組回答 ---------------------------------------------------------------------


def _given(guess: PlannedFile) -> Callable[[], PlannedFile]:
    """已經猜好的那一份（Feed Item 每一筆都要猜：回答裡要列出它猜到的季集）。"""
    return lambda: guess


def _rejected(item: RssItem) -> bool:
    """綁好了、還沒送成，而上一次送單被拒。"""
    return item.status is FeedItemStatus.MATCHED and bool(item.error)


def _pick(jobs: Sequence[Job], verdicts: Sequence[EpisodeVerdict], visible: set[str]) -> list[Job]:
    """蓋到列出的那幾集、這個人看得到的 Job，最新的在前。"""
    wanted = {job_hash for verdict in verdicts for job_hash in verdict.jobs}
    return [job for job in jobs if job.hash in wanted and job.hash in visible][:JOB_LIMIT]


async def _job(session: AsyncSession, job: Job) -> WhyNotJob:
    events = await read_job_events(session, job.hash)
    return WhyNotJob(
        hash=job.hash,
        name=job.name,
        state=job.state,
        trigger=job.trigger,
        error=job.error,
        client_state=job.client_state,
        progress=job.progress,
        added_at=job.added_at,
        events=events[-EVENTS_PER_JOB:],
    )


async def _issues(
    session: AsyncSession,
    holdings: Holdings,
    verdicts: Sequence[EpisodeVerdict],
    jobs: Sequence[Job],
    series: Sequence[RssSeries],
    items: Sequence[RssItem],
) -> tuple[WhyNotIssue, ...]:
    """開著的 Issue：列出的 Job 的、列出那幾集帳本的、相關 RSS Series 與蓋到那幾集的 Feed Item
    所在 Feed 的。磁碟、TVDB 那種整台 Berth 的 Issue 不在這裡（健康頁說它們）。"""
    ledger_ids = [
        entry.id
        for verdict in verdicts
        for entry in _features(
            holdings,
            None if verdict.season is None else (verdict.season, verdict.episode or 0),
        )
    ]
    wanted = {item_id for verdict in verdicts for item_id in verdict.items}
    feeds = {str(item.feed_id) for item in items if item.id in wanted}
    rows = await session.scalars(
        select(Issue)
        .where(
            Issue.status == IssueStatus.OPEN,
            or_(
                Issue.job_hash.in_([job.hash for job in jobs]),
                Issue.ledger_id.in_(ledger_ids),
                Issue.type.in_(_about(IssueSubject.RSS_SERIES))
                & Issue.subject.in_([str(row.id) for row in series]),
                Issue.type.in_(_about(IssueSubject.RSS_FEED)) & Issue.subject.in_(feeds),
            ),
        )
        .order_by(Issue.detected_at.desc(), Issue.id.desc())
    )
    return tuple(
        WhyNotIssue(id=row.id, type=row.type, job_hash=row.job_hash, detected_at=row.detected_at)
        for row in rows
    )


def _about(subject: IssueSubject) -> list[IssueType]:
    return [kind for kind, found in SUBJECT_OF.items() if found is subject]


def _rss(
    series: Sequence[RssSeries],
    items: Sequence[RssItem],
    guesses: dict[int, PlannedFile],
    verdicts: Sequence[EpisodeVerdict],
) -> WhyNotRss:
    wanted = {item_id for verdict in verdicts for item_id in verdict.items}
    return WhyNotRss(
        series=tuple(
            WhyNotSeries(
                id=row.id,
                title=row.title_raw,
                bound=row.media_id is not None,
                confirmed=row.confirmed,
                exclude=tuple(row.exclude_json or ()),
            )
            for row in series
        ),
        items=tuple(
            WhyNotItem(
                id=item.id,
                series_id=item.series_id,
                title=item.title,
                status=item.status,
                season=guesses[item.id].season,
                episode_start=guesses[item.id].episode_start,
                episode_end=guesses[item.id].episode_end,
                error=item.error,
                skip=item.skip_json,
                job_hash=item.job_hash,
                published_at=item.published_at,
            )
            for item in items
            if item.id in wanted
        )[:ITEM_LIMIT],
    )
