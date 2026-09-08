"""對真的 qBittorrent Web API 說話（brief §20.2、§20.7）。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    AuthFailedError,
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.qbittorrent import QbittorrentCategory, QbittorrentVersion


class HttpQbittorrentClient:
    r"""免密路徑：compose 內的 Berth 在 `WebUI\AuthSubnetWhitelist` 上，不需要登入。

    既有服務要憑證時 `app/version` 會回 403，由 `HttpSession` 翻成 `AuthFailedError`；
    使用者在精靈第 2 步填了帳密就先 `login` 換 SID，之後的請求帶著它。
    """

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = base_url
        # Host 檢查除了網域還比對 port，所以 base URL 必須就是使用者實際連的那一個（brief §20.7）。
        self._session = HttpSession(base_url, headers={"Referer": base_url}, timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def login(self, username: str, password: str) -> None:
        """`auth/login` 成功回 `Ok.`，帳密錯回 200 + `Fails.`——不是 401（brief §20.2）。"""
        response = await self._session.request(
            "POST", "/api/v2/auth/login", data={"username": username, "password": password}
        )
        if response.text.strip() != "Ok.":
            raise AuthFailedError("auth/login: rejected")

    async def version(self) -> QbittorrentVersion:
        app = await self._session.get("/api/v2/app/version")
        webapi = await self._session.get("/api/v2/app/webapiVersion")
        return QbittorrentVersion(app=app.text.strip(), webapi=webapi.text.strip())

    async def preferences(self) -> Mapping[str, Any]:
        payload = json_body(await self._session.get("/api/v2/app/preferences"))
        if not isinstance(payload, dict):
            raise ProtocolMismatchError("app/preferences: expected an object")
        return payload

    async def set_preferences(self, values: Mapping[str, Any]) -> None:
        """收的是表單裡一個叫 `json` 的欄位，不是 JSON body。"""
        await self._session.request(
            "POST", "/api/v2/app/setPreferences", data={"json": json.dumps(dict(values))}
        )

    async def categories(self) -> tuple[QbittorrentCategory, ...]:
        """鍵名兩種都收：4.4.5 與 5.2.3 實測都是 `savePath`，`save_path` 只出現在
        4.4.0–4.4.1，而那兩版仍在支援範圍內（brief §20.7）。
        """
        payload = json_body(await self._session.get("/api/v2/torrents/categories"))
        if not isinstance(payload, dict):
            raise ProtocolMismatchError("torrents/categories: expected an object")
        return tuple(
            QbittorrentCategory(
                name=str(row.get("name", name)),
                save_path=str(row.get("savePath", row.get("save_path", ""))),
            )
            for name, row in payload.items()
            if isinstance(row, dict)
        )

    async def aclose(self) -> None:
        await self._session.aclose()
