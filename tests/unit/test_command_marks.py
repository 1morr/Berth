"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05 立下）。

M5 的命令登錄表要讀每一個命令的副作用等級與反向命令：可逆的 AI 自己做、不可逆的永遠要人。
登錄表本身在 M5 做，**標記現在就要標**——M3 起新增的命令一出生就帶著它，M5 不必回頭逐一猜。

這一條測試守兩件事：

1. 標了反向命令的，反向命令本身也是一個已標記的命令（寫錯名字、指到沒標的函式都紅）。
2. M3 起新增的 service 模組裡，公開的命令函式（模組自己定義的公開 `async def`，包了
   `asynccontextmanager` 的也算）都有標記。
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

#: M3 開工前就在的 service 模組，公開命令還沒有標記（M5 票 03、04 補）。補完一個就從這裡
#: 拿掉；新模組不在這裡，所以一出生就被守。`review` 不在：M3 第一個新命令
#: （批次確認）落在它裡面，整個模組已經標完。
BEFORE_M3 = frozenset(
    {
        "auth",
        "bench",
        "clients",
        "deeplink",
        "discover",
        "downloads",
        "events",
        "health",
        "hints",
        "jellyfin",
        "jellyfin_access",
        "jellyfin_images",
        "qbittorrent",
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
    """模組**自己定義的**公開 `async def`。從別處 import 進來的不算它的。

    包了一層 `asynccontextmanager` 的也算（`downloading.download_round`）：外層是普通函式，
    `functools.wraps` 留下的 `__wrapped__` 才是那個 `async def`。
    """
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and _is_async(value)
        and getattr(value, "__module__", None) == module.__name__
    }


def _is_async(value: object) -> bool:
    if inspect.iscoroutinefunction(value):
        return True
    wrapped = getattr(value, "__wrapped__", None) if inspect.isfunction(value) else None
    return inspect.isasyncgenfunction(wrapped)


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

    def test_confirming_an_audit_has_no_single_way_back(self) -> None:
        """確認可逆（brief §14），但沒有一支命令把它撤回來（M5 票 03 改掉 M3 票 05 的標法）。

        `review.undo_audit` 不是它的反向：撤銷拆掉的是入庫，不是確認；而且它拒絕確認過的列
        （`not_audited`）。旗標掛不回去，但確認錯了的那個檔案照樣改得動：rematch 改落點，或刪除。
        """
        from berth.services.review import confirm_audit, confirm_audits

        for confirm in (confirm_audit, confirm_audits):
            mark = mark_of(confirm)
            assert mark is not None
            assert (mark.effect, mark.inverse) == (Effect.REVERSIBLE, None)

    def test_deleting_a_feed_is_irreversible(self) -> None:
        """Feed Item 跟著刪（CASCADE）：加回同一個網址只長得出那一站現在還列著的，更早的紀錄與
        每一筆排除、預覽過的結論都回不來。所以不是 `add_feed` 撤得回的。"""
        from berth.services.rss import delete_feed

        mark = mark_of(delete_feed)
        assert mark is not None
        assert (mark.effect, mark.inverse) == (Effect.IRREVERSIBLE, None)

    def test_the_unattended_rss_round_is_irreversible_but_the_button_is_not(self) -> None:
        """`poll_due` 是 `rss_poller` 的一輪：沒有人在場，送出的「正在下載」排給每一位訂閱者
        （`downloading.download_round`），送出去收不回來——同其他背景迴圈的入口
        （`sweep.sweep_once`、`resolver.sweep_resolutions`）。人按的「立即輪詢」（`poll_feed`）
        照手動送單的標法看主效果（`downloading.add_manual_download`）。"""
        from berth.services.rss import poll_due, poll_feed

        due, pressed = mark_of(poll_due), mark_of(poll_feed)
        assert due is not None and pressed is not None
        assert (due.effect, pressed.effect) == (Effect.IRREVERSIBLE, Effect.REVERSIBLE)


# --- 雙向變異：以原始碼造一個假的 service 模組，改它，看檢查怎麼說 ---------------------------

_SOURCE = """
from contextlib import asynccontextmanager

from berth.services.commands import Effect, command


@command(Effect.READ)
async def look(session): ...


@command(Effect.REVERSIBLE, inverse="fake.take_back")
async def settle(session, ids): ...


@command(Effect.REVERSIBLE)
async def take_back(session, id): ...


@command(Effect.IRREVERSIBLE)
@asynccontextmanager
async def round_of(session):
    yield


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

    def test_a_removed_mark_on_a_context_manager_is_caught(self) -> None:
        """包了一層 `asynccontextmanager` 就不是 coroutine function，但它照樣是公開命令。"""
        source = _SOURCE.replace(
            "@command(Effect.IRREVERSIBLE)\n@asynccontextmanager", "@asynccontextmanager"
        )
        assert check(source) == ["fake.round_of: public command without a mark"]

    def test_a_mark_under_the_context_manager_is_seen(self) -> None:
        """標在 `asynccontextmanager` 裡面也算：`functools.wraps` 把屬性帶到外層。"""
        source = _SOURCE.replace(
            "@command(Effect.IRREVERSIBLE)\n@asynccontextmanager",
            "@asynccontextmanager\n@command(Effect.IRREVERSIBLE)",
        )
        assert check(source) == []

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
