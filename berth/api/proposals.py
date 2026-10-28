"""確認卡（Proposal）的端點（plan §6、M5 票 08；`services/proposals.py`）。

登入就進得來（一般使用者也是），看得到與按得到的範圍由命令判斷：自己的，管理員是每一張；別人的
看不到也按不到，是 `proposal_missing`。

**決定的 body 只有核准、勾選與逐列的 Route、字幕組**（`extra="forbid"`）：執行用伺服器存的那一份
參數，前端送來的參數一律不收（brief §20.24：`VercelAIAdapter` 預設信任前端，偽造一則核准就能
換參數）。例外只有 Route（票 23b）與訂閱的字幕組（票 26）：可選的不只一個時人在卡片上選，
只收提出時存下的那份清單裡的。

狀態變更經 `GET /events/stream` 的 `event: proposal` 推出去；畫面讓 `['proposals']` 失效再問一次。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ExecutorDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.domain import (
    ActorKind,
    FeedKind,
    PrimeMode,
    ProposalRefusal,
    ProposalRowOutcome,
    ProposalStatus,
)
from berth.services import proposals
from berth.services.commands import Effect, Flag
from berth.services.proposals import ProposalRejectedError, ProposalView

router = APIRouter(prefix="/proposals", tags=["proposals"])

_STATUS: dict[ProposalRefusal, int] = {
    ProposalRefusal.PROPOSAL_MISSING: status.HTTP_404_NOT_FOUND,
    # 已經不在等人了：重新問一次清單就看得到它現在的樣子。
    ProposalRefusal.PROPOSAL_DECIDED: status.HTTP_409_CONFLICT,
    ProposalRefusal.PROPOSAL_EXPIRED: status.HTTP_409_CONFLICT,
    # 勾選本身說不通（空的、重複、超出列數）。
    ProposalRefusal.SELECTION_INVALID: status.HTTP_422_UNPROCESSABLE_CONTENT,
    # 要選 Route 的列沒選，或選了清單外的（票 23b）。
    ProposalRefusal.ROUTE_REQUIRED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ProposalRefusal.ROUTE_NOT_OFFERED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    # 要選字幕組的列沒選，或選了清單外的（票 26）。
    ProposalRefusal.SUBGROUP_REQUIRED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ProposalRefusal.SUBGROUP_NOT_OFFERED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ProposalRefusal.FIRST_BATCH_NOT_OFFERED: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class ProposalRefusalOut(BaseModel):
    """與其他群組的拒絕同形：`reason` 挑句子，`detail` 是原文。`proposal_decided` 的 `detail` 是
    它現在的狀態。"""

    reason: ProposalRefusal
    detail: str


class RouteOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 提出那一刻的名字。
    name: str


class RouteAskOut(BaseModel):
    """一列要人在卡片上選的 Route（票 23b）：作品放得進的不只一條。"""

    model_config = ConfigDict(from_attributes=True)

    options: list[RouteOptionOut]
    #: 這部作品上次送單用的那一條；沒用過是 `null`（不預選）。
    preselected: int | None


class SubgroupOptionOut(BaseModel):
    """訂閱可選的一個字幕組（票 26）。"""

    model_config = ConfigDict(from_attributes=True)

    #: 決定時送回來的那一格：Mikan 是字幕組 id 的字串，關鍵字訂閱是字幕組名。
    key: str
    name: str
    releases: int
    updated: date | None
    latest: str
    #: 關鍵字訂閱的第一批：按下確認就送出的發佈名，新的在前。Mikan 是空清單（整季）。
    titles: list[str]


class SubgroupAskOut(BaseModel):
    """一列訂閱的字幕組（票 26）。`required` 時勾著的這一列一定要選，`preselected` 是模型建議的
    那一個。"""

    model_config = ConfigDict(from_attributes=True)

    options: list[SubgroupOptionOut]
    preselected: str | None
    required: bool


class SubscriptionRefOut(BaseModel):
    """這部作品提出那一刻已經有的一條訂閱（票 26）。網址不給：聚合 feed 的網址帶 token。"""

    model_config = ConfigDict(from_attributes=True)

    feed_id: int
    name: str
    kind: FeedKind
    #: 它收的字幕組；空字串是搜到的每一組都收。
    subgroup: str


class ProposalPreviewOut(BaseModel):
    """提出那一刻伺服器算的。卡片照 `effect` 與 `flags` 說「不可逆」「會送出 torrent」。"""

    model_config = ConfigDict(from_attributes=True)

    effect: Effect
    flags: list[Flag]
    #: 逐列：提出時跑過命令的驗證沒有。`false` 是命令沒有驗證函式，預覽只看得到參數。
    checked: list[bool]
    #: 逐列：出自外部內容（網頁）的自由文字欄位名（M5 票 14）。卡片只在這幾格標警示。
    external_fields: list[list[str]]
    #: 超過一張卡的上限、留給下一張的列數（送單的數量閘）。
    held_back: int
    #: 逐列：按下去會送出幾個 torrent；`null` 是要送出時才知道（讀不到 Mikan 的單一 feed）。
    #: 不送 torrent 的命令是空清單。
    torrents: list[int | None]
    #: 逐列：要人選 Route 的列是可選清單，其餘是 `null`。命令沒有 Route 的是空清單。
    routes: list[RouteAskOut | None]
    #: 逐列：訂閱的字幕組選項，其餘是 `null`。不是訂閱的命令是空清單。
    subgroups: list[SubgroupAskOut | None]
    #: 逐列：這部作品已經有的訂閱。不是訂閱的命令是空清單。
    existing: list[list[SubscriptionRefOut]]
    #: 逐列：卡片上能不能選第一輪（關鍵字訂閱）。都不能是空清單。
    first_batch: list[bool]


class ProposalRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outcome: ProposalRowOutcome
    #: 拒絕理由的值（`refused`）或例外的型別名（`failed`）；做成的與沒勾的是空字串。
    reason: str
    detail: str
    #: 命令回傳值的 JSON 形狀，做成的那一列才有。`Any`：形狀隨命令。
    result: Any


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 登錄表上的命令名（`"<模組>.<函式>"`）。
    command: str
    #: 每一列一份命令輸入，執行時就用這一份。`Any`：每一格的型別隨命令。
    arguments: list[dict[str, Any]]
    arguments_hash: str
    preview: ProposalPreviewOut
    #: 替誰提出、按得到的那個人。
    user_id: int
    proposer: ActorKind
    #: 提出它的那段對話；人提出的是 `null`。
    conversation_id: str | None
    #: 提出它的那一次 tool call（AI 提出的才有）：側面板照它把卡片畫在那一格工具呼叫上（票 13）。
    tool_call_id: str | None
    status: ProposalStatus
    created_at: datetime
    expires_at: datetime
    decided_by: int | None
    decided_at: datetime | None
    #: 核准時勾的那幾列（0 起算）；`null` 是全部。
    selection: list[int] | None
    #: 逐列結果；還沒執行是 `null`。
    results: list[ProposalRowOut] | None
    #: 脫離提出它的那一輪的時刻（使用者沒按就繼續說話）；之後按下去當場執行。
    detached_at: datetime | None
    #: 核准時逐列在卡片上選的 Route；沒選過是 `null`。
    routes: list[int | None] | None
    #: 核准時逐列在卡片上選的字幕組（選項的 `key`）；沒選過是 `null`。
    subgroups: list[str | None] | None
    #: 核准時逐列選的第一輪；沒選過是 `null`（照存下的：下載這些並追之後的）。
    first_batch: list[PrimeMode | None] | None


class ProposalDecisionIn(BaseModel):
    """只有決定本身。參數不在這裡：執行用伺服器存的那一份，Route 與字幕組除外（票 23b、26）。"""

    model_config = ConfigDict(extra="forbid")

    approve: bool
    #: 總覽卡上勾著的那幾列（0 起算）；`null` 是全部。拒絕時不看它。
    selection: list[int] | None = None
    #: 逐列的 Route，與列對齊；只有 `preview.routes` 有清單的列能給值，勾著的那幾列必給。
    routes: list[int | None] | None = None
    #: 逐列的字幕組（選項的 `key`），與列對齊；只有 `preview.subgroups` 有選項的列能給值，
    #: `required` 而勾著的那幾列必給。
    subgroups: list[str | None] | None = None
    #: 逐列的第一輪（`all`「下載這些並追之後的」/ `later`「只追之後的」）；只有
    #: `preview.first_batch` 是真的列能給值，沒給的照存下的。
    first_batch: list[PrimeMode | None] | None = None


@router.get("")
async def get_proposals(
    session: SessionDep, request: Request, conversation_id: str | None = None
) -> list[ProposalOut]:
    """按的人決定得了的卡片，舊的在前；帶 `conversation_id` 只列那一段對話的。"""
    user = current_user(request)
    # 在要登入的門後面，門禁跑過之後一定有人。
    assert user is not None
    found = await proposals.list_proposals(
        session, conversation_id, user_id=user.id, role=user.role
    )
    return [_out(view) for view in found]


@router.post("/{proposal_id}/decide", responses=refusal_responses(ProposalRefusalOut, _STATUS))
async def post_decision(
    session: SessionDep,
    executor: ExecutorDep,
    request: Request,
    proposal_id: int,
    body: ProposalDecisionIn,
) -> ProposalOut:
    """核准或拒絕。不在對話裡的、已經脫離對話的，核准之後當場執行，回逐列結果；還在對話裡的只記
    決定，由對話恢復時執行（票 13）。"""
    user = current_user(request)
    assert user is not None
    try:
        view = await proposals.decide(
            session,
            executor,
            proposal_id,
            approve=body.approve,
            selection=body.selection,
            routes=body.routes,
            subgroups=body.subgroups,
            first_batch=body.first_batch,
            user_id=user.id,
            role=user.role,
        )
    except ProposalRejectedError as refusal:
        raise proposal_refusal(refusal) from refusal
    return _out(view)


def proposal_refusal(refusal: ProposalRejectedError) -> HTTPException:
    body = ProposalRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


def _out(view: ProposalView) -> ProposalOut:
    return ProposalOut.model_validate(view)
