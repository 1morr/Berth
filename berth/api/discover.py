"""探索與搜尋的端點（plan §6 discover 群組、票 03）。

誰進得來由門禁決定（`api/gate.py`）：`/api/discover/*` 不在白名單上，所以未登入一律 401，
前端據此導向 `/login`。探索不是管理動作，一般使用者也進得來。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.domain import MediaKind, TmdbProblem
from berth.services.discover import DiscoverResult, read_popular, read_trending, search_media

router = APIRouter(prefix="/discover", tags=["discover"])


class DiscoverItemOut(BaseModel):
    """牆上的一格。"""

    model_config = ConfigDict(from_attributes=True)

    #: `tv:<tmdb>` / `movie:<tmdb>`，也是 `/media/:id` 的路徑段（票 04）。
    id: str
    tmdb_id: int
    kind: MediaKind
    #: 顯示用標題（`zh-TW` 有就用它）。
    title: str
    #: 英文標題。與 `title` 不同時卡片兩個都顯示——檔名用的是這一個（brief §7.5）。
    title_en: str
    year: int | None
    #: 完整的海報網址；沒有海報時是空字串，卡片自己畫沒有海報的樣子。
    poster_url: str


class DiscoverOut(BaseModel):
    """一個 feed 的回應。

    **失敗也是 200**：一頁上有三個 feed，其中一個拿不到 TMDB 時另外兩個照樣畫得出來，
    而畫面要說得出下一步。把它做成 HTTP 錯誤的話，前端只剩一個狀態碼，分不出
    「還沒填憑證」與「TMDB 連不上」——那兩件事的修法完全不同（票 03 驗收）。
    """

    items: list[DiscoverItemOut]
    #: 拿不到東西的理由。正常時是 `None`。
    problem: TmdbProblem | None
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    detail: str


@router.get("/trending")
async def get_trending(session: SessionDep, factory: ClientFactoryDep) -> DiscoverOut:
    return _out(await read_trending(session, factory))


@router.get("/popular")
async def get_popular(session: SessionDep, factory: ClientFactoryDep) -> DiscoverOut:
    return _out(await read_popular(session, factory))


@router.get("/search")
async def get_search(
    session: SessionDep,
    factory: ClientFactoryDep,
    q: Annotated[str, Query(description="搜尋詞。空白的查詢回空清單而不是錯誤。")],
) -> DiscoverOut:
    return _out(await search_media(session, factory, q))


def _out(result: DiscoverResult) -> DiscoverOut:
    return DiscoverOut(
        items=[DiscoverItemOut.model_validate(item) for item in result.items],
        problem=result.problem,
        detail=result.detail,
    )
