"""AI 設定的端點（M5 票 07、plan §11.6〈provider〉）。掛在 `/settings` 底下，所以只有管理員進得來
（`api/gate.py`）。

**key 只進不出**：回的只有 `api_key_present`。測試失敗時回的原文是端點的錯誤訊息，不含 key
（key 只走標頭）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.domain import AiFailure, AiProbeStep, AiRefusal, ApiFormat, ToolGap
from berth.services.ai import AiRefusedError, list_models, read_ai, run_ai_test, set_ai

router = APIRouter(prefix="/settings/ai", tags=["settings"])

_STATUS: dict[AiRefusal, int] = {
    AiRefusal.BASE_URL_INVALID: status.HTTP_422_UNPROCESSABLE_CONTENT,
    #: 前提還沒齊：先填 key（官方端點）或 base URL，與模型。
    AiRefusal.NOT_READY: status.HTTP_409_CONFLICT,
}


class AiRefusalOut(BaseModel):
    """與其他群組的拒絕同形：`reason` 挑句子，`detail` 是原文。"""

    reason: AiRefusal
    detail: str


# Any：FastAPI 的 `responses` 參數本身就是這個型別（同 `api/notify.py`）。
def _responses(*reasons: AiRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(AiRefusalOut, {reason: _STATUS[reason] for reason in reasons})


def ai_refusal(refusal: AiRefusedError) -> HTTPException:
    body = AiRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


class AiToolTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    supported: bool
    #: 不支援的樣子；支援是 `null`。
    gap: ToolGap | None
    #: 端點的原文或模型回的文字開頭，給技術細節。
    detail: str
    tested_at: datetime


class AiSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    format: ApiFormat
    #: 空字串是官方端點。
    base_url: str
    #: 存過 key 沒有。key 本身永遠不回來。
    api_key_present: bool
    #: 存的模型；空字串是沒填。
    model: str
    #: 每一種格式的官方端點在模型空著時用的那一個；`null` 是一定要選或填（第三方一律沒有）。
    official_models: dict[ApiFormat, str | None]
    #: AI 設定好了：有端點（填了 base URL，或官方端點而且有 key）、有模型。
    ready: bool
    #: 上一次測試對工具呼叫的結論；`null` 是還沒測，或格式、base URL、模型改過之後還沒重測。
    tool_test: AiToolTestOut | None


class AiSettingsIn(BaseModel):
    format: ApiFormat
    #: 空字串是官方端點。
    base_url: str
    #: 空字串是沒填（有預設的官方端點用 `official_models` 裡那一個）。
    model: str
    #: 不送或 `null` 是留著存著的那一把；空字串是清掉。
    api_key: str | None = None


class UsageOut(BaseModel):
    """一次呼叫的 tokens。`null` 是端點沒回那一格（不知道），不是 0。"""

    model_config = ConfigDict(from_attributes=True)

    #: 全部輸入，含快取寫入與讀取。
    input_tokens: int | None
    output_tokens: int | None
    cache_write_tokens: int | None
    cache_read_tokens: int | None


class AiProbeCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step: AiProbeStep
    usage: UsageOut


class AiTestOut(BaseModel):
    """一次測試。端點說不行也是 200：那是「測試的結果」，不是請求錯了。"""

    model_config = ConfigDict(from_attributes=True)

    #: 第一次（不帶工具）沒成的原因；成了是 `null`。
    failure: AiFailure | None
    #: 端點的原文，給技術細節。
    detail: str
    #: 限流時端點說的「幾秒後再來」。
    retry_after: float | None
    #: 第一次模型回的文字。
    reply: str
    #: 這次測試打的每一次請求與它的 tokens，照順序。
    calls: list[AiProbeCallOut]
    #: 支不支援工具呼叫的結論（已存下）；`null` 是沒測到結論。
    tools: AiToolTestOut | None
    #: 沒測到結論的原因（限流、provider 掛掉、連不上）。
    tools_failure: AiFailure | None
    tools_detail: str


class AiModelsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 端點列得出的模型 id；`null` 是列不出來，退回手填。
    models: list[str] | None
    #: 有下一步的失敗（key 不對、連不上）；列不出來但不是錯時是 `null`。
    failure: AiFailure | None
    detail: str


def _user_id(request: Request) -> int:
    user = current_user(request)
    # 在要登入的門後面，門禁跑過之後一定有人。
    assert user is not None
    return user.id


@router.get("")
async def get_ai(session: SessionDep) -> AiSettingsOut:
    return AiSettingsOut.model_validate(await read_ai(session))


@router.put("", responses=_responses(AiRefusal.BASE_URL_INVALID))
async def put_ai(session: SessionDep, body: AiSettingsIn) -> AiSettingsOut:
    """存設定。不連端點：連得上與否是「測試」的事。"""
    try:
        view = await set_ai(
            session,
            format=body.format,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key,
        )
    except AiRefusedError as exc:
        raise ai_refusal(exc) from exc
    return AiSettingsOut.model_validate(view)


@router.post("/test", responses=_responses(AiRefusal.NOT_READY))
async def post_test(session: SessionDep, factory: ClientFactoryDep, request: Request) -> AiTestOut:
    """照存著的設定打三次請求（`services.ai`），每一次都記進用量。"""
    try:
        result = await run_ai_test(session, factory, user_id=_user_id(request))
    except AiRefusedError as exc:
        raise ai_refusal(exc) from exc
    return AiTestOut.model_validate(result)


@router.get("/models", responses=_responses(AiRefusal.NOT_READY))
async def get_models(session: SessionDep, factory: ClientFactoryDep) -> AiModelsOut:
    try:
        listed = await list_models(session, factory)
    except AiRefusedError as exc:
        raise ai_refusal(exc) from exc
    return AiModelsOut.model_validate(listed)
