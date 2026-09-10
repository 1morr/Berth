"""送單與 Job 的端點（plan §6 jobs 群組、票 09）。

誰進得來由門禁決定（`api/gate.py`）：`/api/jobs` 不在白名單上，所以未登入一律 401。
**送單不是管理動作**——那本來就是一般使用者做的事（brief §11），只有設定才要 admin。

拒絕用的是 HTTP 狀態碼，而不是探索頁與搜尋那種「200 + `problem`」：那兩支一次畫好幾個
feed，其中一個垮掉時另外幾個還要畫得出來。這一支只做一件事，做不了就是做不了，而理由
在 `reason` 那一格（封閉集合，UI 逐種說一句話）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, EventHubDep, SessionDep
from berth.api.gate import current_user
from berth.domain import JobState, JobTrigger
from berth.services.jobs import (
    JobRejectedError,
    JobSource,
    add_download,
    list_jobs,
    read_job,
    read_job_events,
    retry_job,
)
from berth.services.plan import replan_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

#: 哪一種拒絕該回哪個狀態碼。`route_unhealthy` 是 409：請求本身沒問題，是**現在**做不了
#: （紅的 Route 修好之後同一個請求就會成功），而 422 讀起來像「你送錯東西了」。
_STATUS = {
    "media_missing": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "route_missing": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "route_kind_mismatch": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "route_disabled": status.HTTP_409_CONFLICT,
    "route_unhealthy": status.HTTP_409_CONFLICT,
    "source_unavailable": status.HTTP_502_BAD_GATEWAY,
    "job_missing": status.HTTP_404_NOT_FOUND,
    "not_retryable": status.HTTP_409_CONFLICT,
    # 已經在入庫的那一份計劃正被 importer 照著動檔案（票 12），重算會讓兩邊指向不同的地方。
    "not_replannable": status.HTTP_409_CONFLICT,
}


class JobSourceIn(BaseModel):
    """結果表那一列帶過來的東西。

    **不是一個結果 id**：搜尋結果不落地（票 08），所以送單時前端要把那一列本身送回來。
    `url` 尤其如此——Prowlarr 的代理連結每次搜尋都不一樣（brief §20.7），只有使用者
    眼前那一輪的那一條是有效的。
    """

    #: 索引站的下載連結（`.torrent` 或磁力）。
    url: str = Field(min_length=1)
    #: 發佈名，原樣。下載列表上認得出這一列的就是它。
    title: str = Field(min_length=1)
    #: 索引站報的 info hash。**可能沒有**（實測 ACG.RIP 不報）；有的話重複送單連下載
    #: 都不必發，沒有的話 Berth 從那份 torrent 自己算。
    info_hash: str = ""


class JobCreateIn(BaseModel):
    source: JobSourceIn
    #: `tv:<tmdb>` / `movie:<tmdb>`。
    media: str = Field(min_length=1)
    #: 入庫到哪一條 Route。**這一次是承諾**（票 04b：搜尋時它只是偏好），所以是必填——
    #: 猜一條的代價是檔案進錯媒體庫，而那件事之後要人工搬。
    route: int


class JobOut(BaseModel):
    """下載列表與 Job 詳情上的一筆。"""

    model_config = ConfigDict(from_attributes=True)

    #: info hash，小寫十六進位。它是這一筆的身分（plan §2.3）。
    hash: str
    #: 發佈名，原樣。
    name: str
    state: JobState
    trigger: JobTrigger
    #: rule id 或重新入庫的來源目錄。`manual` 時是空字串。
    trigger_ref: str
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    error: str
    media_id: str | None
    #: 英文標題。作品那一格連到 `/media/{id}`。
    media_title: str
    route_id: int | None
    route_name: str
    route_slug: str
    user_id: int | None
    #: 誰按的。RSS 與重新入庫沒有人在場，那時是空字串。
    user_name: str
    #: qBittorrent 報的下載目錄與內容路徑。票 10 的 poller 才填得出來。
    save_path: str
    content_path: str
    total_size: int
    #: 0.0–1.0。
    progress: float
    #: qBittorrent 自己的狀態字串（`stalledDL`…），原樣。畫面用它說「客戶端那邊怎麼了」。
    client_state: str
    added_at: datetime
    completed_at: datetime | None
    imported_at: datetime | None
    #: 這一筆現在按得了重試嗎（plan §3.1）。規則在後端算，前端不重算一份。
    retryable: bool
    #: 這一筆現在按得了重新規劃嗎（票 11）。規則在後端算，前端不重算一份。
    replannable: bool
    #: 這一筆現在那一份 Import Plan 的 id（票 11）。還沒算過就是 `null`——畫面照它決定
    #: 要不要去要那一份逐檔的決定，而不是先打一次 404。
    plan_id: int | None


class JobCreatedOut(BaseModel):
    """送單的結果。

    `created` 分得出「送出去了」與「這一個本來就在了」（plan §3.3）。兩者都是 200——
    使用者按第二次時要看到的是那一筆既有的 Job，不是一則錯誤。
    """

    job: JobOut
    created: bool


class JobEventOut(BaseModel):
    """時間線上的一筆（brief §5.2）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: `created` / `submitted` / `submit_failed` / `retried`（`domain.EventType`）。
    type: str
    #: user id、`system`、`rss:<rule>` 或 `ai`。
    actor: str
    #: 逐型別不同的那幾格。畫面照型別挑要顯示哪幾個。
    payload: dict[str, Any]
    created_at: datetime


