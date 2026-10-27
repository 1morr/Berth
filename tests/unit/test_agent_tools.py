"""側面板的工具與每人一輪的位子（M5 票 11）：工具都來自命令登錄表，帶著給模型的說明。

票 11 只開讀取類；寫入（要確認卡的）在票 13、14 加進來時，這裡的「只讀」跟著改成那兩張的規則。
"""

from __future__ import annotations

import re

import pytest

from berth.adapters.ai import chat_settings
from berth.domain import AiProvider, Role
from berth.services.agent import (
    STALE_CLAIM_SECONDS,
    TOOLS,
    AgentRefusedError,
    AgentRuntime,
    tool_name,
    visible_tools,
)
from berth.services.commands import Effect
from berth.services.registry import commands


def test_every_tool_is_a_registered_read_command_with_an_about() -> None:
    registry = commands()
    for name in TOOLS:
        assert name in registry, name
        assert registry[name].effect is Effect.READ, name
        assert registry[name].about, name


def test_tool_names_are_unique_and_accepted_by_both_providers() -> None:
    names = [tool_name(name) for name in TOOLS]
    assert len(set(names)) == len(names)
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) for name in names)


def test_a_user_sees_only_the_commands_meant_for_users() -> None:
    registry = commands()
    assert set(visible_tools(Role.ADMIN)) == set(TOOLS)
    assert visible_tools(Role.USER)
    assert all(registry[name].audience is Role.USER for name in visible_tools(Role.USER))


class TestOneTurnAtATime:
    """每人同時 1 輪（plan §11.6〈防護〉）。"""

    def test_a_second_turn_waits_for_the_first(self) -> None:
        runtime = AgentRuntime()
        runtime.claim(1)
        with pytest.raises(AgentRefusedError):
            runtime.claim(1)
        runtime.claim(2)
        runtime.release(1)
        runtime.claim(1)

    def test_a_claim_whose_stream_never_started_frees_itself(self) -> None:
        """佔了位子、回應卻沒送出去（commit 失敗、送出前就斷線）。

        串流的收尾不會跑，位子要自己回來。
        """
        now = [100.0]
        runtime = AgentRuntime(clock=lambda: now[0])
        runtime.claim(1)
        now[0] += STALE_CLAIM_SECONDS - 1
        with pytest.raises(AgentRefusedError):
            runtime.claim(1)
        now[0] += 2
        runtime.claim(1)

    def test_a_streaming_turn_holds_its_claim_however_long_it_runs(self) -> None:
        now = [100.0]
        runtime = AgentRuntime(clock=lambda: now[0])
        runtime.claim(1)
        runtime.streaming(1)
        now[0] += STALE_CLAIM_SECONDS * 10
        with pytest.raises(AgentRefusedError):
            runtime.claim(1)


def test_every_call_caps_its_output_and_anthropic_marks_what_to_cache() -> None:
    anthropic = chat_settings(AiProvider.ANTHROPIC, 4096)
    assert anthropic.get("max_tokens") == 4096
    assert anthropic.get("anthropic_cache_instructions") == "5m"
    assert anthropic.get("anthropic_cache_messages") == "5m"
    assert chat_settings(AiProvider.OPENAI, 4096) == {"max_tokens": 4096}
