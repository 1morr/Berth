"""精靈第 6 步：索引站（plan §9.3 第 6 步、§8.4、brief §16.3）。

兩條路徑，同一份狀態形狀（`SetupIndexer`）：

- **套件內 Prowlarr**：勾選預設公開站，Berth 以 `indexer/schema` 取定義、`indexer` 新增、
  `indexer/test` 驗證，逐站顯示成敗。勾了「同一組帳密」時順便替 Prowlarr 介面設 Forms 登入。
- **既有**：Prowlarr 位址 + API key，或任意 Torznab 端點 + key，各有一顆「測試」。

**逐站的成敗來自新增那一支**：`POST /api/v1/indexer` 會先連一次那個站，連不上就回 400 而且
什麼都不建立（2026-09-08 實測，brief §20.7）。已經加過的站不重加——同名會被拒（`Should be
unique`），所以重按時改成 `indexer/test`，結果一樣是「這個站現在通不通」。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.indexer import IndexerSearch, SearchQuery
from berth.adapters.prowlarr import (
    IndexerDefinition,
    IndexerRejectedError,
    ProwlarrClient,
    ProwlarrIndexer,
)
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    DetectionReason,
    IndexerKind,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import IndexerSettings, SetupSettings, SetupStep
from berth.models.types import utcnow
from berth.services.clients import BUNDLED_PROWLARR_URL, ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.settings import read_settings, update_settings, write_settings
from berth.services.steps import StepView, message, step_views

#: 預設勾的九個公開站（plan §9.3 第 6 步、brief §16.3）。值是 Prowlarr 的 `definitionName`：
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

#: Prowlarr 設了 Forms 登入之後會自行重啟；等它回來的輪詢（brief §20.7）。
RESTART_ATTEMPTS = 60
POLL_SECONDS = 2.0

Sleeper = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class IndexerOption:
    """勾選清單的一列。"""

    definition_name: str
    name: str
    privacy: str
    #: 這台 Prowlarr 上已經有這個站了。
    present: bool
    #: BCP 47 代碼與一句英文說明，取自這台伺服器自己的定義（票 06e）。
    language: str = ""
    description: str = ""
    #: 那個站在這台 Prowlarr 上的 id。加進來了才有；移除與試搜認的是它。
    indexer_id: int | None = None


@dataclass(frozen=True, slots=True)
class IndexerSetupStatus:
    """`GET /api/setup/indexers` 與兩顆按鈕的整份形狀。"""

    origin: ServiceOrigin
    kind: IndexerKind
    base_url: str
    api_key_present: bool
    #: 連得上那台 Prowlarr（套件內路徑才有意義）。
    reachable: bool
    options: tuple[IndexerOption, ...]
    steps: tuple[StepView, ...]
    skipped: bool
    #: 勾了「同一組帳密」而且這一台是套件內的 —— 套用時會順便設 Prowlarr 介面的登入。
    sets_password: bool
    error: str


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
    """套件內路徑列出預設站與它們現在的狀態；既有路徑只回存下來的連線資訊。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    origin, base_url = _target(setup, settings)
    if origin is not ServiceOrigin.BUNDLED:
        return _view(setup, settings, origin, base_url, options=(), reachable=True, error="")

    client = factory.prowlarr(base_url, settings.api_key)
    try:
        options = _options(await client.definitions(), await client.indexers())
    except ServiceError as exc:
        return _view(
            setup, settings, origin, base_url, options=(), reachable=False, error=message(exc)
        )
    finally:
        await client.aclose()

    return _view(setup, settings, origin, base_url, options=options, reachable=True, error="")


