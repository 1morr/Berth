"""同一步並行的工具呼叫（M5 票 24）。

pydantic-ai 把同一則回應裡的工具呼叫一起跑，`Turn.run_tool` 每一支各開一個 session。2026-10-28
試用機上模型同一步叫了 `media_read_media` 與 `search_search_torrents`，兩支都在「這部作品還沒有
快照」時建 `media` 列，後到的那一支回模型一串 `UNIQUE constraint failed: media.id`。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart

from berth.adapters.ai.fake import FakeAi
from berth.adapters.tmdb import TmdbDetail
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.config import Config
from berth.domain import AiToolOutcome, MediaKind
from tests.integration.arrange import Meeting, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import Script, chat, recorded, say, turn_ai_on
from tests.integration.test_agent_cards import start
from tests.integration.test_jobs_api import ADMIN, _seed, sign_in
from tests.integration.test_media import ORDERING, SEASONS, SPY, SPY_ID


class OverTheNetwork(FakeTmdbClient):
    """真的 TMDB 走網路，兩支工具都會在「還沒有快照」時出發；替身不讓出事件迴圈，所以在這裡碰面。"""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]  # 照傳給 FakeTmdbClient 的關鍵字參數
        self.meeting = Meeting()

    async def detail(self, kind: MediaKind, tmdb_id: int, *, language: str) -> TmdbDetail:
        await self.meeting.arrive()
        return await super().detail(kind, tmdb_id, language=language)


@pytest.fixture
def script() -> Script:
    return Script()


@pytest.fixture
def factory(roots: dict[str, Path], script: Script) -> FakeClientFactory:
    made = factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]), admin=(ADMIN["username"], ADMIN["password"])
        ),
        tmdb=OverTheNetwork(details=[SPY], seasons=SEASONS, ordering=ORDERING),
    )
    made.ai_ = FakeAi(script=script)
    return made


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """精靈跑完、AI 開著；作品頁**沒有**打開過，所以 SPY×FAMILY 還沒有快照。"""
    with start(config, tmp_path, factory) as running:
        _seed(running, roots, factory)
        sign_in(running)
        turn_ai_on(running)
        yield running


def at_once(*commands: str) -> ModelResponse:
    """一則回應裡一起叫這幾個命令（工具名是登錄表名字的 `.` 換成 `_`）。"""
    return ModelResponse(
        parts=[
            ToolCallPart(name.replace(".", "_"), {"media_id": SPY_ID}, tool_call_id=f"call-{index}")
            for index, name in enumerate(commands)
        ]
    )


def test_two_tools_building_the_same_snapshot_both_succeed(
    client: TestClient, script: Script
) -> None:
    """試用機上撞到的那一對：兩支都要先有這部作品的快照。"""
    commands = ("media.read_media", "search.search_torrents")
    script.steps = [lambda _m, _i: at_once(*commands), say("Done.")]

    response = chat(client, "Subscribe to SPY×FAMILY.")

    assert response.status_code == 200, response.text
    [turn] = recorded(client)
    assert sorted((tool.command, tool.outcome, tool.detail) for tool in turn.tools) == [
        ("media.read_media", AiToolOutcome.OK, ""),
        ("search.search_torrents", AiToolOutcome.OK, ""),
    ]
