"""精靈第 6 步：索引站（plan §9.3 第 6 步、§8.4、brief §16.3）。

兩條路徑，同一份狀態形狀（`SetupIndexer`）：

- **套件內 Prowlarr**：推薦清單與 schema 裡其他公開的 torrent 站（`candidates`），**先測再加**
  （M4 票 09）：`verify_sites` 以 `indexer/test` 測還沒加入的定義，通過的才勾得起來；加入是
  `indexer` 新增，逐站顯示成敗。泊位上填的介面登入跟著送進來，替 Prowlarr 介面設 Forms 登入
  （M4 票 07）；設定頁改它走 `set_interface_login`。
- **既有**：Prowlarr 位址 + API key，或任意 Torznab 端點 + key，各有一顆「測試」。Berth 列出它已有的
  站、可以試搜，不加、不測、不移除（票 05）。

**逐站的成敗來自新增那一支**：`POST /api/v1/indexer` 會先連一次那個站，連不上就回 400 而且
什麼都不建立（2026-09-08 實測，brief §20.7）。已經加過的站不重加——同名會被拒（`Should be
unique`），所以重按時改成 `indexer/test`，結果一樣是「這個站現在通不通」。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.indexer import IndexerSearch, SearchQuery
from berth.adapters.prowlarr import (
    IndexerDefinition,
    IndexerRejectedError,
    ProwlarrClient,
    ProwlarrIndexer,
    failure_of,
    unsupported_message,
)
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    ConnectionReason,
    ConnectionState,
    IndexerKind,
    ServiceKind,
    ServiceOrigin,
    SiteFailure,
    StepStatus,
)
from berth.models import IndexerSettings, ServiceChoice, ServiceTest, SetupSettings, SetupStep
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.jellyfin import resolve_interface_login
from berth.services.settings import read_settings, update_settings, write_settings
from berth.services.steps import (
    InterfaceLogin,
    StepView,
    hash_password,
    message,
    password_matches,
    step_views,
)

#: 推薦的九個站（plan §9.3 頁 4、brief §16.3），預設不勾、先測再勾（M4 票 09）。值是 Prowlarr 的
#: `definitionName`：
#: 顯示用的站名 Prowlarr 自己會改，機器名不會。原本有第十個 `Anidex`：它的定義還在，但
#: anidex.info 從 2026-09-08 起每一次都回 502（brief §20.7），預設勾它只是多一條紅線（票 06e）。
DEFAULT_INDEXERS: tuple[str, ...] = (
    "nyaasi",
    "dmhy",
    "animetosho-xyz",
    "acgrip",
    "mikan",
    "1337x",
    "yts",
    "eztv",
    "thepiratebay",
)

#: 一次「測試全部」同時連幾站。每一站是 Prowlarr 現場去連那個站（實測 1–2 秒，連不上的等到逾時），
#: 一次放八十幾個出去只是讓它們一起逾時。
VERIFY_CONCURRENCY = 4

#: Prowlarr 設了 Forms 登入之後會自行重啟；等它回來的輪詢（brief §20.7）。
RESTART_ATTEMPTS = 60
POLL_SECONDS = 2.0

Sleeper = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class IndexerSite:
    """Prowlarr 裡已經有的一站（M4 票 09 的「已加入」）。

    Berth 加的、使用者在 Prowlarr 自己加的都算。
    """

    indexer_id: int
    definition_name: str
    name: str
    enabled: bool
    #: BCP 47 代碼與一句英文說明，取自這台伺服器自己的定義（票 06e）。
    language: str
    description: str
    privacy: str
    #: 可以從 Berth 移除：套件內，而且是 Berth 加得回去的站（`_offered`），反向命令才成立。
    removable: bool


@dataclass(frozen=True, slots=True)
class IndexerCandidate:
    """還沒加入、Berth 加得了的一站（M4 票 09 的「加站」）。"""

    definition_name: str
    name: str
    privacy: str
    language: str
    description: str
    #: 推薦清單上的（排最前、順序照 `DEFAULT_INDEXERS`）；其餘是 schema 裡其他公開的 torrent 站。
    recommended: bool


@dataclass(frozen=True, slots=True)
class SiteCheck:
    """一站通不通（M4 票 09）：「測試」的回答，也是上一次「加入」對那一站的結論。"""

    definition_name: str
    passed: bool
    #: 沒通過時是哪一種（Prowlarr 原文分出來的）；通過是 `None`。
    reason: SiteFailure | None
    #: Prowlarr 的原文（英文），畫面收在可展開的區塊裡。
    detail: str


@dataclass(frozen=True, slots=True)
class IndexerSetupStatus:
    """`GET /api/setup/indexers` 與兩顆按鈕的整份形狀。"""

    #: 使用者在頁 4 選的來源；還沒選是 `None`。Torznab 端點一律是既有。
    origin: ServiceOrigin | None
    kind: IndexerKind
    base_url: str
    api_key_present: bool
    #: 連得上那台 Prowlarr（套件內路徑才有意義）。
    reachable: bool
    #: Prowlarr 裡已經有的站（套件內與既有 Prowlarr；Torznab 端點沒有站的清單）。
    sites: tuple[IndexerSite, ...]
    #: 還沒加入、Berth 加得了的站。只有套件內。
    candidates: tuple[IndexerCandidate, ...]
    #: 上一次「加入」對每一站的結論（從 `steps` 導出，理由分好了）。
    checks: tuple[SiteCheck, ...]
    steps: tuple[StepView, ...]
    skipped: bool
    #: 泊位上有介面登入那一格：只有套件內的 Prowlarr（M4 票 07）。
    web_ui_login: bool
    #: 套件內 Prowlarr 的介面帳號：Berth 設下的，或那一台自己就設過的。還沒設過、或是既有的那一台
    #: 是空字串。
    web_ui_username: str
    error: str
    #: 上一次連線測試的理由（服務頁與頁 4 的既有表單寫的同一份）；還沒測過是 `None`。
    #: 既有表單照它選補法：版本太舊時叫人升級，不叫人改位址（M4 票 17）。
    reason: ConnectionReason | None = None


@dataclass(frozen=True, slots=True)
class SiteSearch:
    """試搜的一站（票 06e）：搜到幾筆、前三筆叫什麼，或那一站為什麼搜不了。"""

    #: Prowlarr 上的 id。單一 Torznab 端點整個算一站，沒有 id。
    indexer_id: int | None
    definition_name: str
    name: str
    count: int
    titles: tuple[str, ...]
    #: 那一站失敗時服務回的原文（英文）。成功而搜不到東西是 `count == 0` 加空字串。
    error: str


@dataclass(frozen=True, slots=True)
class IndexerSearchResult:
    query: str
    sites: tuple[SiteSearch, ...]
    #: 連要問哪幾站都列不出來（Prowlarr 連不上）。逐站的失敗在 `sites` 裡，不在這裡。
    error: str


#: 試搜每一站列出的標題數。三筆夠認出「這個站搜得到我要的那種東西」，多了只是把畫面拉長。
TRIAL_TITLES = 3


@command(Effect.READ)
async def read_indexer_status(
    session: AsyncSession, factory: ServiceClientFactory
) -> IndexerSetupStatus:
    """套件內列出已加入的站與加得了的站；既有 Prowlarr 只列它已有的站；Torznab 只回連線資訊。

    **只讀**：進這一頁（精靈與設定頁）只發這一支，不測任何一站（M4 票 09）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    origin, base_url = _target(setup, settings)
    if origin is None or settings.kind == IndexerKind.TORZNAB.value:
        return _view(setup, settings, origin, base_url)

    bundled = origin is ServiceOrigin.BUNDLED
    client = factory.prowlarr(base_url, settings.api_key)
    try:
        present = await client.indexers()
        if not bundled:
            # 既有的那一台：列出來、可以試搜，就這樣（票 05）。連不上照舊由測試那一條說。
            return _view(setup, settings, origin, base_url, sites=_sites(present, bundled=False))
        candidates = _candidates(await client.definitions(), present)
        instance = _instance_username(await client.host_config())
    except ServiceError as exc:
        return _view(setup, settings, origin, base_url, reachable=not bundled, error=message(exc))
    finally:
        await client.aclose()

    return _view(
        setup,
        settings,
        origin,
        base_url,
        sites=_sites(present, bundled=True),
        candidates=candidates,
        instance_username=instance,
    )


