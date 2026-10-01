"""精靈每個泊位共用的「一條纜繩」視圖（plan §9.3）。

各泊位的步驟集合不同（Jellyfin 七步、qBittorrent 六個鍵、來源逐站），但攤給 UI 的形狀完全
一樣，所以形狀只定義一次；`SetupStep` 是它存下來的樣子，這裡是它被讀出來的樣子。

泊位 2 與泊位 4 共用的輸入也住這裡：套件內服務自己的介面登入（`InterfaceLogin`，M4 票 07）。
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from berth.adapters.fs import PROBE_PREFIX, PathEscapeError
from berth.adapters.http import (
    AuthFailedError,
    NotFoundError,
    ProtocolMismatchError,
    SchemeMismatchError,
    SchemeMissingError,
    ServiceBusyError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.qbittorrent import IpBannedError
from berth.domain import StepFailure, StepStatus
from berth.models import SetupStep


@dataclass(frozen=True, slots=True)
class StepView:
    step: str
    status: StepStatus
    #: 實測值：版本號、路徑、任務 id。UI 放進「技術細節」，不翻譯。
    detail: str
    #: 失敗時服務回的原文（英文）。UI 收進「技術細節」。
    error: str
    #: 失敗時為什麼（`SetupStep.failure`）。票 21 之前存下的失敗沒有，讀出來補成 `unexpected`。
    failure: StepFailure | None = None
    params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InterfaceLogin:
    """套件內 qBittorrent / Prowlarr 自己的介面登入（M4 票 07）。

    給使用者打開那個服務的介面用的；Berth 自己不靠它（qBittorrent 在免密白名單上、Prowlarr 用
    掛載讀到的 API key）。跟著泊位的「套用」或設定頁的「更新登入」送進來，既有服務不收。
    """

    username: str
    password: str
    #: 「沿用 Jellyfin 帳密」（brief §16.3，M4 票 15）：帳號是擁有者、密碼要先過 Jellyfin 那一關
    #: （`jellyfin.owner_login`）。勾了它時 `username` 不算數。
    reuse_owner: bool = False


def hash_password(password: str) -> str:
    """Berth 寫進套件內服務的介面密碼只存這個（brief §19 2026-09-29 ⑤）：加鹽的 scrypt。

    勾了「沿用 Jellyfin 帳密」時那一組就是擁有者的 Jellyfin 密碼，存明文會推翻票 06 的「資料庫裡
    沒有擁有者的明文密碼」。雜湊只拿來比對「已經是這一組了」（`password_matches`）。
    """
    salt = os.urandom(16)
    return f"scrypt${salt.hex()}${_scrypt(password, salt).hex()}"


def password_matches(password: str, stored: str) -> bool:
    """`stored` 是 `hash_password` 寫下的那一串。空的或認不得的一律不相符。"""
    try:
        scheme, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        return hmac.compare_digest(_scrypt(password, bytes.fromhex(salt)).hex(), digest)
    except ValueError:
        return False


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)


def step_views(rows: Iterable[SetupStep]) -> tuple[StepView, ...]:
    return tuple(
        StepView(
            step=row.key,
            status=row.status,
            detail=row.detail,
            error=row.error,
            failure=_failure_or_unknown(row),
            params=dict(row.params),
        )
        for row in rows
    )


def _failure_or_unknown(row: SetupStep) -> StepFailure | None:
    if row.status is not StepStatus.FAILED:
        return None
    return row.failure or StepFailure.UNEXPECTED


class StepFailedError(OSError):
    """這一條沒過，而原因是 Berth 自己判斷出來的（不是誰丟出來的例外），代碼與參數跟著走。

    繼承 `OSError`：與 `stat` / `link` 的失敗走同一條處理路徑（`failed_step`）——對畫面來說它們是
    同一件事：這條纜繩沒繫上。訊息是英文原文，收進技術細節。
    """

    def __init__(self, failure: StepFailure, message: str, **params: str) -> None:
        super().__init__(message)
        self.failure = failure
        self.params = params


def failure_of(exc: Exception) -> tuple[StepFailure, dict[str, str]]:
    """例外 → 代碼與參數（M4 票 21）。adapter 已經把 httpx 分好類（`adapters.http`），這裡只是對照。

    **`IpBannedError` 排在 `AuthFailedError` 前面**：它是子類，被封與帳密不對的下一步不同（票 10）。
    其餘的 `OSError` 是 Berth 在自己的容器裡碰檔案時的失敗：建目錄、寫探測檔。
    """
    if isinstance(exc, StepFailedError):
        return exc.failure, dict(exc.params)
    for kind, failure in _FAILURES:
        if isinstance(exc, kind):
            return failure, {}
    if isinstance(exc, OSError) and exc.filename is not None:
        # 寫不進的是探測檔時說它所在的目錄（M4 票 25）：要改權限的是那個目錄，探測檔本來就不存在。
        path = PurePosixPath(str(exc.filename))
        where = path.parent if path.name.startswith(PROBE_PREFIX) else path
        return StepFailure.BERTH_CANNOT_WRITE, {"path": str(where)}
    return StepFailure.UNEXPECTED, {}


_FAILURES: tuple[tuple[type[BaseException], StepFailure], ...] = (
    (ServiceNotDeployedError, StepFailure.NOT_DEPLOYED),
    (ServiceUnavailableError, StepFailure.UNREACHABLE),
    (ServiceBusyError, StepFailure.STARTING),
    (IpBannedError, StepFailure.IP_BANNED),
    (AuthFailedError, StepFailure.AUTH_REJECTED),
    (ProtocolMismatchError, StepFailure.PROTOCOL_MISMATCH),
    (SchemeMismatchError, StepFailure.SCHEME_MISMATCH),
    (SchemeMissingError, StepFailure.SCHEME_MISSING),
    (NotFoundError, StepFailure.NOT_FOUND),
    (PathEscapeError, StepFailure.BERTH_CANNOT_WRITE),
)


def failed_step(key: str, exc: Exception, *, detail: str = "") -> SetupStep:
    """一條失敗的纜繩：代碼照例外分類，原文照錄。"""
    failure, params = failure_of(exc)
    return SetupStep(
        key=key,
        status=StepStatus.FAILED,
        detail=detail,
        failure=failure,
        params=params,
        error=message(exc),
    )


def message(exc: Exception) -> str:
    """例外的原文。空訊息的例外至少要說得出自己是哪一種。"""
    return str(exc) or type(exc).__name__
