"""Torznab adapter（plan §8.4）。

任意 Torznab 端點：Jackett 的聚合網址、Prowlarr 的單站網址，或別的什麼。M0 只用 `t=caps`
—— 它同時證明位址對、key 對、而且那一端真的是 Torznab。搜尋在 M1。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TorznabSearchMode:
    """`<search>` / `<tv-search>` / `<movie-search>` 各一種問法。

    `available` 與 `params` 分開，因為它們回答不同的問題：「這個端點做不做這種搜尋」與
    「它認得哪些參數」。私站的 `tv-search` 認得 `tmdbid`，公開站只認 `q`（票 08 實測），
    而兩者的 `available` 都是 `yes`。
    """

    available: bool = False
    #: `supportedParams` 逗號切開的集合，原樣小寫（`q`、`season`、`ep`、`tmdbid`…）。
    params: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class TorznabCaps:
    """`?t=caps` 回的 XML 裡 Berth 用得到的部分。"""

    server_title: str = ""
    #: 泛用搜尋（`t=search`）。沒有它這個端點對 Berth 沒有用處。
    search: TorznabSearchMode = TorznabSearchMode()
    #: `t=tvsearch` 與 `t=movie`。票 08 依它們的 `supportedParams` 決定能不能用 tmdbid 搜。
    tv: TorznabSearchMode = TorznabSearchMode()
    movie: TorznabSearchMode = TorznabSearchMode()
    #: `<categories><category name=…>` 的名字，畫面顯示前幾個當作證據。
    categories: tuple[str, ...] = ()


class TorznabClient(Protocol):
    @property
    def base_url(self) -> str: ...

    async def caps(self) -> TorznabCaps:
        """key 不對時丟 `AuthFailedError`（Torznab 回 401）。"""
        ...

    async def aclose(self) -> None: ...


__all__ = ["TorznabCaps", "TorznabClient", "TorznabSearchMode"]
