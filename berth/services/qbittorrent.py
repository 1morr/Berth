"""精靈第 4 步：qBittorrent（plan §9.3 第 4 步、§8.1、§9.5）。

形狀與第 3 步一樣：先讓使用者看見「將會寫什麼」（`read_qbittorrent_diff`），按下之後
逐鍵套用（`apply_qbittorrent`）。兩者都不改使用者沒同意的東西：

- **只寫有差異的鍵**。已經是建議值的鍵連送都不送，重按時它們是 `skipped`。
- **全域偏好只寫套件內的那一台**（M4 票 05，brief §16.4）。既有 qBittorrent 的全域偏好一個都
  不寫，也不列（M4 票 22）：改它的全域 `save_path` 會讓使用者不經 Berth 加的 torrent 全部跑進
  Berth 的目錄，而它的全域偏好沒有一個影響 Berth——Berth 的下載靠自己的分類（建立時帶 save path
  與未完成目錄）與逐個 torrent 的 `autoTMM=true`，與 Sonarr / Radarr 對下載器的做法相同。
- **未完成目錄不寫全域**（M4 票 22）：套件內的那一台也不寫 `temp_path`。Berth 的每個分類帶自己的
  `downloadPath`，兩版實測全域關著也生效、開著時分類的贏（brief §20.2）。
- **WebUI 登入只給套件內的那一台**：頁上填的那一組跟著「套用」送進來（M4 票 07），設定頁改它走
  `set_interface_login`。既有 qBittorrent 是他自己的服務，Berth 不改它的密碼（brief §16.4），帶了
  登入就拒絕。**Berth 只記帳號與雜湊**，自己連它靠免密白名單（M4 票 15）。
- **還沒選來源就什麼都不寫**（M4 票 15）：寫入的命令一律拒絕。
- **Web API 低於 2.8.4 拒絕接入**，因為 Berth 要用的端點在那之前不存在（brief §16.4）。
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.qbittorrent import (
    BERTH_TAG,
    QbittorrentClient,
    QbittorrentVersion,
    TorrentStatus,
)
from berth.domain import (
    IssueType,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepFailure,
    StepStatus,
)
from berth.models import Job, PathSettings, QbittorrentSettings, Route, SetupSettings, SetupStep
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.jellyfin import resolve_interface_login
from berth.services.settings import read_settings, write_settings
from berth.services.steps import (
    InterfaceLogin,
    StepView,
    failed_step,
    failure_of,
    hash_password,
    message,
    password_matches,
    step_views,
)

#: 建議偏好的三個鍵（plan §8.1）。順序即畫面上的順序，也是送出去的順序。
RECOMMENDED_STEPS: tuple[QbittorrentStep, ...] = (
    QbittorrentStep.SAVE_PATH,
    QbittorrentStep.AUTO_TMM_ENABLED,
    QbittorrentStep.CATEGORY_CHANGED_TMM_ENABLED,
)

#: WebUI 帳號的偏好鍵。`web_ui_password` 只寫不讀，讀回來的偏好裡根本沒有它（brief §20.7）。
WEB_UI_USERNAME_KEY = "web_ui_username"
WEB_UI_PASSWORD_KEY = "web_ui_password"

#: 全新 qBittorrent 的 WebUI 帳號（brief §20.14）。它讀得回來、密碼讀不回來，所以「套件內那一台
#: 自己就設過登入了」只認得出帳號不是它的那一種；還是 `admin` 的一律當沒設過（寧可多問一次）。
DEFAULT_WEB_UI_USERNAME = "admin"


def managed(statuses: Iterable[TorrentStatus], categories: Container[str]) -> list[TorrentStatus]:
    """客戶端上掛著 Berth 記號的那幾筆（plan §3.2 的**兩道篩子的聯集**）。

    category 是 Berth 某一條 Route 的，**或** tag 是 `berth`。只認 category 的話，Route 被刪掉
    之後它送出去的那些 torrent 就再也沒有人認領；只認 tag 的話，使用者自己丟進 Berth category
    的 torrent 看不見——而那一筆之後會被 importer 撿走。

    **只有一份實作**：poller（無主 torrent）與對帳（客戶端那一方）問的是同一個問題，各寫一份
    的話加第三道篩子時會漏改一邊。
    """
    return [row for row in statuses if row.category in categories or BERTH_TAG in row.tags]


async def unknown_torrents(
    session: AsyncSession, statuses: Iterable[TorrentStatus]
) -> list[TorrentStatus]:
    """掛著 Berth 記號、而 Berth 沒有 Job 的那幾筆（plan §3.2 的 `unknown_torrent`）。

    **兩個生產者問同一題**：`qbit_poller` 每一輪、對帳每一天（M2 票 09）。它們寫的是同一個
    冪等鍵，判準若各寫一份，漂移的那一天兩邊會對同一個 hash 一個開、一個不開。
    """
    categories = {row for row in await session.scalars(select(Route.category)) if row}
    ours = managed(statuses, categories)
    if not ours:
        return []
    known = set(
        await session.scalars(select(Job.hash).where(Job.hash.in_([row.hash for row in ours])))
    )
    return [row for row in ours if row.hash not in known]


def unknown_torrent_detail(status: TorrentStatus) -> dict[str, Any]:
    """`unknown_torrent` 那一件說的內容。**兩個生產者寫同一份**：`qbit_poller` 每一輪、對帳
    每一天（M2 票 09），而冪等鍵把它們收成一筆——兩邊寫的形狀不同的話，清單上那一列說的話會
    跟著最後寫的是誰變。"""
    return {
        "type": IssueType.UNKNOWN_TORRENT.value,
        "name": status.name,
        "category": status.category,
        "client_state": status.state,
    }


async def sign_in(client: QbittorrentClient, settings: QbittorrentSettings) -> None:
    """既有服務要先登入；套件內的那一台在免密白名單上（plan §9.2）。

    住在這裡而不是 `services/routes`：它問的是 qBittorrent 的事，而 Route 檢查（票 09 起
    還有送單）只是兩個呼叫端。

    **登入失敗不在這裡爆掉**：帳密不對要變成每個 Route 的 `category` 那一條紅燈（接下來的
    呼叫會丟同一個 `AuthFailedError`，原文就落在那一行），而不是一個把整頁換成 500、
    連哪個 Route 卡住都看不出來的例外。
    """
    await try_sign_in(client, settings)


async def try_sign_in(
    client: QbittorrentClient, settings: QbittorrentSettings
) -> ServiceError | None:
    """`sign_in`，但把失敗交回來。Route 檢查要把它說成第一條的紅燈（M4 票 21）：帳密錯時
    接下來的 403 與「沒登入」同形（brief §20.2），原因只有這一次登入說得出來。"""
    if not settings.username:
        return None
    try:
        await client.login(settings.username, settings.password)
    except ServiceError as exc:
        return exc
    return None


@dataclass(frozen=True, slots=True)
class PreferenceDiff:
    """一個鍵的現值與建議值。值都轉成字串，畫面照原樣顯示（剖面即預覽）。"""

    key: str
    current: str
    recommended: str
    differs: bool


@dataclass(frozen=True, slots=True)
class QbittorrentSetupStatus:
    """`GET /api/setup/qbittorrent/diff` 與 `POST .../apply` 的整份形狀。"""

    #: 使用者在頁 2 選的來源；還沒選是 `None`。
    origin: ServiceOrigin | None
    base_url: str
    #: `app/version` 與 `app/webapiVersion`，探到什麼就顯示什麼。
    version: str
    webapi_version: str
    #: Web API 夠新（≥ 2.8.4）。
    supported: bool
    #: 這一步做不下去：版本太舊或根本連不上。
    blocked: bool
    reachable: bool
    #: 套件內那一台的逐鍵差異。既有的那一台是空的：它的全域偏好 Berth 不寫、也不影響 Berth。
    diffs: tuple[PreferenceDiff, ...]
    steps: tuple[StepView, ...]
    #: 泊位上有 WebUI 登入那一格：只有套件內的那一台（M4 票 07）。
    web_ui_login: bool
    #: 套件內那一台的 WebUI 帳號：Berth 設下的，或那一台自己就設過的（不是 `admin`）。還沒設過、
    #: 或是既有的那一台是空字串。
    web_ui_username: str
    #: 建議鍵會被寫。既有的那一台是 `False`：按鈕只是確認連得上、版本夠新。
    writes_preferences: bool
    #: 連線本身為什麼失敗（M4 票 21）：UI 照它說人話。連上了是 `None`。
    failure: StepFailure | None
    #: 連線本身的失敗原文（英文）。UI 收進「技術細節」。
    error: str


async def read_qbittorrent_diff(
    session: AsyncSession, factory: ServiceClientFactory
) -> QbittorrentSetupStatus:
    """連一次那台 qBittorrent，回「現值 vs 建議值」。不寫任何東西。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = qbittorrent_target(setup, settings)
    if origin is None:
        # 選之前不連（M4 票 15）：不知道那一台是誰的，連「讀」也不去敲。
        return _unreachable(
            setup, settings, origin, base_url, ValueError("choose where it comes from first")
        )

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
    except ServiceError as exc:
        return _unreachable(setup, settings, origin, base_url, exc)
    finally:
        await client.aclose()

    return _status(
        setup,
        settings,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
        paths=paths,
    )


