"""`/rss` 的端點（plan §6 rss 群組、brief §15、M3 票 08）。

整組只有 admin（門禁的 `ADMIN_PREFIXES`）：Mikan 聚合 feed 的網址帶著 token，它就是憑證；而綁定會
替整個家送單。規則不掛在這裡的相依上。

plan 原本那一組 `rss/rules` 在 2026-09-24 改成 RSS Series（brief §15）：綁定是 `PUT` 一個
`binding` 子資源、解除是 `DELETE` 同一個，與 Jellyfin 的 `UserPlayedItems` 成對動詞同一個形狀。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.api.search import TagsOut
from berth.domain import (
    BindReasonCode,
    FeedItemStatus,
    FeedKind,
    MappingStrategy,
    MediaKind,
    PrimeMode,
    ReleaseKind,
    RssRefusal,
    SkipCode,
)
from berth.services.bangumi import read_bangumi, search_bangumi
from berth.services.oneshot import read_oneshot
from berth.services.rss import (
    RssRejectedError,
    add_feed,
    bind_series,
    delete_feed,
    list_feeds,
    list_items,
    list_series,
    poll_feed,
    preview_feed,
    prime_feed,
    read_exclusions,
    set_exclusions,
    set_feed_exclusions,
    set_series_exclusions,
    subscribe_mikan,
    subscribe_search,
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
    #: 規則寫壞了：`detail` 是 `<規則>: <原因>`，什麼都沒存。
    RssRefusal.RULE_INVALID: status.HTTP_422_UNPROCESSABLE_CONTENT,
    #: 另一個分頁先選了。重讀清單就看得到選了哪一個。
    RssRefusal.FEED_PRIMED: status.HTTP_409_CONFLICT,
    #: 與送單的 `source_unavailable` 同一個判斷：上游那一站這一刻讀不到。
    RssRefusal.FEED_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
    #: 先輪詢一次（背景半分鐘內，或「立即輪詢」）再選。
    RssRefusal.FEED_UNREAD: status.HTTP_409_CONFLICT,
    #: 上游回了東西，但不是 RSS：與 `feed_unreachable` 同樣是上游那一頭的事。
    RssRefusal.FEED_NOT_RSS: status.HTTP_502_BAD_GATEWAY,
    #: 請求預算用完（M3 票 20）：不是上游的錯，是 Berth 自己先停手；等 `detail` 說的時刻再試。
    RssRefusal.BUDGET_EXHAUSTED: status.HTTP_429_TOO_MANY_REQUESTS,
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
    #: 這一層的排除條件（一般字詞不分大小寫；`/…/` 是正則，`/…/i` 不分大小寫）。
    exclusions: list[str]
    #: 第一輪預覽選過的那一刻。`null` 是還沒選：這個 Feed 一筆都不送，畫面列出預覽（票 11）。
    #: Mikan 加的那一刻就有值。
    primed_at: datetime | None
    #: 自動綁定送進的 Route：收得下那部作品的 Route 不只一條時用它（M3 票 21）。`null` 是沒選。
    route_id: int | None


class FeedIn(BaseModel):
    """加一個 Feed。來源種類由網址的主機認出來：Mikan、Nyaa、acg.rip。"""

    url: str = Field(min_length=1)
    #: 選填，空的就用網址的主機名。
    name: str = ""
    #: 選填：自動綁定送進的 Route（照 Sonarr Import List 的 Root Folder）。收得下那部作品的
    #: Route 只有一條時用不到它；不只一條又沒選，那部就留在待綁定（`route_ambiguous`）。
    route: int | None = None


class FeedDeletedOut(BaseModel):
    #: 跟著刪掉的 Feed Item 筆數。
    items: int


class PollOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: int
    series: int
    #: 新長出的 Series 裡自動綁上的（票 09）。
    bound: int
    submitted: int
    #: Feed 本身抓不到時的原文（同那一列的 `last_error`）；抓到了是空字串。畫面照它說「這一輪
    #: 沒讀到」，而不是「新 0 筆」（M3 票 21 的 critique）。
    failed: str


class PrimeIn(BaseModel):
    """第一輪預覽選哪一個：`all` 全部下載、`later` 只追之後的。"""

    mode: PrimeMode


class PrimeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feed: FeedOut
    #: 這一次送出去的（`all` 時綁好的那幾筆）。
    submitted: int
    #: `later` 略過的。
    passed: int
    #: 第一輪被排除條件擋下的（兩個選項都不動它們）。
    excluded: int


class BindReasonOut(BaseModel):
    """自動綁定的一條理由：封閉集合的 code 加參數，句子由前端照 code 挑（`rss.grounds.*`，票 09）。

    參數是標題、日期、Route 名這種**不翻譯**的事實（`ItemReasonOut` 同一個形狀）。
    """

    model_config = ConfigDict(from_attributes=True)

    code: BindReasonCode
    params: dict[str, str | int]


class CandidateOut(BaseModel):
    """待綁定那一列給人一鍵選的作品。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: MediaKind
    title: str
    title_en: str
    year: int | None


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
    #: 自動綁定查到的結果：`bound_by` 是 `system` 時是依據，待綁定時是為什麼沒綁。沒查過是空的。
    reasons: list[BindReasonOut]
    #: 給人一鍵選的作品，照 TMDB 搜尋結果的順序。
    candidates: list[CandidateOut]
    #: 這一層的排除條件。
    exclusions: list[str]
    #: 第一批確認過了沒（票 13）：還沒的期間每一集入庫之後都等人看一眼。
    confirmed: bool
    #: 從哪一站來的；一筆 Item 都沒有的非 Mikan Series 是 `null`。
    source: FeedKind | None
    #: 發佈名讀出的字幕組。
    group: str
    #: 最近的一筆（排除條件擋下的不算）；沒有是空字串與 `null`（票 19 的詳情頁）。
    latest_title: str
    latest_at: datetime | None
    #: 只有綁定回的那一份有值：這一次送出去了幾筆。
    submitted: int


