"""一次模型呼叫記成 `ai_calls` 的哪一列（M5 票 11、17；票 18 從 `services.agent` 拆出來）。

一輪對話（`agent.Turn`）與壓縮的摘要（`compaction.compact`）都照這一份記：token、快取、估計費用、
伺服器端網搜。認不得的模型與不知道價錢的網搜照 `adapters.ai.prices` 記 `NULL`。
"""

from __future__ import annotations

import time

from pydantic_ai.messages import ModelResponse

from berth.adapters.ai.prices import cost_of, web_search_cost
from berth.adapters.ai.usage import usage_of, web_searches_of
from berth.domain import AiProvider
from berth.models import AiCall


def call_row(
    *,
    run_id: str,
    step: int,
    provider: AiProvider,
    model_name: str,
    official: bool,
    response: ModelResponse | None,
    started: float,
    error: str,
) -> AiCall:
    """`response` 是 `None`：出錯、沒有回應（`error` 是原文，key 要先遮掉）。"""
    row = AiCall(
        run_id=run_id,
        step=step,
        model=model_name,
        duration_ms=elapsed_ms(started),
        error=error,
        # 預設是 `None` 也明寫：SQLAlchemy 的預設會蓋掉明設的 `None`（`AiCall` 那一格說了）。
        web_search_cost_usd=None,
    )
    if response is None:
        return row
    usage = usage_of(provider, response.usage)
    cost = cost_of(model_name, usage)
    searches = web_searches_of(response)
    search_cost = web_search_cost(searches, official=official)
    row.model = response.model_name or model_name
    row.input_tokens, row.output_tokens = usage.input, usage.output
    row.cache_read_tokens, row.cache_write_tokens = usage.cache_read, usage.cache_write
    row.web_searches = searches
    row.web_search_cost_usd = float(search_cost) if search_cost is not None else None
    # 網搜的價不知道就不計（畫面說明），不讓整筆變成不知道。
    if cost is not None and search_cost is not None:
        cost += search_cost
    row.cost_usd = float(cost) if cost is not None else None
    row.finish_reason = response.finish_reason or ""
    return row


def elapsed_ms(started: float) -> int:
    """`started` 是 `time.monotonic()`。"""
    return int((time.monotonic() - started) * 1000)
