"""斜線指令的登錄表（M5 票 18）：每一個 `SlashCommand` 有一支、API 回得出它的形狀。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_args

from berth.api.agent import SlashOut, slash_out
from berth.domain import AiProvider, SlashCommand
from berth.services.slash import (
    COMMANDS,
    Compacted,
    NewConversation,
    Pending,
    Skills,
    SlashResult,
    Status,
    Usage,
)

NOW = datetime(2026, 10, 27, tzinfo=UTC)

ONE_OF_EACH: list[SlashResult] = [
    NewConversation(),
    Compacted(before=8, after=3),
    Usage(1, 0, 2, 1, 100, 20, 0, 0, 0, 0.01),
    Status(AiProvider.ANTHROPIC, "m", 2, 120, 128_000, 0.6, None),
    Pending(cards=()),
    Skills(skills=()),
]


def test_every_command_has_a_handler() -> None:
    assert set(COMMANDS) == set(SlashCommand)


def test_every_result_has_an_api_shape_named_after_its_command() -> None:
    [union, _field] = get_args(SlashOut)
    shapes = {get_args(model.model_fields["command"].annotation)[0] for model in get_args(union)}

    commands = {slash_out(result).command for result in ONE_OF_EACH}

    assert commands == shapes == {command.value for command in SlashCommand}
