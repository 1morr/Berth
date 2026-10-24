"""AI 活動頁的端點（M5 票 14，`.scratch/m5/ai-activity-shape.md`）。

登入就進得來：管理員看全部、其他人只看自己對話裡的，在 service 裡分（`services.ai_activity`）。
只有讀；撤銷走結果卡同一支（`POST /conversations/{id}/messages/{m}/tools/{call}/undo`）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from berth.api.conversations import AssistantDep
from berth.api.deps import SessionDep
from berth.api.gate import current_user
from berth.domain import ActivityUndo, ActivityVia
from berth.services.ai_activity import read_activity

router = APIRouter(prefix="/ai-activity", tags=["assistant"])


class ReplyTokensOut(BaseModel):
    """那一次回覆（使用者那一句之後的每一次模型呼叫）花的 tokens。`null` 是不知道。"""

    model_config = ConfigDict(from_attributes=True)

    input: int | None
    output: int | None


class ActivityEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: int
    conversation_title: str
    #: 是看的人自己的對話：連得回側面板；別人的只印標題。
    own: bool
    #: 撤銷的位址（同結果卡）。
    message_id: int
    call_id: str
    at: datetime
    user_id: int
    user_name: str
    via: ActivityVia
    tool: str
    # Any：模型給的輸入，每個工具的欄位不同（登錄表的 pydantic 輸入）。
    arguments: dict[str, Any]
    #: AI 給的理由，原文；舊的紀錄沒有時是空字串。
    reason: str
    #: 結果型別的名字與那一份結果（同 `ToolResultPart`），前端照它說做了什麼。
    result_type: str
    # Any：每個結果型別的形狀不同（`ToolResults`）。
    result: dict[str, Any]
    tokens: ReplyTokensOut
    undo: ActivityUndo
    undone_at: datetime | None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 新的在前。
    entries: list[ActivityEntryOut]
    #: 更早的沒列出來（`services.ai_activity.LIMIT`）。
    truncated: bool


@router.get("")
async def get_activity(session: SessionDep, request: Request, runs: AssistantDep) -> ActivityOut:
    viewer = current_user(request)
    # 在要登入的門後面，門禁跑過之後一定有人。
    assert viewer is not None
    found = await read_activity(session, runs.registry, viewer=viewer)
    return ActivityOut.model_validate(found)