# 沒有單一反向命令：一次加好幾站、還可能設了 Prowlarr 的介面登入，
# `remove_indexer` 一次只撤得掉一站。
@command(Effect.REVERSIBLE)
async def apply_default_indexers(
    session: AsyncSession,
    factory: ServiceClientFactory,
    selected: Sequence[str],
    *,
    sleep: Sleeper = asyncio.sleep,
) -> IndexerSetupStatus:
    """勾起來的站逐個加進套件內的 Prowlarr（plan §9.3 第 6 步）。

    一站一條纜繩：新增成功 `ok`、已經在了就改用 `indexer/test` 驗一次（通過是 `skipped`），
    連不上是 `failed` 加上 Prowlarr 回的原文。整批不會因為一個站失敗就停下來——公開站裡
    有幾個連不上是常態。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    origin, base_url = _target(setup, settings)
    if origin is not ServiceOrigin.BUNDLED:
        # 既有的索引站是使用者自己的，Berth 只做檢查（brief §16.4 的紅線）。UI 在這個狀態下
        # 根本不給這顆按鈕，所以走到這裡的只有直接打 API 的人。
        raise ValueError("this indexer is an existing service; Berth does not add sites to it")

    client = factory.prowlarr(base_url, settings.api_key)
    steps: list[SetupStep] = []
    try:
        definitions = {row.definition_name: row for row in await client.definitions()}
        existing = {row.definition_name: row for row in await client.indexers()}
        for name in selected:
            steps.append(await _ensure_indexer(client, name, definitions, existing))
        steps.append(await _apply_password(client, setup, settings, origin, sleep=sleep))
    except ServiceError as exc:
        return _view(
            setup, settings, origin, base_url, options=(), reachable=False, error=message(exc)
        )
    finally:
        await client.aclose()

    settings.kind = IndexerKind.PROWLARR.value
    settings.base_url = base_url
    await write_settings(session, settings)

    def record(latest: SetupSettings) -> None:
        latest.indexer.steps = steps
        latest.indexer.skipped = False
        if steps[-1].key == PROWLARR_LOGIN_STEP and steps[-1].status is StepStatus.OK:
            latest.indexer.login_password = setup.admin.interface_password
        _pin_probe(latest, origin)

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
    """既有路徑的「測試」：先存再測，測不過也存（與第 2 步的連線表單同一個規矩）。"""
    settings = await read_settings(session, IndexerSettings)
    settings.kind = kind.value
    settings.base_url = base_url
    settings.api_key = api_key
    await write_settings(session, settings)

    step = await probe_indexer(factory, kind, base_url, api_key)

    def record(latest: SetupSettings) -> None:
        latest.indexer.steps = [step]
        latest.indexer.skipped = False

    # 測試在路上的那幾秒裡，第 7 步可能已經寫進同一組設定（M2 票 15）。
    setup = await update_settings(session, SetupSettings, record)
    origin, _ = _target(setup, settings)
    return _view(setup, settings, origin, base_url, options=(), reachable=True, error="")


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
    session: AsyncSession, factory: ServiceClientFactory, *, query: str
) -> IndexerSearchResult:
    """加入之後的試搜（票 06e）：逐站問一次，列出搜到幾筆與前三筆標題。

    **逐站各發一個查詢**（`indexerIds` 只帶那一站）而不是一次問全部：聚合的回應只有結果，
    哪一站失敗了看不出來，而「一站失敗不影響其他站」正是這一頁要說的事。查詢併發——
    Prowlarr 現場去連每一個站，一個接一個問要好幾分鐘（brief §20.7）。

    空白的查詢也是一個問題：Prowlarr 與 Torznab 都回各站最新的發佈（2026-09-25 實測 dmhy
    80 筆、YTS 96 筆，約 1.3 秒），證明那個站回得出東西，不必先想一個標題。
    **不寫任何東西**：它是 `read` 命令，精靈的步驟不因它前進或後退。
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
            indexers = [row for row in await client.indexers() if row.enabled]
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

    **只移除 Berth 提供的預設站**：反向命令是再勾一次那一站，預設站是公開站，加回來就是原樣；
    使用者在 Prowlarr 自己加的站（可能是私站、帶帳號）Berth 加不回去，所以不碰。那一站的「加入結果」
    一起拿掉——留著一條綠的等於說它還在；最後一站也移除時，精靈就回到第 6 步（`_indexer_settled`）。
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
        if gone is not None and gone.definition_name not in DEFAULT_INDEXERS:
            raise ValueError(f"{gone.name}: Berth only removes the default sites it offers")
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
    if definition is None and already is None:
        return SetupStep(
            key=definition_name,
            status=StepStatus.FAILED,
            error=f"{definition_name}: this Prowlarr has no definition by that name",
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


async def _apply_password(
    client: ProwlarrClient,
    setup: SetupSettings,
    settings: IndexerSettings,
    origin: ServiceOrigin,
    *,
    sleep: Sleeper,
) -> SetupStep:
    """套件內 Prowlarr 的介面登入用第 1 步的介面帳密（brief §16.3、票 06c）。

    `PUT config/host` 回 202 之後 Prowlarr **自行重啟**，所以要等它回來才算做完；
    整份物件都要送回去，少了 `passwordConfirmation` 會被拒（brief §20.7）。
    """
    key = PROWLARR_LOGIN_STEP
    admin = setup.admin
    username, password = admin.interface_username, admin.interface_password
    if origin is not ServiceOrigin.BUNDLED or not admin.apply_to_services or not password:
        return SetupStep(key=key, status=StepStatus.SKIPPED)

    try:
        config = await client.host_config()
        if (
            config.get("authenticationMethod") == "forms"
            and config.get("username") == username
            and setup.indexer.login_password == password
        ):
            # 已經是這一組帳密了。密碼讀回來是雜湊，比不了，所以比的是 Berth 上一次寫下去的值
            # ——只改密碼時帳號一樣，只比帳號會把新密碼略過（票 06c）。
            return SetupStep(key=key, status=StepStatus.SKIPPED, detail=username)

        await client.set_host_config(
            {
                **config,
                "authenticationMethod": "forms",
                "authenticationRequired": "enabled",
                "username": username,
                "password": password,
                "passwordConfirmation": password,
            }
        )
        await _wait_for_restart(client, sleep=sleep)
    except ServiceError as exc:
        # 這一條失敗不該把前面那幾站的結果一起丟掉——它們已經加進去了，畫面必須說得出來。
        return SetupStep(key=key, status=StepStatus.FAILED, error=message(exc))
    return SetupStep(key=key, status=StepStatus.OK, detail=username)


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


@command(Effect.READ)
async def probe_indexer(
    factory: ServiceClientFactory, kind: IndexerKind, base_url: str, api_key: str
) -> SetupStep:
    """那個索引站位址現在回得出什麼。

    精靈第 6 步的既有路徑與健康檢查的第三項用的是同一支：兩者問的都是「這個端點還能不能
    搜」，分成兩份實作只會讓其中一份先過期（票 10）。
    """
    if kind is IndexerKind.TORZNAB:
        torznab = factory.torznab(base_url, api_key)
        try:
            caps = await torznab.caps()
        except ServiceError as exc:
            return SetupStep(key=kind.value, status=StepStatus.FAILED, error=message(exc))
        finally:
            await torznab.aclose()
        if not caps.search.available:
            return SetupStep(
                key=kind.value,
                status=StepStatus.FAILED,
                detail=caps.server_title,
                error="t=caps: this endpoint does not offer search",
            )
        return SetupStep(
            key=kind.value,
            status=StepStatus.OK,
            detail=" · ".join(part for part in (caps.server_title, *caps.categories[:3]) if part),
        )

    prowlarr = factory.prowlarr(base_url, api_key)
    try:
        await prowlarr.ping()
        indexers = await prowlarr.indexers()
    except ServiceError as exc:
        return SetupStep(key=kind.value, status=StepStatus.FAILED, error=message(exc))
    finally:
        await prowlarr.aclose()
    return SetupStep(key=kind.value, status=StepStatus.OK, detail=str(len(indexers)))


def _target(setup: SetupSettings, settings: IndexerSettings) -> tuple[ServiceOrigin, str]:
    probe = setup.services.get(ServiceKind.PROWLARR)
    origin = probe.origin if probe is not None else ServiceOrigin.BUNDLED
    if settings.kind == IndexerKind.TORZNAB.value:
        # Torznab 是使用者自己貼的端點，與 compose 裡那台 Prowlarr 無關。
        return (ServiceOrigin.EXISTING, settings.base_url)
    return (origin, settings.base_url or (probe.base_url if probe else "") or BUNDLED_PROWLARR_URL)


def _pin_probe(setup: SetupSettings, origin: ServiceOrigin) -> None:
    """加完索引站之後不能再被重探判成「既有」。

    判定的規則是「讀得到 key 而且一個索引站都沒有 → 套件內」，而現在它有好幾個了——還是
    Berth 自己加的。與 qBittorrent 設完密碼之後同一個道理。
    """
    probe = setup.services.get(ServiceKind.PROWLARR)
    if probe is None or origin is not ServiceOrigin.BUNDLED:
        return
    setup.services = {
        **setup.services,
        ServiceKind.PROWLARR: probe.model_copy(
            update={
                "reason": DetectionReason.CONNECTED,
                "configured": True,
                "checked_at": utcnow(),
            }
        ),
    }


def _options(
    definitions: tuple[IndexerDefinition, ...], existing: list[ProwlarrIndexer]
) -> tuple[IndexerOption, ...]:
    """預設站，順序照 `DEFAULT_INDEXERS`；顯示名、privacy、語言與說明取自這台伺服器自己的定義。"""
    by_name = {row.definition_name: row for row in definitions}
    present = {row.definition_name: row.id for row in existing}
    # 定義不在了、站還在的（這台 Prowlarr 的定義更新拿掉了它）：照樣列出來，只有機器名可顯示。
    missing = IndexerDefinition("", "", "")
    return tuple(
        IndexerOption(
            definition_name=name,
            name=by_name.get(name, missing).name or name,
            privacy=by_name.get(name, missing).privacy,
            present=name in present,
            language=by_name.get(name, missing).language,
            description=by_name.get(name, missing).description,
            indexer_id=present.get(name),
        )
        for name in DEFAULT_INDEXERS
        if name in by_name or name in present
    )


def _view(
    setup: SetupSettings,
    settings: IndexerSettings,
    origin: ServiceOrigin,
    base_url: str,
    *,
    options: tuple[IndexerOption, ...],
    reachable: bool,
    error: str,
) -> IndexerSetupStatus:
    admin = setup.admin
    return IndexerSetupStatus(
        origin=origin,
        kind=IndexerKind(settings.kind),
        base_url=base_url,
        api_key_present=bool(settings.api_key),
        reachable=reachable,
        options=options,
        steps=step_views(setup.indexer.steps),
        skipped=setup.indexer.skipped,
        sets_password=(
            origin is ServiceOrigin.BUNDLED
            and admin.apply_to_services
            and bool(admin.interface_password)
        ),
        error=error,
    )
