"""精靈第 4 步：qBittorrent（plan §9.3 第 4 步、§8.1、§9.5）。

形狀與第 3 步一樣：先讓使用者看見「將會寫什麼」（`read_qbittorrent_diff`），按下之後
逐鍵套用（`apply_qbittorrent`）。兩者都不改使用者沒同意的東西：

- **只寫有差異的鍵**。已經是建議值的鍵連送都不送，重按時它們是 `skipped`。
- **密碼只給套件內的那一台**，而且要使用者勾了「同一組帳密」。既有 qBittorrent 是他自己的
  服務，Berth 不改它的密碼（brief §16.4）。
- **temp path 未啟用只警告**。建議值仍然列出來，套不套是使用者的事。
- **Web API 低於 2.8.4 拒絕接入**，因為 Berth 要用的端點在那之前不存在（brief §16.4）。
"""

from __future__ import annotations

import contextlib
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
    DetectionReason,
    IssueType,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import Job, PathSettings, QbittorrentSettings, Route, SetupSettings, SetupStep
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings, write_settings
from berth.services.steps import StepView, message, step_views

#: 建議偏好的五個鍵（plan §8.1）。順序即畫面上的順序，也是送出去的順序。
RECOMMENDED_STEPS: tuple[QbittorrentStep, ...] = (
    QbittorrentStep.TEMP_PATH_ENABLED,
    QbittorrentStep.TEMP_PATH,
    QbittorrentStep.SAVE_PATH,
    QbittorrentStep.AUTO_TMM_ENABLED,
    QbittorrentStep.CATEGORY_CHANGED_TMM_ENABLED,
)

#: WebUI 帳號的偏好鍵。`web_ui_password` 只寫不讀，讀回來的偏好裡根本沒有它（brief §20.7）。
WEB_UI_USERNAME_KEY = "web_ui_username"
WEB_UI_PASSWORD_KEY = "web_ui_password"


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
    if not settings.username:
        return
    with contextlib.suppress(ServiceError):
        await client.login(settings.username, settings.password)


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

    origin: ServiceOrigin
    base_url: str
    #: `app/version` 與 `app/webapiVersion`，探到什麼就顯示什麼。
    version: str
    webapi_version: str
    #: Web API 夠新（≥ 2.8.4）。
    supported: bool
    #: 這一步做不下去：版本太舊或根本連不上。
    blocked: bool
    reachable: bool
    diffs: tuple[PreferenceDiff, ...]
    steps: tuple[StepView, ...]
    #: 既有服務的 temp path 未啟用——只警告，不阻擋（brief §16.4）。
    temp_path_warning: bool
    #: 勾了「同一組帳密也套用到 qBittorrent」而且這一台是套件內的。
    sets_password: bool
    #: 連線本身的失敗原文（英文）。UI 貼在手動步驟旁邊。
    error: str


async def read_qbittorrent_diff(
    session: AsyncSession, factory: ServiceClientFactory
) -> QbittorrentSetupStatus:
    """連一次那台 qBittorrent，回「現值 vs 建議值」。不寫任何東西。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = qbittorrent_target(setup, settings)

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
    except ServiceError as exc:
        return _unreachable(setup, origin, base_url, message(exc))
    finally:
        await client.aclose()

    return _status(
        setup,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
        paths=paths,
    )


async def apply_qbittorrent(
    session: AsyncSession, factory: ServiceClientFactory
) -> QbittorrentSetupStatus:
    """套用建議偏好。只寫有差異的鍵；密碼是另一次呼叫，所以它失敗不影響前面五個鍵。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = qbittorrent_target(setup, settings)

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
        if not version.supported:
            # 版本太舊：什麼都不寫，畫面顯示升級提示（brief §16.4）。
            return _status(
                setup,
                origin=origin,
                base_url=base_url,
                version=version,
                preferences=preferences,
                paths=paths,
            )

        diffs = _diffs(preferences, paths)
        changes = {row.key: _recommended_value(row.key, paths) for row in diffs if row.differs}
        steps = [_preference_step(row) for row in diffs]
        if changes:
            await client.set_preferences(changes)

        steps.append(await _apply_password(client, setup, settings, origin))
        preferences = dict(await client.preferences())
    except ServiceError as exc:
        return _unreachable(setup, origin, base_url, message(exc))
    finally:
        await client.aclose()

    setup.qbittorrent.steps = steps
    settings.base_url = base_url
    await write_settings(session, settings)
    await write_settings(session, setup)
    await session.commit()

    return _status(
        setup,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
        paths=paths,
    )


