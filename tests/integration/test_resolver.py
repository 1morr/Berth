"""`jellyfin_resolver`：入庫的檔案在 Jellyfin 裡是哪一個 item（plan §3.2、brief §20.1、票 12）。

起點是 importer 真的跑完的那一份帳本（`test_importer.importing`），替身 Jellyfin 擺出「它掃到了
什麼」。三組斷言：**什麼時候問**（排程）、**怎麼對上**（兩段查詢與路徑）、**對上之後記下什麼**
（item id、Series id、Jellyfin 算的版本名與時間線）。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinItem, JellyfinSource
from berth.adapters.jellyfin.fake import LIBRARY_SCAN_TASK
from berth.db import create_session_factory
from berth.domain import IssueType, PlanAction
from berth.models import LedgerEntry, Route
from berth.pipeline import JellyfinResolver
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.resolve_schedule import RESOLVE_DELAYS
from berth.services.resolver import ResolveOutcome, locate, sweep_resolutions
from tests.integration.factories import FakeClientFactory
from tests.integration.test_importer import importing, ledger_of
from tests.integration.test_plan import NOW, events_of

pytestmark = pytest.mark.asyncio

FIRST = RESOLVE_DELAYS[0]


async def imported(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Route, FakeClientFactory]:
    _, route, factory = await importing(session, roots)
    await sweep_imports(session, factory, EventHub(), now=NOW)
    return route, factory


async def features(session: AsyncSession) -> list[LedgerEntry]:
    return [entry for entry in await ledger_of(session) if entry.action is PlanAction.IMPORT]


async def scanned(session: AsyncSession, route: Route, factory: FakeClientFactory) -> None:
    """Jellyfin 掃完之後的樣子：作品資料夾是一個 Series，每一個正片檔案一個 Episode。

    資料夾名從帳本讀，不在這裡再寫一次命名模板——那份模板屬於 `naming`。
    """
    episodes = await features(session)
    root = PurePosixPath(route.target_path)
    folder = root / PurePosixPath(episodes[0].target_path).relative_to(root).parts[0]
    factory.jellyfin_.items_ = [
        JellyfinItem(
            id="series-1",
            type="Series",
            name="SPY x FAMILY",
            path=str(folder),
            tmdb_id="120089",
        ),
        *(
            JellyfinItem(
                id=f"episode-{entry.episode_start}",
                type="Episode",
                name=f"Episode {entry.episode_start}",
                path=entry.target_path,
                tmdb_id="",
                # 單一版本時 Jellyfin 回的 `MediaSources[].Name` 就是整個檔名主幹
                # （2026-09-15 對 12.0.0 / 12.1.0 實測，brief §20.9）。
                sources=(
                    JellyfinSource(
                        path=entry.target_path, name=PurePosixPath(entry.target_path).stem
                    ),
                ),
                series_id="series-1",
                # Jellyfin 從檔名的 `SxxEyy` 讀出來的，與帳本一致（回驗不開 Issue，票 17）。
                season=entry.season,
                episode_start=entry.episode_start,
                episode_end=entry.episode_end,
            )
            for entry in episodes
        ),
    ]


async def resolve(
    session: AsyncSession, factory: FakeClientFactory, after: timedelta
) -> ResolveOutcome:
    return await sweep_resolutions(session, factory, now=NOW + after)


class TestSchedule:
    async def test_nothing_is_asked_before_the_first_delay(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """剛通知完 Jellyfin 的那一刻它多半還沒掃，問了也是白問。"""
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)

        outcome = await resolve(session, factory, FIRST - timedelta(seconds=1))

        assert outcome.resolved == 0
        assert factory.jellyfin_.item_queries == []

    async def test_it_retries_on_the_schedule_and_gives_up_after_six_tries(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """30 秒 → 2 分 → 10 分 → 1 小時 ×3，共 6 次（plan §3.2）。"""
        _, factory = await imported(session, roots)
        waits: list[timedelta] = []
        at = FIRST
        for _attempt in RESOLVE_DELAYS:
            await resolve(session, factory, at)
            entry = (await features(session))[0]
            if entry.resolve_after is None:
                break
            waits.append(entry.resolve_after - (NOW + at))
            at = entry.resolve_after - NOW

        assert waits == list(RESOLVE_DELAYS[1:])
        assert entry.resolve_attempts == len(RESOLVE_DELAYS)
        assert entry.jellyfin_item_id == ""

    async def test_giving_up_is_one_issue_on_the_timeline(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`issues` 表在 M2，M1 的載體是一筆 `issue_detected`（票上的範圍）。"""
        _, factory = await imported(session, roots)
        at = FIRST
        for _attempt in RESOLVE_DELAYS:
            await resolve(session, factory, at)
            upcoming = (await features(session))[0].resolve_after
            if upcoming is None:
                break
            at = upcoming - NOW

        issues = [row for row in await events_of(session) if row.type == "issue_detected"]
        assert len(issues) == 1
        payload = issues[0].payload_json or {}
        assert payload["type"] == IssueType.JELLYFIN_ITEM_UNRESOLVED.value
        assert payload["count"] == 3

    async def test_what_is_still_missing_is_announced_to_jellyfin_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """入庫當下那一次通知可能沒送到，或 Berth 在狀態落地與通知之間被關掉（plan §3.3）。"""
        _, factory = await imported(session, roots)
        factory.jellyfin_.notified.clear()

        await resolve(session, factory, FIRST)

        assert sorted(factory.jellyfin_.notified) == sorted(
            entry.target_path for entry in await features(session)
        )

    async def test_what_was_found_is_not_announced_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)
        factory.jellyfin_.notified.clear()

        await resolve(session, factory, FIRST)

        assert factory.jellyfin_.notified == []

    async def test_a_second_miss_asks_jellyfin_to_scan_its_libraries(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """從來沒掃到過內容的媒體庫，路徑通知靜靜地什麼都不做（brief §20.1、12.0.0 實測）。

        第一次沒找到多半只是通知的延遲還沒過，所以不掃；第二次還沒有，才請 Jellyfin 掃描——
        一輪一次，不是一個檔案一次。
        """
        _, factory = await imported(session, roots)
        factory.jellyfin_.tasks_ = [LIBRARY_SCAN_TASK]

        await resolve(session, factory, FIRST)
        assert factory.jellyfin_.tasks_run == []

        second = (await features(session))[0].resolve_after
        assert second is not None
        await resolve(session, factory, second - NOW)

        assert factory.jellyfin_.tasks_run == [LIBRARY_SCAN_TASK.id]

    async def test_after_asking_for_a_scan_it_looks_again_within_ten_minutes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """已經開口請它掃了，就不必照原本的間隔等到一小時。"""
        _, factory = await imported(session, roots)
        factory.jellyfin_.tasks_ = [LIBRARY_SCAN_TASK]
        waits: list[timedelta] = []
        at = FIRST
        for _attempt in RESOLVE_DELAYS[:-1]:
            await resolve(session, factory, at)
            upcoming = (await features(session))[0].resolve_after
            assert upcoming is not None
            waits.append(upcoming - (NOW + at))
            at = upcoming - NOW

        assert waits == [RESOLVE_DELAYS[1], *[timedelta(minutes=10)] * 4]

    async def test_a_jellyfin_without_the_scan_task_keeps_the_schedule(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await imported(session, roots)
        await resolve(session, factory, FIRST)
        second = (await features(session))[0].resolve_after
        assert second is not None

        outcome = await resolve(session, factory, second - NOW)

        assert outcome.retried == 3
        assert factory.jellyfin_.tasks_run == []

    async def test_jellyfin_being_down_counts_as_one_try(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await imported(session, roots)
        factory.jellyfin_.error = ServiceUnavailableError("GET /Items: connection refused")

        outcome = await resolve(session, factory, FIRST)

        assert outcome.retried == 3
        assert all(entry.resolve_attempts == 1 for entry in await features(session))


class TestMatching:
    async def test_every_feature_is_found_by_its_exact_path(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)

        outcome = await resolve(session, factory, FIRST)

        assert outcome.resolved == 3
        for entry in await features(session):
            assert entry.jellyfin_item_id == f"episode-{entry.episode_start}"
            assert entry.resolve_after is None
        resolved = [row for row in await events_of(session) if row.type == "jellyfin_item_resolved"]
        assert [(row.payload_json or {})["count"] for row in resolved] == [3]

    async def test_an_episode_remembers_the_series_it_belongs_to(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """媒體庫的卡片連到作品，不是某一集（票 13）：Episode 自己帶 `SeriesId`（12.0.0 實測）。"""
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)

        await resolve(session, factory, FIRST)

        assert {entry.jellyfin_series_id for entry in await features(session)} == {"series-1"}

    async def test_subtitles_and_extras_are_never_looked_up(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)

        await resolve(session, factory, FIRST)

        others = [row for row in await ledger_of(session) if row.action is not PlanAction.IMPORT]
        assert others
        assert all(row.jellyfin_item_id == "" and row.resolve_attempts == 0 for row in others)

    async def test_both_queries_hang_off_the_library_not_the_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`parentId=<seriesId>` 在 10.11 第一次掃描後回 0（brief §20.1）。"""
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)

        await resolve(session, factory, FIRST)

        assert factory.jellyfin_.item_queries == [
            (route.jellyfin_library_id, ("Series",)),
            (route.jellyfin_library_id, ("Episode",)),
        ]

    async def test_a_folder_jellyfin_has_not_scanned_yet_does_not_ask_for_episodes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await imported(session, roots)

        outcome = await resolve(session, factory, FIRST)

        assert outcome.retried == 3
        assert factory.jellyfin_.item_queries == [(route.jellyfin_library_id, ("Series",))]

    async def test_a_second_version_is_found_among_the_media_sources(self) -> None:
        """多版本合併之後，第二個版本的檔案只是那個 item 底下的一個來源（brief §7.7）。"""
        folder = "/data/library/movies/Your Name. (2016) [tmdbid-372058]"
        merged = JellyfinItem(
            id="movie-1",
            type="Movie",
            name="Your Name.",
            path=f"{folder}/Your Name. (2016) [tmdbid-372058] - 1080p.mkv",
            tmdb_id="372058",
            sources=(
                JellyfinSource(
                    path=f"{folder}/Your Name. (2016) [tmdbid-372058] - 1080p.mkv", name="1080p"
                ),
                JellyfinSource(
                    path=f"{folder}/Your Name. (2016) [tmdbid-372058] - 2160p.mkv", name="2160p"
                ),
            ),
        )

        assert locate(f"{folder}/Your Name. (2016) [tmdbid-372058] - 2160p.mkv", [merged]) == (
            merged
        )
        # 版本名是 Jellyfin 算的，逐條路徑對回去（brief §7.7）。
        assert merged.version_name(f"{folder}/Your Name. (2016) [tmdbid-372058] - 2160p.mkv") == (
            "2160p"
        )
        assert merged.version_name("/somewhere/else.mkv") == ""

    async def test_a_path_that_only_shares_a_prefix_is_not_a_match(self) -> None:
        episode = JellyfinItem(
            id="e1",
            type="Episode",
            name="E1",
            path="/data/library/tv/Show/Season 01/Show S01E01.mkv",
            tmdb_id="",
        )

        assert locate("/data/library/tv/Show/Season 01/Show S01E01", [episode]) is None


class TestVersionNames:
    """版本選單上的名字由 Jellyfin 算，Berth 讀它（brief §7.7、§20.9、票 14b）。"""

    async def test_the_name_jellyfin_computed_is_written_to_the_ledger(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """自己重算就要追著 10.x / 12.0 / 12.1 三種算法跑，所以反查到的那一刻抄下來。"""
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)

        await resolve(session, factory, FIRST)

        entries = await features(session)
        assert [entry.jellyfin_version_name for entry in entries] == [
            PurePosixPath(entry.target_path).stem for entry in entries
        ]

    async def test_a_file_jellyfin_has_not_indexed_has_no_name(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """還沒收錄的沒有版本名：畫面照實說，不自己補一個。"""
        _, factory = await imported(session, roots)

        await resolve(session, factory, FIRST)

        assert {entry.jellyfin_version_name for entry in await features(session)} == {""}


class TestRunner:
    async def test_it_does_nothing_until_the_wizard_is_done(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        _, factory = await imported(session, roots)

        assert await JellyfinResolver(create_session_factory(engine), factory).tick() is None
