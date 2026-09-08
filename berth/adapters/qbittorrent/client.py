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
        """成功與失敗的形狀隨版本不同（brief §20.2，2026-09-08 對兩個版本實測）：

        - 4.4.5：成功 `200` + `Ok.`，帳密錯也是 `200`，body 才是 `Fails.`。
        - 5.2.3：成功 `204` 空 body，帳密錯 `401`（`HttpSession` 已翻成 `AuthFailedError`）。

        免密白名單上的 client 一律回 204（帳密錯也是），那也是成功——套件內的 Berth 本來就
        不需要帳密進得去。

        成功只有那兩種形狀，所以其餘的 2xx 判為連到了別的東西：位址填錯打到反向代理時，
        那一台很可能回 `200` 加一頁 HTML 登入表單，當成登入成功會一路錯到後面才爆。
        """
        response = await self._session.request(
            "POST", "/api/v2/auth/login", data={"username": username, "password": password}
        )
        body = response.text.strip()
        if body == "Fails.":
            raise AuthFailedError("auth/login: rejected")
        if body not in ("", "Ok."):
            raise ProtocolMismatchError("auth/login: not a qBittorrent reply")

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

    async def create_category(self, name: str, save_path: str) -> None:
        """表單欄位是 `category` 與 `savePath`（駝峰，與讀回來的鍵一致）。

        per-category 的未完成路徑不送：Berth 只用全域的 `temp_path`（plan §4.2）。
        """
        await self._session.request(
            "POST",
            "/api/v2/torrents/createCategory",
            data={"category": name, "savePath": save_path},
        )

    async def aclose(self) -> None:
        await self._session.aclose()
