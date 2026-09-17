"""媒體庫的端點（plan §6 inventory 群組、票 13、`.scratch/m1/library-shape.md`）。

誰進得來由門禁決定（`api/gate.py`）：不在白名單上，所以未登入一律 401。看媒體庫**不是**
管理動作，一般使用者也看得了（brief §11）。

路徑叫 `inventory` 不叫 `library`：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端的
媒體庫，而這裡盤點的是 Library Route（前端的頁面網址仍是 plan §7 的 `/library/:routeSlug`）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import SessionDep
from berth.api.schemas import JellyfinWebOut
from berth.domain import CollectionType, InventoryStatus, JellyfinPresence, MediaKind
from berth.services.deeplink import jellyfin_web
from berth.services.inventory import list_inventories, read_inventory

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryRouteOut(BaseModel):
    """切換列上的一條 Route，與兩個篩選的數字。"""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    collection_type: CollectionType
    #: 停用的 Route 仍然列出來：已經入庫的東西還在它底下。
    enabled: bool
    titles: int
    #: 有計劃停下來等人的作品數。
    review: int
    #: 現在那一份計劃裡有對不到的檔案的作品數。
    unmatched: int


class InventoryItemOut(BaseModel):
    """牆上的一格。判定規則全部在後端（`services/inventory.py`），前端只照畫。"""

    model_config = ConfigDict(from_attributes=True)

    media_id: str
    kind: MediaKind
    #: 顯示用標題（`zh-TW` 那一輪）。
    title: str
    title_en: str
    year: int | None
    poster_url: str
    #: 依序取第一個成立的：失敗 → 待審 → 下載中 → 已入庫 / 部分 / 沒有檔案。
    status: InventoryStatus
    #: 劇集：已播出的正片入庫了幾集（不含 S00）。電影：0 或 1。
    imported: int
    #: 劇集：TMDB 上已播出的正片集數。電影一律是 1。
    aired: int
    #: 電影的正片版本數；劇集是 0。
    versions: int
    needs_review: bool
    has_unmatched: bool
    #: medium 自動入庫、掛著 audit 的檔案數（跨這部作品在這條 Route 上的 Job 加總，票 15）。
    audits: int
    presence: JellyfinPresence
    #: 深連結要開的 item：劇集是 Series，電影是 Movie。沒找到時是空字串。
    jellyfin_item_id: str


class InventoryOut(BaseModel):
    route: InventoryRouteOut
    #: 深連結的主機。每一格都用同一台，所以放在牆上而不是逐格帶。
    jellyfin: JellyfinWebOut
    items: list[InventoryItemOut]


@router.get("")
async def get_inventories(session: SessionDep) -> list[InventoryRouteOut]:
    """切換列：每一條 Route 與它的作品數。"""
    return [InventoryRouteOut.model_validate(row) for row in await list_inventories(session)]


@router.get("/{slug}")
async def get_inventory(session: SessionDep, slug: str) -> InventoryOut:
    view = await read_inventory(session, slug)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such route")
    return InventoryOut(
        route=InventoryRouteOut.model_validate(view.route),
        jellyfin=JellyfinWebOut.model_validate(await jellyfin_web(session)),
        items=[InventoryItemOut.model_validate(item) for item in view.items],
    )
