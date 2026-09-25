"""`/rss` 的端點（plan §6 rss 群組、brief §15、M3 票 08）。

整組只有 admin（門禁的 `ADMIN_PREFIXES`）：Mikan 聚合 feed 的網址帶著 token，它就是憑證；而綁定會
替整個家送單。規則不掛在這裡的相依上。

plan 原本那一組 `rss/rules` 在 2026-09-24 改成 RSS Series（brief §15）：綁定是 `PUT` 一個
`binding` 子資源、解除是 `DELETE` 同一個，與 Jellyfin 的 `UserPlayedItems` 成對動詞同一個形狀。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.domain import FeedItemStatus, FeedKind, RssRefusal
from berth.services.rss import (
    RssRejectedError,
    add_feed,
    bind_series,
    delete_feed,
    list_feeds,
    list_items,
    list_series,
    poll_feed,
    unbind_series,
)

router = APIRouter(prefix="/rss", tags=["rss"])

#: 拒絕理由 → 狀態碼。**每一種都要在這裡**（`tests/unit/test_openapi_contract.py` 守著）。
_STATUS: dict[RssRefusal, int] = {
    RssRefusal.FEED_MISSING: status.HTTP_404_NOT_FOUND,
    RssRefusal.FEED_UNSUPPORTED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RssRefusal.FEED_DUPLICATE: status.HTTP_409_CONFLICT,
    RssRefusal.SERIES_MISSING: status.HTTP_404_NOT_FOUND,
    #: 另一個分頁先綁了。選擇本身沒錯，重新看一次再決定。
    RssRefusal.SERIES_BOUND: status.HTTP_409_CONFLICT,
    RssRefusal.MEDIA_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RssRefusal.ROUTE_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    #: 與送單的 `route_disabled` 同一個判斷：Route 在，只是現在不收。
    RssRefusal.ROUTE_DISABLED: status.HTTP_409_CONFLICT,
    RssRefusal.ROUTE_KIND_MISMATCH: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class RssRefusalOut(BaseModel):
    """與其他群組的拒絕同形：`reason` 挑句子，`detail` 是原文或那一個 id。"""

    reason: RssRefusal
    detail: str


def _responses(*reasons: RssRefusal) -> dict[int | str, dict[str, Any]]:
    """這一支端點真的會回的那幾種（`api/jobs.py` 的 `_refusals` 同一個形狀）。"""
    return refusal_responses(RssRefusalOut, {reason: _STATUS[reason] for reason in reasons})


def rss_refusal(refusal: RssRejectedError) -> HTTPException:
    body = RssRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


class FeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    kind: FeedKind
    interval_sec: int
    last_polled_at: datetime | None
    #: 上一輪失敗的原文（英文）。空字串是上一輪好好的。
    last_error: str
    #: 這個 Feed 長出了幾筆 Item；刪除的確認說出會刪掉幾筆。
    items: int


class FeedIn(BaseModel):
    """加一個 Feed。來源種類由網址的主機認出來（這一票只認 Mikan）。"""

    url: str = Field(min_length=1)
    #: 選填，空的就用網址的主機名。
    name: str = ""


class FeedDeletedOut(BaseModel):
    #: 跟著刪掉的 Feed Item 筆數。
    items: int


class PollOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: int
    series: int
    submitted: int


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    title_raw: str
    mikan_bangumi_id: int | None
    mikan_subgroup_id: int | None
    #: `null` 是待綁定。
    media_id: str | None
    media_title: str
    media_title_en: str
    route_id: int | None
    route_name: str
    season: int | None
    episode_offset: int | None
    bound_by: str
    #: 還沒送出去的 Item：待綁定時是綁定之後會送出的那幾筆（確認區塊的「將送出 N 集」）。
    waiting: int
    #: 只有綁定回的那一份有值：這一次送出去了幾筆。
    submitted: int


class BindingIn(BaseModel):
    """綁到哪一部作品、入庫到哪一條 Route。作品要先打過 `GET /media/{id}`（它才有那一列）。"""

    media: str = Field(min_length=1)
    route: int


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feed_id: int
    title: str
    link: str
    published_at: datetime | None
    seen_at: datetime
    series_id: int | None
    status: FeedItemStatus
    job_hash: str
    #: 上一次送單被拒的原文（`reason: detail`）。
    error: str


@router.get("/feeds")
async def get_feeds(session: SessionDep) -> list[FeedOut]:
    return [FeedOut.model_validate(row) for row in await list_feeds(session)]


@router.post(
    "/feeds",
    status_code=status.HTTP_201_CREATED,
    responses=_responses(RssRefusal.FEED_UNSUPPORTED, RssRefusal.FEED_DUPLICATE),
)
async def post_feed(session: SessionDep, body: FeedIn) -> FeedOut:
    """記下這個 Feed。不當場輪詢——背景迴圈在半分鐘內輪到它，畫面上也有「立即輪詢」。"""
    try:
        return FeedOut.model_validate(await add_feed(session, url=body.url, name=body.name))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.delete("/feeds/{feed_id}", responses=_responses(RssRefusal.FEED_MISSING))
async def delete_one_feed(session: SessionDep, feed_id: int) -> FeedDeletedOut:
    try:
        return FeedDeletedOut(items=await delete_feed(session, feed_id))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.post("/feeds/{feed_id}/poll", responses=_responses(RssRefusal.FEED_MISSING))
async def post_poll(session: SessionDep, factory: ClientFactoryDep, feed_id: int) -> PollOut:
    """立刻輪這一個。抓不到 Feed 仍是 200：失敗記在那一列的 `last_error`，畫面重讀清單就看得到。"""
    try:
        return PollOut.model_validate(await poll_feed(session, factory, feed_id))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.get("/series")
async def get_series(session: SessionDep) -> list[SeriesOut]:
    """待綁定的排前面。"""
    return [SeriesOut.model_validate(row) for row in await list_series(session)]


@router.put(
    "/series/{series_id}/binding",
    responses=_responses(
        RssRefusal.SERIES_MISSING,
        RssRefusal.SERIES_BOUND,
        RssRefusal.MEDIA_MISSING,
        RssRefusal.ROUTE_MISSING,
        RssRefusal.ROUTE_DISABLED,
        RssRefusal.ROUTE_KIND_MISMATCH,
    ),
)
async def put_binding(
    session: SessionDep,
    factory: ClientFactoryDep,
    request: Request,
    series_id: int,
    body: BindingIn,
) -> SeriesOut:
    """綁定並把留著的 Item 送出去。送單被拒的那幾筆不讓這一支失敗：它們留在 `matched` 帶著原文。"""
    user = current_user(request)
    try:
        view = await bind_series(
            session,
            factory,
            series_id,
            media_id=body.media,
            route_id=body.route,
            user_id=user.id if user is not None else None,
        )
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal
    return SeriesOut.model_validate(view)


@router.delete("/series/{series_id}/binding", responses=_responses(RssRefusal.SERIES_MISSING))
async def delete_binding(session: SessionDep, series_id: int) -> SeriesOut:
    try:
        return SeriesOut.model_validate(await unbind_series(session, series_id))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.get("/items")
async def get_items(session: SessionDep) -> list[ItemOut]:
    """最近看到的 50 筆，新的在前。"""
    return [ItemOut.model_validate(row) for row in await list_items(session)]
