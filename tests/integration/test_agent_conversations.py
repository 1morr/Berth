"""對話清單（M5.5 票 18、plan §6〈agent〉）：`GET /agent/conversations` 與 `/history`。

對話 id 原本只在瀏覽器裡，換瀏覽器就接不回去；清單讓人切回舊的一段，新瀏覽器自動接上最近的一段
（前端）。只列自己的，新的在前，最多 50 段；標題是第一則使用者訊息（沒有標題欄位）。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    UserPromptPart,
)
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai.fake import FakeAi
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.domain import AiProvider, AiRunKind, AiStopReason
from berth.main import create_app
from berth.models import AiConversation, AiRun
from berth.services.agent import CONVERSATION_LIST_LIMIT
from tests.integration.arrange import sign_in_crew, sign_in_owner
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import Script, chat, say, turn_ai_on
from tests.integration.test_agent_slash import OWNER_ID, in_portal, ok

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def script() -> Script:
    return Script(steps=[say("ok")])


@pytest.fixture
def client(config: Config, tmp_path: Path, script: Script) -> Iterator[TestClient]:
    factory = FakeClientFactory(ai=FakeAi(script=script))
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        turn_ai_on(running)
        yield running


def listed(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/agent/conversations")
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def seed(
    client: TestClient,
    conversation_id: str,
    *,
    said: str = "hello",
    at: datetime = T0,
    user_id: int = OWNER_ID,
    run: AiStopReason | None = AiStopReason.COMPLETED,
    kind: AiRunKind = AiRunKind.CHAT,
) -> None:
    """直接放一段對話與它的一輪：`run=None` 是那一輪還在跑（`stop_reason` 還是 `NULL`）。"""
    history: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart(said)])]

    async def put(session: AsyncSession) -> None:
        session.add(
            AiConversation(
                id=conversation_id,
                user_id=user_id,
                history_json=ModelMessagesTypeAdapter.dump_json(history).decode(),
                created_at=at,
                updated_at=at,
            )
        )
        await session.flush()
        session.add(
            AiRun(
                id=f"run-{conversation_id}",
                conversation_id=conversation_id,
                user_id=user_id,
                provider=AiProvider.ANTHROPIC,
                model="m",
                started_at=at,
                stop_reason=run,
                kind=kind,
            )
        )
        await session.commit()

    in_portal(client, put)


class TestTheList:
    def test_the_last_one_talked_in_comes_first_titled_by_its_first_message(
        self, client: TestClient
    ) -> None:
        for conversation, text in (("c1", "first one"), ("c2", "second one")):
            assert chat(client, text, conversation=conversation).status_code == 200
        assert chat(client, "back to the first", conversation="c1").status_code == 200

        found = listed(client)

        assert [(c["id"], c["title"], c["running"]) for c in found] == [
            ("c1", "first one", False),
            ("c2", "second one", False),
        ]
        assert found[0]["updated_at"] > found[1]["updated_at"]

    def test_the_title_is_the_first_line_cut_short(self, client: TestClient) -> None:
        seed(client, "c1", said=f"{'x' * 50}\nsecond line")
        seed(client, "c2", said="  short  \nsecond line", at=T0 - timedelta(minutes=1))

        assert [c["title"] for c in listed(client)] == [f"{'x' * 40}…", "short"]

    def test_the_turn_still_running_is_marked(self, client: TestClient) -> None:
        seed(client, "c1", run=None)
        seed(client, "c2", at=T0 - timedelta(minutes=1))
        # 壓縮的摘要不是一輪：它沒收尾也不算在跑。
        seed(client, "c3", at=T0 - timedelta(minutes=2), run=None, kind=AiRunKind.COMPACTION)

        assert [(c["id"], c["running"]) for c in listed(client)] == [
            ("c1", True),
            ("c2", False),
            ("c3", False),
        ]

    def test_at_most_fifty_newest_first(self, client: TestClient) -> None:
        for n in range(CONVERSATION_LIST_LIMIT + 1):
            seed(client, f"c{n}", at=T0 + timedelta(minutes=n))

        found = listed(client)

        assert len(found) == CONVERSATION_LIST_LIMIT == 50
        assert found[0]["id"] == f"c{CONVERSATION_LIST_LIMIT}"
        assert "c0" not in {c["id"] for c in found}

    def test_nobody_sees_anyone_elses(self, client: TestClient) -> None:
        assert chat(client, "the owner's", conversation="c1").status_code == 200
        sign_in_crew(client)
        assert listed(client) == []
        assert chat(client, "the crew's", conversation="c2").status_code == 200

        assert [c["id"] for c in listed(client)] == ["c2"]
        sign_in_owner(client)
        assert [c["id"] for c in listed(client)] == ["c1"]

    def test_signed_out_it_is_not_there(self, client: TestClient) -> None:
        client.cookies.clear()
        assert client.get("/api/agent/conversations").status_code == 401


class TestHistoryCommand:
    """`/history`（不叫 `/resume`：`GLOSSARY.md` 把 resume 留給 Jellyfin 的繼續觀看）。"""

    def test_it_answers_with_the_same_list(self, client: TestClient) -> None:
        seed(client, "c1", said="older", at=T0 - timedelta(minutes=1))
        seed(client, "c2", said="newer", run=None)

        # 從一段還沒有的對話（剛按了「新對話」的面板）也問得到。
        body = ok(client, "/history", conversation="fresh")

        assert body == {"command": "history", "conversations": listed(client)}
        assert [(c["id"], c["running"]) for c in body["conversations"]] == [
            ("c2", True),
            ("c1", False),
        ]

    def test_it_lists_only_your_own(self, client: TestClient) -> None:
        seed(client, "c1", said="the owner's")
        sign_in_crew(client)

        assert ok(client, "/history", conversation="fresh")["conversations"] == []
