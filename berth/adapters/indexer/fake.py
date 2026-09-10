"""測試與前端演練用的索引站搜尋替身。

一份而不是兩份：`ProwlarrSearch` 與 `TorznabSearch` 對呼叫端來說是同一個介面，而
services 那一層要驗的是**多標題展開、合併去重、逐查詢成敗**——那些邏輯不認得協定，
所以替身也不必分兩種。協定本身的差異由對錄製回應的契約測試守著。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from berth.adapters.indexer import IndexerResult, SearchCapability, SearchQuery


class FakeIndexerSearch:
    def __init__(
        self,
        *,
        base_url: str = "http://prowlarr:9696",
        results: Sequence[IndexerResult] = (),
        by_query: Mapping[str, Sequence[IndexerResult]] | None = None,
        capability: SearchCapability | None = None,
        error: Exception | None = None,
        errors: Mapping[str, Exception] | None = None,
    ) -> None:
        self.base_url = base_url
        self._results = tuple(results)
        #: 逐查詢的回答。多標題展開要驗的正是「每個標題各拿到不同的東西」。
        self._by_query = {key: tuple(value) for key, value in (by_query or {}).items()}
        self._capability = capability or SearchCapability()
        self.error = error
        #: 逐查詢的失敗。單一查詢垮掉不該把整次搜尋一起拖下水（票 08 驗收）。
        self._errors = dict(errors or {})
        #: 收到過的查詢，順序即呼叫順序。
        self.queries: list[SearchQuery] = []
        self.closed = False

    async def capabilities(self) -> SearchCapability:
        if self.error is not None:
            raise self.error
        return self._capability

    async def search(self, query: SearchQuery) -> tuple[IndexerResult, ...]:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        failure = self._errors.get(query.text)
        if failure is not None:
            raise failure
        return self._by_query.get(query.text, self._results)

    async def aclose(self) -> None:
        self.closed = True
