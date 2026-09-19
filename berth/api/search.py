"""索引站搜尋的端點（plan §6 search 群組、票 08）。

誰進得來由門禁決定（`api/gate.py`）：`/api/search` 不在白名單上，所以未登入一律 401。
搜尋不是管理動作——送單本來就是一般使用者做的事（brief §11）。

**這一支可以很慢**：Prowlarr 收到請求之後要現場去連它認得的每一個追蹤站，實測單次
60–85 秒。前端因此要畫得出「還在問」的樣子，而不是假設它幾百毫秒就回來。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
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
    #: 這一列的身分（info hash 或 guid）。畫列表用。
    key: str
    #: 索引站報的 info hash，**只有真的是 hash 時才有值**。送單拿它短路重複檢查（票 09）。
    info_hash: str
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


#: 缺集一鍵搜的兩個參數（M1.5 票 10）。預覽與搜尋收同一組，兩支才問得出同一件事。
MissingParam = Annotated[
    bool,
    Query(description="從季表的缺集開始搜：查詢由後端依缺的季集產生，不是作品名。"),
]
SeasonParam = Annotated[
    int | None,
    Query(ge=0, description="把缺集搜尋收到這一季。只在 `missing=true` 時有意義。"),
]


@router.get("/queries")
async def get_queries(
    session: SessionDep,
    factory: ClientFactoryDep,
    media: Annotated[str, Query(description="`tv:<tmdb>` / `movie:<tmdb>`。")],
    missing: MissingParam = False,
    season: SeasonParam = None,
) -> SearchQueriesOut:
    """不打索引站，只讀快照與這部作品的入庫狀態。"""
    _refuse_bare_season(missing, season)
    return SearchQueriesOut(
        queries=list(
            await plan_queries(session, factory, media_id=media, missing=missing, season=season)
        )
    )


@router.get("")
async def get_search(
    session: SessionDep,
    factory: ClientFactoryDep,
    media: Annotated[str, Query(description="`tv:<tmdb>` / `movie:<tmdb>`。")],
    q: Annotated[
        str, Query(description="自己打的關鍵字。有值時取代作品的各個標題，只問這一個。")
    ] = "",
    missing: MissingParam = False,
    season: SeasonParam = None,
) -> SearchOut:
    _refuse_bare_season(missing, season)
    return _out(
        await search_torrents(
            session, factory, media_id=media, query=q, missing=missing, season=season
        )
    )


def _refuse_bare_season(missing: bool, season: int | None) -> None:
    """`season` 單獨帶著沒有意義——它是「缺集搜尋收到那一季」的參數。

    默默當成整部作品搜的話，手改網址的人會拿到他沒有要的那一份，而畫面上沒有任何地方說得出
    差別。照實拒絕，形狀與其餘的拒絕一樣（`{reason, detail}`）。
    """
    if season is not None and not missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"reason": "season_without_missing", "detail": "season needs missing=true"},
        )


def _out(view: SearchView) -> SearchOut:
    return SearchOut(
        rows=[SearchResultOut.model_validate(row) for row in view.rows],
        total=view.total,
        discarded=view.discarded,
        attempts=[StepOut.model_validate(attempt) for attempt in view.attempts],
        problem=view.problem,
        detail=view.detail,
    )
