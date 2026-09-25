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

**全部接受，只排除**（brief §15、票 10）：一筆 Item 寫下的那一刻看排除條件（全域、Feed、RSS Series
三層取聯集，規則在 `parser.exclusion`），擋下的是 `excluded`、記下哪一層的哪一條。規則收緊時，還沒
送出去的那幾筆照新規則再看一次；放寬不把擋下的放回來——拿掉一條規則不該讓幾個月前被它擋下的一次
全部下載。

**去重**依序：同一個 Feed 的 GUID（`(feed_id, guid)` 唯一，寫下時）→ 同一個 info hash（送單時：
Job 已經在了、或另一筆已經送過）→ 帳本已有同 Media / 季 / 集 / Tags（送單時，`_in_library`）。
擋下的是 `duplicate`。v2 的 Tags 不同（`version`），不是重複（brief §7.7）。排除與去重擋下的都
不是錯誤，理由（`domain.SkipReason`）存在 `skip_json`，Feed Item 清單照它說話。

**新 Feed 的第一輪預覽**（brief §15「補舊集」最後一句、票 11）：搜尋類 feed（Nyaa、acg.rip）第一輪就
帶著幾個月的歷史，所以 `primed_at` 還是 `NULL` 的 Feed 一筆都不送——照樣寫 Item、長 Series、看排除
條件，停在預覽（`preview_feed`）等使用者選「全部下載」或「只追之後的」（`prime_feed`）。擋在送單
那一頭（`_submit_waiting` 只看選過的 Feed），所以輪詢、綁定、自動綁定三條送單的路一起擋住。Mikan
聚合 feed 只有最近的集數，加的那一刻就寫 `primed_at`。

**補舊集與每日補漏**（brief §15「補舊集」、票 12）：Mikan 的 RSS Series 綁定那一刻讀它的單一 feed
（`/RSS/Bangumi?bangumiId=&subgroupid=`，整季都在），預設全部補下載；之後滿一天、輪到它所在的
聚合 Feed 時再讀一次（`_backfill_due`），接住停機期間被聚合 feed 捲掉的集數。補下來的**寫成那個
聚合 Feed 的 Item**：`(feed_id, guid)` 去重（Mikan 的 guid 是 info hash，聚合 feed 之後帶到同一集
認得出見過）、同樣看三層排除條件、同樣由 `_submit_waiting` 送出——不另開一條送單的路。人工綁定時
取消勾選，記在 RSS Series 的 `passed_before`：補舊集與補漏讀到的、在那之前發佈的記成 `passed`。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from berth.adapters.http import ServiceError
from berth.adapters.rss import FeedFetcher, FeedItem, acgrip, mikan, nyaa
from berth.domain import (
    BindReason,
    BindReasonCode,
    FeedItemStatus,
    FeedKind,
    FileEntry,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PrimeMode,
    RssRefusal,
    SkipCode,
    SkipReason,
    Tags,
    because,
    collection_type_for,
    skipped,
)
from berth.models import Job, LedgerEntry, Media, Route, RssFeed, RssItem, RssSeries, RssSettings
from berth.models import media_id as build_media_id
from berth.models.types import utcnow
from berth.parser import plan as decide
from berth.parser.binding import SeriesClues, could_be, judge, search_terms, title_key
from berth.parser.exclusion import Layer, RuleError, normalize_rules, screen
from berth.parser.planner import episode_span
from berth.parser.release import parse_release, tags_of
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.discover import search_media
from berth.services.jobs import JobRejectedError, JobSource, actor_of, add_download, freeze
from berth.services.media import read_snapshot
from berth.services.plan import parse_context
from berth.services.settings import read_settings, update_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 「最近的 Feed Item」一次給幾筆（shape §5）。
RECENT_ITEMS = 50

#: 自動綁定時每一個搜尋詞取前幾筆去讀詳情。一部作品是 3 + 季數個 TMDB 請求，TMDB 的相關性排序
#: 多半把要的那一部放在最前面；搜尋詞最多三個（`parser.binding.MAX_SEARCHES`）。
SEARCH_DEPTH = 3

#: 自動綁定的 `bound_by`（`events.actor` 的 `system`）。
SYSTEM = actor_of(None)

#: 帳本那一層猜季集時那一個（中性的）檔案的大小：夠大才不會被分類成 sample（`parser.classify`）。
_EPISODE_SIZE = 1 << 30

#: 綁好的 Mikan RSS Series 多久讀一次單一 feed 補漏（plan §3.2）。實際的間隔再加上聚合 Feed 的
#: 輪詢間隔：補漏是輪到那個 Feed 時順手做的。
BACKFILL_EVERY = timedelta(days=1)

