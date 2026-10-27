"""網路搜尋的替身：回一份固定的頁面，記下每一次收到的查詢（M5 票 17）。

測試與演練伺服器共用（同 `adapters/ai/fake.py`）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from berth.adapters.http import ServiceError
from berth.adapters.websearch import WebPage


@dataclass(frozen=True, slots=True)
class Searched:
    query: str
    domains: tuple[str, ...]
    max_results: int
    #: 拿 client 時給的 key。
    api_key: str


@dataclass
class FakeWebSearch:
    pages: list[WebPage] = field(default_factory=list)
    #: 給了就每一次都丟它（演出 key 被拒、限流）。
    error: ServiceError | None = None
    api_key: str = ""
    searched: list[Searched] = field(default_factory=list)

    async def search(
        self, query: str, *, domains: Sequence[str], max_results: int
    ) -> list[WebPage]:
        self.searched.append(Searched(query, tuple(domains), max_results, self.api_key))
        if self.error is not None:
            raise self.error
        return list(self.pages[:max_results])
