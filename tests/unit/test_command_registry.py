"""命令登錄表（M5 票 06，plan §11.6〈分段〉第 2 段）：AI 的工具、確認卡、M7 的 MCP 讀同一份清單。

守三件事：

1. 登錄表列得出每一個非 `INTERNAL` 的命令，欄位齊（名稱、輸入模型、結果型別、拒絕理由、Effect、
   inverse、旗標、說明、`validate`）；注入的依賴不進輸入模型。
2. 閘門：每一個有標記、非 `INTERNAL` 的命令都推得出輸入模型（`collect` 沒有失敗）。
3. 閘門本身的雙向變異：以一段原始碼載成假的 service 模組，收 ORM 列的命令會紅；改無關的函式名、
   改排版、把它標成 `INTERNAL` 不紅。
"""

from __future__ import annotations

import textwrap
from types import ModuleType

import pytest
from pydantic import BaseModel, ValidationError

from berth.domain import JobRefusal, RssRefusal
from berth.services import registry
from berth.services.commands import Effect, Flag, command, mark_of
from berth.services.downloading import add_manual_download
from berth.services.jobs import AddDownloadOutcome
from berth.services.rss import FeedView, add_feed
from tests.unit.test_command_marks import commands_of, service_modules, short


class TestTheListing:
    def test_a_command_carries_every_field(self) -> None:
        spec = registry.commands()["rss.add_feed"]

        assert spec.name == "rss.add_feed"
        assert spec.function is add_feed
        assert spec.result is FeedView
        assert spec.effect is Effect.REVERSIBLE
        assert spec.inverse == "rss.delete_feed"
        assert spec.flags == {Flag.CONNECTS_OUT, Flag.SETTINGS}
        assert spec.needs_person
        assert spec.refusals == (RssRefusal,)
        assert spec.about
        assert spec.validate is not None

    def test_the_input_model_is_the_signature_without_what_the_server_injects(self) -> None:
        spec = registry.commands()["downloading.add_manual_download"]

        assert spec.function is add_manual_download
        assert spec.result is AddDownloadOutcome
        assert set(spec.input.model_fields) == {"source", "media_id", "route_id"}
        assert set(spec.injected) == {"session", "factory", "user_id"}
        assert spec.refusals == (JobRefusal,)

    def test_the_input_model_validates_and_keeps_the_defaults(self) -> None:
        spec = registry.commands()["rss.add_feed"]

        parsed = spec.input.model_validate({"url": "https://mikanani.me/RSS/MyBangumi?token=x"})

        assert isinstance(parsed, BaseModel)
        assert parsed.model_dump() == {
            "url": "https://mikanani.me/RSS/MyBangumi?token=x",
            "name": "",
            "tv_route_id": None,
            "movie_route_id": None,
            "exclusions": (),
            "interval_sec": 900,
        }
        with pytest.raises(ValidationError):
            spec.input.model_validate({"url": "x", "interval_sec": "often"})

    def test_the_input_model_has_a_json_schema_for_the_model(self) -> None:
        schema = registry.commands()["rss.subscribe_mikan"].input.model_json_schema()

        assert set(schema["required"]) == {"bangumi_id", "subgroup_id", "media_id", "route_id"}
        assert "user_id" not in schema["properties"]
        assert "now" not in schema["properties"]

    def test_every_marked_command_but_the_internal_ones_is_listed(self) -> None:
        expected = {
            f"{short(module)}.{name}"
            for module in service_modules()
            for name, function in commands_of(module).items()
            if (mark := mark_of(function)) is not None and Flag.INTERNAL not in mark.flags
        }

        assert set(registry.commands()) == expected
        assert len(expected) > 100

    def test_internal_commands_are_not_listed(self) -> None:
        listed = registry.commands()

        assert "rss.poll_due" not in listed
        assert "jobs.add_download" not in listed
        assert "auth.sign_in" not in listed

    def test_a_command_without_a_validator_says_so(self) -> None:
        spec = registry.commands()["rss.list_feeds"]

        assert spec.validate is None
        assert spec.about == ""
        assert spec.refusals == ()
        assert not spec.needs_person


