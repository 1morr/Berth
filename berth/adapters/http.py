"""adapter 共用的 HTTP 外殼：逾時、錯誤分類（plan §1.4、§8）。

每個 adapter 把 httpx 的例外翻成這裡的四種，services 只認這四種而不認 httpx。
分類的重點是**「服務不在」與「服務還沒起來」要分得開**：前者是使用者把它從
`COMPOSE_PROFILES` 拿掉了，該立刻顯示既有服務的表單；後者只是容器還在啟動，該繼續等。
"""

from __future__ import annotations

import socket
from types import TracebackType
from typing import Any, Self

import httpx

#: 探測用的逾時。容器啟動中通常是 connect 就失敗，不需要等太久（plan §9.3 第 2 步）。
DEFAULT_TIMEOUT_SECONDS = 5.0


class ServiceError(Exception):
    """與某個外部服務往來時的失敗。"""


class ServiceNotDeployedError(ServiceError):
    """主機名解不到 —— 這個服務不在 compose 套件裡。"""


class ServiceUnavailableError(ServiceError):
    """主機名解得到但連不上或逾時，通常是容器還在啟動。"""


class AuthFailedError(ServiceError):
    """服務要求憑證（401 / 403）。"""


class ServiceBusyError(ServiceError):
    """連得上、也是對的服務，但它還在載入（503）。

    Jellyfin 重啟後每一支端點都會有一段時間回 503「伺服器載入中」，所以「還沒好」必須與
    「壞了」分得開：前者該繼續輪詢，後者該把手動步驟攤給使用者看（brief §20.7）。
    """


class ProtocolMismatchError(ServiceError):
    """連得上，但回的東西不是預期的那個服務。"""


class HttpSession:
    """一個 base URL 的非同步 HTTP 工作階段，回傳已分類的錯誤。"""

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers or {},
            timeout=timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, *, timeout: float | None = None) -> httpx.Response:
        """`timeout` 只給少數「冷啟動時很慢」的端點覆寫（Prowlarr 的 `indexer/schema`）。"""
        if timeout is None:
            return await self.request("GET", path)
        return await self.request("GET", path, timeout=timeout)

    def set_header(self, name: str, value: str) -> None:
        """換掉一個標頭。憑證是可變的：Jellyfin 的初始精靈匿名開始，之後才有 token。"""
        self._client.headers[name] = value

    async def request(
        self, method: str, path: str, *, tolerate: tuple[int, ...] = (), **kwargs: Any
    ) -> httpx.Response:
        """`tolerate` 裡的狀態碼原樣回傳，不翻成例外。

        給「服務用 4xx 講一件有內容的事」那種端點用：Prowlarr 新增索引站失敗時回的是
        400 加一份逐條理由，那份理由正是畫面要顯示的東西，翻成例外就丟掉了。
        """
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            if is_dns_failure(exc):
                raise ServiceNotDeployedError(f"{method} {path}: host does not resolve") from exc
            raise ServiceUnavailableError(f"{method} {path}: connection refused") from exc
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f"{method} {path}: {type(exc).__name__}") from exc

        if response.status_code in tolerate:
            return response
        if response.status_code in (401, 403):
            raise AuthFailedError(f"{method} {path}: {response.status_code}")
        if response.status_code == 503:
            raise ServiceBusyError(f"{method} {path}: 503 still loading")
        if response.status_code >= 400:
            raise ProtocolMismatchError(f"{method} {path}: {response.status_code}")
        return response


def json_body(response: httpx.Response) -> Any:
    """回應必須是 JSON；不是就當成「連到了別的東西」。"""
    try:
        return response.json()
    except ValueError as exc:
        raise ProtocolMismatchError(f"{response.request.url}: response is not JSON") from exc


def is_dns_failure(exc: BaseException) -> bool:
    """走例外鏈找 `socket.gaierror`。

    連不上與解不到在 httpx 都是 `ConnectError`，光看型別分不出來，只能從鏈上認。
    實測 compose 網路內解不到服務名的完整鏈是（2026-09-07，容器內對 Docker 內建 DNS）：

        httpx.ConnectError → httpcore.ConnectError → socket.gaierror(-5)

    **兩層的接法不同**：httpx 用 `raise ... from exc`（`__cause__`），httpcore 在
    `except` 區塊裡重拋（`__context__`）。只走 `__cause__` 會在第二層斷掉，把「服務不在
    compose 裡」誤判成「還在啟動」，害使用者白等兩分鐘。所以兩條都要走。
    """
    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        if isinstance(current, socket.gaierror):
            return True
        seen.add(id(current))
        pending.extend(link for link in (current.__cause__, current.__context__) if link)
    return False
