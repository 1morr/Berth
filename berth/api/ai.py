"""AI provider 設定的端點（M5 票 09、plan §11.6〈provider〉）。

掛在 `/settings` 底下，所以只有管理員進得來（`api/gate.py`）。**key 只進不出**：回的是 `has_key`
與 `has_tavily_key`；送進來的 key 欄位是 `null` 或空字串表示沒動，清掉走
`DELETE /settings/ai/keys/{key}`。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.errors import refusal_responses
from berth.domain import (
    AiModelSource,
    AiProbeFailure,
    AiProvider,
    AiReasoning,
    AiRefusal,
    AiSecret,
    PriceTable,
)
from berth.services.ai import (
    AiForm,
    AiRefusedError,
    forget_ai_key,
    list_models,
    read_ai,
    reasoning_takes_effect,
    set_ai,
    suggest_models,
    test_ai,
)

router = APIRouter(prefix="/settings/ai", tags=["settings"])

_STATUS: dict[AiRefusal, int] = {
    AiRefusal.BASE_URL_INVALID: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AiRefusal.KEY_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AiRefusal.MODEL_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class AiRefusalOut(BaseModel):
    """與其他群組的拒絕同形：`reason` 挑句子，`detail` 是原文（沒有就是空字串）。"""

    reason: AiRefusal
    detail: str


def _responses() -> dict[int | str, dict[str, Any]]:
    return refusal_responses(AiRefusalOut, _STATUS)


def ai_refusal(refusal: AiRefusedError) -> HTTPException:
    body = AiRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


class PriceSourceOut(BaseModel):
    """價目從哪來（M5 票 21b）。"""

    model_config = ConfigDict(from_attributes=True)

    table: PriceTable
    #: genai-prices 的版本；補位表是空字串。
    version: str
    #: genai-prices 認出的服務商（`Deepseek`）；補位表是空字串。
    vendor: str
    #: 補位表那一列的查證日期；genai-prices 是 `null`。
    verified: date | None


class AiPriceOut(BaseModel):
    """美元 / 百萬 token（`adapters.ai.prices`）。分時段計價的服務是現在這個時段的價。"""

    model_config = ConfigDict(from_attributes=True)

    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write: Decimal
    source: PriceSourceOut


class AiEndpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 空的是官方端點。
    base_url: str
    model: str
    #: 存過 key 沒有。key 本身永遠不回來。
    has_key: bool
    #: 推理程度；沒設過是 `medium`（沒有「預設」這一級）。
    reasoning: AiReasoning
    #: 這個端點上查不到這個模型的價是 `null`：費用未知，不當 0。
    price: AiPriceOut | None


class AiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 關著就是沒有 AI，其餘功能照常。
    enabled: bool
    #: 現在用的接口。
    provider: AiProvider
    anthropic: AiEndpointOut
    openai: AiEndpointOut
    has_tavily_key: bool


class AiTestIn(BaseModel):
    """表單上的一種接口。`api_key` 是 `null` 或空字串表示沒動：存檔時留著、測試時用存著的那一把；
    只在 base URL 與存著的相同時（留空與填官方網址算同一個），不同就是 `key_missing`。"""

    provider: AiProvider
    #: 空字串是官方端點。
    base_url: str
    model: str
    api_key: str | None = None


class AiIn(AiTestIn):
    enabled: bool
    #: `null` 或不帶是不動。
    reasoning: AiReasoning | None = None
    #: `null` 或空字串是不動。
    tavily_api_key: str | None = None


class AiTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ok: bool
    #: 沒成功的分類；成功是 `null`。
    failure: AiProbeFailure | None
    #: 服務回的 HTTP 狀態碼；成功或沒有回應是 `null`。
    status: int | None
    #: 服務回的原文（key 若被貼回來已遮掉）。
    detail: str
    #: 回話的模型（服務自己報的名字）；失敗是空字串。
    model: str


class AiModelsIn(BaseModel):
    """「取得模型」：表單上還沒存的接口、base URL 與 key，不要模型名。`api_key` 的規則同
    `AiTestIn`：空著時網址與存著的相同才用存著的那把。"""

    provider: AiProvider
    #: 空字串是官方端點。
    base_url: str
    api_key: str | None = None


class AiModelsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 模型欄的建議；不在裡面的照樣可以填。端點列的照它的順序，本機表排序過。
    models: list[str]
    #: `endpoint` 是端點列的；`prices` 是本機價目表（沒按、問不到、或端點列出空的）。
    source: AiModelSource
    #: 「取得模型」沒問到的分類；問到了或只查本機表是 `null`。
    failure: AiProbeFailure | None
    #: 服務回的 HTTP 狀態碼；成功或沒有回應是 `null`。
    status: int | None
    #: 服務回的原文（key 若被貼回來已遮掉）。
    detail: str


class AiReasoningOut(BaseModel):
    #: 假的是這個接口上的這個模型不收推理程度，Berth 不送（M5.5 票 17）。
    applies: bool


def _form(body: AiTestIn) -> AiForm:
    reasoning = body.reasoning if isinstance(body, AiIn) else None
    return AiForm(body.provider, body.base_url, body.model, body.api_key, reasoning)


@router.get("")
async def get_ai(session: SessionDep) -> AiOut:
    return AiOut.model_validate(await read_ai(session))


@router.put("", responses=_responses())
async def put_ai(session: SessionDep, body: AiIn) -> AiOut:
    """存表單上那一種接口並設成現在用的；另一種存著的不動。開啟要有 key 與模型名。"""
    try:
        view = await set_ai(
            session, enabled=body.enabled, form=_form(body), tavily_api_key=body.tavily_api_key
        )
    except AiRefusedError as exc:
        raise ai_refusal(exc) from exc
    return AiOut.model_validate(view)


@router.delete("/keys/{key}")
async def delete_ai_key(session: SessionDep, key: AiSecret) -> AiOut:
    """清掉一把 key。清的是現在用的接口的 key 時一併關掉 AI。"""
    return AiOut.model_validate(await forget_ai_key(session, key))


@router.post("/test", responses=_responses())
async def post_ai_test(session: SessionDep, factory: ClientFactoryDep, body: AiTestIn) -> AiTestOut:
    """照表單打一次最小呼叫，不存。服務拒絕也是 200：那是測試的結果，不是請求錯了。"""
    try:
        result = await test_ai(session, factory, _form(body))
    except AiRefusedError as exc:
        raise ai_refusal(exc) from exc
    return AiTestOut.model_validate(result)


@router.get("/models")
async def get_ai_models(
    provider: AiProvider, base_url: Annotated[str, Query()] = ""
) -> AiModelsOut:
    """沒按「取得模型」之前的建議：本機價目表照這個網址認出的那一家。不帶 key、不連外。"""
    return AiModelsOut.model_validate(await suggest_models(provider, base_url))


@router.get("/reasoning")
async def get_ai_reasoning(
    provider: AiProvider, model: Annotated[str, Query()] = ""
) -> AiReasoningOut:
    """表單上的模型收不收推理程度。不帶 key、不連外。"""
    return AiReasoningOut(applies=await reasoning_takes_effect(provider, model))


@router.post("/models", responses=_responses())
async def post_ai_models(
    session: SessionDep, factory: ClientFactoryDep, body: AiModelsIn
) -> AiModelsOut:
    """向表單上的端點問模型，不存。問不到也是 200：退回本機價目表並帶著原因。"""
    try:
        result = await list_models(session, factory, body.provider, body.base_url, body.api_key)
    except AiRefusedError as exc:
        raise ai_refusal(exc) from exc
    return AiModelsOut.model_validate(result)