async def apply_qbittorrent(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    login: InterfaceLogin | None = None,
) -> QbittorrentSetupStatus:
    """套用建議偏好。只寫有差異的鍵；密碼是另一次呼叫，所以它失敗不影響前面幾個鍵。

    `login` 是泊位上填的 WebUI 登入（M4 票 07）。不帶就是「登入照舊」：回頭重按與設定頁的
    「還原建議設定」都不帶，已經設過的那一組不重寫。

    既有的那一台一個鍵都不寫、也不記偏好的纜繩：這一步對它的意思只剩「連得上、版本夠新」，
    按下去只記密碼那一條 `skipped`（`setup._qbittorrent_secured` 認它）。帶了登入就拒絕
    （`ValueError`）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = qbittorrent_target(setup, settings)
    if origin is None:
        raise ValueError("choose where qBittorrent comes from first")
    if login is not None:
        _refuse_existing(origin)
        # 沿用 Jellyfin 帳密要先過 Jellyfin 那一關：在寫任何東西之前（M4 票 15）。
        login = await resolve_interface_login(session, factory, login)

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
        if not version.supported:
            # 版本太舊：什麼都不寫，畫面顯示升級提示（brief §16.4）。
            return _status(
                setup,
                settings,
                origin=origin,
                base_url=base_url,
                version=version,
                preferences=preferences,
                paths=paths,
            )

        diffs = _diffs(preferences, paths, origin)
        changes = {row.key: _recommended_value(row.key, paths) for row in diffs if row.differs}
        steps = [_preference_step(row) for row in diffs]
        if changes:
            await client.set_preferences(changes)

        steps.append(await _apply_password(client, setup, origin, login, preferences))
        preferences = dict(await client.preferences())
    except ServiceError as exc:
        return _unreachable(setup, settings, origin, base_url, exc)
    finally:
        await client.aclose()

    setup.qbittorrent.steps = steps
    settings.base_url = base_url
    await write_settings(session, settings)
    await write_settings(session, setup)
    await session.commit()

    return _status(
        setup,
        settings,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
        paths=paths,
    )


@command(Effect.REVERSIBLE)
async def set_interface_login(
    session: AsyncSession, factory: ServiceClientFactory, login: InterfaceLogin
) -> QbittorrentSetupStatus:
    """設定頁的「更新登入」（M4 票 07）：只換套件內那一台的 WebUI 登入，偏好的鍵不動。

    與第 4 步的密碼那一條是同一段（`_apply_password`），結果換掉那一條纜繩。可逆的方式就是
    再設一組。既有的那一台拒絕（`ValueError`）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = qbittorrent_target(setup, settings)
    _refuse_existing(origin)
    login = await resolve_interface_login(session, factory, login)

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
        step = await _apply_password(client, setup, origin, login, preferences)
    except ServiceError as exc:
        return _unreachable(setup, settings, origin, base_url, exc)
    finally:
        await client.aclose()

    setup.qbittorrent.steps = [
        *(row for row in setup.qbittorrent.steps if row.key != step.key),
        step,
    ]
    await write_settings(session, settings)
    await write_settings(session, setup)
    await session.commit()
    return _status(
        setup,
        settings,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
        paths=paths,
    )


