"""精靈第 6–7 步的 services 命令（plan §9.3 第 6–7 步、§8.3、§8.4、票 08）。

驗的是票 08 的驗收條件：預設站逐站顯示成敗、重按不會重複新增、既有 Prowlarr 與任意
Torznab 各有測試；TMDB 那一半改由票 02b 定義——憑證使用者自備、必填，測得過才走得下去。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.indexer import IndexerResult
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.prowlarr import IndexerDefinition, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.tmdb import TmdbConfiguration
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torznab import TorznabCaps, TorznabSearchMode
from berth.adapters.torznab.fake import FakeTorznabClient
from berth.db import create_session_factory
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    CollectionType,
    ConnectionReason,
    HealthStatus,
    IndexerKind,
    JellyfinStep,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    SiteFailure,
    StepStatus,
)
from berth.models import (
    IndexerSettings,
    Route,
    SetupSettings,
    SetupStep,
    TmdbSettings,
)
from berth.services.commands import CommandMark, Effect, mark_of
from berth.services.indexer import (
    DEFAULT_INDEXERS,
    apply_default_indexers,
    connect_indexer,
    read_indexer_status,
    remove_indexer,
    search_indexers,
    set_interface_login,
    skip_indexers,
    verify_sites,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_COMPLETE, STEP_INDEXER, STEP_TMDB, read_status
from berth.services.steps import InterfaceLogin
from berth.services.tmdb import read_tmdb_status, verify_tmdb
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import chosen, own
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)

#: 泊位上填的 Prowlarr 介面登入（M4 票 07）。
SKIPPER = InterfaceLogin(username="skipper", password="harbour")

TORZNAB = "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api"

#: 這台 Prowlarr 連不出去的那幾個站，訊息取自 2026-09-08 的實測（brief §20.7）。
BLOCKED = {
    "1337x": "Unable to access 1337x.to, blocked by CloudFlare Protection.",
    "eztv": "Unable to access eztvx.to, blocked by CloudFlare Protection.",
}


async def arrange(
    session: AsyncSession,
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
) -> None:
    """把資料庫推到「Jellyfin、qBittorrent、媒體庫路徑都接好、輪到來源」的狀態。

    媒體庫路徑排在來源之前（票 06d），所以這裡要有一條綠的 Route，否則精靈停在第 5 步。
    """
    await own(session)
    setup = await read_settings(session, SetupSettings)
    setup.jellyfin.steps = [SetupStep(key=JellyfinStep.API_KEY.value, status=StepStatus.OK)]
    setup.qbittorrent.steps = [
        SetupStep(key=step.value, status=StepStatus.OK) for step in QbittorrentStep
    ]
    setup.choices = {
        ServiceKind.JELLYFIN: chosen(
            ServiceOrigin.EXISTING, "http://nas:8096", ConnectionReason.SETUP_COMPLETED
        ),
        ServiceKind.QBITTORRENT: chosen(ServiceOrigin.BUNDLED, "http://qbittorrent:8080"),
        ServiceKind.PROWLARR: chosen(
            origin,
            "http://prowlarr:9696" if origin is ServiceOrigin.BUNDLED else "http://nas:9696",
        ),
    }
    await write_settings(session, setup)
    settings = await read_settings(session, IndexerSettings)
    settings.api_key = "0" * 31 + "1"
    await write_settings(session, settings)
    session.add(
        Route(
            slug="tv",
            name="TV",
            jellyfin_library_id="item-tv",
            jellyfin_library_name="TV",
            collection_type=CollectionType.TVSHOWS,
            target_path="/data/library/tv",
            category="berth-tv",
            health_status=HealthStatus.OK,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_the_default_indexers_are_offered_with_their_real_names(
    session: AsyncSession,
) -> None:
    await arrange(session)
    factory = FakeClientFactory()

    status = await read_indexer_status(session, factory)

    recommended = [row for row in status.candidates if row.recommended]
    assert [row.definition_name for row in recommended] == list(DEFAULT_INDEXERS)
    assert [row.name for row in recommended][:3] == ["Nyaa.si", "dmhy", "Anime Tosho"]
    # 站名是伺服器自己報的，privacy 也是——勾選清單靠它標出唯一不是公開的那一個。
    assert [row.privacy for row in recommended if row.definition_name == "animetosho-xyz"] == [
        "semiPrivate"
    ]
    assert status.sites == ()


@pytest.mark.asyncio
async def test_applying_the_defaults_reports_every_site_on_its_own_line(
    session: AsyncSession,
) -> None:
    """公開站裡有幾個連不上是常態：失敗的那幾條變紅，其餘照樣繫上。"""
    await arrange(session)
    client = FakeProwlarrClient(rejects=BLOCKED)
    factory = FakeClientFactory(prowlarr=client)

    status = await apply_default_indexers(session, factory, DEFAULT_INDEXERS)

    by_step = {row.step: row for row in status.steps}
    assert by_step["nyaasi"].status is StepStatus.OK
    assert by_step["1337x"].status is StepStatus.FAILED
    assert by_step["1337x"].error == BLOCKED["1337x"]
    assert [row.definition_name for row in status.sites] == [
        name for name in DEFAULT_INDEXERS if name not in BLOCKED
    ]


@pytest.mark.asyncio
async def test_only_the_ticked_indexers_are_added(session: AsyncSession) -> None:
    await arrange(session)
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
    await arrange(session)
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
async def test_the_bundled_prowlarr_gets_the_login_typed_on_the_berth(
    session: AsyncSession,
) -> None:
    """泊位上的登入跟著「加入」送進來，替 Prowlarr 介面設 Forms 登入（brief §16.3、M4 票 07）。"""
    await arrange(session)
    client = FakeProwlarrClient()
    factory = FakeClientFactory(prowlarr=client)

    status = await apply_default_indexers(
        session, factory, ["nyaasi"], login=SKIPPER, sleep=_no_sleep
    )

    assert client.signs_in("skipper", "harbour")
    config = await client.host_config()
    assert config["authenticationMethod"] == "forms"
    assert client.restarts == 1
    assert [row.status for row in status.steps if row.step == PROWLARR_LOGIN_STEP] == [
        StepStatus.OK
    ]
    assert (status.web_ui_login, status.web_ui_username) == (True, "skipper")

    # 重按（帶同一組、或不帶）不會再設一次，也就不會再重啟一次。
    await apply_default_indexers(session, factory, ["nyaasi"], login=SKIPPER, sleep=_no_sleep)
    again = await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)
    assert client.restarts == 1
    assert [(row.status, row.detail) for row in again.steps if row.step == PROWLARR_LOGIN_STEP] == [
        (StepStatus.SKIPPED, "skipper")
    ]


@pytest.mark.asyncio
async def test_a_changed_prowlarr_login_replaces_the_old_one(session: AsyncSession) -> None:
    """設定頁改登入（M4 票 07）：舊的失效、新的有效，站不重驗。

    只改密碼也要重寫（票 06c）：Prowlarr 讀回來的密碼是雜湊，比的是 Berth 上次寫的那一組。
    """
    await arrange(session)
    client = FakeProwlarrClient()
    factory = FakeClientFactory(prowlarr=client)
    await apply_default_indexers(session, factory, ["nyaasi"], login=SKIPPER, sleep=_no_sleep)
    tested = list(client.tested)

    status = await set_interface_login(
        session, factory, InterfaceLogin(username="skipper", password="changed"), sleep=_no_sleep
    )

    assert client.signs_in("skipper", "changed")
    assert not client.signs_in("skipper", "harbour")
    assert client.restarts == 2
    assert client.tested == tested
    by_step = {row.step: row.status for row in status.steps}
    assert by_step[PROWLARR_LOGIN_STEP] is StepStatus.OK
    assert by_step["nyaasi"] is StepStatus.OK

    await set_interface_login(
        session, factory, InterfaceLogin(username="deckhand", password="changed"), sleep=_no_sleep
    )
    assert client.signs_in("deckhand", "changed")
    assert not client.signs_in("skipper", "changed")
    assert mark_of(set_interface_login) == CommandMark(Effect.REVERSIBLE)


@pytest.mark.asyncio
async def test_a_bundled_prowlarr_without_a_login_holds_the_wizard(
    session: AsyncSession,
) -> None:
    """兩格都必填（M4 票 07 shape）：站接上了，但介面登入那一條沒跑到，精靈不往下走。"""
    await arrange(session)
    client = FakeProwlarrClient()

    status = await apply_default_indexers(session, FakeClientFactory(prowlarr=client), ["nyaasi"])

    assert (await client.host_config())["authenticationMethod"] == "none"
    assert client.restarts == 0
    assert [row.status for row in status.steps if row.step == PROWLARR_LOGIN_STEP] == [
        StepStatus.PENDING
    ]
    assert (await read_status(session)).current_step == STEP_INDEXER


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
    """第 6 步可跳過，第 7 步不行（票 02b）。

    沒有索引站只是搜尋不到東西，Berth 其餘功能還在；沒有 TMDB 則探索、季集快照、命名
    全部停擺，所以第 7 步是閘門而不是「之後再說」。
    """
    await arrange(session)
    assert (await read_status(session)).current_step == STEP_INDEXER

    await skip_indexers(session, FakeClientFactory())
    assert (await read_status(session)).current_step == STEP_TMDB

    await verify_tmdb(session, FakeClientFactory(), api_key=TMDB_API_KEY)
    assert (await read_status(session)).current_step == STEP_COMPLETE


@pytest.mark.asyncio
async def test_a_rejected_credential_leaves_the_wizard_on_step_seven(session: AsyncSession) -> None:
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


@pytest.mark.asyncio
async def test_a_failing_key_does_not_replace_one_that_already_works(
    session: AsyncSession,
) -> None:
    """設定頁換 key（票 06i，使用者拍板）：已經驗過的那一把在用，新的測不過就不換掉它。

    先存再測只對「還沒有能用的 key」成立——那時存下來讓人改一個字再按；已經有一把能用的時候，
    貼錯一把就讓探索與入庫停擺，代價不對稱。
    """
    await arrange(session)
    working = FakeClientFactory(tmdb=FakeTmdbClient())
    await verify_tmdb(session, working, api_key=TMDB_API_KEY)
    rejecting = FakeClientFactory(
        tmdb=FakeTmdbClient(error=AuthFailedError("GET /configuration: 401"))
    )

    status = await verify_tmdb(session, rejecting, api_key="0000000000000000000000000000dead")

    # 這一次的結果照樣說出來……
    assert [(row.status, row.error) for row in status.steps] == [
        (StepStatus.FAILED, "GET /configuration: 401")
    ]
    # ……但舊的那一把照舊在用，閘門也還是綠的。
    assert status.verified is True
    assert (await read_settings(session, TmdbSettings)).api_key == TMDB_API_KEY
    assert (await read_tmdb_status(session)).verified is True


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

    status = await apply_default_indexers(
        session, factory, ["nyaasi", "mikan"], login=SKIPPER, sleep=_no_sleep
    )

    by_step = {row.step: row.status for row in status.steps}
    assert by_step["nyaasi"] is StepStatus.OK
    assert by_step["mikan"] is StepStatus.OK
    assert by_step[PROWLARR_LOGIN_STEP] is StepStatus.FAILED


async def _never_comes_back() -> None:
    raise ServiceUnavailableError("connection refused")


@pytest.mark.asyncio
async def test_every_site_failing_does_not_let_the_wizard_move_on(session: AsyncSession) -> None:
    """一個站都沒接上就還沒做完。替 Prowlarr 介面設登入那一條不算——它與站無關。"""
    await arrange(session)
    every_site = dict.fromkeys(DEFAULT_INDEXERS, "Unable to connect to indexer.")
    factory = FakeClientFactory(prowlarr=FakeProwlarrClient(rejects=every_site))

    status = await apply_default_indexers(
        session, factory, DEFAULT_INDEXERS, login=SKIPPER, sleep=_no_sleep
    )

    assert [row.status for row in status.steps if row.step in DEFAULT_INDEXERS] == [
        StepStatus.FAILED
    ] * len(DEFAULT_INDEXERS)
    assert [row.status for row in status.steps if row.step == PROWLARR_LOGIN_STEP] == [
        StepStatus.OK
    ]
    assert (await read_status(session)).current_step == STEP_INDEXER


@pytest.mark.asyncio
async def test_berth_never_adds_sites_to_an_existing_indexer(session: AsyncSession) -> None:
    """既有服務只做檢查（brief §16.4 的紅線）。UI 不給這顆按鈕，直接打 API 的也要被擋。"""
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeProwlarrClient(base_url="http://nas:9696")

    factory = FakeClientFactory(prowlarr=client)
    with pytest.raises(ValueError, match="existing service"):
        await apply_default_indexers(session, factory, ["nyaasi"])
    # 泊位上沒有介面登入那一格（M4 票 07）；直接打 API 帶了也一個字都不送。
    with pytest.raises(ValueError, match="existing service"):
        await set_interface_login(session, factory, SKIPPER, sleep=_no_sleep)

    assert await client.indexers() == []
    assert client.restarts == 0
    status = await read_indexer_status(session, factory)
    assert (status.web_ui_login, status.web_ui_username) == (False, "")


class _TmdbPressedMeanwhile(FakeProwlarrClient):
    """加第一個站的那幾秒裡，使用者在同一頁按了「測試 TMDB」（M2 票 15 的 e2e 抓到的）。

    真的 Prowlarr 逐站連線再加上重啟要一分鐘上下，而第 6、7 步在同一頁上，所以這不是假想。
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
            await apply_default_indexers(other, factory, ["nyaasi"], login=SKIPPER, sleep=_no_sleep)
        return await super().configuration()


