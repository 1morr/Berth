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

from berth.api.deps import (
    ClientFactoryDep,
    EventHubDep,
    ImportHintsDep,
    PlanHintsDep,
    SessionDep,
)
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.domain import JobRefusal, JobState, JobTrigger
from berth.services import deletion
from berth.services.deletion import DeleteScope
from berth.services.jobs import (
    JobRejectedError,
    JobSource,
    actor_of,
    add_download,
    list_jobs,
    read_job,
    read_job_events,
    retry_job,
)
from berth.services.plan import replan_job
from berth.services.reimport import reimport_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

#: 哪一種拒絕該回哪個狀態碼。`route_unhealthy` 是 409：請求本身沒問題，是**現在**做不了
#: （紅的 Route 修好之後同一個請求就會成功），而 422 讀起來像「你送錯東西了」。
#: **每一種理由都要在這裡**（`tests/unit/test_openapi_contract.py` 守著）：漏一種就是執行期
#: 的 `KeyError`，而預設值會讓一種沒人想過的拒絕靜靜變成 422。
_STATUS: dict[JobRefusal, int] = {
    JobRefusal.MEDIA_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    JobRefusal.ROUTE_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    JobRefusal.ROUTE_KIND_MISMATCH: status.HTTP_422_UNPROCESSABLE_CONTENT,
    JobRefusal.ROUTE_DISABLED: status.HTTP_409_CONFLICT,
    JobRefusal.ROUTE_UNHEALTHY: status.HTTP_409_CONFLICT,
    JobRefusal.SOURCE_UNAVAILABLE: status.HTTP_502_BAD_GATEWAY,
    JobRefusal.JOB_MISSING: status.HTTP_404_NOT_FOUND,
    JobRefusal.NOT_RETRYABLE: status.HTTP_409_CONFLICT,
    # 已經在入庫的那一份計劃正被 importer 照著動檔案（票 12），重算會讓兩邊指向不同的地方。
    JobRefusal.NOT_REPLANNABLE: status.HTTP_409_CONFLICT,
    # 勾錯組合是 422：請求本身說不通（brief §9.2），不是「現在做不了」。
    JobRefusal.DELETE_FILES_REQUIRES_REMOVE_TORRENT: status.HTTP_422_UNPROCESSABLE_CONTENT,
    JobRefusal.CLIENT_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
    # 還在下載、還在入庫的那一筆是**現在**不能從頭再來，等它停下來同一個請求就會成功。
    JobRefusal.NOT_REIMPORTABLE: status.HTTP_409_CONFLICT,
    # 那一包不在 complete 裡了：請求本身沒錯，是磁碟上的事實變了（brief §9.3）。
    JobRefusal.CONTENT_MISSING: status.HTTP_409_CONFLICT,
    # 另一個分頁先刪了、背景迴圈先推進了：重新看一次那一筆，同一個請求可能就成立。
    JobRefusal.MOVED_ON: status.HTTP_409_CONFLICT,
}


class JobRefusalOut(BaseModel):
    """做不了的時候回的那一份。`reason` 給畫面挑句子、挑下一步，`detail` 是原文，不翻譯。

    是 model 而不是手組的 dict，前端才從 OpenAPI 取得到 `JobRefusal` 這個封閉集合——
    它原本在 `web/src/api/jobs.ts` 是手抄的（M2 票 02）。
    """

    reason: JobRefusal
    detail: str


def _refusals(*reasons: JobRefusal) -> dict[int | str, dict[str, Any]]:
    """這一支端點回得出來的那幾種。三支的集合真的不一樣，所以逐支列：重新規劃只到得了兩種，
    而把另外七種寫上去只會讓讀的人以為要處理（同 `api/jellyfin.access_responses`）。"""
    return refusal_responses(JobRefusalOut, {reason: _STATUS[reason] for reason in reasons})


#: 送單：Route 的四種前提、作品不在、索引站給不出那一份 torrent（`services/jobs.add_download`）。
SUBMIT_RESPONSES = _refusals(
    JobRefusal.MEDIA_MISSING,
    JobRefusal.ROUTE_MISSING,
    JobRefusal.ROUTE_KIND_MISMATCH,
    JobRefusal.ROUTE_DISABLED,
    JobRefusal.ROUTE_UNHEALTHY,
    JobRefusal.SOURCE_UNAVAILABLE,
)

