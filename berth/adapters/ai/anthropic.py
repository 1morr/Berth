"""Anthropic Messages 格式（brief §20.24；研究 `docs/research/ai-providers.md` 與底稿）。

**直接用 httpx 打，不用官方 SDK**：SDK 改用 `httpx2`，專案的 respx 攔不到它（研究結論 1）。

- base URL 照 `ANTHROPIC_BASE_URL` 的慣例**不含** `/v1`，空的是官方；請求打 `{base}/v1/messages`。
- 認證送 `Authorization: Bearer`（官方現在的做法，`x-api-key` 是 legacy fallback）與 `x-api-key`
  兩個：第三方不一（DeepSeek 文件只列 `x-api-key`）。沒有 key（自架的 Ollama）兩個都不送。
- 版本 `anthropic-version: 2026-10-21`；不送 `temperature` / `top_p` / `top_k`（這一版送了回 400）。
- 快取兩個 breakpoint：system 最後一個 block 上的顯式 `cache_control`，與請求頂層的自動快取
  （研究結論 6）。工具依名稱排序，前綴才逐字相同。
- usage：`message_start` 起始，`message_delta` 是累計值、有給的欄位就覆寫。全部輸入 =
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`。沒回的是 `None`。
- **不重試**（研究結論 8）。

key 只走標頭，不進網址與錯誤訊息；`request-id` 寫進 log 方便對帳。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx
from httpx_sse import EventSource

from berth.adapters.ai import (
    AiProviderError,
    ChatRequest,
    Endpoint,
    ModelTurn,
    OpaquePart,
    StopReason,
    StreamEvent,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallStarted,
    ToolResult,
    TurnEnded,
    Usage,
    UserTurn,
)
from berth.adapters.ai.wire import (
    LIST_TIMEOUT,
    STREAM_TIMEOUT,
    failure_of_status,
    host_of,
    list_model_ids,
    retry_after,
)
from berth.adapters.http import HttpSession, ServiceError
from berth.domain import AiFailure, ApiFormat

logger = logging.getLogger(__name__)

#: provider 的 JSON 物件（請求 body、事件、content block）。值是 Any：形狀由 API 版本決定、
#: 不認得的欄位要原樣保留（thinking block 帶回下一輪），寫成 TypedDict 反而會丟欄位。
_Json = dict[str, Any]

OFFICIAL_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2026-10-21"
#: 官方 models overview「start with Claude Opus 5.5」。只在官方端點時當預設（研究結論 5）。
DEFAULT_MODEL = "claude-opus-5-5"

_EPHEMERAL = {"type": "ephemeral"}

_STOPS = {
    "end_turn": StopReason.END,
    "stop_sequence": StopReason.END,
    "tool_use": StopReason.TOOL_CALLS,
    "max_tokens": StopReason.MAX_TOKENS,
    "refusal": StopReason.REFUSED,
}

#: 錯誤 body 的 `error.type`（`{"type":"error","error":{"type","message"}}`），比狀態碼更準：
#: 串流中途的錯誤事件只有它。
_ERROR_TYPES = {
    "rate_limit_error": AiFailure.RATE_LIMITED,
    "billing_error": AiFailure.QUOTA_EXHAUSTED,
    "overloaded_error": AiFailure.PROVIDER_DOWN,
    "api_error": AiFailure.PROVIDER_DOWN,
    "timeout_error": AiFailure.PROVIDER_DOWN,
    "authentication_error": AiFailure.AUTH_FAILED,
    "permission_error": AiFailure.AUTH_FAILED,
    "not_found_error": AiFailure.MODEL_NOT_FOUND,
}


def _error_of(body: object) -> tuple[str, str]:
    """`(error.type, error.message)`；body 不是這個形狀時兩個都是空字串。"""
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping):
            return str(error.get("type") or ""), str(error.get("message") or "")
    return "", ""


class AnthropicProvider:
    def __init__(self, endpoint: Endpoint) -> None:
        self._base_url = (endpoint.base_url.strip() or OFFICIAL_BASE_URL).rstrip("/")
        self._api_key = endpoint.api_key.strip()

    @property
    def host(self) -> str:
        return host_of(self._base_url)

    def _session(self) -> HttpSession:
        headers = {"anthropic-version": API_VERSION}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
            headers["x-api-key"] = self._api_key
        return HttpSession(self._base_url, headers=headers, timeout=LIST_TIMEOUT)

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        turn = _TurnAssembler()
        opened = False
        try:
            async with (
                self._session() as session,
                session.stream(
                    "POST", "/v1/messages", json=_body(request), timeout=STREAM_TIMEOUT
                ) as response,
            ):
                if response.status_code != 200:
                    raise await _http_error(response)
                opened = True
                logger.debug("anthropic stream opened", extra={"request_id": _request_id(response)})
                async for sse in EventSource(response).aiter_sse():
                    for event in turn.feed(sse.event, sse.data):
                        yield event
                    if turn.ended is not None:
                        yield turn.ended
                        return
        except AiProviderError as exc:
            if exc.usage == Usage():
                exc.usage = turn.usage(partial=True)
            raise
        except ServiceError as exc:
            raise AiProviderError(
                # 開始回了才斷掉的是 provider 那一側出事；連都沒連上是連不上。
                AiFailure.PROVIDER_DOWN if opened else AiFailure.UNREACHABLE,
                str(exc),
                usage=turn.usage(partial=True),
            ) from exc
        raise AiProviderError(
            AiFailure.PROVIDER_DOWN,
            "stream ended before message_stop",
            usage=turn.usage(partial=True),
        )

    async def list_models(self) -> list[str] | None:
        async with self._session() as session:
            return await list_model_ids(
                session, "/v1/models", params={"limit": 1000}, read_error=_http_error
            )


def _request_id(response: httpx.Response) -> str:
    return str(response.headers.get("request-id", ""))


async def _http_error(response: httpx.Response) -> AiProviderError:
    raw = await response.aread()
    try:
        body: object = json.loads(raw)
    except ValueError:
        body = None
    kind, message = _error_of(body)
    failure = _ERROR_TYPES.get(kind) or failure_of_status(response.status_code)
    if response.status_code == 404 and kind != "not_found_error":
        # 不是 Anthropic 形狀的 404：多半是 base URL 多寫或少寫了一段，不是模型不存在。
        failure = AiFailure.REJECTED
    text = message or raw.decode(errors="replace")[:500]
    detail = f"{response.status_code} {kind}: {text}".strip()
    logger.info(
        "anthropic request failed",
        extra={
            "status": response.status_code,
            "request_id": _request_id(response),
            "detail": detail,
        },
    )
    return AiProviderError(failure, detail, retry_after=retry_after(response))


def _body(request: ChatRequest) -> _Json:
    body: _Json = {
        "model": request.model,
        "max_tokens": request.max_output_tokens,
        "messages": [_message(turn) for turn in request.turns],
        "stream": True,
        # 自動快取：breakpoint 跟著對話往後移。
        "cache_control": _EPHEMERAL,
    }
    if request.system:
        body["system"] = [{"type": "text", "text": request.system, "cache_control": _EPHEMERAL}]
    if request.tools:
        body["tools"] = [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in sorted(request.tools, key=lambda tool: tool.name)
        ]
    return body


def _message(turn: UserTurn | ModelTurn) -> _Json:
    if isinstance(turn, UserTurn):
        # tool_result 一律排在最前面（A §3.6）。
        results = [part for part in turn.parts if isinstance(part, ToolResult)]
        texts = [part for part in turn.parts if isinstance(part, TextPart)]
        content: list[_Json] = [
            {
                "type": "tool_result",
                "tool_use_id": part.call_id,
                "content": part.content,
                "is_error": part.is_error,
            }
            for part in results
        ]
        content += [{"type": "text", "text": part.text} for part in texts]
        return {"role": "user", "content": content}
    blocks: list[_Json] = []
    for part in turn.parts:
        if isinstance(part, TextPart):
            blocks.append({"type": "text", "text": part.text})
        elif isinstance(part, ToolCall):
            blocks.append(
                {
                    "type": "tool_use",
                    "id": part.id,
                    "name": part.name,
                    # 要是 JSON 物件；解不開時送空物件（結果裡會說參數不對）。
                    "input": part.arguments_object() or {},
                }
            )
        elif part.format is ApiFormat.ANTHROPIC:
            blocks.append(dict(part.raw))
    return {"role": "assistant", "content": blocks}


class _TurnAssembler:
    """把一輪的 SSE 事件拼回 `ModelTurn` 與 `Usage`。"""

    def __init__(self) -> None:
        self.ended: TurnEnded | None = None
        self._blocks: dict[int, _Json] = {}
        self._usage: dict[str, int] = {}
        self._stop_raw = ""

    def feed(self, name: str, data: str) -> list[StreamEvent]:
        try:
            payload = json.loads(data) if data else {}
        except ValueError as exc:
            raise AiProviderError(
                AiFailure.REJECTED, f"unreadable event {name}: {data[:200]}"
            ) from exc
        if not isinstance(payload, dict):
            return []
        kind = name or str(payload.get("type", ""))
        if kind == "message_start":
            message = payload.get("message")
            if isinstance(message, Mapping):
                self._take_usage(message.get("usage"))
        elif kind == "content_block_start":
            return self._start_block(payload)
        elif kind == "content_block_delta":
            return self._delta(payload)
        elif kind == "message_delta":
            delta = payload.get("delta")
            if isinstance(delta, Mapping) and delta.get("stop_reason"):
                self._stop_raw = str(delta["stop_reason"])
            self._take_usage(payload.get("usage"))
        elif kind == "message_stop":
            self.ended = TurnEnded(
                stop=_STOPS.get(self._stop_raw, StopReason.OTHER),
                stop_raw=self._stop_raw,
                reply=self._reply(),
                usage=self.usage(partial=False),
            )
        elif kind == "error":
            error_type, message = _error_of(payload)
            raise AiProviderError(
                _ERROR_TYPES.get(error_type, AiFailure.PROVIDER_DOWN),
                f"stream error {error_type}: {message}",
            )
        # ping 與將來的新事件略過。
        return []

    def _start_block(self, payload: Mapping[str, Any]) -> list[StreamEvent]:
        block = payload.get("content_block")
        index = payload.get("index")
        if not isinstance(block, Mapping) or not isinstance(index, int):
            return []
        self._blocks[index] = {**block, "_json": ""}
        if block.get("type") == "tool_use":
            return [ToolCallStarted(id=str(block.get("id", "")), name=str(block.get("name", "")))]
        return []

    def _delta(self, payload: Mapping[str, Any]) -> list[StreamEvent]:
        delta = payload.get("delta")
        index = payload.get("index")
        block = self._blocks.get(index) if isinstance(index, int) else None
        if not isinstance(delta, Mapping) or block is None:
            return []
        kind = delta.get("type")
        if kind == "text_delta":
            text = str(delta.get("text", ""))
            block["text"] = str(block.get("text", "")) + text
            return [TextDelta(text)]
        if kind == "input_json_delta":
            block["_json"] += str(delta.get("partial_json", ""))
        elif kind == "thinking_delta":
            block["thinking"] = str(block.get("thinking", "")) + str(delta.get("thinking", ""))
        elif kind == "signature_delta":
            block["signature"] = str(delta.get("signature", ""))
        return []

    def _reply(self) -> ModelTurn:
        parts: list[TextPart | ToolCall | OpaquePart] = []
        for index in sorted(self._blocks):
            block = self._blocks[index]
            kind = block.get("type")
            if kind == "text":
                parts.append(TextPart(str(block.get("text", ""))))
            elif kind == "tool_use":
                parts.append(
                    ToolCall(
                        id=str(block.get("id") or f"call_{index}"),
                        name=str(block.get("name", "")),
                        arguments=block["_json"],
                    )
                )
            else:
                raw = {key: value for key, value in block.items() if key != "_json"}
                parts.append(OpaquePart(format=ApiFormat.ANTHROPIC, raw=raw))
        return ModelTurn(tuple(parts))

    def _take_usage(self, usage: object) -> None:
        if not isinstance(usage, Mapping):
            return
        for key, value in usage.items():
            if isinstance(value, int) and not isinstance(value, bool):
                self._usage[key] = value

    def usage(self, *, partial: bool) -> Usage:
        """`partial`：串流沒結束，`output_tokens` 還不是最後的數，記成不知道。"""
        fresh = self._usage.get("input_tokens")
        write = self._usage.get("cache_creation_input_tokens")
        read = self._usage.get("cache_read_input_tokens")
        total = None if fresh is None else fresh + (write or 0) + (read or 0)
        return Usage(
            input_tokens=total,
            output_tokens=None if partial else self._usage.get("output_tokens"),
            cache_write_tokens=write,
            cache_read_tokens=read,
        )
