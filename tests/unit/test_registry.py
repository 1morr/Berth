"""命令登錄表（M5 票 05，plan §11.6〈命令登錄表〉）：工具逐條登記、依角色過濾、統一拒絕。

斷言只走登錄表的介面：`Tool(...)` 造得出來與否、`tools_for(role)` 給了誰、`resolve(...)` 之後
`run` / `preview` / `apply` 回什麼。假工具包的是這裡定義的假命令（標了或沒標），所以不碰資料庫——
`run` 不開 session。
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
from berth.domain import IssueRefusal, JobRefusal, PlanRefusal, ProposalCause, Role, RssRefusal
from berth.main import create_app
from berth.services.access import access_of, admits
from berth.services.auth import AuthenticatedUser
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command, mark_of
from berth.services.issues import IssueRejectedError
from berth.services.jobs import JobRejectedError, actor_of, ai_actor, user_of
from berth.services.plan_review import PlanRejectedError
from berth.services.registry import (
    REJECTIONS,
    NextStep,
    ProposalInput,
    Refusal,
    Registry,
    Tool,
    ToolContext,
    ToolRefusal,
    Undo,
    UnmarkedCommandError,
    cause_of,
)
from berth.services.rss import RssRejectedError
from berth.services.sources import SourceCache
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


def context(user: AuthenticatedUser = ADMIN, *, confirmed: bool = False) -> ToolContext:
    # 假工具不開 session、不連服務；真的由整合測試給。
    sessions = cast(async_sessionmaker[AsyncSession], None)
    clients = cast(ServiceClientFactory, None)
    return ToolContext(
        sessions=sessions,
        clients=clients,
        sources=SourceCache(),
        user=user,
        now=NOW,
        confirmed=confirmed,
    )


async def invoke(
    registry: Registry, name: str, arguments: dict[str, object], given: ToolContext
) -> BaseModel:
    """直接做的那一條：`resolve` 之後 `run`。"""
    call = registry.resolve(name, arguments, given.user)
    if isinstance(call, Refusal):
        return call
    return await registry.run(call, given)


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


@command(Effect.IRREVERSIBLE)
async def scuttle() -> None:
    """一支不可逆的假命令。"""


class Scuttle(ProposalInput):
    ship: str


class Scuttling(BaseModel):
    ship: str


async def plan_scuttle(_: ToolContext, given: Scuttle) -> Scuttling:
    return Scuttling(ship=given.ship)


async def do_scuttle(_: ToolContext, given: Scuttle, shown: Scuttling) -> Scuttling:
    return shown


def proposed(**extra: Any) -> Tool[Any, Any]:
    """一個要人按的假工具（M5 票 10）：預覽說出要鑿沉哪一艘，執行照人看到的那一份。"""
    fields: dict[str, Any] = {
        "name": "scuttle",
        "description": "Scuttle a ship.",
        "input": Scuttle,
        "result": Scuttling,
        "command": scuttle,
        "route": ("DELETE", "/jobs/{job_hash}"),
        "preview": plan_scuttle,
        "preview_type": Scuttling,
        "apply": do_scuttle,
    }
    return Tool(**(fields | extra))


class TestToolsThatNeedAPerson:
    """不可逆的工具 AI 自己做不了，在登記的形狀上就是這樣（M5 票 10）。"""

    def test_an_irreversible_tool_cannot_be_run_directly(self) -> None:
        async def run(_: ToolContext, given: Scuttle) -> Scuttling:
            return Scuttling(ship=given.ship)

        with pytest.raises(ValueError, match="no run"):
            proposed(run=run)

    def test_an_irreversible_tool_says_what_would_happen(self) -> None:
        with pytest.raises(ValueError, match="preview"):
            proposed(preview=None, preview_type=None, apply=None)

    def test_preview_and_apply_come_together(self) -> None:
        with pytest.raises(ValueError, match="together"):
            proposed(apply=None)

    def test_an_irreversible_tool_asks_for_a_reason(self) -> None:
        with pytest.raises(ValueError, match="ProposalInput"):
            proposed(input=Count)

    def test_a_reversible_tool_is_run(self) -> None:
        with pytest.raises(ValueError, match="needs run"):
            Tool(
                name="poke",
                description="Poke.",
                input=Count,
                result=Counted,
                command=poke,
                route=("GET", "/jobs"),
            )

    @pytest.mark.asyncio
    async def test_an_irreversible_call_always_needs_a_person(self) -> None:
        registered = proposed()

        assert await cause_of(registered, context(), Scuttle(ship="Pinafore", reason="x")) is (
            ProposalCause.IRREVERSIBLE
        )

    @pytest.mark.asyncio
    async def test_a_reversible_call_is_done_unless_a_check_demotes_it(self) -> None:
        """降級的入口：可逆的工具在某些呼叫上要人按（票 11 的網址來源接這裡，要讀對話所以是
        async）。"""

        async def from_the_user(_: ToolContext, given: Count) -> ProposalCause | None:
            return ProposalCause.IRREVERSIBLE if given.days > 7 else None

        async def plan(_: ToolContext, given: Count) -> Counted:
            return Counted(days=given.days)

        async def do(_: ToolContext, given: Count, shown: Counted) -> Counted:
            return shown

        plain = tool(target=poke)
        checked = tool(
            target=poke, demote=from_the_user, preview=plan, preview_type=Counted, apply=do
        )

        assert await cause_of(plain, context(), Count(days=30)) is None
        assert await cause_of(checked, context(), Count(days=3)) is None
        assert await cause_of(checked, context(), Count(days=30)) is ProposalCause.IRREVERSIBLE

    def test_a_tool_that_can_be_demoted_says_what_would_happen(self) -> None:
        async def never(_: ToolContext, __: Count) -> None:
            return None

        with pytest.raises(ValueError, match="demoted"):
            tool(target=poke, demote=never)


@command(Effect.REVERSIBLE, inverse="tests.unit.test_registry.unnudge")
async def nudge() -> None:
    """可逆、反向命令是 `unnudge`。"""


@command(Effect.IRREVERSIBLE)
async def unnudge() -> None:
    """`nudge` 的反向命令。"""


class Uncounted(BaseModel):
    days: int


async def take_back(_: ToolContext, done: Counted) -> Uncounted:
    return Uncounted(days=done.days)


class TestUndo:
    """結果卡上的撤銷走命令標著的反向命令（M5 票 11），不另寫一套。"""

    def test_the_undo_calls_the_marked_inverse(self) -> None:
        undone = tool(
            target=nudge,
            undo=Undo(command=unnudge, route=("GET", "/jobs"), run=take_back, result=Uncounted),
        )

        assert undone.undo is not None and undone.inverse == "tests.unit.test_registry.unnudge"

    def test_an_undo_through_another_command_is_refused(self) -> None:
        with pytest.raises(ValueError, match="inverse"):
            tool(
                target=nudge,
                undo=Undo(command=scuttle, route=("GET", "/jobs"), run=take_back, result=Uncounted),
            )

    def test_only_a_reversible_tool_has_an_undo(self) -> None:
        with pytest.raises(ValueError, match="only a reversible"):
            tool(
                target=peek,
                undo=Undo(command=unnudge, route=("GET", "/jobs"), run=take_back, result=Uncounted),
            )

    @pytest.mark.asyncio
    async def test_it_is_run_on_the_stored_result_and_a_stale_shape_is_changed(self) -> None:
        undone = tool(
            target=nudge,
            undo=Undo(command=unnudge, route=("GET", "/jobs"), run=take_back, result=Uncounted),
        )
        registry = Registry((undone,))

        assert await registry.undo(undone, context(), {"days": 3}) == Uncounted(days=3)
        stale = await registry.undo(undone, context(), {"weeks": 3})
        assert isinstance(stale, Refusal) and stale.reason == ToolRefusal.CHANGED

    @pytest.mark.asyncio
    async def test_preview_then_apply_what_was_shown(self) -> None:
        registry = Registry((proposed(),))
        call = registry.resolve("scuttle", {"ship": "Pinafore", "reason": "x"}, ADMIN)
        assert not isinstance(call, Refusal)

        shown = await registry.preview(call, context())
        done = await registry.apply(call, context(confirmed=True), Scuttling(ship="Shown"))

        assert shown == Scuttling(ship="Pinafore")
        assert done == Scuttling(ship="Shown")

    @pytest.mark.asyncio
    async def test_a_rejection_in_the_preview_is_a_refusal(self) -> None:
        async def refuse(_: ToolContext, __: Scuttle) -> Scuttling:
            raise JobRejectedError(JobRefusal.JOB_MISSING, "abc")

        registry = Registry((proposed(preview=refuse),))
        call = registry.resolve("scuttle", {"ship": "Pinafore", "reason": "x"}, ADMIN)
        assert not isinstance(call, Refusal)

        assert await registry.preview(call, context()) == Refusal(
            tool="scuttle", reason="job_missing", detail="abc", next=NextStep.HAND_OVER
        )

    def test_a_confirmed_call_is_the_person_not_the_ai(self) -> None:
        assert context(DECKHAND).actor == "ai:2"
        assert context(DECKHAND, confirmed=True).actor == "2"


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

        hidden = await invoke(registry, "delete_job", {}, context(DECKHAND))
        missing = await invoke(registry, "no_such_tool", {}, context(DECKHAND))

        assert hidden == Refusal(
            tool="delete_job", reason="unknown_tool", detail="", next=NextStep.GIVE_UP
        )
        assert missing.model_dump(exclude={"tool"}) == hidden.model_dump(exclude={"tool"})


@pytest.mark.asyncio
class TestInvoking:
    async def test_the_input_is_validated_and_the_result_returned(self) -> None:
        result = await invoke(Registry((tool(),)), "count_days", {"days": 3}, context())

        assert result == Counted(days=3)

    async def test_bad_input_is_a_retry_that_does_not_echo_the_value(self) -> None:
        result = await invoke(Registry((tool(),)), "count_days", {"days": "sk-secret"}, context())

        assert isinstance(result, Refusal)
        assert (result.reason, result.next) == ("invalid_input", NextStep.RETRY)
        assert "days" in result.detail
        assert "sk-secret" not in result.detail

    async def test_a_result_of_the_wrong_type_is_a_bug_not_a_refusal(self) -> None:
        async def wrong(_: ToolContext, __: Count) -> Nothing:
            return Nothing()

        with pytest.raises(TypeError, match="count_days"):
            await invoke(Registry((tool(run=wrong),)), "count_days", {}, context())

    async def test_what_the_tool_sees_acts_for_the_person_through_the_ai(self) -> None:
        seen: list[ToolContext] = []

        async def remember(given: ToolContext, args: Count) -> Counted:
            seen.append(given)
            return Counted(days=args.days)

        await invoke(Registry((tool(run=remember),)), "count_days", {}, context(DECKHAND))

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
        result = await invoke(Registry((tool(run=raising(exc)),)), "count_days", {}, context())

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

        result = await invoke(Registry((registered,)), "count_days", {}, context())

        assert isinstance(result, Refusal)
        assert result.next is NextStep.RETRY

    async def test_the_same_word_from_another_module_is_not_the_reason_listed(self) -> None:
        """`JobRefusal.MEDIA_MISSING` 與 `RssRefusal.MEDIA_MISSING` 的值都是 `media_missing`。"""
        missing = RssRejectedError(RssRefusal.MEDIA_MISSING, "tv:1")
        registered = tool(
            run=raising(missing),
            next_steps={JobRefusal.MEDIA_MISSING: NextStep.RETRY},
        )

        result = await invoke(Registry((registered,)), "count_days", {}, context())

        assert isinstance(result, Refusal)
        assert result.next is NextStep.HAND_OVER

    async def test_anything_else_is_a_bug_and_propagates(self) -> None:
        registered = tool(run=raising(KeyError("missing")))

        with pytest.raises(KeyError):
            await invoke(Registry((registered,)), "count_days", {}, context())


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


class TestTheDispatcherItself:
    """三支派發照它們跑得到的最壞的那一種登記標（M5 票 04 起閘門看得到類別上的方法）。"""

    @pytest.mark.parametrize(
        ("method", "effect"),
        [
            # 只有讀取與可逆的工具有 `run`。
            (Registry.run, Effect.REVERSIBLE),
            (Registry.preview, Effect.READ),
            # 加索引站、刪 complete 從這裡做。
            (Registry.apply, Effect.IRREVERSIBLE),
        ],
        ids=["run", "preview", "apply"],
    )
    def test_each_dispatcher_is_marked_as_bad_as_what_it_reaches(
        self, method: Any, effect: Effect
    ) -> None:
        mark = mark_of(method)

        assert mark is not None
        assert (mark.effect, mark.inverse) == (effect, None)


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