@command(Effect.READ)
async def verify_sites(
    session: AsyncSession, factory: ServiceClientFactory, names: Sequence[str]
) -> tuple[SiteCheck, ...]:
    """「測試」：逐站問 Prowlarr 通不通，**什麼都不建立、什麼都不寫**（M4 票 09）。

    `indexer/test` 也收還沒加入的定義（2026-09-30 實測，brief §20.7）：送的是 schema 的原樣。
    測的是「加站」那一段的候選，所以一律測定義；Berth 加不了的（私站、usenet、這台沒有的定義）
    直接回沒通過，一個請求都不送。只有套件內：既有的那一台 Berth 不加站，也就沒有要測的（票 05）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    origin, base_url = _target(setup, settings)
    _refuse_existing(origin)

    client = factory.prowlarr(base_url, settings.api_key)
    gate = asyncio.Semaphore(VERIFY_CONCURRENCY)

    async def verify(name: str, definitions: Mapping[str, IndexerDefinition]) -> SiteCheck:
        definition = definitions.get(name)
        if definition is None or not _offered(definition):
            return _refused(name)
        async with gate:
            try:
                await client.test_definition(definition)
            except IndexerRejectedError as exc:
                return _failed(name, exc.messages)
        return _passed(name)

    try:
        definitions = _by_definition(await client.definitions())
        return tuple(await asyncio.gather(*(verify(name, definitions) for name in names)))
    finally:
        await client.aclose()


# 沒有單一反向命令：一次加好幾站、還可能設了 Prowlarr 的介面登入，
# `remove_indexer` 一次只撤得掉一站。
@command(Effect.REVERSIBLE)
async def apply_default_indexers(
    session: AsyncSession,
    factory: ServiceClientFactory,
    selected: Sequence[str],
    *,
    login: InterfaceLogin | None = None,
    sleep: Sleeper = asyncio.sleep,
) -> IndexerSetupStatus:
    """勾起來的站逐個加進套件內的 Prowlarr（plan §9.3 頁 4）。

    勾得起來的是測試通過的站（M4 票 09，前端擋）；Prowlarr 加之前自己會再連一次，所以這裡照樣
    逐站記成敗。Berth 加不了的定義（私站、usenet）是 `failed`，不送。

    一站一條纜繩：新增成功 `ok`、已經在了就改用 `indexer/test` 驗一次（通過是 `skipped`），
    連不上是 `failed` 加上 Prowlarr 回的原文。整批不會因為一個站失敗就停下來——公開站裡
    有幾個連不上是常態。

    `login` 是泊位上填的介面登入（M4 票 07）；不帶就是登入照舊（設定頁加站不帶）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    origin, base_url = _target(setup, settings)
    if origin is not ServiceOrigin.BUNDLED:
        # 既有的索引站是使用者自己的，Berth 只做檢查（brief §16.4 的紅線）。UI 在這個狀態下
        # 根本不給這顆按鈕，所以走到這裡的只有直接打 API 的人。
        raise ValueError("this indexer is an existing service; Berth does not add sites to it")
    if login is not None:
        # 沿用 Jellyfin 帳密要先過 Jellyfin 那一關：在加站與寫登入之前（M4 票 15）。
        login = await resolve_interface_login(session, factory, login)

    client = factory.prowlarr(base_url, settings.api_key)
    steps: list[SetupStep] = []
    try:
        definitions = _by_definition(await client.definitions())
        existing = {row.definition_name: row for row in await client.indexers()}
        for name in selected:
            steps.append(await _ensure_indexer(client, name, definitions, existing))
        instance = _instance_username(await client.host_config())
        steps.append(await _apply_password(client, setup, origin, login, instance, sleep=sleep))
    except ServiceError as exc:
        return _view(setup, settings, origin, base_url, reachable=False, error=message(exc))
    finally:
        await client.aclose()

    settings.kind = IndexerKind.PROWLARR.value
    settings.base_url = base_url
    await write_settings(session, settings)

    def record(latest: SetupSettings) -> None:
        latest.indexer.steps = steps
        latest.indexer.skipped = False
        _record_login(latest, steps[-1], login, instance)

    # 逐站加完要一分鐘上下，這段時間裡第 7 步可能已經寫進同一組設定（M2 票 15）。
    await update_settings(session, SetupSettings, record)
    return await read_indexer_status(session, factory)


