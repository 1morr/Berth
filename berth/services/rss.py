"""RSS 的命令：Feed、RSS Series 的綁定、一輪輪詢（brief §15、plan §2.4、§3.2、§8.5、M3 票 08）。

一輪輪詢是 **抓 → 解析 → 找到或長出 RSS Series → 寫 Feed Item → 送出綁好的**。新長出的 RSS Series
先待綁定（`media_id = NULL`），它的 Item 是 `unbound`、留著不送；**長出來的那一輪就去認作品**
（`_auto_bind`，票 09）：Mikan 番組頁的中文名與開播日期、發佈名的標題骨幹去 TMDB 搜，規則在
`parser.binding.judge`。有把握就自動綁進 Feed 那一種的 Route（M4 票 105：劇集、電影各一條；
Feed 沒說才看同類型是不是只有一條啟用中的 Route），否則留在待綁定並記下理由與候選。自動綁定、
人工綁定與之後 M5 的 AI 走的是同一支 `bind_series`。

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
聚合 Feed 時再讀一次（`_backfill_due`），接住停機期間被聚合 feed 捲掉的集數；完結之後再補最後
一次就停（M4 票 116）。補下來的**寫成那個聚合 Feed 的 Item**：`(feed_id, guid)` 去重（Mikan 的
guid 是 info hash，聚合 feed 之後帶到同一集認得出見過）、同樣看三層排除條件、同樣由
`_submit_waiting` 送出——不另開一條送單的路。綁定一律補，沒有不補的選項（brief §15、M4 票 78）。
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any, NamedTuple
from urllib.parse import urlsplit

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from berth.adapters.http import ServiceError, is_transient
from berth.adapters.rss import FeedFetcher, FeedItem, acgrip, mikan, nyaa
from berth.adapters.tmdb import BASE_URL as TMDB_BASE_URL
from berth.domain import (
    SYSTEM,
    BindReason,
    BindReasonCode,
    FeedItemStatus,
    FeedKind,
    JobFilter,
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
    TmdbProblem,
    because,
    collection_type_for,
    label_of,
    rss_label,
    skipped,
)
from berth.models import DEFAULT_INTERVAL_SEC as DEFAULT_INTERVAL_SEC
from berth.models import FEED_INTERVALS as FEED_INTERVALS
from berth.models import (
    Job,
    LedgerEntry,
    Media,
    Route,
    RssFeed,
    RssItem,
    RssSeries,
    RssSettings,
    parse_media_id,
)
from berth.models import media_id as build_media_id
from berth.models.types import utcnow
from berth.parser import series_finished
from berth.parser.binding import (
    SeriesClues,
    could_be,
    judge,
    of_group,
    search_term,
    search_terms,
    title_key,
)
from berth.parser.exclusion import Layer, RuleError, normalize_rules, screen
from berth.parser.planner import episode_span
from berth.parser.release import parse_release, tags_of
from berth.parser.title import normalize_title
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, Flag, command
from berth.services.discover import search_media
from berth.services.downloading import DownloadRound, download_round
from berth.services.first_batch import FirstBatchAsk
from berth.services.first_batch import asks as first_batch_asks
from berth.services.jobs import (
    FILTER_STATES,
    JobRejectedError,
    JobSource,
    add_download,
    freeze,
)
from berth.services.media import read_snapshot_checked
from berth.services.plan import guess_from_title
from berth.services.settings import read_settings, update_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 「最近的 Feed Item」一次給幾筆（shape §5）。
RECENT_ITEMS = 50

#: 自動綁定時每一個搜尋詞取前幾筆去讀詳情。一部作品是 3 + 季數個 TMDB 請求，TMDB 的相關性排序
#: 多半把要的那一部放在最前面；搜尋詞最多三個（`parser.binding.MAX_SEARCHES`）。
SEARCH_DEPTH = 3

#: 自動綁定暫時查不到時（連不上、逾時、限流、5xx），第幾次重認之前等多久（M4 票 14，plan §3.2）；
#: 用完落到 `lookup_failed`。一個 Series 最多認 1 + 3 次、分散在 17 小時裡：試跑那一次的 TMDB
#: 同日稍後就讀得到，而壞掉的番組頁也不會每 15 分鐘被打一次（brief §15「綁定」原本的顧慮）。
LOOKUP_RETRIES = (timedelta(hours=1), timedelta(hours=4), timedelta(hours=12))


def _site_of(url: str) -> str:
    """重認理由裡的站名：小寫主機名，`www.` 去掉（`nyaa.si` 與 `www.nyaa.si` 是同一站）。"""
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


#: TMDB 在重認理由裡的站名。
_TMDB_SITE = _site_of(TMDB_BASE_URL)

#: 正在跑的那一輪（`poll_feed`）：Feed id → 做完時放進結果（沒做完就結束是 `None`）。
_rounds: dict[int, asyncio.Future[PollOutcome | None]] = {}

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


def unread(exc: ServiceError) -> RssRejectedError:
    """人在畫面上按的讀取沒讀到（`feed_unreachable`，`detail` 是原文）。"""
    return RssRejectedError(RssRefusal.FEED_UNREACHABLE, message(exc))


@dataclass(frozen=True, slots=True)
class KindCounts:
    """劇集、電影各幾個。"""

    tv: int = 0
    movie: int = 0


@dataclass(frozen=True, slots=True)
class KindRoutes:
    """劇集、電影各一條 Route；`None` 是沒有。"""

    tv: int | None
    movie: int | None

    def of(self, kind: MediaKind) -> int | None:
        return self.tv if kind is MediaKind.TV else self.movie

    @classmethod
    def of_feed(cls, feed: RssFeed) -> KindRoutes:
        return cls(tv=feed.tv_route_id, movie=feed.movie_route_id)


class _AwaitingRoute(NamedTuple):
    """因為 Route 不只一條而停在待綁定的一個 RSS Series。"""

    series_id: int
    #: 長出它的 Feed（`_grown_by`）。
    feed_id: int
    #: 自動綁定判出來的那一部（`candidates_json[0]`）。
    media_id: str
    kind: MediaKind


@dataclass(frozen=True, slots=True)
class FeedView:
    id: int
    name: str
    url: str
    kind: FeedKind
    interval_sec: int
    last_polled_at: datetime | None
    #: 上一輪輪詢與每日補漏各自失敗的原文（M4 票 130 拆欄）；成功是空字串。
    poll_error: str
    backfill_error: str
    #: 這個 Feed 長出了幾筆 Item。刪除的確認要說出會刪掉幾筆（shape §4）。
    items: int
    #: 這一層的排除條件。
    exclusions: tuple[str, ...]
    #: 第一輪預覽選過的那一刻；`None` 是還沒選，這個 Feed 一筆都不送。
    primed_at: datetime | None
    #: 自動綁定送進的 Route，劇集與電影各一條（M4 票 105）。`None` 是那一種沒有 Route、或票 105
    #: 之前加的 Feed 推不出來（畫面標「要選 Route」）。
    tv_route_id: int | None
    movie_route_id: int | None
    #: 這個 Feed 用得到哪幾種的 Route（`_route_kinds`）：從作品頁訂閱建的只有那部作品那一種，
    #: 另一格不提示、不要求、自動綁定也不讀。
    route_kinds: tuple[MediaKind, ...]
    #: 至少讀到過一次（`_ever_read`）：第一輪的「全部下載」只在它為真時給。
    ever_read: bool
    #: 它長出的、因為 Route 不只一條而停在待綁定的，照認出來的種類數（M4 票 105）：選了那一種的
    #: Route 會當場綁上幾部。
    awaiting_route: KindCounts


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
    #: Mikan 的番組名與字幕組名（M4 票 13）；沒讀到是空字串。畫面上的來源說名字、不說 id。
    mikan_bangumi_name: str
    mikan_subgroup_name: str
    #: `None` 是待綁定。
    media_id: str | None
    #: 作品名的兩輪（`JobView` 同一個規矩）；沒綁是空字串。
    media_title: str
    media_title_en: str
    route_id: int | None
    route_name: str
    #: 長出它的 Feed 的兩條 Route（M4 票 105）：手動綁定的「入庫到」先預選作品那一種的這一條。
    #: 長出它的 Feed 被刪了是兩個 `None`。
    feed_routes: KindRoutes
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
    #: 第一批確認過了沒（票 13）。
    confirmed: bool
    #: 綁定時搜尋框預填的字：`title_raw` 讀出的作品名（`binding.search_term`，M4 票 88）。
    search_term: str
    #: 從哪一站來的：Mikan 看鍵，其他看最近一筆的 Feed。一筆都沒有時是 `None`。
    source: FeedKind | None
    #: 發佈名讀出的字幕組（Mikan 的字幕組名稱 Berth 沒有存）。
    group: str
    #: 最近的一筆（照發佈時間，排除條件擋下的不算）：詳情頁的「最近一集」（票 19）。沒有是空字串。
    latest_title: str
    latest_at: datetime | None
    #: 最近那一筆的集數（發佈名讀出的）；讀不出是 `None`。
    latest_episode: int | None
    #: 它送出去的 Item：Job 已入庫的、在路上的（`/jobs` 的「在路上」那一組狀態，需要人的也在裡面），
    #: 與排除條件擋下的（M4 票 13）。
    imported: int
    active: int
    excluded: int
    #: 完結了（`parser.series_finished`）：RSS 頁收進「已完結」。紀錄照舊，新的一筆出現時自己
    #: 變回 `False`。
    finished: bool
    #: 上一次讀它的 Mikan 單一 feed 補舊集或補漏的那一刻；還沒補過、或不是 Mikan 的是 `None`
    #: （M4 票 108）。
    backfilled_at: datetime | None
    #: 這一次呼叫送出去了幾筆。只有 `bind_series` 回的那一份有意義，清單上一律是 0。
    submitted: int = 0
    #: 還沒確認時，第一批在問人什麼（M4 票 11，`first_batch.asks`）：作品頁的「第一批待確認」帶
    #: 這一句。確認過、或還沒有已入庫的集數在等人是 `None`。
    ask: FirstBatchAsk | None = None


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
    #: 發佈名讀出的集數（M4 票 13，Series 展開的清單）；讀不出是 `None`。
    episode: int | None
    #: 「仍然下載」現在會怎麼被拒（`release_item`，M4 票 111）；放行得了是 `None`。不是
    #: `excluded` 的一律 `item_not_excluded`。
    release_blocked: RssRefusal | None


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
    #: Feed 本身抓不到時的原文（也寫進那一列的 `poll_error`）；抓到了是空字串。
    failed: str = ""


@dataclass(frozen=True, slots=True)
class FeedRoutesOutcome:
    feed: FeedView
    #: 這一次當場綁上的 RSS Series。
    bound: int
    #: 綁上之後送出去的。
    submitted: int


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
    awaiting = await _awaiting_counts(session)
    return tuple(
        _feed_view(row, counts.get(row.id, 0), awaiting.get(row.id, KindCounts())) for row in rows
    )


async def _can_add_feed(
    session: AsyncSession,
    *,
    url: str,
    tv_route_id: int | None,
    movie_route_id: int | None,
    exclusions: Sequence[str],
    interval_sec: int,
) -> None:
    """`add_feed` 的乾跑：它在寫入之前的每一項檢查，照同樣的順序。"""
    url = url.strip()
    if kind_of(url) is None:
        raise RssRejectedError(RssRefusal.FEED_UNSUPPORTED, url)
    if await session.scalar(select(RssFeed.id).where(RssFeed.url == url)) is not None:
        raise RssRejectedError(RssRefusal.FEED_DUPLICATE, url)
    _check_interval(interval_sec)
    await _check_routes(session, KindRoutes(tv=tv_route_id, movie=movie_route_id))
    _normalized_rules(exclusions)


@command(
    Effect.REVERSIBLE,
    inverse="rss.delete_feed",
    flags={Flag.CONNECTS_OUT, Flag.SETTINGS},
    about=(
        "Add an RSS feed that Berth polls and downloads from. Only mikanani.me, nyaa.si and "
        "acg.rip feeds are accepted, and the URL must be one the user typed. For each kind "
        "(tv, movie) that has an enabled route, give the route new series of that kind go to."
    ),
    refusals=(RssRefusal,),
    validate=_can_add_feed,
)
async def add_feed(
    session: AsyncSession,
    *,
    url: str,
    name: str = "",
    tv_route_id: int | None = None,
    movie_route_id: int | None = None,
    exclusions: Sequence[str] = (),
    interval_sec: int = DEFAULT_INTERVAL_SEC,
) -> FeedView:
    """加一個 Feed。不當場輪詢——畫面上那一顆「立即輪詢」與背景迴圈會做，這一支只記下來。

    間隔只收 `FEED_INTERVALS` 的檔位（`interval_unsupported`，M4 票 109）。

    排除條件可以一起給（M4 票 110）：Mikan 不預覽、第一輪就自動綁定送單，
    加完再設的擋不到已經送出的。
    寫壞的整個 Feed 都不加（`rule_invalid`，與 `set_feed_exclusions` 同一個檢查）。

    兩條 Route 是自動綁定送進的地方（M4 票 105，照 Sonarr Import List 的 Root Folder 必填）：
    那一種有啟用中的 Route 就要給（`route_required`），一條都沒有時那一格存 `None`
    （`_check_routes`）。
    """
    await _can_add_feed(
        session,
        url=url,
        tv_route_id=tv_route_id,
        movie_route_id=movie_route_id,
        exclusions=exclusions,
        interval_sec=interval_sec,
    )
    url = url.strip()
    kind = kind_of(url)
    assert kind is not None  # `_can_add_feed` 擋過認不得的網址
    rules = _normalized_rules(exclusions)
    row = RssFeed(
        name=name.strip() or _default_name(url),
        url=url,
        kind=kind,
        interval_sec=interval_sec,
        primed_at=utcnow() if kind in _NO_PREVIEW else None,
        tv_route_id=tv_route_id,
        movie_route_id=movie_route_id,
        exclude_json=list(rules),
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise RssRejectedError(RssRefusal.FEED_DUPLICATE, url) from exc
    return _feed_view(row, 0, KindCounts())


def _check_interval(interval_sec: int) -> None:
    if interval_sec not in FEED_INTERVALS:
        raise RssRejectedError(RssRefusal.INTERVAL_UNSUPPORTED, str(interval_sec))


@command(Effect.REVERSIBLE, inverse="rss.set_feed_interval", flags={Flag.SETTINGS})
async def set_feed_interval(session: AsyncSession, feed_id: int, interval_sec: int) -> FeedView:
    """改這個 Feed 的輪詢間隔（M4 票 109）。不當場輪：下一輪照 `poll_due` 的算法，是上一輪
    （`last_polled_at`）加上新的間隔。"""
    row = await session.get(RssFeed, feed_id)
    if row is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    _check_interval(interval_sec)
    row.interval_sec = interval_sec
    await session.commit()
    return await _feed_view_of(session, feed_id)


@command(Effect.REVERSIBLE, flags={Flag.SETTINGS, Flag.DOWNLOADS})
async def set_feed_routes(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed_id: int,
    *,
    tv_route_id: int | None,
    movie_route_id: int | None,
    user_id: int | None = None,
    now: datetime | None = None,
) -> FeedRoutesOutcome:
    """選或改 Feed 的兩條 Route（M4 票 105），檢查同 `add_feed`。

    存下之後**當場綁上**它長出的、因為 Route 不只一條而停在待綁定的 RSS Series
    （`_awaiting_route`）：用它存著的候選（自動綁定判出來的那一部）加上新的 Route 走 `bind_series`
    （`system`），不重新上網查。那一種的 Route 是 `None` 的不綁；其他理由停著的不動；已經綁上的
    不搬家。

    從作品頁訂閱建的 Feed 只看那部作品那一種（`_route_kinds`）：另一種不要求，給了也存 `None`。

    沒有單一的反向命令：Route 再改一次是同一支，當場綁上的由 `unbind_series` 一個一個拆。

    當場綁上送出的是一輪「正在下載」，不告訴改 Route 的人（`user_id`，M4 票 126）。
    """
    row = await session.get(RssFeed, feed_id)
    if row is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    kinds = _route_kinds(row)
    # 用不到的那一種不收：存 `None`，不檢查、不要求。
    chosen = KindRoutes(
        tv=tv_route_id if MediaKind.TV in kinds else None,
        movie=movie_route_id if MediaKind.MOVIE in kinds else None,
    )
    await _check_routes(session, chosen, kinds)
    _set_routes(row, chosen)
    await session.commit()
    bound = submitted = 0
    moment = now or utcnow()
    async with download_round(session, presser=user_id, now=moment) as batch:
        for one in await _awaiting_route(session):
            route_id = chosen.of(one.kind)
            if one.feed_id != feed_id or route_id is None:
                continue
            sent = await _bind_to_feed_route(
                session, factory, one.series_id, one.media_id, route_id, moment, batch
            )
            if sent is not None:
                bound += 1
                submitted += sent
    return FeedRoutesOutcome(
        feed=await _feed_view_of(session, feed_id), bound=bound, submitted=submitted
    )


async def _check_routes(
    session: AsyncSession,
    routes: KindRoutes,
    kinds: tuple[MediaKind, ...] = (MediaKind.TV, MediaKind.MOVIE),
) -> None:
    """Feed 用得到的那幾種（`kinds`）的格子：給了的要在、啟用中、收得下那一種；沒給的那一種不能有
    啟用中的 Route。"""
    for kind in kinds:
        route_id = routes.of(kind)
        if route_id is None:
            if await _routes_for(session, kind):
                raise RssRejectedError(RssRefusal.ROUTE_REQUIRED, kind.value)
            continue
        route = await session.get(Route, route_id)
        if route is None:
            raise RssRejectedError(RssRefusal.ROUTE_MISSING, str(route_id))
        if not route.enabled:
            raise RssRejectedError(RssRefusal.ROUTE_DISABLED, route.slug)
        if route.collection_type is not collection_type_for(kind):
            raise RssRejectedError(
                RssRefusal.ROUTE_KIND_MISMATCH, f"{route.slug} holds {route.collection_type.value}"
            )


def _route_kinds(feed: RssFeed) -> tuple[MediaKind, ...]:
    """這個 Feed 用得到哪幾種的 Route。從作品頁訂閱建的（`media_id` 有值）長出的每一個都綁到那一部
    （`_prebind`），另一種那一格永遠用不到；其他的兩種都用得到。"""
    parsed = parse_media_id(feed.media_id) if feed.media_id is not None else None
    return (parsed[0],) if parsed is not None else (MediaKind.TV, MediaKind.MOVIE)


async def _grown_by(session: AsyncSession, series_id: int | None = None) -> dict[int, int]:
    """RSS Series → 長出它的 Feed：它最早那一筆 Feed Item 的 Feed（M4 票 105）。給 `series_id`
    只問那一個。

    RSS Series 不屬於任何一個 Feed（`CONTEXT.md`），這是從 Item 推的，不是一個欄位。那一筆跟著
    Feed 刪掉之後，剩下的最早那一筆就是。
    """
    first = select(RssItem.series_id, func.min(RssItem.id).label("first")).group_by(
        RssItem.series_id
    )
    first = first.where(
        RssItem.series_id.is_not(None) if series_id is None else RssItem.series_id == series_id
    )
    picked = first.subquery()
    rows = await session.execute(
        select(picked.c.series_id, RssItem.feed_id).join(RssItem, RssItem.id == picked.c.first)
    )
    return {series: feed for series, feed in rows.tuples() if series is not None}


async def _awaiting_route(session: AsyncSession) -> list[_AwaitingRoute]:
    """因為 Route 不只一條而停在待綁定、候選認得出種類的 RSS Series，連同長出它的 Feed。"""
    rows = await session.scalars(
        select(RssSeries)
        .where(RssSeries.media_id.is_(None), RssSeries.reasons_json.is_not(None))
        .order_by(RssSeries.id)
    )
    waiting = [
        row
        for row in rows
        if row.candidates_json
        and any(reason.code is BindReasonCode.ROUTE_AMBIGUOUS for reason in _reasons(row))
    ]
    if not waiting:
        return []
    grown = await _grown_by(session)
    found: list[_AwaitingRoute] = []
    for row in waiting:
        media_id = (row.candidates_json or [""])[0]
        parsed = parse_media_id(media_id)
        if parsed is not None and row.id in grown:
            found.append(_AwaitingRoute(row.id, grown[row.id], media_id, parsed[0]))
    return found


async def _awaiting_counts(session: AsyncSession) -> dict[int, KindCounts]:
    tally: dict[int, dict[MediaKind, int]] = {}
    for one in await _awaiting_route(session):
        kinds = tally.setdefault(one.feed_id, {})
        kinds[one.kind] = kinds.get(one.kind, 0) + 1
    return {
        feed: KindCounts(tv=kinds.get(MediaKind.TV, 0), movie=kinds.get(MediaKind.MOVIE, 0))
        for feed, kinds in tally.items()
    }


async def _bind_to_feed_route(
    session: AsyncSession,
    factory: ServiceClientFactory,
    series_id: int,
    media_id: str,
    route_id: int,
    moment: datetime,
    batch: DownloadRound,
) -> int | None:
    """Feed 選了 Route 之後綁上一個停在 `route_ambiguous` 的：理由那一條換成依據再綁（送單把它帶進
    時間線，同 `_auto_bind`）。綁不上（作品不在了、另一個分頁先綁了）收回原本的理由，回 `None`。"""
    series = await session.get(RssSeries, series_id)
    route = await session.get(Route, route_id)
    if series is None or route is None:
        return None
    before = _reasons(series)
    candidates = tuple(series.candidates_json or ())
    ground = because(BindReasonCode.FEED_ROUTE, route=route.name)
    kept = tuple(one for one in before if one.code is not BindReasonCode.ROUTE_AMBIGUOUS)
    await _note(session, series_id, (*kept, ground), candidates)
    try:
        bound = await _bind(
            session,
            factory,
            series_id,
            media_id=media_id,
            route_id=route_id,
            bound_by=SYSTEM,
            moment=moment,
            batch=batch,
        )
    except RssRejectedError as refusal:
        await _note(session, series_id, before, candidates)
        logger.info(
            "rss series not bound to the feed's new route",
            extra={"series": series_id, "reason": refusal.reason.value},
        )
        return None
    logger.info("rss series bound to the feed's new route", extra={"series": series_id})
    return bound.submitted


@command(
    Effect.IRREVERSIBLE,
    flags={Flag.SETTINGS},
    about=(
        "Delete an RSS feed (a subscription) by feed_id from list_subscriptions or a "
        "subscription's result: Berth stops polling it and forgets its items. Downloaded and "
        "imported files stay, and so do the works it was bound to. Use it when the user wants "
        "a subscription gone, e.g. a duplicate of another one."
    ),
    refusals=(RssRefusal,),
)
async def delete_feed(session: AsyncSession, feed_id: int) -> int:
    """刪 Feed 連它的 Item 一起刪，RSS Series 與綁定留著（shape §4）。回刪掉幾筆 Item。

    **不可逆**（M5 票 02，R4）：Item 上的排除理由、人放行過、第一輪選了什麼都跟著刪；加回同一個
    網址長出的是新的 Item，feed 只帶得到最近那幾筆，已經捲出去的回不來。
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


