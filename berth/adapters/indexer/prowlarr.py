"""Prowlarr 的 REST 搜尋（plan §8.4、brief §20.7）。

Prowlarr **刻意不提供跨站聚合的 Torznab 端點**，所以聚合搜尋只能走 `GET /api/v1/search`。
回的是 `ReleaseResource` 陣列，逐筆帶著它來自哪一個站。

逾時給得很寬：這一支不是問一台伺服器，是叫它替你去問五個追蹤站。2026-09-10 實測單次
冷查詢 60–85 秒，三個查詢**併發**共 35 秒——併發是對的，短逾時不是。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from berth.adapters.http import (
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.indexer import (
    IndexerResult,
    SearchCapability,
    SearchQuery,
    normalise_info_hash,
)

#: 一次搜尋要 Prowlarr 現場去連五個站。實測 60–85 秒（冷），所以不能用探測的 5 秒。
SEARCH_TIMEOUT_SECONDS = 120.0


class ProwlarrSearch:
    def __init__(
        self, base_url: str, api_key: str = "", *, timeout: float = SEARCH_TIMEOUT_SECONDS
    ) -> None:
        self._base_url = base_url
        headers = {"X-Api-Key": api_key} if api_key else {}
        self._session = HttpSession(base_url, headers=headers, timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def capabilities(self) -> SearchCapability:
        """REST 的搜尋只認關鍵字（brief §20.7 的參數表），所以沒有 tmdbid 那條路。

        不發請求：這一支答得出來的東西是 Prowlarr 的 API 形狀，不是某一台伺服器的狀態。
        「這台通不通」是精靈與健康檢查的問題，由 `ProwlarrClient` 回答。
        """
        return SearchCapability(searchable=True, tmdb_id=frozenset())

    async def search(self, query: SearchQuery) -> tuple[IndexerResult, ...]:
        payload = json_body(
            await self._session.request(
                "GET",
                "/api/v1/search",
                params={
                    "query": query.text,
                    "type": "search",
                    "indexerIds": [str(each) for each in query.indexer_ids],
                },
            )
        )
        if not isinstance(payload, list):
            raise ProtocolMismatchError("/api/v1/search: expected a list")
        return tuple(_result(row) for row in payload if isinstance(row, dict) and "title" in row)

    async def aclose(self) -> None:
        await self._session.aclose()


def _result(row: Mapping[str, Any]) -> IndexerResult:
    return IndexerResult(
        title=str(row.get("title", "")),
        indexer=str(row.get("indexer", "")),
        size=int(row.get("size") or 0),
        seeders=_count(row.get("seeders")),
        leechers=_count(row.get("leechers")),
        # 磁力站沒有 `downloadUrl`，Prowlarr 把磁力也包成自己的代理網址；兩者都餵得進
        # qBittorrent（票 09），所以這裡只要一條能用的就好。
        download_url=str(row.get("downloadUrl") or row.get("magnetUrl") or ""),
        info_url=str(row.get("infoUrl", "")),
        info_hash=normalise_info_hash(str(row.get("infoHash") or "")),
        guid=str(row.get("guid", "")),
        published_at=_published(row.get("publishDate")),
        categories=_categories(row.get("categories")),
    )


def _count(value: Any) -> int | None:
    """做種數。那個站沒報時是 `None`——與「真的沒有人做種」不是同一件事。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _published(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _categories(value: Any) -> tuple[int, ...]:
    """只取最上層的 `id`。

    `subCategories` 是**那個站的定義**認得的子分類，不是這一筆發佈的分類——照收的話
    每一筆都會多出十個它根本不屬於的碼。
    """
    if not isinstance(value, list):
        return ()
    return tuple(
        int(row["id"]) for row in value if isinstance(row, dict) and isinstance(row.get("id"), int)
    )
