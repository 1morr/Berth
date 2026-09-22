"""替這位使用者經手的 Jellyfin item：圖（plan §6、M1.5 票 04）與標記已看 / 未看（票 05）。

- **圖**：路徑與 `tag` 沿用 Jellyfin 自己的 `/Items/{id}/Images/{type}?tag=`
  （研究 library-browsing.md §6、§7），尺寸換成具名的 `size`（TMDB 圖片網址的 `w342` 那種做法），
  不收 Jellyfin 的 `fillWidth` 之類的數字。判定在 `services/jellyfin_images.py`。
- **已看**：`POST`（標為已看）/ `DELETE`（標為未看）`/items/{id}/played`。動詞成對沿用 Jellyfin 的
  `/UserPlayedItems/{id}`，使用者不在網址上（GitHub `PUT|DELETE /user/starred/...` 的做法）：
  它只從 session 來（`services/jellyfin_access.py`）。回寫入之後的觀看狀態，前端拿它改牆上那一格，
  不必重抓整面牆（jellyfin-web 收到 `UserDataChanged` 也是就地改卡片）。

- **繼續觀看與下一集**（`GET /watching`，票 07）：首頁上方的兩列，這個人的整個帳號。媒體庫頁那兩列是
  `GET /inventory/{id}/watching`，形狀相同（`watching_out`）。
- **選季選集的一季**（`GET /shows/{id}/episodes?season_id=`，票 08）：Media 詳情的觀看區換季時
  問。整個觀看區是 `GET /media/{id}/watch`（`api/media.py`）。

誰進得來由門禁決定（`api/gate.py`）：不在白名單上，所以要登入；寫入另要 CSRF 標頭。
`/jellyfin/libraries` 那一支是管理員的，這幾組都不是（`ADMIN_PREFIXES` 只收那一支）。
"""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from berth.api.deps import AccessCacheDep, ClientFactoryDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.api.schemas import (
    JellyfinWebOut,
    WatchEpisodeOut,
    WatchingCardOut,
    WatchingOut,
    WatchStateOut,
)
from berth.domain import AccessRefusal, ImageSize, JellyfinImageType
from berth.services.auth import AuthenticatedUser
from berth.services.deeplink import jellyfin_web
from berth.services.jellyfin_access import (
    AccountDisabledError,
    ItemNotVisibleError,
    JellyfinUnreachableError,
    LibraryNotVisibleError,
    SortNotOfferedError,
    jellyfin_access,
)
from berth.services.jellyfin_images import ImageMissingError, read_image
from berth.services.watch_area import WatchEpisode, read_episodes
from berth.services.watching import Watching, WatchingCard, read_watching

router = APIRouter(prefix="/jellyfin", tags=["jellyfin"])

#: Jellyfin 的 item id 與 `ImageTags` 都是 32 個小寫十六進位字元（研究 §6）。
#: **item id 會進 Jellyfin 的路徑**，所以別的形狀（`..`）不轉發。
HEX32 = r"^[0-9a-f]{32}$"

#: `/api` 底下唯一不是 `no-store` 的回應（門禁只替沒設 `Cache-Control` 的回應補 `no-store`）。
#:
#: 網址帶著 `ImageTags`，Jellyfin 換圖時網址就變，所以一年、`immutable`（重新整理也不重問）。
#: `private`：回應在門後，前置代理不該存一份給沒登入的人。
IMAGE_CACHE_CONTROL = "private, max-age=31536000, immutable"

#: 圖是 Jellyfin 那一端的內容（管理員上傳的、metadata 來源給的），卻從 Berth 的網域送出去。直接開
#: 這個網址時，一張 SVG 裡的 script 會帶著 Berth 的 session 跑；`<img>` 裡本來就不執行。照 GitHub 送
#: 使用者內容（`raw.githubusercontent.com`）的標頭：不載入任何東西、沙箱化，也不讓瀏覽器猜型別。
IMAGE_HEADERS = {
    "Cache-Control": IMAGE_CACHE_CONTROL,
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
}


class AccessRefusalOut(BaseModel):
    """權限閘門說不行的那一份，與送單和 Route 的拒絕同形（`api/jobs.py`、`api/routes.py`）。

    **說得出理由的拒絕是答案不是故障**，所以前端拿到它就不重試（`retryUnlessRefused`）。
    是 model 而不是手組的 dict，前端才從 OpenAPI 取得到 `AccessRefusal`——它原本在
    `web/src/api/jellyfin.ts` 是手抄的，而且抄漏了 `sort_not_offered`（M2 票 02）。
    """

    reason: AccessRefusal
    detail: str