@pytest.mark.asyncio
async def test_sites_being_added_do_not_erase_a_tmdb_check_made_meanwhile(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """兩支命令都是「讀、打網路、寫回」：後寫完的那一支不准把對方剛寫的那一半蓋回去。"""
    await arrange(session)
    factory = FakeClientFactory(prowlarr=_TmdbPressedMeanwhile(engine))

    await apply_default_indexers(session, factory, ["nyaasi"], login=SKIPPER, sleep=_no_sleep)

    assert (await read_tmdb_status(session)).verified is True
    assert (await read_status(session)).current_step == STEP_COMPLETE


@pytest.mark.asyncio
async def test_a_tmdb_check_does_not_erase_sites_added_meanwhile(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    await arrange(session)
    factory = FakeClientFactory(tmdb=_SitesAddedMeanwhile(engine))

    await verify_tmdb(session, factory, api_key=TMDB_API_KEY)

    status = await read_indexer_status(session, FakeClientFactory())
    assert [row.step for row in status.steps if row.status is StepStatus.OK][:1] == ["nyaasi"]
    assert (await read_status(session)).current_step == STEP_COMPLETE


# --- 票 06e：語言與說明、加入後試搜、逐站移除 ---


def _results(indexer: str, count: int) -> tuple[IndexerResult, ...]:
    return tuple(
        IndexerResult(title=f"{indexer} release {n}", indexer=indexer) for n in range(count)
    )


@pytest.mark.asyncio
async def test_anidex_is_not_offered_any_more(session: AsyncSession) -> None:
    """anidex.info 從 09-08 起一直回 502（2026-09-25 實測），預設清單不再勾它（票 06e）。"""
    await arrange(session)

    status = await read_indexer_status(session, FakeClientFactory())

    assert "Anidex" not in DEFAULT_INDEXERS
    assert len(DEFAULT_INDEXERS) == 9
    assert "Anidex" not in [row.definition_name for row in status.candidates if row.recommended]


@pytest.mark.asyncio
async def test_every_offered_site_says_its_language_and_what_it_is(session: AsyncSession) -> None:
    await arrange(session)

    status = await read_indexer_status(session, FakeClientFactory())

    by_name = {row.definition_name: row for row in status.candidates}
    assert (by_name["dmhy"].language, by_name["mikan"].language) == ("zh-TW", "zh-CN")
    assert by_name["yts"].description.startswith("YTS is a Public torrent site")


@pytest.mark.asyncio
async def test_a_trial_search_reports_each_site_on_its_own(session: AsyncSession) -> None:
    """加入之後試搜：逐站列出搜到幾筆與前三筆標題，一站失敗不影響其他站。"""
    await arrange(session)
    prowlarr = FakeProwlarrClient()
    search = FakeIndexerSearch(
        by_indexer={1: _results("Nyaa.si", 5), 2: ()},
        indexer_errors={3: ServiceUnavailableError("GET /api/v1/search: 502 Bad Gateway")},
    )
    factory = FakeClientFactory(prowlarr=prowlarr, indexer_search=search)
    added = await apply_default_indexers(session, factory, ["nyaasi", "dmhy", "mikan"])
    ids = {row.definition_name: row.indexer_id for row in added.sites}

    result = await search_indexers(session, factory, query="Frieren")

    by_name = {row.definition_name: row for row in result.sites}
    assert by_name["nyaasi"].indexer_id == ids["nyaasi"]
    assert by_name["nyaasi"].count == 5
    assert by_name["nyaasi"].titles == (
        "Nyaa.si release 0",
        "Nyaa.si release 1",
        "Nyaa.si release 2",
    )
    assert (by_name["dmhy"].count, by_name["dmhy"].error) == (0, "")
    assert by_name["mikan"].error.endswith("502 Bad Gateway")
    assert by_name["mikan"].count == 0
    # 一站一個查詢，每個都只問那一站。
    assert sorted(query.indexer_ids for query in search.queries) == [(1,), (2,), (3,)]
    assert {query.text for query in search.queries} == {"Frieren"}


@pytest.mark.asyncio
async def test_a_trial_search_writes_nothing(session: AsyncSession) -> None:
    """試搜是 `read` 命令（票 05 的標記）：它不寫任何東西，所以也不會讓精靈前進或後退。"""
    await arrange(session)
    factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=_results("x", 1)))
    await apply_default_indexers(session, factory, ["nyaasi"])
    before = (await read_settings(session, SetupSettings)).model_dump()

    await search_indexers(session, factory, query="")

    assert (await read_settings(session, SetupSettings)).model_dump() == before
    assert mark_of(search_indexers) == CommandMark(Effect.READ)