#: 還沒送出去的兩種：規則收緊時照新規則再看一次的就是它們。
_WAITING = (FeedItemStatus.UNBOUND, FeedItemStatus.MATCHED)

#: 認得的來源：主機名 → 種類（`www.` 先去掉）。
_HOSTS: dict[str, FeedKind] = {
    "mikanani.me": FeedKind.MIKAN,
    "nyaa.si": FeedKind.NYAA,
    "acg.rip": FeedKind.ACGRIP,
}

#: 加的那一刻就算選過第一輪的來源：Mikan 聚合 feed 只有最近的集數（brief §15），沒有歷史要選。
_NO_PREVIEW = frozenset({FeedKind.MIKAN})


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
    #: 這一層的排除條件。
    exclusions: tuple[str, ...]
    #: 第一輪預覽選過的那一刻；`None` 是還沒選，這個 Feed 一筆都不送。
    primed_at: datetime | None


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
    #: 這一層的排除條件。
    exclusions: tuple[str, ...]
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
    #: `excluded` / `duplicate` 的那一條理由；其他狀態是 `None`。
    skip: SkipReason | None
    #: 近似的位元組數（只供顯示）；來源不報時 `None`。
    size: int | None


@dataclass(frozen=True, slots=True)
class ExclusionsView:
    """全域那一層（`settings.rss`）。"""

    #: 預設只排合集：不是單集的不自動下載。
    not_single: bool
    rules: tuple[str, ...]


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
    #: Feed 本身抓不到時的原文（也寫進那一列的 `last_error`）；抓到了是空字串。
    failed: str = ""


@dataclass(frozen=True, slots=True)
class PrimeOutcome:
    feed: FeedView
    #: 這一次送出去的（「全部下載」時綁好的那幾筆）。
    submitted: int
    #: 「只追之後的」略過的。
    passed: int
    #: 第一輪被排除條件擋下的（兩個選項都不改它們）。
    excluded: int


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
    row = RssFeed(
        name=name.strip() or _default_name(url),
        url=url,
        kind=kind,
        primed_at=utcnow() if kind in _NO_PREVIEW else None,
    )
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
    host = urlsplit(url).hostname
    return host.removeprefix("www.") if host else url


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
        exclusions=tuple(row.exclude_json),
        primed_at=row.primed_at,
    )


# --- 第一輪預覽 ---------------------------------------------------------


@command(Effect.READ)
async def preview_feed(session: AsyncSession, feed_id: int) -> tuple[ItemView, ...]:
    """這個 Feed 的每一筆，新的在前，說出各自會怎樣（brief §15、票 11）。

    排除條件在寫下的那一刻就看過了（`excluded`）。還沒送的那幾筆當場看一次去重（`_held_back`，
    **只讀**）：重複的照 `duplicate` 說出理由、不寫回——真的送單時還會再看一次，那時的帳本才算數。
    """
    if await session.get(RssFeed, feed_id) is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    rows = list(
        await session.scalars(
            select(RssItem)
            .where(RssItem.feed_id == feed_id)
            .order_by(RssItem.published_at.desc(), RssItem.id.desc())
        )
    )
    views: list[ItemView] = []
    for row in rows:
        view = _item_view(row)
        series = await session.get(RssSeries, row.series_id) if row.series_id else None
        if row.status in _WAITING and series is not None:
            held = await _held_back(session, row, series)
            if held is not None:
                skip, job_hash = held
                view = replace(view, status=FeedItemStatus.DUPLICATE, skip=skip, job_hash=job_hash)
        views.append(view)
    return tuple(views)


