"""AI 用量頁的端點（M5 票 21、研究 C5）。

掛在 `/settings` 底下，所以只有管理員進得來（`api/gate.py`）：花的是管理員設的 key。每輪的步驟頁
（一般使用者也看得到自己的）在 `/agent/runs/{id}`（`api/agent.py`）。

**不知道的不當 0**：快取讀寫與費用都是 `{known, unknown}`——知道的加總與幾次呼叫不知道。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, NonNegativeFloat

from berth.api.ai import AiPriceOut
from berth.api.deps import SessionDep
from berth.domain import AiStopReason
from berth.domain.spend import SpendAlertKind
from berth.services.usage import read_usage, set_spend_alert

router = APIRouter(prefix="/settings/usage", tags=["settings"])


class TokenTallyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 知道的那幾次呼叫的加總。
    known: int
    #: 幾次呼叫知道（0 也是知道）。`0` 而 `unknown` 不是 0 就是全部不知道。
    counted: int
    #: 幾次呼叫不知道（接口沒報）。
    unknown: int


class CostTallyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 估計費用（美元），只算查得到價目的呼叫。
    known: float
    #: 幾次呼叫算得出費用。
    counted: int
    #: 幾次有回應的呼叫算不出費用（查不到價目）；出錯沒有回應的沒有花費，不數。
    unknown: int


class DayUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 伺服器時區的日期；`totals` 的這一格是今天。
    day: date
    calls: int
    #: 全部的 input，含快取讀寫。
    input_tokens: int
    #: 沒命中、也沒寫進快取的 input。
    new_input: int
    cache_read: TokenTallyOut
    cache_write: TokenTallyOut
    output_tokens: int
    #: 快取讀 ÷ input；沒有 input 是 `null`。
    hit_rate: float | None
    cost: CostTallyOut
    #: 伺服器端網搜的次數（Anthropic `web_search`）。
    web_searches: int
    #: Tavily 搜了幾次（花使用者 Tavily 帳號的 credit，不在估計費用裡）。
    tavily_searches: int


class GuardCountsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 完成之外的每一種停止原因各幾輪；0 的也在。
    stops: dict[AiStopReason, int]
    blocked: int
    refused: int
    failed: int
    truncated: int


class RunRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: datetime
    user_name: str
    #: 還在跑是 `null`。
    stop_reason: AiStopReason | None
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    #: 有一次算不出來就是 `null`。
    cost_usd: float | None


class ModelPriceRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model: str
    #: 打的端點；`null` 是票 21b 之前記的呼叫（照接口種類查價）。
    base_url: str | None
    #: 現在的價（分時段計價的服務照現在這個時段）；查不到是 `null`：費用「未知」。
    price: AiPriceOut | None


class SpendAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: SpendAlertKind
    #: 今天的估計費用（美元）。
    today: Decimal
    #: 比的那個數：提醒值，或近 14 天有用量那幾天的中位數。
    against: Decimal


class SpendCheckOut(BaseModel):
    """今天的花費提醒，與它沒算進去的呼叫數：只提醒、不停用；費用未知的不當 0。"""

    model_config = ConfigDict(from_attributes=True)

    alerts: list[SpendAlertOut]
    #: 今天幾次有回應的呼叫費用不知道（查不到價目）：提醒沒算進它們。
    unknown_today: int
    #: 前 14 天（異常的基準）幾次呼叫的費用不知道。
    unknown_before: int


class AiUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    today: date
    #: 有用量的日子加上今天，新的在前（近 30 天）。
    days: list[DayUsageOut]
    totals: DayUsageOut
    runs_count: int
    guards: GuardCountsOut
    #: 最新的 20 輪。
    runs: list[RunRowOut]
    #: 期間內用到的模型。
    prices: list[ModelPriceRowOut]
    #: 每日提醒值（美元）；`null` 是不提醒。
    daily_alert_usd: float | None
    #: 只提醒，不停用 AI。
    spend: SpendCheckOut


class SpendAlertIn(BaseModel):
    #: `null` 是不提醒。
    daily_usd: NonNegativeFloat | None


class SpendAlertSetOut(BaseModel):
    daily_usd: float | None


@router.get("")
async def get_usage(session: SessionDep) -> AiUsageOut:
    """近 30 天的用量、防護次數、最近的輪、價目與花費提醒。"""
    return AiUsageOut.model_validate(await read_usage(session))


@router.put("/alert")
async def put_spend_alert(session: SessionDep, body: SpendAlertIn) -> SpendAlertSetOut:
    """存每日提醒值。只提醒，不擋任何東西。"""
    return SpendAlertSetOut(daily_usd=await set_spend_alert(session, body.daily_usd))
