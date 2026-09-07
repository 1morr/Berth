"""Prowlarr adapter（plan §8.4、§9.2）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProwlarrIndexer:
    """`GET /api/v1/indexer` 的一列。精靈第 2 步只看有沒有，逐站設定在票 08。"""

    id: int
    name: str
    enabled: bool


class ProwlarrClient(Protocol):
    @property
    def base_url(self) -> str: ...

    async def ping(self) -> None:
        """`GET /ping`。設了密碼之後仍然匿名 200（brief §20.7）。"""
        ...

    async def indexers(self) -> list[ProwlarrIndexer]: ...

    async def aclose(self) -> None: ...


__all__ = ["ProwlarrClient", "ProwlarrIndexer"]
