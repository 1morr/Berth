"""Media 詳情與刷新的端點（plan §6 media 群組、票 04、04b）。

誰進得來由門禁決定（`api/gate.py`）：`/api/media/*` 不在白名單上，所以未登入一律 401。
瀏覽詳情**不是管理動作**——送單本來就是一般使用者做的事（brief §11）。

**這一頁沒有「追蹤」這個動作**（票 04b）：`tracked` 是推導出來的（票 09 起是 `EXISTS(jobs)`），
入庫到哪一條 Route 是搜尋與送單時才帶上的偏好，不落地成一個端點。
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.domain import CollectionType, MediaKind, TmdbProblem
from berth.services.media import read_media, refresh_media

router = APIRouter(prefix="/media", tags=["media"])


class EpisodeOut(BaseModel):
    """一集。"""

    model_config = ConfigDict(from_attributes=True)

    episode_number: int
    name: str
    #: 播出日。TMDB 未定檔時是 `None`——畫面留一條 `—`，不省略整欄。
    air_date: date | None
    #: 分鐘。還沒播的集數 TMDB 常常給不出來。
    runtime: int | None
    #: Absolute episode group 給的絕對編號。沒有那種 group 的作品整欄是 `None`。
    absolute_number: int | None


class SeasonOut(BaseModel):
    """一季。`season_number: 0` 是 Specials。"""

    model_config = ConfigDict(from_attributes=True)

    season_number: int
    #: TMDB 的季名。`Hashira Training Arc` 這種篇章名原樣顯示，不正規化成 `Season N`。
    name: str
    #: TMDB 自己報的集數。與 `episodes` 的長度可能不同（未播的集數已經先列進來）。
    episode_count: int
    air_date: date | None
    episodes: list[EpisodeOut]


class RouteChoiceOut(BaseModel):
    """下拉裡的一條 Route。只會出現 `collection_type` 與這部作品相符的。

    「劇集只進得了 tvshows 媒體庫」是領域規則（`domain.collection_type_for`），所以過濾在
    後端做，前端拿到的就是選得下去的那幾條——放前端會變成第二份實作。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    collection_type: CollectionType


class MediaOut(BaseModel):
    """詳情頁的一整份。

    **拿不到 TMDB 時仍然是 200**，理由放在 `problem`（與探索頁同一個 enum）：存下來的
    快照過期了但仍然是真的季集，畫得出來就該畫出來，只是要說一句「這是舊的」（票 04）。
    """

    model_config = ConfigDict(from_attributes=True)

    #: `tv:<tmdb>` / `movie:<tmdb>`。
    id: str
    tmdb_id: int
    kind: MediaKind
    #: 顯示用標題（`zh-TW` 有就用它）。
    title: str
    #: 英文標題。**檔名用的那一個**（brief §7.5），所以與 `title` 不同時兩個都要顯示。
    title_en: str
    title_original: str
    year: int | None
    #: 首播 / 上映日。TMDB 未定檔時是 `None`。
    first_air_date: date | None
    overview: str
    poster_url: str
    #: 電影片長（分鐘）；劇集是 `None`，它的片長在每一集上。
    runtime: int | None
    #: 作品資料夾名。畫面上是「將會是」的預覽——凍結在第一次送單成功那一刻（plan §5、票 09）。
    folder_name: str
    seasons: list[SeasonOut]
    #: 這份快照什麼時候抓的。畫面用它說「這是 N 前的快照」。
    fetched_at: datetime | None
    routes: list[RouteChoiceOut]
    problem: TmdbProblem | None
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    detail: str


@router.get("/{media_id}")
async def get_media(session: SessionDep, factory: ClientFactoryDep, media_id: str) -> MediaOut:
    """快照超過 24 小時就順手重抓（plan §8.3）。使用者不必按任何東西。"""
    return MediaOut.model_validate(await read_media(session, factory, media_id))


@router.post("/{media_id}/refresh")
async def post_refresh(session: SessionDep, factory: ClientFactoryDep, media_id: str) -> MediaOut:
    """不管幾歲都重抓一次。TMDB 改了標題，`folder_name` 就跟著改（票 04b 驗收）。"""
    return MediaOut.model_validate(await refresh_media(session, factory, media_id))