def _refuse_existing(origin: ServiceOrigin | None) -> None:
    if origin is not ServiceOrigin.BUNDLED:
        # 泊位上根本沒有那一格；走到這裡的只有直接打 API 的人（brief §16.4 的紅線）。
        raise ValueError("this qBittorrent is an existing service; Berth does not set its login")


async def _apply_password(
    client: QbittorrentClient,
    setup: SetupSettings,
    origin: ServiceOrigin | None,
    login: InterfaceLogin | None,
    preferences: Mapping[str, Any],
) -> SetupStep:
    """套件內的那一台另設 WebUI 登入（M4 票 07）。

    設完的那一組只記帳號與加鹽雜湊（`setup.qbittorrent.web_ui_*`，M4 票 15）：Berth 連它靠免密
    白名單，用不到密碼；雜湊只拿來比出「已經是這一組了」——密碼是這一步唯一讀不回來比對的鍵。

    不帶登入時：設過的照舊（`skipped`、細節是帳號）；**那一台自己就設過的也不強迫再設**（重裝保留
    config，M4 票 15）——帳號不是 `admin` 就是設過了（brief §20.14），記下帳號、雜湊留空；其餘是
    `pending`：必填，精靈停在頁 2（`setup._qbittorrent_secured`）。
    """
    key = QbittorrentStep.PASSWORD.value
    if origin is not ServiceOrigin.BUNDLED:
        return SetupStep(key=key, status=StepStatus.SKIPPED)
    record = setup.qbittorrent
    if login is None:
        instance = _instance_username(preferences)
        if not record.web_ui_username and instance:
            record.web_ui_username = instance
            record.web_ui_password_hash = ""
        if not record.web_ui_username:
            return SetupStep(key=key, status=StepStatus.PENDING)
        return SetupStep(key=key, status=StepStatus.SKIPPED, detail=record.web_ui_username)
    if login.username == record.web_ui_username and password_matches(
        login.password, record.web_ui_password_hash
    ):
        return SetupStep(key=key, status=StepStatus.SKIPPED, detail=login.username)

    try:
        await client.set_preferences(
            {WEB_UI_USERNAME_KEY: login.username, WEB_UI_PASSWORD_KEY: login.password}
        )
    except ServiceError as exc:
        # 這一條失敗不該把前面幾個鍵的結果一起丟掉——它們已經寫進去了。
        return failed_step(key, exc)
    record.web_ui_username = login.username
    record.web_ui_password_hash = hash_password(login.password)
    return SetupStep(key=key, status=StepStatus.OK, detail=login.username)