@command(Effect.REVERSIBLE)
async def connect_indexer(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    kind: IndexerKind,
    base_url: str,
    api_key: str,
) -> IndexerSetupStatus:
    """既有路徑的「測試」：先存再測，測不過也存（與服務頁的連線表單同一個規矩）。

    **這就是選了「既有」**（M4 票 15）：頁 4 與設定頁的既有表單走這一支，Torznab 端點
    （Jackett）也是。
    選擇記成既有，Berth 從此不替它加站、不設它的登入（票 05）。
    """
    settings = await read_settings(session, IndexerSettings)
    settings.kind = kind.value
    settings.base_url = base_url
    settings.api_key = api_key
    await write_settings(session, settings)

    probe = await probe_indexer(factory, kind, base_url, api_key)
    step = probe.step
    moment = utcnow()

    def record(latest: SetupSettings) -> None:
        previous = latest.choices.get(ServiceKind.PROWLARR)
        if previous is not None and (previous.origin, previous.base_url) != (
            ServiceOrigin.EXISTING,
            base_url,
        ):
            # 換了一台：原本那一台的介面登入紀錄說的不是它（`setup._start_over` 同一條）。
            latest.indexer.web_ui_username = ""
            latest.indexer.web_ui_password_hash = ""
        latest.indexer.steps = [step]
        latest.indexer.skipped = False
        latest.choices = {
            **latest.choices,
            ServiceKind.PROWLARR: ServiceChoice(
                origin=ServiceOrigin.EXISTING,
                base_url=base_url,
                test=ServiceTest(
                    state=ConnectionState.OK
                    if step.status is StepStatus.OK
                    else ConnectionState.FAILED,
                    reason=probe.reason,
                    detail=step.detail,
                    checked_at=moment,
                ),
            ),
        }

    # 測試在路上的那幾秒裡，TMDB 頁可能已經寫進同一組設定（M2 票 15）。
    await update_settings(session, SetupSettings, record)
    return await read_indexer_status(session, factory)