class BindingIn(BaseModel):
    """綁到哪一部作品、入庫到哪一條 Route。作品要先打過 `GET /media/{id}`（它才有那一列）。"""

    media: str = Field(min_length=1)
    route: int
    #: Mikan 的 RSS Series 同時補舊集（票 12）：讀單一 feed，聚合 feed 沒帶到的那幾集一起送。
    #: `false` 時綁定之前發佈的舊集記成略過（之後的每日補漏也是）。
    backfill: bool = True


class SkipReasonOut(BaseModel):
    """一筆 Item 為什麼沒送出去：code 加參數，句子由前端照 code 挑（`rss.skip.*`，票 10）。"""

    model_config = ConfigDict(from_attributes=True)

    code: SkipCode
    params: dict[str, str | int]


class RulesIn(BaseModel):
    """一層的排除條件，整組覆寫。寫壞的那一條讓整組都不存（422 `rule_invalid`）。"""

    rules: list[str]


class ExclusionsIn(RulesIn):
    """全域那一層：規則加上合集預設。"""

    #: 預設只排合集：不是單集的不自動下載。
    not_single: bool


class ExclusionsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    not_single: bool
    rules: list[str]


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
    #: `excluded` / `duplicate` 的那一條理由；其他狀態是 `null`。重複的那一種連到的 Job 在
    #: `job_hash`。
    skip: SkipReasonOut | None
    #: 近似的位元組數，只供顯示（三站都不準）；來源不報時 `null`。
    size: int | None


class OneshotIn(BaseModel):
    """一次性 RSS 連結（票 18）。網址放在 body：Mikan 聚合 feed 的網址帶 token，不進 query。"""

    url: str = Field(min_length=1)
    #: 選了作品之後才給：季集照它的 TMDB 快照換算。作品要先打過 `GET /media/{id}`。
    media: str | None = None
    #: 與 `media` 一起給時比帳本（同一個資料夾裡有沒有同一個版本）。
    route: int | None = None


class OneshotItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guid: str
    title: str
    link: str
    #: 送單時放進 `POST /jobs` 的 `source.url`：`.torrent` 網址，或站只給的 magnet。
    url: str
    info_hash: str
    size: int | None
    published_at: datetime | None
    #: 合集、區間也照樣勾得了：排除條件只作用在自動下載（brief §15）。
    release_kind: ReleaseKind
    tags: TagsOut
    #: 選了作品時是照它換算的預估（搜尋結果表同一個算法），沒選時是發佈名寫的。
    season: int | None
    episode_start: int | None
    episode_end: int | None
    whole_season: bool
    strategy: MappingStrategy | None
    #: 同一個 info hash 的 Job 已經在了；沒有是空字串。
    job_hash: str
    #: 帳本已有同一個版本：媒體庫裡的檔名。沒給作品與 Route 時是 `null`。
    known: str | None


class OneshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: FeedKind
    #: 照 feed 的順序（新的在前）。
    items: list[OneshotItemOut]


@router.post(
    "/oneshot",
    responses=_responses(
        RssRefusal.FEED_UNSUPPORTED,
        RssRefusal.FEED_UNREACHABLE,
        RssRefusal.FEED_NOT_RSS,
        RssRefusal.BUDGET_EXHAUSTED,
        RssRefusal.MEDIA_MISSING,
        RssRefusal.ROUTE_MISSING,
    ),
)
async def post_oneshot(
    session: SessionDep, factory: ClientFactoryDep, body: OneshotIn
) -> OneshotOut:
    """讀一條 RSS 網址的每一筆。**只讀**：不建 Feed、不長 RSS Series，勾好的那幾筆走 `POST /jobs`。

    `POST` 是因為網址放在 body，不是因為它改了什麼。
    """
    try:
        view = await read_oneshot(
            session, factory, body.url, media_id=body.media, route_id=body.route
        )
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal
    return OneshotOut.model_validate(view)


@router.get("/feeds")
async def get_feeds(session: SessionDep) -> list[FeedOut]:
    return [FeedOut.model_validate(row) for row in await list_feeds(session)]


@router.post(
    "/feeds",
    status_code=status.HTTP_201_CREATED,
    responses=_responses(
        RssRefusal.FEED_UNSUPPORTED, RssRefusal.FEED_DUPLICATE, RssRefusal.ROUTE_MISSING
    ),
)
async def post_feed(session: SessionDep, body: FeedIn) -> FeedOut:
    """記下這個 Feed。不當場輪詢——背景迴圈在半分鐘內輪到它，畫面上也有「立即輪詢」。"""
    try:
        view = await add_feed(session, url=body.url, name=body.name, route_id=body.route)
        return FeedOut.model_validate(view)
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


@router.get("/feeds/{feed_id}/preview", responses=_responses(RssRefusal.FEED_MISSING))
async def get_preview(session: SessionDep, feed_id: int) -> list[ItemOut]:
    """這個 Feed 的每一筆，新的在前，說出各自會怎樣：待綁定、會送出、排除、重複（票 11）。

    重複是當場看的（只讀）；送單時還會再看一次。
    """
    try:
        return [ItemOut.model_validate(row) for row in await preview_feed(session, feed_id)]
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.post(
    "/feeds/{feed_id}/prime",
    responses=_responses(
        RssRefusal.FEED_MISSING,
        RssRefusal.FEED_PRIMED,
        RssRefusal.FEED_UNREACHABLE,
        RssRefusal.FEED_UNREAD,
    ),
)
async def post_prime(
    session: SessionDep, factory: ClientFactoryDep, feed_id: int, body: PrimeIn
) -> PrimeOut:
    """選第一輪。`later` 當場再讀一次 feed（讀不到是 502 `feed_unreachable`，什麼都沒改）；
    還沒讀過的 Feed 不收 `all`（409 `feed_unread`）。"""
    try:
        return PrimeOut.model_validate(await prime_feed(session, factory, feed_id, mode=body.mode))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.put(
    "/feeds/{feed_id}/exclusions",
    responses=_responses(RssRefusal.FEED_MISSING, RssRefusal.RULE_INVALID),
)
async def put_feed_exclusions(session: SessionDep, feed_id: int, body: RulesIn) -> FeedOut:
    """整組覆寫這個 Feed 的排除條件；它還沒送出去的 Item 照新規則再看一次。"""
    try:
        return FeedOut.model_validate(await set_feed_exclusions(session, feed_id, body.rules))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.get("/exclusions")