def _instance_username(preferences: Mapping[str, Any]) -> str:
    """那一台自己的 WebUI 帳號，還是預設的 `admin` 時是空字串（`DEFAULT_WEB_UI_USERNAME`）。"""
    name = str(preferences.get(WEB_UI_USERNAME_KEY) or "")
    return "" if name == DEFAULT_WEB_UI_USERNAME else name


async def _connect(
    client: QbittorrentClient, settings: QbittorrentSettings
) -> tuple[QbittorrentVersion, dict[str, Any]]:
    """既有服務要先登入；套件內的那一台在免密白名單上（plan §9.2）。"""
    if settings.username:
        await client.login(settings.username, settings.password)
    version = await client.version()
    if not version.supported:
        return (version, {})
    return (version, dict(await client.preferences()))


def qbittorrent_target(
    setup: SetupSettings, settings: QbittorrentSettings
) -> tuple[ServiceOrigin | None, str]:
    """要連哪一台、它是誰的：使用者在頁 2 選的（M4 票 15），位址是選的時候存下的那一條
    （套件內是 compose 主機名，`clients.bundled_targets`）。還沒選是 `None`，寫入的命令一律拒絕。
    """
    choice = setup.choices.get(ServiceKind.QBITTORRENT)
    if choice is None:
        return (None, settings.base_url)
    return (choice.origin, settings.base_url or choice.base_url)


def writes_preferences(origin: ServiceOrigin | None) -> bool:
    """建議鍵寫不寫得：只有套件內的那一台（M4 票 05）。"""
    return origin is ServiceOrigin.BUNDLED


def drifted_keys(
    preferences: Mapping[str, Any], paths: PathSettings, origin: ServiceOrigin | None
) -> tuple[str, ...]:
    """現在與建議值不同的那幾個鍵（brief §16.3 的「關鍵設定漂移」）。

    健康檢查與精靈第 4 步問的是同一個問題，所以用同一份比對——包含尾斜線正規化，否則
    4.4 上每一輪健康檢查都會報一次假的漂移。既有的那一台沒有漂移可言：它的全域偏好本來就
    是使用者的，「還原建議設定」在它上面什麼都不寫。
    """
    return tuple(row.key for row in _diffs(dict(preferences), paths, origin) if row.differs)


