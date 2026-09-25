"""Prowlarr adapter（plan §8.4、§9.2、§9.3 第 6 步）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from berth.adapters.http import ServiceError


@dataclass(frozen=True, slots=True)
class ProwlarrIndexer:
    """`GET /api/v1/indexer` 的一列，也就是這台 Prowlarr 上已經有的一個索引站。"""

    id: int
    name: str
    enabled: bool
    #: 站的機器名（`nyaasi`、`thepiratebay`…）。認一個站要用它，不是會被使用者改掉的 `name`。
    definition_name: str = ""
    #: 整份資源原文。`indexer/test` 收的就是它，所以照原樣留著（field 順序與內容由 Prowlarr 決定）。
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IndexerDefinition:
    """`GET /api/v1/indexer/schema` 的一列：一個還沒被加進來的站的定義。"""

    definition_name: str
    name: str
    #: `public` / `semiPrivate` / `private`。精靈只預設勾公開站。
    privacy: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    #: BCP 47 代碼（`zh-TW`、`zh-CN`、`en-US`…）。畫面照 UI 語言換成語言名（票 06e）。
    language: str = ""
    #: 定義自帶的一句英文說明。畫面原樣顯示、不翻（同 Tags）。
    description: str = ""


class IndexerRejectedError(ServiceError):
    """Prowlarr 收到了請求但拒絕了它（400 + 逐條理由）。

    **新增索引站前 Prowlarr 會先連一次那個站**：連不上、被 CloudFlare 擋、或搜尋回不出結果
    都會讓 `POST /api/v1/indexer` 回 400，站也就沒有被建立（2026-09-08 實測，brief §20.7）。
    所以逐站的成敗是這個例外裡的訊息，不是另外一次 `indexer/test`。
    """

    def __init__(self, message: str, *, messages: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.messages = messages or (message,)


class ProwlarrClient(Protocol):
    @property
    def base_url(self) -> str: ...

    async def ping(self) -> None:
        """`GET /ping`。設了密碼之後仍然匿名 200（brief §20.7）。"""
        ...

    async def indexers(self) -> list[ProwlarrIndexer]: ...

    async def definitions(self) -> tuple[IndexerDefinition, ...]:
        """`GET /api/v1/indexer/schema`：這台 Prowlarr 認得的所有站。"""
        ...

    async def add_indexer(self, definition: IndexerDefinition) -> ProwlarrIndexer:
        """`POST /api/v1/indexer`。站連不上時丟 `IndexerRejectedError`，什麼都不會被建立。"""
        ...

    async def test_indexer(self, indexer: ProwlarrIndexer) -> None:
        """`POST /api/v1/indexer/test`：已經加進來的站現在還通不通。"""
        ...

    async def delete_indexer(self, indexer_id: int) -> None:
        """`DELETE /api/v1/indexer/{id}`（Prowlarr 的 OpenAPI，票 06e）。"""
        ...

    async def host_config(self) -> Mapping[str, Any]:
        """`GET /api/v1/config/host`。設帳密要把整份物件送回去（brief §20.7）。"""
        ...

    async def set_host_config(self, values: Mapping[str, Any]) -> None:
        """`PUT /api/v1/config/host/1`。回 202，Prowlarr 隨即自行重啟。"""
        ...

    async def aclose(self) -> None: ...


#: 新增索引站時要指定的同步設定檔。`1` 是 Prowlarr 內建的那一個（schema 給的是 `0`，
#: 直接送會建不起來）。
DEFAULT_APP_PROFILE_ID = 1

__all__ = [
    "DEFAULT_APP_PROFILE_ID",
    "IndexerDefinition",
    "IndexerRejectedError",
    "ProwlarrClient",
    "ProwlarrIndexer",
]
