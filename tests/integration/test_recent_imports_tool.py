"""「最近入庫」經命令登錄表呼叫（M5 票 06，票 11 的 tracer 用它）。

從登錄表的介面進去（`REGISTRY.invoke`），斷言回來的結果型別。帳本的入庫列直接寫，造法與週報的
測試同一套（`tests/integration/test_weekly.py`）：兩者讀的是同一段算法。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.domain import MediaKind, PlanAction, Role
from berth.services.auth import AuthenticatedUser
from berth.services.registry import NextStep, Refusal, ToolContext
from berth.services.tools import REGISTRY, RecentImports, RecentWork
from tests.integration.test_weekly import DUNE, END, FRIEREN, imported, works

pytestmark = pytest.mark.asyncio

ADMIN = AuthenticatedUser(id=1, name="skipper", role=Role.ADMIN, jellyfin_user_id="a")
DECKHAND = AuthenticatedUser(id=2, name="deckhand", role=Role.USER, jellyfin_user_id="b")


async def test_the_last_week_of_imports_comes_back_by_work(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    await works(session)
    for episode in (1, 2, 3, 5):
        await imported(session, FRIEREN, episode, at=END - timedelta(days=2))
    await imported(session, DUNE, at=END - timedelta(days=6))
    # 八天前的不在「最近七天」；被跳過的（不是入庫）也不算。
    await imported(session, FRIEREN, 9, at=END - timedelta(days=8))
    await imported(session, FRIEREN, 10, at=END - timedelta(days=1), action=PlanAction.SKIP)

    context = ToolContext(sessions=create_session_factory(engine), user=ADMIN, now=END)
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
                episodes=[],
            ),
            RecentWork(
                media=FRIEREN,
                kind=MediaKind.TV,
                title="葬送的芙莉蓮",
                title_en="Frieren: Beyond Journey's End",
                episodes=[(1, 1, 3), (1, 5, 5)],
            ),
        ],
    )


async def test_an_ordinary_user_cannot_reach_it(engine: AsyncEngine) -> None:
    """週報頁只有管理員（`/weekly`），這個工具跟著它。"""
    context = ToolContext(sessions=create_session_factory(engine), user=DECKHAND, now=END)

    result = await REGISTRY.invoke("recent_imports", {}, context)

    assert isinstance(result, Refusal)
    assert (result.reason, result.next) == ("unknown_tool", NextStep.GIVE_UP)
