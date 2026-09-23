"""`health_checker` 量出來的兩種 Issue（M2 票 09c）：TVDB 插件與磁碟空間門檻。

驗收的四條在這裡：它們是 Issue（不再只是一行字）、門檻在設定裡、**條件解除時系統自己收掉**、
問不到就不判。另外一條是使用者拍板的：忽略在條件持續期間有效。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import TypeOption
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.domain import IssueStatus, IssueType
from berth.models import Issue, PathSettings, Route
from berth.services.health import check_health
from berth.services.health_issues import SYSTEM, set_min_free, watch_conditions
from berth.services.issues import ignore_issue
from berth.services.settings import read_settings, write_settings
from tests.integration.arrange import factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_downloads import NOW, setup_job

pytestmark = pytest.mark.asyncio

LATER = NOW + timedelta(minutes=5)
TVDB = TypeOption(type="Series", metadata_fetchers=("TheMovieDb", "TheTVDB"), image_fetchers=())
TMDB = TypeOption(type="Series", metadata_fetchers=("TheMovieDb",), image_fetchers=())
#: 比任何一顆真的磁碟都大：量到的一定低於它。
HUGE = 10**9


async def a_route(session: AsyncSession, roots: dict[str, Path]) -> tuple[Route, FakeClientFactory]:
    """一條 Route（`Anime`，媒體庫 `item-2`），Jellyfin 那邊的媒體庫還沒掛 TVDB。"""
    await setup_job(session, roots)
    (route,) = await session.scalars(select(Route))
    return route, factory_for(roots)


def fetchers(factory: FakeClientFactory, option: TypeOption) -> None:
    """使用者在 Jellyfin 的媒體庫設定裡改了 metadata fetcher。"""
    jellyfin: FakeJellyfinClient = factory.jellyfin_
    jellyfin.libraries_ = [
        replace(row, type_options=(option,)) if row.item_id == "item-2" else row
        for row in jellyfin.libraries_
    ]


async def rows_of(session: AsyncSession, kind: IssueType) -> list[Issue]:
    found = await session.scalars(select(Issue).where(Issue.type == kind).order_by(Issue.id))
    return list(found)


async def open_of(session: AsyncSession, kind: IssueType) -> list[Issue]:
    return [row for row in await rows_of(session, kind) if row.status is IssueStatus.OPEN]


class TestTvdb:
    async def test_a_route_whose_library_uses_tvdb_is_an_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一條 Route 一件（2026-09-23 使用者拍板），冪等鍵是它的目標路徑。"""
        route, factory = await a_route(session, roots)
        fetchers(factory, TVDB)

        await watch_conditions(session, factory, now=NOW)
        await watch_conditions(session, factory, now=LATER)

        (issue,) = await open_of(session, IssueType.LIBRARY_USES_TVDB)
        assert issue.path == route.target_path
        assert issue.detail_json == {
            "route": "Anime",
            "library": "Anime",
            "fetchers": ["TheTVDB"],
        }

    async def test_taking_it_off_in_jellyfin_closes_the_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await a_route(session, roots)
        fetchers(factory, TVDB)
        await watch_conditions(session, factory, now=NOW)

        fetchers(factory, TMDB)
        await watch_conditions(session, factory, now=LATER)

        (issue,) = await rows_of(session, IssueType.LIBRARY_USES_TVDB)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == SYSTEM

    async def test_a_deleted_route_takes_its_issue_with_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await a_route(session, roots)
        fetchers(factory, TVDB)
        await watch_conditions(session, factory, now=NOW)

        await session.delete(route)
        await session.commit()
        await watch_conditions(session, factory, now=LATER)

        assert await open_of(session, IssueType.LIBRARY_USES_TVDB) == []

    async def test_an_unreachable_jellyfin_is_not_a_fix(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """問不到 Jellyfin 不是「它不掛 TVDB 了」（brief §16.2）。"""
        _, factory = await a_route(session, roots)
        fetchers(factory, TVDB)
        await watch_conditions(session, factory, now=NOW)

        factory.jellyfin_.error = ServiceUnavailableError("connection refused")
        await watch_conditions(session, factory, now=LATER)

        assert len(await open_of(session, IssueType.LIBRARY_USES_TVDB)) == 1


class TestIgnoringIt:
    """忽略在條件持續期間有效（2026-09-23 使用者拍板）：故意掛 TVDB 的人按一次就安靜。"""

    async def test_it_stays_quiet_while_the_condition_holds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await a_route(session, roots)
        fetchers(factory, TVDB)
        await watch_conditions(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.LIBRARY_USES_TVDB)

        await ignore_issue(session, issue.id, actor="7")
        await watch_conditions(session, factory, now=LATER)

        assert await open_of(session, IssueType.LIBRARY_USES_TVDB) == []

    async def test_it_comes_back_once_the_condition_cleared_and_returned(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await a_route(session, roots)
        fetchers(factory, TVDB)
        await watch_conditions(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.LIBRARY_USES_TVDB)
        await ignore_issue(session, issue.id, actor="7")

        fetchers(factory, TMDB)
        await watch_conditions(session, factory, now=LATER)
        fetchers(factory, TVDB)
        await watch_conditions(session, factory, now=LATER + timedelta(minutes=5))

        assert len(await open_of(session, IssueType.LIBRARY_USES_TVDB)) == 1


class TestDiskSpace:
    async def test_below_the_threshold_is_one_issue_per_filesystem(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """incomplete 與 complete 在同一個檔案系統上（測試的暫存目錄）：一件，掛在 complete。"""
        _, factory = await a_route(session, roots)
        await set_min_free(session, HUGE, now=NOW)

        await watch_conditions(session, factory, now=LATER)

        (issue,) = await open_of(session, IssueType.LOW_DISK_SPACE)
        assert issue.path == str(roots["complete"])
        detail = issue.detail_json or {}
        assert detail["min_free"] == HUGE * 1024**3
        assert 0 < detail["free"] < detail["min_free"]

    async def test_lowering_the_threshold_closes_it_right_away(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """門檻在設定裡，改了立刻重量一次——不必等下一輪 5 分鐘。`0` 是不量。"""
        await a_route(session, roots)
        await set_min_free(session, HUGE, now=NOW)

        await set_min_free(session, 0, now=LATER)

        (issue,) = await rows_of(session, IssueType.LOW_DISK_SPACE)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == SYSTEM

    async def test_a_root_it_cannot_see_is_not_a_fix(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """量不到（沒掛上）不是「空間夠了」：那一件留著，`download_path` 纜繩去報掛載。"""
        _, factory = await a_route(session, roots)
        await set_min_free(session, HUGE, now=NOW)
        paths = await read_settings(session, PathSettings)
        (roots["complete"]).rename(roots["complete"].with_name("gone"))

        await watch_conditions(session, factory, now=LATER)

        # incomplete 那一條這時自己量、自己開一件（它不再與一個量得到的 complete 共用檔案系統）。
        assert paths.complete_root in {
            row.path for row in await open_of(session, IssueType.LOW_DISK_SPACE)
        }

    async def test_an_unmounted_incomplete_root_does_not_hide_the_complete_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一個根目錄量不到只跳過那一個，另一個照量照開。"""
        _, factory = await a_route(session, roots)
        paths = await read_settings(session, PathSettings)
        paths.incomplete_root = str(roots["incomplete"] / "not-mounted")
        await write_settings(session, paths)
        await set_min_free(session, HUGE, now=NOW)

        await watch_conditions(session, factory, now=LATER)

        assert [row.path for row in await open_of(session, IssueType.LOW_DISK_SPACE)] == [
            str(roots["complete"])
        ]


class TestTheHealthChecker:
    async def test_every_round_of_checks_measures_both(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收：由 `health_checker` 偵測（使用者 2026-09-23 拍板），不由對帳。"""
        _, factory = await a_route(session, roots)
        fetchers(factory, TVDB)
        await set_min_free(session, HUGE, now=NOW)
        await session.execute(delete(Issue))
        await session.commit()

        await check_health(session, factory, now=LATER)

        assert [row.type for row in await open_of(session, IssueType.LIBRARY_USES_TVDB)] == [
            IssueType.LIBRARY_USES_TVDB
        ]
        assert len(await open_of(session, IssueType.LOW_DISK_SPACE)) == 1
