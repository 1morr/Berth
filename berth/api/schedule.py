"""時間表（M5.5 票 09，plan §6〈schedule〉）：這一週 TMDB 上播的動畫，一集一張卡。

時刻（AniList）與評分（Bangumi）是第二層（票 14），對不上就是 null。

登入就進得來（不在 `api/gate.py` 的 `ADMIN_PREFIXES`）：時間表給每個人。卡片只帶狀態類別，
字幕組與 Feed 是管理員的頁面，這裡不送（比照 `services/why_not.py` 的範圍）。
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.domain import ScheduleStatus, TmdbProblem
from berth.services.schedule import read_schedule

router = APIRouter(prefix="/schedule", tags=["schedule"])


class ScheduleCardOut(BaseModel):
    """一部作品這一週的一集。"""

    model_config = ConfigDict(from_attributes=True)

    #: `tv:<tmdb>`，也是 `/media/:id` 的路徑段。
    media_id: str
    tmdb_id: int
    #: Display Round：兩輪都送，畫面照 UI 語言挑（`CONTEXT.md`）。
    title: str
    title_en: str
    #: 小海報的完整網址；沒有是空字串。
    poster_url: str
    poster_url_en: str
    #: TMDB 的播出日，卡片放在這一天。
    air_date: date
    season: int
    episode: int
    #: 每次照資料庫算：卡片上那一集入庫了、作品訂閱了，或都沒有。
    status: ScheduleStatus
    #: AniList 的放送時刻（帶時區，畫面照瀏覽器的時區寫）。只給還沒播、原文名對得上的；否則 null。
    airs_at: datetime | None
    #: Bangumi 的評分（1–10）與打分人數。原文名對不上或沒人打分是 null。
    score: float | None
    votes: int | None


class ScheduleOut(BaseModel):
    """這一週。**失敗也是 200**，同探索頁：畫面要分得出沒填憑證與 TMDB 連不上。"""

    model_config = ConfigDict(from_attributes=True)

    #: 週一與週日（容器時區）。
    start: date
    end: date
    #: 容器時區的今天：哪一欄標「今天」照它，不照瀏覽器。
    today: date
    #: 照播出日排，同一天裡已入庫與已訂閱的在前，其餘照 TMDB 的順序。
    cards: list[ScheduleCardOut]
    problem: TmdbProblem | None
    detail: str


@router.get("")
async def get_schedule(session: SessionDep, factory: ClientFactoryDep) -> ScheduleOut:
    return ScheduleOut.model_validate(await read_schedule(session, factory))
