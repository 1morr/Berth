"""追更頁（M5.5 票 12，plan §6〈schedule〉）：訂閱的作品一部一列，有沒有按時入庫。

只有管理員進得來（`api/gate.py` 的 `ADMIN_PREFIXES` 有 `/schedule/tracking`）：一列寫著字幕組與
卡住的那一筆下載，與 `/rss`、`/issues` 是同一群人的事。它的兄弟 `/schedule`（時間表）給每個人。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from berth.api.deps import SessionDep
from berth.domain import KeepingUpSection, OverdueReason, OverdueStall, WhyNot
from berth.services.keeping_up import read_keeping_up

router = APIRouter(prefix="/schedule/tracking", tags=["schedule"])


class EpisodeMarkOut(BaseModel):
    """「已播到」「已入庫到」那一格。"""

    model_config = ConfigDict(from_attributes=True)

    season: int
    episode: int
    #: TMDB 的播出日；沒寫是 null。
    air_date: date | None


class LateEpisodeOut(BaseModel):
    """晚的一集（同 `episodes_overdue` 的 `detail_json.episodes[]`）。"""

    model_config = ConfigDict(from_attributes=True)

    season: int
    episode: int
    air_date: date
    stall: OverdueStall
    #: 卡在 `stall` 的那幾筆 Job（`/jobs/{hash}`）；沒有下載時是空的。
    jobs: list[str]


class TrackedWorkOut(BaseModel):
    """追更頁的一列。"""

    model_config = ConfigDict(from_attributes=True)

    #: `tv:<tmdb>`，也是 `/media/:id` 的路徑段。
    media_id: str
    #: Display Round：兩輪都送，畫面照 UI 語言挑（`GLOSSARY.md`）。
    title: str
    title_en: str
    #: 作品上每一條 RSS Series 的字幕組，不重複。
    groups: list[str]
    #: TMDB 上最新播出的一集；還沒播或沒有快照是 null。
    aired: EpisodeMarkOut | None
    #: 帳本裡最新的一集；一集都沒有是 null。
    imported: EpisodeMarkOut | None
    #: 基準之後缺的那幾集的結論（`imported` 是跟上了）；沒有 TMDB 快照是 null。
    conclusion: WhyNot | None
    #: 缺的集裡有一集下載停滯：`conclusion` 的 `downloading` 這時要說成「下載停滯」。
    stalled: bool
    section: KeepingUpSection
    #: 有晚的集時才有；`next_run` 是「可能是下一輪」。
    reason: OverdueReason | None
    #: 最早那一集晚的集從播出日到今天的天數（「晚 N 天」）；沒有晚的集是 null。
    late_days: int | None
    late: list[LateEpisodeOut]


class KeepingUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 容器時區的今天。
    today: date
    #: 照段（要你動手、準時、斷更很久）排好，段內也排好了。
    works: list[TrackedWorkOut]


@router.get("")
async def get_keeping_up(session: SessionDep) -> KeepingUpOut:
    return KeepingUpOut.model_validate(await read_keeping_up(session))
