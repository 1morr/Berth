"""精靈第 5–6 步的 services 命令（plan §9.3 第 5–6 步、§8.3、§8.4、票 08）。

驗的是票 08 的驗收條件：十個預設站逐站顯示成敗、重按不會重複新增、既有 Prowlarr 與任意
Torznab 各有測試；TMDB 那一半改由票 02b 定義——憑證使用者自備、必填，測得過才走得下去。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.prowlarr import IndexerDefinition, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.tmdb import TmdbConfiguration
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torznab import TorznabCaps, TorznabSearchMode
from berth.adapters.torznab.fake import FakeTorznabClient
from berth.db import create_session_factory
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    DetectionReason,
    IndexerKind,
    JellyfinStep,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import IndexerSettings, ServiceProbe, SetupSettings, SetupStep, TmdbSettings
from berth.services.indexer import (
    DEFAULT_INDEXERS,
    apply_default_indexers,
    connect_indexer,
    read_indexer_status,
    skip_indexers,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_INDEXER, STEP_ROUTES, STEP_TMDB, create_admin, read_status
from berth.services.tmdb import read_tmdb_status, verify_tmdb
from tests.conftest import TMDB_API_KEY
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)

#: 這台 Prowlarr 連不出去的那幾個站，訊息取自 2026-09-08 的實測（brief §20.7）。
BLOCKED = {
    "1337x": "Unable to access 1337x.to, blocked by CloudFlare Protection.",
    "eztv": "Unable to access eztvx.to, blocked by CloudFlare Protection.",
}


async def arrange(
    session: AsyncSession,
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
    apply_to_services: bool = True,
) -> None:
    """把資料庫推到「前三個泊位都接好、輪到來源」的狀態。"""
    await create_admin(
        session, username="skipper", password="harbour", apply_to_services=apply_to_services
    )
    setup = await read_settings(session, SetupSettings)
    setup.jellyfin.steps = [SetupStep(key=JellyfinStep.API_KEY.value, status=StepStatus.OK)]
    setup.qbittorrent.steps = [
        SetupStep(key=step.value, status=StepStatus.OK)
        for step in QbittorrentStep
        if step is not QbittorrentStep.PASSWORD
    ]
    setup.services = {
        ServiceKind.JELLYFIN: ServiceProbe(
            origin=ServiceOrigin.EXISTING,
            reason=DetectionReason.SETUP_COMPLETED,
            base_url="http://nas:8096",
            checked_at=NOW,
            configured=True,
        ),
        ServiceKind.QBITTORRENT: ServiceProbe(
            origin=ServiceOrigin.BUNDLED,
            reason=DetectionReason.ANONYMOUS_OK,
            base_url="http://qbittorrent:8080",
            checked_at=NOW,
        ),
        ServiceKind.PROWLARR: ServiceProbe(
            origin=origin,
            reason=(
                DetectionReason.NO_INDEXERS
                if origin is ServiceOrigin.BUNDLED
                else DetectionReason.HAS_INDEXERS
            ),
            base_url="http://prowlarr:9696"
            if origin is ServiceOrigin.BUNDLED
            else "http://nas:9696",
            checked_at=NOW,
            configured=origin is not ServiceOrigin.BUNDLED,
        ),
    }
    await write_settings(session, setup)
    settings = await read_settings(session, IndexerSettings)
    settings.api_key = "0" * 31 + "1"
    await write_settings(session, settings)
    await session.commit()


@pytest.mark.asyncio
async def test_the_ten_default_indexers_are_offered_with_their_real_names(
    session: AsyncSession,
) -> None:
    await arrange(session)
    factory = FakeClientFactory()

    status = await read_indexer_status(session, factory)

    assert [row.definition_name for row in status.options] == list(DEFAULT_INDEXERS)
    assert [row.name for row in status.options][:3] == ["Nyaa.si", "dmhy", "Anidex"]
    # 站名是伺服器自己報的，privacy 也是——勾選清單靠它標出唯一不是公開的那一個。
    assert [row.privacy for row in status.options if row.definition_name == "animetosho-xyz"] == [
        "semiPrivate"
    ]
    assert all(row.present is False for row in status.options)


@pytest.mark.asyncio
async def test_applying_the_defaults_reports_every_site_on_its_own_line(
    session: AsyncSession,
) -> None:
    """十個公開站裡有幾個連不上是常態：失敗的那幾條變紅，其餘照樣繫上。"""
    await arrange(session, apply_to_services=False)
    client = FakeProwlarrClient(rejects=BLOCKED)
    factory = FakeClientFactory(prowlarr=client)

    status = await apply_default_indexers(session, factory, DEFAULT_INDEXERS)

    by_step = {row.step: row for row in status.steps}
    assert by_step["nyaasi"].status is StepStatus.OK
    assert by_step["1337x"].status is StepStatus.FAILED
    assert by_step["1337x"].error == BLOCKED["1337x"]
    assert [row.definition_name for row in status.options if row.present] == [
        name for name in DEFAULT_INDEXERS if name not in BLOCKED
    ]


@pytest.mark.asyncio
async def test_only_the_ticked_indexers_are_added(session: AsyncSession) -> None:
    await arrange(session, apply_to_services=False)
    client = FakeProwlarrClient()
    factory = FakeClientFactory(prowlarr=client)

    status = await apply_default_indexers(session, factory, ["nyaasi", "mikan"])

    assert [row.step for row in status.steps if row.step in DEFAULT_INDEXERS] == [
        "nyaasi",
        "mikan",
    ]
    assert {row.definition_name for row in await client.indexers()} == {"nyaasi", "mikan"}


@pytest.mark.asyncio
async def test_pressing_apply_twice_does_not_add_a_second_copy(session: AsyncSession) -> None:
    """同名的第二個站會被 Prowlarr 拒（`Should be unique`），所以先列再決定（實測）。"""
    await arrange(session, apply_to_services=False)
    client = FakeProwlarrClient()
    factory = FakeClientFactory(prowlarr=client)

    await apply_default_indexers(session, factory, ["nyaasi", "mikan"])
    status = await apply_default_indexers(session, factory, ["nyaasi", "mikan"])

    assert len(await client.indexers()) == 2
    # 已經在了的站改用 `indexer/test` 驗一次，結果一樣是「這個站現在通不通」。
    assert client.tested == ["nyaasi", "mikan"]
    assert [row.status for row in status.steps if row.step in DEFAULT_INDEXERS] == [
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
    ]


@pytest.mark.asyncio
async def test_the_bundled_prowlarr_gets_the_admin_credentials(session: AsyncSession) -> None:
    """勾了「同一組帳密」就替 Prowlarr 介面設 Forms 登入（brief §16.3）。"""
    await arrange(session)
    client = FakeProwlarrClient()
    factory = FakeClientFactory(prowlarr=client)

    status = await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)

    config = await client.host_config()
    assert config["authenticationMethod"] == "forms"
    assert config["username"] == "skipper"
    # 少了 `passwordConfirmation` 那台真的會拒收（brief §20.7）。
    assert config["passwordConfirmation"] == "harbour"
    assert client.restarts == 1
    assert [row.status for row in status.steps if row.step == PROWLARR_LOGIN_STEP] == [
        StepStatus.OK
    ]

    # 重按不會再設一次，也就不會再重啟一次。
    await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)
    assert client.restarts == 1


@pytest.mark.asyncio
async def test_new_interface_credentials_reach_prowlarr_when_step_five_is_applied_again(
    session: AsyncSession,
) -> None:
    """只改密碼也要重寫（票 06c）：Prowlarr 讀回來的密碼是雜湊，比的是 Berth 上次寫的那一組。"""
    await arrange(session)
    client = FakeProwlarrClient()
    factory = FakeClientFactory(prowlarr=client)
    await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)

    await create_admin(session, username="skipper", password="changed", apply_to_services=True)
    await session.commit()
    status = await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)

    config = await client.host_config()
    assert (config["username"], config["password"]) == ("skipper", "changed")
    assert client.restarts == 2
    assert [row.status for row in status.steps if row.step == PROWLARR_LOGIN_STEP] == [
        StepStatus.OK
    ]

    await create_admin(session, username="deckhand", password="changed", apply_to_services=True)
    await session.commit()
    await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)

    assert (await client.host_config())["username"] == "deckhand"
    assert client.restarts == 3


@pytest.mark.asyncio
async def test_an_unticked_box_leaves_the_prowlarr_interface_alone(
    session: AsyncSession,
) -> None:
    await arrange(session, apply_to_services=False)
    client = FakeProwlarrClient()

    await apply_default_indexers(session, FakeClientFactory(prowlarr=client), ["nyaasi"])

    assert (await client.host_config())["authenticationMethod"] == "none"
    assert client.restarts == 0


@pytest.mark.asyncio
async def test_the_prowlarr_verdict_is_pinned_once_berth_has_added_indexers(
    session: AsyncSession,
) -> None:
    """判定是「一個索引站都沒有 → 套件內」，加完之後重探會說謊，所以釘住它。"""
    await arrange(session, apply_to_services=False)

    await apply_default_indexers(session, FakeClientFactory(), ["nyaasi"])

    setup = await read_settings(session, SetupSettings)
    probe = setup.services[ServiceKind.PROWLARR]
    assert (probe.origin, probe.configured) == (ServiceOrigin.BUNDLED, True)


@pytest.mark.asyncio
async def test_an_existing_prowlarr_is_tested_by_address_and_key(session: AsyncSession) -> None:
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeProwlarrClient(
        indexers=[ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True, definition_name="nyaasi")]
    )
    factory = FakeClientFactory(prowlarr=client)

    status = await connect_indexer(
        session,
        factory,
        kind=IndexerKind.PROWLARR,
        base_url="http://nas:9696",
        api_key="the-key",
    )

    assert [(row.step, row.status, row.detail) for row in status.steps] == [
        (IndexerKind.PROWLARR.value, StepStatus.OK, "1")
    ]
    settings = await read_settings(session, IndexerSettings)
    assert (settings.kind, settings.base_url, settings.api_key) == (
        "prowlarr",
        "http://nas:9696",
        "the-key",
    )


@pytest.mark.asyncio
async def test_any_torznab_endpoint_works_too(session: AsyncSession) -> None:
    await arrange(session, origin=ServiceOrigin.EXISTING)
    factory = FakeClientFactory(
        torznab=FakeTorznabClient(
            caps=TorznabCaps(
                server_title="Jackett",
                search=TorznabSearchMode(available=True),
                categories=("TV",),
            )
        )
    )

    status = await connect_indexer(
        session,
        factory,
        kind=IndexerKind.TORZNAB,
        base_url="http://jackett:9117/api/v2.0/indexers/all/results/torznab/api",
        api_key="the-key",
    )

    assert [(row.step, row.status, row.detail) for row in status.steps] == [
        (IndexerKind.TORZNAB.value, StepStatus.OK, "Jackett · TV")
    ]
    assert (await read_settings(session, IndexerSettings)).kind == "torznab"


@pytest.mark.asyncio
async def test_a_failing_endpoint_is_saved_anyway_so_one_field_can_be_fixed(
    session: AsyncSession,
) -> None:
    await arrange(session, origin=ServiceOrigin.EXISTING)
    factory = FakeClientFactory(
        prowlarr=FakeProwlarrClient(ping_error=ServiceUnavailableError("connection refused"))
    )

    status = await connect_indexer(
        session, factory, kind=IndexerKind.PROWLARR, base_url="http://typo:9696", api_key="k"
    )

    assert status.steps[0].status is StepStatus.FAILED
    assert status.steps[0].error == "connection refused"
    assert (await read_settings(session, IndexerSettings)).base_url == "http://typo:9696"


@pytest.mark.asyncio
async def test_only_the_indexer_half_of_the_source_berth_can_be_skipped(
    session: AsyncSession,
) -> None:
    """第 5 步可跳過，第 6 步不行（票 02b）。

    沒有索引站只是搜尋不到東西，Berth 其餘功能還在；沒有 TMDB 則探索、季集快照、命名
    全部停擺，所以第 6 步是閘門而不是「之後再說」。
    """
    await arrange(session)
    assert (await read_status(session)).current_step == STEP_INDEXER

    await skip_indexers(session, FakeClientFactory())
    assert (await read_status(session)).current_step == STEP_TMDB

    await verify_tmdb(session, FakeClientFactory(), api_key=TMDB_API_KEY)
    assert (await read_status(session)).current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_a_rejected_credential_leaves_the_wizard_on_step_six(session: AsyncSession) -> None:
    """測失敗與沒測過一樣走不下去——閘門看的是綠燈，不是「按過了」。"""
    await arrange(session)
    await skip_indexers(session, FakeClientFactory())
    factory = FakeClientFactory(
        tmdb=FakeTmdbClient(error=AuthFailedError("GET /configuration: 401"))
    )

    await verify_tmdb(session, factory, api_key="0000000000000000000000000000dead")

    assert (await read_status(session)).current_step == STEP_TMDB


@pytest.mark.asyncio
async def test_the_pasted_key_is_the_only_source_of_the_credential(
    session: AsyncSession,
) -> None:
    """Berth 不內建任何 provider 的 key（票 02b），所以測之前這裡是空的。"""
    await arrange(session)
    client = FakeTmdbClient(
        configuration=TmdbConfiguration(image_base_url="https://image.tmdb.org/t/p/")
    )
    factory = FakeClientFactory(tmdb=client)

    before = await read_tmdb_status(session)
    assert (before.api_key_present, before.verified) == (False, False)

    status = await verify_tmdb(session, factory, api_key=f"  {TMDB_API_KEY} ")

    assert client.credential == TMDB_API_KEY
    assert [(row.step, row.status, row.detail) for row in status.steps] == [
        ("configuration", StepStatus.OK, "https://image.tmdb.org/t/p/")
    ]
    assert (status.api_key_present, status.verified) == (True, True)
    assert (await read_settings(session, TmdbSettings)).api_key == TMDB_API_KEY


@pytest.mark.asyncio
async def test_a_blank_credential_is_a_red_line_not_a_request(session: AsyncSession) -> None:
    """空白不必打去 TMDB 才知道不行，而它說的話要是「必填」不是「401」。"""
    await arrange(session)
    client = FakeTmdbClient()

    status = await verify_tmdb(session, FakeClientFactory(tmdb=client), api_key="   ")

    assert client.calls == 0
    assert status.steps[0].status is StepStatus.FAILED
    assert (status.api_key_present, status.verified) == (False, False)


@pytest.mark.asyncio
async def test_a_rejected_tmdb_key_is_a_failed_line_not_a_500(session: AsyncSession) -> None:
    await arrange(session)
    factory = FakeClientFactory(
        tmdb=FakeTmdbClient(error=AuthFailedError("GET /configuration: 401"))
    )

    status = await verify_tmdb(session, factory, api_key="0000000000000000000000000000dead")

    assert status.steps[0].status is StepStatus.FAILED
    assert status.steps[0].error == "GET /configuration: 401"
    # 測不過也存下來，使用者才能改一個字再按一次。
    assert (await read_settings(session, TmdbSettings)).api_key.endswith("dead")


async def _no_sleep(_seconds: float) -> None:
    """Prowlarr 重啟的輪詢在測試裡不真的等。"""
    return None


@pytest.mark.asyncio
async def test_a_prowlarr_that_never_comes_back_does_not_erase_the_site_results(
    session: AsyncSession,
) -> None:
    """設密碼會讓 Prowlarr 重啟。它沒回來時，前面那幾站已經加進去了——結果不能跟著消失。"""
    await arrange(session)
    client = FakeProwlarrClient()
    client.ping = _never_comes_back  # type: ignore[method-assign]
    factory = FakeClientFactory(prowlarr=client)

    status = await apply_default_indexers(session, factory, ["nyaasi", "mikan"], sleep=_no_sleep)

    by_step = {row.step: row.status for row in status.steps}
    assert by_step["nyaasi"] is StepStatus.OK
    assert by_step["mikan"] is StepStatus.OK
    assert by_step[PROWLARR_LOGIN_STEP] is StepStatus.FAILED


async def _never_comes_back() -> None:
    raise ServiceUnavailableError("connection refused")


@pytest.mark.asyncio
async def test_ten_failing_sites_do_not_let_the_wizard_move_on(session: AsyncSession) -> None:
    """一個站都沒接上就還沒做完。替 Prowlarr 介面設登入那一條不算——它與站無關。"""
    await arrange(session)
    every_site = dict.fromkeys(DEFAULT_INDEXERS, "Unable to connect to indexer.")
    factory = FakeClientFactory(prowlarr=FakeProwlarrClient(rejects=every_site))

    status = await apply_default_indexers(session, factory, DEFAULT_INDEXERS, sleep=_no_sleep)

    assert [row.status for row in status.steps if row.step in DEFAULT_INDEXERS] == [
        StepStatus.FAILED
    ] * 10
    assert [row.status for row in status.steps if row.step == PROWLARR_LOGIN_STEP] == [
        StepStatus.OK
    ]
    assert (await read_status(session)).current_step == STEP_INDEXER


@pytest.mark.asyncio
async def test_berth_never_adds_sites_to_an_existing_indexer(session: AsyncSession) -> None:
    """既有服務只做檢查（brief §16.4 的紅線）。UI 不給這顆按鈕，直接打 API 的也要被擋。"""
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeProwlarrClient(base_url="http://nas:9696")

    with pytest.raises(ValueError, match="existing service"):
        await apply_default_indexers(session, FakeClientFactory(prowlarr=client), ["nyaasi"])

    assert await client.indexers() == []


class _TmdbPressedMeanwhile(FakeProwlarrClient):
    """加第一個站的那幾秒裡，使用者在同一頁按了「測試 TMDB」（M2 票 15 的 e2e 抓到的）。

    真的 Prowlarr 逐站連線再加上重啟要一分鐘上下，而第 5、6 步在同一頁上，所以這不是假想。
    """

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__()
        self._engine = engine
        self._pressed = False

    async def add_indexer(self, definition: IndexerDefinition) -> ProwlarrIndexer:
        if not self._pressed:
            self._pressed = True
            async with create_session_factory(self._engine)() as other:
                await verify_tmdb(other, FakeClientFactory(), api_key=TMDB_API_KEY)
        return await super().add_indexer(definition)


class _SitesAddedMeanwhile(FakeTmdbClient):
    """反過來：TMDB 的測試還在路上時，加站那一輪先寫完了。"""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__()
        self._engine = engine

    async def configuration(self) -> TmdbConfiguration:
        async with create_session_factory(self._engine)() as other:
            factory = FakeClientFactory()
            await apply_default_indexers(other, factory, ["nyaasi"], sleep=_no_sleep)
        return await super().configuration()


@pytest.mark.asyncio
async def test_sites_being_added_do_not_erase_a_tmdb_check_made_meanwhile(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """兩支命令都是「讀、打網路、寫回」：後寫完的那一支不准把對方剛寫的那一半蓋回去。"""
    await arrange(session)
    factory = FakeClientFactory(prowlarr=_TmdbPressedMeanwhile(engine))

    await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)

    assert (await read_tmdb_status(session)).verified is True
    assert (await read_status(session)).current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_a_tmdb_check_does_not_erase_sites_added_meanwhile(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    await arrange(session)
    factory = FakeClientFactory(tmdb=_SitesAddedMeanwhile(engine))

    await verify_tmdb(session, factory, api_key=TMDB_API_KEY)

    status = await read_indexer_status(session, FakeClientFactory())
    assert [row.step for row in status.steps if row.status is StepStatus.OK][:1] == ["nyaasi"]
    assert (await read_status(session)).current_step == STEP_ROUTES
