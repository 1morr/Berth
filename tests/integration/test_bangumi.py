"""從 Media 頁訂閱 Mikan 之前：搜番組、列字幕組（M3 票 19）。

Berth 代搜（2026-09-26 使用者拍板）：Mikan 的搜尋頁用英文、羅馬字、日文、繁中都搜得到
（brief §20.12），番組頁左欄列出每個字幕組的 id、名稱與最近更新。輸入是錄下來的原文。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss.mikan import BangumiHit, bangumi_url, search_url
from berth.domain import RssRefusal
from berth.services.bangumi import read_bangumi, search_bangumi
from berth.services.rss import RssRejectedError, bind_series
from tests.conftest import FIXTURES
from tests.integration.test_rss import NOW
from tests.integration.test_rss_backfill import subscribed

pytestmark = pytest.mark.asyncio

MIKAN = FIXTURES / "http" / "mikan"


async def test_a_search_lists_the_bangumi_mikan_finds(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    _, _, factory, _, _ = await subscribed(session, roots)
    factory.rss_.pages[search_url("Frieren")] = (MIKAN / "home-search.frieren.html").read_bytes()

    assert await search_bangumi(factory, " Frieren ") == (
        BangumiHit(id=3141, title="葬送的芙莉莲"),
        BangumiHit(id=3821, title="葬送的芙莉莲 第二季"),
    )


async def test_an_unreachable_mikan_is_a_refusal(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    _, _, factory, _, _ = await subscribed(session, roots)

    with pytest.raises(RssRejectedError) as refused:
        await search_bangumi(factory, "Frieren")

    assert refused.value.reason is RssRefusal.FEED_UNREACHABLE


async def test_a_bangumi_lists_its_subgroups_and_which_are_bound(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """已經綁好的那一組說出綁在哪一部：畫面不讓人再訂一次（`series_bound`）。"""
    media, route, factory, _, series_id = await subscribed(session, roots)
    await bind_series(
        session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
    )
    factory.rss_.pages[bangumi_url(4009)] = (MIKAN / "home-bangumi.4009.html").read_bytes()

    found = await read_bangumi(session, factory, 4009)

    assert (found.id, found.title, found.premiere) == (4009, "与你相恋到生命尽头", date(2026, 7, 7))
    groups = {group.id: group for group in found.subgroups}
    assert len(groups) == 11
    assert groups[370].bound_to == media.id
    assert groups[370].releases == 12
    assert groups[583].bound_to is None
