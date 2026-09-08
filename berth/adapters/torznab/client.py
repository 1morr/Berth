"""對真的 Torznab 端點說話（plan §8.4）。"""

from __future__ import annotations

from xml.etree import ElementTree

import httpx

from berth.adapters.http import DEFAULT_TIMEOUT_SECONDS, HttpSession, ProtocolMismatchError
from berth.adapters.torznab import TorznabCaps


class HttpTorznabClient:
    """位址是使用者貼的整條 Torznab 網址，key 走 `apikey` 查詢參數（Torznab 的慣例）。"""

    def __init__(
        self, base_url: str, api_key: str = "", *, timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        # Torznab 的位址是**整條網址**（Jackett 的 `/api/v2.0/indexers/all/results/torznab/api`
        # 之類），不是一個服務根。`HttpSession` 的 base URL 只放來源，路徑逐次帶上——
        # 否則 httpx 會在後面補一條斜線，而有些端點對它很敏感。
        url = httpx.URL(base_url)
        self._path = url.path or "/"
        self._session = HttpSession(f"{url.scheme}://{url.netloc.decode()}", timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def caps(self) -> TorznabCaps:
        params = {"t": "caps"}
        if self._api_key:
            params["apikey"] = self._api_key
        response = await self._session.request("GET", self._path, params=params)
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError as exc:
            raise ProtocolMismatchError("t=caps: response is not XML") from exc
        if root.tag != "caps":
            raise ProtocolMismatchError(f"t=caps: root element is <{root.tag}>, not <caps>")

        server = root.find("server")
        search = root.find("searching/search")
        return TorznabCaps(
            server_title=server.get("title", "") if server is not None else "",
            search_available=search is not None and search.get("available") == "yes",
            categories=tuple(
                category.get("name", "") for category in root.findall("categories/category")
            ),
        )

    async def aclose(self) -> None:
        await self._session.aclose()
