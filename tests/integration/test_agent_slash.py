"""側面板的斜線指令（M5 票 18、plan §11.6〈分段〉第 7 段）。

端點是 `POST /agent/conversations/{id}/commands`。

只認人類訊息開頭的 `/`，不經過模型——`/compact` 的摘要除外。登錄表在 `services.slash`，M7 的
Discord 共用同一份。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    CompactionPart,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.ai.fake import FakeAi
from berth.api.deps import get_client_factory
from berth.api.gate import SESSION_COOKIE
from berth.config import Config
from berth.domain import Actor, AiToolOutcome, JobState, JobTrigger, Role
from berth.main import create_app
from berth.models import AiConversation, AiRun, AiToolCall, Job, User
from berth.services import proposals
from berth.services.events import EventHub
from berth.services.executor import Executor
from berth.services.hints import JobHints
from berth.services.skills import list_skills
from tests.integration.arrange import sign_in_crew, sign_in_owner
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import (
    BROWSER,
    Script,
    call,
    chat,
    recorded,
    say,
    stored_history,
    texts,
    turn_ai_on,
)


@pytest.fixture
def script() -> Script:
    return Script()


@pytest.fixture
def factory(script: Script) -> FakeClientFactory:
    return FakeClientFactory(ai=FakeAi(script=script))


@pytest.fixture
def client(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        turn_ai_on(running)
        yield running


def slash(client: TestClient, text: str, conversation: str = "c1") -> Any:
    return client.post(
        f"/api/agent/conversations/{conversation}/commands", json={"text": text}, headers=BROWSER
    )


def ok(client: TestClient, text: str, conversation: str = "c1") -> dict[str, Any]:
    response = slash(client, text, conversation)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def in_portal[T](client: TestClient, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            return await work(session)

    assert client.portal is not None
    found: T = client.portal.call(run)
    return found


def three_turns(client: TestClient, script: Script) -> None:
    script.steps = [say("one"), say("two"), say("three")]
    for text in ("first", "second", "third"):
        assert chat(client, text).status_code == 200


def summaries(messages: list[ModelMessage]) -> list[str | None]:
    return [
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, CompactionPart)
    ]


class TestOnlyALeadingSlash:
    def test_an_unknown_command_is_refused_without_asking_the_model(
        self, client: TestClient, script: Script
    ) -> None:
        response = slash(client, "/frobnicate")

        assert response.status_code == 422
        assert response.json()["detail"] == {"reason": "unknown_command", "detail": "/frobnicate"}
        assert script.seen == []

    def test_words_after_a_command_make_it_unknown(self, client: TestClient) -> None:
        response = slash(client, "/compact keep the ids")

        assert response.json()["detail"]["reason"] == "unknown_command"

    def test_a_message_without_the_slash_is_not_a_command(self, client: TestClient) -> None:
        assert slash(client, "usage").json()["detail"]["reason"] == "unknown_command"

    def test_the_chat_never_hands_a_command_to_the_model(
        self, client: TestClient, script: Script
    ) -> None:
        response = chat(client, "/usage")

        assert response.status_code == 422
        assert response.json()["detail"] == {"reason": "slash_command", "detail": "/usage"}
        assert script.seen == []
        assert recorded(client) == []

    def test_someone_elses_conversation_does_not_exist(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [say("one")]
        chat(client, "first")
        sign_in_crew(client)

        response = slash(client, "/usage")

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "conversation_missing"

    def test_commands_need_ai_turned_on(self, client: TestClient) -> None:
        body = {"enabled": False, "provider": "anthropic", "base_url": "", "model": "x"}
        assert client.put("/api/settings/ai", json=body, headers=BROWSER).status_code == 200

        assert slash(client, "/status").json()["detail"]["reason"] == "ai_disabled"


class TestNew:
    def test_new_tells_the_panel_to_start_over(self, client: TestClient) -> None:
        assert ok(client, "/new") == {"command": "new"}


class TestUsage:
    def test_a_fresh_conversation_has_used_nothing(self, client: TestClient) -> None:
        assert ok(client, "/usage", conversation="fresh") == {
            "command": "usage",
            "turns": 0,
            "compactions": 0,
            "requests": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "web_searches": 0,
            "tavily_searches": 0,
            "cost_usd": 0.0,
        }

    def test_the_totals_of_this_conversation(self, client: TestClient, script: Script) -> None:
        script.steps = [call("jobs_list_jobs", page=1), say("Nothing."), say("Hi.")]
        chat(client, "What is downloading?")
        chat(client, "Hello?")
        chat(client, "Elsewhere", conversation="c2")
        runs = [r.run for r in recorded(client) if r.run.conversation_id == "c1"]

        # Tavily 的次數是成功（與照樣做了的）那幾次；被擋下的不算（票 17 的交接）。
        async def searched(session: AsyncSession) -> None:
            for outcome in (AiToolOutcome.OK, AiToolOutcome.WARNED, AiToolOutcome.BLOCKED):
                session.add(
                    AiToolCall(
                        run_id=runs[0].id, step=1, command="web.tavily_search", outcome=outcome
                    )
                )
            await session.commit()

        in_portal(client, searched)

        usage = ok(client, "/usage")

        assert usage["turns"] == 2
        assert usage["compactions"] == 0
        assert usage["requests"] == 3
        assert usage["tool_calls"] == 1
        assert usage["input_tokens"] == sum(r.input_tokens for r in runs)
        assert usage["output_tokens"] == sum(r.output_tokens for r in runs)
        assert usage["tavily_searches"] == 2
        assert usage["cost_usd"] == pytest.approx(sum(r.cost_usd or 0 for r in runs))

    def test_a_cost_nobody_knows_makes_the_total_unknown(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [say("Hi.")]
        chat(client, "Hello?")

        async def unknown(session: AsyncSession) -> None:
            run = (await session.scalars(select(AiRun))).one()
            run.cost_usd = None
            run.cache_read_tokens = None
            await session.commit()

        in_portal(client, unknown)

        usage = ok(client, "/usage")
        assert usage["cost_usd"] is None
        assert usage["cache_read_tokens"] is None


class TestStatus:
    def test_the_model_and_how_full_the_context_is(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [say("Hi.")]
        chat(client, "Hello?")
        [run] = [r.run for r in recorded(client)]

        status = ok(client, "/status")

        assert status["command"] == "status"
        assert status["provider"] == "anthropic"
        assert status["model"] == "claude-sonnet-5-5"
        assert status["messages"] == 2
        assert status["context_tokens"] == run.input_tokens + run.output_tokens
        assert status["context_window"] > 0
        assert status["compact_at"] == 0.6
        assert status["paused_until"] is None

    def test_before_the_first_reply_nothing_is_measured(self, client: TestClient) -> None:
        status = ok(client, "/status", conversation="fresh")

        assert status["messages"] == 0
        assert status["context_tokens"] is None


def a_card(
    client: TestClient, conversation: str | None, job_hash: str, *, who: str = "skipper"
) -> int:
    """AI 替 `who` 在 `conversation` 裡提出一張「重試」的卡片（入庫失敗的 Job）。"""

    async def arrange(session: AsyncSession) -> int:
        user = (await session.scalars(select(User).where(User.name == who))).one()
        session.add(
            Job(
                hash=job_hash,
                name=job_hash,
                trigger=JobTrigger.MANUAL,
                user_id=user.id,
                state=JobState.IMPORT_FAILED,
            )
        )
        await session.commit()
        card = await proposals.propose(
            session,
            EventHub(),
            "jobs.retry_job",
            [{"job_hash": job_hash}],
            actor=Actor.ai(user.id, Role(user.role)),
            conversation_id=conversation,
        )
        return card.id

    return in_portal(client, arrange)


class TestPending:
    def test_the_cards_still_waiting_for_me(self, client: TestClient) -> None:
        here = a_card(client, "c1", "a" * 40)
        elsewhere = a_card(client, "c-old", "b" * 40)
        decided = a_card(client, "c1", "c" * 40)
        assert (
            client.post(
                f"/api/proposals/{decided}/decide", json={"approve": False}, headers=BROWSER
            ).status_code
            == 200
        )

        pending = ok(client, "/pending")

        assert pending["command"] == "pending"
        assert [(c["id"], c["here"], c["status"]) for c in pending["cards"]] == [
            (here, True, "pending"),
            (elsewhere, False, "pending"),
        ]
        [first, _] = pending["cards"]
        assert first["command"] == "jobs.retry_job"
        assert first["rows"] == 1
        assert first["expires_at"]

    def test_an_admin_sees_only_their_own(self, client: TestClient) -> None:
        owner = client.cookies.get(SESSION_COOKIE)
        sign_in_crew(client)
        a_card(client, "c-crew", "d" * 40, who="deckhand")
        client.cookies.set(SESSION_COOKIE, owner or "")

        assert ok(client, "/pending")["cards"] == []


class TestSkills:
    def test_the_skills_this_person_can_load(self, client: TestClient) -> None:
        listed = ok(client, "/skills")

        expected = [entry.model_dump() for entry in in_portal(client, _skills_for_admin)]
        assert listed == {"command": "skills", "skills": expected}
        assert "why-not-imported" in [s["name"] for s in listed["skills"]]


async def _skills_for_admin(_session: AsyncSession) -> list[Any]:
    return await list_skills(role=Role.ADMIN)


class TestCompact:
    def test_only_the_last_turn_is_kept(self, client: TestClient, script: Script) -> None:
        three_turns(client, script)
        before = len(stored_history(client))
        script.steps = [*script.steps, say("SUMMARY: said hello three times")]

        compacted = ok(client, "/compact")

        history = stored_history(client)
        assert compacted == {
            "command": "compact",
            "before": before,
            "after": len(history),
            "error": "",
        }
        assert summaries(history) == ["SUMMARY: said hello three times"]
        assert texts(history) == ["third"]
        # 摘要那一次看到的是前兩個回合。
        summarized = texts(script.seen[-1])[0]
        assert "User: first" in summarized and "User: second" in summarized
        assert "User: third" not in summarized
        assert [r.run.kind for r in recorded(client)][-1] == "compaction"
        # 重新載入的面板看得到摘要在哪。
        messages = client.get("/api/agent/conversations/c1").json()["messages"]
        assert any(p["type"] == "data-compaction" for m in messages for p in m["parts"])
        # 之後照常說話，模型看到摘要 + 最後一個回合 + 新的話。
        script.steps = [*script.steps, say("four")]
        chat(client, "fourth")
        assert texts(script.seen[-1]) == ["third", "fourth"]
        assert summaries(script.seen[-1]) == ["SUMMARY: said hello three times"]

    def test_one_turn_has_nothing_to_compact(self, client: TestClient, script: Script) -> None:
        script.steps = [say("one")]
        chat(client, "first")

        assert ok(client, "/compact") == {
            "command": "compact",
            "before": 2,
            "after": None,
            "error": "",
        }
        assert [r.run.kind for r in recorded(client)] == ["chat"]

    def test_a_failed_summary_leaves_the_history_alone(
        self, client: TestClient, script: Script
    ) -> None:
        three_turns(client, script)
        before = stored_history(client)

        def overloaded(_m: list[ModelMessage], _i: AgentInfo) -> ModelResponse:
            raise ModelHTTPError(529, "claude-sonnet-5-5", {"error": {"message": "overloaded"}})

        script.steps = [*script.steps, overloaded]

        compacted = ok(client, "/compact")

        assert compacted["after"] is None
        assert "529" in compacted["error"]
        assert texts(stored_history(client)) == texts(before)


class TestACardSurvivesCompaction:
    """有待確認的卡片時 `/compact`，之後照常確認並執行（驗收第 2 條）。

    卡片的事實來源是 Proposal 表；歷史尾巴那個還沒有結果的呼叫，是票 13 恢復時找的那一個。票 13 落地
    之前，「確認之後由對話恢復執行」這一步以 `proposals.execute` 代替（票 08：在對話裡的卡片核准只記
    決定，由恢復執行）。
    """

    def test_compact_then_confirm_and_run(self, client: TestClient, script: Script) -> None:
        three_turns(client, script)
        card = a_card(client, "c1", "e" * 40)
        waiting = ModelResponse(
            parts=[ToolCallPart("jobs_retry_job", {"job_hash": "e" * 40}, tool_call_id="card")]
        )

        async def asked(session: AsyncSession) -> None:
            row = await session.get_one(AiConversation, "c1")
            history = [
                *ModelMessagesTypeAdapter.validate_json(row.history_json),
                ModelRequest(parts=[UserPromptPart("retry the failed one")]),
                waiting,
            ]
            row.history_json = ModelMessagesTypeAdapter.dump_json(history).decode()
            await session.commit()

        in_portal(client, asked)
        script.steps = [*script.steps, say("SUMMARY")]

        assert ok(client, "/compact")["after"] is not None

        # 待確認的呼叫原樣留在尾巴，卡片照舊在等。
        history = stored_history(client)
        assert texts(history) == ["retry the failed one"]
        last = history[-1]
        assert isinstance(last, ModelResponse)
        assert [(p.tool_call_id, p.args) for p in last.parts if isinstance(p, ToolCallPart)] == [
            ("card", {"job_hash": "e" * 40})
        ]
        assert [c["id"] for c in ok(client, "/pending")["cards"]] == [card]

        decided = client.post(
            f"/api/proposals/{card}/decide", json={"approve": True}, headers=BROWSER
        )
        assert decided.status_code == 200, decided.text
        assert decided.json()["status"] == "approved"

        async def resumed(session: AsyncSession) -> tuple[str, JobState]:
            app = client.app
            executor = Executor(
                factory=app.dependency_overrides[get_client_factory](),  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
                hub=app.state.events,  # type: ignore[attr-defined]  # 同上
                sources=app.state.sources,  # type: ignore[attr-defined]  # 同上
                plans=JobHints(),
                imports=JobHints(),
            )
            view = await proposals.execute(session, executor, card)
            job = await session.get_one(Job, "e" * 40)
            return view.status, job.state

        status, state = in_portal(client, resumed)
        assert status == "executed"
        assert state != JobState.IMPORT_FAILED
        assert ok(client, "/pending")["cards"] == []