@router.post("", status_code=status.HTTP_200_OK)
async def post_job(
    session: SessionDep, factory: ClientFactoryDep, request: Request, body: JobCreateIn
) -> JobCreatedOut:
    """送一個 torrent 進 qBittorrent（plan §3.1、§3.3）。

    **qBittorrent 收不下不是這一支的錯誤**：那時 Job 已經存在了，狀態是 `submit_failed`
    加上原文，而畫面上那一列有一顆重試（plan §3.1）。200 回的就是那一筆。
    """
    user = current_user(request)
    try:
        outcome = await add_download(
            session,
            factory,
            source=JobSource(
                url=body.source.url,
                title=body.source.title,
                info_hash=body.source.info_hash,
            ),
            media_id=body.media,
            route_id=body.route,
            user_id=user.id if user is not None else None,
        )
    except JobRejectedError as refusal:
        raise _refuse(refusal) from refusal
    return JobCreatedOut(job=JobOut.model_validate(outcome.job), created=outcome.created)


@router.get("")
async def get_jobs(session: SessionDep) -> list[JobOut]:
    """下載列表，最新的在前面。"""
    return [JobOut.model_validate(row) for row in await list_jobs(session)]


@router.get("/{job_hash}")
async def get_job(session: SessionDep, job_hash: str) -> JobOut:
    job = await read_job(session, job_hash)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such job")
    return JobOut.model_validate(job)


@router.get("/{job_hash}/events")
async def get_job_events(session: SessionDep, job_hash: str) -> list[JobEventOut]:
    """時間線，最舊的在前面——讀的方向就是事情發生的方向。"""
    return [JobEventOut.model_validate(row) for row in await read_job_events(session, job_hash)]


@router.post("/{job_hash}/replan")
async def post_replan(
    session: SessionDep, factory: ClientFactoryDep, hub: EventHubDep, job_hash: str
) -> JobOut:
    """重新算一份 Plan（plan §6 jobs 群組、票 11）。

    使用者按它的時刻是：Plan 停在 review 而他剛改了 Route 的設定，或 TMDB 那邊補上了正確的
    季集。回的是**那一筆 Job**（新的狀態與 `plan_id`）而不是 Plan 本身——按下去之後畫面上
    要重畫的是那一列。
    """
    try:
        await replan_job(session, factory, hub, job_hash)
    except JobRejectedError as refusal:
        raise _refuse(refusal) from refusal
    job = await read_job(session, job_hash)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such job")
    return JobOut.model_validate(job)


@router.post("/{job_hash}/retry")
async def post_retry(session: SessionDep, factory: ClientFactoryDep, job_hash: str) -> JobOut:
    """`submit_failed` → `requested` → 再送一次（plan §3.1）。"""
    try:
        return JobOut.model_validate(await retry_job(session, factory, job_hash))
    except JobRejectedError as refusal:
        raise _refuse(refusal) from refusal


def _refuse(refusal: JobRejectedError) -> HTTPException:
    """`reason` 是給畫面挑句子的封閉集合，`detail` 是原文。兩個都送出去。"""
    return HTTPException(
        status_code=_STATUS.get(refusal.reason, status.HTTP_422_UNPROCESSABLE_CONTENT),
        detail={"reason": refusal.reason, "detail": refusal.detail},
    )
