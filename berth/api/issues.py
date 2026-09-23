"""Issue 清單與對帳的端點（plan §6 issues 群組、brief §9.1、M2 票 05）。

誰進得來由門禁決定（`api/gate.py`）：`issues/*` 與 `reconcile` 整組只有 `admin`
（plan §6，2026-09-22 拍板——審核、修正、刪除都是管理員的事）。所以這裡沒有任何權限判斷。

`POST /reconcile` 回 **202** 而不是 200：那一輪在背景跑，回的是「收下了，這一輪是第幾號」。
進度問 `GET /reconcile`。正在跑時再按是 409 而不是排隊——排隊的那一輪看到的會是同一份磁碟
（plan §3.2）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from berth.api.deps import ClientFactoryDep, PlanHintsDep, ReconcilerDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.domain import IssueAction, IssueRefusal, IssueStatus, IssueType, ReconcileSide
from berth.services.issues import (
    IssueRejectedError,
    IssueView,
    ignore_issue,
    list_issues,
    resolve_issue,
)
from berth.services.jobs import actor_of
from berth.services.reconcile import ReconcileReport, SideReport

router = APIRouter(tags=["issues"])

#: 哪一種拒絕該回哪個狀態碼。**每一種理由都要在這裡**（`tests/unit/test_openapi_contract.py`
#: 守著）：漏一種就是執行期的 `KeyError`。
#:
#: 409 的共通點是「請求本身沒問題，是**現在**做不了」：另一個分頁先按了、來源檔也不在、
#: 掛載壞著、目錄有主了。修好之後同一個請求就會成功，所以不是 422。`action_not_available` 反過來——
#: 那一顆對這一種 Issue 根本不存在，重送幾次都一樣。
_STATUS: dict[IssueRefusal, int] = {
    IssueRefusal.ISSUE_MISSING: status.HTTP_404_NOT_FOUND,
    IssueRefusal.ISSUE_NOT_OPEN: status.HTTP_409_CONFLICT,
    IssueRefusal.ACTION_NOT_AVAILABLE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    IssueRefusal.SOURCE_MISSING: status.HTTP_409_CONFLICT,
    IssueRefusal.RELINK_FAILED: status.HTTP_409_CONFLICT,
    IssueRefusal.CLIENT_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
    IssueRefusal.RECONCILE_RUNNING: status.HTTP_409_CONFLICT,
    IssueRefusal.IN_USE: status.HTTP_409_CONFLICT,
    IssueRefusal.SIZE_DIFFERS: status.HTTP_409_CONFLICT,
    IssueRefusal.DELETE_FAILED: status.HTTP_409_CONFLICT,
    IssueRefusal.JELLYFIN_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
    # 同 `POST /jobs`：索引站那一頭給不出同一個 torrent，是上游的事（`JobRefusal` 同一種）。
    IssueRefusal.SOURCE_UNAVAILABLE: status.HTTP_502_BAD_GATEWAY,
    IssueRefusal.RESUBMIT_FAILED: status.HTTP_409_CONFLICT,
    IssueRefusal.ROUTE_UNUSABLE: status.HTTP_409_CONFLICT,
}


class IssueRefusalOut(BaseModel):
    """做不了的時候回的那一份。`reason` 給畫面挑句子，`detail` 是原文，不翻譯。

    `relink_failed` 的 `detail` 尤其重要：它是系統的 `errno` 與「哪兩個掛載」那一句
    （plan §8.6），而那正是使用者要改的那一行 compose。
    """

    reason: IssueRefusal
    detail: str


def _refusals(*reasons: IssueRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(IssueRefusalOut, {reason: _STATUS[reason] for reason in reasons})


#: 按下任何一顆都到得了的：這一件不在了、已經被決定過了、那一顆按不了。其餘各自屬於幾顆：
#: 來源不在（重新鏈接、以硬鏈接取代）、鏈接沒成（同兩顆）、問不到 qBittorrent（兩顆會刪
#: complete 的，與管線那三種的重新 recheck / 重試 / 重新送單）、目錄有主了與刪不掉（刪除孤兒）、
#: 大小變了（以硬鏈接取代）、問不到 Jellyfin（重新掃描媒體庫）、下載連結給不出同一個 torrent、
#: qBittorrent 不收、Route 用不了（重新送單）。
RESOLVE_RESPONSES = _refusals(
    IssueRefusal.ISSUE_MISSING,
    IssueRefusal.ISSUE_NOT_OPEN,
    IssueRefusal.ACTION_NOT_AVAILABLE,
    IssueRefusal.SOURCE_MISSING,
    IssueRefusal.RELINK_FAILED,
    IssueRefusal.CLIENT_UNREACHABLE,
    IssueRefusal.IN_USE,
    IssueRefusal.SIZE_DIFFERS,
    IssueRefusal.DELETE_FAILED,
    IssueRefusal.JELLYFIN_UNREACHABLE,
    IssueRefusal.SOURCE_UNAVAILABLE,
    IssueRefusal.RESUBMIT_FAILED,
    IssueRefusal.ROUTE_UNUSABLE,
)

#: 忽略不碰磁碟也不碰服務，所以只有這一件本身的兩種。
IGNORE_RESPONSES = _refusals(IssueRefusal.ISSUE_MISSING, IssueRefusal.ISSUE_NOT_OPEN)

#: 手動對帳唯一做不了的時候：上一輪還在跑。
RECONCILE_RESPONSES = _refusals(IssueRefusal.RECONCILE_RUNNING)


class IssueOut(BaseModel):
    """清單上的一列（`services/issues.IssueView` 的對外形狀）。

    **`actions` 由後端算**（同 `JobOut.retryable`）：按下去會被拒絕的按鈕不該畫出來，而
    「這一筆現在按得了什麼」要看它的型別**與**它的資料（指不到帳本的按不了重新鏈接）。
    前端照這一格畫按鈕，不自己重算一份規則。
    """

    id: int
    type: IssueType
    #: 冪等鍵的後半：同一件事再偵測到時對上的就是它（plan §2.4）。畫面不顯示它。
    subject: str
    #: 空字串代表這一件不掛在任何一筆下載上（重新入庫建出來的帳本，`models/ledger.py`）。
    job_hash: str
    ledger_id: int | None
    #: 出問題的那一條路徑。不適用的型別是空字串。
    path: str
    #: 逐型別不同的那幾格。畫面照型別挑要顯示哪幾個（同 `JobEventOut.payload`）。
    detail: dict[str, Any]
    status: IssueStatus
    detected_at: datetime
    #: 這一列現在按得了哪幾顆，順序就是畫面上的順序。空的代表只剩「忽略」。
    actions: list[IssueAction]


class IssueResolveIn(BaseModel):
    """按了哪一顆。**封閉集合**（brief §9.1 那一欄），不是自由文字。"""

    action: IssueAction


class SideOut(BaseModel):
    """一輪裡的一方（plan §3.2 的「哪一方比到哪、幾筆」）。"""

    side: ReconcileSide
    counted: int
    #: 整方問不到的原文。問得到就是空字串——**畫面要分得出「都好好的」與「根本沒比」**。
    unavailable: str
    #: 問得到、但跳過的那幾處（媒體庫那一方逐 Route）。
    skipped: list[str]


class ReconcileRunOut(BaseModel):
    """一輪對帳。`finished_at` 是 `null` 就是還在跑。"""

    id: int
    started_at: datetime
    finished_at: datetime | None
    sides: list[SideOut]
    opened: int
    updated: int


class ReconcileStatusOut(BaseModel):
    """`GET /reconcile`：上一輪與進行中的那一輪。

    兩格都可能是 `null`，意思不同：`current` 是 `null` 代表現在沒有在跑，`last` 是 `null`
    代表這個程序起來之後還沒跑過（進度活在記憶體裡，`pipeline/reconciling.py`）。
    """

    current: ReconcileRunOut | None
    last: ReconcileRunOut | None


@router.get("/issues")
async def get_issues(session: SessionDep) -> list[IssueOut]:
    """還沒有人決定的那幾件，最近偵測到的在前面。

    **只有 `open`**：這是一份工作清單不是歷史（`services/issues.list_issues`）。
    """
    return [issue_out(row) for row in await list_issues(session)]


@router.post("/issues/{issue_id}/resolve", responses=RESOLVE_RESPONSES)
async def post_resolve(
    session: SessionDep,
    factory: ClientFactoryDep,
    plans: PlanHintsDep,
    request: Request,
    issue_id: int,
    body: IssueResolveIn,
) -> IssueOut:
    """按下那一顆（brief §9.1 的「預設建議動作」那一欄）。

    **做得到才記成 resolved**：重新鏈接失敗時那一筆仍然是 `open`，清單上還看得到它——
    畫面說修好了而媒體庫沒變，是這一票最糟的結果。
    """
    user = current_user(request)
    try:
        view = await resolve_issue(
            session,
            factory,
            issue_id,
            body.action,
            actor=actor_of(user.id if user is not None else None),
            plans=plans,
        )
    except IssueRejectedError as refusal:
        raise issue_refusal(refusal) from refusal
    return issue_out(view)


@router.post("/issues/{issue_id}/ignore", responses=IGNORE_RESPONSES)
async def post_ignore(session: SessionDep, request: Request, issue_id: int) -> IssueOut:
    """「我知道了，不用管它」。不碰磁碟、不碰帳本。

    那個檔案仍然不在，所以**下一輪對帳會再開一筆新的**（`services/issues.ignore_issue`）。
    真的要它安靜下來，按的是「承認刪除並清帳本」。
    """
    user = current_user(request)
    try:
        view = await ignore_issue(
            session, issue_id, actor=actor_of(user.id if user is not None else None)
        )
    except IssueRejectedError as refusal:
        raise issue_refusal(refusal) from refusal
    return issue_out(view)


@router.post("/reconcile", status_code=status.HTTP_202_ACCEPTED, responses=RECONCILE_RESPONSES)
async def post_reconcile(reconciler: ReconcilerDep) -> ReconcileRunOut:
    """開一輪對帳。**202**：收下了，那一輪在背景跑，進度問 `GET /reconcile`。

    一輪要走過整個媒體庫，而 HTTP 請求不該掛在那上面等。正在跑時再按是 409
    `reconcile_running`——不排隊，排隊的那一輪看到的會是同一份磁碟（plan §3.2）。
    """
    try:
        return _run_out(await reconciler.start())
    except IssueRejectedError as refusal:
        raise issue_refusal(refusal) from refusal


@router.get("/reconcile")
async def get_reconcile(reconciler: ReconcilerDep) -> ReconcileStatusOut:
    """上一輪與進行中的那一輪（plan §3.2）。前端在跑的時候輪詢它。"""
    state = reconciler.status()
    return ReconcileStatusOut(
        current=_run_out(state.current) if state.current is not None else None,
        last=_run_out(state.last) if state.last is not None else None,
    )


def issue_out(view: IssueView) -> IssueOut:
    return IssueOut(
        id=view.id,
        type=view.type,
        subject=view.subject,
        job_hash=view.job_hash,
        ledger_id=view.ledger_id,
        path=view.path,
        detail=view.detail,
        status=view.status,
        detected_at=view.detected_at,
        actions=list(view.actions),
    )


def _run_out(report: ReconcileReport) -> ReconcileRunOut:
    return ReconcileRunOut(
        id=report.id,
        started_at=report.started_at,
        finished_at=report.finished_at,
        sides=[_side_out(row) for row in report.sides],
        opened=report.opened,
        updated=report.updated,
    )


def _side_out(report: SideReport) -> SideOut:
    return SideOut(
        side=report.side,
        counted=report.counted,
        unavailable=report.unavailable,
        skipped=list(report.skipped),
    )


def issue_refusal(refusal: IssueRejectedError) -> HTTPException:
    """`reason` 是給畫面挑句子的封閉集合，`detail` 是原文。兩個都送出去。

    **不叫 `_refuse`**：`api/jobs.py` 已經有一支同名的，而「會拒絕就要宣告」那條閘門的
    登記簿以函式名為鍵（`tests/unit/test_openapi_contract.py`）——撞名會讓它把這裡的
    宣告算到另一種形狀上。命名照 `route_refusal` / `access_refusal`。
    """
    body = IssueRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))