@command(Effect.REVERSIBLE, inverse="indexer.skip_indexers")
async def skip_indexers(
    session: AsyncSession, factory: ServiceClientFactory, *, skipped: bool = True
) -> IndexerSetupStatus:
    """「之後再說」。完成頁會列出跳過了什麼、在哪裡補（plan §9.3）。"""
    setup = await read_settings(session, SetupSettings)
    setup.indexer.skipped = skipped
    await write_settings(session, setup)
    await session.commit()
    return await read_indexer_status(session, factory)


@command(Effect.READ)
async def search_indexers(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    query: str,
    indexer_id: int | None = None,
) -> IndexerSearchResult:
    """加入之後的試搜（票 06e）：逐站問一次，列出搜到幾筆與前三筆標題。

    **逐站各發一個查詢**（`indexerIds` 只帶那一站）而不是一次問全部：聚合的回應只有結果，
    哪一站失敗了看不出來，而「一站失敗不影響其他站」正是這一頁要說的事。查詢併發——
    Prowlarr 現場去連每一個站，一個接一個問要好幾分鐘（brief §20.7）。

    空白的查詢也是一個問題：Prowlarr 與 Torznab 都回各站最新的發佈（2026-09-25 實測 dmhy
    80 筆、YTS 96 筆，約 1.3 秒），證明那個站回得出東西，不必先想一個標題。
    **不寫任何東西**：它是 `read` 命令，精靈的步驟不因它前進或後退。

    `indexer_id` 是那一列的「搜尋」（M4 票 09）：只問那一站。不帶是「搜尋全部」。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    kind = IndexerKind(settings.kind)
    _, base_url = _target(setup, settings)
    search = factory.indexer_search(kind, base_url, settings.api_key)
    try:
        if kind is IndexerKind.TORZNAB:
            site = await _search_site(search, query, None, "", urlsplit(base_url).netloc)
            return IndexerSearchResult(query=query, sites=(site,), error="")

        client = factory.prowlarr(base_url, settings.api_key)
        try:
            indexers = [
                row
                for row in await client.indexers()
                if row.enabled and indexer_id in (None, row.id)
            ]
        except ServiceError as exc:
            return IndexerSearchResult(query=query, sites=(), error=message(exc))
        finally:
            await client.aclose()
        sites = await asyncio.gather(
            *(
                _search_site(search, query, row.id, row.definition_name, row.name)
                for row in indexers
            )
        )
    finally:
        await search.aclose()
    return IndexerSearchResult(query=query, sites=tuple(sites), error="")


@command(Effect.REVERSIBLE, inverse="indexer.apply_default_indexers")
async def remove_indexer(
    session: AsyncSession, factory: ServiceClientFactory, indexer_id: int
) -> IndexerSetupStatus:
    """從套件內的 Prowlarr 移除一站（`DELETE /api/v1/indexer/{id}`，票 06e）。

    **只移除 Berth 加得回去的站**（推薦清單與公開的 torrent 站，`_offered`）：反向命令是再加一次
    那一站，公開站加回來就是原樣；私站帶帳號，Berth 加不回去，所以不碰——不論是誰加的（M4 票 09）。
    那一站的「加入結果」一起拿掉——留著一條綠的等於說它還在；最後一站也移除時，精靈就回到頁 4
    （`_indexer_settled`）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    origin, base_url = _target(setup, settings)
    if origin is not ServiceOrigin.BUNDLED:
        # 與 `apply_default_indexers` 同一條紅線：既有的索引站是使用者自己的（brief §16.4）。
        raise ValueError("this indexer is an existing service; Berth does not remove its sites")

    client = factory.prowlarr(base_url, settings.api_key)
    try:
        gone = next((row for row in await client.indexers() if row.id == indexer_id), None)
        if gone is not None and not _offered(gone):
            raise ValueError(f"{gone.name}: Berth only removes the public sites it can add back")
        if gone is not None:
            await client.delete_indexer(indexer_id)
    finally:
        await client.aclose()

    if gone is not None:
        removed = gone.definition_name

        def record(latest: SetupSettings) -> None:
            latest.indexer.steps = [row for row in latest.indexer.steps if row.key != removed]

        await update_settings(session, SetupSettings, record)
    return await read_indexer_status(session, factory)