#: `services/jellyfin_access.py` 丟的例外 → 畫面認得的那個理由。媒體庫與這一組共用。
_REFUSALS: dict[type[Exception], AccessRefusal] = {
    AccountDisabledError: AccessRefusal.ACCOUNT_DISABLED,
    LibraryNotVisibleError: AccessRefusal.LIBRARY_NOT_VISIBLE,
    ItemNotVisibleError: AccessRefusal.ITEM_NOT_VISIBLE,
    JellyfinUnreachableError: AccessRefusal.JELLYFIN_UNREACHABLE,
    SortNotOfferedError: AccessRefusal.SORT_NOT_OFFERED,
}

#: 理由 → 狀態碼。**每一種都要在這裡**（`tests/unit/test_openapi_contract.py` 守著）。
#:
#: - `account_disabled`（401）：session 已經結束，前端照「登入失效」處理。
#: - `library_not_visible` / `item_not_visible`（404）：沒有權限與不存在是同一個回應。
#: - `jellyfin_unreachable`（503）：`detail` 是服務回的原文。
#: - `sort_not_offered`（422）：這一種媒體庫的排序選單上沒有這個鍵（票 06）。
_STATUS: dict[AccessRefusal, int] = {
    AccessRefusal.ACCOUNT_DISABLED: status.HTTP_401_UNAUTHORIZED,
    AccessRefusal.LIBRARY_NOT_VISIBLE: status.HTTP_404_NOT_FOUND,
    AccessRefusal.ITEM_NOT_VISIBLE: status.HTTP_404_NOT_FOUND,
    AccessRefusal.JELLYFIN_UNREACHABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    AccessRefusal.SORT_NOT_OFFERED: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def access_responses(*errors: type[Exception]) -> dict[int | str, dict[str, Any]]:
    """這一支端點回得出來的那幾種，**用它 `except` 的那一組例外說**。

    逐端點列而不是整份倒出來：標記已看碰不到媒體庫與排序鍵，文件把它們寫上去只會讓讀的人
    以為要處理。收例外而不是收理由，是為了讓 decorator 與 `except` 吃同一個 tuple——
    兩份各寫一次的話，多接一種例外時文件不會跟著變。
    """
    picked = {_REFUSALS[error]: _STATUS[_REFUSALS[error]] for error in errors}
    return refusal_responses(AccessRefusalOut, picked)


#: 整個帳號的那兩列碰不到媒體庫（不帶 `parentId`），所以只有這兩種。
WATCHING_REFUSALS = (AccountDisabledError, JellyfinUnreachableError)

#: 一季的集：劇與季的可見性由 Jellyfin 查，看不到是 `item_not_visible`。
EPISODES_REFUSALS = (AccountDisabledError, ItemNotVisibleError, JellyfinUnreachableError)


def access_refusal(refusal: Exception) -> HTTPException:
    """`{reason, detail}`，與 Route 設定頁的拒絕同形（`api/routes.py`）。"""
    reason = _REFUSALS[type(refusal)]
    body = AccessRefusalOut(reason=reason, detail=str(refusal))
    return HTTPException(_STATUS[reason], body.model_dump(mode="json"))


def image_url(item_id: str, image_type: JellyfinImageType, *, size: ImageSize, tag: str) -> str:
    """卡片上的圖片網址。**`tag` 一定要是 DTO 的 `ImageTags`**：錯的 tag Jellyfin 一樣回圖，
    而這個網址被快取一年。`/api` 是 `main.API_PREFIX`（api 不 import main）。"""
    query = urlencode({"size": size.value, "tag": tag})
    return f"/api/jellyfin/items/{item_id}/images/{image_type.value}?{query}"


@router.get(
    "/items/{item_id}/images/{image_type}",
    response_class=Response,
    responses={
        200: {"content": {"image/webp": {}}, "description": "縮好的圖"},
        404: {"description": "`image_missing`：Jellyfin 沒有這張圖"},
        503: {"description": "`jellyfin_unreachable`：問不到 Jellyfin"},
    },
)
async def get_image(
    session: SessionDep,
    factory: ClientFactoryDep,
    item_id: Annotated[str, Path(pattern=HEX32)],
    image_type: JellyfinImageType,
    size: ImageSize,
    tag: Annotated[str, Query(pattern=HEX32)],
) -> Response:
    try:
        image = await read_image(session, factory, item_id, image_type, size=size, tag=tag)
    except ImageMissingError as missing:
        # `image_missing` 只有這一支說得出來，所以它不在 `AccessRefusal` 裡；前端不解析它
        # （圖是 `<img>` 的來源，壞掉就是 `onError`）。
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"reason": "image_missing", "detail": str(missing)}
        ) from missing
    except JellyfinUnreachableError as refusal:
        # 與其餘每一支同一種拒絕，所以走同一支（`JellyfinUnreachableError` 的 `str()` 就是
        # `detail`）。自己組一份的話那個理由字串會有兩個來源。
        raise access_refusal(refusal) from refusal
    return Response(
        image.content,
        media_type=image.content_type,
        headers=IMAGE_HEADERS,
    )