def _feed_view(row: RssFeed, items: int, awaiting: KindCounts) -> FeedView:
    kinds = _route_kinds(row)
    awaiting = KindCounts(
        tv=awaiting.tv if MediaKind.TV in kinds else 0,
        movie=awaiting.movie if MediaKind.MOVIE in kinds else 0,
    )
    return FeedView(
        id=row.id,
        name=row.name,
        url=row.url,
        kind=row.kind,
        interval_sec=row.interval_sec,
        last_polled_at=row.last_polled_at,
        poll_error=row.poll_error,
        backfill_error=row.backfill_error,
        items=items,
        exclusions=tuple(row.exclude_json),
        primed_at=row.primed_at,
        tv_route_id=row.tv_route_id,
        movie_route_id=row.movie_route_id,
        route_kinds=kinds,
        ever_read=_ever_read(row, items),
        awaiting_route=awaiting,
    )


# --- 第一輪預覽 ---------------------------------------------------------


def _ever_read(feed: RssFeed, items: int) -> bool:
    """這個 Feed 至少讀到過一次：輪過、而且不是「一筆都沒有又失敗」。

    讀不到的那一輪照樣寫 `last_polled_at`（輪詢的間隔靠它），所以光看它不夠——連不上的
    Feed 預覽是空的，「全部下載」等於替沒看過的整份歷史做決定（M3 票 21）。畫面讀
    `FeedView.ever_read`，不自己再算一次。
    """
    return feed.last_polled_at is not None and (not feed.poll_error or items > 0)