async def _search_site(
    search: IndexerSearch,
    query: str,
    indexer_id: int | None,
    definition_name: str,
    name: str,
) -> SiteSearch:
    ids = (indexer_id,) if indexer_id is not None else ()
    try:
        results = await search.search(SearchQuery(text=query, indexer_ids=ids))
    except ServiceError as exc:
        return SiteSearch(indexer_id, definition_name, name, 0, (), message(exc))
    titles = tuple(row.title for row in results[:TRIAL_TITLES])
    return SiteSearch(indexer_id, definition_name, name, len(results), titles, "")


async def _ensure_indexer(
    client: ProwlarrClient,
    definition_name: str,
    definitions: dict[str, IndexerDefinition],
    existing: dict[str, ProwlarrIndexer],
) -> SetupStep:
    definition = definitions.get(definition_name)
    already = existing.get(definition_name)
    if already is None and (definition is None or not _offered(definition)):
        return SetupStep(
            key=definition_name, status=StepStatus.FAILED, error=_refused(definition_name).detail
        )

    # `detail` 留空：站名已經是這一條纜繩的標題，重複一次只是噪音。
    try:
        if already is not None:
            # 已經在了：同名再加一次會被拒，所以改成驗一次它現在通不通。
            await client.test_indexer(already)
            return SetupStep(key=definition_name, status=StepStatus.SKIPPED)
        assert definition is not None
        await client.add_indexer(definition)
    except IndexerRejectedError as exc:
        return SetupStep(
            key=definition_name, status=StepStatus.FAILED, error=" · ".join(exc.messages)
        )
    return SetupStep(key=definition_name, status=StepStatus.OK)