@command(Effect.IRREVERSIBLE)
async def prime_feed(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed_id: int,
    *,
    mode: PrimeMode,
    now: datetime | None = None,
) -> PrimeOutcome:
    """新 Feed 的第一輪選「全部下載」或「只追之後的」，寫下 `primed_at`（brief §15、票 11）。

    **「只追之後的」當場再讀一次 feed**：「之前」是選的那一刻已經在 feed 裡的每一筆。只看已經寫下的
    Item 的話，第一輪沒讀到 feed（連不上）或預覽之後才出現的那幾筆，下一輪就會被當成新的整批送出。
    讀不到就不決定（`feed_unreachable`）。「全部下載」不必讀：留著的照一般規則送，綁好的當場送、
    待綁定的綁定之後送；**還沒讀過的 Feed 不收「全部下載」**（`feed_unread`）——沒看過的東西不讓人選
    （shape §2），畫面不給按，命令本身也不收。排除條件擋下的兩個選項都不動。

    **不可逆**：選完就定了（shape §6），`passed` 放不回來，「全部下載」一次送出整份歷史。所以 M5 的
    AI 不自己選，做成 Proposal 等人。

    **寫 `primed_at` 是條件式的**（`WHERE primed_at IS NULL`）：「只追之後的」重讀 feed 的那幾秒裡
    另一個分頁可能先選了，後到的這一個是 `feed_primed`、什麼都不改。
    """
    feed = await session.get(RssFeed, feed_id)
    if feed is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    if feed.primed_at is not None:
        raise RssRejectedError(RssRefusal.FEED_PRIMED, feed.primed_at.isoformat())
    if mode is PrimeMode.ALL and feed.last_polled_at is None:
        raise RssRejectedError(RssRefusal.FEED_UNREAD, str(feed_id))
    if mode is PrimeMode.LATER:
        polled = await poll_feed(session, factory, feed_id, now=now)
        if polled.failed:
            raise RssRejectedError(RssRefusal.FEED_UNREACHABLE, polled.failed)
    won = await session.execute(
        update(RssFeed)
        .where(RssFeed.id == feed_id, RssFeed.primed_at.is_(None))
        .values(primed_at=now or utcnow())
    )
    if won.rowcount == 0:  # type: ignore[attr-defined]  # `execute(update)` 回 CursorResult，型別只說 Result
        await session.rollback()
        raise RssRejectedError(RssRefusal.FEED_PRIMED, str(feed_id))
    passed = 0
    if mode is PrimeMode.LATER:
        for row in await session.scalars(
            select(RssItem).where(RssItem.feed_id == feed_id, RssItem.status.in_(_WAITING))
        ):
            row.status = FeedItemStatus.PASSED
            row.error = ""
            passed += 1
    await session.commit()
    logger.info("rss feed primed", extra={"feed": feed_id, "mode": mode.value, "passed": passed})

    submitted = 0
    if mode is PrimeMode.ALL:
        submitted = await _submit_waiting(session, factory, RssItem.feed_id == feed_id)
    excluded = await session.scalar(
        select(func.count())
        .select_from(RssItem)
        .where(RssItem.feed_id == feed_id, RssItem.status == FeedItemStatus.EXCLUDED)
    )
    items = await session.scalar(
        select(func.count()).select_from(RssItem).where(RssItem.feed_id == feed_id)
    )
    saved = await session.get(RssFeed, feed_id, populate_existing=True)
    assert saved is not None
    return PrimeOutcome(
        feed=_feed_view(saved, int(items or 0)),
        submitted=submitted,
        passed=passed,
        excluded=int(excluded or 0),
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
            found = parse_items(feed.kind, await fetcher.fetch(feed.url))
        except ServiceError as exc:
            feed.last_polled_at = moment
            feed.last_error = message(exc)
            await session.commit()
            logger.warning(
                "rss feed could not be fetched", extra={"feed": feed.id, "error": feed.last_error}
            )
            return PollOutcome(items=0, series=0, bound=0, submitted=0, failed=feed.last_error)
        items, grown, skipped = await _record(session, fetcher, feed, found, moment)
        feed.last_polled_at = moment
        feed.last_error = skipped
        await session.commit()
        # 番組頁要同一個 fetcher 抓，所以在它關掉之前認。
        for series_id in grown:
            sent = await _auto_bind(session, factory, fetcher, series_id, moment)
            if sent is not None:
                bound += 1
                submitted += sent
        await _backfill_due(session, fetcher, feed_id, moment)
    finally:
        await fetcher.aclose()
    submitted += await _submit_waiting(session, factory, RssItem.feed_id == feed_id)
    return PollOutcome(items=items, series=len(grown), bound=bound, submitted=submitted)


def parse_items(kind: FeedKind, content: bytes) -> tuple[FeedItem, ...]:
    """種類 → 那一站的 mapper。認不出 feed 格式丟 `ProtocolMismatchError`（`rss/feed.py`）。"""
    match kind:
        case FeedKind.MIKAN:
            return mikan.parse_feed(content)
        case FeedKind.NYAA:
            return nyaa.parse_feed(content)
        case FeedKind.ACGRIP:
            return acgrip.parse_feed(content)


async def _record(
    session: AsyncSession,
    fetcher: FeedFetcher,
    feed: RssFeed,
    found: tuple[FeedItem, ...],
    moment: datetime,
    *,
    known: RssSeries | None = None,
) -> tuple[int, list[int], str]:
    """寫下這一輪新看到的 Item。回（新 Item 數、新 Series 的 id、跳過的那幾筆的原文）。

    **舊的先寫**：feed 是新的在前，送單照寫入順序走，第 11 集先於第 12 集進 qBittorrent。
    認不出 RSS Series 的那一筆（單集頁抓不到、改版了）**不寫**：寫了就是見過，下一輪不會再試。

    `known` 是補舊集讀的單一 feed：每一筆都屬於那一個 RSS Series，不抓單集頁；取消勾選補舊集之前
    發佈的記成 `passed`（`passed_before`）。
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
    unkeyed: list[str] = []
    settings = await read_settings(session, RssSettings)
    for item in reversed(found):
        if item.guid in seen:
            continue
        if known is not None:
            series = known
        else:
            try:
                key = await _series_key(fetcher, feed.kind, item)
            except _UnkeyedError as failed:
                unkeyed.append(str(failed))
                continue
            series, created = await _series(session, key, item)
            if created:
                grown.append(series.id)
        skip = _screen(settings, feed, series, item.title)
        session.add(
            RssItem(
                feed_id=feed.id,
                guid=item.guid,
                title=item.title,
                link=item.link,
                torrent_url=item.torrent_url or item.magnet,
                info_hash=item.info_hash,
                size=item.size,
                published_at=item.published_at,
                seen_at=moment,
                series_id=series.id,
                status=_arriving(series, skip, item.published_at if known else None),
                skip_json=_dump(skip),
            )
        )
        seen.add(item.guid)
        items += 1
    await session.flush()
    detail = f"{len(unkeyed)} item(s) skipped: {unkeyed[0]}" if unkeyed else ""
    return items, grown, detail


def _arriving(
    series: RssSeries, skip: SkipReason | None, backfilled: datetime | None = None
) -> FeedItemStatus:
    """剛寫下的那一筆從哪一個狀態起步。`backfilled` 是補舊集讀到的那一筆的發佈時間。"""
    if skip is not None:
        return FeedItemStatus.EXCLUDED
    if series.media_id is None:
        return FeedItemStatus.UNBOUND
    if backfilled is not None and series.passed_before is not None:
        return (
            FeedItemStatus.PASSED if backfilled < series.passed_before else FeedItemStatus.MATCHED
        )
    return FeedItemStatus.MATCHED


class _UnkeyedError(Exception):
    """認不出這一筆屬於哪一個 RSS Series。訊息是原因（英文原文）。"""


async def _series_key(fetcher: FeedFetcher, kind: FeedKind, item: FeedItem) -> str:
    """這一筆屬於哪一個 RSS Series 的鍵（plan §2.4）。認不出來丟 `_UnkeyedError`。

    Mikan 的鍵（番組 id, 字幕組 id）不在 feed 裡，要抓單集頁（brief §20.12）。其他來源沒有番組這種
    東西，鍵是標題骨幹 + 字幕組（`parser.binding.title_key`，AutoBangumi 的做法）。
    """
    match kind:
        case FeedKind.NYAA | FeedKind.ACGRIP:
            key = title_key(item.title)
            if key is None:
                raise _UnkeyedError(
                    f"no title left once the group and episode are cut: {item.title}"
                )
            return key
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
    row = RssSeries(key=key, title_raw=item.title)
    if key.startswith("mikan:"):
        _, bangumi, subgroup = key.split(":")
        row.mikan_bangumi_id = int(bangumi)
        row.mikan_subgroup_id = int(subgroup)
    session.add(row)
    await session.flush()
    return row, True


# --- 補舊集 -------------------------------------------------------------


async def _home_feed(session: AsyncSession, series: RssSeries) -> RssFeed | None:
    """補下來的 Item 寫在哪一個 Feed 底下：最早帶到這個 RSS Series、還在的那一個 Mikan Feed。

    綁定與每日補漏認同一個，所以一集只在一個 Feed 底下補一次。不是 Mikan 的 RSS Series（沒有單一
    feed）、或它的 Feed 都刪掉了（不再訂閱）是 `None`，不補。
    """
    if series.mikan_bangumi_id is None or series.mikan_subgroup_id is None:
        return None
    feed: RssFeed | None = await session.scalar(
        select(RssFeed)
        .join(RssItem, RssItem.feed_id == RssFeed.id)
        .where(RssItem.series_id == series.id, RssFeed.kind == FeedKind.MIKAN)
        .order_by(RssItem.id)
        .limit(1)
    )
    return feed


async def _backfill(
    session: AsyncSession,
    fetcher: FeedFetcher,
    home: RssFeed,
    series: RssSeries,
    moment: datetime,
) -> str:
    """讀這個 Mikan RSS Series 的單一 feed（整季），沒見過的寫成 `home` 的 Item，記下補過的時間。

    不 commit（呼叫的一方與自己的改動一起）。讀不到回原文（英文）、什麼都不寫；讀到了回空字串。
    """
    assert series.mikan_bangumi_id is not None and series.mikan_subgroup_id is not None
    url = mikan.bangumi_feed_url(series.mikan_bangumi_id, series.mikan_subgroup_id)
    try:
        season = mikan.parse_feed(await fetcher.fetch(url))
    except ServiceError as exc:
        logger.warning(
            "rss backfill could not read the single feed; the next round tries again",
            extra={"series": series.id, "error": message(exc)},
        )
        return message(exc)
    await _record(session, fetcher, home, season, moment, known=series)
    series.backfilled_at = moment
    return ""


async def _backfill_due(
    session: AsyncSession, fetcher: FeedFetcher, feed_id: int, moment: datetime
) -> None:
    """每日補漏：這個 Feed 是 home 的、綁好的 Mikan RSS Series，上次補過滿一天（或還沒補過）的各讀
    一次單一 feed（plan §3.2）。

    讀不到的那一個記在這個 Feed 的 `last_error`、`backfilled_at` 不動，下一輪再試；一個讀不到不拖累
    其他的。補下來的由 `poll_feed` 最後那一次 `_submit_waiting` 送出。
    """
    feed = await session.get(RssFeed, feed_id)
    assert feed is not None
    due = await session.scalars(
        select(RssSeries)
        .where(
            RssSeries.media_id.is_not(None),
            RssSeries.mikan_bangumi_id.is_not(None),
            RssSeries.mikan_subgroup_id.is_not(None),
            or_(
                RssSeries.backfilled_at.is_(None),
                RssSeries.backfilled_at <= moment - BACKFILL_EVERY,
            ),
            RssSeries.id.in_(select(RssItem.series_id).where(RssItem.feed_id == feed_id)),
        )
        .order_by(RssSeries.id)
    )
    failures: list[str] = []
    for series in list(due):
        home = await _home_feed(session, series)
        if home is None or home.id != feed_id:
            continue
        failed = await _backfill(session, fetcher, feed, series, moment)
        if failed:
            failures.append(f"backfill {series.key}: {failed}")
        await session.commit()
    if failures:
        feed.last_error = "; ".join(one for one in (feed.last_error, *failures) if one)
        await session.commit()


async def _submit_waiting(
    session: AsyncSession, factory: ServiceClientFactory, scope: ColumnElement[bool]
) -> int:
    """把 `scope` 裡綁好而還沒送的 Item（`matched`）送出去，舊的先。回送成了幾筆。

    **第一輪還沒選過的 Feed 不送**（`primed_at` 是 `NULL`）：三條送單的路（輪詢、綁定、自動綁定）
    都經過這裡，擋一處就擋住全部。
    """
    rows = list(
        await session.scalars(
            select(RssItem)
            .join(RssFeed, RssFeed.id == RssItem.feed_id)
            .where(RssItem.status == FeedItemStatus.MATCHED, RssFeed.primed_at.is_not(None), scope)
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
    mine = await _sent_before(session, item, series)
    if mine is not None:
        await _mark_sent(session, item, mine)
        return 0
    held = await _held_back(session, item, series)
    if held is not None:
        await _mark_duplicate(session, item, *held)
        return 0
    try:
        outcome = await add_download(
            session,
            factory,
            source=JobSource(
                url=item.torrent_url,
                title=item.title,
                info_hash=item.info_hash,
                published_at=item.published_at,
            ),
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
    # 來源不報 hash（acg.rip）時，送單算出來的寫回來：之後別的 Feed 帶同一個 hash 來時才比得到它
    # （plan §8.5）。
    row.info_hash = row.info_hash or outcome.job.hash
    if not outcome.created:
        # 要了 torrent 才知道是同一個：Job 本來就在了。
        await _mark_duplicate(session, row, skipped(SkipCode.SAME_TORRENT), outcome.job.hash)
        return 0
    await _mark_sent(session, row, outcome.job.hash)
    return 1


async def _mark_sent(session: AsyncSession, item: RssItem, job_hash: str) -> None:
    item.status = FeedItemStatus.DOWNLOADED
    item.job_hash = job_hash
    item.skip_json = None
    item.error = ""
    await session.commit()


async def _sent_before(session: AsyncSession, item: RssItem, series: RssSeries) -> str | None:
    """這一筆自己之前就送出去了嗎：回那一筆 Job 的 hash，不是是 `None`。

    Job commit 之後、Item 改狀態之前程序中斷，或綁定與輪詢同時送同一筆時，下一次看到的是「Job 已經
    在了」——而它就是這個 RSS Series 送的。認回成已送單，不能記成它自己的重複。另一筆 Item 已經認領
    那一筆 Job 的（兩個 Feed 帶同一個 hash），這一筆才是重複；刪掉過的（`removed`）也不認回。
    """
    if not item.info_hash:
        return None
    job = await session.get(Job, item.info_hash)
    if (
        job is None
        or job.state is JobState.REMOVED
        or job.trigger is not JobTrigger.RSS
        or job.trigger_ref != str(series.id)
    ):
        return None
    claimed = await session.scalar(
        select(RssItem.id).where(
            RssItem.job_hash == job.hash,
            RssItem.id != item.id,
            RssItem.status == FeedItemStatus.DOWNLOADED,
        )
    )
    return job.hash if claimed is None else None


async def _mark_duplicate(
    session: AsyncSession, item: RssItem, skip: SkipReason, job_hash: str
) -> None:
    item.status = FeedItemStatus.DUPLICATE
    item.skip_json = _dump(skip)
    item.job_hash = job_hash
    item.error = ""
    await session.commit()
    logger.info("rss item is a duplicate", extra={"item": item.id, "reason": skip.code.value})


async def _held_back(
    session: AsyncSession, item: RssItem, series: RssSeries
) -> tuple[SkipReason, str] | None:
    """去重（brief §15「處理」）：擋下的回（理由, 連到的那一筆 Job 的 hash），沒擋是 `None`。

    同一個 torrent 看兩處：Job 在不在（另一個 Feed 送過、手動送過、刪掉過——刪掉過的讓 `add_download`
    每一輪回一次 `job_removed` 沒有意義），與另一筆 Item 送過沒有（Job 連同紀錄一起清掉之後，使用者
    刪掉的東西不該從另一個 Feed 被抓回來）。
    """
    if item.info_hash:
        if await session.get(Job, item.info_hash) is not None:
            return skipped(SkipCode.SAME_TORRENT), item.info_hash
        sent = await session.scalar(
            select(RssItem.job_hash).where(
                RssItem.info_hash == item.info_hash,
                RssItem.id != item.id,
                RssItem.status == FeedItemStatus.DOWNLOADED,
            )
        )
        if sent is not None:
            # 那一筆送出去時的 Job（`.torrent` 算出的 hash 可能與來源報的不同）；清掉了就不連。
            alive = sent and await session.get(Job, sent) is not None
            return skipped(SkipCode.SAME_TORRENT), sent if alive else ""
    known = await _in_library(session, item, series)
    if known is not None:
        return skipped(SkipCode.IN_LIBRARY, known=known), ""
    return None


async def _in_library(session: AsyncSession, item: RssItem, series: RssSeries) -> str | None:
    """帳本已有這一筆的同一個版本：回它在媒體庫裡的檔名，沒有是 `None`（`library_copy`）。"""
    media = await session.get(Media, series.media_id) if series.media_id is not None else None
    route = await session.get(Route, series.route_id) if series.route_id is not None else None
    if media is None or route is None:
        return None
    return await library_copy(
        session, item.title, item.published_at, media=media, route=route, series=series
    )


@command(Effect.READ)
async def library_copy(
    session: AsyncSession,
    title: str,
    published: datetime | None,
    *,
    media: Media,
    route: Route,
    series: RssSeries | None,
) -> str | None:
    """帳本已有同 Media / 季 / 集 / Tags 的那一份：回它在媒體庫裡的檔名，沒有是 `None`。

    RSS 送單前（`_in_library`）與一次性 RSS 連結（`services/oneshot`，M3 票 18）共用；後者沒有
    RSS Series——它送的是手動的 Job，規劃時也不讀季號與 offset。

    季集照規劃時的算法猜（同一份 `parse_context`、同一支 `plan`，發佈名當 torrent 名、配一個中性的
    檔名）；猜不到、或信心不夠自動入庫的不擋——規劃時那一層（`services/plan._against_ledger`）照樣
    會比，漏在這裡只是多下載一次，擋錯了卻是少一集。比的範圍與那一層相同：同一個資料夾。

    **Tags 比兩處**：帳本那一列的 Tags 是從 torrent 裡的**檔名**讀的，字幕組常在檔名寫另一個組名
    （發佈名 `[喵萌奶茶屋&LoliHouse]`、檔名 `[LoliHouse]`），只比它的話同一個發佈換個 hash
    重新上傳就認不出來。所以也拿那一列的 Job 的發佈名算一次 Tags——標題對標題。**讀不出字幕組的
    標題不比這一半**：兩邊的 Tags 都可能是空的，空對空不是同一個版本。
    """
    snapshot = media.stored_snapshot()
    if snapshot is None:
        return None
    (guess,) = decide(
        title,
        [FileEntry(rel_path="episode.mkv", size=_EPISODE_SIZE)],
        parse_context(route, snapshot, series, published=published),
    )
    span = episode_span(guess)
    if span is None or not guess.target_path:
        return None
    season, start, end = span
    folder = str((PurePosixPath(route.target_path) / guess.target_path).parent)
    by_title = tags_of(parse_release(title))
    rows = await session.execute(
        select(LedgerEntry, Job.name)
        .outerjoin(Job, Job.hash == LedgerEntry.job_hash)
        .where(
            LedgerEntry.media_id == media.id,
            LedgerEntry.action == PlanAction.IMPORT,
            LedgerEntry.season == season,
            LedgerEntry.episode_start == start,
        )
        .order_by(LedgerEntry.id)
    )
    for entry, released in rows.tuples():
        if str(PurePosixPath(entry.target_path).parent) != folder:
            continue
        if (entry.episode_end or entry.episode_start) != end:
            continue
        if Tags.model_validate(entry.tags_json or {}) == guess.tags or (
            # 外接：沒有 Job 的那一列（`rebuild-ledger` 長回來的）是 `None`，型別上看不出來。
            released and by_title.group and tags_of(parse_release(released)) == by_title
        ):
            return PurePosixPath(entry.target_path).name
    return None


# --- 排除條件 -----------------------------------------------------------
#
# 三支都是可逆但**沒有單一反向命令**：規則本身用同一支帶回原本的值就還原了，但收緊時擋下的 Item
# 不會因此放回來（只往前看，brief §15）。沒有東西被下載或刪掉，擋下的那一集仍可從搜尋手動送。


@command(Effect.READ)
async def read_exclusions(session: AsyncSession) -> ExclusionsView:
    """全域那一層。"""
    settings = await read_settings(session, RssSettings)
    return ExclusionsView(not_single=settings.exclude_not_single, rules=tuple(settings.exclude))


@command(Effect.REVERSIBLE)
async def set_exclusions(
    session: AsyncSession, *, not_single: bool, rules: Sequence[str]
) -> ExclusionsView:
    """整組覆寫全域那一層。反向是同一支帶回原本的值：收緊時擋下的那幾筆本來就還沒下載。"""
    kept = _normalized_rules(rules)

    def change(value: RssSettings) -> None:
        value.exclude_not_single = not_single
        value.exclude = list(kept)

    saved = await update_settings(session, RssSettings, change)
    await _rescreen(session, None)
    return ExclusionsView(not_single=saved.exclude_not_single, rules=tuple(saved.exclude))


@command(Effect.REVERSIBLE)
async def set_feed_exclusions(
    session: AsyncSession, feed_id: int, rules: Sequence[str]
) -> FeedView:
    """整組覆寫這個 Feed 的排除條件。"""
    row = await session.get(RssFeed, feed_id)
    if row is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    row.exclude_json = list(_normalized_rules(rules))
    await session.commit()
    await _rescreen(session, RssItem.feed_id == feed_id)
    items = await session.scalar(
        select(func.count()).select_from(RssItem).where(RssItem.feed_id == feed_id)
    )
    return _feed_view(row, int(items or 0))


@command(Effect.REVERSIBLE)
async def set_series_exclusions(
    session: AsyncSession, series_id: int, rules: Sequence[str]
) -> SeriesView:
    """整組覆寫這個 RSS Series 的排除條件。"""
    row = await session.get(RssSeries, series_id)
    if row is None:
        raise RssRejectedError(RssRefusal.SERIES_MISSING, str(series_id))
    row.exclude_json = list(_normalized_rules(rules))
    await session.commit()
    await _rescreen(session, RssItem.series_id == series_id)
    return await _series_view(session, row)


def _normalized_rules(rules: Sequence[str]) -> tuple[str, ...]:
    """存之前就擋寫壞的規則（票 10：不等到輪詢時才炸）。"""
    try:
        return normalize_rules(rules)
    except RuleError as broken:
        raise RssRejectedError(RssRefusal.RULE_INVALID, str(broken)) from broken


def _screen(
    settings: RssSettings, feed: RssFeed, series: RssSeries, title: str
) -> SkipReason | None:
    """這一筆過不過三層排除條件。層的順序就是理由要先說的順序：全域、Feed、RSS Series。"""
    layers: tuple[Layer, ...] = (
        (SkipCode.GLOBAL_RULE, settings.exclude),
        (SkipCode.FEED_RULE, feed.exclude_json),
        (SkipCode.SERIES_RULE, series.exclude_json),
    )
    return screen(title, not_single=settings.exclude_not_single, layers=layers)


async def _rescreen(session: AsyncSession, scope: ColumnElement[bool] | None) -> None:
    """規則改了之後，`scope` 裡還沒送出去的那幾筆照新規則再看一次。**只收緊**：擋下的不放回來。"""
    settings = await read_settings(session, RssSettings)
    query = select(RssItem).where(RssItem.status.in_(_WAITING))
    if scope is not None:
        query = query.where(scope)
    for item in list(await session.scalars(query)):
        feed = await session.get(RssFeed, item.feed_id)
        series = await session.get(RssSeries, item.series_id) if item.series_id else None
        if feed is None or series is None:
            continue
        skip = _screen(settings, feed, series, item.title)
        if skip is not None:
            item.status = FeedItemStatus.EXCLUDED
            item.skip_json = _dump(skip)
            item.error = ""
    await session.commit()


def _dump(skip: SkipReason | None) -> dict[str, Any] | None:
    return skip.model_dump(mode="json") if skip is not None else None


def _skip_of(row: RssItem) -> SkipReason | None:
    return SkipReason.model_validate(row.skip_json) if row.skip_json is not None else None


# --- 自動綁定 -----------------------------------------------------------


class _LookupError(Exception):
    """番組頁或 TMDB 這一次查不到。訊息是原文（英文），進 `lookup_failed` 的 `detail`。"""


async def _auto_bind(
    session: AsyncSession,
    factory: ServiceClientFactory,
    fetcher: FeedFetcher,
    series_id: int,
    moment: datetime,
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
        # 自動綁定照預設補舊集（brief §15）。
        bound = await bind_series(
            session,
            factory,
            series_id,
            media_id=ids[0],
            route_id=route.id,
            user_id=None,
            now=moment,
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
    """番組頁的中文名與開播日期 + 長出它的那一筆發佈名。

    不是 Mikan 的（Nyaa、acg.rip）沒有番組頁：線索只有發佈名，`judge` 列出候選、一律留給人
    （票 11）。
    """
    if series.mikan_bangumi_id is None:
        return SeriesClues(title="", premiere=None, release_title=series.title_raw, show_page=False)
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
    backfill: bool = True,
    now: datetime | None = None,
) -> SeriesView:
    """把一個 RSS Series 綁到作品與 Route，凍結資料夾名，然後把它留著的 Item 送出去。

    Route 的健康不在這裡擋：紅燈是「現在送不了」，綁定照樣成立、送單被拒的那幾筆下一輪再送。
    停用與收錯種類是「綁錯了」，當場拒絕、什麼都不改。

    **Mikan 的 RSS Series 同時補舊集**（票 12）：讀單一 feed，聚合 feed 沒帶到的那幾集寫成 Item
    一起送（`backfill`，預設是；帳本已有、已有 Job 的由送單前的去重跳過）。讀不到不擋綁定，
    `backfilled_at` 留空、下一輪輪詢再補。取消勾選記在 `passed_before`：那一刻之前發佈的舊集之後
    不論在哪一個 Feed 補到都記成 `passed`。勾著重綁時，當初略過的那幾筆放回來一起送。

    反向命令 `unbind_series` 不收回已經送出去的 Job（同一般送單）。
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

    moment = now or utcnow()
    home = await _home_feed(session, series)
    series.media_id = media.id
    series.route_id = route.id
    series.bound_by = actor_of(user_id)
    # 沒有 Feed 可補（刪掉了）也記下：之後有 Feed 帶到它時，補漏照這個決定走。
    series.passed_before = None if backfill or series.mikan_bangumi_id is None else moment
    freeze(media, route)
    waiting = await session.scalars(
        select(RssItem).where(
            RssItem.series_id == series.id, RssItem.status == FeedItemStatus.UNBOUND
        )
    )
    for item in waiting:
        item.status = FeedItemStatus.MATCHED
    if home is not None:
        if backfill:
            # 上一次取消勾選略過的：這一次要整季。排除條件由下面的 `_rescreen` 照現在的規則再看。
            passed = await session.scalars(
                select(RssItem).where(
                    RssItem.series_id == series.id, RssItem.status == FeedItemStatus.PASSED
                )
            )
            for item in passed:
                item.status = FeedItemStatus.MATCHED
        fetcher = factory.rss()
        try:
            await _backfill(session, fetcher, home, series, moment)
        finally:
            await fetcher.aclose()
    await session.commit()
    await _rescreen(session, RssItem.series_id == series_id)
    logger.info("rss series bound", extra={"series": series_id, "media": media_id})

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
    # 「媒體庫裡已經有」是對綁上的那一部作品說的：綁錯的話改綁之後要重新判斷。
    for item in await session.scalars(
        select(RssItem).where(
            RssItem.series_id == series.id, RssItem.status == FeedItemStatus.DUPLICATE
        )
    ):
        skip = _skip_of(item)
        if skip is not None and skip.code is SkipCode.IN_LIBRARY:
            item.status = FeedItemStatus.UNBOUND
            item.skip_json = None
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
        exclusions=tuple(row.exclude_json),
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
    return tuple(_item_view(row) for row in rows)


def _item_view(row: RssItem) -> ItemView:
    return ItemView(
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
        skip=_skip_of(row),
        size=row.size,
    )
