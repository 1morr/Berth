"""健康頁的總狀態說真話（M4 票 59，審計 P1-3、P2-17）。

三件事：換一台 qBittorrent 之後 Route 那一格不再是「已繫上」，重查完才是；探針從沒問過的 Route
不算綠；完成精靈時頁序驗過的結論寫進健康紀錄，健康頁一打開就有時間。

每一條都雙向：壞的那一邊與好的那一邊各一個斷言，只有一邊的話把判定寫死也會過。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import HealthStatus, RouteCheck, ServiceKind, ServiceOrigin, StepStatus
from berth.models import HealthSettings, Route, RouteHealth, SetupSettings
from berth.services.clients import BundledServices
from berth.services.health import CHECK_INTERVAL, check_health, overall_status, read_health
from berth.services.routes import build_routes, check_routes
from berth.services.settings import read_settings, write_settings
from berth.services.setup import ServiceConnection, choose_service, complete_setup
from tests.integration.arrange import NOW, arrange, factory_for
from tests.integration.factories import COMPOSE, FakeClientFactory

pytestmark = pytest.mark.asyncio

BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="mounted-key")


async def ready(session: AsyncSession, roots: dict[str, Path]) -> FakeClientFactory:
    """精靈頁 3 做完：三條 Route 都真的問過探針、綠燈。"""
    factory = factory_for(roots)
    await arrange(session, roots)
    assert (await build_routes(session, factory, ())).ready
    return factory


async def switch_qbittorrent(session: AsyncSession, factory: FakeClientFactory) -> None:
    await choose_service(
        session,
        factory,
        BUNDLED,
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8080"),
        now=NOW,
    )


async def forget_probes(session: AsyncSession) -> None:
    """探針那一條從沒問過的樣子：其餘五條照舊，`download_visible` 是 `pending`、沒有另存的結論。"""
    for stored in (await session.scalars(select(Route))).all():
        health = RouteHealth.model_validate(stored.health_detail_json)
        stored.health_detail_json = health.model_copy(
            update={
                "checks": [
                    row.model_copy(update={"status": StepStatus.PENDING})
                    if row.key == RouteCheck.DOWNLOAD_VISIBLE.value
                    else row
                    for row in health.checks
                ],
                "probe": None,
                "probed_at": None,
            }
        ).model_dump(mode="json")
    await session.commit()


class TestAfterSwitchingQbittorrent:
    async def test_the_routes_berth_is_not_secured_until_they_are_checked_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """審計 S4：換台之後 BTH 3 寫「已繫上」，三條 Route 卻都是「尚未檢查」。"""
        factory = await ready(session, roots)
        assert (await check_health(session, factory, now=NOW)).routes_status is HealthStatus.OK

        await switch_qbittorrent(session, factory)

        assert (await read_health(session)).routes_status is HealthStatus.UNKNOWN
        # 迴圈不問探針：分類在新那台建好了，但它看不看得到 Berth 的檔案沒人問過，仍不是綠的。
        looped = await check_health(session, factory, now=NOW + CHECK_INTERVAL)
        assert looped.routes_status is HealthStatus.UNKNOWN
        assert {route.health for route in looped.routes} == {HealthStatus.UNKNOWN}

        # 換台成功之後自動跑的那一輪（`POST /routes/check`）真的問探針。
        await check_routes(session, factory)

        rechecked = await read_health(session)
        assert rechecked.routes_status is HealthStatus.OK
        assert {route.health for route in rechecked.routes} == {HealthStatus.OK}

    async def test_switching_does_not_make_berth_degraded(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「要重新檢查」不是壞了：匿名的 `GET /api/health` 照樣是 ok。"""
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)

        await switch_qbittorrent(session, factory)

        assert await overall_status(session) == "ok"

    async def test_a_red_route_makes_berth_degraded_without_waiting_for_the_loop(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """反向：總狀態跟著 Route 表走，一條 Route 被重新檢查成紅燈，不必等下一輪就降級。"""
        factory = await ready(session, roots)
        await check_health(session, factory, now=NOW)
        assert await overall_status(session) == "ok"

        factory.jellyfin_.visible_roots = ("/somewhere-else",)
        await check_routes(session, factory)

        assert await overall_status(session) == "degraded"
        assert (await read_health(session)).routes_status is HealthStatus.FAILED


class TestWhenTheRouteChecksCrash:
    async def test_the_routes_keep_their_last_conclusion_and_the_services_are_recorded(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """總結不再存一份「炸了就紅」（M4 票 59）：沒預料到的例外記 log，三項服務照樣記下，
        各條 Route 留著上一次的結論與時間——健康頁看得到那是何時的，下一輪重跑。"""
        factory = await ready(session, roots)
        before = {route.slug: route.checked_at for route in (await read_health(session)).routes}

        async def explode(*args: object, **kwargs: object) -> None:
            raise RuntimeError("the route checks blew up")

        monkeypatch.setattr("berth.services.health.check_routes", explode)

        report = await check_health(session, factory, now=NOW)

        assert report.checked_at == NOW
        assert {row.kind: row.status for row in report.services} == dict.fromkeys(
            ServiceKind, HealthStatus.OK
        )
        assert report.routes_status is HealthStatus.OK
        assert {route.slug: route.checked_at for route in report.routes} == before


class TestNeverProbed:
    async def test_a_route_whose_probe_was_never_asked_is_not_green(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """審計 S4 換回套件內：5/6，探針那一條「尚未執行」，標題卻是「已繫上」。"""
        factory = await ready(session, roots)
        await forget_probes(session)
        passed = {route.slug: route.last_ok_at for route in (await read_health(session)).routes}

        report = await check_health(session, factory, now=NOW)

        assert report.routes_status is HealthStatus.UNKNOWN
        assert {route.health for route in report.routes} == {HealthStatus.UNKNOWN}
        for route in report.routes:
            row = next(step for step in route.checks if step.step == "download_visible")
            assert row.status is StepStatus.PENDING
            # 「最後一次通過」不因為沒問的那一輪往前推。
            assert route.last_ok_at == passed[route.slug]

    async def test_a_route_whose_probe_was_asked_stays_green_in_the_loop(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """反向：問過探針的 Route，迴圈沿用那一次的結論，照樣是綠的。"""
        factory = await ready(session, roots)
        passed = {route.slug: route.last_ok_at for route in (await read_health(session)).routes}

        report = await check_health(session, factory, now=NOW)

        assert report.routes_status is HealthStatus.OK
        for route in report.routes:
            before = passed[route.slug]
            assert before is not None and route.last_ok_at is not None
            assert route.last_ok_at > before

    async def test_a_route_that_was_never_probed_still_takes_sends(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送單的規則不變（`jobs.check_route`）：`unknown` 放行，只有紅的擋。"""
        factory = await ready(session, roots)
        await forget_probes(session)
        await check_health(session, factory, now=NOW)

        rows = (await session.scalars(select(Route))).all()

        assert {row.health_status for row in rows} == {HealthStatus.UNKNOWN}
        assert all(row.enabled for row in rows)


class TestFinishingTheWizard:
    async def test_finishing_writes_what_the_pages_verified_into_the_health_record(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """審計 P2-17：完成精靈之後打開健康頁，四個泊位都是「尚未檢查」、「沒有紀錄」。"""
        await ready(session, roots)
        finished_at = NOW + timedelta(minutes=3)

        await complete_setup(session, now=finished_at)

        report = await read_health(session)
        assert report.checked_at == finished_at
        assert {row.kind: row.status for row in report.services} == dict.fromkeys(
            ServiceKind, HealthStatus.OK
        )
        # 每一格的時間是那一頁真的測的那一刻，不是按下完成的那一刻。
        assert {row.checked_at for row in report.services} == {NOW}
        assert all(row.configured and row.last_ok_at == NOW for row in report.services)
        assert report.routes_status is HealthStatus.OK
        assert await overall_status(session) == "ok"

    async def test_a_skipped_indexer_page_is_recorded_as_not_connected(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """頁 4 之後再說：那一格是「尚未接上」，不是「已繫上」也不是紅燈。"""
        await ready(session, roots)
        setup = await read_settings(session, SetupSettings)
        setup.indexer.steps = []
        setup.indexer.skipped = True
        await write_settings(session, setup)
        await session.commit()

        await complete_setup(session, now=NOW)

        prowlarr = next(
            row for row in (await read_health(session)).services if row.kind is ServiceKind.PROWLARR
        )
        assert prowlarr.status is HealthStatus.UNKNOWN
        assert prowlarr.configured is False
        assert prowlarr.checked_at is not None

    async def test_a_newer_loop_result_is_not_overwritten(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """反向：精靈還沒完成時迴圈已經跑過、而且比頁上的測試新，留著迴圈那一份。"""
        factory = await ready(session, roots)
        later = NOW + timedelta(minutes=10)
        await check_health(session, factory, now=later)
        before = await read_settings(session, HealthSettings)

        await complete_setup(session, now=later + timedelta(minutes=1))

        after = await read_settings(session, HealthSettings)
        assert after.services == before.services
        assert after.checked_at == later + timedelta(minutes=1)
