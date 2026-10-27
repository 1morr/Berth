"""從 Media 頁訂閱 Mikan 之前的兩個查詢：搜番組、列字幕組（brief §15、M3 票 19）。

Berth 代搜而不是讓人貼網址（2026-09-26 使用者拍板）：Mikan 的搜尋頁用英文、羅馬字、日文、繁中都
搜得到（brief §20.12），所以搜尋框預填這部作品的標題就夠。兩支都只讀；選好之後的訂閱是
`rss.subscribe_mikan`。讀不到 Mikan 與 RSS 同一個理由（`feed_unreachable`）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.rss import mikan
from berth.domain import RssRefusal
from berth.models import RssSeries
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.rss import unread


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
    about = mikan.bangumi_page(page)
    rows = await session.execute(
        select(RssSeries.mikan_subgroup_id, RssSeries.media_id).where(
            RssSeries.mikan_bangumi_id == bangumi_id, RssSeries.media_id.is_not(None)
        )
    )
    bound: dict[int | None, str | None] = dict(rows.tuples().all())
    return BangumiView(
        id=bangumi_id,
        title=about.title,
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
        return (await fetcher.fetch(url)).decode("utf-8", errors="replace")
    except ServiceError as exc:
        raise unread(exc) from exc
    finally:
        await fetcher.aclose()