@pytest.mark.asyncio
async def test_an_existing_torznab_endpoint_is_searched_on_its_own_endpoint(
    session: AsyncSession,
) -> None:
    """既有 Torznab 同樣可以試搜：打它自己的 `t=search`，整個端點算一站。"""
    await arrange(session, origin=ServiceOrigin.EXISTING)
    search = FakeIndexerSearch(results=_results("Jackett", 2))
    factory = FakeClientFactory(indexer_search=search)
    await connect_indexer(
        session, factory, kind=IndexerKind.TORZNAB, base_url=TORZNAB, api_key="the-key"
    )

    result = await search_indexers(session, factory, query="Frieren")

    assert [(row.name, row.count, row.indexer_id) for row in result.sites] == [
        ("jackett:9117", 2, None)
    ]
    assert factory.indexer_kinds[-1] is IndexerKind.TORZNAB
    assert search.base_url == TORZNAB


@pytest.mark.asyncio
async def test_a_trial_search_that_cannot_list_the_sites_says_so(session: AsyncSession) -> None:
    await arrange(session)
    prowlarr = FakeProwlarrClient(indexers_error=ServiceUnavailableError("connection refused"))

    result = await search_indexers(session, FakeClientFactory(prowlarr=prowlarr), query="x")

    assert result.sites == ()
    assert result.error == "connection refused"


