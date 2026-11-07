"""Mikan 的番組：從 Media 頁訂閱之前的兩個查詢，與以作品訂閱時伺服器自己找番組
（brief §15、M3 票 19、M5.6 票 08）。

Berth 代搜而不是讓人貼網址（2026-09-26 使用者拍板）：Mikan 的搜尋頁用英文、羅馬字、日文、繁中都
搜得到（brief §20.12），所以搜尋框預填這部作品的標題就夠。兩支 `search_bangumi` / `read_bangumi`
只讀，畫面用；選好之後的訂閱是 `rss.subscribe_mikan`。`match_bangumi` 是給 `rss.subscribe` 的那一條
（模型只給作品）：用作品的名字搜、用開播日挑（`parser.bangumi`）。讀不到 Mikan 與 RSS 同一個理由
（`feed_unreachable`）。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.rss import FeedFetcher, mikan
from berth.domain import MediaSnapshot, RssRefusal
from berth.models import Media, RssSeries
from berth.parser import bangumi
from berth.parser.bangumi import BangumiCandidate
from berth.parser.title import normalize_title
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, Flag, command
from berth.services.rss import RssRejectedError, unread

#: `rss.subscribe` 一次最多搜幾個名字：每個詞要真的打一次 Mikan 的搜尋頁（約 1.5 秒）。
MAX_SEARCH_TERMS = 4


@dataclass(frozen=True, slots=True)
class SubgroupView:
    id: int
    name: str
    updated: date | None
    releases: int
    latest: str
    #: 這一組的 RSS Series 已經綁在哪一部作品上；沒綁（或還沒長出來）是 `None`。
    bound_to: str | None
    #: 番組 × 這一組的單一 feed（M4 票 112）：「只下載現有的」拿它走一次性連結。
    feed_url: str


@dataclass(frozen=True, slots=True)
class BangumiView:
    id: int
    title: str
    subgroups: tuple[SubgroupView, ...]


def subgroup_named(view: BangumiView, wanted: str) -> SubgroupView | None:
    """番組頁上名字相等的那一組（`normalize_title`）：卡片的預選與 `rss.subscribe` 共用。"""
    key = normalize_title(wanted)
    return next((group for group in view.subgroups if normalize_title(group.name) == key), None)


# 讀不到 Mikan 是 `feed_unreachable`（`rss.unread`）。
@command(
    Effect.READ,
    about=(
        "Search Mikan (mikanani.me) for a bangumi by title; English, romaji, Japanese and "
        "Chinese titles all work. Gives each bangumi's id for read_bangumi."
    ),
    refusals=(RssRefusal,),
)
async def search_bangumi(factory: ServiceClientFactory, term: str) -> tuple[mikan.BangumiHit, ...]:
    """Mikan 搜尋頁上的番組，照頁上的順序。"""
    page = await _fetch(factory, mikan.search_url(term.strip()))
    return mikan.search_page(page)


@command(
    Effect.READ,
    about=(
        "Read one Mikan bangumi (bangumi_id from search_bangumi): its Chinese title and the "
        "subgroups releasing it, with their ids, latest release and whether a work is already "
        "subscribed to that subgroup (bound_to)."
    ),
    refusals=(RssRefusal,),
)
async def read_bangumi(
    session: AsyncSession, factory: ServiceClientFactory, bangumi_id: int
) -> BangumiView:
    """一個番組的中文名與字幕組，每一組說出它是不是已經綁在某部作品上。"""
    page = await _fetch(factory, mikan.bangumi_url(bangumi_id))
    return await _view(session, bangumi_id, page)


# 只讀：找出這部作品在 Mikan 上是哪一個番組，`rss.subscribe` 與確認卡的預覽自己叫它。
@command(Effect.READ, flags={Flag.INTERNAL})
async def match_bangumi(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str
) -> BangumiView:
    """作品 → 它在 Mikan 上的番組（M5.6 票 08）：用作品的名字搜、用開播日挑（`parser.bangumi`）。

    每個名字真的打一次 Mikan 的搜尋頁（最多 `MAX_SEARCH_TERMS` 個），只用標題對得上的番組去讀
    番組頁——`same_work` 先篩，同名的番組不必每次都多抓一頁。一次搜尋讀不到就跳過它，全部讀不到
    才是 `feed_unreachable`；搜得到而挑不出來是 `bangumi_not_found`，番組頁沒有字幕組是
    `bangumi_without_subgroups`。
    """
    media = await session.get(Media, media_id)
    if media is None:
        raise RssRejectedError(RssRefusal.MEDIA_MISSING, media_id)
    snapshot = media.snapshot()
    fetcher = factory.rss()
    try:
        search = await _search(fetcher, snapshot)
        if not search.answered and search.failure is not None:
            raise search.failure
        candidates: list[BangumiCandidate] = []
        pages: dict[int, str] = {}
        for bangumi_id, title in search.found.items():
            try:
                page = await _page(fetcher, mikan.bangumi_url(bangumi_id))
            except RssRejectedError as exc:
                search = replace(search, failure=search.failure or exc)
                continue
            about = mikan.bangumi_page(page)
            pages[bangumi_id] = page
            candidates.append(
                BangumiCandidate(id=bangumi_id, title=about.title or title, premiere=about.premiere)
            )
    finally:
        await fetcher.aclose()
    chosen = bangumi.choose(snapshot, candidates)
    if chosen is None:
        # 找到番組、番組頁卻一頁都讀不到時說的是讀不到，不是「Mikan 上沒有」：模型會照理由換做法。
        if search.found and search.failure is not None and not candidates:
            raise search.failure
        raise RssRejectedError(RssRefusal.BANGUMI_NOT_FOUND, snapshot.title)
    page = pages[chosen.id]
    about = mikan.bangumi_page(page)
    if not mikan.subgroups(page):
        raise RssRejectedError(RssRefusal.BANGUMI_WITHOUT_SUBGROUPS, about.title or chosen.title)
    return await _view(session, chosen.id, page, about)


@dataclass(frozen=True, slots=True)
class _Search:
    """每一個名字搜過一輪之後的結果：搜到什麼、有沒有讀不到、有幾次有回應。"""

    #: 標題對得上的番組 id → 搜尋頁上的名字。
    found: dict[int, str]
    #: 第一次讀不到的那一次（其餘照跑）。
    failure: RssRejectedError | None
    #: 有回應的幾次搜尋（回空頁也算）。
    answered: int


async def _search(fetcher: FeedFetcher, snapshot: MediaSnapshot) -> _Search:
    """作品的名字 → 標題對得上的番組。讀不到一次不擋其餘的：站上偶爾一次逾時不該讓整張卡出不來。"""
    found: dict[int, str] = {}
    failure: RssRejectedError | None = None
    answered = 0
    for term in bangumi.names(snapshot)[:MAX_SEARCH_TERMS]:
        try:
            page = await _page(fetcher, mikan.search_url(term))
        except RssRejectedError as exc:
            failure = failure or exc
            continue
        answered += 1
        for hit in mikan.search_page(page):
            if bangumi.same_work(snapshot, hit.title):
                found.setdefault(hit.id, hit.title)
    return _Search(found=found, failure=failure, answered=answered)


async def _view(
    session: AsyncSession,
    bangumi_id: int,
    page: str,
    about: mikan.MikanBangumi | None = None,
) -> BangumiView:
    """番組頁 → 畫面要的那一份。`about` 是呼叫端解析過的那一份（`match_bangumi` 用它挑番組）。"""
    shown = about or mikan.bangumi_page(page)
    rows = await session.execute(
        select(RssSeries.mikan_subgroup_id, RssSeries.media_id).where(
            RssSeries.mikan_bangumi_id == bangumi_id, RssSeries.media_id.is_not(None)
        )
    )
    bound: dict[int | None, str | None] = dict(rows.tuples().all())
    return BangumiView(
        id=bangumi_id,
        title=shown.title,
        subgroups=tuple(
            SubgroupView(
                id=group.id,
                name=group.name,
                updated=group.updated,
                releases=group.releases,
                latest=group.latest,
                bound_to=bound.get(group.id),
                feed_url=mikan.bangumi_feed_url(bangumi_id, group.id),
            )
            for group in mikan.subgroups(page)
        ),
    )


async def _fetch(factory: ServiceClientFactory, url: str) -> str:
    fetcher = factory.rss()
    try:
        return await _page(fetcher, url)
    finally:
        await fetcher.aclose()


async def _page(fetcher: FeedFetcher, url: str) -> str:
    """一頁 HTML；讀不到是 `feed_unreachable`（`rss.unread`）。"""
    try:
        return (await fetcher.fetch(url)).decode("utf-8", errors="replace")
    except ServiceError as exc:
        raise unread(exc) from exc