async def _apply_password(
    client: QbittorrentClient,
    setup: SetupSettings,
    settings: QbittorrentSettings,
    origin: ServiceOrigin,
) -> SetupStep:
    """套件內的那一台另設 WebUI 密碼（plan §9.3 第 4 步）。

    設完之後**不能再被重探判成「既有」**：判定的規則是「免密進得去 → 套件內」，而現在它要
    密碼了——那個密碼還是 Berth 自己設的。所以連同判定一起釘住（`configured`）。
    """
    admin = setup.admin
    if not _sets_password(setup, origin):
        return SetupStep(key=QbittorrentStep.PASSWORD.value, status=StepStatus.SKIPPED)
    if (settings.username, settings.password) == (admin.username, admin.password):
        # 已經是這一組帳密了。重按不必再寫一次密碼——那是這一步唯一沒辦法讀回來比對的鍵，
        # 所以比對的是 Berth 自己上一次寫下去的值。
        return SetupStep(
            key=QbittorrentStep.PASSWORD.value,
            status=StepStatus.SKIPPED,
            detail=admin.username,
        )

    try:
        await client.set_preferences(
            {WEB_UI_USERNAME_KEY: admin.username, WEB_UI_PASSWORD_KEY: admin.password}
        )
    except ServiceError as exc:
        # 這一條失敗不該把前面五個鍵的結果一起丟掉——它們已經寫進去了。
        return SetupStep(
            key=QbittorrentStep.PASSWORD.value, status=StepStatus.FAILED, error=message(exc)
        )
    settings.username = admin.username
    settings.password = admin.password
    probe = setup.services.get(ServiceKind.QBITTORRENT)
    if probe is not None:
        setup.services = {
            **setup.services,
            ServiceKind.QBITTORRENT: probe.model_copy(
                update={
                    "reason": DetectionReason.CONNECTED,
                    "configured": True,
                    "checked_at": utcnow(),
                }
            ),
        }
    return SetupStep(
        key=QbittorrentStep.PASSWORD.value, status=StepStatus.OK, detail=admin.username
    )


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
) -> tuple[ServiceOrigin, str]:
    """要連哪一台：存過位址就用它，否則是第 2 步探到的那一台。

    套件內那一台的位址不在這裡組：它的 port 是部署的設定值（`QBITTORRENT_WEBUI_PORT`），
    偵測照設定敲到之後記在判定上（`clients.build_setup_probes`）。還沒偵測過就沒有位址，
    連線會以連不上收場。
    """
    probe = setup.services.get(ServiceKind.QBITTORRENT)
    origin = probe.origin if probe is not None else ServiceOrigin.BUNDLED
    return (origin, settings.base_url or (probe.base_url if probe else ""))


def drifted_keys(preferences: Mapping[str, Any], paths: PathSettings) -> tuple[str, ...]:
    """現在與建議值不同的那幾個鍵（brief §16.3 的「關鍵設定漂移」）。

    健康檢查與精靈第 4 步問的是同一個問題，所以用同一份比對——包含尾斜線正規化，否則
    4.4 上每一輪健康檢查都會報一次假的漂移。
    """
    return tuple(row.key for row in _diffs(dict(preferences), paths) if row.differs)


def _diffs(preferences: dict[str, Any], paths: PathSettings) -> tuple[PreferenceDiff, ...]:
    return tuple(
        _diff(step.value, preferences.get(step.value), paths) for step in RECOMMENDED_STEPS
    )


def _diff(key: str, current: Any, paths: PathSettings) -> PreferenceDiff:
    """一個鍵的現值與建議值。

    **路徑要正規化尾斜線再比**：4.4.5 把 `/downloads` 讀回來寫成 `/downloads/`（brief §20.7），
    照字面比對的話那兩個鍵在 4.4 上永遠「不同」，每次重按都重寫一次同樣的值。
    """
    recommended = _recommended_value(key, paths)
    return PreferenceDiff(
        key=key,
        current=_text(current),
        recommended=_text(recommended),
        differs=_comparable(key, current) != _comparable(key, recommended),
    )


def _comparable(key: str, value: Any) -> Any:
    if key in _PATH_KEYS and isinstance(value, str):
        return value.rstrip("/") or "/"
    return value


#: 值是路徑的那兩個鍵。其餘三個是布林，照字面比。
_PATH_KEYS = frozenset({QbittorrentStep.TEMP_PATH.value, QbittorrentStep.SAVE_PATH.value})


def _recommended_value(key: str, paths: PathSettings) -> Any:
    """建議值（plan §8.1）。路徑兩個鍵跟著 `settings.paths` 走，不另外寫死一份。"""
    if key == QbittorrentStep.TEMP_PATH.value:
        return paths.incomplete_root
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


def _sets_password(setup: SetupSettings, origin: ServiceOrigin) -> bool:
    return (
        origin is ServiceOrigin.BUNDLED
        and setup.admin.apply_to_services
        and bool(setup.admin.username)
        and bool(setup.admin.password)
    )


def _status(
    setup: SetupSettings,
    *,
    origin: ServiceOrigin,
    base_url: str,
    version: QbittorrentVersion,
    preferences: dict[str, Any],
    paths: PathSettings,
) -> QbittorrentSetupStatus:
    supported = version.supported
    diffs = _diffs(preferences, paths) if supported else ()
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
        temp_path_warning=(
            origin is ServiceOrigin.EXISTING and preferences.get("temp_path_enabled") is False
        ),
        sets_password=_sets_password(setup, origin),
        error="",
    )


def _unreachable(
    setup: SetupSettings, origin: ServiceOrigin, base_url: str, error: str
) -> QbittorrentSetupStatus:
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
        temp_path_warning=False,
        sets_password=_sets_password(setup, origin),
        error=error,
    )


def _text(value: Any) -> str:
    """布林寫成 `true` / `false`——畫面顯示的要與 Web API 的字面一致，不是「是 / 否」。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)
