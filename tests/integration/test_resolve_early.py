"""作品頁打開時先問一次 Jellyfin（`resolver.resolve_early`，M4 票 51）。

2026-10-06 審計 S6：入庫約 2 分鐘 Jellyfin 已經有這部，媒體庫頁與觀看區都看得到，作品頁的檔案清單
卻寫「Jellyfin 還在掃描，下一次查詢 9 分鐘後」——第二次沒找到之後退避到 10 分鐘。

起點是 `test_resolver` 那一份真的入庫完的帳本，先照排程問兩次都沒找到（退避中）。每一組斷言都是
雙向的：Jellyfin 列出了就不再說還在掃描，還沒列出（或還在認、或問不到）就照舊，而且**不算一次**。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.domain import EventType, IssueType, JellyfinPresence
from berth.models import LedgerEntry, Route
from berth.services.media import read_media
from berth.services.resolve_schedule import RESOLVE_DELAYS
from berth.services.resolver import resolve_early, sweep_resolutions
from tests.integration.factories import FakeClientFactory
from tests.integration.test_jellyfin_verify import (
    jellyfin_reads,
    season_two,
    still_identifying,
    unidentified_series,
)
from tests.integration.test_media import SPY_ID
from tests.integration.test_plan import NOW, events_of
from tests.integration.test_reconcile import issues_of
from tests.integration.test_resolver import FIRST, features, imported, scanned

pytestmark = pytest.mark.asyncio

#: 第二次沒找到的那一刻：再下一次排在 10 分鐘後（審計看到的「9 分鐘後」）。
SECOND = FIRST + RESOLVE_DELAYS[1]
#: 退避中、作品頁被打開的那一刻。
OPENED = SECOND + RESOLVE_DELAYS[1]


async def backing_off(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Route, FakeClientFactory]:
    """入庫完，resolver 照排程問了兩次都沒找到，下一次在 10 分鐘後。"""
    route, factory = await imported(session, roots)
    await sweep_resolutions(session, factory, now=NOW + FIRST)
    await sweep_resolutions(session, factory, now=NOW + SECOND)
    return route, factory


def schedule(entries: list[LedgerEntry]) -> list[tuple[datetime | None, int]]:
    return [(entry.resolve_after, entry.resolve_attempts) for entry in entries]


async def presences(session: AsyncSession, factory: FakeClientFactory) -> set[JellyfinPresence]:
    """作品頁的「檔案與版本」那幾列說的 Jellyfin 狀態。字幕不查 Jellyfin（`none`），不算。"""
    view = await read_media(session, factory, SPY_ID)
    return {file.presence for file in view.files} - {JellyfinPresence.NONE}


class TestJellyfinAlreadyListsIt:
    async def test_the_page_stops_saying_it_is_still_scanning(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await backing_off(session, roots)
        assert await presences(session, factory) == {JellyfinPresence.SEARCHING}
        await scanned(session, route, factory)

        found = await resolve_early(session, factory, SPY_ID, now=NOW + OPENED)

        entries = await features(session)
        assert found == len(entries)
        assert await presences(session, factory) == {JellyfinPresence.FOUND}
        assert {entry.resolve_after for entry in entries} == {None}
        assert all(entry.jellyfin_item_id for entry in entries)

    async def test_it_is_the_resolver_finding_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """提前的那一次走 resolver 找到的同一條路：「全部找到」寫一次，之後照排程那一輪不再寫。"""
        route, factory = await backing_off(session, roots)
        await scanned(session, route, factory)

        await resolve_early(session, factory, SPY_ID, now=NOW + OPENED)
        later = await sweep_resolutions(session, factory, now=NOW + OPENED + RESOLVE_DELAYS[2])

        resolved = [
            row
            for row in await events_of(session)
            if row.type == EventType.JELLYFIN_ITEM_RESOLVED.value
        ]
        assert len(resolved) == 1
        assert later.resolved == 0

    async def test_it_checks_the_reading_like_the_resolver_does(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """回驗的權威來源仍然是 resolver（票 02）：Jellyfin 認成別的季，提前找到也一樣開那一件。"""
        route, factory = await backing_off(session, roots)
        await scanned(session, route, factory)
        first = (await features(session))[0]
        jellyfin_reads(factory, f"episode-{first.episode_start}", season_two)

        await resolve_early(session, factory, SPY_ID, now=NOW + OPENED)

        mismatches = [
            row for row in await issues_of(session) if row.type is IssueType.JELLYFIN_ITEM_MISMATCH
        ]
        assert [row.ledger_id for row in mismatches] == [first.id]


class TestJellyfinDoesNotListItYet:
    async def test_the_page_still_says_it_is_scanning_and_no_try_is_spent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """打開頁面就會跑：算次數的話，多開幾次就把 6 次用完了。"""
        _, factory = await backing_off(session, roots)
        before = schedule(await features(session))

        found = await resolve_early(session, factory, SPY_ID, now=NOW + OPENED)

        assert found == 0
        assert await presences(session, factory) == {JellyfinPresence.SEARCHING}
        assert schedule(await features(session)) == before

    async def test_a_file_jellyfin_is_still_identifying_keeps_waiting(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """列出了但還沒認完（M4 票 02）不算找到：作品頁照舊，排程不動。"""
        route, factory = await backing_off(session, roots)
        await scanned(session, route, factory)
        first = (await features(session))[0]
        jellyfin_reads(factory, f"episode-{first.episode_start}", still_identifying)
        before = schedule([first])

        found = await resolve_early(session, factory, SPY_ID, now=NOW + OPENED)

        await session.refresh(first)
        assert found == len(await features(session)) - 1
        assert (first.jellyfin_item_id, schedule([first])) == ("", before)

    async def test_an_unidentified_series_keeps_every_episode_waiting(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await backing_off(session, roots)
        await scanned(session, route, factory)
        jellyfin_reads(factory, "series-1", unidentified_series)

        assert await resolve_early(session, factory, SPY_ID, now=NOW + OPENED) == 0
        assert await presences(session, factory) == {JellyfinPresence.SEARCHING}

    async def test_jellyfin_unreachable_changes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await backing_off(session, roots)
        await scanned(session, route, factory)
        factory.jellyfin_.error = ServiceUnavailableError("GET /Items: connection refused")
        before = schedule(await features(session))

        assert await resolve_early(session, factory, SPY_ID, now=NOW + OPENED) == 0
        assert schedule(await features(session)) == before


class TestDueEntriesAreTheLoops:
    async def test_an_entry_already_due_is_left_to_the_scheduled_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """到時間的那幾列 15 秒內排程那一輪就會問；兩邊同時寫同一列，「找到了」會被蓋掉。"""
        route, factory = await backing_off(session, roots)
        await scanned(session, route, factory)
        due = max(entry.resolve_after for entry in await features(session) if entry.resolve_after)

        assert await resolve_early(session, factory, SPY_ID, now=due) == 0
        assert await resolve_early(session, factory, SPY_ID, now=due - timedelta(seconds=1)) > 0


class TestOnlyThisWork:
    async def test_another_work_asks_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await backing_off(session, roots)
        await scanned(session, route, factory)
        asked = len(factory.jellyfin_.item_queries)

        assert await resolve_early(session, factory, "movie:1", now=NOW + OPENED) == 0
        assert len(factory.jellyfin_.item_queries) == asked
        assert {entry.resolve_after for entry in await features(session)} != {None}
