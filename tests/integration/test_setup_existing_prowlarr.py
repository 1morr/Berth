"""既有 Prowlarr 不再是死路（M4 票 20，2026-09-30 精靈審查）。

- **0 站不算完成**：零站的 Berth 什麼都搜不到。連上了、一站都沒有，頁 4 停在待處理，按「之後再說」
  才往下；有站就完成。服務頁的二選一（頁 4 的既有表單也是它，M4 票 39）與「重新測試」同一條規則。
- **舊版說出版本**：1.3.2 之前沒有 `/ping`（回介面的 HTML），版本從 `system/status` 讀
  （帶 key；2026-09-30 對 `bad-prowlarr-old` 1.0.1.2220 實測）。
- **key 錯是 `auth_required`**，不是「連不上」。
- **既有 Prowlarr 也能測站、勾選、按一次加入**（使用者 2026-09-30 拍板）：加的只有勾選的站、不碰
  `config/host`；沒按就不加。介面登入只屬於套件內。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ProtocolMismatchError, ServiceUnavailableError
from berth.adapters.prowlarr import ProwlarrIndexer
from berth.domain import (
    ConnectionReason,
    ConnectionState,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import SetupSettings
from berth.services.clients import BundledServices
from berth.services.indexer import (
    apply_default_indexers,
    read_indexer_status,
    remove_indexer,
    skip_indexers,
    verify_sites,
)
from berth.services.routes import build_routes
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_INDEXER,
    ConnectionFailedError,
    ServiceConnection,
    ServiceView,
    choose_service,
    read_status,
    retest_service,
)
from tests.integration.arrange import arrange, factory_for
from tests.integration.factories import COMPOSE, FakeClientFactory

pytestmark = pytest.mark.asyncio

HOME = "http://host.docker.internal:48696"
BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="")
#: `bad-prowlarr-old` 回報的版號（2026-09-30 實測 `GET /api/v1/system/status`）。
OLD = "1.0.1.2220"
AT_FLOOR = "1.3.2.3006"


def site(indexer_id: int, definition_name: str) -> ProwlarrIndexer:
    return ProwlarrIndexer(
        id=indexer_id,
        name=definition_name,
        enabled=True,
        definition_name=definition_name,
        privacy="private",
        protocol="torrent",
    )


async def ready(session: AsyncSession, roots: dict[str, Path]) -> FakeClientFactory:
    """前三個泊位接好、Route 建好：輪到頁 4。Prowlarr 還沒有任何站。"""
    await arrange(session, roots)
    factory = factory_for(roots)
    await build_routes(session, factory, ())
    return factory


async def choose_existing(session: AsyncSession, factory: FakeClientFactory) -> None:
    await choose_service(
        session,
        factory,
        BUNDLED,
        ServiceKind.PROWLARR,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url=HOME, api_key="theirs"),
    )


async def refused(session: AsyncSession, factory: FakeClientFactory) -> ServiceView:
    """測不過不存（M4 票 45）：那一次的結論在拒絕裡，選擇與頁 4 的纜繩都沒動。"""
    before = await read_settings(session, SetupSettings)
    with pytest.raises(ConnectionFailedError) as refusal:
        await choose_existing(session, factory)
    after = await read_settings(session, SetupSettings)
    assert (after.choices, after.indexer.steps) == (before.choices, before.indexer.steps)
    return refusal.value.attempt


class TestZeroSites:
    async def test_a_prowlarr_with_no_sites_keeps_the_wizard_on_page_four(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)

        await choose_existing(session, factory)

        assert (await read_status(session)).current_step == STEP_INDEXER
        (step,) = (await read_settings(session, SetupSettings)).indexer.steps
        # 待處理，不是失敗：連上了，只是還沒有站。細節照樣是站數。
        assert (step.status, step.detail) == (StepStatus.PENDING, "0")

    async def test_a_prowlarr_with_sites_settles_the_page(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_ = type(factory.prowlarr_)(indexers=[site(7, "animebytes")])

        await choose_existing(session, factory)

        assert (await read_status(session)).current_step > STEP_INDEXER

    async def test_skipping_moves_past_an_empty_prowlarr(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        await choose_existing(session, factory)

        await skip_indexers(session, factory)

        assert (await read_status(session)).current_step > STEP_INDEXER

    async def test_rereading_after_adding_sites_in_prowlarr_settles_the_page(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「到 Prowlarr 加站後按重新讀取」：重新讀取就是服務頁的重新測試。"""
        factory = await ready(session, roots)
        await choose_existing(session, factory)
        factory.prowlarr_ = type(factory.prowlarr_)(indexers=[site(7, "animebytes")])

        await retest_service(session, factory, BUNDLED, ServiceKind.PROWLARR, restart=True)

        assert (await read_status(session)).current_step > STEP_INDEXER


