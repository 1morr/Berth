"""對真的 qBittorrent Web API 說話（brief §20.2、§20.7）。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    AuthFailedError,
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.qbittorrent import (
    BAN_MARKER,
    IpBannedError,
    MaindataCursor,
    QbittorrentCategory,
    QbittorrentVersion,
    TorrentAdd,
    TorrentFile,
    TorrentRejectedError,
    TorrentStatus,
    add_form,
)

#: `torrents/add` 對「不收這一個」用的狀態碼。實測兩種成因（見 `_reason`）。
CONFLICT = 409

#: 登入端點上「被封了」的狀態碼。**帳密錯不是這一個**（4.4.5 是 200 + `Fails.`，
#: 5.2.3 是 401），所以這裡的 403 只有一個意思。
FORBIDDEN = 403


class HttpQbittorrentClient:
    r"""免密路徑：compose 內的 Berth 在 `WebUI\AuthSubnetWhitelist` 上，不需要登入。

    既有服務要憑證時 `app/version` 會回 403，由 `HttpSession` 翻成 `AuthFailedError`；
    使用者在精靈第 2 步填了帳密就先 `login` 換 SID，之後的請求帶著它。
    """

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = base_url
        # Host 檢查除了網域還比對 port，所以 base URL 必須就是使用者實際連的那一個（brief §20.7）。
        self._session = HttpSession(base_url, headers={"Referer": base_url}, timeout=timeout)
        # rid 的狀態與這條連線同生死：qBittorrent 把它掛在 SID 上（2026-09-10 實測，
        # 不帶 cookie 的話每一輪都是 `full_update`），而 httpx 的 client 會自己帶 cookie。
        self._cursor = MaindataCursor()

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
            "POST",
            "/api/v2/auth/login",
            data={"username": username, "password": password},
            # 403 要看得到 body 才分得出「被封了」與「帳密不對」（`IpBannedError`）。
            tolerate=(FORBIDDEN,),
        )
        body = response.text.strip()
        if response.status_code == FORBIDDEN:
            if BAN_MARKER in body.lower():
                raise IpBannedError(f"auth/login: {body}")
            raise AuthFailedError(f"auth/login: 403 {body}")
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

    async def add_torrent(self, request: TorrentAdd) -> None:
        """`torrents/add`。**成功的形狀隨版本不同**（2026-09-10 對 5.2.3 實測）：

        - 4.4.x：`200` + body `Ok.`。
        - 5.2.3（API 2.15.1）：`200` + 一份 JSON 摘要
          （`{"added_torrent_ids": […], "failure_count": 0, "success_count": 1}`）。

        失敗也說得出話——這正是 Berth 自己先把 torrent 抓下來的回報（`adapters/torrent.py`）：
        交出去的是磁力連結或位元組時 qBittorrent **當場**答得出收不收，而交一條 http 網址
        時它回 `202` + `pending_count: 1` 然後在背景抓，抓失敗就再也沒有下文。

        - `409 Conflict`：不收。實測兩種成因——**它已經有同一個 hash 的 torrent**，
          以及 category 的 save path 當下用不了。訊息兩種都說出來，因為 body 只有一個
          `Conflict`，光靠它使用者查不出是哪一種。
        - `415`：那份 `.torrent` 不是有效的 torrent（body 帶檔名與原因）。
        """
        version = await self.version()
        files = (
            {"torrents": (request.filename, request.content, "application/x-bittorrent")}
            if request.content
            else None
        )
        response = await self._session.request(
            "POST",
            "/api/v2/torrents/add",
            data=add_form(request, version),
            files=files,
            tolerate=(409, 415),
        )
        if response.status_code == 200 and _accepted(response):
            return
        raise TorrentRejectedError(f"torrents/add: {response.status_code} {_reason(response)}")

    async def delete_torrent(self, info_hash: str, *, delete_files: bool) -> None:
        """`torrents/delete`（2026-09-22 對 4.1.0–5.2.3 逐個 tag 核對原始碼，brief §20.2）。

        兩件事是照著原始碼寫的，不是照著直覺：

        - **`deleteFiles` 只認字面 `true` / `false`**（`Utils::String::parseBool`，大小寫不敏感）。
          `1` 不是真，是「解析不出來」→ 退回 `false`，於是呼叫端以為檔案刪了而磁碟上還在。
          兩個參數都是必填，少一個是 400。
        - **一律 POST**。4.4.5 以前 GET 也行，4.5.0 起 `torrents/delete` 進了 POST 白名單，
          GET 從此是 405；Berth 接得了的最低版本涵蓋兩邊，所以只用兩邊都成立的那一種。

        成功是 200 + 空 body，**而且它沒有這個 hash 時也是 200**——不必先問一次它還在不在。
        """
        await self._session.request(
            "POST",
            "/api/v2/torrents/delete",
            data={"hashes": info_hash, "deleteFiles": "true" if delete_files else "false"},
        )

    async def sync(self) -> tuple[TorrentStatus, ...]:
        """`sync/maindata?rid=N`。合併由 `MaindataCursor` 做，這裡只負責問與檢查形狀。"""
        path = f"/api/v2/sync/maindata?rid={self._cursor.rid}"
        payload = json_body(await self._session.get(path))
        if not isinstance(payload, dict):
            raise ProtocolMismatchError("sync/maindata: expected an object")
        return self._cursor.apply(payload)

    async def files(self, info_hash: str) -> tuple[TorrentFile, ...]:
        """`torrents/files?hash=…`。

        metadata 還沒到時它回 `200` + `[]`（實測 4.4.5 與 5.2.3 皆然），所以「空的」與
        「這個 torrent 不存在」在這一支上分不出來——呼叫端要先看 state（plan §3.1）。
        """
        payload = json_body(await self._session.get(f"/api/v2/torrents/files?hash={info_hash}"))
        if not isinstance(payload, list):
            raise ProtocolMismatchError("torrents/files: expected an array")
        return tuple(
            TorrentFile(
                index=int(row.get("index", position)),
                name=str(row.get("name", "")),
                size=int(row.get("size", 0) or 0),
                priority=int(row.get("priority", 1)),
                progress=float(row.get("progress", 0.0) or 0.0),
            )
            for position, row in enumerate(payload)
            if isinstance(row, dict)
        )

    async def aclose(self) -> None:
        await self._session.aclose()


def _accepted(response: httpx.Response) -> bool:
    """這一次 `torrents/add` 真的被收下了嗎。

    **不是「2xx 就算成功」**：`202` 是「網址收下了，之後再去抓」（`pending_count`），
    而那條路徑的失敗永遠不會回來（brief §20.7）。Berth 只交磁力連結或位元組，所以
    收下就是 `200`，而 `200` 有兩種 body。
    """
    body = response.text.strip()
    if body == "Ok.":
        return True
    try:
        summary = response.json()
    except ValueError:
        return False
    if not isinstance(summary, dict):
        return False
    return summary.get("failure_count") == 0 and summary.get("success_count", 0) > 0


def _reason(response: httpx.Response) -> str:
    """被拒的原文，加上一句「這個狀態碼在這支端點上是什麼意思」。

    body 常常只有一個 `Conflict`——那串字對使用者說不出下一步（PRODUCT 原則 4）。
    """
    body = " ".join(response.text.split())[:120]
    if response.status_code == CONFLICT:
        return (
            f"{body} (qBittorrent already has this torrent, "
            "or the category's save path is unusable)"
        )
    return body
