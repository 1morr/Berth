"""RSS 的命令：Feed、RSS Series 的綁定、一輪輪詢（brief §15、plan §2.4、§3.2、§8.5、M3 票 08）。

一輪輪詢是 **抓 → 解析 → 找到或長出 RSS Series → 寫 Feed Item → 送出綁好的**。新長出的 RSS Series
先待綁定（`media_id = NULL`），它的 Item 是 `unbound`、留著不送；**長出來的那一輪就去認作品**
（`_auto_bind`，票 09）：Mikan 番組頁的中文名與開播日期、發佈名的標題骨幹去 TMDB 搜，規則在
`parser.binding.judge`。有把握、而且同類型只有一條啟用中的 Route 時自動綁上，否則留在待綁定並記下
理由與候選。自動綁定、人工綁定與之後 M5 的 AI 走的是同一支 `bind_series`。

**綁定是第一次通向磁碟的那一刻**，所以在這裡凍結資料夾名（plan §2.2、brief §4.5）：有人在場、
有一次明確確認（畫面在確認區塊重述那一串，`.scratch/m3/rss-shape.md` §3）。之後的送單沒有人按，
凍下去的必須是那個人看到的那一串。

**送單被拒不擋綁定**：綁定本身成立，那幾筆 Item 留在 `matched` 帶著原文，下一輪輪詢再送。
Route 紅燈、磁碟門檻這些是「現在送不了」，不是「綁錯了」。

這一票只做同一個 Feed 內的 GUID 去重（`(feed_id, guid)` 唯一）；跨 Feed 的 info hash 與帳本那一層
在票 10。同一個 torrent 從兩條路來時 `add_download` 本身以 info hash 認回同一筆 Job（plan §3.3）。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from berth.adapters.http import ServiceError
from berth.adapters.rss import FeedFetcher, FeedItem, mikan
from berth.domain import (
    BindReason,
    BindReasonCode,
    FeedItemStatus,
    FeedKind,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    RssRefusal,
    because,
    collection_type_for,
)
from berth.models import Media, Route, RssFeed, RssItem, RssSeries
from berth.models import media_id as build_media_id
from berth.models.types import utcnow
from berth.parser.binding import SeriesClues, could_be, judge, search_terms
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.discover import search_media
from berth.services.jobs import JobRejectedError, JobSource, actor_of, add_download, freeze
from berth.services.media import read_snapshot
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 「最近的 Feed Item」一次給幾筆（shape §5）。
RECENT_ITEMS = 50

#: 自動綁定時每一個搜尋詞取前幾筆去讀詳情。一部作品是 3 + 季數個 TMDB 請求，TMDB 的相關性排序
#: 多半把要的那一部放在最前面；搜尋詞最多三個（`parser.binding.MAX_SEARCHES`）。
SEARCH_DEPTH = 3

#: 自動綁定的 `bound_by`（`events.actor` 的 `system`）。
SYSTEM = actor_of(None)

#: 認得的來源：主機名 → 種類。這一票只認 Mikan 本站（shape §5）；Nyaa 與 acg.rip 在票 11。
_HOSTS: dict[str, FeedKind] = {"mikanani.me": FeedKind.MIKAN}


class RssRejectedError(Exception):
    """命令在做出任何改變之前就停下來了。`reason` 翻譯，`detail` 是原文或那一個 id。"""

    def __init__(self, reason: RssRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class FeedView:
    id: int
    name: str
    url: str
    kind: FeedKind
    interval_sec: int
    last_polled_at: datetime | None
    last_error: str
    #: 這個 Feed 長出了幾筆 Item。刪除的確認要說出會刪掉幾筆（shape §4）。
    items: int


@dataclass(frozen=True, slots=True)
class CandidateView:
    """待綁定那一列給人一鍵選的一部作品。"""

    id: str
    kind: MediaKind
    #: 兩輪標題（`JobView` 同一個規矩）。
    title: str
    title_en: str
    year: int | None


@dataclass(frozen=True, slots=True)
class SeriesView:
    id: int
    key: str
    title_raw: str
    mikan_bangumi_id: int | None
    mikan_subgroup_id: int | None
    #: `None` 是待綁定。
    media_id: str | None
    #: 作品名的兩輪（`JobView` 同一個規矩）；沒綁是空字串。
    media_title: str
    media_title_en: str
    route_id: int | None
    route_name: str
    season: int | None
    episode_offset: int | None
    bound_by: str
    #: 綁好之後還沒送出去的（待綁定時就是綁定之後會送出的那幾筆，確認區塊說的「將送出 N 集」）。
    waiting: int
    #: 自動綁定查到的結果（票 09）：`bound_by = system` 時是依據，待綁定時是為什麼。沒查過是空的。
    reasons: tuple[BindReason, ...]
    #: 給人一鍵選的作品，照搜尋結果的順序。
    candidates: tuple[CandidateView, ...]
    #: 這一次呼叫送出去了幾筆。只有 `bind_series` 回的那一份有意義，清單上一律是 0。
    submitted: int = 0


@dataclass(frozen=True, slots=True)
class ItemView:
    id: int
    feed_id: int
    title: str
    link: str
    published_at: datetime | None
    seen_at: datetime
    series_id: int | None
    status: FeedItemStatus
    job_hash: str
    error: str


@dataclass(frozen=True, slots=True)
class PollOutcome:
    #: 這一輪新寫下的 Item。
    items: int
    #: 這一輪新長出的 RSS Series。
    series: int
    #: 其中自動綁上的。
    bound: int
    #: 這一輪送出去的。
    submitted: int


def kind_of(url: str) -> FeedKind | None:
    """網址 → 來源種類。不是 http(s) 或主機不認得是 `None`。"""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower().removeprefix("www.")
    return _HOSTS.get(host)


# --- Feed ---------------------------------------------------------------


@command(Effect.READ)
async def list_feeds(session: AsyncSession) -> tuple[FeedView, ...]:
    grouped = await session.execute(select(RssItem.feed_id, func.count()).group_by(RssItem.feed_id))
    counts: dict[int, int] = dict(grouped.tuples().all())
    rows = await session.scalars(select(RssFeed).order_by(RssFeed.created_at, RssFeed.id))
    return tuple(_feed_view(row, counts.get(row.id, 0)) for row in rows)


@command(Effect.REVERSIBLE, inverse="rss.delete_feed")
async def add_feed(session: AsyncSession, *, url: str, name: str = "") -> FeedView:
    """加一個 Feed。不當場輪詢——畫面上那一顆「立即輪詢」與背景迴圈會做，這一支只記下來。"""
    url = url.strip()
    kind = kind_of(url)
    if kind is None:
        raise RssRejectedError(RssRefusal.FEED_UNSUPPORTED, url)
    if await session.scalar(select(RssFeed.id).where(RssFeed.url == url)) is not None:
        raise RssRejectedError(RssRefusal.FEED_DUPLICATE, url)
    row = RssFeed(name=name.strip() or _default_name(url), url=url, kind=kind)
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise RssRejectedError(RssRefusal.FEED_DUPLICATE, url) from exc
    return _feed_view(row, 0)


@command(Effect.REVERSIBLE, inverse="rss.add_feed")
async def delete_feed(session: AsyncSession, feed_id: int) -> int:
    """刪 Feed 連它的 Item 一起刪，RSS Series 與綁定留著（shape §4）。回刪掉幾筆 Item。

    可逆的根據：重新加回同一個網址會重新長出 Item，已經送過的由 `add_download` 以 info hash
    認回同一筆 Job，不重送。
    """
    row = await session.get(RssFeed, feed_id)
    if row is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    items = await session.scalar(
        select(func.count()).select_from(RssItem).where(RssItem.feed_id == feed_id)
    )
    # 外鍵的 `CASCADE` 也會刪，但 ORM 不知道；明刪一次，同一個 session 裡讀回來才是對的。
    await session.execute(delete(RssItem).where(RssItem.feed_id == feed_id))
    await session.delete(row)
    await session.commit()
    return int(items or 0)


def _default_name(url: str) -> str:
    return urlsplit(url).hostname or url


def _feed_view(row: RssFeed, items: int) -> FeedView:
    return FeedView(
        id=row.id,
        name=row.name,
        url=row.url,
        kind=row.kind,
        interval_sec=row.interval_sec,
        last_polled_at=row.last_polled_at,
        last_error=row.last_error,
        items=items,
    )


# --- 輪詢 ---------------------------------------------------------------


@command(Effect.REVERSIBLE)
async def poll_due(
    session: AsyncSession, factory: ServiceClientFactory, *, now: datetime | None = None
) -> int:
    """到時間的每一個 Feed 各輪一次（`rss_poller` 的一輪，plan §3.2）。回輪了幾個。

    **一個 Feed 爆掉不拖累其他的**：非預期的例外記 log、寫進那一列的 `last_error`，接著輪下一個。
    """
    moment = now or utcnow()
    polled = 0
    for feed_id, last, interval in (
        await session.execute(select(RssFeed.id, RssFeed.last_polled_at, RssFeed.interval_sec))
    ).all():
        if last is not None and moment - last < timedelta(seconds=interval):
            continue
        try:
            await poll_feed(session, factory, feed_id, now=moment)
        except Exception as failure:
            await session.rollback()
            logger.exception("an rss feed round failed; the other feeds go on")
            await _note_failure(session, feed_id, moment, f"{type(failure).__name__}: {failure}")
        polled += 1
    return polled


async def _note_failure(session: AsyncSession, feed_id: int, moment: datetime, detail: str) -> None:
    row = await session.get(RssFeed, feed_id)
    if row is None:
        return
    row.last_polled_at = moment
    row.last_error = detail
    await session.commit()


@command(Effect.REVERSIBLE)
async def poll_feed(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed_id: int,
    *,
    now: datetime | None = None,
) -> PollOutcome:
    """一個 Feed 的一輪。抓不到 Feed 時失敗記在那一列，不丟例外（畫面上的「立即輪詢」照樣回 200）。

    可逆但沒有單一反向命令：它長出的 Item 與 Series 是紀錄，送出去的 Job 有自己的刪除範圍。
    """
    moment = now or utcnow()
    feed = await session.get(RssFeed, feed_id)
    if feed is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    fetcher = factory.rss()
    bound = submitted = 0
    try:
        try:
            found = _parse(feed.kind, await fetcher.fetch(feed.url))
        except ServiceError as exc:
            feed.last_polled_at = moment
            feed.last_error = message(exc)
            await session.commit()
            logger.warning(
                "rss feed could not be fetched", extra={"feed": feed.id, "error": feed.last_error}
            )
            return PollOutcome(items=0, series=0, bound=0, submitted=0)
        items, grown, skipped = await _record(session, fetcher, feed, found, moment)
        feed.last_polled_at = moment
        feed.last_error = skipped
        await session.commit()
        # 番組頁要同一個 fetcher 抓，所以在它關掉之前認。
        for series_id in grown:
            sent = await _auto_bind(session, factory, fetcher, series_id)
            if sent is not None:
                bound += 1
                submitted += sent
    finally:
        await fetcher.aclose()
    submitted += await _submit_waiting(session, factory, RssItem.feed_id == feed_id)
    return PollOutcome(items=items, series=len(grown), bound=bound, submitted=submitted)


def _parse(kind: FeedKind, content: bytes) -> tuple[FeedItem, ...]:
    """種類 → 那一站的 mapper。"""
    match kind:
        case FeedKind.MIKAN:
            return mikan.parse_feed(content)


async def _record(
    session: AsyncSession,
    fetcher: FeedFetcher,
    feed: RssFeed,
    found: tuple[FeedItem, ...],
    moment: datetime,
) -> tuple[int, list[int], str]:
    """寫下這一輪新看到的 Item。回（新 Item 數、新 Series 的 id、跳過的那幾筆的原文）。

    **舊的先寫**：feed 是新的在前，送單照寫入順序走，第 11 集先於第 12 集進 qBittorrent。
    認不出 RSS Series 的那一筆（單集頁抓不到、改版了）**不寫**：寫了就是見過，下一輪不會再試。
    """
    seen = set(
        await session.scalars(
            select(RssItem.guid).where(
                RssItem.feed_id == feed.id, RssItem.guid.in_([item.guid for item in found])
            )
        )
    )
    items = 0
    grown: list[int] = []
    skipped: list[str] = []
    for item in reversed(found):
        if item.guid in seen:
            continue
        try:
            key = await _series_key(fetcher, feed.kind, item)
        except _UnkeyedError as unkeyed:
            skipped.append(str(unkeyed))
            continue
        series, created = await _series(session, key, item)
        if created:
            grown.append(series.id)
        session.add(
            RssItem(
                feed_id=feed.id,
                guid=item.guid,
                title=item.title,
                link=item.link,
                torrent_url=item.torrent_url,
                info_hash=item.info_hash,
                published_at=item.published_at,
                seen_at=moment,
                series_id=series.id,
                status=FeedItemStatus.UNBOUND
                if series.media_id is None
                else FeedItemStatus.MATCHED,
            )
        )
        seen.add(item.guid)
        items += 1
    await session.flush()
    detail = f"{len(skipped)} item(s) skipped: {skipped[0]}" if skipped else ""
    return items, grown, detail


class _UnkeyedError(Exception):
    """認不出這一筆屬於哪一個 RSS Series。訊息是原因（英文原文）。"""


async def _series_key(fetcher: FeedFetcher, kind: FeedKind, item: FeedItem) -> str:
    """這一筆屬於哪一個 RSS Series 的鍵（plan §2.4）。認不出來丟 `_UnkeyedError`。

    Mikan 的鍵（番組 id, 字幕組 id）不在 feed 裡，要抓單集頁（brief §20.12）。
    """
    match kind:
        case FeedKind.MIKAN:
            try:
                page = await fetcher.fetch(item.link)
            except ServiceError as exc:
                raise _UnkeyedError(f"episode page: {message(exc)}") from exc
            pair = mikan.series_key(page.decode("utf-8", errors="replace"))
            if pair is None:
                raise _UnkeyedError(f"episode page has no RSS link: {item.link}")
            return f"mikan:{pair[0]}:{pair[1]}"


async def _series(session: AsyncSession, key: str, item: FeedItem) -> tuple[RssSeries, bool]:
    """找到或長出這個鍵的 RSS Series。回（那一列, 是不是這一輪長出來的）。"""
    row = await session.scalar(select(RssSeries).where(RssSeries.key == key))
    if row is not None:
        return row, False
    _, bangumi, subgroup = key.split(":")
    row = RssSeries(
        key=key,
        mikan_bangumi_id=int(bangumi),
        mikan_subgroup_id=int(subgroup),
        title_raw=item.title,
    )
    session.add(row)
    await session.flush()
    return row, True


async def _submit_waiting(
    session: AsyncSession, factory: ServiceClientFactory, scope: ColumnElement[bool]
) -> int:
    """把 `scope` 裡綁好而還沒送的 Item（`matched`）送出去，舊的先。回送成了幾筆。"""
    rows = list(
        await session.scalars(
            select(RssItem)
            .where(RssItem.status == FeedItemStatus.MATCHED, scope)
            .order_by(RssItem.published_at, RssItem.id)
        )
    )
    sent = 0
    for item in rows:
        sent += await _submit(session, factory, item)
    return sent


async def _submit(session: AsyncSession, factory: ServiceClientFactory, item: RssItem) -> int:
    """送一筆。成了是 `downloaded` 加 Job 的 hash；被拒留在 `matched` 帶著原文。回 1 或 0。"""
    series = await session.get(RssSeries, item.series_id) if item.series_id is not None else None
    item_id = item.id
    if series is None or series.media_id is None:
        return 0
    if series.route_id is None:
        item.error = f"{RssRefusal.ROUTE_MISSING}: the series has no route"
        await session.commit()
        return 0
    try:
        outcome = await add_download(
            session,
            factory,
            source=JobSource(url=item.torrent_url, title=item.title, info_hash=item.info_hash),
            media_id=series.media_id,
            route_id=series.route_id,
            user_id=None,
            trigger=JobTrigger.RSS,
            trigger_ref=str(series.id),
            grounds=_reasons(series) if series.bound_by == SYSTEM else (),
        )
    except JobRejectedError as refusal:
        # `add_download` 可能 rollback 過，那一列要重讀。
        row = await session.get(RssItem, item_id)
        if row is not None:
            row.error = f"{refusal.reason}: {refusal.detail}" if refusal.detail else refusal.reason
            await session.commit()
        logger.info("rss item not sent", extra={"item": item_id, "reason": refusal.reason.value})
        return 0
    row = await session.get(RssItem, item_id)
    if row is None:
        return 0
    row.status = FeedItemStatus.DOWNLOADED
    row.job_hash = outcome.job.hash
    row.error = ""
    await session.commit()
    return 1


# --- 自動綁定 -----------------------------------------------------------


class _LookupError(Exception):
    """番組頁或 TMDB 這一次查不到。訊息是原文（英文），進 `lookup_failed` 的 `detail`。"""


async def _auto_bind(
    session: AsyncSession, factory: ServiceClientFactory, fetcher: FeedFetcher, series_id: int
) -> int | None:
    """第一次見到的 RSS Series 去 TMDB 認作品（brief §15「綁定」、票 09）。

    綁上了回送出幾筆，沒綁是 `None`。**只在長出來的那一輪做**：查不到（Mikan 或 TMDB 連不上）也
    不在之後每一輪重試——那會讓一個壞掉的番組頁每 15 分鐘打一次；留在待綁定、理由寫
    `lookup_failed`，人手上有搜尋。人拆掉的自動綁定也因此不會被下一輪綁回去。

    有把握與否是 `parser.binding.judge` 的事；Route 在這裡挑：TMDB 的類型推得出電影或劇集，
    同類型只有一條啟用中的 Route 才自動選，否則留在待綁定、作品預填成候選。
    """
    series = await session.get(RssSeries, series_id)
    if series is None or series.media_id is not None:
        return None
    try:
        clues = await _clues(fetcher, series)
        shots = await _candidates(session, factory, clues)
    except _LookupError as failed:
        logger.info("rss series lookup failed", extra={"series": series_id, "error": str(failed)})
        await _note(
            session, series_id, (because(BindReasonCode.LOOKUP_FAILED, detail=str(failed)),)
        )
        return None

    verdict = judge(clues, shots)
    ids = tuple(build_media_id(shot.kind, shot.tmdb_id) for shot in verdict.candidates)
    if verdict.media is None:
        await _note(session, series_id, verdict.reasons, ids)
        return None
    routes = await _routes_for(session, verdict.media.kind)
    if len(routes) != 1:
        await _note(session, series_id, (*verdict.reasons, _route_reason(routes)), ids)
        return None
    route = routes[0]
    await _note(
        session,
        series_id,
        (*verdict.reasons, because(BindReasonCode.ONLY_ROUTE, route=route.name)),
        ids,
    )
    try:
        bound = await bind_series(
            session, factory, series_id, media_id=ids[0], route_id=route.id, user_id=None
        )
    except RssRejectedError as refusal:
        # 認到與綁之間 Route 被停用、另一個分頁先綁了：留給人，不是整輪的失敗。依據要先寫下
        # （送單把它帶進時間線），沒綁成就收回「只有這一條 Route」那一句，否則待綁定那一列會把
        # 綁上用的依據當成沒綁的理由。
        await _note(session, series_id, verdict.reasons, ids)
        logger.info(
            "rss series not bound automatically",
            extra={"series": series_id, "reason": refusal.reason.value},
        )
        return None
    logger.info("rss series bound automatically", extra={"series": series_id, "media": ids[0]})
    return bound.submitted


async def _clues(fetcher: FeedFetcher, series: RssSeries) -> SeriesClues:
    """番組頁的中文名與開播日期 + 長出它的那一筆發佈名。"""
    if series.mikan_bangumi_id is None:
        raise _LookupError("the series has no Mikan bangumi id")
    try:
        page = await fetcher.fetch(mikan.bangumi_url(series.mikan_bangumi_id))
    except ServiceError as exc:
        raise _LookupError(f"bangumi page: {message(exc)}") from exc
    found = mikan.bangumi_page(page.decode("utf-8", errors="replace"))
    return SeriesClues(title=found.title, premiere=found.premiere, release_title=series.title_raw)


async def _candidates(
    session: AsyncSession, factory: ServiceClientFactory, clues: SeriesClues
) -> tuple[MediaSnapshot, ...]:
    """線索去 TMDB 搜，每個詞取前 `SEARCH_DEPTH` 筆讀回快照。

    探索頁同一支搜尋與詳情頁同一支讀取：同一份快取、同一條 24 小時規則。
    """
    ids: dict[str, None] = {}
    for term in search_terms(clues):
        found = await search_media(session, factory, term)
        if found.problem is not None:
            raise _LookupError(f"tmdb search: {found.detail or found.problem.value}")
        for item in found.items[:SEARCH_DEPTH]:
            if could_be(item.kind, item.year, clues.premiere):
                ids.setdefault(item.id, None)
    shots: list[MediaSnapshot] = []
    for media_id in ids:
        shot = await read_snapshot(session, factory, media_id)
        if shot is None:
            raise _LookupError(f"tmdb detail: {media_id} could not be read")
        shots.append(shot)
    return tuple(shots)


async def _routes_for(session: AsyncSession, kind: MediaKind) -> list[Route]:
    """收得下這種作品的啟用中 Route，照名稱排（理由的參數照這個順序列）。"""
    rows = await session.scalars(
        select(Route)
        .where(Route.enabled.is_(True), Route.collection_type == collection_type_for(kind))
        .order_by(Route.name, Route.id)
    )
    return list(rows)


def _route_reason(routes: list[Route]) -> BindReason:
    if not routes:
        return because(BindReasonCode.NO_ROUTE)
    return because(BindReasonCode.ROUTE_AMBIGUOUS, routes=", ".join(row.name for row in routes))


async def _note(
    session: AsyncSession,
    series_id: int,
    reasons: tuple[BindReason, ...],
    candidates: tuple[str, ...] = (),
) -> None:
    """記下這一次查到的結果。"""
    row = await session.get(RssSeries, series_id)
    if row is None:
        return
    row.reasons_json = [reason.model_dump(mode="json") for reason in reasons]
    row.candidates_json = list(candidates)
    await session.commit()


def _reasons(row: RssSeries) -> tuple[BindReason, ...]:
    return tuple(BindReason.model_validate(raw) for raw in row.reasons_json or ())


# --- RSS Series ---------------------------------------------------------


@command(Effect.READ)
async def list_series(session: AsyncSession) -> tuple[SeriesView, ...]:
    """待綁定的排前面（shape §2），同類之內新的在前。"""
    rows = list(
        await session.scalars(
            select(RssSeries).order_by(
                RssSeries.media_id.is_not(None), RssSeries.created_at.desc(), RssSeries.id.desc()
            )
        )
    )
    return tuple([await _series_view(session, row) for row in rows])


@command(Effect.REVERSIBLE, inverse="rss.unbind_series")
async def bind_series(
    session: AsyncSession,
    factory: ServiceClientFactory,
    series_id: int,
    *,
    media_id: str,
    route_id: int,
    user_id: int | None,
) -> SeriesView:
    """把一個 RSS Series 綁到作品與 Route，凍結資料夾名，然後把它留著的 Item 送出去。

    Route 的健康不在這裡擋：紅燈是「現在送不了」，綁定照樣成立、送單被拒的那幾筆下一輪再送。
    停用與收錯種類是「綁錯了」，當場拒絕、什麼都不改。
    """
    series = await session.get(RssSeries, series_id)
    if series is None:
        raise RssRejectedError(RssRefusal.SERIES_MISSING, str(series_id))
    if series.media_id is not None:
        raise RssRejectedError(RssRefusal.SERIES_BOUND, series.media_id)
    media = await session.get(Media, media_id)
    if media is None:
        raise RssRejectedError(RssRefusal.MEDIA_MISSING, media_id)
    route = await session.get(Route, route_id)
    if route is None:
        raise RssRejectedError(RssRefusal.ROUTE_MISSING, str(route_id))
    if not route.enabled:
        raise RssRejectedError(RssRefusal.ROUTE_DISABLED, route.slug)
    if route.collection_type is not collection_type_for(media.kind):
        raise RssRejectedError(
            RssRefusal.ROUTE_KIND_MISMATCH, f"{route.slug} holds {route.collection_type.value}"
        )

    series.media_id = media.id
    series.route_id = route.id
    series.bound_by = actor_of(user_id)
    freeze(media, route)
    waiting = await session.scalars(
        select(RssItem).where(
            RssItem.series_id == series.id, RssItem.status == FeedItemStatus.UNBOUND
        )
    )
    for item in waiting:
        item.status = FeedItemStatus.MATCHED
    await session.commit()
    logger.info("rss series bound", extra={"series": series.id, "media": media.id})

    submitted = await _submit_waiting(session, factory, RssItem.series_id == series_id)
    row = await session.get(RssSeries, series_id)
    assert row is not None
    return replace(await _series_view(session, row), submitted=submitted)


@command(Effect.REVERSIBLE, inverse="rss.bind_series")
async def unbind_series(session: AsyncSession, series_id: int) -> SeriesView:
    """解除綁定：還沒送出去的 Item 回到待綁定。已經送出的 Job 不動，資料夾名也不解凍——
    磁碟上已經有那一串了。"""
    series = await session.get(RssSeries, series_id)
    if series is None:
        raise RssRejectedError(RssRefusal.SERIES_MISSING, str(series_id))
    series.media_id = None
    series.route_id = None
    series.bound_by = ""
    # 綁上時的依據不再成立；候選留著，重綁時仍然一鍵選得到。
    series.reasons_json = None
    held = await session.scalars(
        select(RssItem).where(
            RssItem.series_id == series.id, RssItem.status == FeedItemStatus.MATCHED
        )
    )
    for item in held:
        item.status = FeedItemStatus.UNBOUND
        item.error = ""
    await session.commit()
    return await _series_view(session, series)


async def _series_view(session: AsyncSession, row: RssSeries) -> SeriesView:
    media = await session.get(Media, row.media_id) if row.media_id is not None else None
    route = await session.get(Route, row.route_id) if row.route_id is not None else None
    waiting = await session.scalar(
        select(func.count())
        .select_from(RssItem)
        .where(
            RssItem.series_id == row.id,
            or_(
                RssItem.status == FeedItemStatus.UNBOUND,
                RssItem.status == FeedItemStatus.MATCHED,
            ),
        )
    )
    return SeriesView(
        id=row.id,
        key=row.key,
        title_raw=row.title_raw,
        mikan_bangumi_id=row.mikan_bangumi_id,
        mikan_subgroup_id=row.mikan_subgroup_id,
        media_id=row.media_id,
        media_title=media.snapshot().title if media is not None else "",
        media_title_en=media.title_en if media is not None else "",
        route_id=row.route_id,
        route_name=route.name if route is not None else "",
        season=row.season,
        episode_offset=row.episode_offset,
        bound_by=row.bound_by,
        waiting=int(waiting or 0),
        reasons=_reasons(row),
        candidates=await _candidate_views(session, row.candidates_json or ()),
    )


async def _candidate_views(session: AsyncSession, ids: Sequence[str]) -> tuple[CandidateView, ...]:
    """候選的 id → 畫面上的那幾格。自動綁定讀過詳情，所以每一部都有 Media 列；不在了就略過。"""
    if not ids:
        return ()
    rows = {row.id: row for row in await session.scalars(select(Media).where(Media.id.in_(ids)))}
    return tuple(
        CandidateView(
            id=row.id,
            kind=row.kind,
            title=row.snapshot().title,
            title_en=row.title_en,
            year=row.year,
        )
        for row in (rows.get(one) for one in ids)
        if row is not None
    )


# --- Feed Item ----------------------------------------------------------


@command(Effect.READ)
async def list_items(session: AsyncSession) -> tuple[ItemView, ...]:
    """最近看到的 `RECENT_ITEMS` 筆，新的在前。"""
    rows = await session.scalars(
        select(RssItem).order_by(RssItem.seen_at.desc(), RssItem.id.desc()).limit(RECENT_ITEMS)
    )
    return tuple(
        ItemView(
            id=row.id,
            feed_id=row.feed_id,
            title=row.title,
            link=row.link,
            published_at=row.published_at,
            seen_at=row.seen_at,
            series_id=row.series_id,
            status=row.status,
            job_hash=row.job_hash,
            error=row.error,
        )
        for row in rows
    )
