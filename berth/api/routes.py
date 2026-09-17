"""Route 設定頁的端點（plan §6 routes 群組、brief §4.3、票 14）。

誰進得來由門禁決定（`api/gate.py`）：與 `settings/*` 一樣永遠只有管理員（票 14a）。精靈第 7 步的
「刪除」走自己的 `DELETE /setup/routes/{id}`（`api/setup.py`），跟著 `setup/*` 的規則。規則不掛在
這裡的相依上：新掛的端點什麼都不做就已經在門後。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.schemas import RouteOut
from berth.services.routes import (
    RouteInUseError,
    RouteRejectedError,
    check_route,
    create_route,
    delete_route,
    list_libraries,
    list_routes,
    update_route,
)

router = APIRouter(tags=["routes"])

#: 拒絕理由 → 狀態碼。沒列的是 422：這個選擇本身無效（媒體庫不在、不是它的路徑、目標被佔了）。
_STATUS = {
    "route_missing": status.HTTP_404_NOT_FOUND,
    "route_in_use": status.HTTP_409_CONFLICT,
    "route_unhealthy": status.HTTP_409_CONFLICT,
    #: 建立時撞上唯一索引（鎖外的寫入搶先了）。選擇本身沒錯，再按一次就好。
    "route_conflict": status.HTTP_409_CONFLICT,
    #: 與登入同一個判斷（plan §6 auth）：Jellyfin 連不上不是使用者選錯了。
    "jellyfin_unreachable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


class ManagedRouteOut(BaseModel):
    """設定頁上的一列：Route 本身，加上有多少東西指著它——刪不得的時候，按下去之前就說得出為什麼。"""

    route: RouteOut
    #: 送到這條 Route 的下載。
    jobs: int
    #: 目標落在它底下的帳本（帳本不記 Route，以目標路徑認它）。
    ledger_entries: int
    #: 刪不得。規則只在後端一份（`RouteUsage.in_use`），畫面照它決定給不給刪除鍵。
    in_use: bool


class LibraryPathOut(BaseModel):
    """媒體庫回報的一條路徑。"""

    model_config = ConfigDict(from_attributes=True)

    path: str
    #: 已經寫在這條路徑的 Route 名，沒有就是 `null`。同一個目標不會有第二條 Route。
    route_name: str | None


class LibraryOptionOut(BaseModel):
    """新增 Route 時可選的一個 Jellyfin 媒體庫（現查）。"""

    model_config = ConfigDict(from_attributes=True)

    item_id: str
    name: str
    collection_type: str
    #: Jellyfin 回報的順序；被佔用的帶著 Route 名。
    paths: list[LibraryPathOut]
    #: Berth 建得了 Route 的類型（movies / tvshows）。
    supported: bool
    uses_tvdb: bool


class RouteIn(BaseModel):
    """新增一條 Route。目標必須是那個媒體庫回報的路徑之一（brief §4.1）。"""

    #: Jellyfin virtual folder 的 `ItemId`。同一個媒體庫可以有好幾條 Route，所以不用名字認。
    library_id: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    name: str = Field(min_length=1)


class RouteEditIn(BaseModel):
    """修改一條 Route。slug 與目標路徑建立之後不能改（使用者拍板，理由在 `update_route`）。"""

    name: str = Field(min_length=1)
    enabled: bool


@router.get("/routes")
async def get_routes(session: SessionDep) -> list[ManagedRouteOut]:
    """全部 Route 與它們的引用數。不連線。"""
    return [
        ManagedRouteOut(
            route=RouteOut.model_validate(row.route),
            jobs=row.usage.jobs,
            ledger_entries=row.usage.ledger_entries,
            in_use=row.usage.in_use,
        )
        for row in await list_routes(session)
    ]


@router.post("/routes")
async def post_route(session: SessionDep, factory: ClientFactoryDep, body: RouteIn) -> RouteOut:
    """新增，並立刻跑五條纜繩。**檢查紅燈不是 4xx**：Route 照樣建立、維持停用，紅的那一條
    回在 `checks` 裡——與精靈第 7 步同一個規矩。"""
    try:
        view = await create_route(
            session,
            factory,
            library_id=body.library_id,
            target_path=body.target_path,
            name=body.name,
        )
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal
    return RouteOut.model_validate(view)


@router.put("/routes/{route_id}")
async def put_route(
    session: SessionDep, factory: ClientFactoryDep, route_id: int, body: RouteEditIn
) -> RouteOut:
    """修改並重跑檢查。從停用到啟用而檢查是紅的：409 `route_unhealthy`，名稱照樣存下。"""
    try:
        view = await update_route(
            session,
            factory,
            route_id,
            name=body.name,
            enabled=body.enabled,
        )
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal
    return RouteOut.model_validate(view)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route_endpoint(session: SessionDep, route_id: int) -> None:
    """明確的刪除（二次確認在前端）。被 Job 或帳本引用：409 `route_in_use`，出路是停用。"""
    try:
        await delete_route(session, route_id)
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal


@router.post("/routes/{route_id}/check")
async def post_route_check(
    session: SessionDep, factory: ClientFactoryDep, route_id: int
) -> RouteOut:
    """重新檢查這一條。只是診斷，不動 `enabled`。"""
    try:
        view = await check_route(session, factory, route_id)
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal
    return RouteOut.model_validate(view)


@router.get("/jellyfin/libraries")
async def get_jellyfin_libraries(
    session: SessionDep, factory: ClientFactoryDep
) -> list[LibraryOptionOut]:
    """Jellyfin 現在的媒體庫與路徑，標出哪些路徑已經有 Route（plan §6 routes 群組）。"""
    try:
        options = await list_libraries(session, factory)
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal
    return [LibraryOptionOut.model_validate(row) for row in options]


def route_refusal(refusal: RouteRejectedError) -> HTTPException:
    """與送單的拒絕同形（`api/jobs.py`）：`reason` 給畫面挑句子，`detail` 是原文。

    刪除被拒時另帶 `jobs`、`ledger_entries`（與 `GET /routes` 同一組詞），畫面說得出數字。
    精靈的刪除（`api/setup.py`）走同一支，兩個入口的拒絕長得一樣。
    """
    body: dict[str, object] = {"reason": refusal.reason, "detail": refusal.detail}
    if isinstance(refusal, RouteInUseError):
        body |= {"jobs": refusal.usage.jobs, "ledger_entries": refusal.usage.ledger_entries}
    return HTTPException(
        status_code=_STATUS.get(refusal.reason, status.HTTP_422_UNPROCESSABLE_CONTENT),
        detail=body,
    )
