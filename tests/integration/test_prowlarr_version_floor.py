"""既有 Prowlarr 的版本下限（M4 票 17、brief §20.14、plan §9.5）。

精靈的兩條入口（頁 4 的既有表單 `connect_indexer`、服務頁的二選一 `choose_service` 與「重新測試」）
與健康檢查用同一個判斷、同一句原文；低於下限停在 Prowlarr 頁，說出目前版本與下限。
雙向：比下限舊一版的擋、剛好等於下限的過。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.prowlarr import unsupported_message
from berth.domain import (
    ConnectionReason,
    ConnectionState,
    HealthStatus,
    IndexerKind,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import SetupSettings, SetupStep
from berth.services.clients import BundledServices
from berth.services.health import check_health
from berth.services.indexer import connect_indexer
from berth.services.routes import build_routes
from berth.services.settings import read_settings
from berth.services.setup import (
    STEP_INDEXER,
    ServiceConnection,
    choose_service,
    read_status,
    retest_service,
)
from tests.integration.arrange import NOW, arrange, factory_for
from tests.integration.factories import COMPOSE, FakeClientFactory

pytestmark = pytest.mark.asyncio

#: 下限本身（brief §20.14：第一個有 `/ping` 的 stable）與比它舊、而且還沒有 `/ping` 的那一版。
AT_FLOOR = "1.3.2.3006"
BELOW_FLOOR = "1.2.2.2699"

LATER = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


async def ready(session: AsyncSession, roots: dict[str, Path], version: str) -> FakeClientFactory:
    """精靈跑到底的樣子，Prowlarr 回報 `version`；各條測試再把頁 4 改成它要的那一條入口。"""
    await arrange(session, roots)
    factory = factory_for(roots)
    await build_routes(session, factory, ())
    factory.prowlarr_.version = version
    return factory


class TestWizard:
    async def test_the_existing_form_stops_below_the_floor_and_says_both_versions(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots, BELOW_FLOOR)

        status = await connect_indexer(
            session, factory, kind=IndexerKind.PROWLARR, base_url="http://nas:9696", api_key="k"
        )

        (step,) = status.steps
        assert (step.status, step.detail) == (StepStatus.FAILED, BELOW_FLOOR)
        assert step.error == unsupported_message(BELOW_FLOOR)
        assert BELOW_FLOOR in step.error and "1.3.2" in step.error
        setup = await read_settings(session, SetupSettings)
        test = setup.choices[ServiceKind.PROWLARR].test
        assert test is not None
        assert (test.state, test.reason) == (
            ConnectionState.FAILED,
            ConnectionReason.VERSION_UNSUPPORTED,
        )
        assert (await read_status(session)).current_step == STEP_INDEXER
        # 既有表單照理由選補法：叫人升級，不叫人改位址。
        assert status.reason is ConnectionReason.VERSION_UNSUPPORTED

    async def test_the_existing_form_passes_exactly_at_the_floor(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots, AT_FLOOR)

        status = await connect_indexer(
            session, factory, kind=IndexerKind.PROWLARR, base_url="http://nas:9696", api_key="k"
        )

        assert status.steps[0].status is StepStatus.OK

    @pytest.mark.parametrize(
        ("version", "passes"), [(BELOW_FLOOR, False), (AT_FLOOR, True)], ids=["below", "at"]
    )
    async def test_choosing_and_retesting_use_the_same_gate(
        self, session: AsyncSession, roots: dict[str, Path], version: str, passes: bool
    ) -> None:
        """服務頁的二選一與「重新測試」不經過頁 4 的表單，一樣要擋（它們會改寫這一頁的結果）。"""
        factory = await ready(session, roots, version)
        bundled = BundledServices(targets=COMPOSE, prowlarr_api_key="")

        await choose_service(
            session,
            factory,
            bundled,
            ServiceKind.PROWLARR,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://nas:9696", api_key="k"),
            now=LATER,
        )
        chosen = (await read_settings(session, SetupSettings)).indexer.steps
        await retest_service(session, factory, ServiceKind.PROWLARR, restart=True, now=LATER)
        retested = (await read_settings(session, SetupSettings)).indexer.steps

        expected = (
            SetupStep(key="prowlarr", status=StepStatus.OK, detail="0")
            if passes
            else SetupStep(
                key="prowlarr",
                status=StepStatus.FAILED,
                detail=version,
                error=unsupported_message(version),
            )
        )
        assert chosen == retested == [expected]


class TestHealth:
    @pytest.mark.parametrize(
        ("version", "status"),
        [(BELOW_FLOOR, HealthStatus.FAILED), (AT_FLOOR, HealthStatus.OK)],
        ids=["below", "at"],
    )
    async def test_the_health_check_says_the_same_sentence(
        self, session: AsyncSession, roots: dict[str, Path], version: str, status: HealthStatus
    ) -> None:
        factory = await ready(session, roots, version)

        report = await check_health(session, factory, now=NOW)
        row = next(row for row in report.services if row.kind is ServiceKind.PROWLARR)

        assert row.status is status
        if status is HealthStatus.FAILED:
            # 健康頁把 `detail` 標成「索引站」，版本只在原文裡說。
            assert (row.detail, row.error) == ("", unsupported_message(version))