@pytest.mark.asyncio
async def test_a_removed_site_is_gone_and_no_longer_searched(session: AsyncSession) -> None:
    """每一站可以移除（Prowlarr `DELETE /api/v1/indexer/{id}`）；移除後試搜不再打它。"""
    await arrange(session)
    prowlarr = FakeProwlarrClient()
    search = FakeIndexerSearch()
    factory = FakeClientFactory(prowlarr=prowlarr, indexer_search=search)
    added = await apply_default_indexers(session, factory, ["nyaasi", "yts"])
    yts = next(row.indexer_id for row in added.sites if row.definition_name == "yts")

    status = await remove_indexer(session, factory, yts)

    assert prowlarr.deleted == [yts]
    assert [row.definition_name for row in status.sites] == ["nyaasi"]
    # 那一站的「加入結果」一起拿掉：留著一條綠的「YTS」等於說它還在。
    assert [row.step for row in status.steps] == ["nyaasi", PROWLARR_LOGIN_STEP]
    await search_indexers(session, factory, query="")
    assert [query.indexer_ids for query in search.queries] == [(1,)]
    assert mark_of(remove_indexer) == CommandMark(
        Effect.REVERSIBLE, inverse="indexer.apply_default_indexers"
    )


@pytest.mark.asyncio
async def test_removing_the_last_site_sends_the_wizard_back_to_the_indexers(
    session: AsyncSession,
) -> None:
    await arrange(session)
    factory = FakeClientFactory()
    added = await apply_default_indexers(
        session, factory, ["nyaasi"], login=SKIPPER, sleep=_no_sleep
    )
    assert (await read_status(session)).current_step == STEP_TMDB
    (only,) = [row.indexer_id for row in added.sites]

    await remove_indexer(session, factory, only)

    assert (await read_status(session)).current_step == STEP_INDEXER