async def _items_of(session: AsyncSession, feed_id: int) -> int:
    items = await session.scalar(
        select(func.count()).select_from(RssItem).where(RssItem.feed_id == feed_id)
    )
    return int(items or 0)


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
        view = await _item_view(session, row)
        series = await session.get(RssSeries, row.series_id) if row.series_id else None
        if row.status in _WAITING and series is not None:
            held = await _held_back(session, row, series)
            if held is not None:
                skip, job_hash = held
                view = replace(view, status=FeedItemStatus.DUPLICATE, skip=skip, job_hash=job_hash)
        views.append(view)
    return tuple(views)


@command(Effect.IRREVERSIBLE, flags={Flag.DOWNLOADS})
async def prime_feed(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed_id: int,
    *,
    mode: PrimeMode,
    user_id: int | None = None,
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
    if mode is PrimeMode.ALL and not _ever_read(feed, await _items_of(session, feed_id)):
        raise RssRejectedError(RssRefusal.FEED_UNREAD, str(feed_id))
    if mode is PrimeMode.LATER:
        polled = await poll_feed(session, factory, feed_id, user_id=user_id, now=now)
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
        async with download_round(session, presser=user_id, now=now or utcnow()) as batch:
            submitted = await _submit_waiting(session, factory, RssItem.feed_id == feed_id, batch)
    excluded = await session.scalar(
        select(func.count())
        .select_from(RssItem)
        .where(RssItem.feed_id == feed_id, RssItem.status == FeedItemStatus.EXCLUDED)
    )
    return PrimeOutcome(
        feed=await _feed_view_of(session, feed_id),
        submitted=submitted,
        passed=passed,
        excluded=int(excluded or 0),
    )


# --- 輪詢 ---------------------------------------------------------------


@command(Effect.REVERSIBLE, flags={Flag.INTERNAL, Flag.DOWNLOADS})
async def poll_due(
    session: AsyncSession, factory: ServiceClientFactory, *, now: datetime | None = None
) -> int:
    """到時間的每一個 Feed 各輪一次（`rss_poller` 的一輪，plan §3.2）。回輪了幾個。

    **一個 Feed 爆掉不拖累其他的**：非預期的例外記 log、寫進那一列的 `poll_error`，接著輪下一個。
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
    _note_poll(row, detail, moment)
    await session.commit()


def _note_poll(feed: RssFeed, error: str, moment: datetime) -> None:
    """記這一輪輪詢的結果：`error` 空的是成功。由成功轉失敗的那一輪起算「一直失敗」，成功就清掉
    （巡檢的「一直失敗的 Feed」讀它，M4 票 130）。"""
    feed.poll_error = error
    feed.poll_failing_since = (feed.poll_failing_since or moment) if error else None


def _note_backfill(feed: RssFeed, error: str, moment: datetime) -> None:
    """記這一輪每日補漏的結果，同 `_note_poll`。"""
    feed.backfill_error = error
    feed.backfill_failing_since = (feed.backfill_failing_since or moment) if error else None


@command(Effect.REVERSIBLE, flags={Flag.DOWNLOADS})
async def poll_feed(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed_id: int,
    *,
    user_id: int | None = None,
    now: datetime | None = None,
) -> PollOutcome:
    """一個 Feed 的一輪。抓不到 Feed 時失敗記在那一列，不丟例外（畫面上的「立即輪詢」照樣回 200）。

    `user_id` 是按「立即輪詢」的人：這一輪送出的「正在下載」不告訴他（M4 票 126）；背景輪詢沒有。

    可逆但沒有單一反向命令：它長出的 Item 與 Series 是紀錄，送出去的 Job 有自己的刪除範圍。

    **同一個 Feed 一次只輪一輪，後到的拿正在跑的那一輪的結果**（`_rounds`；Go `singleflight` 的
    做法）：人按「立即輪詢」時背景 poller 也可能正挑到它（剛加的 Feed 從沒輪過，兩邊同時到）。兩輪
    一起跑會各長一次同一個 RSS Series、撞 `rss_series.key` 的 unique（2026-09-27 真服務 e2e）；
    排隊再輪一次則讀到的全是看過的 Item，畫面說「新 0 筆」而那幾筆剛被前一輪收下（M4 票 13c），
    也多打那一站一次。後到的拿的是前一輪的 `now` 算出的結果；前一輪沒做完就結束（例外、被
    cancel）時，後到的自己再輪。
    """
    while (running := _rounds.get(feed_id)) is not None:
        # shield：後到的被 cancel 時不能連帶 cancel 別人也在等的那一個結果。
        if (shared := await asyncio.shield(running)) is not None:
            return shared
    running = asyncio.get_running_loop().create_future()
    _rounds[feed_id] = running
    outcome = None
    try:
        outcome = await _poll_feed(session, factory, feed_id, user_id=user_id, now=now)
        return outcome
    finally:
        del _rounds[feed_id]
        running.set_result(outcome)


async def _poll_feed(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed_id: int,
    *,
    user_id: int | None,
    now: datetime | None,
) -> PollOutcome:
    moment = now or utcnow()
    feed = await session.get(RssFeed, feed_id)
    if feed is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    # 這一輪送出的（自動綁定、預先綁定的補送也算）合成「正在下載」（M4 票 126）。
    async with download_round(session, presser=user_id, now=moment) as batch:
        return await _poll_round(session, factory, feed, moment, batch)


async def _poll_round(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed: RssFeed,
    moment: datetime,
    batch: DownloadRound,
) -> PollOutcome:
    feed_id = feed.id
    fetcher = factory.rss()
    bound = submitted = 0
    try:
        try:
            found = _of_subgroup(feed, parse_items(feed.kind, await fetcher.fetch(feed.url)))
        except ServiceError as exc:
            feed.last_polled_at = moment
            _note_poll(feed, message(exc), moment)
            await session.commit()
            logger.warning(
                "rss feed could not be fetched", extra={"feed": feed.id, "error": feed.poll_error}
            )
            return PollOutcome(items=0, series=0, bound=0, submitted=0, failed=feed.poll_error)
        fresh = await _unseen(session, feed.id, found)
        # 單集頁在寫之前抓完（plan §3.3）：一頁一個請求、逾時 30 秒，寫下第一筆之後才抓第二頁的話，
        # 整輪都握著寫鎖。
        keys, unkeyed = await _series_keys(fetcher, feed.kind, fresh)
        items, grown = await _record(session, feed, fresh, moment, keys=keys)
        feed.last_polled_at = moment
        # 讀到了：略過幾筆認不出 Series 的照寫原因，但不算輪詢失敗（巡檢的「輪詢一直失敗」說的是
        # 整個 Feed 讀不到，M4 票 130）。
        _note_poll(feed, "", moment)
        feed.poll_error = f"{len(unkeyed)} item(s) skipped: {unkeyed[0]}" if unkeyed else ""
        await session.commit()
        # 番組頁要同一個 fetcher 抓，所以在它關掉之前認。同一部的不同字幕組共用一頁（票 82）。
        pages = _ShowPages(fetcher)
        for series_id in grown:
            sent = await _prebind(session, factory, feed_id, series_id, moment, batch)
            if sent is None:
                sent = await _auto_bind(session, factory, pages, feed, series_id, moment, batch)
            if sent is not None:
                bound += 1
                submitted += sent
        # 從 Media 頁建的 Feed 也帶到別的 Feed 先長出、還在待綁定的 Series（同一個字幕組）：
        # 一樣綁上。
        for series_id in await _waiting_series(session, feed_id):
            sent = await _prebind(session, factory, feed_id, series_id, moment, batch)
            if sent is not None:
                bound += 1
                submitted += sent
        # 暫時查不到、重認時間到了的（M4 票 14）：只有它們在長出來之後的輪詢裡重認。
        # 這一輪才長出來的剛認過，不再撞一次。
        for series_id in await _due_lookups(session, feed_id, moment, skip=grown):
            sent = await _auto_bind(session, factory, pages, feed, series_id, moment, batch)
            if sent is not None:
                bound += 1
                submitted += sent
    finally:
        await fetcher.aclose()
    await _backfill_due(session, factory, feed_id, moment)
    submitted += await _submit_waiting(session, factory, RssItem.feed_id == feed_id, batch)
    return PollOutcome(items=items, series=len(grown), bound=bound, submitted=submitted)


def _of_subgroup(feed: RssFeed, found: Sequence[FeedItem]) -> Sequence[FeedItem]:
    """只收一個字幕組的 Feed（M5 票 26）：別的字幕組的發佈不寫、不長 RSS Series，等於沒出現過。
    寫成 Item 的話它們會長出待綁定的 Series，而那正是使用者說不要的（試用機上每一組都綁上了）。"""
    if not feed.subgroup:
        return found
    return tuple(item for item in found if of_group(item.title, feed.subgroup))


def parse_items(kind: FeedKind, content: bytes) -> tuple[FeedItem, ...]:
    """種類 → 那一站的 mapper。認不出 feed 格式丟 `ProtocolMismatchError`（`rss/feed.py`）。"""
    match kind:
        case FeedKind.MIKAN:
            return mikan.parse_feed(content)
        case FeedKind.NYAA:
            return nyaa.parse_feed(content)
        case FeedKind.ACGRIP:
            return acgrip.parse_feed(content)


async def _unseen(session: AsyncSession, feed_id: int, found: Sequence[FeedItem]) -> list[FeedItem]:
    """`found` 裡這個 Feed 還沒寫過的那幾筆，**舊的在前**。同一份裡重複的 GUID 只留一筆。

    舊的在前：feed 是新的在前，送單照寫入順序走，第 11 集先於第 12 集進 qBittorrent。
    """
    seen = set(
        await session.scalars(
            select(RssItem.guid).where(
                RssItem.feed_id == feed_id, RssItem.guid.in_([item.guid for item in found])
            )
        )
    )
    fresh: list[FeedItem] = []
    for item in reversed(found):
        if item.guid not in seen:
            seen.add(item.guid)
            fresh.append(item)
    return fresh


async def _series_keys(
    fetcher: FeedFetcher, kind: FeedKind, items: Sequence[FeedItem]
) -> tuple[dict[str, str], list[str]]:
    """每一筆屬於哪一個 RSS Series（GUID → 鍵），加上認不出來的那幾筆的原因。只打網路、不寫。"""
    keys: dict[str, str] = {}
    unkeyed: list[str] = []
    for item in items:
        try:
            keys[item.guid] = await _series_key(fetcher, kind, item)
        except _UnkeyedError as failed:
            unkeyed.append(str(failed))
    return keys, unkeyed


async def _record(
    session: AsyncSession,
    feed: RssFeed,
    fresh: Sequence[FeedItem],
    moment: datetime,
    *,
    keys: Mapping[str, str] | None = None,
    known: RssSeries | None = None,
) -> tuple[int, list[int]]:
    """寫下這一輪新看到的 Item（`_unseen` 挑出來的）。回（新 Item 數、新 Series 的 id）。

    **不打網路**（plan §3.3）：RSS Series 的鍵由呼叫的一方先問好（`_series_keys`）。`keys` 裡沒有的
    那一筆（單集頁抓不到、改版了）**不寫**：寫了就是見過，下一輪不會再試。

    `known` 是補舊集讀的單一 feed：每一筆都屬於那一個 RSS Series，沒有鍵要認。
    """
    items = 0
    grown: list[int] = []
    settings = await read_settings(session, RssSettings)
    for item in fresh:
        if known is not None:
            series = known
        else:
            key = (keys or {}).get(item.guid)
            if key is None:
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
                status=_arriving(series, skip),
                skip_json=_dump(skip),
            )
        )
        items += 1
    await session.flush()
    return items, grown


def _arriving(series: RssSeries, skip: SkipReason | None) -> FeedItemStatus:
    """剛寫下的那一筆從哪一個狀態起步。"""
    if skip is not None:
        return FeedItemStatus.EXCLUDED
    if series.media_id is None:
        return FeedItemStatus.UNBOUND
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
    """找到或長出這個鍵的 RSS Series。回（那一列, 是不是這一輪長出來的）。

    鍵跨 Feed 共用（nyaa / acg.rip 是標題骨幹），所以**別的 Feed 可能同時在長同一個**（M5 票 24：
    同一步並行的兩個搜尋訂閱；背景輪詢與「立即輪詢」不同 Feed 時也一樣）。`_rounds` 只排同一個
    Feed。長出交給資料庫的 unique：`INSERT … ON CONFLICT DO NOTHING`，搶輸的讀回別人長的那一列、
    不算這一輪長出來的（與它晚一輪才讀到是同一個結果）。
    """
    row = await session.scalar(select(RssSeries).where(RssSeries.key == key))
    if row is not None:
        return row, False
    values: dict[str, object] = {"key": key, "title_raw": item.title}
    if key.startswith("mikan:"):
        _, bangumi, subgroup = key.split(":")
        values |= {"mikan_bangumi_id": int(bangumi), "mikan_subgroup_id": int(subgroup)}
    grown = await session.scalar(
        sqlite_insert(RssSeries)
        .values(values)
        .on_conflict_do_nothing(index_elements=[RssSeries.key])
        .returning(RssSeries.id)
    )
    row = await session.scalar(select(RssSeries).where(RssSeries.key == key))
    assert row is not None  # 剛插入，或搶贏的那一邊已經 commit
    return row, grown is not None


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


async def _read_season(factory: ServiceClientFactory, series: RssSeries) -> mikan.SingleFeed | str:
    """讀這個 Mikan RSS Series 的單一 feed（整季）。讀不到回原文（英文）。

    **只打網路、不寫**（plan §3.3）：呼叫的一方在改任何東西之前讀它，讀完再交給 `_backfill` 寫。
    """
    assert series.mikan_bangumi_id is not None and series.mikan_subgroup_id is not None
    url = mikan.bangumi_feed_url(series.mikan_bangumi_id, series.mikan_subgroup_id)
    fetcher = factory.rss()
    try:
        return mikan.parse_single_feed(await fetcher.fetch(url))
    except ServiceError as exc:
        logger.warning(
            "rss backfill could not read the single feed; the next round tries again",
            extra={"series": series.id, "error": message(exc)},
        )
        return message(exc)
    finally:
        await fetcher.aclose()


async def _backfill(
    session: AsyncSession,
    home: RssFeed,
    series: RssSeries,
    season: mikan.SingleFeed,
    moment: datetime,
) -> None:
    """把讀到的整季裡沒見過的寫成 `home` 的 Item，記下補過的時間。不 commit（呼叫的一方與自己的
    改動一起）。

    單一 feed 的 channel 標題帶著番組名（M4 票 13）：還沒有名字的 Series 順手記下——補漏每天讀它，
    自動綁定之前就長出來、或讀不到番組頁的 Series 也就有了名字，不為了顯示多打 Mikan。
    """
    fresh = await _unseen(session, home.id, season.items)
    await _record(session, home, fresh, moment, known=series)
    series.backfilled_at = moment
    series.mikan_bangumi_name = series.mikan_bangumi_name or season.bangumi


async def _backfill_due(
    session: AsyncSession, factory: ServiceClientFactory, feed_id: int, moment: datetime
) -> None:
    """每日補漏：這個 Feed 是 home 的、綁好的 Mikan RSS Series，上次補過滿一天（或還沒補過）的各讀
    一次單一 feed（plan §3.2、M4 票 108）。**完結之後再補最後一次才停**（`_backfill_settled`，M4 票
    116）：停機跨過 `QUIET_AFTER` 時，被聚合 feed 捲掉的最後幾集靠這一次接住。完結照現況算，新的
    一筆出現時條件自己不成立，補漏也就恢復。

    讀不到的那一個記在這個 Feed 的 `backfill_error`、`backfilled_at` 不動，下一輪再試；一個讀不到
    不拖累其他的。該補的都讀到了（或沒有該補的）就清掉那一欄：讀不到的那一個每一輪都還在該補的
    清單上。補下來的由 `poll_feed` 最後那一次 `_submit_waiting` 送出。
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
        if home is None or home.id != feed_id or await _backfill_settled(session, series, moment):
            continue
        season = await _read_season(factory, series)
        if isinstance(season, str):
            failures.append(f"backfill {series.key}: {season}")
            continue
        await _backfill(session, feed, series, season, moment)
        await session.commit()
    _note_backfill(feed, "; ".join(failures), moment)
    await session.commit()


async def _submit_waiting(
    session: AsyncSession,
    factory: ServiceClientFactory,
    scope: ColumnElement[bool],
    batch: DownloadRound,
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
        sent += await _submit(session, factory, item, batch)
    return sent


@command(Effect.REVERSIBLE, flags={Flag.DOWNLOADS})
async def release_item(
    session: AsyncSession,
    factory: ServiceClientFactory,
    item_id: int,
    *,
    user_id: int | None = None,
) -> ItemView:
    """放行一筆 `excluded` 的 Item，**當場送出**（brief §15「全部接受，只排除」、M4 票 111）。

    逐筆、人按的例外，不違反「只往前看」：那一條防的是改規則時批次放回。照 Sonarr 互動搜尋的
    「照樣下載」：理由看得到，仍可以逐筆送。

    走 `_submit_waiting` 同一支 `_submit`（`trigger = rss`、帶 RSS Series id），送單時的去重照常：
    同一個 torrent 已送過、帳本已有就成 `duplicate`。**送不出就留在 `excluded`**，帶著送單那一頭的
    原文（`error`）；不放回 `matched` 等下一輪——下次改規則時 `_rescreen` 不看已排除的，也不另記
    「人放行過」。

    只放行 RSS Series 已綁定、Feed 已選過第一輪的；其他在改任何東西之前就拒絕。

    **沒有單一的反向命令**：送成的那一筆是 Job，撤銷是刪 Job（它有自己的刪除範圍），Item 不回到
    `excluded`——與 `subscribe_mikan` 同一種標法。
    """
    item = await session.get(RssItem, item_id)
    if item is None:
        raise RssRejectedError(RssRefusal.ITEM_MISSING, str(item_id))
    blocked = await _release_block(session, item)
    if blocked is not None:
        raise blocked
    async with download_round(session, presser=user_id, now=utcnow()) as batch:
        await _submit(session, factory, item, batch)
    row = await session.get(RssItem, item_id, populate_existing=True)
    assert row is not None
    logger.info("rss item released", extra={"item": item_id, "status": row.status.value})
    return await _item_view(session, row)


async def _release_block(session: AsyncSession, item: RssItem) -> RssRejectedError | None:
    """`release_item` 現在會怎麼拒絕這一筆；放行得了是 `None`。清單照它的 `reason` 把按鈕停用、
    說出原因。"""
    if item.status is not FeedItemStatus.EXCLUDED:
        return RssRejectedError(RssRefusal.ITEM_NOT_EXCLUDED, item.status.value)
    series = await session.get(RssSeries, item.series_id) if item.series_id is not None else None
    if series is None or series.media_id is None:
        return RssRejectedError(RssRefusal.SERIES_UNBOUND, str(item.series_id))
    if series.route_id is None:
        # Route 刪除時外鍵 `SET NULL` 留下的（票 115 之後刪不掉被綁著的 Route，舊的還在）。
        return RssRejectedError(RssRefusal.ROUTE_MISSING, str(series.id))
    feed = await session.get(RssFeed, item.feed_id)
    if feed is None or feed.primed_at is None:
        return RssRejectedError(RssRefusal.FEED_UNPRIMED, str(item.feed_id))
    return None


async def _submit(
    session: AsyncSession, factory: ServiceClientFactory, item: RssItem, batch: DownloadRound
) -> int:
    """送一筆。成了是 `downloaded` 加 Job 的 hash；被拒留在原本的狀態（`matched`，或放行的
    `excluded`）帶著原文。回 1 或 0。"""
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
                size=item.size or 0,
            ),
            media_id=series.media_id,
            route_id=series.route_id,
            user_id=None,
            trigger=JobTrigger.RSS,
            trigger_ref=str(series.id),
            grounds=_reasons(series) if series.bound_by == SYSTEM else (),
            actor=rss_label(str(series.id)),
        )
    except JobRejectedError as refusal:
        # `add_download` 可能 rollback 過，那一列要重讀。
        row = await session.get(RssItem, item_id)
        if row is not None:
            row.error = f"{refusal.reason}: {refusal.detail}" if refusal.detail else refusal.reason
            await session.commit()
        logger.info("rss item not sent", extra={"item": item_id, "reason": refusal.reason.value})
        return 0
    batch.note(outcome)
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