async def get_exclusions(session: SessionDep) -> ExclusionsOut:
    """全域那一層。"""
    return ExclusionsOut.model_validate(await read_exclusions(session))


@router.put("/exclusions", responses=_responses(RssRefusal.RULE_INVALID))
async def put_exclusions(session: SessionDep, body: ExclusionsIn) -> ExclusionsOut:
    """整組覆寫全域那一層。放寬不把已經擋下的放回來（brief §15）。"""
    try:
        view = await set_exclusions(session, not_single=body.not_single, rules=body.rules)
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal
    return ExclusionsOut.model_validate(view)


@router.get("/series")
async def get_series(session: SessionDep, media: str | None = None) -> list[SeriesOut]:
    """待綁定的排前面。給 `media` 時只列綁在那部作品上的（詳情頁，票 19）。"""
    return [SeriesOut.model_validate(row) for row in await list_series(session, media_id=media)]


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
    """綁定並把留著的 Item 送出去，Mikan 的同時補舊集。送單被拒的那幾筆不讓這一支失敗：它們留在
    `matched` 帶著原文。"""
    user = current_user(request)
    try:
        view = await bind_series(
            session,
            factory,
            series_id,
            media_id=body.media,
            route_id=body.route,
            user_id=user.id if user is not None else None,
            backfill=body.backfill,
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


@router.put(
    "/series/{series_id}/exclusions",
    responses=_responses(RssRefusal.SERIES_MISSING, RssRefusal.RULE_INVALID),
)
async def put_series_exclusions(session: SessionDep, series_id: int, body: RulesIn) -> SeriesOut:
    """整組覆寫這個 RSS Series 的排除條件；它還沒送出去的 Item 照新規則再看一次。"""
    try:
        return SeriesOut.model_validate(await set_series_exclusions(session, series_id, body.rules))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.get("/items")
async def get_items(session: SessionDep) -> list[ItemOut]:
    """最近看到的 50 筆，新的在前。"""
    return [ItemOut.model_validate(row) for row in await list_items(session)]


# --- 從 Media 頁訂閱（票 19） ---------------------------------------------


class BangumiHitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    #: Mikan 上的中文名（多半是簡體），原樣。
    title: str


class SubgroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    #: 最近一次發佈的日期；讀不到是 `null`。
    updated: date | None
    #: 這一組在這個番組下的發佈筆數。
    releases: int
    #: 最新一筆的發佈名（看得出語言、解析度）。
    latest: str
    #: 這一組的 RSS Series 已經綁在哪一部作品上；沒有是 `null`。
    bound_to: str | None


class BangumiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    premiere: date | None
    #: 照番組頁左欄的順序。
    subgroups: list[SubgroupOut]


class MikanSubscriptionIn(BaseModel):
    """訂閱一個 Mikan 番組 × 字幕組並綁到這部作品。作品要先打過 `GET /media/{id}`。"""

    media: str = Field(min_length=1)
    route: int
    bangumi: int
    subgroup: int
    #: Feed 的名字；空的就用網址的主機名。
    name: str = ""
    #: 補舊集（票 12）：`false` 時綁定之前發佈的記成略過。
    backfill: bool = True


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feed: FeedOut
    #: `submitted` 是這一次送出去的（整季）。
    series: SeriesOut


class SearchSubscriptionIn(BaseModel):
    """以作品的一個標題建 Nyaa / acg.rip 搜尋 feed，它長出的 RSS Series 都綁到這部作品。"""

    media: str = Field(min_length=1)
    route: int
    kind: FeedKind
    term: str = Field(min_length=1)


_BINDING_REFUSALS = (
    RssRefusal.MEDIA_MISSING,
    RssRefusal.ROUTE_MISSING,
    RssRefusal.ROUTE_DISABLED,
    RssRefusal.ROUTE_KIND_MISMATCH,
)


@router.get(
    "/mikan/search",
    responses=_responses(RssRefusal.FEED_UNREACHABLE, RssRefusal.BUDGET_EXHAUSTED),
)
async def get_mikan_search(
    factory: ClientFactoryDep, q: str = Query(min_length=1)
) -> list[BangumiHitOut]:
    """Mikan 搜尋頁上的番組。英文、羅馬字、日文、繁中都搜得到（brief §20.12）。"""
    try:
        return [BangumiHitOut.model_validate(hit) for hit in await search_bangumi(factory, q)]
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.get(
    "/mikan/bangumi/{bangumi_id}",
    responses=_responses(RssRefusal.FEED_UNREACHABLE, RssRefusal.BUDGET_EXHAUSTED),
)
async def get_mikan_bangumi(
    session: SessionDep, factory: ClientFactoryDep, bangumi_id: int
) -> BangumiOut:
    """一個番組的字幕組，每一組說出是不是已經綁在某部作品上。"""
    try:
        return BangumiOut.model_validate(await read_bangumi(session, factory, bangumi_id))
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal


@router.post(
    "/subscriptions/mikan",
    status_code=status.HTTP_201_CREATED,
    responses=_responses(
        RssRefusal.SERIES_BOUND,
        RssRefusal.FEED_DUPLICATE,
        RssRefusal.FEED_UNREACHABLE,
        RssRefusal.BUDGET_EXHAUSTED,
        *_BINDING_REFUSALS,
    ),
)
async def post_mikan_subscription(
    session: SessionDep, factory: ClientFactoryDep, request: Request, body: MikanSubscriptionIn
) -> SubscriptionOut:
    """建單一 feed、綁上它的 RSS Series、送出整季（或只追之後的）。那個 Series 已經在待綁定時
    就地綁它，不多開 Feed。讀不到單一 feed 是 502，什麼都沒加。"""
    user = current_user(request)
    try:
        done = await subscribe_mikan(
            session,
            factory,
            bangumi_id=body.bangumi,
            subgroup_id=body.subgroup,
            media_id=body.media,
            route_id=body.route,
            user_id=user.id if user is not None else None,
            name=body.name,
            backfill=body.backfill,
        )
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal
    return SubscriptionOut.model_validate(done)


@router.post(
    "/subscriptions/search",
    status_code=status.HTTP_201_CREATED,
    responses=_responses(
        RssRefusal.FEED_UNSUPPORTED, RssRefusal.FEED_DUPLICATE, *_BINDING_REFUSALS
    ),
)
async def post_search_subscription(
    session: SessionDep, factory: ClientFactoryDep, request: Request, body: SearchSubscriptionIn
) -> FeedOut:
    """建搜尋 feed 並當場讀一輪：第一輪預覽（`GET /rss/feeds/{id}/preview`）馬上有東西。讀不到
    仍是 201，原文在 `last_error`。"""
    user = current_user(request)
    try:
        feed = await subscribe_search(
            session,
            factory,
            kind=body.kind,
            term=body.term,
            media_id=body.media,
            route_id=body.route,
            user_id=user.id if user is not None else None,
        )
    except RssRejectedError as refusal:
        raise rss_refusal(refusal) from refusal
    return FeedOut.model_validate(feed)
