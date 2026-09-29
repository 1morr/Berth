"""精靈每個泊位共用的「一條纜繩」視圖（plan §9.3）。

各泊位的步驟集合不同（Jellyfin 七步、qBittorrent 六個鍵、來源逐站），但攤給 UI 的形狀完全
一樣，所以形狀只定義一次；`SetupStep` 是它存下來的樣子，這裡是它被讀出來的樣子。

泊位 2 與泊位 4 共用的輸入也住這裡：套件內服務自己的介面登入（`InterfaceLogin`，M4 票 07）。
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Iterable
from dataclasses import dataclass

from berth.domain import StepStatus
from berth.models import SetupStep


@dataclass(frozen=True, slots=True)
class StepView:
    step: str
    status: StepStatus
    #: 實測值：版本號、路徑、任務 id。UI 直接顯示，不翻譯。
    detail: str
    #: 失敗時服務回的原文（英文）。UI 貼在手動步驟旁邊。
    error: str


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
        StepView(step=row.key, status=row.status, detail=row.detail, error=row.error)
        for row in rows
    )


def message(exc: Exception) -> str:
    """例外的原文。空訊息的例外至少要說得出自己是哪一種。"""
    return str(exc) or type(exc).__name__
