"""AI 設定與設定頁的測試（M5 票 07、plan §11.6〈provider〉、brief §20.24）。

**「AI 設定好了」**（`is_ready`）：有端點、有模型。端點是「填了 base URL」或「官方端點而且有 key」
——自架的 Ollama / vLLM 不需要 key（研究最後一節第 6 條），官方沒有 key 什麼都做不了。模型空的
時候官方端點用預設的那一個，第三方沒有預設。**沒設定好時整個系統與 M4 相同**：沒有東西會叫模型。

**測試是三次請求**（研究結論 4）：不帶工具的最小請求 → 帶一個假工具與隨機 nonce → 把工具的結果
送回去要拿到文字。第一次沒過就說原因、不往下；後兩次判出「支不支援工具呼叫」存進
`settings.ai.tool_test`，限流、provider 掛掉、連不上是「這次沒測成」，不存。請求的組法與對話核心
相同：同一個 adapter，不強制呼叫（不送 `tool_choice`：現役模型對 `any` / `tool` 回 400）。
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import (
    AiProviderError,
    ChatProvider,
    ChatRequest,
    Endpoint,
    ModelTurn,
    TextPart,
    ToolCall,
    ToolResult,
    ToolSpec,
    TurnEnded,
    Usage,
    UserTurn,
)
from berth.adapters.ai.anthropic import DEFAULT_MODEL
from berth.domain import AiCallOrigin, AiFailure, AiProbeStep, AiRefusal, ApiFormat, ToolGap
from berth.models import AiSettings, AiToolTest
from berth.models.types import utcnow
from berth.services.ai_calls import call_model
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.settings import read_settings, update_settings

logger = logging.getLogger(__name__)

#: 探針的假工具。無害：Berth 收到呼叫只是把 nonce 照抄回去。
PROBE_TOOL = ToolSpec(
    name="berth_echo",
    description="Echo a nonce back to Berth. Used only to check that tool calling works.",
    input_schema={
        "type": "object",
        "properties": {"nonce": {"type": "string", "description": "The nonce to echo back."}},
        "required": ["nonce"],
    },
)
_HELLO = "This is a connection test from Berth. Reply with the single word: ok"
_CALL = (
    'This is a tool-calling test from Berth. Call the berth_echo tool with nonce "{nonce}". '
    "Do not answer in text."
)
#: 會先想一下的模型要留一點空間；三次加起來仍是幾百個 tokens。
_MAX_OUTPUT = 256
#: 技術細節裡抄模型回的文字到多長。
_SNIPPET = 300


class AiRefusedError(Exception):
    def __init__(self, reason: AiRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class AiView:
    format: ApiFormat
    base_url: str
    #: 存過 key 沒有。key 本身永遠不回來。
    api_key_present: bool
    #: 存的模型；空的是沒填。
    model: str
    #: 模型空著時用的那一個：只有官方端點有。
    default_model: str | None
    ready: bool
    tool_test: AiToolTest | None


@dataclass(frozen=True, slots=True)
class ProbeCall:
    step: AiProbeStep
    usage: Usage


@dataclass(frozen=True, slots=True)
class AiTestView:
    """一次測試的結果。`failure` 是第一次（不帶工具）沒成的原因；成了才有後面兩格。"""

    failure: AiFailure | None
    #: 端點的原文。
    detail: str
    retry_after: float | None
    #: 第一次模型回的文字。
    reply: str
    calls: tuple[ProbeCall, ...]
    #: 支不支援工具呼叫的結論（已存進 `settings.ai`）；`None` 是沒測到結論。
    tools: AiToolTest | None
    #: 沒測到結論的原因（限流、掛掉、連不上）。
    tools_failure: AiFailure | None
    tools_detail: str


@dataclass(frozen=True, slots=True)
class ModelList:
    #: `None` 是端點列不出來，設定頁退回手填。
    models: tuple[str, ...] | None
    failure: AiFailure | None = None
    detail: str = ""


def default_model(settings: AiSettings) -> str | None:
    """預設模型只在官方 Anthropic 端點時給（研究結論 5）：第三方會把 `claude-*` 映射成別的模型。"""
    return DEFAULT_MODEL if not settings.base_url else None


def effective_model(settings: AiSettings) -> str:
    return settings.model or default_model(settings) or ""


def has_endpoint(settings: AiSettings) -> bool:
    """有一台打得了的端點：填了 base URL，或官方端點而且有 key。"""
    return bool(settings.base_url or settings.api_key)


def is_ready(settings: AiSettings) -> bool:
    """AI 設定好了：有端點、有模型。票 08 的側面板與之後每一個叫模型的地方都看它。"""
    return has_endpoint(settings) and bool(effective_model(settings))


def _view(settings: AiSettings) -> AiView:
    return AiView(
        format=settings.format,
        base_url=settings.base_url,
        api_key_present=bool(settings.api_key),
        model=settings.model,
        default_model=default_model(settings),
        ready=is_ready(settings),
        tool_test=settings.tool_test,
    )


def _endpoint(settings: AiSettings) -> Endpoint:
    return Endpoint(format=settings.format, base_url=settings.base_url, api_key=settings.api_key)


def _tested_for(settings: AiSettings) -> tuple[ApiFormat, str, str]:
    """測試結果說的是哪一個組合：格式、base URL、模型任一改了就要重測（票 07 第 6 條）。"""
    return settings.format, settings.base_url, effective_model(settings)


@command(Effect.READ)
async def read_ai(session: AsyncSession) -> AiView:
    return _view(await read_settings(session, AiSettings))


def _clean_base_url(raw: str) -> str:
    base_url = raw.strip().rstrip("/")
    if not base_url:
        return ""
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise AiRefusedError(AiRefusal.BASE_URL_INVALID, base_url)
    return base_url


@command(Effect.REVERSIBLE)
async def set_ai(
    session: AsyncSession,
    *,
    format: ApiFormat,
    base_url: str,
    model: str,
    api_key: str | None,
) -> AiView:
    """存 AI 設定。`api_key` 是 `None` 時留著存著的那一把，空字串是清掉。不連端點：連得上與否
    是「測試」的事。格式、base URL 或模型變了，工具呼叫的測試結果跟著清掉。"""
    cleaned = _clean_base_url(base_url)

    def change(settings: AiSettings) -> None:
        before = _tested_for(settings)
        settings.format = format
        settings.base_url = cleaned
        settings.model = model.strip()
        if api_key is not None:
            settings.api_key = api_key.strip()
        if _tested_for(settings) != before:
            settings.tool_test = None

    saved = await update_settings(session, AiSettings, change)
    logger.info("ai settings saved", extra={"format": saved.format, "ready": is_ready(saved)})
    return _view(saved)


@command(Effect.READ)
async def list_models(session: AsyncSession, factory: ServiceClientFactory) -> ModelList:
    """端點列得出的模型。列不出來是 `models=None`（設定頁退回手填）；有下一步的失敗帶著原因。"""
    settings = await read_settings(session, AiSettings)
    if not has_endpoint(settings):
        raise AiRefusedError(AiRefusal.NOT_READY)
    try:
        models = await factory.ai(_endpoint(settings)).list_models()
    except AiProviderError as exc:
        return ModelList(models=None, failure=exc.failure, detail=exc.detail)
    return ModelList(models=None if models is None else tuple(models))


# 三次請求花掉的 tokens 收不回來。
@command(Effect.IRREVERSIBLE)
async def run_ai_test(
    session: AsyncSession, factory: ServiceClientFactory, *, user_id: int
) -> AiTestView:
    """設定頁的「測試」：照存著的設定打三次請求（模組說明）。每一次都記一列 `ai_calls`。"""
    settings = await read_settings(session, AiSettings)
    if not is_ready(settings):
        raise AiRefusedError(AiRefusal.NOT_READY)
    probe = _Probe(session, factory.ai(_endpoint(settings)), settings, user_id)

    try:
        hello = await probe.send(AiProbeStep.HELLO, (UserTurn((TextPart(_HELLO),)),), tools=False)
    except AiProviderError as exc:
        return probe.view(failure=exc, reply="")

    outcome = await probe.check_tools()
    if isinstance(outcome, AiToolTest):
        tested = _tested_for(settings)

        def store(current: AiSettings) -> None:
            # 測試那幾秒裡設定被改了：這個結論說的是舊的那一組，不存。
            if _tested_for(current) == tested:
                current.tool_test = outcome

        await update_settings(session, AiSettings, store)
        return probe.view(reply=hello.reply.text, tools=outcome)
    return probe.view(reply=hello.reply.text, tools_failure=outcome)


class _Probe:
    def __init__(
        self, session: AsyncSession, provider: ChatProvider, settings: AiSettings, user_id: int
    ) -> None:
        self._session = session
        self._provider = provider
        self._format = settings.format
        self._model = effective_model(settings)
        self._user_id = user_id
        self.calls: list[ProbeCall] = []

    async def send(
        self, step: AiProbeStep, turns: tuple[UserTurn | ModelTurn, ...], *, tools: bool
    ) -> TurnEnded:
        request = ChatRequest(
            model=self._model,
            system="",
            tools=(PROBE_TOOL,) if tools else (),
            turns=turns,
            max_output_tokens=_MAX_OUTPUT,
        )
        try:
            ended = await call_model(
                self._session,
                self._provider,
                request,
                format=self._format,
                origin=AiCallOrigin.TEST,
                user_id=self._user_id,
            )
        except AiProviderError as exc:
            self.calls.append(ProbeCall(step=step, usage=exc.usage))
            raise
        self.calls.append(ProbeCall(step=step, usage=ended.usage))
        return ended

    async def check_tools(self) -> AiToolTest | AiProviderError:
        """第二、三次。回結論，或沒測成的那一個錯誤。"""
        nonce = secrets.token_hex(4)
        ask = UserTurn((TextPart(_CALL.format(nonce=nonce)),))
        try:
            called = await self.send(AiProbeStep.TOOL_CALL, (ask,), tools=True)
        except AiProviderError as exc:
            if exc.failure is AiFailure.REJECTED:
                return _unsupported(ToolGap.TOOLS_REJECTED, exc.detail)
            return exc
        verdict = _judge_call(called.reply, nonce)
        if isinstance(verdict, AiToolTest):
            return verdict

        # 每一個呼叫都要有結果（模型可以平行呼叫兩次）。
        echoed = json.dumps({"nonce": nonce})
        result = UserTurn(tuple(ToolResult(call.id, echoed) for call in verdict))
        try:
            answered = await self.send(
                AiProbeStep.TOOL_RESULT, (ask, called.reply, result), tools=True
            )
        except AiProviderError as exc:
            if exc.failure is AiFailure.REJECTED:
                return _unsupported(ToolGap.RESULT_REJECTED, exc.detail)
            return exc
        if not answered.reply.text.strip():
            return _unsupported(ToolGap.NO_REPLY, _describe(answered))
        return AiToolTest(supported=True, tested_at=utcnow())

    def view(
        self,
        *,
        reply: str,
        failure: AiProviderError | None = None,
        tools: AiToolTest | None = None,
        tools_failure: AiProviderError | None = None,
    ) -> AiTestView:
        return AiTestView(
            failure=failure.failure if failure else None,
            detail=failure.detail if failure else "",
            retry_after=failure.retry_after if failure else None,
            reply=reply,
            calls=tuple(self.calls),
            tools=tools,
            tools_failure=tools_failure.failure if tools_failure else None,
            tools_detail=tools_failure.detail if tools_failure else "",
        )


def _unsupported(gap: ToolGap, detail: str) -> AiToolTest:
    return AiToolTest(supported=False, gap=gap, detail=detail, tested_at=utcnow())


def _judge_call(reply: ModelTurn, nonce: str) -> tuple[ToolCall, ...] | AiToolTest:
    """第二次的回覆：每一個呼叫都是名字對、nonce 對的，就往下走第三次；其餘是不支援的哪一種樣子。"""
    calls = reply.tool_calls
    if not calls:
        text = reply.text
        gap = (
            ToolGap.WRITTEN_AS_TEXT
            if nonce in text or PROBE_TOOL.name in text
            else ToolGap.TOOLS_IGNORED
        )
        return _unsupported(gap, text[:_SNIPPET])
    for call in calls:
        if call.name != PROBE_TOOL.name or _nonce_of(call) != nonce:
            return _unsupported(ToolGap.WRONG_CALL, f"{call.name} {call.arguments}"[:_SNIPPET])
    return calls


def _nonce_of(call: ToolCall) -> object:
    try:
        arguments = json.loads(call.arguments or "{}")
    except ValueError:
        return None
    return arguments.get("nonce") if isinstance(arguments, dict) else None


def _describe(ended: TurnEnded) -> str:
    return f"stop={ended.stop_raw} text={ended.reply.text[:_SNIPPET]!r}"
