"""「為什麼沒入庫」的端點（M5 票 10，plan §6 media 群組）。

`GET /media/{id}/why-not` 問整部作品，加 `?season=&episode=` 問一集。登入就進得來（門禁的預設），
看得到什麼由命令照按的人決定（`services/why_not.explain`）：一般使用者只有自己送的 Job，Issue
與 RSS 那一側是 `null`。結論分類只在 `domain/why_not.py` 算一次，這裡原樣送出去。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import SessionDep
from berth.api.errors import refusal_responses
from berth.api.jellyfin import session_user
from berth.api.jobs import JobEventOut
from berth.domain import (
    EpisodeStatus,
    FeedItemStatus,
    IssueType,
    JobState,
    JobTrigger,
    MediaKind,
    WhyNot,
    WhyNotRefusal,
)
from berth.services.why_not import WhyNotRejectedError, explain

router = APIRouter(prefix="/media", tags=["media"])

_STATUS: dict[WhyNotRefusal, int] = {
    WhyNotRefusal.MEDIA_MISSING: status.HTTP_404_NOT_FOUND,
    # 請求本身說不通：季與集要一起給，電影沒有集。
    WhyNotRefusal.EPISODE_INCOMPLETE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    WhyNotRefusal.NOT_A_SERIES: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class WhyNotRefusalOut(BaseModel):
    """做不了的時候回的那一份。`reason` 給畫面挑句子，`detail` 是原文。"""

    reason: WhyNotRefusal
    detail: str


class WhyNotJobOut(BaseModel):
    hash: str
    name: str
    state: JobState
    trigger: JobTrigger
    #: 失敗時服務回的原文（英文）。
    error: str
    #: qBittorrent 自己的狀態字串，原樣。
    client_state: str
    #: 0.0–1.0。
    progress: float
    added_at: datetime
    #: 最後幾筆事件，最舊的在前。整條在 `GET /jobs/{hash}/events`。
    events: list[JobEventOut]


class WhyNotIssueOut(BaseModel):
    id: int
    type: IssueType
    job_hash: str | None
    detected_at: datetime


class WhyNotSeriesOut(BaseModel):
    """綁到這部作品的 RSS Series，或待綁定而候選裡有它的。"""

    id: int
    #: 長出它的那一筆 Item 的標題，原樣。
    title: str
    #: `false` 是還在待綁定。
    bound: bool
    confirmed: bool
    exclude: list[str]


class WhyNotItemOut(BaseModel):
    id: int
    series_id: int | None
    title: str
    status: FeedItemStatus
    #: 照發佈名猜的季集；猜不出是 `null`。
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 上一次送單被拒的原文。
    error: str
    #: `excluded` / `duplicate` 的那一條理由（`SkipReason` 的 JSON，值的型別逐條不同所以是 Any）。
    skip: dict[str, Any] | None
    job_hash: str
    published_at: datetime | None


class WhyNotRssOut(BaseModel):
    series: list[WhyNotSeriesOut]
    items: list[WhyNotItemOut]


class EpisodeVerdictOut(BaseModel):
    """一集（電影是整部，季集都是 `null`）的結論與蓋到它的那幾筆。"""

    season: int | None
    episode: int | None
    #: 季表上那一格。電影是 `null`。
    status: EpisodeStatus | None
    conclusion: WhyNot
    #: 蓋到它的 Job hash（這個人看得到的）。
    jobs: list[str]
    #: 蓋到它的 Feed Item id。看不到 RSS 的人是空陣列。
    items: list[int]


class SeasonTallyOut(BaseModel):
    season_number: int
    aired: int
    imported: int


class WhyNotOut(BaseModel):
    """一部作品（或一集）為什麼沒入庫。"""

    model_config = ConfigDict(from_attributes=True)

    media_id: str
    kind: MediaKind
    title: str
    #: 問的是哪一集；問整部作品時都是 `null`。
    season: int | None
    episode: int | None
    #: 問一集時是那一集的；問整部時是各集裡最需要人的那一種。
    conclusion: WhyNot
    seasons: list[SeasonTallyOut]
    #: 問一集時就是那一集；問整部時只有有事的那幾集（已入庫、還沒播的看 `seasons`）。
    episodes: list[EpisodeVerdictOut]
    jobs: list[WhyNotJobOut]
    #: 一般使用者是 `null`：Issue 是管理員的頁面。
    issues: list[WhyNotIssueOut] | None
    #: 一般使用者是 `null`：RSS 是管理員的頁面。
    rss: WhyNotRssOut | None


@router.get(
    "/{media_id}/why-not",
    responses=refusal_responses(WhyNotRefusalOut, _STATUS),
)
async def get_why_not(
    session: SessionDep,
    request: Request,
    media_id: str,
    season: int | None = None,
    episode: int | None = None,
) -> WhyNotOut:
    """這部作品（或那一集）為什麼沒入庫：季表、Job 與最後幾筆事件、Issue、RSS 那一側與一個結論。
    只讀資料庫，不問任何服務。"""
    user = session_user(request)
    try:
        if (season is None) != (episode is None):
            raise WhyNotRejectedError(WhyNotRefusal.EPISODE_INCOMPLETE, "season and episode")
        view = await explain(
            session,
            media_id,
            role=user.role,
            user_id=user.id,
            episode=None if season is None or episode is None else (season, episode),
        )
    except WhyNotRejectedError as refusal:
        raise why_not_refusal(refusal) from refusal
    return WhyNotOut.model_validate(asdict(view))


def why_not_refusal(refusal: WhyNotRejectedError) -> HTTPException:
    body = WhyNotRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))
