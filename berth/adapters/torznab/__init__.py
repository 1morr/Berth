"""Torznab adapter（plan §8.4）。

任意 Torznab 端點：Jackett 的聚合網址、Prowlarr 的單站網址，或別的什麼。M0 只用 `t=caps`
—— 它同時證明位址對、key 對、而且那一端真的是 Torznab。搜尋在 M1。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TorznabCaps:
    """`?t=caps` 回的 XML 裡精靈要顯示的部分。"""

    server_title: str
    #: `<searching><search available="yes">`。沒有它這個端點對 Berth 沒有用處。
    search_available: bool
    #: `<categories><category name=…>` 的名字，畫面顯示前幾個當作證據。
    categories: tuple[str, ...]


class TorznabClient(Protocol):
    @property
    def base_url(self) -> str: ...

    async def caps(self) -> TorznabCaps:
        """key 不對時丟 `AuthFailedError`（Torznab 回 401）。"""
        ...

    async def aclose(self) -> None: ...


__all__ = ["TorznabCaps", "TorznabClient"]
