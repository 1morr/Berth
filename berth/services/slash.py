"""斜線指令（M5 票 18、plan §11.6〈分段〉第 7 段、研究 C2）。

一份登錄表給所有表面共用（Hermes 的 `COMMAND_REGISTRY`）：側面板現在用，M7 的 Discord 照
`SLASH_COMMANDS` 列指令、叫同一支 `run_slash`。

- **只認人類訊息開頭的 `/`**：整則訊息就是 `/<名字>`，名字照 `domain.SlashCommand`；不是的
  （多帶了字、打錯）是 `unknown_command`，不會退回去當成問模型的話。反過來，送進對話的 `/`
  開頭訊息由 `agent.open_turn` 擋下（`slash_command`）：指令永遠不經過模型。
- **不經過模型**，只有 `/compact` 的摘要要叫一次（`services.compaction`，記一筆 `ai_runs`）。
- **門禁同側面板**：AI 開著才能用（面板關著時本來就沒有輸入欄），對話是別人的就當作沒有。
  `/compact` 另外要 provider 沒有暫停、這個人沒有正在跑的一輪（它佔同一個位子）。

結果是結構（`SlashResult`），字由各個表面照自己的語言組（側面板走 i18n）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.domain import (
    WAITING_PROPOSALS,
    Actor,
    AgentRefusal,
    AiProvider,
    AiRunKind,
    ProposalStatus,
    SlashCommand,
)
from berth.models import AiConversation, AiRun, AiSettings, AiToolCall
from berth.models.types import utcnow
from berth.services.agent import (
    CONVERSATION_ID,
    SLASH,
    AgentRefusedError,
    AgentRuntime,
    current_endpoint,
    load_history,
)
from berth.services.agent_books import plus
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, Flag, command
from berth.services.compaction import Summarizer, compact, last_context_tokens
from berth.services.proposals import list_proposals
from berth.services.settings import read_settings
from berth.services.skills import SkillEntry, list_skills
from berth.services.usage import tavily_searched_sql


@dataclass(frozen=True, slots=True)
class NewConversation:
    """這個表面換一段新對話（側面板換 chat id；伺服器在第一則訊息時建）。"""


@dataclass(frozen=True, slots=True)
class Compacted:
    #: 壓縮前有幾則訊息。
    before: int
    #: 壓縮後有幾則；`None` 是沒有壓（只有一輪，或摘要失敗）。
    after: int | None
    #: 摘要失敗的原文（key 已遮掉）；成功與沒什麼好壓是空字串。
    error: str = ""


@dataclass(frozen=True, slots=True)
class Usage:
    """這段對話到目前為止（含壓縮的摘要）。`None` 是有一次不知道，合計就是不知道。"""

    turns: int
    compactions: int
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    #: 伺服器端網搜的次數（`ai_runs.web_searches`）。
    web_searches: int
    #: Tavily 真的搜了的次數：`ai_tool_calls` 裡成功與照樣做了的（被擋下、失敗的不算）。
    tavily_searches: int
    cost_usd: float | None


@dataclass(frozen=True, slots=True)
class Status:
    provider: AiProvider
    model: str
    #: 存著的歷史有幾則。
    messages: int
    #: 上一次回應的 input + output（下一次至少這麼大）；還沒有回應是 `None`。
    context_tokens: int | None
    #: 模型的 context window：pydantic-ai 的模型資料，查不到是 `Limits.context_window`。
    context_window: int
    #: 到了這個比例，下一輪開頭自動壓縮。
    compact_at: float
    #: provider 斷路器暫停到什麼時候；`None` 是沒有暫停。
    paused_until: datetime | None


@dataclass(frozen=True, slots=True)
class PendingCard:
    id: int
    command: str
    status: ProposalStatus
    #: 卡片有幾列（總覽卡是好幾列）。
    rows: int
    expires_at: datetime
    #: 在這段對話裡。
    here: bool


@dataclass(frozen=True, slots=True)
class Pending:
    """這個人還沒決定的卡片，每一段對話的，舊的在前。管理員也只看自己的：「我在等什麼」。"""

    cards: tuple[PendingCard, ...]


@dataclass(frozen=True, slots=True)
class Skills:
    skills: tuple[SkillEntry, ...]


SlashResult = NewConversation | Compacted | Usage | Status | Pending | Skills


@dataclass(frozen=True, slots=True)
class _Call:
    runtime: AgentRuntime
    sessions: async_sessionmaker[AsyncSession]
    factory: ServiceClientFactory
    actor: Actor
    conversation_id: str
    settings: AiSettings
    #: 開始時讀到的歷史（`/compact` 佔到位子之後自己重讀）。
    history: list[ModelMessage]

    @property
    def user_id(self) -> int:
        assert self.actor.user_id is not None
        return self.actor.user_id


def parse(text: str) -> SlashCommand:
    """整則訊息是 `/<名字>` 才算；其餘是 `unknown_command`（detail 是打的第一個詞）。"""
    stripped = text.strip()
    word = stripped.split()[0] if stripped else ""
    if word == stripped and word.startswith(SLASH):
        try:
            return SlashCommand(word.removeprefix(SLASH))
        except ValueError:
            pass
    raise AgentRefusedError(AgentRefusal.UNKNOWN_COMMAND, word)


# 斜線指令的入口：`/compact` 換掉存著的歷史、花掉摘要的 token，回不來。入口不是工具。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL})
async def run_slash(
    *,
    runtime: AgentRuntime,
    sessions: async_sessionmaker[AsyncSession],
    factory: ServiceClientFactory,
    actor: Actor,
    conversation_id: str,
    text: str,
) -> SlashResult:
    """拒絕：`unknown_command`、`conversation_missing`、`ai_disabled`；`/compact` 另有
    `ai_paused`、`busy`。還沒有的對話（新的面板）照樣能問：用量是 0、沒什麼好壓。"""
    assert actor.user_id is not None
    name = parse(text)
    if not CONVERSATION_ID.fullmatch(conversation_id):
        raise AgentRefusedError(AgentRefusal.CONVERSATION_MISSING, conversation_id)
    async with sessions() as session:
        settings = await read_settings(session, AiSettings)
        if not settings.enabled:
            raise AgentRefusedError(AgentRefusal.AI_DISABLED)
        history = await _history(session, conversation_id, actor.user_id)
    call = _Call(runtime, sessions, factory, actor, conversation_id, settings, history)
    return await SLASH_COMMANDS[name](call)


async def _history(session: AsyncSession, conversation_id: str, user_id: int) -> list[ModelMessage]:
    conversation = await session.get(AiConversation, conversation_id)
    if conversation is None:
        return []
    if conversation.user_id != user_id:
        raise AgentRefusedError(AgentRefusal.CONVERSATION_MISSING, conversation_id)
    return load_history(conversation.history_json)


async def _new(_call: _Call) -> NewConversation:
    return NewConversation()


async def _compact(call: _Call) -> Compacted:
    """只留最後一輪（plan §11.6）。待確認的呼叫在那一輪裡，卡片本身在 Proposal 表。"""
    endpoint = current_endpoint(call.settings)
    if (pause := call.runtime.breaker.paused(endpoint)) is not None:
        raise AgentRefusedError(AgentRefusal.AI_PAUSED, pause.until.isoformat())
    # 佔住這個人的那一輪：壓縮時開不了新的一輪，壓完存回去的才不會蓋掉它的回覆。
    call.runtime.claim(call.user_id)
    try:
        async with call.sessions() as session:
            history = await _history(session, call.conversation_id, call.user_id)
        summarizer = Summarizer(
            sessions=call.sessions,
            model=call.factory.ai(endpoint),
            endpoint=endpoint,
            breaker=call.runtime.breaker,
            conversation_id=call.conversation_id,
            user_id=call.user_id,
        )
        done = await compact(summarizer, history, keep=1)
        if done is None or done.error:
            return Compacted(before=len(history), after=None, error=done.error if done else "")
        async with call.sessions() as session:
            conversation = await session.get_one(AiConversation, call.conversation_id)
            conversation.history_json = ModelMessagesTypeAdapter.dump_json(done.messages).decode()
            conversation.updated_at = utcnow()
            await session.commit()
        return Compacted(before=done.before, after=len(done.messages))
    finally:
        call.runtime.release(call.user_id)


async def _usage(call: _Call) -> Usage:
    async with call.sessions() as session:
        runs = (
            await session.scalars(
                select(AiRun).where(AiRun.conversation_id == call.conversation_id)
            )
        ).all()
        tavily = await session.scalar(
            select(func.count())
            .select_from(AiToolCall)
            .join(AiRun, AiToolCall.run_id == AiRun.id)
            .where(
                AiRun.conversation_id == call.conversation_id,
                # 與用量頁、步驟頁同一條規則（`services.usage`）。
                tavily_searched_sql(),
            )
        )
    return Usage(
        turns=sum(run.kind is AiRunKind.CHAT for run in runs),
        compactions=sum(run.kind is AiRunKind.COMPACTION for run in runs),
        requests=sum(run.requests for run in runs),
        tool_calls=sum(run.tool_calls for run in runs),
        input_tokens=sum(run.input_tokens for run in runs),
        output_tokens=sum(run.output_tokens for run in runs),
        cache_read_tokens=_total((run.cache_read_tokens for run in runs), 0),
        web_searches=sum(run.web_searches for run in runs),
        tavily_searches=tavily or 0,
        cost_usd=_total((run.cost_usd for run in runs), 0.0),
    )


def _total[N: (int, float)](values: Iterable[N | None], zero: N) -> N | None:
    """有一個不知道，合計就是不知道（`agent_books.plus`，同一輪的合計）。"""
    total: N | None = zero
    for value in values:
        total = plus(total, value)
    return total


async def _status(call: _Call) -> Status:
    endpoint = current_endpoint(call.settings)
    window = call.factory.ai(endpoint).context_window or call.runtime.limits.context_window
    pause = call.runtime.breaker.paused(endpoint)
    return Status(
        provider=call.settings.provider,
        model=endpoint.model,
        messages=len(call.history),
        context_tokens=last_context_tokens(call.history),
        context_window=window,
        compact_at=call.runtime.limits.compact_at,
        paused_until=pause.until if pause is not None else None,
    )


async def _pending(call: _Call) -> Pending:
    async with call.sessions() as session:
        views = await list_proposals(session, user_id=call.user_id, role=call.actor.role)
    return Pending(
        cards=tuple(
            PendingCard(
                id=view.id,
                command=view.command,
                status=view.status,
                rows=len(view.arguments),
                expires_at=view.expires_at,
                here=view.conversation_id == call.conversation_id,
            )
            for view in views
            if view.user_id == call.user_id and view.status in WAITING_PROPOSALS
        )
    )


async def _skills(call: _Call) -> Skills:
    return Skills(skills=tuple(await list_skills(role=call.actor.role)))


#: 登錄表：每一個 `SlashCommand` 一支（`tests/unit/test_slash.py` 守全不全）。不叫 `COMMANDS`：
#: 那是 Command Registry（`registry.commands()`）。
SLASH_COMMANDS: dict[SlashCommand, Callable[[_Call], Awaitable[SlashResult]]] = {
    SlashCommand.NEW: _new,
    SlashCommand.COMPACT: _compact,
    SlashCommand.USAGE: _usage,
    SlashCommand.STATUS: _status,
    SlashCommand.PENDING: _pending,
    SlashCommand.SKILLS: _skills,
}
