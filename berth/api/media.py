"""Media 詳情與刷新的端點（plan §6 media 群組、票 04、04b）。

誰進得來由門禁決定（`api/gate.py`）：`/api/media/*` 不在白名單上，所以未登入一律 401。
瀏覽詳情**不是管理動作**——送單本來就是一般使用者做的事（brief §11）。

**這一頁沒有「追蹤」這個動作**（票 04b）：`tracked` 是推導出來的（票 09 起是 `EXISTS(jobs)`），
而「入庫到哪一條 Route」由送單那一刻寫成 `default_route_id`，不另外開一支端點。
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.domain import (
    CollectionType,
    EpisodeStatus,
    JellyfinPresence,
    LedgerStatus,
    MediaKind,
    PlanAction,
    TmdbProblem,
)
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
    #: 這一集在媒體庫裡的樣子（票 13）。依序取：已入庫 → 卡住 → 下載中 → 缺 / 未播出。
    status: EpisodeStatus


class SeasonOut(BaseModel):
    """一季。`season_number: 0` 是 Specials。"""

    model_config = ConfigDict(from_attributes=True)

    season_number: int
    #: TMDB 的季名。`Hashira Training Arc` 這種篇章名原樣顯示，不正規化成 `Season N`。
    name: str
    #: TMDB 自己報的集數。與 `episodes` 的長度可能不同（未播的集數已經先列進來）。
    episode_count: int
    air_date: date | None
    #: 這一季播出了的集數裡入庫了幾集，與它的分母（票 13）。與媒體庫卡片同一個定義，前端不重算。
    imported: int
    aired: int
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


class LedgerFileOut(BaseModel):
    """檔案清單的一列：一筆帳本（CONTEXT.md 的 Ledger Entry）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: `import` / `extra` / `subtitle`。
    action: PlanAction
    season: int | None
    episode_start: int | None
    #: 單檔多集時的結尾集號（`S01E01-E02`，brief §6.6）。
    episode_end: int | None
    #: `[WEB][1080p][CHT][Group]`——檔名裡的那一段，不是文案。
    tags: str
    #: 容器裡的完整路徑。
    target_path: str
    #: 帳本與磁碟對不對得起來。M1 只會是 `ok`，其餘三種是 M2 的 Reconciler 寫的。
    status: LedgerStatus
    #: 正片才查 Jellyfin；字幕與特典是 `none`。
    presence: JellyfinPresence
    #: 下一次反查的時間。`presence` 是 `searching` 時畫面拿它說「下一次 N 後」。
    resolve_after: datetime | None
    resolve_attempts: int
    job_hash: str | None


class UnmatchedFileOut(BaseModel):
    """對不到任何一集的檔案。它留在 complete 原位，不在帳本裡（brief §7.4）。"""

    model_config = ConfigDict(from_attributes=True)

    #: 相對於 torrent 內容根的路徑。
    rel_path: str
    job_hash: str
    #: 發佈名，原樣——使用者在下載列表上認得出那一筆的東西。
    job_name: str


class VersionOut(BaseModel):
    """並存的版本裡的一個（brief §7.7）。"""

    model_config = ConfigDict(from_attributes=True)

    #: Jellyfin 版本選單上的名字（帳本的 `jellyfin_version_name`）。**由 Jellyfin 算**，
    #: 所以它還沒收錄這個檔案時是空字串。
    name: str
    #: 這個檔案的 Tags。沒有 `name` 時畫面顯示它，並說明那不是版本名（brief §7.7）。
    tags: str


class VersionGroupOut(BaseModel):
    """同一集（或同一部電影）並存的版本（brief §7.7）。"""

    model_config = ConfigDict(from_attributes=True)

    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 先後順序不保證：Jellyfin 依解析度降冪再依檔名排，Berth 這裡照帳本的順序。
    versions: list[VersionOut]


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
    #: `zh-Hant` 介面的顯示用標題（`zh-TW` 有就用它）。**兩種語言都送**，畫面照 UI 語言挑一個：
    #: 換語言時當場換掉，不必重抓（brief §7.5）。
    title: str
    #: 英文標題。**檔名用的那一個**（brief §7.5），也是 `en` 介面的顯示用標題。
    title_en: str
    title_original: str
    year: int | None
    #: 首播 / 上映日。TMDB 未定檔時是 `None`。
    first_air_date: date | None
    #: `zh-Hant` 介面的簡介（`zh-TW` 那一輪，缺就是英文）。
    overview: str
    #: `en` 介面的簡介（`en-US` 那一輪）。缺就是空字串，不落回中文。
    overview_en: str
    poster_url: str
    #: 電影片長（分鐘）；劇集是 `None`，它的片長在每一集上。
    runtime: int | None
    #: 作品資料夾名。凍結之前是「將會是」的預覽（plan §5、票 09）。
    folder_name: str
    #: 那串字已經定死了：第一次送單成功那一刻起磁碟上真的有一個那樣的資料夾（brief §4.5）。
    folder_frozen: bool
    #: Berth 已經為這部作品做過事（`CONTEXT.md` 的 Tracked Media）。**推導出來的**，
    #: 不是欄位——票 09 起是 `EXISTS(jobs)`，票 12 加帳本，M3 加 Rule（票 04b）。
    tracked: bool
    #: 上次送單用的 Route。下拉的預選值——「入庫到哪裡」是一個會重複的決定（plan §2.2）。
    default_route_id: int | None
    seasons: list[SeasonOut]
    #: 這份快照什麼時候抓的。畫面用它說「這是 N 前的快照」。
    fetched_at: datetime | None
    routes: list[RouteChoiceOut]
    problem: TmdbProblem | None
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    detail: str
    #: 帳本裡這部作品的每一個檔案（跨 Route），照季集排（票 13）。
    files: list[LedgerFileOut]
    #: 現在那幾份計劃裡對不到的檔案。預估不算。
    unmatched: list[UnmatchedFileOut]
    #: 只有兩個以上版本並存的那幾組。
    versions: list[VersionGroupOut]


@router.get("/{media_id}")
async def get_media(session: SessionDep, factory: ClientFactoryDep, media_id: str) -> MediaOut:
    """快照超過 24 小時就順手重抓（plan §8.3）。使用者不必按任何東西。"""
    return MediaOut.model_validate(await read_media(session, factory, media_id))


@router.post("/{media_id}/refresh")
async def post_refresh(session: SessionDep, factory: ClientFactoryDep, media_id: str) -> MediaOut:
    """不管幾歲都重抓一次。TMDB 改了標題，`folder_name` 就跟著改（票 04b 驗收）。"""
    return MediaOut.model_validate(await refresh_media(session, factory, media_id))
