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
from berth.domain import BudgetUse
from berth.models import RssSeries
from berth.services.clients import ServiceClientFactory, feed_fetcher
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


@dataclass(frozen=True, slots=True)
class BangumiView:
    id: int
    title: str
    premiere: date | None
    subgroups: tuple[SubgroupView, ...]


@command(Effect.READ)
async def search_bangumi(factory: ServiceClientFactory, term: str) -> tuple[mikan.BangumiHit, ...]:
    """Mikan 搜尋頁上的番組，照頁上的順序。"""
    page = await _fetch(factory, mikan.search_url(term.strip()))
    return mikan.search_page(page)


@command(Effect.READ)
async def read_bangumi(
    session: AsyncSession, factory: ServiceClientFactory, bangumi_id: int
) -> BangumiView:
    """一個番組的中文名、開播日期與字幕組，每一組說出它是不是已經綁在某部作品上。"""
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
        premiere=about.premiere,
        subgroups=tuple(
            SubgroupView(
                id=group.id,
                name=group.name,
                updated=group.updated,
                releases=group.releases,
                latest=group.latest,
                bound_to=bound.get(group.id),
            )
            for group in mikan.subgroups(page)
        ),
    )


async def _fetch(factory: ServiceClientFactory, url: str) -> str:
    fetcher = feed_fetcher(factory, BudgetUse.MANUAL)
    try:
        return (await fetcher.fetch(url)).decode("utf-8", errors="replace")
    except ServiceError as exc:
        raise unread(exc) from exc
    finally:
        await fetcher.aclose()
