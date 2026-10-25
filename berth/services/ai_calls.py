"""對 provider 的一次呼叫，連同它的用量記錄（plan §11.6〈用量記錄〉、CONTEXT.md 的 AI Call）。

每一個叫模型的地方都走 `call_model`：設定頁的測試（票 08）、對話核心（票 10）、AI 任務（M6）。
**成與不成都寫一列 `ai_calls`**，沒成的帶著斷掉之前已知的 tokens 與分類，再把錯誤原樣拋回去。

**被取消的也一列**（`failure = cancelled`）：使用者在串流講到一半時關掉，已經送出的輸入照樣
花掉了，記的是取消前最後一次 `UsageReported` 說的數字。

那一列**自己 commit**：呼叫端接下來多半要再打一次網路（探針的下一步、對話的下一輪），用量不能
跟著後面的失敗一起 rollback 掉。網路在交易之外（plan §3.3）：送出之前什麼都不寫。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import (
    AiProviderError,
    ChatProvider,
    ChatRequest,
    TurnEnded,
    Usage,
    UsageReported,
)
from berth.domain import AiCallOrigin, AiFailure, ApiFormat
from berth.models import AiCall
from berth.models.types import utcnow
from berth.services.commands import Effect, command

logger = logging.getLogger(__name__)


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

    取消也記一列，再把取消往上傳。Berth 自己的錯不記：說不出那一次是成是敗。
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
    known = Usage()
    try:
        # 讀到串流結束，不在 TurnEnded 就跳出：產生器要自己走完，`async with` 才在這裡關掉連線。
        async for event in provider.stream(request):
            if isinstance(event, UsageReported):
                known = event.usage
            elif isinstance(event, TurnEnded):
                ended = event
        if ended is None:
            # adapter 保證最後一個是 TurnEnded；沒有就是它的錯，當成 provider 那一側出事。
            raise AiProviderError(
                AiFailure.PROVIDER_DOWN, "stream ended without a turn", usage=known
            )
    except AiProviderError as exc:
        await record(exc.usage, exc.failure)
        raise
    except asyncio.CancelledError:
        writing = asyncio.ensure_future(record(known, AiFailure.CANCELLED))
        while not writing.done():
            # 再被 cancel 也等它寫完：放手的話它在背景用著呼叫端正要關掉的同一個 session。
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.shield(writing)
        if writing.exception() is not None:
            # 丟出去的是取消本身；寫不成只記 log。
            logger.error("ai call of a cancelled stream not logged", exc_info=writing.exception())
        raise
    await record(ended.usage, None)
    return ended