def _diffs(
    preferences: dict[str, Any], paths: PathSettings, origin: ServiceOrigin | None
) -> tuple[PreferenceDiff, ...]:
    """逐鍵差異。既有的那一台沒有：它的全域偏好 Berth 不寫，而且沒有一個影響 Berth（M4 票 22），
    列出套件內的建議值只會讓人以為該去改。"""
    if not writes_preferences(origin):
        return ()
    return tuple(
        _diff(step.value, preferences.get(step.value), paths) for step in RECOMMENDED_STEPS
    )


def _diff(key: str, current: Any, paths: PathSettings) -> PreferenceDiff:
    """一個鍵的現值與建議值。

    **路徑要正規化尾斜線再比**：4.4.5 把 `/downloads` 讀回來寫成 `/downloads/`（brief §20.7），
    照字面比對的話 `save_path` 在 4.4 上永遠「不同」，每次重按都重寫一次同樣的值。
    """
    recommended = _recommended_value(key, paths)
    return PreferenceDiff(
        key=key,
        current=_text(current),
        recommended=_text(recommended),
        differs=_comparable(key, current) != _comparable(key, recommended),
    )


def _comparable(key: str, value: Any) -> Any:
    # 值是路徑的只有 `save_path`；其餘兩個是布林，照字面比。
    if key == QbittorrentStep.SAVE_PATH.value and isinstance(value, str):
        return value.rstrip("/") or "/"
    return value


def _recommended_value(key: str, paths: PathSettings) -> Any:
    """建議值（plan §8.1）。路徑跟著 `settings.paths` 走，不另外寫死一份。"""
    if key == QbittorrentStep.SAVE_PATH.value:
        return paths.complete_root
    return True


def _preference_step(diff: PreferenceDiff) -> SetupStep:
    """寫過的鍵是 `ok`，本來就對的是 `skipped`——兩者都代表「這一條繫上了」。"""
    return SetupStep(
        key=diff.key,
        status=StepStatus.OK if diff.differs else StepStatus.SKIPPED,
        detail=diff.recommended,
    )


def _web_ui_username(
    setup: SetupSettings, origin: ServiceOrigin | None, preferences: Mapping[str, Any]
) -> str:
    """套件內那一台的 WebUI 帳號：Berth 記下的，或那一台自己就設過的。既有的那一台是空字串——
    Berth 連它用的帳密是使用者給的，不是 Berth 設的登入。"""
    if origin is not ServiceOrigin.BUNDLED:
        return ""
    return setup.qbittorrent.web_ui_username or _instance_username(preferences)


def _status(
    setup: SetupSettings,
    settings: QbittorrentSettings,
    *,
    origin: ServiceOrigin | None,
    base_url: str,
    version: QbittorrentVersion,
    preferences: dict[str, Any],
    paths: PathSettings,
) -> QbittorrentSetupStatus:
    supported = version.supported
    diffs = _diffs(preferences, paths, origin) if supported else ()
    return QbittorrentSetupStatus(
        origin=origin,
        base_url=base_url,
        version=version.app,
        webapi_version=version.webapi,
        supported=supported,
        blocked=not supported,
        reachable=True,
        diffs=diffs,
        steps=step_views(setup.qbittorrent.steps),
        web_ui_login=origin is ServiceOrigin.BUNDLED,
        web_ui_username=_web_ui_username(setup, origin, preferences),
        writes_preferences=writes_preferences(origin),
        failure=None,
        error="",
    )


def _unreachable(
    setup: SetupSettings,
    settings: QbittorrentSettings,
    origin: ServiceOrigin | None,
    base_url: str,
    exc: Exception,
) -> QbittorrentSetupStatus:
    failure, _ = failure_of(exc)
    return QbittorrentSetupStatus(
        origin=origin,
        base_url=base_url,
        version="",
        webapi_version="",
        supported=False,
        blocked=True,
        reachable=False,
        diffs=(),
        steps=step_views(setup.qbittorrent.steps),
        web_ui_login=origin is ServiceOrigin.BUNDLED,
        web_ui_username=_web_ui_username(setup, origin, {}),
        writes_preferences=writes_preferences(origin),
        failure=failure,
        error=message(exc),
    )


def _text(value: Any) -> str:
    """布林寫成 `true` / `false`——畫面顯示的要與 Web API 的字面一致，不是「是 / 否」。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)