@pytest.mark.asyncio
async def test_berth_never_removes_sites_from_an_existing_indexer(session: AsyncSession) -> None:
    """既有服務只做檢查（brief §16.4 的紅線），移除也一樣。"""
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeProwlarrClient(
        base_url="http://nas:9696",
        indexers=[ProwlarrIndexer(id=4, name="dmhy", enabled=True, definition_name="dmhy")],
    )

    with pytest.raises(ValueError, match="existing service"):
        await remove_indexer(session, FakeClientFactory(prowlarr=client), 4)

    assert client.deleted == []


@pytest.mark.asyncio
async def test_a_site_the_user_added_in_prowlarr_is_not_removed(session: AsyncSession) -> None:
    """只移除 Berth 提供的預設站：使用者自己加的（可能是帶帳號的私站）Berth 加不回去。"""
    await arrange(session)
    client = FakeProwlarrClient(
        indexers=[ProwlarrIndexer(id=7, name="MyTracker", enabled=True, definition_name="private")]
    )

    with pytest.raises(ValueError, match="Berth only removes"):
        await remove_indexer(session, FakeClientFactory(prowlarr=client), 7)

    assert client.deleted == []


# --- M4 票 09：先測再勾、全部公開站、已加入的站 ---


@pytest.mark.asyncio
async def test_the_other_public_torrent_sites_follow_the_recommended_ones(
    session: AsyncSession,
) -> None:
    """推薦清單之外是 schema 裡 privacy = public 的 torrent 站，依名稱排
    （`.scratch/m4/indexer-berth-shape.md`）。

    usenet 的公開站（NZBIndex）Berth 接不了；私站要帳號，連到 Prowlarr 自己加。同一個
    `definitionName` 出現兩次（`Torrent RSS Feed` 與它的 preset showRSS）只列第一個——Berth
    認站靠的就是它。
    """
    await arrange(session)

    status = await read_indexer_status(session, FakeClientFactory())

    others = [row.definition_name for row in status.candidates if not row.recommended]
    assert others == ["Anidex", "Knaben", "rutor", "Torrent RSS Feed", "tokyotosho"]
    assert [row.name for row in status.candidates if row.definition_name == "rutor"] == ["RuTor"]
    assert [row.language for row in status.candidates if row.definition_name == "rutor"] == [
        "ru-RU"
    ]