@command(Effect.REVERSIBLE)
async def set_interface_login(
    session: AsyncSession,
    factory: ServiceClientFactory,
    login: InterfaceLogin,
    *,
    sleep: Sleeper = asyncio.sleep,
) -> IndexerSetupStatus:
    """設定頁的「更新登入」（M4 票 07）：只換套件內 Prowlarr 的介面登入，站不重驗。

    與第 6 步的登入那一條是同一段（`_apply_password`），結果換掉那一條纜繩。可逆的方式就是
    再設一組。既有的索引站拒絕（`ValueError`）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    origin, base_url = _target(setup, settings)
    _refuse_existing(origin)
    login = await resolve_interface_login(session, factory, login)

    client = factory.prowlarr(base_url, settings.api_key)
    try:
        instance = _instance_username(await client.host_config())
        step = await _apply_password(client, setup, origin, login, instance, sleep=sleep)
    except ServiceError as exc:
        step = SetupStep(key=PROWLARR_LOGIN_STEP, status=StepStatus.FAILED, error=message(exc))
        instance = ""
    finally:
        await client.aclose()

    def record(latest: SetupSettings) -> None:
        latest.indexer.steps = [
            *(row for row in latest.indexer.steps if row.key != PROWLARR_LOGIN_STEP),
            step,
        ]
        _record_login(latest, step, login, instance)

    await update_settings(session, SetupSettings, record)
    return await read_indexer_status(session, factory)


def _refuse_existing(origin: ServiceOrigin | None) -> None:
    if origin is not ServiceOrigin.BUNDLED:
        # 既有的索引站是使用者自己的，Berth 只做檢查（brief §16.4 的紅線）。UI 在這個狀態下
        # 根本不給這顆按鈕，所以走到這裡的只有直接打 API 的人。
        raise ValueError("this indexer is an existing service; Berth does not change it")


def _record_login(
    setup: SetupSettings, step: SetupStep, login: InterfaceLogin | None, instance: str
) -> None:
    """登入真的寫進去了才記下那一組：之後靠它比出「已經是這一組」，也靠它說出帳號是誰。只記帳號
    與加鹽雜湊（M4 票 15）。沒帶登入、那一台自己就設過的，只記帳號（雜湊留空）。"""
    if step.key != PROWLARR_LOGIN_STEP or step.status not in (StepStatus.OK, StepStatus.SKIPPED):
        return
    if login is not None and step.status is StepStatus.OK:
        setup.indexer.web_ui_username = login.username
        setup.indexer.web_ui_password_hash = hash_password(login.password)
    elif login is None and not setup.indexer.web_ui_username and instance:
        setup.indexer.web_ui_username = instance
        setup.indexer.web_ui_password_hash = ""


def _instance_username(config: Mapping[str, Any]) -> str:
    """那一台自己設過的介面帳號（brief §20.14）：`config/host` 的 `authenticationMethod` 全新是
    `none`、帳號空白；設過是 `forms` / `basic` 加帳號。沒設過是空字串。"""
    if str(config.get("authenticationMethod") or "none").lower() == "none":
        return ""
    return str(config.get("username") or "")


async def _apply_password(
    client: ProwlarrClient,
    setup: SetupSettings,
    origin: ServiceOrigin | None,
    login: InterfaceLogin | None,
    instance: str,
    *,
    sleep: Sleeper,
) -> SetupStep:
    """套件內 Prowlarr 的介面登入（M4 票 07）：`config/host` 的 Forms 驗證。

    不帶登入時，設過的照舊（`skipped`、細節是帳號）；**那一台自己就設過的也不強迫再設**
    （重裝保留 config，M4 票 15，`instance`）；其餘是 `pending`：必填，精靈停在頁 4
    （`setup._indexer_settled`）。

    `PUT config/host` 回 202 之後 Prowlarr **自行重啟**，所以要等它回來才算做完；
    整份物件都要送回去，少了 `passwordConfirmation` 會被拒（brief §20.7）。
    """
    key = PROWLARR_LOGIN_STEP
    if origin is not ServiceOrigin.BUNDLED:
        return SetupStep(key=key, status=StepStatus.SKIPPED)
    recorded = setup.indexer.web_ui_username
    if login is None:
        known = recorded or instance
        if not known:
            return SetupStep(key=key, status=StepStatus.PENDING)
        return SetupStep(key=key, status=StepStatus.SKIPPED, detail=known)

    try:
        config = await client.host_config()
        if (
            config.get("authenticationMethod") == "forms"
            and config.get("username") == login.username
            and recorded == login.username
            and password_matches(login.password, setup.indexer.web_ui_password_hash)
        ):
            # 已經是這一組帳密了。密碼讀回來是雜湊，比不了，所以比的是 Berth 上一次寫下去的那一組
            # 的雜湊——只改密碼時帳號一樣，只比帳號會把新密碼略過（票 06c）。
            return SetupStep(key=key, status=StepStatus.SKIPPED, detail=login.username)

        await client.set_host_config(
            {
                **config,
                "authenticationMethod": "forms",
                "authenticationRequired": "enabled",
                "username": login.username,
                "password": login.password,
                "passwordConfirmation": login.password,
            }
        )
        await _wait_for_restart(client, sleep=sleep)
    except ServiceError as exc:
        # 這一條失敗不該把前面那幾站的結果一起丟掉——它們已經加進去了，畫面必須說得出來。
        return SetupStep(key=key, status=StepStatus.FAILED, error=message(exc))
    return SetupStep(key=key, status=StepStatus.OK, detail=login.username)


async def _wait_for_restart(client: ProwlarrClient, *, sleep: Sleeper) -> None:
    """`GET /ping` 設了密碼之後仍然匿名 200，所以它就是「回來了沒」的判準（brief §20.7）。"""
    for attempt in range(RESTART_ATTEMPTS):
        if attempt:
            await sleep(POLL_SECONDS)
        try:
            await client.ping()
        except ServiceError:
            continue
        if attempt:
            return
    raise ServiceError("prowlarr did not come back after the credentials were set")


@dataclass(frozen=True, slots=True)
class IndexerProbe:
    step: SetupStep
    #: 給服務頁的理由。這一支的失敗多半只有原文，分得出來的只有「版本太舊」（M4 票 17），
    #: 其餘一律是連不上。
    reason: ConnectionReason


@command(Effect.READ)
async def probe_indexer(
    factory: ServiceClientFactory, kind: IndexerKind, base_url: str, api_key: str
) -> IndexerProbe:
    """那個索引站位址現在回得出什麼。

    精靈第 6 步的既有路徑與健康檢查的第三項用的是同一支：兩者問的都是「這個端點還能不能
    搜」，分成兩份實作只會讓其中一份先過期（票 10）。
    """
    if kind is IndexerKind.TORZNAB:
        torznab = factory.torznab(base_url, api_key)
        try:
            caps = await torznab.caps()
        except ServiceError as exc:
            return _unreachable(
                SetupStep(key=kind.value, status=StepStatus.FAILED, error=message(exc))
            )
        finally:
            await torznab.aclose()
        if not caps.search.available:
            return _unreachable(
                SetupStep(
                    key=kind.value,
                    status=StepStatus.FAILED,
                    detail=caps.server_title,
                    error="t=caps: this endpoint does not offer search",
                )
            )
        return _connected(
            SetupStep(
                key=kind.value,
                status=StepStatus.OK,
                detail=" · ".join(
                    part for part in (caps.server_title, *caps.categories[:3]) if part
                ),
            )
        )

    prowlarr = factory.prowlarr(base_url, api_key)
    try:
        await prowlarr.ping()
        status = await prowlarr.status()
        if not status.supported:
            return IndexerProbe(
                step=outdated_step(status.version),
                reason=ConnectionReason.VERSION_UNSUPPORTED,
            )
        indexers = await prowlarr.indexers()
    except ServiceError as exc:
        return _unreachable(SetupStep(key=kind.value, status=StepStatus.FAILED, error=message(exc)))
    finally:
        await prowlarr.aclose()
    return _connected(SetupStep(key=kind.value, status=StepStatus.OK, detail=str(len(indexers))))


def outdated_step(version: str) -> SetupStep:
    """比下限舊的 Prowlarr：細節是它的版本、錯誤是那一句原文（brief §20.14）。

    精靈的兩條入口與健康檢查都寫這一份，所以三處說的是同一句話。
    """
    return SetupStep(
        key=IndexerKind.PROWLARR.value,
        status=StepStatus.FAILED,
        detail=version,
        error=unsupported_message(version),
    )


def _connected(step: SetupStep) -> IndexerProbe:
    return IndexerProbe(step=step, reason=ConnectionReason.CONNECTED)


def _unreachable(step: SetupStep) -> IndexerProbe:
    return IndexerProbe(step=step, reason=ConnectionReason.UNREACHABLE)


def _target(setup: SetupSettings, settings: IndexerSettings) -> tuple[ServiceOrigin | None, str]:
    """要連哪一台、它是誰的：使用者在頁 4 選的（M4 票 15）。還沒選是 `None`，寫入的命令一律拒絕。"""
    if settings.kind == IndexerKind.TORZNAB.value:
        # Torznab 是使用者自己貼的端點，與 compose 裡那台 Prowlarr 無關。
        return (ServiceOrigin.EXISTING, settings.base_url)
    choice = setup.choices.get(ServiceKind.PROWLARR)
    if choice is None:
        return (None, settings.base_url)
    return (choice.origin, settings.base_url or choice.base_url)


def _offered(site: IndexerDefinition | ProwlarrIndexer) -> bool:
    """Berth 加得了（也就加得回去）的站：推薦清單上的，或公開的 torrent 站（M4 票 09）。

    私站與半私站要帳號、usenet 站 qBittorrent 接不了；推薦清單上的 Anime Tosho 是半私站，照樣算。
    """
    if site.definition_name in DEFAULT_INDEXERS:
        return True
    return site.privacy == "public" and site.protocol == "torrent"


def _refused(name: str) -> SiteCheck:
    return SiteCheck(
        name,
        passed=False,
        reason=SiteFailure.OTHER,
        detail=f"{name}: not a public torrent site this Prowlarr knows; add it in Prowlarr itself",
    )


def _passed(name: str) -> SiteCheck:
    return SiteCheck(name, passed=True, reason=None, detail="")


def _failed(name: str, messages: tuple[str, ...]) -> SiteCheck:
    return SiteCheck(name, passed=False, reason=failure_of(messages), detail=" · ".join(messages))


def _by_definition(definitions: tuple[IndexerDefinition, ...]) -> dict[str, IndexerDefinition]:
    """同一個 `definitionName` 可能出現兩次（`Torrent RSS Feed` 與它的 preset showRSS，
    brief §20.7）：Berth 認站靠它，所以第一個算數。"""
    by_name: dict[str, IndexerDefinition] = {}
    for row in definitions:
        by_name.setdefault(row.definition_name, row)
    return by_name


def _candidates(
    definitions: tuple[IndexerDefinition, ...], present: list[ProwlarrIndexer]
) -> tuple[IndexerCandidate, ...]:
    """還沒加入、Berth 加得了的站：推薦清單照 `DEFAULT_INDEXERS` 的順序在前，其餘依名稱。"""
    added = {row.definition_name for row in present}
    by_name = _by_definition(definitions)
    recommended = [by_name[name] for name in DEFAULT_INDEXERS if name in by_name]
    others = sorted(
        (
            row
            for row in by_name.values()
            if row.definition_name not in DEFAULT_INDEXERS and _offered(row)
        ),
        key=lambda row: row.name.casefold(),
    )
    return tuple(
        IndexerCandidate(
            definition_name=row.definition_name,
            name=row.name,
            privacy=row.privacy,
            language=row.language,
            description=row.description,
            recommended=row.definition_name in DEFAULT_INDEXERS,
        )
        for row in (*recommended, *others)
        if row.definition_name not in added
    )


def _sites(present: list[ProwlarrIndexer], *, bundled: bool) -> tuple[IndexerSite, ...]:
    return tuple(
        IndexerSite(
            indexer_id=row.id,
            definition_name=row.definition_name,
            name=row.name,
            enabled=row.enabled,
            language=row.language,
            description=row.description,
            privacy=row.privacy,
            removable=bundled and _offered(row),
        )
        for row in present
    )


def _checks(steps: list[SetupStep]) -> tuple[SiteCheck, ...]:
    """上一次「加入」對每一站的結論。介面登入那一條不是站。"""
    return tuple(
        _failed(row.key, (row.error,)) if row.status is StepStatus.FAILED else _passed(row.key)
        for row in steps
        if row.key != PROWLARR_LOGIN_STEP
        and row.status in (StepStatus.OK, StepStatus.SKIPPED, StepStatus.FAILED)
    )


def _view(
    setup: SetupSettings,
    settings: IndexerSettings,
    origin: ServiceOrigin | None,
    base_url: str,
    *,
    sites: tuple[IndexerSite, ...] = (),
    candidates: tuple[IndexerCandidate, ...] = (),
    reachable: bool = True,
    error: str = "",
    instance_username: str = "",
) -> IndexerSetupStatus:
    return IndexerSetupStatus(
        origin=origin,
        kind=IndexerKind(settings.kind),
        base_url=base_url,
        api_key_present=bool(settings.api_key),
        reachable=reachable,
        sites=sites,
        candidates=candidates,
        checks=_checks(setup.indexer.steps),
        steps=step_views(setup.indexer.steps),
        skipped=setup.indexer.skipped,
        web_ui_login=origin is ServiceOrigin.BUNDLED,
        web_ui_username=(setup.indexer.web_ui_username or instance_username)
        if origin is ServiceOrigin.BUNDLED
        else "",
        error=error,
        reason=_last_reason(setup),
    )


def _last_reason(setup: SetupSettings) -> ConnectionReason | None:
    choice = setup.choices.get(ServiceKind.PROWLARR)
    return choice.test.reason if choice is not None and choice.test is not None else None
