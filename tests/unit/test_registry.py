"""命令登錄表（M5 票 06，plan §11.6〈命令登錄表〉）：工具逐條登記、依角色過濾、統一拒絕。

斷言只走登錄表的介面：`Tool(...)` 造得出來與否、`tools_for(role)` 給了誰、`invoke(...)` 回什麼。
假工具包的是這裡定義的假命令（標了或沒標），所以不碰資料庫——`run` 不開 session。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import textwrap
from datetime import UTC, datetime
from types import ModuleType
from typing import Any, cast

import pytest
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import berth.services
from berth.domain import IssueRefusal, JobRefusal, PlanRefusal, Role, RssRefusal
from berth.main import create_app
from berth.services.access import access_of, admits
from berth.services.auth import AuthenticatedUser
from berth.services.commands import Effect, command, mark_of
from berth.services.issues import IssueRejectedError
from berth.services.jobs import JobRejectedError, actor_of, ai_actor, user_of
from berth.services.plan_review import PlanRejectedError
from berth.services.registry import (
    REJECTIONS,
    NextStep,
    Refusal,
    Registry,
    Tool,
    ToolContext,
    UnmarkedCommandError,
)
from berth.services.rss import RssRejectedError
from berth.services.tools import REGISTRY
from tests.endpoints import api_endpoints

ADMIN = AuthenticatedUser(id=1, name="skipper", role=Role.ADMIN, jellyfin_user_id="a")
DECKHAND = AuthenticatedUser(id=2, name="deckhand", role=Role.USER, jellyfin_user_id="b")
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


class Nothing(BaseModel):
    pass


class Count(BaseModel):
    days: int = Field(default=7, ge=1, le=31)


class Counted(BaseModel):
    days: int


@command(Effect.READ)
async def peek() -> None:
    """一支只讀的假命令。"""


@command(Effect.REVERSIBLE, inverse="tests.unpeek")
async def poke() -> None:
    """一支可逆的假命令。"""


async def unmarked() -> None:
    """一支沒標副作用的假命令。"""


def context(user: AuthenticatedUser = ADMIN) -> ToolContext:
    # 假工具不開 session；真的 factory 由整合測試給。
    sessions = cast(async_sessionmaker[AsyncSession], None)
    return ToolContext(sessions=sessions, user=user, now=NOW)


def tool(
    name: str = "count_days",
    *,
    target: Any = peek,
    route: tuple[str, str] = ("GET", "/jobs"),
    run: Any = None,
    **extra: Any,
) -> Tool[Any, Any]:
    async def echo(_: ToolContext, given: Count) -> Counted:
        return Counted(days=given.days)

    return Tool(
        name=name,
        description="Count days.",
        input=Count,
        result=Counted,
        command=target,
        route=route,
        run=run or echo,
        **extra,
    )


def raising(exc: Exception) -> Any:
    async def run(_: ToolContext, __: Count) -> Counted:
        raise exc

    return run


class TestRegistering:
    def test_a_command_without_a_mark_cannot_become_a_tool(self) -> None:
        with pytest.raises(UnmarkedCommandError, match="unmarked"):
            tool(target=unmarked)

    def test_effect_and_inverse_are_read_from_the_mark(self) -> None:
        registered = tool(target=poke)

        assert (registered.effect, registered.inverse) == (Effect.REVERSIBLE, "tests.unpeek")

    @pytest.mark.parametrize("name", ["", "Count Days", "count-days!", "x" * 65])
    def test_a_name_providers_would_refuse_is_refused_here(self, name: str) -> None:
        with pytest.raises(ValueError, match="tool name"):
            tool(name)

    def test_two_tools_cannot_share_a_name(self) -> None:
        with pytest.raises(ValueError, match="count_days"):
            Registry((tool(), tool()))

    def test_the_route_must_be_a_method_and_an_api_path(self) -> None:
        with pytest.raises(ValueError, match="route"):
            tool(route=("FETCH", "jobs"))


class TestTheRealRegistry:
    """全部登記都過同一組規則：等級與命令的標記一致、指著的端點真的在 app 上。"""

    @pytest.mark.parametrize("registered", list(REGISTRY), ids=lambda found: found.name)
    def test_the_effect_is_the_marks(self, registered: Tool[Any, Any]) -> None:
        mark = mark_of(registered.command)

        assert mark is not None
        assert (registered.effect, registered.inverse) == (mark.effect, mark.inverse)

    @pytest.mark.parametrize("registered", list(REGISTRY), ids=lambda found: found.name)
    def test_the_route_it_mirrors_exists(self, registered: Tool[Any, Any]) -> None:
        """工具清單照那一支端點的門禁過濾：指著一條不存在的路徑，過濾的就是一條沒人守的規則。"""
        routes = {
            (method, endpoint.path.removeprefix("/api"))
            for endpoint in api_endpoints(create_app())
            for method in endpoint.methods
        }

        assert registered.route in routes


class TestWhoGetsWhichTools:
    def registry(self) -> Registry:
        return Registry(
            (
                tool("list_jobs", route=("GET", "/jobs")),
                tool("delete_job", route=("DELETE", "/jobs/{job_hash}")),
                tool("change_settings", route=("PUT", "/settings/general")),
            )
        )

    def test_a_user_gets_no_administrator_command(self) -> None:
        names = [found.name for found in self.registry().tools_for(Role.USER)]

        assert names == ["list_jobs"]

    def test_an_administrator_gets_everything_in_registration_order(self) -> None:
        """順序固定：工具定義在 prompt 的固定前綴裡，順序一變快取就吃不到（plan §11.6）。"""
        names = [found.name for found in self.registry().tools_for(Role.ADMIN)]

        assert names == ["list_jobs", "delete_job", "change_settings"]

    @pytest.mark.parametrize("role", list(Role))
    @pytest.mark.parametrize("registered", list(REGISTRY), ids=lambda found: found.name)
    def test_the_real_list_is_the_api_gate(self, registered: Tool[Any, Any], role: Role) -> None:
        """與 API 是同一道：拿得到工具 ⇔ 門禁放那個角色進它指著的那一支端點。"""
        allowed = admits(access_of(*registered.route), role)

        assert (registered in REGISTRY.tools_for(role)) is allowed

    @pytest.mark.asyncio
    async def test_a_user_calling_an_administrator_tool_is_told_it_does_not_exist(self) -> None:
        """模型叫了清單外的名字：與真的不存在同一句，不說出「有，但你不行」。"""
        registry = self.registry()

        hidden = await registry.invoke("delete_job", {}, context(DECKHAND))
        missing = await registry.invoke("no_such_tool", {}, context(DECKHAND))

        assert hidden == Refusal(
            tool="delete_job", reason="unknown_tool", detail="", next=NextStep.GIVE_UP
        )
        assert missing.model_dump(exclude={"tool"}) == hidden.model_dump(exclude={"tool"})


@pytest.mark.asyncio
class TestInvoking:
    async def test_the_input_is_validated_and_the_result_returned(self) -> None:
        result = await Registry((tool(),)).invoke("count_days", {"days": 3}, context())

        assert result == Counted(days=3)

    async def test_bad_input_is_a_retry_that_does_not_echo_the_value(self) -> None:
        result = await Registry((tool(),)).invoke("count_days", {"days": "sk-secret"}, context())

        assert isinstance(result, Refusal)
        assert (result.reason, result.next) == ("invalid_input", NextStep.RETRY)
        assert "days" in result.detail
        assert "sk-secret" not in result.detail

    async def test_a_result_of_the_wrong_type_is_a_bug_not_a_refusal(self) -> None:
        async def wrong(_: ToolContext, __: Count) -> Nothing:
            return Nothing()

        with pytest.raises(TypeError, match="count_days"):
            await Registry((tool(run=wrong),)).invoke("count_days", {}, context())

    async def test_what_the_tool_sees_acts_for_the_person_through_the_ai(self) -> None:
        seen: list[ToolContext] = []

        async def remember(given: ToolContext, args: Count) -> Counted:
            seen.append(given)
            return Counted(days=args.days)

        await Registry((tool(run=remember),)).invoke("count_days", {}, context(DECKHAND))

        assert seen[0].actor == "ai:2"


@pytest.mark.asyncio
class TestRefusals:
    """各模組自己的拒絕在這一層變成同一種，帶下一步（plan §11.6）。模組的例外不改。"""

    @pytest.mark.parametrize(
        "exc",
        [
            IssueRejectedError(IssueRefusal.SOURCE_MISSING, "S02E01.mkv"),
            PlanRejectedError(PlanRefusal.NOT_PENDING, "plan 3"),
            RssRejectedError(RssRefusal.FEED_UNREACHABLE, "timed out"),
            JobRejectedError(JobRefusal.LOW_DISK_SPACE, "12 GB"),
        ],
        ids=lambda exc: type(exc).__name__,
    )
    async def test_a_module_rejection_becomes_one_refusal(self, exc: Any) -> None:
        result = await Registry((tool(run=raising(exc)),)).invoke("count_days", {}, context())

        assert result == Refusal(
            tool="count_days",
            reason=exc.reason.value,
            detail=exc.detail,
            next=NextStep.HAND_OVER,
        )

    async def test_the_registration_says_which_reasons_are_worth_retrying(self) -> None:
        unreachable = RssRejectedError(RssRefusal.FEED_UNREACHABLE, "timed out")
        registered = tool(
            run=raising(unreachable),
            next_steps={RssRefusal.FEED_UNREACHABLE: NextStep.RETRY},
        )

        result = await Registry((registered,)).invoke("count_days", {}, context())

        assert isinstance(result, Refusal)
        assert result.next is NextStep.RETRY

    async def test_the_same_word_from_another_module_is_not_the_reason_listed(self) -> None:
        """`JobRefusal.MEDIA_MISSING` 與 `RssRefusal.MEDIA_MISSING` 的值都是 `media_missing`。"""
        missing = RssRejectedError(RssRefusal.MEDIA_MISSING, "tv:1")
        registered = tool(
            run=raising(missing),
            next_steps={JobRefusal.MEDIA_MISSING: NextStep.RETRY},
        )

        result = await Registry((registered,)).invoke("count_days", {}, context())

        assert isinstance(result, Refusal)
        assert result.next is NextStep.HAND_OVER

    async def test_anything_else_is_a_bug_and_propagates(self) -> None:
        registered = tool(run=raising(KeyError("missing")))

        with pytest.raises(KeyError):
            await Registry((registered,)).invoke("count_days", {}, context())


def rejections_in(modules: list[ModuleType]) -> set[type[Exception]]:
    """每一個 service 模組自己定義、建構時收 `reason` 的例外：畫面據它挑句子的那一種拒絕。"""
    return {
        member
        for module in modules
        for member in vars(module).values()
        if inspect.isclass(member)
        and issubclass(member, Exception)
        and member.__module__ == module.__name__
        and "reason" in inspect.signature(member.__init__).parameters
    }


def service_modules() -> list[ModuleType]:
    return [
        importlib.import_module(f"berth.services.{found.name}")
        for found in pkgutil.iter_modules(berth.services.__path__)
    ]


def fake_module(source: str) -> ModuleType:
    module = ModuleType("berth.services.fake_rejections")
    exec(textwrap.dedent(source), module.__dict__)  # 雙向變異：載入一段假的 service 模組
    return module


class TestEveryRejectionIsTranslated:
    """新模組多了一種拒絕而登錄表不認得它，到了 AI 那一邊就是一個沒接住的例外。"""

    def test_every_service_rejection_is_in_the_table(self) -> None:
        assert rejections_in(service_modules()) - set(REJECTIONS) == set()

    def test_a_new_rejection_is_noticed(self) -> None:
        module = fake_module(
            """
            class MoorRejectedError(Exception):
                def __init__(self, reason, detail=""):
                    self.reason = reason
                    self.detail = detail
            """
        )

        assert {found.__name__ for found in rejections_in([module])} == {"MoorRejectedError"}

    def test_an_exception_without_a_reason_is_not(self) -> None:
        module = fake_module(
            """
            class ReportMissingError(LookupError):
                def __init__(self, report_id, detail=""):
                    self.report_id = report_id
            """
        )

        assert rejections_in([module]) == set()


class TestTheActor:
    """`ai:<user id>` 仍然認得出是哪一位使用者：Job 的歸屬、認領進帳本都要那個數字。"""

    @pytest.mark.parametrize(
        ("actor", "user"),
        [(ai_actor(2), 2), (actor_of(7), 7), (actor_of(None), None), ("rss:3", None)],
    )
    def test_the_person_behind_an_actor(self, actor: str, user: int | None) -> None:
        assert user_of(actor) == user