class TestOldProwlarr:
    """`/ping` 回 HTML（1.3.2 之前沒有它），版本照樣說得出來。"""

    async def test_a_prowlarr_without_ping_says_its_version(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.version = OLD

        attempt = await refused(session, factory)

        assert (attempt.state, attempt.reason, attempt.detail) == (
            ConnectionState.FAILED,
            ConnectionReason.VERSION_UNSUPPORTED,
            OLD,
        )

    async def test_the_floor_passes(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.version = AT_FLOOR

        await choose_existing(session, factory)

        test = (await read_settings(session, SetupSettings)).choices[ServiceKind.PROWLARR].test
        assert test is not None
        assert (test.state, test.reason) == (ConnectionState.OK, ConnectionReason.CONNECTED)


class TestWrongKey:
    async def test_a_rejected_key_is_auth_required(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.key_rejected = True

        attempt = await refused(session, factory)

        assert (attempt.state, attempt.reason) == (
            ConnectionState.FAILED,
            ConnectionReason.AUTH_REQUIRED,
        )


class TestOtherFailures:
    """票 20 之前頁 4 的既有表單把每一種失敗都說成連不上。分得出來的另外兩種；雙向：連不上照舊。"""

    async def test_something_else_at_the_address_is_protocol_mismatch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.ping_error = ProtocolMismatchError("/api/v1/system/status: not JSON")

        assert (await refused(session, factory)).reason is ConnectionReason.PROTOCOL_MISMATCH

    async def test_nothing_answering_is_still_unreachable(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        factory.prowlarr_.ping_error = ServiceUnavailableError("connection refused")

        assert (await refused(session, factory)).reason is ConnectionReason.UNREACHABLE


class TestAddingToAnExistingProwlarr:
    async def test_only_the_ticked_sites_are_added_and_the_login_is_untouched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        prowlarr = factory.prowlarr_
        await choose_existing(session, factory)
        login = await prowlarr.host_config()

        status = await read_indexer_status(session, factory)
        offered = {row.definition_name for row in status.candidates}
        assert {"nyaasi", "dmhy", "mikan"} <= offered
        checks = await verify_sites(session, factory, ["nyaasi", "dmhy", "mikan"])
        assert all(row.passed for row in checks)
        assert await prowlarr.indexers() == []

        status = await apply_default_indexers(session, factory, ["nyaasi", "dmhy"])

        assert sorted(row.definition_name for row in await prowlarr.indexers()) == [
            "dmhy",
            "nyaasi",
        ]
        assert prowlarr.restarts == 0
        assert await prowlarr.host_config() == login
        # 介面登入只屬於套件內：既有的那一台沒有那一條纜繩。
        assert "prowlarr_login" not in {row.step for row in status.steps}
        assert not status.web_ui_login
        # 加完這一頁就完成了，連線卡與泊位卡讀到的站數跟著清單。
        assert (await read_status(session)).current_step > STEP_INDEXER
        test = (await read_settings(session, SetupSettings)).choices[ServiceKind.PROWLARR].test
        assert test is not None and test.detail == "2"
        assert [row.definition_name for row in status.sites] == ["nyaasi", "dmhy"]
        assert not any(row.removable for row in status.sites)

    async def test_nothing_is_added_before_the_button(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """測試與讀清單都不建立任何站：沒按「加入」，那一台原封不動。"""
        factory = await ready(session, roots)
        await choose_existing(session, factory)

        await read_indexer_status(session, factory)
        await verify_sites(session, factory, ["nyaasi"])
        await apply_default_indexers(session, factory, [])

        assert await factory.prowlarr_.indexers() == []
        assert factory.prowlarr_.restarts == 0
        assert (await read_status(session)).current_step == STEP_INDEXER

    async def test_berth_still_does_not_remove_sites_from_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """移除交給 Prowlarr 自己的介面：Berth 加上去的也一樣。"""
        factory = await ready(session, roots)
        await choose_existing(session, factory)
        await apply_default_indexers(session, factory, ["nyaasi"])
        (added,) = await factory.prowlarr_.indexers()

        with pytest.raises(ValueError, match="existing service"):
            await remove_indexer(session, factory, added.id)
        assert factory.prowlarr_.deleted == []


class TestBundledLoginIsItsOwnStep:
    async def test_adding_sites_needs_no_login_and_the_login_still_gates_the_page(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """套件內：「加入 N 個站」不帶登入；沒設過介面登入時這一頁仍停著（M4 票 07 的必填照舊）。"""
        factory = await ready(session, roots)
        setup = await read_settings(session, SetupSettings)
        setup.indexer.steps = []
        await write_settings(session, setup)
        await session.commit()

        status = await apply_default_indexers(session, factory, ["nyaasi"])

        assert [row.definition_name for row in await factory.prowlarr_.indexers()] == ["nyaasi"]
        login = next(row for row in status.steps if row.step == "prowlarr_login")
        assert login.status is StepStatus.PENDING
        assert factory.prowlarr_.restarts == 0
        assert (await read_status(session)).current_step == STEP_INDEXER
