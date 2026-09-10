"""索引站搜尋的端點（plan §6 search 群組、票 08）。

誰進得來由門禁決定（`api/gate.py`）：`/api/search` 不在白名單上，所以未登入一律 401。
搜尋不是管理動作——送單本來就是一般使用者做的事（brief §11）。

**這一支可以很慢**：Prowlarr 收到請求之後要現場去連它認得的每一個追蹤站，實測單次
60–85 秒。前端因此要畫得出「還在問」的樣子，而不是假設它幾百毫秒就回來。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.schemas import StepOut
from berth.domain import IndexerProblem, MappingStrategy, Source
from berth.services.search import SearchView, plan_queries, search_torrents

router = APIRouter(prefix="/search", tags=["search"])


class TagsOut(BaseModel):
    """會進檔名的那幾格（brief §6.8）。

    送結構化欄位而不是 `render()` 的那一串字：結果表要逐格顯示（來源一欄、解析度一欄），
    而字串只能整條印出來。畫面要那一串字時自己拼——拼法在 `Tags.render()`，不在這裡。
    """

    model_config = ConfigDict(from_attributes=True)

    source: Source | None
    resolution: str
    #: 字幕語言 token（`CHS` / `CHT` / `JP` / `EN`），已照 brief §6.8 的順序排好。
    subs: list[str]
    hardsub: bool
    group: str
    version: str
    edition: str


class SearchResultOut(BaseModel):
    """結果表的一列（brief §13）。"""

    model_config = ConfigDict(from_attributes=True)

    #: 發佈名，原樣。解析器讀的就是它，所以畫面顯示的也是同一串字。
    title: str
    #: 哪一個站。Prowlarr 聚合時逐筆不同。
    indexer: str
    #: 位元組。索引站沒說時是 0，畫面顯示 `—`。
    size: int
    #: `null` = 那個站沒報做種數，與 0 不是同一件事。
    seeders: int | None
    info_url: str
    #: 票 09 送單時交給 qBittorrent 的那一條。
    download_url: str
    #: 這一列的身分（info hash 或 guid）。
    key: str
    tags: TagsOut
    #: 預估季集。`season` 與 `episode_start` 都是 `null` = 判斷不出來（結果表的第三種說法）。
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 這個範圍蓋掉那一季 TMDB 已知的每一集——畫面才說得出「S03 全季」。
    whole_season: bool
    #: 季集是怎麼算出來的。畫面只讀 `movie`——「這一格沒有季集是因為它是電影」。
    strategy: MappingStrategy | None


class SearchOut(BaseModel):
    """一次搜尋的回應。

    **拿不到索引站時仍然是 200**（與探索頁同一個道理，票 03）：「還沒接」「連不上」
    「憑證被拒」的下一步完全不同，做成 HTTP 錯誤的話前端只剩一個狀態碼分不出來。
    """

    rows: list[SearchResultOut]
    #: 對得上這部作品的總筆數。`rows` 只有其中的前 100 筆，逐站輪流取，畫面用兩個數字說得出差別。
    total: int
    #: 索引站回了、但名字對不上這部作品的筆數。畫面用它說「那一千五百筆不是這部作品」。
    discarded: int
    #: 實際問出去的關鍵字與逐個的成敗。形狀與精靈的纜繩一樣。
    attempts: list[StepOut]
    problem: IndexerProblem | None
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    detail: str


class SearchQueriesOut(BaseModel):
    """搜尋**之前**畫面要說的那句話：Berth 會拿這幾個名字去問。"""

    queries: list[str]


@router.get("/queries")
async def get_queries(
    session: SessionDep,
    factory: ClientFactoryDep,
    media: Annotated[str, Query(description="`tv:<tmdb>` / `movie:<tmdb>`。")],
    route: Annotated[
        int | None, Query(description="換這條 Route 的 profile 算一次（anime 多兩個季號變體）。")
    ] = None,
) -> SearchQueriesOut:
    """不打索引站，只讀快照——所以改 Route 時可以隨手重問。"""
    return SearchQueriesOut(
        queries=list(await plan_queries(session, factory, media_id=media, route_id=route))
    )


@router.get("")
async def get_search(
    session: SessionDep,
    factory: ClientFactoryDep,
    media: Annotated[str, Query(description="`tv:<tmdb>` / `movie:<tmdb>`。")],
    q: Annotated[
        str, Query(description="自己打的關鍵字。有值時取代作品的各個標題，只問這一個。")
    ] = "",
    route: Annotated[
        int | None,
        Query(
            description=(
                "**這一輪搜尋的偏好，不是承諾**（票 04b）：只用來決定 anime profile 要不要"
                "加季號變體，不寫進 `media`，也不代表之後一定送到那條 Route。"
            )
        ),
    ] = None,
) -> SearchOut:
    return _out(await search_torrents(session, factory, media_id=media, query=q, route_id=route))


def _out(view: SearchView) -> SearchOut:
    return SearchOut(
        rows=[SearchResultOut.model_validate(row) for row in view.rows],
        total=view.total,
        discarded=view.discarded,
        attempts=[StepOut.model_validate(attempt) for attempt in view.attempts],
        problem=view.problem,
        detail=view.detail,
    )
