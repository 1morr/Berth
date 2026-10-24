"""OpenAI 相容格式：Chat Completions（brief §20.24；研究 `docs/research/ai-providers.md` 結論 2）。

OpenAI、OpenRouter、vLLM、Ollama、DeepSeek 都收這一支，工具呼叫也都能用。**直接用 httpx 打，
不用官方 SDK**（同 `anthropic.py`，研究結論 1）。

- base URL 照 `OPENAI_BASE_URL` 的慣例**含** `/v1`，空的是官方；請求打 `{base}/chat/completions`。
- 認證 `Authorization: Bearer`；沒有 key（自架的 Ollama、vLLM）不送。
- 輸出上限：官方端點送 `max_completion_tokens`（推理模型不收 `max_tokens`），第三方送
  `max_tokens`（Ollama 只認得它，其餘都收）。
- **不送 `tool_choice`**（Ollama 不支援；同 Anthropic，不強制呼叫，研究結論 4），也不送
  `strict`、`parallel_tool_calls`、`reasoning_effort` 這類只有部分端點認得的欄位。
- 快取是端點自動做的，什麼都不送（研究結論 6）；工具依名稱排序，前綴才逐字相同。
- usage：帶 `stream_options.include_usage`，取最後一個 `usage` 不是 null 的 chunk（OpenRouter
  那一個的 `choices` 不是空的）。對映見 `_usage`；沒回的是 `None`。
- 工具呼叫的片段依 `index` 拼回；DeepSeek 的 `reasoning_content` 當 `OpaquePart` 帶回下一輪
  （思考模式帶工具時一定要送回去，研究底稿 §3.4）。
- 錯誤 body 照 `error.{message,type,code}` 讀；讀不懂的照狀態碼分，原文附在 `detail`
  （票 07b：「端點回了看不懂的錯誤」）。
- **不重試**（研究結論 8）。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
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

#: 請求 body、chunk 與錯誤 body。值是 Any：形狀看端點，不認得的欄位略過。
_Json = dict[str, Any]

OFFICIAL_BASE_URL = "https://api.openai.com/v1"

#: 錯誤原文抄到多長。
_RAW = 500
#: 要原樣帶回下一輪的 assistant 欄位（DeepSeek、vLLM 的推理內容）。
_REASONING = "reasoning_content"

_STOPS = {
    "stop": StopReason.END,
    "tool_calls": StopReason.TOOL_CALLS,
    # 舊的 functions API；有的相容端點還在回。
    "function_call": StopReason.TOOL_CALLS,
    "length": StopReason.MAX_TOKENS,
    "content_filter": StopReason.REFUSED,
}

#: 429 裡其實是額度或支出上限的那幾種（OpenAI「Error codes」：看 `error.code`，`error.type` 是
#: `insufficient_quota`）。重試也沒用。
_QUOTA_CODES = {"credit_balance_exhausted", "insufficient_quota"}
_QUOTA_SUFFIXES = ("_spend_limit_exceeded", "_usage_limit_exceeded")
#: 用 `error.code` / `error.type` 說的限流：串流中途的錯誤 chunk 沒有狀態碼，只有這些字。
_RATE_CODES = {"rate_limit_exceeded", "slow_down"}


class OpenAiProvider:
    def __init__(self, endpoint: Endpoint) -> None:
        base_url = endpoint.base_url.strip()
        self._official = not base_url
        self._base_url = (base_url or OFFICIAL_BASE_URL).rstrip("/")
        self._api_key = endpoint.api_key.strip()

    @property
    def host(self) -> str:
        return host_of(self._base_url)

    def _session(self) -> HttpSession:
        headers = {"authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        return HttpSession(self._base_url, headers=headers, timeout=LIST_TIMEOUT)

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        turn = _TurnAssembler()
        opened = False
        try:
            async with (
                self._session() as session,
                session.stream(
                    "POST",
                    "/chat/completions",
                    json=_body(request, official=self._official),
                    timeout=STREAM_TIMEOUT,
                ) as response,
            ):
                if response.status_code != 200 or not _is_event_stream(response):
                    raise await _http_error(response)
                opened = True
                logger.debug("openai stream opened", extra={"request_id": _request_id(response)})
                async for sse in EventSource(response).aiter_sse():
                    if sse.data.strip() == "[DONE]":
                        yield turn.end()
                        return
                    for event in turn.feed(sse.data):
                        yield event
        except AiProviderError as exc:
            if exc.usage == Usage():
                exc.usage = turn.usage()
            raise
        except ServiceError as exc:
            raise AiProviderError(
                # 開始回了才斷掉的是 provider 那一側出事；連都沒連上是連不上。
                AiFailure.PROVIDER_DOWN if opened else AiFailure.UNREACHABLE,
                str(exc),
                usage=turn.usage(),
            ) from exc
        if turn.finished:
            # 模型說完了（有 `finish_reason`），只是端點沒送 `[DONE]` 就關了連線。
            yield turn.end()
            return
        raise AiProviderError(
            AiFailure.PROVIDER_DOWN, "stream ended before the model finished", usage=turn.usage()
        )

    async def list_models(self) -> list[str] | None:
        async with self._session() as session:
            return await list_model_ids(session, "/models", read_error=_http_error)


def _is_event_stream(response: httpx.Response) -> bool:
    return "text/event-stream" in response.headers.get("content-type", "")


def _request_id(response: httpx.Response) -> str:
    return str(response.headers.get("x-request-id", ""))


async def _http_error(response: httpx.Response) -> AiProviderError:
    """不是一段事件串流的回應 → 分類過的錯誤。200 也可能走到這裡：body 只有 `error`
    （OpenRouter 非串流的樣子），或根本不是這個端點（登入頁、反向代理）。"""
    raw = await response.aread()
    try:
        body: object = json.loads(raw)
    except ValueError:
        body = None
    status = response.status_code
    error = body.get("error") if isinstance(body, Mapping) else None
    if status == 200 and error is None:
        text = raw.decode(errors="replace")[:_RAW]
        return AiProviderError(AiFailure.REJECTED, f"200 not an event stream: {text}".strip())
    failure, detail = _classify(status, error, raw)
    # 原文也寫進 log：認不得的錯誤（`REJECTED`）之後要靠它補分類。
    logger.info(
        "openai request failed",
        extra={"status": status, "request_id": _request_id(response), "detail": detail},
    )
    return AiProviderError(failure, detail, retry_after=retry_after(response))


def _classify(status: int | None, error: object, raw: bytes = b"") -> tuple[AiFailure, str]:
    """`error` 物件（`{message, type, code}`；Ollama 原生端點是字串）加狀態碼 → 分類與原文。

    `status` 是 `None` 時是串流中途的錯誤 chunk：照 `error.code`（OpenRouter 放的是 HTTP 狀態碼）
    分，說不出來的是 provider 那一側出事。
    """
    message, kind, code = "", "", None
    if isinstance(error, Mapping):
        message = str(error.get("message") or "")
        kind = str(error.get("type") or "")
        code = error.get("code")
    elif isinstance(error, str):
        message = error
    if not message:
        message = raw.decode(errors="replace")[:_RAW]
    named = str(code) if isinstance(code, str) else ""
    label = named or kind

    if named in _QUOTA_CODES or kind == "insufficient_quota" or named.endswith(_QUOTA_SUFFIXES):
        failure = AiFailure.QUOTA_EXHAUSTED
    elif named in _RATE_CODES or kind == "rate_limit_error":
        failure = AiFailure.RATE_LIMITED
    else:
        if status in (None, 200):
            status = _int(code)
        if status is None:
            failure = AiFailure.PROVIDER_DOWN
        elif status == 404 and not _says_model(named, message):
            # 不是在說模型的 404：多半是 base URL 多寫或少寫了 `/v1`，歸看不懂、附原文。
            failure = AiFailure.REJECTED
        else:
            failure = failure_of_status(status)
    prefix = f"{status} {label}" if status is not None else f"stream error {label}"
    return failure, f"{prefix.strip()}: {message}".strip()


def _says_model(code: str, message: str) -> bool:
    return code == "model_not_found" or "model" in message.lower()


# ---- 請求 ----------------------------------------------------------------------------------------


def _body(request: ChatRequest, *, official: bool) -> _Json:
    messages: list[_Json] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    for turn in request.turns:
        messages += _messages(turn)
    body: _Json = {
        "model": request.model,
        "messages": messages,
        "max_completion_tokens" if official else "max_tokens": request.max_output_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if request.tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in sorted(request.tools, key=lambda tool: tool.name)
        ]
    return body


def _messages(turn: UserTurn | ModelTurn) -> list[_Json]:
    if isinstance(turn, UserTurn):
        # 每個結果一則 `role: "tool"`，緊接在帶 `tool_calls` 的那一則之後；使用者的字排在後面。
        # 這個格式沒有 `is_error`：失敗的原因本來就寫在 content 裡（`adapters.ai` 的轉換規則）。
        out: list[_Json] = [
            {"role": "tool", "tool_call_id": part.call_id, "content": part.content}
            for part in turn.parts
            if isinstance(part, ToolResult)
        ]
        texts = [part.text for part in turn.parts if isinstance(part, TextPart)]
        if len(texts) == 1:
            out.append({"role": "user", "content": texts[0]})
        elif texts:
            out.append({"role": "user", "content": [{"type": "text", "text": t} for t in texts]})
        return out
    message: _Json = {"role": "assistant", "content": turn.text or None}
    for part in turn.parts:
        if isinstance(part, OpaquePart) and part.format is ApiFormat.OPENAI:
            message.update(part.raw)
    if turn.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments or "{}"},
            }
            for call in turn.tool_calls
        ]
    return [message]


# ---- 回應 ----------------------------------------------------------------------------------------


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _usage(raw: Mapping[str, Any] | None) -> Usage:
    """OpenAI 相容的 usage → `Usage`（研究結論 7 的表）。

    - 全部輸入是 `prompt_tokens`（DeepSeek 與 vLLM 明寫含快取讀取）。
    - 讀取：`prompt_tokens_details.cached_tokens`，沒有時 DeepSeek 的 `prompt_cache_hit_tokens`。
    - 寫入：`prompt_tokens_details.cache_write_tokens`（OpenAI、OpenRouter）或
      `created_cache_tokens`（vLLM）。
    - **讀取大於全部輸入時不信它**（研究最後一節第 7 條：`prompt_tokens` 含不含讀取沒有逐字說明）：
      讀取記成不知道、寫 log。
    """
    if raw is None:
        return Usage()
    details = raw.get("prompt_tokens_details")
    details = details if isinstance(details, Mapping) else {}
    total = _int(raw.get("prompt_tokens"))
    read = _int(details.get("cached_tokens"))
    if read is None:
        read = _int(raw.get("prompt_cache_hit_tokens"))
    write = _int(details.get("cache_write_tokens"))
    if write is None:
        write = _int(details.get("created_cache_tokens"))
    if read is not None and total is not None and read > total:
        logger.warning("cache read exceeds prompt tokens", extra={"read": read, "prompt": total})
        read = None
    return Usage(
        input_tokens=total,
        output_tokens=_int(raw.get("completion_tokens")),
        cache_write_tokens=write,
        cache_read_tokens=read,
    )


@dataclass(slots=True)
class _PendingCall:
    """串流中拼到一半的一個工具呼叫。"""

    id: str = ""
    name: str = ""
    arguments: str = ""


class _TurnAssembler:
    """把一輪的 chunk 拼回 `ModelTurn` 與 `Usage`。只看第一個 choice（Berth 不送 `n`）。"""

    def __init__(self) -> None:
        self._text = ""
        self._reasoning = ""
        #: 依 `index` 排的呼叫。
        self._calls: dict[int, _PendingCall] = {}
        self._finish = ""
        self._usage: Mapping[str, Any] | None = None

    @property
    def finished(self) -> bool:
        return bool(self._finish)

    def feed(self, data: str) -> list[StreamEvent]:
        try:
            payload = json.loads(data) if data.strip() else {}
        except ValueError as exc:
            raise AiProviderError(AiFailure.REJECTED, f"unreadable chunk: {data[:200]}") from exc
        if not isinstance(payload, Mapping):
            return []
        if payload.get("error") is not None:
            failure, detail = _classify(None, payload["error"])
            raise AiProviderError(failure, detail)
        if isinstance(payload.get("usage"), Mapping):
            self._usage = payload["usage"]
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            return []
        choice = choices[0]
        finish = choice.get("finish_reason")
        if finish == "error":
            raise AiProviderError(AiFailure.PROVIDER_DOWN, "stream finished with error")
        if isinstance(finish, str) and finish:
            self._finish = finish
        delta = choice.get("delta")
        return self._delta(delta) if isinstance(delta, Mapping) else []

    def _delta(self, delta: Mapping[str, Any]) -> list[StreamEvent]:
        events: list[StreamEvent] = []
        reasoning = delta.get(_REASONING)
        if isinstance(reasoning, str):
            self._reasoning += reasoning
        content = delta.get("content")
        if isinstance(content, str) and content:
            self._text += content
            events.append(TextDelta(content))
        pieces = delta.get("tool_calls")
        for piece in pieces if isinstance(pieces, list) else []:
            if isinstance(piece, Mapping):
                events += self._call_piece(piece)
        return events

    def _call_piece(self, piece: Mapping[str, Any]) -> list[StreamEvent]:
        index = _int(piece.get("index"))
        if index is None:
            # 不給 index 的端點：新的 id 是下一個呼叫，否則接在最後一個上。
            new = piece.get("id") and all(c.id != piece["id"] for c in self._calls.values())
            index = len(self._calls) if new or not self._calls else max(self._calls)
        call = self._calls.setdefault(index, _PendingCall())
        function = piece.get("function")
        function = function if isinstance(function, Mapping) else {}
        named = bool(call.name)
        if piece.get("id") and not call.id:
            call.id = str(piece["id"])
        if function.get("name") and not call.name:
            call.name = str(function["name"])
        if isinstance(function.get("arguments"), str):
            call.arguments += function["arguments"]
        if call.name and not named:
            return [ToolCallStarted(id=call.id or f"call_{index}", name=call.name)]
        return []

    def end(self) -> TurnEnded:
        parts: list[TextPart | ToolCall | OpaquePart] = []
        if self._reasoning:
            parts.append(OpaquePart(format=ApiFormat.OPENAI, raw={_REASONING: self._reasoning}))
        if self._text:
            parts.append(TextPart(self._text))
        for index in sorted(self._calls):
            call = self._calls[index]
            parts.append(
                ToolCall(id=call.id or f"call_{index}", name=call.name, arguments=call.arguments)
            )
        stop = _STOPS.get(self._finish, StopReason.OTHER)
        if any(isinstance(part, ToolCall) for part in parts) and stop in (
            StopReason.END,
            StopReason.OTHER,
        ):
            # 有的端點有呼叫也寫 `stop`（或不寫）：呼叫在就是要等結果。
            stop = StopReason.TOOL_CALLS
        return TurnEnded(
            stop=stop, stop_raw=self._finish, reply=ModelTurn(tuple(parts)), usage=self.usage()
        )

    def usage(self) -> Usage:
        return _usage(self._usage)
