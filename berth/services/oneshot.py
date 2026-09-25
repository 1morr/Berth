"""一次性 RSS 連結（brief §15、plan §6 rss 群組、M3 票 18）。

貼上一條 RSS 網址 → 讀一次、解析每一筆 → 使用者勾幾筆 → 走一般的送單（`POST /jobs`，
`trigger = manual`）。**這裡只讀**：不建 Feed、不長 RSS Series、不寫 Feed Item——那是訂閱，
一次性連結不追之後的集數。所以送單也不在這裡：勾選的那幾筆與搜尋結果表的一列是同一種東西
（一條 torrent 網址加發佈名），走同一支 `add_download`，這裡多開一條送單的路只會讓兩邊的規則分岔。

**排除條件不擋**：它們只作用在自動下載（brief §15「合集不是不能解析，只是不自動下載」）。每一筆
帶著 `release_kind`，畫面標出合集，人照樣勾得了。

**選了作品與 Route 才比帳本**：季集要照那部作品的 TMDB 快照換算，「帳本已有」要比同一個資料夾。
沒選時季集是發佈名寫的那一個（`parse_release`），畫面照樣列得出整季。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ProtocolMismatchError, ServiceError
from berth.adapters.rss import FeedItem
from berth.domain import FeedKind, MappingStrategy, ReleaseKind, RssRefusal, Tags
from berth.models import Job, Media, Route
from berth.parser import parse_release, tags_of
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.rss import RssRejectedError, kind_of, library_copy, parse_items
from berth.services.search import estimate
from berth.services.steps import message


@dataclass(frozen=True, slots=True)
class OneshotItem:
    """一次性連結的一筆：送單要的那幾格，加上解析結果與「已經有了」。"""

    guid: str
    title: str
    #: 單集頁。
    link: str
    #: 送單時交給 `POST /jobs` 的那一條：`.torrent` 網址，站只給 magnet 時是 magnet。
    url: str
    #: 站報的 info hash；不報時空字串（acg.rip，送單時由 `TorrentFetcher` 算）。
    info_hash: str
    size: int | None
    published_at: datetime | None
    release_kind: ReleaseKind
    tags: Tags
    #: 選了作品時是照它換算的預估（搜尋結果表同一支 `search.estimate`），沒選時是發佈名寫的。
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 這個範圍蓋掉那一季 TMDB 已知的每一集。沒選作品時一律 `False`：不知道一季有幾集。
    whole_season: bool
    #: 預估是怎麼算出來的；沒選作品是 `None`。
    strategy: MappingStrategy | None
    #: 同一個 info hash 的 Job 已經在了（手動送過、RSS 送過、刪掉過）。沒有是空字串。
    job_hash: str
    #: 帳本已有同一個版本：它在媒體庫裡的檔名（`rss.library_copy`）。沒選作品與 Route 時是 `None`。
    known: str | None


@dataclass(frozen=True, slots=True)
class OneshotView:
    kind: FeedKind
    #: 照 feed 的順序（新的在前）。
    items: tuple[OneshotItem, ...]


@command(Effect.READ)
async def read_oneshot(
    session: AsyncSession,
    factory: ServiceClientFactory,
    url: str,
    *,
    media_id: str | None = None,
    route_id: int | None = None,
) -> OneshotView:
    """讀一次 `url`，每一筆說出它是什麼、已經有了沒有。

    失敗各有各的理由（票 18 驗收：說得出是哪一種）：網址不是認得的來源 `feed_unsupported`、
    抓不到 `feed_unreachable`、抓到的不是 RSS `feed_not_rss`；作品或 Route 不在是 `media_missing` /
    `route_missing`（先檢查，不必為一個送不出去的組合打一次上游）。
    """
    kind = kind_of(url)
    if kind is None:
        raise RssRejectedError(RssRefusal.FEED_UNSUPPORTED, url)
    media = await _media(session, media_id)
    route = await _route(session, route_id)
    fetcher = factory.rss()
    try:
        found = parse_items(kind, await fetcher.fetch(url.strip()))
    except ProtocolMismatchError as exc:
        raise RssRejectedError(RssRefusal.FEED_NOT_RSS, message(exc)) from exc
    except ServiceError as exc:
        raise RssRejectedError(RssRefusal.FEED_UNREACHABLE, message(exc)) from exc
    finally:
        await fetcher.aclose()
    hashes = [item.info_hash for item in found if item.info_hash]
    jobs = set(await session.scalars(select(Job.hash).where(Job.hash.in_(hashes))))
    items = [await _item(session, item, media, route, jobs) for item in found]
    return OneshotView(kind=kind, items=tuple(items))


async def _media(session: AsyncSession, media_id: str | None) -> Media | None:
    if media_id is None:
        return None
    media = await session.get(Media, media_id)
    if media is None:
        raise RssRejectedError(RssRefusal.MEDIA_MISSING, media_id)
    return media


async def _route(session: AsyncSession, route_id: int | None) -> Route | None:
    if route_id is None:
        return None
    route = await session.get(Route, route_id)
    if route is None:
        raise RssRejectedError(RssRefusal.ROUTE_MISSING, str(route_id))
    return route


async def _item(
    session: AsyncSession,
    item: FeedItem,
    media: Media | None,
    route: Route | None,
    jobs: set[str],
) -> OneshotItem:
    info = parse_release(item.title)
    snapshot = media.stored_snapshot() if media is not None else None
    if snapshot is not None:
        guess = estimate(item.title, item.published_at, snapshot)
        season, start, end = guess.season, guess.episode_start, guess.episode_end
        whole, strategy = guess.whole_season, guess.strategy
    else:
        # 發佈名寫的那一個：單集的 `episode_end` 補成起始集，與搜尋結果表同一個規矩。
        season, start = info.season, info.episode
        end = info.episode_end or start
        whole, strategy = False, None
    known = None
    if media is not None and route is not None:
        known = await library_copy(
            session, item.title, item.published_at, media=media, route=route, series=None
        )
    return OneshotItem(
        guid=item.guid,
        title=item.title,
        link=item.link,
        url=item.torrent_url or item.magnet,
        info_hash=item.info_hash,
        size=item.size,
        published_at=item.published_at,
        release_kind=info.release_kind,
        tags=tags_of(info),
        season=season,
        episode_start=start,
        episode_end=end,
        whole_season=whole,
        strategy=strategy,
        job_hash=item.info_hash if item.info_hash in jobs else "",
        known=known,
    )
