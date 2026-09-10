"""對真的 Torznab 端點說話（plan §8.4）。"""

from __future__ import annotations

from xml.etree import ElementTree

import httpx

from berth.adapters.http import DEFAULT_TIMEOUT_SECONDS, HttpSession, ProtocolMismatchError
from berth.adapters.torznab import TorznabCaps, TorznabSearchMode


class HttpTorznabClient:
    """位址是使用者貼的整條 Torznab 網址，key 走 `apikey` 查詢參數（Torznab 的慣例）。"""

    def __init__(
        self, base_url: str, api_key: str = "", *, timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._session, self._path = torznab_session(base_url, timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def caps(self) -> TorznabCaps:
        params = {"t": "caps"}
        if self._api_key:
            params["apikey"] = self._api_key
        response = await self._session.request("GET", self._path, params=params)
        return parse_caps(response.text)

    async def aclose(self) -> None:
        await self._session.aclose()


def torznab_session(base_url: str, *, timeout: float) -> tuple[HttpSession, str]:
    """把使用者貼的整條 Torznab 網址拆成「來源 + 路徑」。

    Torznab 的位址是**整條網址**（Jackett 的 `/api/v2.0/indexers/all/results/torznab/api`
    之類），不是一個服務根。`HttpSession` 的 base URL 只放來源，路徑逐次帶上——否則
    httpx 會在後面補一條斜線，而有些端點對它很敏感。

    精靈的 `HttpTorznabClient` 與票 08 的 `TorznabSearch` 打的是同一條網址，所以這一段
    只寫一次：拆錯了兩邊要一起錯，才看得出來是這裡的問題。
    """
    url = httpx.URL(base_url)
    return HttpSession(f"{url.scheme}://{url.netloc.decode()}", timeout=timeout), url.path or "/"


def parse_caps(text: str) -> TorznabCaps:
    """`?t=caps` 的 XML → `TorznabCaps`。

    精靈用它回答「這個端點還通不通」，票 08 用它回答「能不能用 tmdbid 搜」。同一份 XML
    兩個問題，解析寫兩份的話其中一份遲早會先過期。
    """
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ProtocolMismatchError("t=caps: response is not XML") from exc
    if root.tag != "caps":
        raise ProtocolMismatchError(f"t=caps: root element is <{root.tag}>, not <caps>")

    server = root.find("server")
    return TorznabCaps(
        server_title=server.get("title", "") if server is not None else "",
        search=_mode(root.find("searching/search")),
        tv=_mode(root.find("searching/tv-search")),
        movie=_mode(root.find("searching/movie-search")),
        categories=tuple(
            category.get("name", "") for category in root.findall("categories/category")
        ),
    )


def _mode(element: ElementTree.Element | None) -> TorznabSearchMode:
    if element is None:
        return TorznabSearchMode()
    params = element.get("supportedParams", "")
    return TorznabSearchMode(
        available=element.get("available") == "yes",
        params=frozenset(part.strip().lower() for part in params.split(",") if part.strip()),
    )