@pytest.mark.asyncio
async def test_an_added_site_moves_from_the_candidates_to_the_sites(session: AsyncSession) -> None:
    await arrange(session)
    factory = FakeClientFactory()

    status = await apply_default_indexers(session, factory, ["dmhy", "Knaben"])

    assert [(row.definition_name, row.language) for row in status.sites] == [
        ("dmhy", "zh-TW"),
        ("Knaben", "en-US"),
    ]
    assert {"dmhy", "Knaben"}.isdisjoint(row.definition_name for row in status.candidates)
    # 兩站都是 Berth 加得回去的（推薦清單、公開 torrent 站），所以都可以從 Berth 移除。
    assert [row.removable for row in status.sites] == [True, True]


@pytest.mark.asyncio
async def test_a_site_is_tested_before_it_is_added(session: AsyncSession) -> None:
    """`indexer/test` 收還沒加入的定義（brief §20.7）：逐站通不通、理由分成幾種，什麼都不建立。"""
    await arrange(session)
    client = FakeProwlarrClient(rejects=BLOCKED)
    factory = FakeClientFactory(prowlarr=client)
    before = (await read_settings(session, SetupSettings)).model_dump()

    checks = await verify_sites(session, factory, ["yts", "1337x"])

    assert [(row.definition_name, row.passed, row.reason) for row in checks] == [
        ("yts", True, None),
        ("1337x", False, SiteFailure.CLOUDFLARE),
    ]
    assert checks[1].detail == BLOCKED["1337x"]
    assert await client.indexers() == []
    assert (await read_settings(session, SetupSettings)).model_dump() == before
    assert mark_of(verify_sites) == CommandMark(Effect.READ)


