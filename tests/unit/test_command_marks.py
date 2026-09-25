"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05 立下）。

M5 的命令登錄表要讀每一個命令的副作用等級與反向命令：可逆的 AI 自己做、不可逆的永遠要人。
登錄表本身在 M5 做，**標記現在就要標**——M3 起新增的命令一出生就帶著它，M5 不必回頭逐一猜。

這一條測試守兩件事：

1. 標了反向命令的，反向命令本身也是一個已標記的命令（寫錯名字、指到沒標的函式都紅）。
2. M3 起新增的 service 模組裡，公開的命令函式（模組自己定義的公開 `async def`）都有標記。
   「M3 之前就在」的模組列在 `BEFORE_M3`，豁免；**新模組不必登記就自動被守**。

檢查本身在最後做雙向變異：以一段原始碼載成假的 service 模組，拿掉一個標記、寫錯反向命令名
會紅；改一個無關的函式名或排版不紅。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import textwrap
from collections.abc import Iterable
from types import ModuleType

import berth.services
from berth.services.commands import Effect, mark_of

#: M3 開工前就在的 service 模組，公開命令還沒有標記（M5 做登錄表時一起補）。補完一個就從這裡
#: 拿掉；新模組不在這裡，所以一出生就被守。`review` 不在：M3 第一個新命令
#: （批次確認）落在它裡面，整個模組已經標完。
BEFORE_M3 = frozenset(
    {
        "auth",
        "bench",
        "claims",
        "clients",
        "complete",
        "deeplink",
        "deletion",
        "discover",
        "downloads",
        "duplicates",
        "events",
        "health",
        "health_issues",
        "hints",
        "importer",
        "inventory",
        "issues",
        "jellyfin",
        "jellyfin_access",
        "jellyfin_images",
        "jobs",
        "ledger_rebuild",
        "media",
        "plan",
        "plan_review",
        "plan_view",
        "qbittorrent",
        "reconcile",
        "reimport",
        "rematch",
        "resolve_schedule",
        "resolver",
        "routes",
        "search",
        "settings",
        "setup",
        "steps",
        "tmdb",
        "tracking",
        "watch",
        "watch_area",
        "watching",
    }
)

_PACKAGE = "berth.services."


def service_modules() -> list[ModuleType]:
    return [
        importlib.import_module(_PACKAGE + found.name)
        for found in pkgutil.iter_modules(berth.services.__path__)
    ]


def short(module: ModuleType) -> str:
    return module.__name__.removeprefix(_PACKAGE)


def commands_of(module: ModuleType) -> dict[str, object]:
    """模組**自己定義的**公開 `async def`。從別處 import 進來的不算它的。"""
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and inspect.iscoroutinefunction(value)
        and value.__module__ == module.__name__
    }


def violations(modules: Iterable[ModuleType], *, exempt: frozenset[str]) -> list[str]:
    """兩條規則不成立的每一處，一行一處。空的就是守住了。"""
    modules = list(modules)
    marked = {
        f"{short(module)}.{name}": mark
        for module in modules
        for name, function in commands_of(module).items()
        if (mark := mark_of(function)) is not None
    }
    found = [
        f"{name}: inverse {mark.inverse} is not a marked command"
        for name, mark in marked.items()
        if mark.inverse is not None and mark.inverse not in marked
    ]
    found += [
        f"{short(module)}.{name}: public command without a mark"
        for module in modules
        if short(module) not in exempt
        for name in commands_of(module)
        if f"{short(module)}.{name}" not in marked
    ]
    return found


class TestTheServices:
    def test_every_rule_holds(self) -> None:
        assert violations(service_modules(), exempt=BEFORE_M3) == []

    def test_every_exempt_module_still_exists(self) -> None:
        """豁免表指著不存在的模組，就是有人拆了檔案卻沒回來收這一格。"""
        assert BEFORE_M3 - {short(module) for module in service_modules()} == set()

    def test_the_batch_confirm_is_reversible_and_undone_row_by_row(self) -> None:
        """票面點名的那一個：批次確認是可逆的，反向命令是逐列撤銷。"""
        from berth.services.review import confirm_audits

        mark = mark_of(confirm_audits)
        assert mark is not None
        assert (mark.effect, mark.inverse) == (Effect.REVERSIBLE, "review.undo_audit")


# --- 雙向變異：以原始碼造一個假的 service 模組，改它，看檢查怎麼說 ---------------------------

_SOURCE = """
from berth.services.commands import Effect, command


@command(Effect.READ)
async def look(session): ...


@command(Effect.REVERSIBLE, inverse="fake.take_back")
async def settle(session, ids): ...


@command(Effect.REVERSIBLE)
async def take_back(session, id): ...


async def _helper(session): ...


def plain(value):
    return value
"""


def load(source: str) -> ModuleType:
    """把一段原始碼載成 `berth.services.fake`：`__module__` 要對，`commands_of` 才認它。"""
    module = ModuleType(_PACKAGE + "fake")
    exec(compile(textwrap.dedent(source), module.__name__, "exec"), vars(module))
    return module


def check(source: str, *, exempt: frozenset[str] = frozenset()) -> list[str]:
    return violations([load(source)], exempt=exempt)


class TestTheCheckItself:
    def test_the_untouched_module_passes(self) -> None:
        assert check(_SOURCE) == []

    def test_a_removed_mark_is_caught(self) -> None:
        source = _SOURCE.replace("@command(Effect.READ)\n", "")
        assert check(source) == ["fake.look: public command without a mark"]

    def test_a_removed_mark_on_an_inverse_is_caught_twice(self) -> None:
        """反向命令的標記拿掉了：它自己沒標，而指著它的那一個也跟著落空。"""
        source = _SOURCE.replace(
            "@command(Effect.REVERSIBLE)\nasync def take_back", "async def take_back"
        )
        assert sorted(check(source)) == [
            "fake.settle: inverse fake.take_back is not a marked command",
            "fake.take_back: public command without a mark",
        ]

    def test_a_misspelled_inverse_is_caught(self) -> None:
        source = _SOURCE.replace('inverse="fake.take_back"', 'inverse="fake.takeback"')
        assert check(source) == ["fake.settle: inverse fake.takeback is not a marked command"]

    def test_an_exempt_module_may_leave_marks_out_but_not_misname_an_inverse(self) -> None:
        source = _SOURCE.replace("@command(Effect.READ)\n", "").replace(
            'inverse="fake.take_back"', 'inverse="fake.nowhere"'
        )
        assert check(source, exempt=frozenset({"fake"})) == [
            "fake.settle: inverse fake.nowhere is not a marked command"
        ]

    def test_renaming_an_unrelated_function_is_not_caught(self) -> None:
        source = _SOURCE.replace("_helper", "_other_helper").replace("def plain", "def simple")
        assert check(source) == []

    def test_reformatting_is_not_caught(self) -> None:
        source = _SOURCE.replace(
            '@command(Effect.REVERSIBLE, inverse="fake.take_back")',
            '@command(\n    Effect.REVERSIBLE,\n    inverse="fake.take_back",\n)',
        ).replace("\n\n\n", "\n\n")
        assert check(source) == []

    def test_renaming_a_command_and_its_inverse_together_is_not_caught(self) -> None:
        source = _SOURCE.replace("take_back", "revert")
        assert check(source) == []