class TestTheGate:
    def test_every_marked_command_registers(self) -> None:
        """推不出輸入模型的（收 ORM 列、收函式、`*args`）要改成 `INTERNAL` 或改簽名。"""
        _, failures = registry.collect(service_modules())

        assert failures == []

    def test_every_validated_command_declares_its_refusals(self) -> None:
        listed = registry.commands().values()

        assert [spec.name for spec in listed if spec.validate and not spec.refusals] == []


_SOURCE = """
from collections.abc import Callable

from berth.models import Route
from berth.services.commands import Effect, Flag, command
from sqlalchemy.ext.asyncio import AsyncSession


@command(Effect.READ)
async def look(session: AsyncSession, route_id: int, *, actor: str) -> int:
    return route_id


@command(Effect.READ, flags={Flag.INTERNAL})
async def inside(session: AsyncSession, route: Route) -> int:
    return route.id


async def _helper(session: AsyncSession, route: Route) -> None: ...
"""


def load(source: str) -> ModuleType:
    module = ModuleType("berth.services.fake")
    exec(compile(textwrap.dedent(source), module.__name__, "exec"), vars(module))
    return module


def check(source: str) -> tuple[list[str], list[str]]:
    found, failures = registry.collect([load(source)])
    return sorted(found), failures


class TestTheGateItself:
    def test_the_untouched_module_passes(self) -> None:
        assert check(_SOURCE) == (["fake.look"], [])

    def test_a_command_taking_a_row_is_caught(self) -> None:
        source = _SOURCE.replace("route_id: int, *", "route: Route, *")

        found, failures = check(source)

        assert found == []
        assert len(failures) == 1
        assert failures[0].startswith("fake.look: ")

    def test_a_command_taking_star_args_is_caught(self) -> None:
        source = _SOURCE.replace("route_id: int, *, actor: str", "*ids: int")

        assert check(source)[1][0].startswith("fake.look: ")

    def test_a_command_taking_a_function_is_caught(self) -> None:
        source = _SOURCE.replace("route_id: int, *", "pick: Callable[[int], int], *")

        found, failures = check(source)

        assert found == []
        assert failures[0].startswith("fake.look: ")

    def test_a_validator_taking_what_the_input_lacks_is_caught(self) -> None:
        source = _SOURCE.replace(
            "@command(Effect.READ)\n",
            "async def _can(session: AsyncSession, *, route: int) -> None: ...\n\n\n"
            "@command(Effect.READ, refusals=(Flag,), validate=_can)\n",
        )
        assert check(source)[1] == ["fake.look: validate takes what the input lacks: ['route']"]
        assert check(source.replace("route: int)", "route_id: int)")) == (["fake.look"], [])

    def test_taking_a_row_inside_an_internal_command_is_not_caught(self) -> None:
        assert check(_SOURCE)[1] == []
        source = _SOURCE.replace(
            "@command(Effect.READ)\n", "@command(Effect.READ, flags={Flag.INTERNAL})\n"
        )
        assert check(source) == ([], [])

    def test_renaming_and_reformatting_are_not_caught(self) -> None:
        source = (
            _SOURCE.replace("_helper", "_other")
            .replace("look", "glance")
            .replace("route_id: int, *, actor: str", "route_id: int,\n    *,\n    actor: str,\n")
        )
        assert check(source) == (["fake.glance"], [])


class TestTheMarks:
    def test_a_validator_needs_its_refusals(self) -> None:
        async def check_it(session: object) -> None: ...

        with pytest.raises(ValueError, match="refusals"):
            command(Effect.REVERSIBLE, validate=check_it)

    def test_an_internal_command_has_nothing_for_the_model(self) -> None:
        with pytest.raises(ValueError, match="internal"):
            command(Effect.READ, flags={Flag.INTERNAL}, about="not a tool")