@pytest.mark.asyncio
async def test_a_site_that_needs_an_account_is_neither_tested_nor_added(
    session: AsyncSession,
) -> None:
    """私站與 usenet 站不在 Berth 加得了的範圍：測試與加入都回「沒通過」，一個請求都不送。"""
    await arrange(session)
    client = FakeProwlarrClient()
    factory = FakeClientFactory(prowlarr=client)

    checks = await verify_sites(session, factory, ["AnimeBytes", "NZBIndex", "nope"])
    status = await apply_default_indexers(session, factory, ["AnimeBytes"])

    assert [(row.passed, row.reason) for row in checks] == [(False, SiteFailure.OTHER)] * 3
    assert client.tested == []
    assert await client.indexers() == []
    assert [(row.step, row.status) for row in status.steps][:1] == [
        ("AnimeBytes", StepStatus.FAILED)
    ]


@pytest.mark.asyncio
async def test_berth_does_not_test_sites_for_an_existing_indexer(session: AsyncSession) -> None:
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeProwlarrClient(base_url="http://nas:9696")

    with pytest.raises(ValueError, match="existing service"):
        await verify_sites(session, FakeClientFactory(prowlarr=client), ["yts"])

    assert client.tested == []


@pytest.mark.asyncio
async def test_what_the_last_apply_said_about_each_site_is_kept_with_a_reason(
    session: AsyncSession,
) -> None:
    """勾了的站在加入時仍可能加不進去（Prowlarr 加之前自己再連一次）：那一站的理由與測試同一套。"""
    await arrange(session)
    factory = FakeClientFactory(prowlarr=FakeProwlarrClient(rejects=BLOCKED))

    status = await apply_default_indexers(session, factory, ["yts", "eztv"])

    assert [(row.definition_name, row.passed, row.reason) for row in status.checks] == [
        ("yts", True, None),
        ("eztv", False, SiteFailure.CLOUDFLARE),
    ]
    again = await read_indexer_status(session, factory)
    assert again.checks == status.checks


@pytest.mark.asyncio
async def test_an_existing_prowlarr_lists_its_own_sites_and_none_to_add(
    session: AsyncSession,
) -> None:
    """既有 Prowlarr：列出它已有的站與站數，沒有可加的站，也沒有一站可以從 Berth 移除（票 05）。"""
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeProwlarrClient(
        base_url="http://nas:9696",
        indexers=[
            ProwlarrIndexer(4, "dmhy", True, "dmhy", privacy="public", language="zh-TW"),
            ProwlarrIndexer(9, "MyTracker", True, "private", privacy="private"),
        ],
    )
    factory = FakeClientFactory(prowlarr=client)
    await connect_indexer(
        session, factory, kind=IndexerKind.PROWLARR, base_url="http://nas:9696", api_key="k"
    )

    status = await read_indexer_status(session, factory)

    assert [(row.indexer_id, row.name, row.removable) for row in status.sites] == [
        (4, "dmhy", False),
        (9, "MyTracker", False),
    ]
    assert status.candidates == ()


@pytest.mark.asyncio
async def test_a_single_site_can_be_searched_on_its_own(session: AsyncSession) -> None:
    """每一列一顆「搜尋」：只問那一站（`indexerIds` 只帶它）。"""
    await arrange(session)
    search = FakeIndexerSearch(by_indexer={1: _results("Nyaa.si", 2), 2: _results("dmhy", 4)})
    factory = FakeClientFactory(indexer_search=search)
    await apply_default_indexers(session, factory, ["nyaasi", "dmhy"])

    result = await search_indexers(session, factory, query="Frieren", indexer_id=2)

    assert [(row.definition_name, row.count) for row in result.sites] == [("dmhy", 4)]
    assert [query.indexer_ids for query in search.queries] == [(2,)]


@pytest.mark.asyncio
async def test_a_public_site_the_user_added_in_prowlarr_can_be_removed(
    session: AsyncSession,
) -> None:
    """Berth 加得回去的站（公開的 torrent 站）都可以從 Berth 移除，不論是誰加的：反向命令成立。"""
    await arrange(session)
    client = FakeProwlarrClient(
        indexers=[
            ProwlarrIndexer(5, "Knaben", True, "Knaben", privacy="public", protocol="torrent")
        ]
    )
    factory = FakeClientFactory(prowlarr=client)

    status = await remove_indexer(session, factory, 5)

    assert client.deleted == [5]
    assert status.sites == ()
