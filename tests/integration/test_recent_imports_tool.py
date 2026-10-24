"""「最近入庫」經命令登錄表呼叫（M5 票 05，票 09 的 tracer 用它）。

從登錄表的介面進去（`REGISTRY.invoke`），斷言回來的結果型別。帳本的入庫列直接寫，造法與週報的
測試同一套（`tests/integration/test_weekly.py`）：兩者讀的是同一段算法。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.domain import JellyfinPresence, MediaKind, PlanAction, Role
from berth.models import LedgerEntry, Media
from berth.services.auth import AuthenticatedUser
from berth.services.registry import NextStep, Refusal, ToolContext
from berth.services.sources import SourceCache
from berth.services.tools import REGISTRY, RecentImports, RecentWork
from tests.integration.factories import FakeClientFactory
from tests.integration.test_weekly import DUNE, END, FRIEREN, imported, works

pytestmark = pytest.mark.asyncio

ADMIN = AuthenticatedUser(id=1, name="skipper", role=Role.ADMIN, jellyfin_user_id="a")
DECKHAND = AuthenticatedUser(id=2, name="deckhand", role=Role.USER, jellyfin_user_id="b")


async def test_the_last_week_of_imports_comes_back_by_work(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    await works(session)
    await poster(session, FRIEREN, "https://image.tmdb.org/t/p/w342/zh.jpg", "")
    for episode in (1, 2, 3, 5):
        entry = await imported(session, FRIEREN, episode, at=END - timedelta(days=2))
        # 第 5 集 Jellyfin 還沒收錄，其餘找到了：整部說「還在等」。
        await seen(session, entry, found=episode != 5)
    await seen(session, await imported(session, DUNE, at=END - timedelta(days=6)), found=True)
    # 八天前的不在「最近七天」；被跳過的（不是入庫）也不算。
    await imported(session, FRIEREN, 9, at=END - timedelta(days=8))
    await imported(session, FRIEREN, 10, at=END - timedelta(days=1), action=PlanAction.SKIP)

    context = ToolContext(
        sessions=create_session_factory(engine),
        clients=FakeClientFactory(),
        sources=SourceCache(),
        user=ADMIN,
        now=END,
    )
    result = await REGISTRY.invoke("recent_imports", {"days": 7}, context)

    assert result == RecentImports(
        since=END - timedelta(days=7),
        until=END,
        works=[
            RecentWork(
                media=DUNE,
                kind=MediaKind.MOVIE,
                title="沙丘：第二部",
                title_en="Dune: Part Two",
                year=2024,
                poster_url="",
                poster_url_en="",
                episodes=[],
                presence=JellyfinPresence.FOUND,
            ),
            RecentWork(
                media=FRIEREN,
                kind=MediaKind.TV,
                title="葬送的芙莉蓮",
                title_en="Frieren: Beyond Journey's End",
                year=2024,
                poster_url="https://image.tmdb.org/t/p/w342/zh.jpg",
                # 舊快照沒有英文那一輪：落回另一輪（同作品頁）。
                poster_url_en="https://image.tmdb.org/t/p/w342/zh.jpg",
                episodes=[(1, 1, 3), (1, 5, 5)],
                presence=JellyfinPresence.SEARCHING,
            ),
        ],
    )


async def test_one_episode_jellyfin_cannot_find_makes_the_work_lost(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """找不到的要人去 Jellyfin 看，比還在等的優先說。"""
    await works(session)
    await seen(session, await imported(session, FRIEREN, 1, at=END - timedelta(days=1)), found=True)
    await imported(session, FRIEREN, 2, at=END - timedelta(days=1))  # 反查用完：找不到
    entry = await imported(session, FRIEREN, 3, at=END - timedelta(days=1))
    await seen(session, entry, found=False)

    context = ToolContext(
        sessions=create_session_factory(engine),
        clients=FakeClientFactory(),
        sources=SourceCache(),
        user=ADMIN,
        now=END,
    )
    result = await REGISTRY.invoke("recent_imports", {}, context)

    assert isinstance(result, RecentImports)
    assert [work.presence for work in result.works] == [JellyfinPresence.LOST]


async def poster(session: AsyncSession, media_id: str, url: str, url_en: str) -> None:
    media = await session.get(Media, media_id)
    assert media is not None
    snapshot = media.snapshot().model_copy(update={"poster_url": url, "poster_url_en": url_en})
    media.tmdb_snapshot_json = snapshot.model_dump(mode="json")
    await session.commit()


async def seen(session: AsyncSession, entry: LedgerEntry, *, found: bool) -> None:
    """Jellyfin 收錄了這一集（`found`），或還排著反查。"""
    if found:
        entry.jellyfin_item_id = f"item-{entry.id}"
    else:
        entry.resolve_after = END
    await session.commit()


async def test_an_ordinary_user_cannot_reach_it(engine: AsyncEngine) -> None:
    """週報頁只有管理員（`/weekly`），這個工具跟著它。"""
    context = ToolContext(
        sessions=create_session_factory(engine),
        clients=FakeClientFactory(),
        sources=SourceCache(),
        user=DECKHAND,
        now=END,
    )

    result = await REGISTRY.invoke("recent_imports", {}, context)

    assert isinstance(result, Refusal)
    assert (result.reason, result.next) == ("unknown_tool", NextStep.GIVE_UP)
