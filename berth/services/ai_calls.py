"""對 provider 的一次呼叫，連同它的用量記錄（plan §11.6〈用量記錄〉、CONTEXT.md 的 AI Call）。

每一個叫模型的地方都走 `call_model`：設定頁的測試（票 07）、對話核心（票 08）、AI 任務（M6）。
**成與不成都寫一列 `ai_calls`**，沒成的帶著斷掉之前已知的 tokens 與分類，再把錯誤原樣拋回去。

那一列**自己 commit**：呼叫端接下來多半要再打一次網路（探針的下一步、對話的下一輪），用量不能
跟著後面的失敗一起 rollback 掉。網路在交易之外（plan §3.3）：送出之前什麼都不寫。
"""

from __future__ import annotations

import time

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import (
    AiProviderError,
    ChatProvider,
    ChatRequest,
    TurnEnded,
    Usage,
)
from berth.domain import AiCallOrigin, AiFailure, ApiFormat
from berth.models import AiCall
from berth.models.types import utcnow
from berth.services.commands import Effect, command


# 花掉的 tokens 收不回來。
@command(Effect.IRREVERSIBLE)
async def call_model(
    session: AsyncSession,
    provider: ChatProvider,
    request: ChatRequest,
    *,
    format: ApiFormat,
    origin: AiCallOrigin,
    user_id: int | None,
) -> TurnEnded:
    """送一輪、等它講完，記一列 `ai_calls`。沒成是 `AiProviderError`（那一列照樣寫了）。

    其他例外（取消、Berth 自己的錯）不記：說不出那一次是成是敗。
    """
    started_at = utcnow()
    started = time.monotonic()

    async def record(usage: Usage, failure: AiFailure | None) -> None:
        session.add(
            AiCall(
                created_at=started_at,
                format=format,
                host=provider.host,
                model=request.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                duration_ms=round((time.monotonic() - started) * 1000),
                origin=origin,
                user_id=user_id,
                failure=failure,
            )
        )
        await session.commit()

    ended: TurnEnded | None = None
    try:
        # 讀到串流結束，不在 TurnEnded 就跳出：產生器要自己走完，`async with` 才在這裡關掉連線。
        async for event in provider.stream(request):
            if isinstance(event, TurnEnded):
                ended = event
        if ended is None:
            # adapter 保證最後一個是 TurnEnded；沒有就是它的錯，當成 provider 那一側出事。
            raise AiProviderError(AiFailure.PROVIDER_DOWN, "stream ended without a turn")
    except AiProviderError as exc:
        await record(exc.usage, exc.failure)
        raise
    await record(ended.usage, None)
    return ended
