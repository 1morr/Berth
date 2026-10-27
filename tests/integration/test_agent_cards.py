"""對話裡的確認卡（M5 票 13、plan §11.6〈分段〉第 5 段、brief §20.24）。

prototype 的 selftest 十一步（`scripts/experiments/m5_agent_selftest.py`）在這裡逐條成為整合測試，
模型是 `FakeAi` 的腳本，不打網路：

1. 寫入停在確認卡：`TestACardStops`
2. 重啟之後卡片還按得下去：`TestRestart`
3. 前端宣稱按了：`TestTheFrontendIsOnlyATrigger`
4. 部分勾選、用伺服器存的參數：`TestConfirming`
5. 模型自己編的 id：`TestRefusedBeforeACard`（來源換不回來；其餘 id 的守法在票 14）
6. 同工具同參數一直叫：`test_agent_api.py::TestGuards`（票 11）
7. 沒按就繼續說話、之後再按：`TestMovingOn`
8、9. 壓縮之後卡片還在：`TestHistoryShape`（壓縮本身在票 18；這裡守住歷史的形狀）
10. 平行呼叫：`TestParallelCalls`
11. 重新載入：`TestReload`

另外：不是提出者的一般使用者按不到別人的卡（`TestWhoMayPress`）。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.ai.fake import FakeAi
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.main import create_app
from berth.models import AiConversation, Job, Route
from berth.services.agent import load_history
from berth.services.jobs import JobSource
from berth.services.sources import SourceCache
from tests.integration.arrange import bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import (
    BROWSER,
    Script,
    Step,
    chat,
    chunks,
    recorded,
    say,
    turn_ai_on,
)
from tests.integration.test_jobs_api import ADMIN, CREW, _seed, sign_in
from tests.integration.test_media import ORDERING, SEASONS, SPY, SPY_ID

CARD = "downloading_add_manual_download"
CALL = "card-1"


@pytest.fixture
def script() -> Script:
    return Script()


@pytest.fixture
def factory(roots: dict[str, Path], script: Script) -> FakeClientFactory:
    made = factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]),
            admin=(ADMIN["username"], ADMIN["password"]),
            users={CREW["username"]: CREW["password"]},
        ),
        tmdb=FakeTmdbClient(details=[SPY], seasons=SEASONS, ordering=ORDERING),
    )
    made.ai_ = FakeAi(script=script)
    return made


def start(config: Config, tmp_path: Path, factory: FakeClientFactory) -> TestClient:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    return TestClient(app)


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """精靈跑完、Route 都在、AI 開著、作品頁打開過的一台 Berth，管理員登入著。"""
    with start(config, tmp_path, factory) as running:
        _seed(running, roots, factory)
        sign_in(running, CREW)
        sign_in(running)
        turn_ai_on(running)
        assert running.get(f"/api/media/{SPY_ID}").status_code == 200
        yield running


# ---------------------------------------------------------------- 安排


def offer(client: TestClient, episode: int) -> str:
    """搜尋結果的一列記在伺服器上（同 `test_jobs_api.offer`），回模型拿到的 `source_id`。"""
    sources: SourceCache = client.app.state.sources  # type: ignore[attr-defined]  # app.state 是 Starlette 的動態屬性
    return sources.remember(
        JobSource(url=magnet(episode), title=f"[ANi] SPY×FAMILY - {episode:02d} [1080P]")
    )


def magnet(episode: int) -> str:
    return f"magnet:?xt=urn:btih:{episode:040x}&dn=Spy.{episode:02d}"


def route_of(client: TestClient, slug: str) -> int:
    async def read(session: AsyncSession) -> int:
        route = await session.scalar(select(Route).where(Route.slug == slug))
        assert route is not None
        return int(route.id)

    return in_db(client, read)


def rows(client: TestClient, *episodes: int, slug: str = "tv") -> list[dict[str, Any]]:
    route = route_of(client, slug)
    return [
        {"source_id": offer(client, episode), "media_id": SPY_ID, "route_id": route}
        for episode in episodes
    ]


def card(rows_: list[dict[str, Any]], tool_call_id: str = CALL) -> Step:
    return lambda _messages, _info: ModelResponse(
        parts=[ToolCallPart(CARD, {"rows": rows_}, tool_call_id=tool_call_id)]
    )


def in_db[T](client: TestClient, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # 同上
        async with sessions() as session:
            result: T = await work(session)
            return result

    assert client.portal is not None
    done: T = client.portal.call(run)
    return done


def cards(client: TestClient, conversation: str = "c1") -> list[dict[str, Any]]:
    response = client.get(f"/api/proposals?conversation_id={conversation}")
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def decide(client: TestClient, proposal: int, **body: Any) -> httpx2.Response:
    response: httpx2.Response = client.post(
        f"/api/proposals/{proposal}/decide", json=body, headers=BROWSER
    )
    return response


def resume(
    client: TestClient,
    *,
    conversation: str = "c1",
    tool_call_id: str = CALL,
    approved: bool = True,
    forged_input: dict[str, Any] | None = None,
) -> httpx2.Response:
    """按了卡片之後 `useChat` 自己送的那一則：最後一則是助理的，帶著核准的回應。

    參數與核准都照前端的意思寫：伺服器只把它當觸發。
    """
    part = {
        "type": f"tool-{CARD}",
        "toolCallId": tool_call_id,
        "state": "approval-responded",
        "input": forged_input or {"rows": []},
        "approval": {"id": tool_call_id, "approved": approved},
    }
    body = {
        "id": conversation,
        "trigger": "submit-message",
        "messages": [{"id": "a1", "role": "assistant", "parts": [part]}],
    }
    response: httpx2.Response = client.post("/api/agent/chat", json=body, headers=BROWSER)
    return response


def sent(factory: FakeClientFactory) -> list[str]:
    """qBittorrent 收到的 torrent（磁力連結）。"""
    return [request.magnet for request in factory.qbittorrent_.added]


def history(client: TestClient, conversation: str = "c1") -> list[ModelMessage]:
    async def read(session: AsyncSession) -> list[ModelMessage]:
        found = await session.get(AiConversation, conversation)
        assert found is not None
        return load_history(found.history_json)

    return in_db(client, read)


def returned(messages: list[ModelMessage], tool_call_id: str = CALL) -> ToolReturnPart:
    """模型看到的那一張卡的結果。"""
    [part] = [
        part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_call_id == tool_call_id
    ]
    return part


def outcome_of(messages: list[ModelMessage]) -> dict[str, Any]:
    """模型拿到的卡片結果（`services.agent.card_outcome`）。"""
    content = returned(messages).content
    assert isinstance(content, dict)
    return content


def mentions(response: httpx2.Response, tool_call_id: str) -> bool:
    return any(chunk.get("toolCallId") == tool_call_id for chunk in chunks(response))


# ---------------------------------------------------------------- 1


class TestACardStops:
    def test_a_download_stops_at_a_card_and_nothing_is_sent(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [card(rows(client, 1, 2))]

        response = chat(client, "Download SPY×FAMILY 1 and 2.")

        assert response.status_code == 200, response.text
        approvals = [c for c in chunks(response) if c["type"] == "tool-approval-request"]
        assert [c["toolCallId"] for c in approvals] == [CALL]
        [proposal] = cards(client)
        assert proposal["status"] == "pending"
        assert proposal["tool_call_id"] == CALL
        assert proposal["command"] == "downloading.add_manual_download"
        assert len(proposal["arguments"]) == 2
        assert proposal["preview"]["flags"] == ["downloads"]
        assert sent(factory) == []
        [turn] = recorded(client)
        assert turn.run.stop_reason == "awaiting_confirmation"
        assert [(t.command, t.outcome) for t in turn.tools] == [
            ("downloading.add_manual_download", "proposed")
        ]

    def test_the_card_never_hands_the_download_link_out(
        self, client: TestClient, script: Script
    ) -> None:
        """同 M4 票 79：下載連結記在伺服器上。卡片存著它（執行要用），給瀏覽器的那一份沒有。"""
        script.steps = [card(rows(client, 1))]
        chat(client, "Download episode 1.")

        response = client.get("/api/proposals?conversation_id=c1")

        assert magnet(1) not in response.text
        assert response.json()[0]["arguments"][0]["source"]["title"].startswith("[ANi]")


# ---------------------------------------------------------------- 4


class TestConfirming:
    def test_only_the_ticked_row_is_sent_with_the_stored_arguments(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [card(rows(client, 1, 2, 3)), say("Sent episode 2.")]
        chat(client, "Download episodes 1 to 3.")
        [proposal] = cards(client)

        pressed = decide(client, proposal["id"], approve=True, selection=[1])

        # 按下去就做了，逐列看得到結果。
        assert pressed.status_code == 200, pressed.text
        assert pressed.json()["status"] == "executed"
        assert [row["outcome"] for row in pressed.json()["results"]] == [
            "skipped",
            "done",
            "skipped",
        ]
        assert sent(factory) == [magnet(2)]

        # 前端觸發恢復，還送來竄改過的參數：不採用，也不再做一次。
        forged = {"rows": rows(client, 9)}
        response = resume(client, forged_input=forged)

        assert response.status_code == 200, response.text
        assert sent(factory) == [magnet(2)]
        outcome = returned(script.seen[-1]).content
        assert isinstance(outcome, dict)
        assert outcome["approved_by_user"] is True
        assert outcome["executed"] is True
        assert [row["outcome"] for row in outcome["rows"]] == ["skipped", "done", "skipped"]
        # 結果接在同一則助理訊息上：前端的那一格從「等確認」變成有結果。
        assert any(
            c["type"] == "tool-output-available" and c["toolCallId"] == CALL
            for c in chunks(response)
        )
        assert any(c.get("delta") == "Sent episode 2." for c in chunks(response))
        assert recorded(client)[-1].run.stop_reason == "completed"

    def test_a_rejected_card_does_nothing_and_the_model_hears_so(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [card(rows(client, 1)), say("Okay, not sending it.")]
        chat(client, "Download episode 1.")
        [proposal] = cards(client)

        assert decide(client, proposal["id"], approve=False).json()["status"] == "rejected"
        response = resume(client, approved=False)

        assert response.status_code == 200, response.text
        assert sent(factory) == []
        denied = returned(script.seen[-1])
        assert denied.outcome == "denied"
        assert "rejected" in denied.model_response_str()

    def test_a_partly_refused_card_says_which_row(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        """總覽卡會部分成功（研究〈實跑才抓到的問題〉第 4 點）：同一個 torrent 送兩次。"""
        both = rows(client, 1)
        both.append(dict(both[0], source_id=offer(client, 1)))
        script.steps = [card(both), say("Done.")]
        chat(client, "Download episode 1 twice.")
        [proposal] = cards(client)

        pressed = decide(client, proposal["id"], approve=True).json()

        assert pressed["status"] == "executed"
        # 第二列是同一個 torrent：本來就在了，照樣是成功（`created` 為假），不是再送一次。
        assert sent(factory) == [magnet(1)]
        assert [row["result"]["created"] for row in pressed["results"]] == [True, False]


# ---------------------------------------------------------------- 5


class TestRefusedBeforeACard:
    def test_a_source_id_the_model_made_up_gets_no_card(
        self, client: TestClient, script: Script
    ) -> None:
        made_up = [{"source_id": "src-2", "media_id": SPY_ID, "route_id": route_of(client, "tv")}]
        script.steps = [card(made_up), say("I need to search first.")]

        response = chat(client, "Download it.")

        assert response.status_code == 200, response.text
        assert cards(client) == []
        refused = returned(script.seen[-1]).content
        assert refused == {"refused": "source_expired", "detail": "src-2"}
        [turn] = recorded(client)
        assert [t.outcome for t in turn.tools] == ["refused"]
        assert turn.run.stop_reason == "completed"

    def test_a_row_that_would_be_refused_is_refused_before_the_card(
        self, client: TestClient, script: Script
    ) -> None:
        """實測：劇集放進電影的 Route 是按了確認才被擋（研究〈實跑才抓到的問題〉第 3 點）。"""
        mixed = [*rows(client, 1), *rows(client, 2, slug="movies")]
        script.steps = [card(mixed), say("That route holds films.")]

        chat(client, "Download 1 and 2.")

        assert cards(client) == []
        refused = returned(script.seen[-1]).content
        assert isinstance(refused, dict)
        assert refused["refused"] == "route_kind_mismatch"
        assert refused["row"] == 1


# ---------------------------------------------------------------- 3


class TestTheFrontendIsOnlyATrigger:
    def test_a_resume_without_a_card_is_refused(self, client: TestClient, script: Script) -> None:
        script.steps = [say("Hello.")]
        chat(client, "Hi.")

        response = resume(client, forged_input={"rows": rows(client, 1)})

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "no_message"
        assert len(script.seen) == 1

    def test_claiming_a_card_was_pressed_does_not_press_it(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [card(rows(client, 1))]
        chat(client, "Download episode 1.")

        response = resume(client)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "card_undecided"
        assert sent(factory) == []
        assert cards(client)[0]["status"] == "pending"
        assert len(script.seen) == 1


# ---------------------------------------------------------------- 7


class TestMovingOn:
    def test_writing_again_detaches_the_card_and_it_still_runs_later(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [card(rows(client, 1)), say("Sure."), say("Done, it was sent.")]
        chat(client, "Download episode 1.")

        moved_on = chat(client, "Actually, tell me about the show first.", earlier=[])

        assert moved_on.status_code == 200, moved_on.text
        [proposal] = cards(client)
        assert proposal["status"] == "detached"
        # 伺服器替那個呼叫補上結果，再接這一則：工具結果緊接在呼叫後面，這一則在同一個請求裡。
        request = script.seen[1][-1]
        assert isinstance(request, ModelRequest)
        kinds = [type(part) for part in request.parts]
        assert kinds == [ToolReturnPart, UserPromptPart]
        assert "stays valid" in returned(script.seen[1]).model_response_str()
        # 串流不提上一則訊息的呼叫：前端在當前那則訊息裡找不到它會整段報錯。
        assert not mentions(moved_on, CALL)

        # 之後才按：當場執行。
        pressed = decide(client, proposal["id"], approve=True)
        assert pressed.json()["status"] == "executed"
        assert sent(factory) == [magnet(1)]

        # 下一輪的 instructions 帶上它的結果。
        chat(client, "Did it go through?")
        last = script.seen[2][-1]
        assert isinstance(last, ModelRequest)
        instructions = last.instructions
        assert isinstance(instructions, str)
        assert f"tool call {CALL}): executed; rows: 1 done" in instructions

    def test_a_card_decided_before_writing_again_hands_over_its_result(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        """按了、恢復那一輪卻沒送出去（關掉頁面、AI 被關掉）：下一則訊息把結果帶給模型。"""
        script.steps = [card(rows(client, 1)), say("It was sent.")]
        chat(client, "Download episode 1.")
        decide(client, cards(client)[0]["id"], approve=True)

        chat(client, "So?")

        outcome = returned(script.seen[1]).content
        assert isinstance(outcome, dict)
        assert outcome["executed"] is True
        assert cards(client)[0]["status"] == "executed"
        assert sent(factory) == [magnet(1)]


# ---------------------------------------------------------------- 10


class TestParallelCalls:
    def test_the_card_is_found_although_another_result_comes_after_it(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        both = rows(client, 1)
        script.steps = [
            lambda _m, _i: ModelResponse(
                parts=[
                    ToolCallPart("jobs_list_jobs", {}, tool_call_id="read-1"),
                    ToolCallPart(CARD, {"rows": both}, tool_call_id=CALL),
                ]
            ),
            say("Sent."),
        ]
        chat(client, "Check downloads and send episode 1.")
        stored = history(client)
        assert isinstance(stored[-1], ModelRequest)
        assert [type(part) for part in stored[-1].parts] == [ToolReturnPart]

        decide(client, cards(client)[0]["id"], approve=True)
        response = resume(client)

        assert response.status_code == 200, response.text
        assert outcome_of(script.seen[-1])["executed"] is True
        assert sent(factory) == [magnet(1)]


# ---------------------------------------------------------------- 8、9


class TestHistoryShape:
    def test_the_waiting_call_stays_at_the_end_of_the_history(
        self, client: TestClient, script: Script
    ) -> None:
        """壓縮（票 18）切在使用者訊息上、保留尾巴；卡片的呼叫一定在尾巴裡。"""
        script.steps = [card(rows(client, 1))]
        chat(client, "Download episode 1.")

        stored = history(client)

        assert isinstance(stored[-1], ModelResponse)
        assert [call.tool_call_id for call in stored[-1].tool_calls] == [CALL]

    def test_a_card_still_resumes_after_the_head_of_the_history_is_dropped(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [
            say("Hello."),
            card(rows(client, 1)),
            say("Sent."),
        ]
        chat(client, "Hi.")
        chat(client, "Download episode 1.")
        tail = history(client)[2:]
        assert isinstance(tail[0], ModelRequest)

        async def compact(session: AsyncSession) -> None:
            found = await session.get(AiConversation, "c1")
            assert found is not None
            found.history_json = ModelMessagesTypeAdapter.dump_json(tail).decode()
            await session.commit()

        in_db(client, compact)
        decide(client, cards(client)[0]["id"], approve=True)
        response = resume(client)

        assert response.status_code == 200, response.text
        assert sent(factory) == [magnet(1)]
        assert outcome_of(script.seen[-1])["executed"] is True


# ---------------------------------------------------------------- 11


class TestReload:
    def test_the_waiting_card_comes_back_as_an_approval_request(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [card(rows(client, 1))]
        chat(client, "Download episode 1.")

        messages = client.get("/api/agent/conversations/c1").json()["messages"]

        parts = [part for m in messages if m["role"] == "assistant" for part in m["parts"]]
        [tool] = [part for part in parts if part["type"] == f"tool-{CARD}"]
        assert tool["state"] == "approval-requested"
        assert tool["toolCallId"] == cards(client)[0]["tool_call_id"]
        assert "source_id" in json.dumps(tool["input"])


# ---------------------------------------------------------------- 2


class TestRestart:
    def test_a_card_from_before_a_restart_is_pressed_and_resumed_after_it(
        self,
        config: Config,
        tmp_path: Path,
        client: TestClient,
        script: Script,
        factory: FakeClientFactory,
    ) -> None:
        script.steps = [card(rows(client, 1)), say("Sent.")]
        chat(client, "Download episode 1.")
        [proposal] = cards(client)

        # 新的行程：新的來源快取（搜尋結果的 id 都不認得了）、新的 runtime，只有資料庫還在。
        with start(config, tmp_path, factory) as after:
            sign_in(after)
            pressed = decide(after, proposal["id"], approve=True)
            response = resume(after)

        assert pressed.json()["status"] == "executed"
        assert sent(factory) == [magnet(1)]
        assert response.status_code == 200, response.text
        assert outcome_of(script.seen[-1])["executed"] is True


# ---------------------------------------------------------------- 誰按得到


class TestWhoMayPress:
    def test_an_ordinary_user_cannot_press_someone_elses_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [card(rows(client, 1))]
        chat(client, "Download episode 1.")
        [proposal] = cards(client)
        sign_in(client, CREW)

        response = decide(client, proposal["id"], approve=True)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "proposal_missing"
        assert client.get("/api/proposals").json() == []
        assert sent(factory) == []

    def test_an_ordinary_user_sends_their_own(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        sign_in(client, CREW)
        script.steps = [card(rows(client, 1)), say("Sent.")]
        chat(client, "Download episode 1.", conversation="crew")
        [proposal] = cards(client, "crew")

        pressed = decide(client, proposal["id"], approve=True)

        assert pressed.json()["status"] == "executed"
        assert sent(factory) == [magnet(1)]

        async def owners(session: AsyncSession) -> list[int | None]:
            return list(await session.scalars(select(Job.user_id)))

        # Job 記在他名下：做的人是提出者（AI 替他），不是按的人以外的誰。
        assert in_db(client, owners) == [pressed.json()["user_id"]]