#: 重試：**與第一次送單同一組 Route 前提**（`services/jobs.retry_job`），加上這一筆本身的兩種。
#: 沒有 `source_unavailable`——重試時索引站給不出來不是拒絕，那一筆會變成 `submit_failed`。
RETRY_RESPONSES = _refusals(
    JobRefusal.JOB_MISSING,
    JobRefusal.NOT_RETRYABLE,
    JobRefusal.ROUTE_MISSING,
    JobRefusal.ROUTE_KIND_MISMATCH,
    JobRefusal.ROUTE_DISABLED,
    JobRefusal.ROUTE_UNHEALTHY,
)

#: 重新規劃只看這一筆自己（`services/plan.replan_job`），碰不到 Route 與索引站。
REPLAN_RESPONSES = _refusals(JobRefusal.JOB_MISSING, JobRefusal.NOT_REPLANNABLE)

#: 重新入庫只看這一筆與磁碟上那一包（`services/reimport.reimport_job`），不碰 qBittorrent。
REIMPORT_RESPONSES = _refusals(
    JobRefusal.JOB_MISSING, JobRefusal.NOT_REIMPORTABLE, JobRefusal.CONTENT_MISSING
)

#: 刪除：沒有這一筆、勾錯組合、按下去之後它被別處改過了，以及要移除 torrent 而 qBittorrent
#: 問不到（`services/deletion.delete_job`）。
DELETE_RESPONSES = _refusals(
    JobRefusal.JOB_MISSING,
    JobRefusal.DELETE_FILES_REQUIRES_REMOVE_TORRENT,
    JobRefusal.MOVED_ON,
    JobRefusal.CLIENT_UNREACHABLE,
)

#: 估算只讀磁碟（`services/deletion.estimate_deletion`），所以只有「沒有這一筆」。
ESTIMATE_RESPONSES = _refusals(JobRefusal.JOB_MISSING)


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
    #: `zh-Hant` 介面的作品名（`zh-TW` 那一輪，缺就是英文）。作品那一格連到 `/media/{id}`。
    #: **兩種語言都送**，畫面照 UI 語言挑一個：換語言時當場換掉，不必重抓（brief §7.5）。
    media_title: str
    #: `en` 介面的作品名：英文標題，也就是檔名用的那一個。
    media_title_en: str
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
    #: 這一筆現在按得了重新入庫嗎（M2 票 10）。只有 admin 看得到那一顆（門禁），旗標誰都拿得到。
    reimportable: bool
    #: 這一筆現在那一份 Import Plan 的 id（票 11）。還沒算過就是 `null`——畫面照它決定
    #: 要不要去要那一份逐檔的決定，而不是先打一次 404。
    plan_id: int | None
    #: 那一份計劃裡 medium 自動入庫、掛著 audit 的檔案數。列上說「N 個待確認」用它（票 15）。
    audits: int


class JobCreatedOut(BaseModel):
    """送單的結果。

    `created` 分得出「送出去了」與「這一個本來就在了」（plan §3.3）。兩者都是 200——
    使用者按第二次時要看到的是那一筆既有的 Job，不是一則錯誤。
    """

    job: JobOut
    created: bool


class DeletionEstimateOut(BaseModel):
    """`services/deletion.DeletionEstimate` 的對外形狀（理由與算法在那裡）。

    畫面要的那一句在 `reclaimable`：**它不是 `link_bytes + source_bytes`**——來源與它的
    媒體庫鏈接是同一份資料，兩邊各算一次會把答案說成兩倍。
    """

    #: 帳本上、磁碟上還在的媒體庫鏈接數。
    links: int
    #: 帳本上有、磁碟上已經不在的。畫面拿它說「其中 N 個已經不在了」。
    links_missing: int
    link_bytes: int
    #: complete 底下還在的來源檔數。**比鏈接多**：沒人要的 readme 也是下載下來的東西。
    sources: int
    sources_missing: int
    source_bytes: int
    #: 來源與所有鏈接都刪掉時真的會空出來的位元組。
    reclaimable: int
    #: 有別人也握著、刪了也不會空出來的位元組。
    held: int


class JobDeletedOut(BaseModel):
    """`services/deletion.DeleteOutcome` 的對外形狀：一次刪除**真的**做掉了什麼。

    與「勾了哪幾個」不是同一件事，所以它是一份回應而不是回聲；時間線上那一筆 `deleted`
    寫的是同一組數字。
    """

    #: 真的移掉的媒體庫鏈接數。
    links: int
    #: 真的刪掉的 complete 檔案數。
    sources: int
    #: 有沒有向 qBittorrent 送出移除。
    torrent: bool
    #: 帳本與 Job 紀錄清掉了嗎。清了的話這一筆從清單上消失，沒清就是一列 `removed`。
    purged: bool
    #: 真的空出來的位元組。只有來源與所有鏈接都刪掉時才不是 0。
    freed: int
    #: 沒有拆的媒體庫路徑：那裡的檔案已經不是 Berth 放的那一個（使用者換成了自己的一份，
    #: CONTEXT.md 的 Unmanaged）。帳本那一列留給下一輪對帳（M3 票 01）。
    unmanaged: list[str]


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