@router.get(
    "/watching",
    responses=access_responses(*WATCHING_REFUSALS),
)
async def get_watching(
    session: SessionDep, factory: ClientFactoryDep, cache: AccessCacheDep, request: Request
) -> WatchingOut:
    """首頁上方的繼續觀看與下一集：這個人整個帳號的（不帶媒體庫，Jellyfin 才照他的權限限縮）。"""
    try:
        async with jellyfin_access(session, factory, cache, session_user(request)) as access:
            watching = await read_watching(access, None)
    except WATCHING_REFUSALS as refusal:
        raise access_refusal(refusal) from refusal
    return await watching_out(session, watching)


async def watching_out(session: SessionDep, watching: Watching) -> WatchingOut:
    """首頁與媒體庫頁共用的形狀。圖片網址在這一層組：services 只知道 Jellyfin 的 tag。"""
    return WatchingOut(
        jellyfin=JellyfinWebOut.model_validate(await jellyfin_web(session)),
        resume=[_watching_card(card) for card in watching.resume],
        next_up=[_watching_card(card) for card in watching.next_up],
    )


def _watching_card(card: WatchingCard) -> WatchingCardOut:
    image = card.image
    return WatchingCardOut(
        item_id=card.item_id,
        kind=card.kind,
        title=card.title,
        episode_name=card.episode_name,
        season=card.season,
        episode_start=card.episode_start,
        episode_end=card.episode_end,
        year=card.year,
        progress=card.progress,
        image_url=image_url(image.item_id, image.image_type, size=ImageSize.WIDE, tag=image.tag)
        if image
        else "",
    )


@router.get(
    "/shows/{series_id}/episodes",
    responses=access_responses(*EPISODES_REFUSALS),
)
async def get_episodes(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    series_id: Annotated[str, Path(pattern=HEX32)],
    season_id: Annotated[str, Query(pattern=HEX32)],
) -> list[WatchEpisodeOut]:
    """Media 詳情觀看區的一季（票 08）。路徑照 Jellyfin 的 `/Shows/{id}/Episodes?seasonId=`；
    劇與季的可見性由 Jellyfin 對 session 那個人查，前端送來的 id 只是 Jellyfin 那一端的 id。"""
    try:
        async with jellyfin_access(session, factory, cache, session_user(request)) as access:
            episodes = await read_episodes(access, series_id, season_id)
    except EPISODES_REFUSALS as refusal:
        raise access_refusal(refusal) from refusal
    return [watch_episode_out(episode) for episode in episodes]


def watch_episode_out(episode: WatchEpisode) -> WatchEpisodeOut:
    """一集的形狀：劇照網址在這一層組（services 只知道 Jellyfin 的 tag）。"""
    still = episode.still
    return WatchEpisodeOut(
        item_id=episode.item_id,
        name=episode.name,
        season=episode.season,
        episode_start=episode.episode_start,
        episode_end=episode.episode_end,
        watch=WatchStateOut.model_validate(episode.watch),
        still_url=image_url(still.item_id, still.image_type, size=ImageSize.WIDE, tag=still.tag)
        if still
        else "",
    )


#: 已看 / 未看遇得到的拒絕。decorator 與底下 `_mark` 的 `except` 吃同一份。
PLAYED_REFUSALS = (AccountDisabledError, ItemNotVisibleError, JellyfinUnreachableError)
PLAYED_RESPONSES = access_responses(*PLAYED_REFUSALS)


@router.post("/items/{item_id}/played", responses=PLAYED_RESPONSES)
async def mark_played(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    item_id: Annotated[str, Path(pattern=HEX32)],
) -> WatchStateOut:
    """標為已看。劇集會連每一集一起標，看到一半的位置歸零（研究 §5）。"""
    return await _mark(session, factory, cache, request, item_id, played=True)


@router.delete("/items/{item_id}/played", responses=PLAYED_RESPONSES)
async def mark_unplayed(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    item_id: Annotated[str, Path(pattern=HEX32)],
) -> WatchStateOut:
    """標為未看：清掉觀看次數與最後觀看時間，**復原不了**；劇集清的是每一集（研究 §5）。
    先確認是畫面的事。"""
    return await _mark(session, factory, cache, request, item_id, played=False)


async def _mark(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    item_id: str,
    *,
    played: bool,
) -> WatchStateOut:
    try:
        async with jellyfin_access(session, factory, cache, session_user(request)) as access:
            written = await access.mark_played(item_id, played=played)
    except PLAYED_REFUSALS as refusal:
        raise access_refusal(refusal) from refusal
    return WatchStateOut.model_validate(written)


def session_user(request: Request) -> AuthenticatedUser:
    """替誰讀寫 Jellyfin：一律是 session 的那個人（`services/jellyfin_access.py`）。"""
    user = current_user(request)
    if user is None:  # pragma: no cover - 門禁保證不會發生
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in to use this API")
    return user
