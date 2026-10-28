"""一輪在伺服器上跑完，不綁在那一條連線上（M5 票 25，plan §11.6〈串流〉）。

照 Vercel AI SDK 的 resumable streams：瀏覽器斷線只是斷線，那一輪照跑；回到對話時
`GET /agent/conversations/{id}` 說哪一輪還在跑，`GET .../stream?turn=<id>` 從頭重播並跟著，
沒有在跑的回 204；停止是另一個端點。

**斷線要真的斷**：`TestClient` 讀完整個回應才回來，所以「跑到一半離開」直接對 ASGI app 送請求、
收到想要的片段之後回 `http.disconnect`（Starlette 的 `StreamingResponse` 在 ASGI spec 2.4 之前
靠它知道斷線）。
替身模型的 `FakeAi.pause` 讓某一次模型呼叫等到測試放行，於是「還在跑」是確定的，不靠時間。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.ai.fake import FakeAi
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import Actor, AiProvider, Language, Role
from berth.main import create_app
from berth.models import AiConversation, AiRun
from berth.services.agent import AgentRuntime, load_history, open_turn, start_turn
from berth.services.executor import Executor
from berth.services.hints import JobHints
from tests.integration.arrange import sign_in_crew, sign_in_owner
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}

Step = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


@dataclass
class Script:
    steps: list[Step] = field(default_factory=list)
    calls: int = 0

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.calls += 1
        return self.steps[min(self.calls, len(self.steps)) - 1](messages, info)


def call(tool: str, **args: object) -> Step:
    return lambda _messages, _info: ModelResponse(parts=[ToolCallPart(tool, dict(args))])


def say(text: str) -> Step:
    return lambda _messages, _info: ModelResponse(parts=[TextPart(text)])


class Gate:
    """第 `at` 次模型呼叫等到 `open()`：那一輪在這之前一定還在跑。"""

    def __init__(self, at: int) -> None:
        self.at = at
        self.calls = 0
        self.event: anyio.Event | None = None

    async def __call__(self, _messages: list[ModelMessage]) -> None:
        self.calls += 1
        if self.calls < self.at:
            return
        if self.event is None:
            self.event = anyio.Event()
        await self.event.wait()


@pytest.fixture
def script() -> Script:
    return Script()


@pytest.fixture
def ai(script: Script) -> FakeAi:
    return FakeAi(script=script)


@pytest.fixture
def factory(ai: FakeAi) -> FakeClientFactory:
    return FakeClientFactory(ai=ai)


def start(config: Config, tmp_path: Path, factory: FakeClientFactory) -> TestClient:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    return TestClient(app)


@pytest.fixture
def client(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    with start(config, tmp_path, factory) as running:
        sign_in_owner(running)
        turn_ai_on(running)
        yield running


def turn_ai_on(client: TestClient) -> None:
    body = {
        "enabled": True,
        "provider": "anthropic",
        "base_url": "",
        "model": "claude-sonnet-5-5",
        "api_key": "sk-ant-api03-resume-test-key",
    }
    assert client.put("/api/settings/ai", json=body, headers=BROWSER).status_code == 200


def chat_body(text: str, conversation: str = "c1") -> dict[str, Any]:
    return {
        "id": conversation,
        "trigger": "submit-message",
        "language": "en",
        "messages": [{"id": "u1", "role": "user", "parts": [{"type": "text", "text": text}]}],
    }


def chunks_of(body: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]


def text_of(found: list[dict[str, Any]]) -> str:
    return "".join(c["delta"] for c in found if c["type"] == "text-delta")


def leave_after(
    client: TestClient,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    until: Callable[[list[dict[str, Any]]], bool],
) -> Future[list[dict[str, Any]]]:
    """對 app 送一個請求，收到 `until` 說夠了的片段就斷線（`http.disconnect`）。回收到的片段。"""
    raw = json.dumps(body).encode() if body is not None else b""
    cookie = "; ".join(f"{name}={value}" for name, value in client.cookies.items())
    path, _, query = path.partition("?")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"cookie", cookie.encode()),
            (b"content-type", b"application/json"),
            (CSRF_HEADER.lower().encode(), b"XMLHttpRequest"),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }

    async def run() -> list[dict[str, Any]]:
        left = anyio.Event()
        sent = False
        text = ""

        async def receive() -> dict[str, Any]:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": raw, "more_body": False}
            await left.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            nonlocal text
            if message["type"] == "http.response.body":
                text += message.get("body", b"").decode()
                if until(chunks_of(text)):
                    left.set()
                if not message.get("more_body", False):
                    left.set()

        await client.app(scope, receive, send)  # type: ignore[arg-type]  # ASGI 的 scope 是 dict，Starlette 的型別要 MutableMapping
        return chunks_of(text)

    assert client.portal is not None
    future: Future[list[dict[str, Any]]] = client.portal.start_task_soon(run)
    return future


def has_tool_output(found: list[dict[str, Any]]) -> bool:
    return any(c["type"] == "tool-output-available" for c in found)


def runs(client: TestClient) -> list[AiRun]:
    async def read() -> list[AiRun]:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            return list(await session.scalars(select(AiRun).order_by(AiRun.started_at)))

    assert client.portal is not None
    found: list[AiRun] = client.portal.call(read)
    return found


def history(client: TestClient, conversation: str = "c1") -> list[ModelMessage]:
    async def read() -> list[ModelMessage]:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # 同上
        async with sessions() as session:
            found = await session.get_one(AiConversation, conversation)
            return load_history(found.history_json)

    assert client.portal is not None
    found: list[ModelMessage] = client.portal.call(read)
    return found


def answer_text(messages: list[ModelMessage]) -> str:
    return "".join(
        part.content
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, TextPart)
    )


def open_gate(client: TestClient, gate: Gate) -> None:
    assert client.portal is not None and gate.event is not None
    client.portal.call(gate.event.set)


def wait_for_gate(client: TestClient, gate: Gate) -> None:
    """等那一輪跑到被擋住的那一次模型呼叫。"""

    async def until_held() -> None:
        with anyio.fail_after(5):
            while gate.event is None:
                await anyio.sleep(0.01)

    assert client.portal is not None
    client.portal.call(until_held)


class TestLeavingMidway:
    def test_the_turn_runs_to_the_end_and_a_return_picks_up_the_rest(
        self, client: TestClient, ai: FakeAi, script: Script
    ) -> None:
        script.steps = [call("jobs_list_jobs"), say("Nothing is downloading.")]
        gate = Gate(at=2)
        ai.pause = gate

        left = leave_after(
            client,
            "POST",
            "/api/agent/chat",
            body=chat_body("What is downloading?"),
            until=has_tool_output,
        )
        seen = left.result(timeout=5)
        assert has_tool_output(seen)
        wait_for_gate(client, gate)

        # 回到對話：那一輪還在跑，讀到的是它開始之前的樣子加上這一則。
        conversation = client.get("/api/agent/conversations/c1").json()
        [run] = runs(client)
        assert run.stop_reason is None
        assert conversation["running"] == run.id
        assert conversation["messages"][-1]["role"] == "user"

        # 跟著看的那一條在放行之前就接上，從頭重播、跟到答完。
        follow = leave_after(
            client,
            "GET",
            f"/api/agent/conversations/c1/stream?turn={run.id}",
            until=lambda _: False,
        )
        open_gate(client, gate)
        replayed = follow.result(timeout=5)

        assert has_tool_output(replayed)
        assert text_of(replayed) == "Nothing is downloading."
        assert replayed[-1]["type"] == "finish"
        [run] = runs(client)
        assert run.stop_reason == "completed"
        assert answer_text(history(client)) == "Nothing is downloading."
        assert client.get("/api/agent/conversations/c1").json()["running"] is None


def stop_of(found: list[dict[str, Any]]) -> dict[str, Any]:
    [stop] = [c["data"] for c in found if c["type"] == "data-stop"]
    data: dict[str, Any] = stop
    return data


def stop_note(client: TestClient, conversation: str = "c1") -> dict[str, Any]:
    """重新載入時最後一則停下的說明（`data-stop` 的 `data`）。"""
    messages = client.get(f"/api/agent/conversations/{conversation}").json()["messages"]
    stops = [p["data"] for m in messages for p in m["parts"] if p["type"] == "data-stop"]
    last: dict[str, Any] = stops[-1]
    return last


class TestStopping:
    def test_stop_ends_the_turn_at_once_and_everyone_watching_sees_it(
        self, client: TestClient, ai: FakeAi, script: Script
    ) -> None:
        script.steps = [call("jobs_list_jobs"), say("Never said.")]
        gate = Gate(at=2)
        ai.pause = gate
        first = leave_after(
            client,
            "POST",
            "/api/agent/chat",
            body=chat_body("What is downloading?"),
            until=lambda _: False,
        )
        wait_for_gate(client, gate)
        [run] = runs(client)
        second = leave_after(
            client,
            "GET",
            f"/api/agent/conversations/c1/stream?turn={run.id}",
            until=lambda _: False,
        )

        # 擋住的那一次模型呼叫永遠不放行：停止不等它。
        response = client.post("/api/agent/conversations/c1/stop", headers=BROWSER)

        assert response.status_code == 204
        [run] = runs(client)
        assert run.stop_reason == "cancelled"
        for watching in (first, second):
            found = watching.result(timeout=5)
            stop = stop_of(found)
            assert stop["reason"] == "cancelled"
            assert stop["note"].startswith("This reply was stopped: you pressed Stop.")
            assert found[-1]["type"] == "finish"
        assert stop_note(client)["reason"] == "cancelled"
        assert client.get("/api/agent/conversations/c1").json()["running"] is None
        # 位子讓出來了：下一則照常開。
        ai.pause = None
        script.steps = [say("Hi.")]
        assert (
            client.post("/api/agent/chat", json=chat_body("Hello?"), headers=BROWSER).status_code
            == 200
        )

    def test_nothing_running_cannot_be_stopped(self, client: TestClient, script: Script) -> None:
        script.steps = [say("Done.")]
        assert (
            client.post("/api/agent/chat", json=chat_body("Hi"), headers=BROWSER).status_code == 200
        )

        response = client.post("/api/agent/conversations/c1/stop", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "not_running"
        [run] = runs(client)
        assert run.stop_reason == "completed"

    def test_someone_else_cannot_stop_or_follow_my_turn(
        self, client: TestClient, ai: FakeAi, script: Script
    ) -> None:
        script.steps = [call("jobs_list_jobs"), say("Done.")]
        gate = Gate(at=2)
        ai.pause = gate
        leave_after(
            client,
            "POST",
            "/api/agent/chat",
            body=chat_body("What is downloading?"),
            until=has_tool_output,
        ).result(timeout=5)
        wait_for_gate(client, gate)
        [run] = runs(client)
        owner = dict(client.cookies)

        sign_in_crew(client)
        stopped = client.post("/api/agent/conversations/c1/stop", headers=BROWSER)
        followed = client.get(f"/api/agent/conversations/c1/stream?turn={run.id}")

        assert stopped.status_code == 409
        assert stopped.json()["detail"]["reason"] == "not_running"
        assert followed.status_code == 204
        client.cookies.update(owner)
        open_gate(client, gate)


class TestOneTurnAtATime:
    def test_coming_back_does_not_open_a_second_turn(
        self, client: TestClient, ai: FakeAi, script: Script
    ) -> None:
        script.steps = [call("jobs_list_jobs"), say("Done.")]
        gate = Gate(at=2)
        ai.pause = gate
        leave_after(
            client,
            "POST",
            "/api/agent/chat",
            body=chat_body("What is downloading?"),
            until=has_tool_output,
        ).result(timeout=5)
        wait_for_gate(client, gate)
        [run] = runs(client)

        # 重新整理：讀對話、重連（離開兩次），再從另一個分頁送一則。
        for _ in range(2):
            assert client.get("/api/agent/conversations/c1").json()["running"] == run.id
            leave_after(
                client,
                "GET",
                f"/api/agent/conversations/c1/stream?turn={run.id}",
                until=has_tool_output,
            ).result(timeout=5)
        other_tab = client.post(
            "/api/agent/chat", json=chat_body("Anything else?"), headers=BROWSER
        )

        assert other_tab.status_code == 409
        assert other_tab.json()["detail"]["reason"] == "busy"
        assert [r.id for r in runs(client)] == [run.id]
        open_gate(client, gate)

    def test_a_turn_that_is_not_running_has_nothing_to_resume(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [say("Done.")]
        assert (
            client.post("/api/agent/chat", json=chat_body("Hi"), headers=BROWSER).status_code == 200
        )

        response = client.get("/api/agent/conversations/c1/stream?turn=someone-else")

        assert response.status_code == 204


class TestRestarting:
    def test_a_turn_running_at_shutdown_is_closed_with_its_reason(
        self, config: Config, tmp_path: Path, factory: FakeClientFactory, ai: FakeAi, script: Script
    ) -> None:
        script.steps = [call("jobs_list_jobs"), say("Never said.")]
        gate = Gate(at=2)
        ai.pause = gate
        with start(config, tmp_path, factory) as running:
            sign_in_owner(running)
            turn_ai_on(running)
            leave_after(
                running,
                "POST",
                "/api/agent/chat",
                body=chat_body("What is downloading?"),
                until=has_tool_output,
            ).result(timeout=5)
            wait_for_gate(running, gate)
            cookies = dict(running.cookies)

        with start(config, tmp_path, factory) as again:
            again.cookies.update(cookies)
            [run] = runs(again)
            assert run.stop_reason == "interrupted"
            assert run.ended_at is not None
            stop = stop_note(again)
            assert stop["reason"] == "interrupted"
            # 是關機時收的（`AgentRuntime.aclose`），不是下一次啟動補記的：照這一輪的介面語言
            # （英文）寫，而補記照這個人的通知語言（中文）；存到最後一次模型呼叫之前，第一次叫的
            # 工具與它的結果都在歷史裡（補記只有開輪時那一份）。
            assert stop["note"].startswith("This reply was stopped: Berth restarted")
            assert "jobs.list_jobs" in stop["note"]
            assert any(
                isinstance(part, ToolReturnPart) and part.tool_name == "jobs_list_jobs"
                for message in history(again)
                for part in message.parts
            )
            assert again.get("/api/agent/conversations/c1").json()["running"] is None

    def test_a_turn_cut_off_by_a_crash_is_closed_on_the_next_start(
        self, config: Config, tmp_path: Path, factory: FakeClientFactory, ai: FakeAi, script: Script
    ) -> None:
        """崩潰（沒跑到關機的收尾）：`ai_runs` 還是 `NULL`。

        下一次啟動時記成 `interrupted`、補一則說明，用那個人的通知語言寫。
        """
        script.steps = [say("Hi.")]
        with start(config, tmp_path, factory) as running:
            sign_in_owner(running)
            turn_ai_on(running)
            assert (
                running.post("/api/agent/chat", json=chat_body("Hi"), headers=BROWSER).status_code
                == 200
            )
            cookies = dict(running.cookies)

            async def crash_midway() -> None:
                # 再開一輪、在它收尾之前「崩潰」：歷史停在開輪時存的那一份，
                # `stop_reason` 是 `NULL`。
                sessions: async_sessionmaker[AsyncSession] = running.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
                async with sessions() as session:
                    conversation = await session.get_one(AiConversation, "c1")
                    started = [
                        *load_history(conversation.history_json),
                        ModelRequest(parts=[UserPromptPart("Still there?")]),
                    ]
                    conversation.history_json = ModelMessagesTypeAdapter.dump_json(started).decode()
                    session.add(
                        AiRun(
                            id="crashed",
                            conversation_id="c1",
                            user_id=1,
                            provider=AiProvider.ANTHROPIC,
                            model="claude-sonnet-5-5",
                            requests=2,
                            tool_calls=1,
                        )
                    )
                    await session.commit()

            assert running.portal is not None
            running.portal.call(crash_midway)

        with start(config, tmp_path, factory) as again:
            again.cookies.update(cookies)
            crashed = next(r for r in runs(again) if r.id == "crashed")
            assert crashed.stop_reason == "interrupted"
            assert crashed.ended_at is not None
            stop = stop_note(again)
            assert stop["turn_id"] == "crashed"
            assert stop["note"].startswith("這一輪停下來了：Berth 重新啟動")
            assert "已做：2 次模型呼叫、1 次工具呼叫" in stop["note"]
            assert again.get("/api/agent/conversations/c1").json()["running"] is None
            # 接得下去：下一則照常開，模型看得到那一則與說明。
            script.steps = [say("Yes.")]
            assert (
                again.post(
                    "/api/agent/chat", json=chat_body("Hello again?"), headers=BROWSER
                ).status_code
                == 200
            )


class TestATurnThatBreaks:
    def test_a_stream_that_fails_to_start_is_still_closed_and_frees_the_slot(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """串流在 task 裡才組：組到一半出錯，那一輪記成 `error`、這個人不會一直 `busy`。"""
        app: Any = client.app
        runtime: AgentRuntime = app.state.agent

        async def broken() -> None:
            turn = await open_turn(
                runtime=runtime,
                sessions=app.state.session_factory,
                executor=Executor(
                    factory=factory,
                    hub=app.state.events,
                    sources=app.state.sources,
                    plans=JobHints(),
                    imports=JobHints(),
                ),
                factory=factory,
                actor=Actor.ai(1, Role.ADMIN),
                conversation_id="c1",
                text="What is downloading?",
                language=Language.EN,
            )

            def chunks(_turn: Any) -> Any:
                raise RuntimeError("the adapter could not be built")

            live = await start_turn(runtime, turn, chunks, lambda _note, _stop: [])
            with anyio.fail_after(5):
                async for _ in live.follow():
                    pass

        assert client.portal is not None
        client.portal.call(broken)

        [run] = runs(client)
        assert run.stop_reason == "error"
        assert client.get("/api/agent/conversations/c1").json()["running"] is None
        runtime.claim(1)
