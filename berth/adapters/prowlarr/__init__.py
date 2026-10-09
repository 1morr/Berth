"""Prowlarr adapter（plan §8.4、§9.2、§9.3 第 6 步）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from berth.adapters.http import ServiceError
from berth.adapters.versions import parse_version
from berth.domain import SiteFailure
from berth.redact import redact_queries

#: 支援下限（brief §16.4、§20.14，M4 票 17，`docs/research/prowlarr-version-floor.md`）：Berth
#: 用到的每一支端點都有的第一個 stable。卡住它的只有匿名的 `GET /ping`（1.3.0.2757 的 develop
#: 版才加進來，第一個 stable 是 1.3.2.3006）；其餘端點與欄位從第一個 tag 0.1.0.361 就有。
MIN_VERSION = (1, 3, 2)


@dataclass(frozen=True, slots=True)
class ProwlarrStatus:
    """`GET /api/v1/system/status` 裡 Berth 讀的那一欄。要 API key，所以它也順便驗了 key。"""

    #: 四段的版號，例如 `2.0.5.5160`。
    version: str

    @property
    def supported(self) -> bool:
        """這台 Prowlarr 夠新嗎。讀不出版號的當成不支援，與 Jellyfin 同一條規則。"""
        return parse_version(self.version) >= MIN_VERSION


def unsupported_message(version: str) -> str:
    """版本太舊時的原文（英文）。精靈與健康檢查共用同一句，因為那是同一個事實。"""
    floor = ".".join(str(part) for part in MIN_VERSION)
    return (
        f"Prowlarr {version or 'with no version string'} is older than {floor}, "
        "the oldest version Berth supports"
    )


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
    #: 與定義同一組（`IndexerDefinition`）：已加入的站自己帶著，列已加入的站不必再讀 schema
    #: （M4 票 09）。
    privacy: str = ""
    language: str = ""
    description: str = ""
    protocol: str = ""


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
    #: `torrent` / `usenet`。Berth 只接 qBittorrent，公開站清單只收 torrent（M4 票 09）。
    protocol: str = ""


class IndexerRejectedError(ServiceError):
    """Prowlarr 收到了請求但拒絕了它（400 + 逐條理由）。

    **新增索引站前 Prowlarr 會先連一次那個站**：連不上、被 CloudFlare 擋、或搜尋回不出結果
    都會讓 `POST /api/v1/indexer` 回 400，站也就沒有被建立（2026-09-08 實測，brief §20.7）。
    所以逐站的成敗是這個例外裡的訊息，不是另外一次 `indexer/test`。
    """

    def __init__(self, message: str, *, messages: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        # 逐條理由是 Prowlarr 的原文，照樣寫進畫面與資料庫，網址的 query 值同 `ServiceError` 遮掉。
        self.messages = tuple(redact_queries(one) for one in messages or (message,))


#: Prowlarr 原文裡認得出來的片段 → 理由（brief §20.7 錄下的實測原文）。順序即優先序。
_FAILURE_MARKS: tuple[tuple[str, SiteFailure], ...] = (
    ("cloudflare", SiteFailure.CLOUDFLARE),
    ("but no results", SiteFailure.NO_RESULTS),
    ("unable to connect", SiteFailure.UNREACHABLE),
)


def failure_of(messages: tuple[str, ...]) -> SiteFailure:
    """Prowlarr 拒絕一個站的理由是哪一種（M4 票 09）。任何一條認得出來就是那一種。"""
    text = " ".join(messages).lower()
    return next((failure for mark, failure in _FAILURE_MARKS if mark in text), SiteFailure.OTHER)


class ProwlarrClient(Protocol):
    @property
    def base_url(self) -> str: ...

    async def ping(self) -> None:
        """`GET /ping`。設了密碼之後仍然匿名 200（brief §20.7）。"""
        ...

    async def status(self) -> ProwlarrStatus:
        """`GET /api/v1/system/status`：版本（M4 票 17）。"""
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

    async def test_definition(self, definition: IndexerDefinition) -> None:
        """同一支 `indexer/test`，送的是還沒加入的定義：通不通，什麼都不建立（M4 票 09）。

        不通丟 `IndexerRejectedError`，理由與新增那一支同一種形狀。
        """
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
    "MIN_VERSION",
    "IndexerDefinition",
    "IndexerRejectedError",
    "ProwlarrClient",
    "ProwlarrIndexer",
    "ProwlarrStatus",
    "failure_of",
    "unsupported_message",
]
