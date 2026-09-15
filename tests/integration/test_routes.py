"""Route 設定頁的 services 命令（plan §6 routes 群組、brief §4.3、票 14）。

精靈第 7 步只新增（`test_setup_routes.py`）；逐條管理在這裡：同一個媒體庫的第二條 Route、
紅燈不給啟用、刪除是明確動作而被引用時拒絕。

與精靈同一個起點（`arrange`）、同一組**真的**檔案系統檢查——一條 Route 綠不綠，問的永遠是
那五條纜繩，而它們在 tmp 目錄底下真的鏈接一次檔案。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.domain import HealthStatus, JobTrigger, PlanAction, Profile, StepStatus
from berth.models import Job, LedgerEntry, SetupLibrary
from berth.services.routes import (
    RouteRejectedError,
    build_routes,
    check_route,
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
    factory_for,
    fake_jellyfin,
    with_second_disk,
)

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
            profile=Profile.ANIME,
        )

        assert (route.slug, route.name, route.library, route.target_path) == (
            "tv-2",
            "TV 2",
            "TV",
            str(disk),
        )
        assert (route.category, route.profile) == ("berth-tv-2", Profile.ANIME)
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
            profile=Profile.STANDARD,
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
                profile=Profile.STANDARD,
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
                profile=Profile.STANDARD,
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
        profile=Profile.STANDARD,
    )
    return route.id, disk


class TestUpdate:
    async def test_name_and_profile_change(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)

        route = await update_route(
            session,
            factory_for(roots, libraries=libraries),
            route_id,
            name="Second disk",
            profile=Profile.ANIME,
            enabled=False,
        )

        assert (route.name, route.profile, route.enabled) == ("Second disk", Profile.ANIME, False)
        # slug 與目標路徑不動：category、complete 子目錄與帳本歸屬都由它們導出（使用者拍板）。
        assert (route.slug, route.category) == ("tv-2", "berth-tv-2")

    async def test_a_route_whose_checks_are_red_is_not_enabled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """紅的不給啟用（票 14 驗收）。啟用那一刻再檢查一次，不相信上一輪的結果；
        同一次送出的名稱與 profile 照樣存下（使用者拍板）。"""
        route_id, _ = await red_second_route(session, roots)
        libraries, _ = with_second_disk(roots)
        blind = fake_jellyfin(libraries, visible_roots=("/elsewhere",))

        with pytest.raises(RouteRejectedError) as refusal:
            await update_route(
                session,
                factory_for(roots, jellyfin=blind),
                route_id,
                name="Second disk",
                profile=Profile.ANIME,
                enabled=True,
            )

        assert refusal.value.reason == "route_unhealthy"
        route = next(row for row in (await read_route_status(session)).routes if row.id == route_id)
        assert (route.enabled, route.health) == (False, HealthStatus.FAILED)
        assert (route.name, route.profile) == ("Second disk", Profile.ANIME)

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
            profile=Profile.STANDARD,
            enabled=True,
        )

        assert (route.enabled, route.health) == (True, HealthStatus.OK)

    async def test_an_unknown_route_is_a_reason(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        with pytest.raises(RouteRejectedError) as refusal:
            await update_route(
                session, factory_for(roots), 999, name="x", profile=Profile.STANDARD, enabled=True
            )

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
        session.add(ledger_entry(f"{disk.as_posix()}/Show (2024)/Season 01/Show - S01E01.mkv"))
        await session.commit()

        with pytest.raises(RouteRejectedError) as refusal:
            await delete_route(session, route_id)

        assert refusal.value.reason == "route_in_use"

    async def test_files_under_another_route_do_not_hold_this_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route_id, _ = await red_second_route(session, roots)
        tv = (roots["library"] / "tv").as_posix()
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
        session.add(ledger_entry(f"{disk.as_posix()}/Show (2024)/Season 01/Show - S01E01.mkv"))
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
        assert (tv.item_id, tv.locations, tv.taken) == (
            "item-1",
            (str(roots["library"] / "tv"), str(disk)),
            (str(roots["library"] / "tv"),),
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


class TestProfile:
    async def test_a_movie_library_cannot_get_an_anime_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票面：「劇集可挑不同 profile」。anime 是劇集的季集與命名規則，電影沒有這條路徑——
        規則在後端，不只靠前端把選項藏起來。"""
        await arrange(session, roots)

        with pytest.raises(RouteRejectedError) as refusal:
            await create_route(
                session,
                factory_for(roots),
                library_id="item-0",
                target_path=str(roots["library"] / "movies"),
                name="Movies",
                profile=Profile.ANIME,
            )

        assert refusal.value.reason == "profile_unsupported"

    async def test_a_movie_route_cannot_switch_to_anime(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())
        movies = next(
            row for row in (await read_route_status(session)).routes if row.slug == "movies"
        )

        with pytest.raises(RouteRejectedError) as refusal:
            await update_route(
                session,
                factory_for(roots),
                movies.id,
                name="Movies",
                profile=Profile.ANIME,
                enabled=True,
            )

        assert refusal.value.reason == "profile_unsupported"


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
        精靈的第 7 步退回未完成，也不該讓健康頁永遠是 degraded。"""
        await red_second_route(session, roots)

        assert await routes_ready(session) is True
        assert await routes_health(session) is HealthStatus.OK


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