# 收 ORM 列，是別的命令同一個交易的一段：不進登錄表（M5 票 06）。
@command(Effect.READ, flags={Flag.INTERNAL})
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

    季集照規劃時的算法猜（`plan.guess_from_title`）；猜不到、或信心不夠自動入庫的不擋——規劃時
    那一層（`services/plan._against_ledger`）照樣會比，漏在這裡只是多下載一次，擋錯了卻是少一集。
    比的範圍與那一層相同：同一個資料夾。

    **Tags 比兩處**：帳本那一列的 Tags 是從 torrent 裡的**檔名**讀的，字幕組常在檔名寫另一個組名
    （發佈名 `[喵萌奶茶屋&LoliHouse]`、檔名 `[LoliHouse]`），只比它的話同一個發佈換個 hash
    重新上傳就認不出來。所以也拿那一列的 Job 的發佈名算一次 Tags——標題對標題。**讀不出字幕組的
    標題不比這一半**：兩邊的 Tags 都可能是空的，空對空不是同一個版本。
    """
    snapshot = media.stored_snapshot()
    if snapshot is None:
        return None
    guess = guess_from_title(title, snapshot=snapshot, series=series, published=published)
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


@command(Effect.REVERSIBLE, flags={Flag.SETTINGS})
async def set_exclusions(
    session: AsyncSession, *, not_single: bool, rules: Sequence[str]
) -> ExclusionsView:
    """整組覆寫全域那一層。

    沒有單一反向命令（M5 票 02）：規則可以帶回原本的值，但 `_rescreen` 只收緊，這一次擋下的那幾筆
    不會跟著放回來，要逐筆 `release_item`。擋下的本來就還沒下載，所以仍算可逆。另外兩層同理。
    """
    kept = _normalized_rules(rules)

    def change(value: RssSettings) -> None:
        value.exclude_not_single = not_single
        value.exclude = list(kept)

    saved = await update_settings(session, RssSettings, change)
    await _rescreen(session, None)
    return ExclusionsView(not_single=saved.exclude_not_single, rules=tuple(saved.exclude))


@command(Effect.REVERSIBLE, flags={Flag.SETTINGS})
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
    return await _feed_view_of(session, feed_id)


@command(Effect.REVERSIBLE, flags={Flag.SETTINGS})
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


async def _prebind(
    session: AsyncSession,
    factory: ServiceClientFactory,
    feed_id: int,
    series_id: int,
    moment: datetime,
    batch: DownloadRound,
) -> int | None:
    """從 Media 頁建的搜尋 feed（票 19）帶著作品，Route 是那一種的那一格：人在建 Feed 時就說了
    「這是那一部」，它帶到的 RSS Series 直接以他的身分綁，不去認。綁上了回送出幾筆；不是這種 Feed、
    或綁不上（Route 之後停用了、作品被刪了）是 `None`，新長出的那一種照一般的路去認作品。
    """
    feed = await session.get(RssFeed, feed_id)
    if feed is None or feed.media_id is None:
        return None
    parsed = parse_media_id(feed.media_id)
    route_id = KindRoutes.of_feed(feed).of(parsed[0]) if parsed is not None else None
    if route_id is None:
        return None
    try:
        bound = await _bind(
            session,
            factory,
            series_id,
            media_id=feed.media_id,
            route_id=route_id,
            bound_by=label_of(feed.user_id),
            moment=moment,
            batch=batch,
        )
    except RssRejectedError as refusal:
        logger.info(
            "rss series not bound to its feed's work",
            extra={"series": series_id, "reason": refusal.reason.value},
        )
        return None
    return bound.submitted


async def _waiting_series(session: AsyncSession, feed_id: int) -> list[int]:
    """這個 Feed 帶到、還在待綁定的 RSS Series。只看預先綁定作品的 Feed，其他的留給人。"""
    feed = await session.get(RssFeed, feed_id)
    if feed is None or feed.media_id is None:
        return []
    rows = await session.scalars(
        select(RssSeries.id)
        .where(
            RssSeries.media_id.is_(None),
            RssSeries.id.in_(select(RssItem.series_id).where(RssItem.feed_id == feed_id)),
        )
        .order_by(RssSeries.id)
    )
    return list(rows)


class _LookupError(Exception):
    """番組頁或 TMDB 這一次查不到。訊息是原文（英文），進理由的 `detail`。"""

    def __init__(self, detail: str, *, site: str, transient: bool) -> None:
        super().__init__(detail)
        #: 哪一站（`_site_of`）。
        self.site = site
        #: 等一下再問可能就好了（`adapters.http.is_transient`）。
        self.transient = transient


async def _due_lookups(
    session: AsyncSession, feed_id: int, moment: datetime, *, skip: Sequence[int] = ()
) -> list[int]:
    """這個 Feed 帶到、該再認一次的 RSS Series：暫時查不到、重認的時間到了的（`lookup_retry`，
    M4 票 14）。"""
    rows = await session.scalars(
        select(RssSeries)
        .where(
            RssSeries.media_id.is_(None),
            RssSeries.id.in_(select(RssItem.series_id).where(RssItem.feed_id == feed_id)),
        )
        .order_by(RssSeries.id)
    )
    return [row.id for row in rows if row.id not in skip and _due(_reasons(row), moment)]


def _due(reasons: Sequence[BindReason], moment: datetime) -> bool:
    retrying = _retrying(reasons)
    return retrying is not None and datetime.fromisoformat(str(retrying.params["at"])) <= moment


def _retrying(reasons: Sequence[BindReason]) -> BindReason | None:
    """排著的那一次重認（`lookup_retry`）；沒有是 `None`。重認的排程只存在這一條理由裡。"""
    return next((one for one in reasons if one.code is BindReasonCode.LOOKUP_RETRY), None)


def _retry(series: RssSeries, failed: _LookupError, moment: datetime) -> BindReason | None:
    """暫時的失敗、次數還沒用完時，下一次重認的理由；否則 `None`（落到 `lookup_failed`）。"""
    previous = _retrying(_reasons(series))
    done = int(previous.params["attempt"]) if previous is not None else 0
    if not failed.transient or done >= len(LOOKUP_RETRIES):
        return None
    return because(
        BindReasonCode.LOOKUP_RETRY,
        site=failed.site,
        attempt=done + 1,
        at=(moment + LOOKUP_RETRIES[done]).isoformat(),
        detail=str(failed),
    )


def _given_up(failed: _LookupError) -> BindReason:
    return because(BindReasonCode.LOOKUP_FAILED, detail=str(failed))


async def _auto_bind(
    session: AsyncSession,
    factory: ServiceClientFactory,
    pages: _ShowPages,
    feed: RssFeed,
    series_id: int,
    moment: datetime,
    batch: DownloadRound,
) -> int | None:
    """第一次見到的 RSS Series 去 TMDB 認作品（brief §15「綁定」、票 09）。

    綁上了回送出幾筆，沒綁是 `None`。**在長出來的那一輪做**，之後不在每一輪重認——那會讓一個壞掉的
    番組頁每 15 分鐘打一次，人拆掉的自動綁定也會被綁回去。例外是**暫時**查不到的（`_due_lookups`；
    連不上、逾時、限流、5xx，M4 票 14）：照 `LOOKUP_RETRIES` 退避、有上限地重認；
    用完了、或再問也一樣的（404、回的不是那個服務）留在待綁定、理由寫 `lookup_failed`，
    人手上有搜尋。

    **一部候選讀不到不拖垮整次**：其餘的照判，判得出來就綁；判不出來而缺的那幾部是暫時讀不到的，
    照暫時的失敗晚點再認（缺的那一部可能正是它）；一部都沒讀到才是查不到。

    有把握與否是 `parser.binding.judge` 的事；Route 在這裡挑：TMDB 的類型推得出電影或劇集，
    用 `feed` 那一種的 Route（它得是啟用中的，M4 票 105）；那一格是 `None`（票 105 之前的 Feed）
    或那條停用了，同類型只有一條啟用中的 Route 就是它；否則留在待綁定、作品預填成候選。
    """
    series = await session.get(RssSeries, series_id)
    if series is None or series.media_id is not None:
        return None
    try:
        clues, subgroup = await _clues(pages, series)
        # 番組頁已經抓了：名字順手記下（RSS 頁的來源那一格，M4 票 13）。先寫完再去問 TMDB——
        # 握著寫交易打網路會鎖住整個資料庫（M4 票 01）。
        await _remember_names(session, series_id, clues.title, subgroup)
        shots, missed = await _candidates(session, factory, clues)
    except _LookupError as failed:
        logger.info("rss series lookup failed", extra={"series": series_id, "error": str(failed)})
        await _note(session, series_id, (_retry(series, failed, moment) or _given_up(failed),))
        return None

    verdict = judge(clues, shots)
    if verdict.media is None and missed is not None:
        retry = _retry(series, missed, moment)
        if retry is not None or not shots:
            logger.info(
                "rss series lookup incomplete", extra={"series": series_id, "error": str(missed)}
            )
            await _note(session, series_id, (retry or _given_up(missed),))
            return None
        # 讀到的幾部判不出來、讀不到的那一部不再重認：兩件事都說，讀不到的那一部可能正是它。
        verdict = replace(verdict, reasons=(*verdict.reasons, _given_up(missed)))
    ids = tuple(build_media_id(shot.kind, shot.tmdb_id) for shot in verdict.candidates)
    if verdict.media is None:
        await _note(session, series_id, verdict.reasons, ids)
        return None
    routes = await _routes_for(session, verdict.media.kind)
    kind = verdict.media.kind
    feed_route = KindRoutes.of_feed(feed).of(kind) if kind in _route_kinds(feed) else None
    chosen = _chosen_route(routes, feed_route)
    if chosen is None:
        await _note(session, series_id, (*verdict.reasons, _route_reason(routes)), ids)
        return None
    route, ground = chosen
    await _note(session, series_id, (*verdict.reasons, ground), ids)
    try:
        # 自動綁定照預設補舊集（brief §15）。
        bound = await _bind(
            session,
            factory,
            series_id,
            media_id=ids[0],
            route_id=route.id,
            bound_by=SYSTEM,
            moment=moment,
            batch=batch,
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


class _ShowPages:
    """一輪輪詢讀過的 Mikan 番組頁，以 `bangumi_id` 為鍵（M4 票 82）。

    同一部的不同字幕組是不同的 RSS Series，番組頁卻是同一頁：同一輪只抓一次。
    「一輪」是一個 Feed 的一輪（`_poll_feed`），MyBangumi 聚合 feed 的各字幕組都在裡面。
    **讀不到也記下來**：同一輪其他共用這頁的 Series 拿到同一種失敗（`_LookupError`），
    不各自再打一次。只活在那一輪，下一輪重新讀。
    """

    def __init__(self, fetcher: FeedFetcher) -> None:
        self._fetcher = fetcher
        self._outcomes: dict[int, str | _LookupError] = {}

    async def read(self, bangumi_id: int) -> str:
        """番組頁的原文；讀不到丟 `_LookupError`。"""
        if bangumi_id not in self._outcomes:
            self._outcomes[bangumi_id] = await self._fetch(bangumi_id)
        outcome = self._outcomes[bangumi_id]
        if isinstance(outcome, str):
            return outcome
        # 同一個例外再丟一次：traceback 不疊上前一次的。
        raise outcome.with_traceback(None)

    async def _fetch(self, bangumi_id: int) -> str | _LookupError:
        url = mikan.bangumi_url(bangumi_id)
        try:
            page = await self._fetcher.fetch(url)
        except ServiceError as exc:
            failed = _LookupError(
                f"bangumi page: {message(exc)}", site=_site_of(url), transient=is_transient(exc)
            )
            failed.__cause__ = exc
            return failed
        return page.decode("utf-8", errors="replace")


async def _clues(pages: _ShowPages, series: RssSeries) -> tuple[SeriesClues, str]:
    """番組頁的中文名與開播日期 + 長出它的那一筆發佈名；加上番組頁上這個字幕組的名字（沒有是
    空字串）。

    不是 Mikan 的（Nyaa、acg.rip）沒有番組頁：線索只有發佈名，`judge` 列出候選、一律留給人
    （票 11）。
    """
    if series.mikan_bangumi_id is None:
        clues = SeriesClues(
            title="", premiere=None, release_title=series.title_raw, show_page=False
        )
        return clues, ""
    text = await pages.read(series.mikan_bangumi_id)
    found = mikan.bangumi_page(text)
    subgroup = next(
        (row.name for row in mikan.subgroups(text) if row.id == series.mikan_subgroup_id), ""
    )
    clues = SeriesClues(title=found.title, premiere=found.premiere, release_title=series.title_raw)
    return clues, subgroup


async def _remember_names(
    session: AsyncSession, series_id: int, bangumi: str, subgroup: str
) -> None:
    """記下 Mikan 的番組名與字幕組名（M4 票 13）。讀不到的那一格不蓋掉已經有的。"""
    bangumi, subgroup = bangumi.strip(), subgroup.strip()
    if not bangumi and not subgroup:
        return
    row = await session.get(RssSeries, series_id)
    if row is None:
        return
    row.mikan_bangumi_name = bangumi or row.mikan_bangumi_name
    row.mikan_subgroup_name = subgroup or row.mikan_subgroup_name
    await session.commit()


async def _candidates(
    session: AsyncSession, factory: ServiceClientFactory, clues: SeriesClues
) -> tuple[tuple[MediaSnapshot, ...], _LookupError | None]:
    """線索去 TMDB 搜，每個詞取前 `SEARCH_DEPTH` 筆讀回快照。回（讀得到的, 讀不到的那一次）。

    一個詞搜不到、一部讀不到都跳過、其餘照讀（M4 票 14）；缺了幾次只回一次，暫時的優先——只要有
    一次是暫時的，這一次的缺口就可能補得回來。探索頁同一支搜尋與詳情頁同一支讀取：同一份快取、
    同一條 24 小時規則。
    """
    missed: list[_LookupError] = []
    ids: dict[str, None] = {}
    for term in search_terms(clues):
        found = await search_media(session, factory, term)
        # 搜尋與讀詳情都會寫快取、不 commit（網頁請求由請求結束時 commit）；這裡接著還要打 TMDB，
        # 不先 commit 就是握著寫交易打網路（M4 票 01，`test_write_discipline` 抓到的，M4 票 13）。
        await session.commit()
        if found.problem is not None:
            missed.append(_tmdb_miss(f"tmdb search: {found.detail}", found.problem))
            continue
        for item in found.items[:SEARCH_DEPTH]:
            if could_be(item.kind, item.year, clues.premiere):
                ids.setdefault(item.id, None)
    shots: list[MediaSnapshot] = []
    for media_id in ids:
        read = await read_snapshot_checked(session, factory, media_id)
        await session.commit()
        if read.snapshot is None:
            missed.append(_tmdb_miss(f"tmdb detail: {media_id}: {read.detail}", read.problem))
            continue
        shots.append(read.snapshot)
    missed.sort(key=lambda one: not one.transient)
    return tuple(shots), (missed[0] if missed else None)


def _tmdb_miss(detail: str, problem: TmdbProblem | None) -> _LookupError:
    """TMDB 那一頭讀不到。`unreachable` 是暫時的；它也包含「回的不是 TMDB」（`services.media` 把
    `ServiceError` 一概歸成它），分不開，照暫時的算——多的只是上限內的幾次重認。"""
    transient = problem is TmdbProblem.UNREACHABLE
    return _LookupError(detail, site=_TMDB_SITE, transient=transient)


async def _routes_for(session: AsyncSession, kind: MediaKind) -> list[Route]:
    """收得下這種作品的啟用中 Route，照名稱排（理由的參數照這個順序列）。"""
    rows = await session.scalars(
        select(Route)
        .where(Route.enabled.is_(True), Route.collection_type == collection_type_for(kind))
        .order_by(Route.name, Route.id)
    )
    return list(rows)


def _chosen_route(routes: list[Route], feed_route: int | None) -> tuple[Route, BindReason] | None:
    """收得下的 Route 裡挑一條，連同依據：Feed 說的那一條優先，再來是「只有一條」。"""
    for route in routes:
        if route.id == feed_route:
            return route, because(BindReasonCode.FEED_ROUTE, route=route.name)
    if len(routes) == 1:
        return routes[0], because(BindReasonCode.ONLY_ROUTE, route=routes[0].name)
    return None


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
async def list_series(
    session: AsyncSession, *, media_id: str | None = None, now: datetime | None = None
) -> tuple[SeriesView, ...]:
    """待綁定的排前面（shape §2），同類之內新的在前。

    給 `media_id` 時只列綁在那部作品上的（票 19 的詳情頁）。`now` 是算完結的那一刻。
    """
    query = select(RssSeries).order_by(
        RssSeries.media_id.is_not(None), RssSeries.created_at.desc(), RssSeries.id.desc()
    )
    if media_id is not None:
        query = query.where(RssSeries.media_id == media_id)
    rows = list(await session.scalars(query))
    # 第一批在問什麼一次問完（`first_batch.asks` 收一串 id），不逐列各問一次。
    asked = await first_batch_asks(session, [row.id for row in rows if not row.confirmed])
    moment = now or utcnow()
    return tuple([await _series_view(session, row, asked=asked, now=moment) for row in rows])


@command(Effect.READ)
async def unbound_series(session: AsyncSession) -> list[int]:
    """待綁定的 RSS Series 的 id，小的在前：RSS 頁待綁定段列的就是這幾個（`media_id` 是空的）。
    「有 N 件等你處理」靠它認出哪一件是新的（M4 票 127）。"""
    return list(
        await session.scalars(
            select(RssSeries.id).where(RssSeries.media_id.is_(None)).order_by(RssSeries.id)
        )
    )


@command(Effect.REVERSIBLE, inverse="rss.unbind_series", flags={Flag.DOWNLOADS})
async def bind_series(
    session: AsyncSession,
    factory: ServiceClientFactory,
    series_id: int,
    *,
    media_id: str,
    route_id: int,
    user_id: int | None,
    now: datetime | None = None,
) -> SeriesView:
    """把一個 RSS Series 綁到作品與 Route，凍結資料夾名，然後把它留著的 Item 送出去。

    Route 的健康不在這裡擋：紅燈是「現在送不了」，綁定照樣成立、送單被拒的那幾筆下一輪再送。
    停用與收錯種類是「綁錯了」，當場拒絕、什麼都不改。

    **Mikan 的 RSS Series 同時補舊集**（票 12）：讀單一 feed，聚合 feed 沒帶到的那幾集寫成 Item
    一起送（一律補，M4 票 78；帳本已有、已有 Job 的由送單前的去重跳過）。讀不到不擋綁定，
    `backfilled_at` 留空、下一輪輪詢再補。

    反向命令 `unbind_series` 不收回已經送出去的 Job（同一般送單）。

    送出的那幾筆是一輪「正在下載」（M4 票 126）；人按的綁定不告訴按的人（`user_id`）。
    """
    moment = now or utcnow()
    async with download_round(session, presser=user_id, now=moment) as batch:
        return await _bind(
            session,
            factory,
            series_id,
            media_id=media_id,
            route_id=route_id,
            bound_by=label_of(user_id),
            moment=moment,
            batch=batch,
        )


async def _bind(
    session: AsyncSession,
    factory: ServiceClientFactory,
    series_id: int,
    *,
    media_id: str,
    route_id: int,
    bound_by: str,
    moment: datetime,
    batch: DownloadRound,
) -> SeriesView:
    """`bind_series` 的本體，送出的記在呼叫端那一輪（輪詢裡的自動綁定、訂閱）。`bound_by` 是
    `events.actor` 的寫法（`domain/actor.py`）。"""
    series = await session.get(RssSeries, series_id)
    if series is None:
        raise RssRejectedError(RssRefusal.SERIES_MISSING, str(series_id))
    if series.media_id is not None:
        raise RssRejectedError(RssRefusal.SERIES_BOUND, series.media_id)
    media, route = await _target(session, media_id, route_id)

    home = await _home_feed(session, series)
    # 補舊集的單一 feed 在改任何東西之前讀（plan §3.3）：下面第一個查詢就會把綁定的改動 flush
    # 出去，之後才讀的話 Mikan 那幾秒（逾時 30 秒）都握著寫鎖。
    season = await _read_season(factory, series) if home is not None else None
    series.media_id = media.id
    series.route_id = route.id
    series.bound_by = bound_by
    freeze(media, route)
    waiting = await session.scalars(
        select(RssItem).where(
            RssItem.series_id == series.id, RssItem.status == FeedItemStatus.UNBOUND
        )
    )
    for item in waiting:
        item.status = FeedItemStatus.MATCHED
    if home is not None and isinstance(season, mikan.SingleFeed):
        await _backfill(session, home, series, season, moment)
    await session.commit()
    await _rescreen(session, RssItem.series_id == series_id)
    logger.info("rss series bound", extra={"series": series_id, "media": media_id})

    submitted = await _submit_waiting(session, factory, RssItem.series_id == series_id, batch)
    row = await session.get(RssSeries, series_id)
    assert row is not None
    return replace(await _series_view(session, row), submitted=submitted)


async def _target(session: AsyncSession, media_id: str, route_id: int) -> tuple[Media, Route]:
    """綁定的目的地。停用與收錯種類是「綁錯了」，當場拒絕。"""
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
    return media, route


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


async def _series_view(
    session: AsyncSession,
    row: RssSeries,
    *,
    asked: dict[int, FirstBatchAsk] | None = None,
    now: datetime | None = None,
) -> SeriesView:
    """一個 RSS Series 在畫面上的樣子。`asked` 是清單先整批問好的「第一批在問什麼」；單一個的
    回應（綁定、解除、排除條件）沒給，這裡自己問。"""
    if asked is None:
        asked = {} if row.confirmed else await first_batch_asks(session, [row.id])
    media = await session.get(Media, row.media_id) if row.media_id is not None else None
    route = await session.get(Route, row.route_id) if row.route_id is not None else None
    tally = await _tally(session, row.id)
    latest = await session.scalar(
        select(RssItem)
        .where(RssItem.series_id == row.id, RssItem.status != FeedItemStatus.EXCLUDED)
        .order_by(RssItem.published_at.desc(), RssItem.id.desc())
        .limit(1)
    )
    feed = await session.get(RssFeed, latest.feed_id) if latest is not None else None
    latest_kind = feed.kind if feed is not None else None
    grower_id = (await _grown_by(session, row.id)).get(row.id)
    grower = await session.get(RssFeed, grower_id) if grower_id is not None else None
    snapshot = media.snapshot() if media is not None else None
    finished = await _finished(session, row, snapshot, tally, now or utcnow())
    return SeriesView(
        id=row.id,
        key=row.key,
        title_raw=row.title_raw,
        mikan_bangumi_id=row.mikan_bangumi_id,
        mikan_subgroup_id=row.mikan_subgroup_id,
        mikan_bangumi_name=row.mikan_bangumi_name,
        mikan_subgroup_name=row.mikan_subgroup_name,
        media_id=row.media_id,
        media_title=snapshot.title if snapshot is not None else "",
        media_title_en=media.title_en if media is not None else "",
        route_id=row.route_id,
        route_name=route.name if route is not None else "",
        feed_routes=(
            KindRoutes.of_feed(grower) if grower is not None else KindRoutes(tv=None, movie=None)
        ),
        season=row.season,
        episode_offset=row.episode_offset,
        bound_by=row.bound_by,
        waiting=tally.waiting,
        reasons=_reasons(row),
        candidates=await _candidate_views(session, row.candidates_json or ()),
        exclusions=tuple(row.exclude_json),
        confirmed=row.confirmed,
        search_term=search_term(row.title_raw),
        source=FeedKind.MIKAN if row.mikan_bangumi_id is not None else latest_kind,
        group=parse_release(row.title_raw).group,
        latest_title=latest.title if latest is not None else "",
        latest_at=latest.published_at if latest is not None else None,
        latest_episode=parse_release(latest.title).episode if latest is not None else None,
        imported=tally.imported,
        active=tally.active,
        excluded=tally.excluded,
        finished=finished,
        backfilled_at=row.backfilled_at,
        ask=asked.get(row.id),
    )


@dataclass(frozen=True, slots=True)
class _Tally:
    """一個 RSS Series 的 Item 各在哪裡。"""

    #: 還沒送出去的（待綁定、綁好還沒送成）。
    waiting: int = 0
    imported: int = 0
    #: 送出去了、Job 在 `/jobs` 的「在路上」那一組（還沒入庫也沒被移走）。
    active: int = 0
    excluded: int = 0


#: 「在路上」與 `/jobs` 的預設那一組是同一份定義。
_ACTIVE_JOBS = FILTER_STATES[JobFilter.ACTIVE] or frozenset()


async def _tally(session: AsyncSession, series_id: int) -> _Tally:
    rows = await session.execute(
        select(RssItem.status, Job.state, func.count())
        .select_from(RssItem)
        .outerjoin(Job, Job.hash == RssItem.job_hash)
        .where(RssItem.series_id == series_id)
        .group_by(RssItem.status, Job.state)
    )
    waiting = imported = active = excluded = 0
    for status, state, number in rows:
        if status in _WAITING:
            waiting += number
        elif status is FeedItemStatus.EXCLUDED:
            excluded += number
        elif status is not FeedItemStatus.DOWNLOADED or state is None:
            continue
        elif state is JobState.IMPORTED:
            imported += number
        elif state in _ACTIVE_JOBS:
            active += number
    return _Tally(waiting=waiting, imported=imported, active=active, excluded=excluded)


async def _finished_now(session: AsyncSession, row: RssSeries, moment: datetime) -> bool:
    """`_finished` 自己讀作品與各狀態的筆數：畫面以外（每日補漏）要問完結了沒時用。"""
    media = await session.get(Media, row.media_id) if row.media_id is not None else None
    snapshot = media.snapshot() if media is not None else None
    return await _finished(session, row, snapshot, await _tally(session, row.id), moment)


async def _backfill_settled(session: AsyncSession, row: RssSeries, moment: datetime) -> bool:
    """每日補漏跳過它的條件：現在已完結，**而且**上次補漏那一刻也已完結（M4 票 116）。只看現在的話，
    停機期間播完、重啟時已安靜滿 `QUIET_AFTER` 的 Series 一次都不補，最後幾集就永遠漏了。兩個時間
    點用同一支 `_finished_now`；還沒補過的（`backfilled_at` 是 `None`）照讀。

    上次那一刻是拿**現在**的 Item 與帳本回推的：安靜那條路只會偏保守（最多多讀一次）；TMDB 完結那條
    路可能把當時還沒入庫完的判成已完結，但那條路成立時每一集都已在庫，跳過也不漏。"""
    if row.backfilled_at is None:
        return False
    return await _finished_now(session, row, moment) and await _finished_now(
        session, row, row.backfilled_at
    )


async def _finished(
    session: AsyncSession,
    row: RssSeries,
    snapshot: MediaSnapshot | None,
    tally: _Tally,
    moment: datetime,
) -> bool:
    """`parser.series_finished` 要的現況：最近一筆的發佈時間（沒寫的用看到它的那一刻；一筆都沒有
    用長出來的那一刻）、這個 Series 入庫過的那幾季、這部作品在庫的集數。後兩者只在 TMDB 說完結時
    才查。"""
    published = await session.scalar(
        select(func.max(RssItem.published_at)).where(RssItem.series_id == row.id)
    )
    unstamped = await session.scalar(
        select(func.max(RssItem.seen_at)).where(
            RssItem.series_id == row.id, RssItem.published_at.is_(None)
        )
    )
    stamps = [one for one in (published, unstamped) if one is not None]
    latest = max(stamps) if stamps else row.created_at
    seasons: set[int] = set()
    held: set[tuple[int, int]] = set()
    if snapshot is not None and snapshot.ended and row.media_id is not None:
        seasons = {
            season
            for season in await session.scalars(
                select(LedgerEntry.season)
                .join(Job, Job.hash == LedgerEntry.job_hash)
                .where(
                    Job.trigger == JobTrigger.RSS,
                    Job.trigger_ref == str(row.id),
                    LedgerEntry.media_id == row.media_id,
                    LedgerEntry.action == PlanAction.IMPORT,
                )
                .distinct()
            )
            if season is not None
        }
        spans = await session.execute(
            select(LedgerEntry.season, LedgerEntry.episode_start, LedgerEntry.episode_end).where(
                LedgerEntry.media_id == row.media_id,
                LedgerEntry.action == PlanAction.IMPORT,
                LedgerEntry.season.in_(seasons),
            )
        )
        held = {
            (season, episode)
            for season, start, end in spans
            if season is not None and start is not None
            for episode in range(start, (end or start) + 1)
        }
    return series_finished(
        latest=latest,
        now=moment,
        media=snapshot,
        seasons=seasons,
        held=held,
        open_items=tally.waiting + tally.active,
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


# --- 從 Media 頁訂閱 ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExcludedCount:
    """一種排除理由擋下了幾筆。"""

    code: SkipCode
    count: int


@dataclass(frozen=True, slots=True)
class Subscription:
    """訂閱 Mikan 番組 × 字幕組的結果：它所在的 Feed 與綁好的 RSS Series（`submitted` 含整季）。"""

    feed: FeedView
    series: SeriesView
    #: 這個 RSS Series 被排除條件擋下、沒有自動下載的，照理由分（M4 票 112）：畫面說出幾筆、
    #: 為什麼，指向「只下載現有的」。算的是整個 Series（就地綁定時含聚合 feed 之前擋下的），
    #: 不只這一次讀到的。照 `SkipCode` 的宣告順序，沒有的不列。
    excluded: tuple[ExcludedCount, ...]


async def _can_subscribe_mikan(
    session: AsyncSession, *, bangumi_id: int, subgroup_id: int, media_id: str, route_id: int
) -> None:
    """`subscribe_mikan` 的乾跑：讀單一 feed 之前的檢查（讀不讀得到要真的去讀才知道）。"""
    await _target(session, media_id, route_id)
    series = await session.scalar(
        select(RssSeries).where(RssSeries.key == _mikan_key(bangumi_id, subgroup_id))
    )
    if series is not None and series.media_id is not None:
        raise RssRejectedError(RssRefusal.SERIES_BOUND, series.media_id)
    if series is not None and await _home_feed(session, series) is not None:
        return
    url = mikan.bangumi_feed_url(bangumi_id, subgroup_id)
    if await session.scalar(select(RssFeed.id).where(RssFeed.url == url)) is not None:
        raise RssRejectedError(RssRefusal.FEED_DUPLICATE, url)


def _mikan_key(bangumi_id: int, subgroup_id: int) -> str:
    return f"mikan:{bangumi_id}:{subgroup_id}"


@command(
    Effect.REVERSIBLE,
    flags={Flag.DOWNLOADS},
    about=(
        "Subscribe a work to one Mikan bangumi and subgroup: Berth reads the whole season, "
        "downloads what is out and keeps downloading new episodes into the route. Use ids "
        "taken from earlier tool results. The route must hold the work's kind."
    ),
    refusals=(RssRefusal,),
    validate=_can_subscribe_mikan,
)
async def subscribe_mikan(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    bangumi_id: int,
    subgroup_id: int,
    media_id: str,
    route_id: int,
    user_id: int | None,
    actor: str,
    name: str = "",
    subgroup_name: str = "",
    now: datetime | None = None,
) -> Subscription:
    """從 Media 頁訂閱一個 Mikan 番組 × 字幕組（brief §15「從 Media 頁訂閱」、票 19）。

    `subgroup_name` 是畫面讓人挑的時候從番組頁讀過的名字（M4 票 13），記在 RSS Series 上；
    番組名由單一 feed 的 channel 標題來（`_backfill`）。

    建它的單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`）、當場長出那一個 RSS Series 並走
    `bind_series` 綁上，讀到的整季寫成這個 Feed 的 Item 送出。**鍵從網址就知道**：單一 feed 只有一個
    RSS Series，不必一筆一筆抓單集頁。整季一律補（票 12、M4 票 78）。

    **那個 RSS Series 已經在待綁定**（聚合 feed 帶過）時就地綁它，不多開一條 Feed：補舊集由
    `bind_series` 寫進它原本的 Feed。已經綁了是 `series_bound`。人在場，所以**讀不到單一 feed 就當場
    拒絕**（`feed_unreachable`），不留下沒讀過的 Feed 與沒有名字的 Series。

    **沒有單一的反向命令**：新建 Feed 那一條是 `delete_feed`（綁定留著），就地綁定那一條是
    `unbind_series`——拿前者撤銷後者會刪掉使用者的聚合 feed。已經送出的 Job 有自己的刪除範圍。
    """
    moment = now or utcnow()
    # 綁定與補舊集送出的是同一輪「正在下載」，不告訴按的人（M4 票 126）。
    async with download_round(session, presser=user_id, now=moment) as batch:
        return await _subscribe(
            session,
            factory,
            bangumi_id=bangumi_id,
            subgroup_id=subgroup_id,
            media_id=media_id,
            route_id=route_id,
            bound_by=actor,
            name=name,
            subgroup_name=subgroup_name,
            moment=moment,
            batch=batch,
        )


async def _subscribe(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    bangumi_id: int,
    subgroup_id: int,
    media_id: str,
    route_id: int,
    bound_by: str,
    name: str,
    subgroup_name: str,
    moment: datetime,
    batch: DownloadRound,
) -> Subscription:
    await _can_subscribe_mikan(
        session,
        bangumi_id=bangumi_id,
        subgroup_id=subgroup_id,
        media_id=media_id,
        route_id=route_id,
    )
    key = _mikan_key(bangumi_id, subgroup_id)
    series = await session.scalar(select(RssSeries).where(RssSeries.key == key))
    home = await _home_feed(session, series) if series is not None else None
    if series is not None and home is not None:
        bound = await _bind(
            session,
            factory,
            series.id,
            media_id=media_id,
            route_id=route_id,
            bound_by=bound_by,
            moment=moment,
            batch=batch,
        )
        await _remember_names(session, series.id, "", subgroup_name)
        named = await session.get(RssSeries, series.id, populate_existing=True)
        assert named is not None
        return Subscription(
            feed=await _feed_view_of(session, home.id),
            series=replace(await _series_view(session, named), submitted=bound.submitted),
            excluded=await _excluded_counts(session, series.id),
        )

    url = mikan.bangumi_feed_url(bangumi_id, subgroup_id)
    fetcher = factory.rss()
    try:
        try:
            season = mikan.parse_single_feed(await fetcher.fetch(url))
        except ServiceError as exc:
            raise unread(exc) from exc
        feed = RssFeed(
            name=name.strip() or _default_name(url),
            url=url,
            kind=FeedKind.MIKAN,
            primed_at=moment,
            last_polled_at=moment,
        )
        _set_routes(feed, await _subscribed_routes(session, media_id, route_id, others=True))
        session.add(feed)
        if series is None:
            series = RssSeries(
                key=key,
                title_raw=season.items[0].title if season.items else "",
                mikan_bangumi_id=bangumi_id,
                mikan_subgroup_id=subgroup_id,
            )
            session.add(series)
        await session.flush()
        try:
            bound = await _bind(
                session,
                factory,
                series.id,
                media_id=media_id,
                route_id=route_id,
                bound_by=bound_by,
                moment=moment,
                batch=batch,
            )
        except RssRejectedError:
            # 另一個分頁在這幾秒裡先綁了：剛加的 Feed 與 Series 都還沒 commit。
            await session.rollback()
            raise
        # 單一 feed 就是整季：讀到的每一筆照補舊集的規矩寫下（`known`），這一次也算補過。
        await _backfill(session, feed, series, season, moment)
        await session.commit()
    finally:
        await fetcher.aclose()
    submitted = await _submit_waiting(session, factory, RssItem.feed_id == feed.id, batch)
    await _remember_names(session, series.id, "", subgroup_name)
    row = await session.get(RssSeries, series.id)
    assert row is not None
    return Subscription(
        feed=await _feed_view_of(session, feed.id),
        series=replace(await _series_view(session, row), submitted=bound.submitted + submitted),
        excluded=await _excluded_counts(session, series.id),
    )


async def _excluded_counts(session: AsyncSession, series_id: int) -> tuple[ExcludedCount, ...]:
    rows = await session.scalars(
        select(RssItem).where(
            RssItem.series_id == series_id, RssItem.status == FeedItemStatus.EXCLUDED
        )
    )
    counts = Counter(skip.code for row in rows if (skip := _skip_of(row)) is not None)
    return tuple(ExcludedCount(code=code, count=counts[code]) for code in SkipCode if counts[code])


def _search_url(kind: FeedKind, term: str) -> str:
    match kind:
        case FeedKind.NYAA:
            return nyaa.search_url(term.strip())
        case FeedKind.ACGRIP:
            return acgrip.search_url(term.strip())
        case FeedKind.MIKAN:
            raise RssRejectedError(RssRefusal.FEED_UNSUPPORTED, "mikan has no search feed")


async def _can_subscribe_search(
    session: AsyncSession,
    *,
    kind: FeedKind,
    term: str,
    media_id: str,
    route_id: int,
    subgroup: str = "",
) -> None:
    """`subscribe_search` 的乾跑：建 Feed 之前的檢查。字幕組不在這裡驗：沒搜到的字幕組也訂得了
    （還沒出第一集的），卡片上的選項才是這一次搜到的（`search_subgroups`）。"""
    await _target(session, media_id, route_id)
    url = _search_url(kind, term)
    if await session.scalar(select(RssFeed.id).where(RssFeed.url == url)) is not None:
        raise RssRejectedError(RssRefusal.FEED_DUPLICATE, url)


@command(
    Effect.REVERSIBLE,
    inverse="rss.delete_feed",
    # 給了字幕組就當場送第一批（看參數，照最嚴標，同 `choose_service`）。
    flags={Flag.DOWNLOADS},
    about=(
        "Subscribe a work to one subgroup's releases in a nyaa or acgrip keyword search feed, "
        "for works Mikan does not carry. Give the subgroup you recommend as it appears in "
        "release names; the card lists every subgroup the search finds and the user picks "
        "one. Only that subgroup is bound, and its releases already out are downloaded when "
        "the user confirms. The route must hold the work's kind."
    ),
    refusals=(RssRefusal,),
    validate=_can_subscribe_search,
)
async def subscribe_search(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    kind: FeedKind,
    term: str,
    media_id: str,
    route_id: int,
    user_id: int | None,
    subgroup: str = "",
    now: datetime | None = None,
) -> FeedView:
    """從 Media 頁或對話以作品的標題建一條 Nyaa / acg.rip 搜尋 feed（brief §15、票 19、M5 票 26）。

    Feed 記下作品、Route 與這個人：它長出的每一個 RSS Series 直接綁上（`_prebind`）。
    **當場讀一輪**。

    **沒給字幕組**（Media 頁）：一個字幕組一個 Series、都綁；第一輪停在預覽（票 11），等人選
    「全部下載」或「只追之後的」；讀不到照一般 Feed 記在 `poll_error`，之後的輪詢再讀。

    **給了字幕組**（確認卡，M5 票 26）：Feed 只收那一組的發佈（`RssFeed.subgroup`），別組的不寫。
    第一批（卡上列出的發佈名）人在卡上看過了，所以 Feed 建好就算選過「全部下載」（`primed_at`），
    這一輪綁上的 Series 記成第一批已確認（`confirmed`），不必再到 RSS 頁按。送出的是按下去那一刻
    feed 上的，所以卡上那一份是上限：已經有 Job 的、被排除條件擋下的不送。
    """
    await _can_subscribe_search(session, kind=kind, term=term, media_id=media_id, route_id=route_id)
    moment = now or utcnow()
    url = _search_url(kind, term)
    chosen = subgroup.strip()
    feed = RssFeed(
        name=" · ".join(part for part in (_default_name(url), term.strip(), chosen) if part),
        url=url,
        kind=kind,
        media_id=media_id,
        user_id=user_id,
        subgroup=chosen,
        primed_at=moment if chosen else None,
    )
    # 它只用得到作品那一種（`_route_kinds`）：另一格留空。
    _set_routes(feed, await _subscribed_routes(session, media_id, route_id, others=False))
    session.add(feed)
    try:
        await session.commit()
    except IntegrityError as exc:
        # 檢查之後、commit 之前別人建了同一條（M5 票 24：同一步並行的兩個工具呼叫）：
        # 由 `rss_feeds.url` 的 unique 判，與檢查擋下的是同一個拒絕；別的約束照原樣丟。
        await session.rollback()
        if await session.scalar(select(RssFeed.id).where(RssFeed.url == url)) is None:
            raise
        raise RssRejectedError(RssRefusal.FEED_DUPLICATE, url) from exc
    await poll_feed(session, factory, feed.id, user_id=user_id, now=moment)
    if chosen:
        await session.execute(
            update(RssSeries)
            .where(
                RssSeries.media_id == media_id,
                RssSeries.id.in_(select(RssItem.series_id).where(RssItem.feed_id == feed.id)),
            )
            .values(confirmed=True)
        )
        await session.commit()
    return await _feed_view_of(session, feed.id)


@dataclass(frozen=True, slots=True)
class SearchSubgroup:
    """一次關鍵字搜尋裡的一個字幕組（M5 票 26）：確認卡讓人挑的那一個選項。"""

    #: 發佈名裡的寫法（最新那一筆的），訂閱照它比對（`parser.binding.of_group`）。
    name: str
    releases: int
    #: 最新一筆的發佈日；站上沒報是 `None`。
    updated: date | None
    latest: str
    #: 這一組的每一筆發佈名，新的在前：訂閱它、按下確認就送出的第一批。
    titles: tuple[str, ...]


# 確認卡的預覽（M5 票 26）：只讀一次搜尋 feed，不寫任何東西；不是給人或 AI 按的命令。
@command(Effect.READ, flags={Flag.INTERNAL})
async def search_subgroups(
    factory: ServiceClientFactory, *, kind: FeedKind, term: str
) -> tuple[SearchSubgroup, ...]:
    """這一次 Nyaa / acg.rip 搜尋裡的字幕組，筆數多的在前（同數照最近更新）。讀不出組名的發佈不算
    任何一組。讀不到是 `feed_unreachable`：人在場，卡片列不出第一批就不出卡。"""
    fetcher = factory.rss()
    try:
        try:
            found = parse_items(kind, await fetcher.fetch(_search_url(kind, term)))
        except ServiceError as exc:
            raise unread(exc) from exc
    finally:
        await fetcher.aclose()
    groups: dict[str, list[FeedItem]] = {}
    for item in found:
        group = parse_release(item.title).group
        if group:
            groups.setdefault(normalize_title(group), []).append(item)
    views = []
    for items in groups.values():
        newest = sorted(items, key=_published, reverse=True)
        latest = newest[0]
        views.append(
            SearchSubgroup(
                name=parse_release(latest.title).group,
                releases=len(newest),
                updated=latest.published_at.date() if latest.published_at else None,
                latest=latest.title,
                titles=tuple(item.title for item in newest),
            )
        )
    return tuple(
        sorted(views, key=lambda view: (view.releases, view.updated or date.min), reverse=True)
    )


def _published(item: FeedItem) -> datetime:
    return item.published_at or datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SubscriptionRef:
    """一部作品現有的一條訂閱（M5 票 26：訂閱之前說出來，由人決定留不留）。"""

    feed_id: int
    #: Feed 的名字。網址不給：聚合 feed 的網址帶 token。
    name: str
    kind: FeedKind
    #: 這條訂閱收的字幕組；空字串是搜到的每一組都收（票 26 之前的關鍵字 Feed、Media 頁建的）。
    subgroup: str


@command(
    Effect.READ,
    about=(
        "List the RSS subscriptions a work already has: each feed's id, name, site and the "
        "subgroup it takes (empty means every subgroup the search finds). Check before "
        "subscribing a work again; delete_feed removes one."
    ),
)
async def list_subscriptions(session: AsyncSession, media_id: str) -> tuple[SubscriptionRef, ...]:
    """這部作品現在被哪幾條 Feed 訂著，照 Feed 建立的順序：預先綁定它的關鍵字 Feed，與帶著綁到它的
    RSS Series 的 Feed（Mikan 的單一 feed、聚合 feed）。一條 Feed 帶著好幾個綁到它的 Series 時
    一個字幕組一列。"""
    bound = list(await session.scalars(select(RssSeries).where(RssSeries.media_id == media_id)))
    carried = await session.execute(
        select(RssItem.feed_id, RssItem.series_id)
        .where(RssItem.series_id.in_([row.id for row in bound]))
        .distinct()
    )
    series_of: dict[int, set[int]] = {}
    for feed_id, series_id in carried.tuples():
        if series_id is not None:  # `in_` 已經擋掉 NULL，型別上 `series_id` 仍可為空
            series_of.setdefault(feed_id, set()).add(series_id)
    feeds = await session.scalars(
        select(RssFeed)
        .where(or_(RssFeed.media_id == media_id, RssFeed.id.in_(list(series_of))))
        .order_by(RssFeed.created_at, RssFeed.id)
    )
    by_id = {row.id: row for row in bound}
    found: list[SubscriptionRef] = []
    for feed in feeds:
        names = (
            [feed.subgroup]
            if feed.media_id == media_id
            else sorted({_subgroup_of(by_id[i]) for i in series_of.get(feed.id, set())})
        )
        found.extend(
            SubscriptionRef(feed_id=feed.id, name=feed.name, kind=feed.kind, subgroup=name)
            for name in names
        )
    return tuple(found)


# 加 Feed 的確認卡預覽（M5 票 26）：只讀；不是給人或 AI 按的命令。
@command(Effect.READ, flags={Flag.INTERNAL})
async def subscriptions_of_feed_url(session: AsyncSession, url: str) -> tuple[SubscriptionRef, ...]:
    """要加的網址是某個 Mikan 番組的單一 feed、而那個番組（任一個字幕組）已經綁在作品上時，那幾部
    作品現有的訂閱（`list_subscriptions`）。其他網址看不出是哪一部作品，是空的。"""
    ids = mikan.feed_ids(url) if kind_of(url.strip()) is FeedKind.MIKAN else None
    if ids is None:
        return ()
    works = await session.scalars(
        select(RssSeries.media_id)
        .where(RssSeries.mikan_bangumi_id == ids[0], RssSeries.media_id.is_not(None))
        .distinct()
        .order_by(RssSeries.media_id)
    )
    found: dict[tuple[int, str], SubscriptionRef] = {}
    for media_id in works:
        assert media_id is not None
        for ref in await list_subscriptions(session, media_id):
            found.setdefault((ref.feed_id, ref.subgroup), ref)
    return tuple(found.values())


def _subgroup_of(series: RssSeries) -> str:
    """RSS Series 的字幕組：Mikan 記下的名字，其他來源讀長出它的那一筆發佈名。"""
    return series.mikan_subgroup_name or parse_release(series.title_raw).group


async def _subscribed_routes(
    session: AsyncSession, media_id: str, route_id: int, *, others: bool
) -> KindRoutes:
    """從 Media 頁訂閱建的 Feed 的兩格（M4 票 105）：選的那一條寫在作品那一種的那一欄。`others` 時
    另一種只有一條啟用中的 Route 就填它（同 migration 的「能推就推」），否則留 `None`——Mikan 的單一
    feed 不預先綁定作品，兩種都用得到；搜尋 feed 只用得到作品那一種，另一格一律空著。"""
    # 作品 id 讀得出來才走到這裡：`_target` 已經讀到了那一列 Media。
    parsed = parse_media_id(media_id)
    assert parsed is not None
    kind = parsed[0]
    other = MediaKind.MOVIE if kind is MediaKind.TV else MediaKind.TV
    candidates = await _routes_for(session, other) if others else []
    rest = candidates[0].id if len(candidates) == 1 else None
    if kind is MediaKind.TV:
        return KindRoutes(tv=route_id, movie=rest)
    return KindRoutes(tv=rest, movie=route_id)


def _set_routes(feed: RssFeed, routes: KindRoutes) -> None:
    feed.tv_route_id, feed.movie_route_id = routes.tv, routes.movie


async def _feed_view_of(session: AsyncSession, feed_id: int) -> FeedView:
    row = await session.get(RssFeed, feed_id, populate_existing=True)
    assert row is not None
    awaiting = (await _awaiting_counts(session)).get(feed_id, KindCounts())
    return _feed_view(row, await _items_of(session, feed_id), awaiting)


# --- Feed Item ----------------------------------------------------------


@command(Effect.READ)
async def list_series_items(session: AsyncSession, series_id: int) -> tuple[ItemView, ...]:
    """一個 RSS Series 的每一筆，發佈新的在前（M4 票 13：RSS 頁展開一列看它下了什麼）。不分頁：一季
    12–50 筆。跟著 Feed 刪掉的就不在了。"""
    if await session.get(RssSeries, series_id) is None:
        raise RssRejectedError(RssRefusal.SERIES_MISSING, str(series_id))
    rows = await session.scalars(
        select(RssItem)
        .where(RssItem.series_id == series_id)
        .order_by(RssItem.published_at.desc(), RssItem.seen_at.desc(), RssItem.id.desc())
    )
    return tuple([await _item_view(session, row) for row in rows])


@command(Effect.READ)
async def list_items(session: AsyncSession) -> tuple[ItemView, ...]:
    """最近看到的 `RECENT_ITEMS` 筆，新的在前。"""
    rows = await session.scalars(
        select(RssItem).order_by(RssItem.seen_at.desc(), RssItem.id.desc()).limit(RECENT_ITEMS)
    )
    return tuple([await _item_view(session, row) for row in rows])


async def _item_view(session: AsyncSession, row: RssItem) -> ItemView:
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
        episode=parse_release(row.title).episode,
        release_blocked=blocked.reason if (blocked := await _release_block(session, row)) else None,
    )
