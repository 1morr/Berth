"""Route 設定頁的 services 命令（plan §6 routes 群組、brief §4.3、票 14）。

精靈第 5 步只新增（`test_setup_routes.py`）；逐條管理在這裡：同一個媒體庫的第二條 Route、
紅燈不給啟用、刪除是明確動作而被引用時拒絕。

與精靈同一個起點（`arrange`）、同一組**真的**檔案系統檢查——一條 Route 綠不綠，問的永遠是
那五條纜繩，而它們在 tmp 目錄底下真的鏈接一次檔案。
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinLibrary
from berth.db import create_session_factory
from berth.domain import CollectionType, HealthStatus, JobTrigger, PlanAction, StepStatus
from berth.models import Job, LedgerEntry, Route, SetupLibrary
from berth.services import routes as routes_service
from berth.services.routes import (
    LibraryPath,
    RouteInUseError,
    RouteRejectedError,
    RouteUsage,
    build_routes,
    check_route,
    check_routes,
    create_route,
    delete_route,
    list_libraries,
    list_routes,
    read_route_status,
    routes_health,
    routes_ready,
    update_route,
)
from tests.integration.arrange import (
    arrange,
    bundled_libraries,
    delete_once_during_checks,
    factory_for,
    fake_jellyfin,
    with_second_disk,
)
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio


class TestCreate:
    async def test_one_library_gets_a_second_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        libraries, disk = with_second_disk(roots)
        await arrange(session, roots, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, ())

        route = await create_route(
            session,
            factory,
            library_id="item-1",
            target_path=str(disk),
            name="TV 2",
        )

        assert (route.slug, route.name, route.library, route.target_path) == (
            "tv-2",
            "TV 2",
            "TV",
            str(disk),
        )
        assert route.category == "berth-tv-2"
        assert (route.health, route.enabled) == (HealthStatus.OK, True)
        assert [row.slug for row in (await read_route_status(session)).routes] == [
            "movies",
            "tv",
            "anime",
            "tv-2",
        ]

    async def test_a_route_that_fails_its_checks_is_kept_but_disabled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """紅燈不給啟用，但這一列留著：修好掛載之後重新檢查再啟用，不必重填（使用者拍板）。"""
        libraries, disk = with_second_disk(roots)
        await arrange(session, roots, libraries=libraries)
        # 這台 Jellyfin 少掛了媒體庫：Berth 寫的探測檔它看不到。
        jellyfin = fake_jellyfin(libraries, visible_roots=("/elsewhere",))

        route = await create_route(
            session,
            factory_for(roots, jellyfin=jellyfin),
            library_id="item-1",
            target_path=str(disk),
            name="TV 2",
        )

        assert (route.health, route.enabled) == (HealthStatus.FAILED, False)
        assert {row.step: row.status for row in route.checks}["probe_visible"] is StepStatus.FAILED

    @pytest.mark.parametrize(
        ("library_id", "target", "reason"),
        [
            ("no-such-library", "tv-disk2", "library_missing"),
            ("music", "music", "library_unsupported"),
            ("item-1", "elsewhere", "target_not_in_library"),
            # 第一條 TV Route 已經寫在這裡了：兩條 Route 同一個目標，帳本就認不出是誰的。
            ("item-1", "tv", "target_taken"),
        ],
    )
    async def test_an_invalid_choice_is_refused_with_a_reason(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        library_id: str,
        target: str,
        reason: str,
    ) -> None:
        libraries, _ = with_second_disk(roots)
        music = SetupLibrary(
            name="Music",
            item_id="music",
            collection_type="music",
            locations=[str(roots["library"] / "music")],
        )
        libraries = (*libraries, music)
        await arrange(session, roots, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, ())

        with pytest.raises(RouteRejectedError) as refusal:
            await create_route(
                session,
                factory,
                library_id=library_id,
                target_path=str(roots["library"] / target),
                name="Another",
            )

        assert refusal.value.reason == reason
        assert len((await read_route_status(session)).routes) == 3

    async def test_an_unreachable_jellyfin_is_a_reason_not_a_crash(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        libraries, disk = with_second_disk(roots)
        await arrange(session, roots, libraries=libraries)
        jellyfin = fake_jellyfin(libraries, error=ServiceUnavailableError("connection refused"))

        with pytest.raises(RouteRejectedError) as refusal:
            await create_route(
                session,
                factory_for(roots, jellyfin=jellyfin),
                library_id="item-1",
                target_path=str(disk),
                name="TV 2",
            )

        assert refusal.value.reason == "jellyfin_unreachable"
        assert "connection refused" in refusal.value.detail


async def red_second_route(session: AsyncSession, roots: dict[str, Path]) -> tuple[int, Path]:
    """TV 的第二條 Route，建立時 Jellyfin 看不到它——所以它被留成停用（`create_route`）。"""
    libraries, disk = with_second_disk(roots)
    await arrange(session, roots, libraries=libraries)
    await build_routes(session, factory_for(roots, libraries=libraries), ())
    blind = fake_jellyfin(libraries, visible_roots=("/elsewhere",))
    route = await create_route(
        session,
        factory_for(roots, jellyfin=blind),
        library_id="item-1",
        target_path=str(disk),
        name="TV 2",
    )
    return route.id, disk


class TestUpdate:
    async def test_name_change(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)

        route = await update_route(
            session,
            factory_for(roots, libraries=libraries),
            route_id,
            name="Second disk",
            enabled=False,
        )

        assert (route.name, route.enabled) == ("Second disk", False)
        # slug 與目標路徑不動：category、complete 子目錄與帳本歸屬都由它們導出（使用者拍板）。
        assert (route.slug, route.category) == ("tv-2", "berth-tv-2")

    async def test_a_route_whose_checks_are_red_is_not_enabled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """紅的不給啟用（票 14 驗收）。啟用那一刻再檢查一次，不相信上一輪的結果；
        同一次送出的名稱照樣存下（使用者拍板）。"""
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)
        blind = fake_jellyfin(libraries, visible_roots=("/elsewhere",))

        with pytest.raises(RouteRejectedError) as refusal:
            await update_route(
                session,
                factory_for(roots, jellyfin=blind),
                route_id,
                name="Second disk",
                enabled=True,
            )

        assert refusal.value.reason == "route_unhealthy"
        route = next(row for row in (await read_route_status(session)).routes if row.id == route_id)
        assert (route.enabled, route.health) == (False, HealthStatus.FAILED)
        assert route.name == "Second disk"

    async def test_a_fixed_route_can_be_enabled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)

        route = await update_route(
            session,
            factory_for(roots, libraries=libraries),
            route_id,
            name="TV 2",
            enabled=True,
        )

        assert (route.enabled, route.health) == (True, HealthStatus.OK)

    async def test_an_enabled_route_that_turns_red_on_save_stays_enabled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """規則擋的是「啟用」這個動作，不是「紅了就停用」：改個名字剛好碰上 Jellyfin 看不到掛載，
        不該把它靜靜關掉——紅的 Route 送單本來就擋（票 09），默默停用是另一種隱式改動（票 14a）。"""
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())
        tv = next(row for row in (await read_route_status(session)).routes if row.slug == "tv")
        blind = fake_jellyfin(bundled_libraries(roots["library"]), visible_roots=("/elsewhere",))

        route = await update_route(
            session,
            factory_for(roots, jellyfin=blind),
            tv.id,
            name="Series",
            enabled=True,
        )

        assert (route.name, route.health, route.enabled) == ("Series", HealthStatus.FAILED, True)

    async def test_disabling_is_always_allowed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """停用是「刪不得」時的出路（票 14），紅著也要停得掉。"""
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)
        blind = fake_jellyfin(libraries, visible_roots=("/elsewhere",))

        route = await update_route(
            session,
            factory_for(roots, jellyfin=blind),
            route_id,
            name="TV 2",
            enabled=False,
        )

        assert (route.health, route.enabled) == (HealthStatus.FAILED, False)

    async def test_an_unknown_route_is_a_reason(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        with pytest.raises(RouteRejectedError) as refusal:
            await update_route(session, factory_for(roots), 999, name="x", enabled=True)

        assert refusal.value.reason == "route_missing"


class TestDelete:
    async def test_a_route_nothing_refers_to_is_deleted(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route_id, _ = await red_second_route(session, roots)

        await delete_route(session, route_id)

        assert [row.slug for row in (await read_route_status(session)).routes] == [
            "movies",
            "tv",
            "anime",
        ]

    async def test_a_route_a_job_points_at_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """被 Job 引用的 Route 不能直接刪（票 14 驗收）：那筆下載入庫時要知道去哪裡。"""
        route_id, _ = await red_second_route(session, roots)
        session.add(
            Job(hash="a" * 40, name="release", trigger=JobTrigger.MANUAL, route_id=route_id)
        )
        await session.commit()

        with pytest.raises(RouteRejectedError) as refusal:
            await delete_route(session, route_id)

        assert refusal.value.reason == "route_in_use"
        assert len((await read_route_status(session)).routes) == 4

    async def test_a_route_with_linked_files_under_it_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """帳本不記 Route，以目標路徑認它（`owning_route`）。Job 可以不在了，檔案還在。"""
        route_id, disk = await red_second_route(session, roots)
        session.add(ledger_entry(f"{disk}/Show (2024)/Season 01/Show - S01E01.mkv"))
        await session.commit()

        with pytest.raises(RouteRejectedError) as refusal:
            await delete_route(session, route_id)

        assert refusal.value.reason == "route_in_use"

    async def test_nested_routes_count_the_same_one_by_one_as_in_the_list(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """刪除只算那一條（前綴粗篩、`owning_route` 精判），清單一次算全部；兩邊的數字要一樣。
        `…/tv/anime` 底下的檔案是更深那一條的，不算 `…/tv` 的（brief §4.3）。"""
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())
        tv = next(row for row in (await read_route_status(session)).routes if row.slug == "tv")
        nested = nested_route(roots)
        session.add(nested)
        await session.commit()
        # importer 以 `PurePosixPath(route.target_path) / 相對路徑` 組目標（`importer.py`），
        # 這裡照著組；巢狀那一條的目標寫法不正規（`//`），組出來的帳本路徑卻是正規的。
        for target in (
            str(PurePosixPath(tv.target_path) / "Show (2024)/Season 01/Show - S01E01.mkv"),
            str(
                PurePosixPath(nested.target_path) / "Frieren (2023)/Season 01/Frieren - S01E01.mkv"
            ),
            str(
                PurePosixPath(nested.target_path) / "Frieren (2023)/Season 01/Frieren - S01E02.mkv"
            ),
            # 字面前綴相同、卻不在它底下：`…/tv-extras` 不是 `…/tv` 的。
            f"{tv.target_path}-extras/Show - S01E01.mkv",
        ):
            session.add(ledger_entry(target))
        await session.commit()
        # 被拒的刪除會 rollback，session 裡的 ORM 物件跟著過期：id 先記下來。
        ids = (tv.id, nested.id)
        listed = {row.route.id: row.usage for row in await list_routes(session)}

        refused = {}
        for route_id in ids:
            with pytest.raises(RouteInUseError) as refusal:
                await delete_route(session, route_id)
            refused[route_id] = refusal.value.usage

        assert refused == {route_id: listed[route_id] for route_id in ids}
        assert [listed[route_id].ledger_entries for route_id in ids] == [1, 2]

    async def test_files_under_another_route_do_not_hold_this_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route_id, _ = await red_second_route(session, roots)
        tv = roots["library"] / "tv"
        session.add(ledger_entry(f"{tv}/Show (2024)/Season 01/Show - S01E01.mkv"))
        await session.commit()

        await delete_route(session, route_id)

        assert len((await read_route_status(session)).routes) == 3

    async def test_an_unknown_route_is_a_reason(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        with pytest.raises(RouteRejectedError) as refusal:
            await delete_route(session, 999)

        assert refusal.value.reason == "route_missing"


class TestRaces:
    """兩條連線同時動同一條 Route（票 14a）。`engine` 開第二個 session，交錯是真的。"""

    async def test_a_job_sent_while_a_delete_counts_waits_then_misses_the_route(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """刪除先算引用數再刪；算完的那一刻另一個請求送了一筆單過來。

        沒有寫鎖時那一筆先落地，刪除接著把它的 `route_id` 設成 NULL——一筆不知道要入庫到哪裡的
        下載。寫鎖讓它等到刪除 commit，然後在外鍵上撞牆（送單那一邊回 `route_missing`）。
        """
        route_id, _ = await red_second_route(session, roots)
        sessions = create_session_factory(engine)
        count = routes_service._usage_of
        sent: list[asyncio.Task[None]] = []
        waiting_while_held: list[bool] = []

        async def send_a_job() -> None:
            async with sessions() as other:
                other.add(
                    Job(hash="a" * 40, name="release", trigger=JobTrigger.MANUAL, route_id=route_id)
                )
                await other.commit()

        async def count_then_race(
            counting: AsyncSession, route: Route, routes: Sequence[Route]
        ) -> RouteUsage:
            usage = await count(counting, route, routes)
            sent.append(asyncio.create_task(send_a_job()))
            await asyncio.sleep(0.5)
            waiting_while_held.append(not sent[0].done())
            return usage

        monkeypatch.setattr(routes_service, "_usage_of", count_then_race)

        await delete_route(session, route_id)

        with pytest.raises(IntegrityError):
            await sent[0]
        assert waiting_while_held == [True]
        orphans = await session.scalar(
            select(func.count()).select_from(Job).where(Job.route_id.is_(None))
        )
        assert orphans == 0

    async def test_two_creates_for_the_same_target_make_one_route(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """兩個分頁同時按「建立並檢查」，選的是同一條路徑。

        沒有寫鎖時兩邊都看到「還沒人佔」、算出同一個 slug，後到的撞上唯一索引變成 500。
        寫鎖讓後到的那一個等先到的 commit、重讀之後說 `target_taken`。
        """
        libraries, disk = with_second_disk(roots)
        await arrange(session, roots, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, ())
        ask_jellyfin_together(factory, monkeypatch)
        sessions = create_session_factory(engine)

        outcomes = await asyncio.gather(
            create_in_own_session(sessions, factory, disk, "TV 2"),
            create_in_own_session(sessions, factory, disk, "TV 3"),
        )

        assert sorted(outcomes) == ["target_taken", "tv-2"]
        targets = [row.target_path for row in (await read_route_status(session)).routes]
        assert targets.count(str(disk)) == 1

    async def test_two_creates_on_different_paths_of_one_library_both_land(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """同一個媒體庫、兩條不同的路徑，兩個分頁同時建立。**這一條證明的是寫鎖本身**：

        沒有鎖時兩邊都算出 `tv-2`，後到的撞上唯一索引，兜底重讀之後目標沒被佔，回 `route_conflict`——
        使用者什麼都沒做錯卻被拒絕。有鎖時後到的那一個重讀之後算出 `tv-3`，兩條都建成。
        """
        libraries, disk = with_second_disk(roots)
        third = roots["library"] / "tv-disk3"
        third.mkdir()
        libraries = tuple(
            row.model_copy(update={"locations": [*row.locations, str(third)]})
            if row.name == "TV"
            else row
            for row in libraries
        )
        await arrange(session, roots, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, ())
        ask_jellyfin_together(factory, monkeypatch)
        sessions = create_session_factory(engine)

        outcomes = await asyncio.gather(
            create_in_own_session(sessions, factory, disk, "TV 2"),
            create_in_own_session(sessions, factory, third, "TV 3"),
        )

        assert sorted(outcomes) == ["tv-2", "tv-3"]

    async def test_a_slug_that_collides_anyway_is_a_conflict_not_a_crash(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """建立點都在鎖內算 slug；還是撞上唯一索引時（鎖外的寫入）回 409 `route_conflict`，
        不是 500。"""
        libraries, disk = with_second_disk(roots)
        await arrange(session, roots, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, ())
        monkeypatch.setattr(routes_service, "_unique_slug", lambda name, taken: "tv")

        with pytest.raises(RouteRejectedError) as refusal:
            await create_route(
                session,
                factory,
                library_id="item-1",
                target_path=str(disk),
                name="TV 2",
            )

        assert refusal.value.reason == "route_conflict"
        assert len((await read_route_status(session)).routes) == 3

    @pytest.mark.parametrize("command", ["update", "check", "check_all"])
    async def test_a_route_deleted_during_its_checks_is_missing_not_a_crash(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
    ) -> None:
        """修改與重新檢查在鎖外打網路；那幾秒裡另一個分頁刪掉了這一條。寫回時 0 列被改到
        （`StaleDataError`），那就是 `route_missing`（404），不是 500。

        `check_all` 是**整組重跑**那一支（`check_routes`，精靈第 5 步與健康迴圈走它）：同一件事
        在那裡曾經裸奔成 500（票 01）。"""
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)
        factory = factory_for(roots, libraries=libraries)
        delete_once_during_checks(factory.qbittorrent_, create_session_factory(engine), route_id)

        with pytest.raises(RouteRejectedError) as refusal:
            if command == "update":
                await update_route(session, factory, route_id, name="TV 2", enabled=True)
            elif command == "check":
                await check_route(session, factory, route_id)
            else:
                await check_routes(session, factory)

        assert refusal.value.reason == "route_missing"


def ask_jellyfin_together(factory: FakeClientFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """頭兩次問 Jellyfin 的呼叫要等彼此都到了才一起回：兩個建立都在鎖外問完，才一起去搶鎖。

    之後的呼叫（五條纜繩裡的 `library_path`）照常，否則只剩一個建立在檢查時會永遠等下去。
    """
    both_asked = asyncio.Barrier(2)
    ask = factory.jellyfin_.libraries
    asked = 0

    async def ask_together() -> tuple[JellyfinLibrary, ...]:
        nonlocal asked
        asked += 1
        if asked <= 2:
            await both_asked.wait()
        return await ask()

    monkeypatch.setattr(factory.jellyfin_, "libraries", ask_together)


async def create_in_own_session(
    sessions: async_sessionmaker[AsyncSession], factory: FakeClientFactory, target: Path, name: str
) -> str:
    """一個分頁的「建立並檢查」：自己的 session、自己的連線。回建出來的 slug，或拒絕的理由。"""
    async with sessions() as own:
        try:
            route = await create_route(
                own,
                factory,
                library_id="item-1",
                target_path=str(target),
                name=name,
            )
        except RouteRejectedError as refusal:
            return refusal.reason
        return route.slug


class TestCheck:
    async def test_a_recheck_turns_a_fixed_route_green_but_leaves_it_disabled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「重新檢查」只是診斷；啟用是另一個動作——管理員可能是故意停用它的。"""
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)

        route = await check_route(session, factory_for(roots, libraries=libraries), route_id)

        assert (route.health, route.enabled) == (HealthStatus.OK, False)

    async def test_an_unknown_route_is_a_reason(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        with pytest.raises(RouteRejectedError) as refusal:
            await check_route(session, factory_for(roots), 999)

        assert refusal.value.reason == "route_missing"


class TestListing:
    async def test_each_route_says_how_much_refers_to_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """設定頁在按下刪除之前就說得出「刪不得、為什麼」（票 14 驗收的「說明原因」）。"""
        route_id, disk = await red_second_route(session, roots)
        session.add(
            Job(hash="a" * 40, name="release", trigger=JobTrigger.MANUAL, route_id=route_id)
        )
        session.add(ledger_entry(f"{disk}/Show (2024)/Season 01/Show - S01E01.mkv"))
        await session.commit()

        rows = await list_routes(session)

        assert [(row.route.slug, row.usage.jobs, row.usage.ledger_entries) for row in rows] == [
            ("movies", 0, 0),
            ("tv", 0, 0),
            ("anime", 0, 0),
            ("tv-2", 1, 1),
        ]

    async def test_libraries_come_from_jellyfin_with_the_paths_already_taken(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """新增 Route 的表單從這裡選：路徑用選的，不用打的（brief §4.1）；已經有 Route 的路徑
        標出來，同一個目標不會有第二條（`target_taken`）。"""
        libraries, disk = with_second_disk(roots)
        await arrange(session, roots, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, ())

        options = await list_libraries(session, factory)

        tv = next(row for row in options if row.name == "TV")
        # 被佔用的路徑帶著佔用它的 Route 名，畫面照著說「已是『TV』」，不必自己反查（票 14a）。
        assert (tv.item_id, tv.paths) == (
            "item-1",
            (
                LibraryPath(path=str(roots["library"] / "tv"), route_name="TV"),
                LibraryPath(path=str(disk), route_name=None),
            ),
        )
        assert tv.supported is True

    async def test_libraries_need_jellyfin_to_answer(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        jellyfin = fake_jellyfin((), error=ServiceUnavailableError("connection refused"))

        with pytest.raises(RouteRejectedError) as refusal:
            await list_libraries(session, factory_for(roots, jellyfin=jellyfin))

        assert refusal.value.reason == "jellyfin_unreachable"


class TestLibraryIdentity:
    async def test_a_library_renamed_in_jellyfin_is_still_its_routes_library(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Route 記的是媒體庫的 `ItemId`（票 09）。一庫多條之後名字認不準：改名不是換了一個
        媒體庫，同名的兩個也是兩個（票 14 code-review）。"""
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())
        renamed = tuple(
            row.model_copy(update={"name": "Series"}) if row.name == "TV" else row
            for row in bundled_libraries(roots["library"])
        )
        tv = next(row for row in (await read_route_status(session)).routes if row.slug == "tv")

        route = await check_route(session, factory_for(roots, libraries=renamed), tv.id)

        assert route.health is HealthStatus.OK


class TestDisabledRoutes:
    async def test_a_disabled_red_route_holds_back_neither_the_wizard_nor_health(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """停用是「被引用、刪不得」時的出路（票 14）。停用的 Route 不是目的地：它紅著不該讓
        精靈的第 5 步退回未完成，也不該讓健康頁永遠是 degraded。"""
        await red_second_route(session, roots)

        assert await routes_ready(session) is True
        assert await routes_health(session) is HealthStatus.OK


def nested_route(roots: dict[str, Path]) -> Route:
    """`…/tv` 底下更深的一條（brief §4.3 允許）。直接寫進表：這裡問的是引用數，不是建立。

    目標故意寫成不正規的 `…/tv//anime`：Jellyfin 回報的路徑是使用者打的，不保證正規。
    """
    target = f"{roots['library'] / 'tv'}//anime"
    Path(target).mkdir(parents=True, exist_ok=True)
    return Route(
        slug="tv-anime",
        name="TV anime",
        jellyfin_library_id="item-1",
        jellyfin_library_name="TV",
        collection_type=CollectionType.TVSHOWS,
        target_path=target,
        category="berth-tv-anime",
    )


def ledger_entry(target: str) -> LedgerEntry:
    """一筆已經鏈接好的帳本。這裡只有目標路徑重要。"""
    return LedgerEntry(
        source_rel_path="release/Show - S01E01.mkv",
        source_abs_path="/data/torrent/complete/tv/release/Show - S01E01.mkv",
        source_inode="1",
        source_dev="1",
        target_path=target,
        target_inode="1",
        action=PlanAction.IMPORT,
    )