@router.post("", status_code=status.HTTP_200_OK, responses=SUBMIT_RESPONSES)
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


@router.post("/{job_hash}/replan", responses=REPLAN_RESPONSES)
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


@router.post("/{job_hash}/reimport", responses=REIMPORT_RESPONSES)
async def post_reimport(
    session: SessionDep, plans: PlanHintsDep, request: Request, job_hash: str
) -> JobOut:
    """以那一筆的 complete 目錄重新入庫（brief §9.3、M2 票 10）。**只有 admin**（門禁）。

    回的是退回 `completed` 的那一筆；算與鏈是規劃器與 importer 照常的一輪，所以這裡叫醒規劃器
    而不是自己算——不另開一條入庫的路。
    """
    user = current_user(request)
    try:
        job = await reimport_job(
            session, job_hash, actor=actor_of(user.id if user is not None else None)
        )
    except JobRejectedError as refusal:
        raise _refuse(refusal) from refusal
    plans.nudge()
    return JobOut.model_validate(job)


@router.post("/{job_hash}/retry", responses=RETRY_RESPONSES)
async def post_retry(
    session: SessionDep, factory: ClientFactoryDep, imports: ImportHintsDep, job_hash: str
) -> JobOut:
    """`submit_failed` → `requested` → 再送一次；`import_failed` → `importing`（plan §3.1）。"""
    try:
        job = await retry_job(session, factory, job_hash)
    except JobRejectedError as refusal:
        raise _refuse(refusal) from refusal
    if job.state is JobState.IMPORTING:
        # importer 平常 60 秒才醒一次，而按下重試的人要的是現在。
        imports.nudge()
    return JobOut.model_validate(job)


@router.get("/{job_hash}/deletion", responses=ESTIMATE_RESPONSES)
async def get_deletion(session: SessionDep, job_hash: str) -> DeletionEstimateOut:
    """刪除對話框打開時算的那一份（brief §9.2、票 04）。**只讀，不改任何東西。**

    **慢是刻意的**：逐一 `stat` 每一個來源與目標，不用 qBittorrent 報的 `total_size` 去猜
    ——那是 torrent 的大小，而磁碟上可能只下載了一部分、可能有人手動刪過幾個檔案。畫面在
    等它的時候說「正在算」。
    """
    try:
        estimate = await deletion.estimate_deletion(session, job_hash)
    except JobRejectedError as refusal:
        raise _refuse(refusal) from refusal
    return DeletionEstimateOut.model_validate(estimate, from_attributes=True)


@router.delete("/{job_hash}", responses=DELETE_RESPONSES)
async def delete_job(
    session: SessionDep,
    factory: ClientFactoryDep,
    request: Request,
    job_hash: str,
    unlink: bool = False,
    remove_torrent: bool = False,
    delete_files: bool = False,
    purge: bool = False,
) -> JobDeletedOut:
    """刪除範圍的四個旗標（brief §9.2、plan §3.1 的最後一列、票 04）。

    **四個預設全不勾**，而且預設值在後端也成立：一個參數都不帶的 `DELETE` 只把這一筆收成
    `removed`，磁碟上一個檔案都不動。預設只寫在對話框上的話，之後的每一個呼叫端（Issue 的
    修復、票 06 的 audit 撤銷）都要自己記得這件事。

    回的是**真的發生了什麼**而不是 204：勾了「移除鏈接」而那幾個檔案早就被人在 Jellyfin 裡
    刪掉時，畫面要說得出「0 個鏈接」而不是一句「刪好了」。
    """
    user = current_user(request)
    try:
        outcome = await deletion.delete_job(
            session,
            factory,
            job_hash,
            DeleteScope(
                unlink=unlink,
                remove_torrent=remove_torrent,
                delete_files=delete_files,
                purge=purge,
            ),
            actor=actor_of(user.id if user is not None else None),
        )
    except JobRejectedError as refusal:
        raise _refuse(refusal) from refusal
    return JobDeletedOut.model_validate(outcome, from_attributes=True)


def _refuse(refusal: JobRejectedError) -> HTTPException:
    """`reason` 是給畫面挑句子的封閉集合，`detail` 是原文。兩個都送出去。"""
    body = JobRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))
