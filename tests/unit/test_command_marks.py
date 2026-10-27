"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05 立下）。

M5 的命令登錄表要讀每一個命令的副作用等級與反向命令：可逆的 AI 自己做、不可逆的永遠要人。
登錄表本身在 M5 做，**標記現在就要標**——M3 起新增的命令一出生就帶著它，M5 不必回頭逐一猜。

這一條測試守三件事：

1. 標了反向命令的，反向命令本身也是一個已標記的命令（寫錯名字、指到沒標的函式都紅）。
2. M3 起新增的 service 模組裡，公開的命令函式（模組自己定義的公開 `async def`，含
   `@asynccontextmanager` 包過的）都有標記。「M3 之前就在」的模組列在 `BEFORE_M3`，豁免；
   **新模組不必登記就自動被守**。
3. `NAMED` 裡判斷過的標記（M5 票 02、03）沒被悄悄改掉。

標記自己矛盾的（只讀卻送單、不可逆卻有反向命令）不在這裡：`CommandMark` 建的那一刻就丟，
見 `test_command_flags.py`。

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

import pytest

import berth.services
from berth.services.commands import CommandMark, Effect, Flag, mark_of

#: M3 開工前就在的 service 模組，公開命令還沒有標記。補完一個就從這裡拿掉；新模組不在這裡，
#: 所以一出生就被守。M5 票 03 清掉管線、媒體庫與審核那一批，剩下的是票 03b 那一批，它清完就
#: 整張刪掉。
BEFORE_M3 = frozenset(
    {
        "auth",
        "bench",
        "clients",
        "deeplink",
        "discover",
        "health",
        "health_issues",
        "jellyfin",
        "jellyfin_access",
        "jellyfin_images",
        "qbittorrent",
        "routes",
        "search",
        "settings",
        "setup",
        "tmdb",
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


def is_async_def(value: object) -> bool:
    """`async def` 寫的：coroutine function，或 async generator（含 `@asynccontextmanager` 包過的，
    它回的是一個普通函式，`__wrapped__` 才是那個 generator——M5 票 02 補的漏洞 R2）。"""
    if not inspect.isfunction(value):
        return False
    inner = inspect.unwrap(value)
    return inspect.iscoroutinefunction(inner) or inspect.isasyncgenfunction(inner)


def commands_of(module: ModuleType) -> dict[str, object]:
    """模組**自己定義的**公開 `async def`。從別處 import 進來的不算它的。"""
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_") and is_async_def(value) and value.__module__ == module.__name__
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


def _mark(effect: Effect, *flags: Flag, inverse: str | None = None) -> CommandMark:
    return CommandMark(effect, inverse=inverse, flags=frozenset(flags))


#: 有人判斷過、不能悄悄改掉的標記（M5 票 02：研究 A3 的 R3–R6，與照同一把尺找到的其他命令）。
#: 改這裡要有理由：它們決定 AI 能不能自己做（`needs_person`）。
NAMED: dict[str, CommandMark] = {
    # R3：撤銷會拆入庫、把 Job 拉回 review，不是確認的反向。
    "review.confirm_audit": _mark(Effect.REVERSIBLE),
    "review.confirm_audits": _mark(Effect.REVERSIBLE),
    # R4：背景迴圈的入口；刪 Feed 連 Item 一起刪。
    "rss.poll_due": _mark(Effect.REVERSIBLE, Flag.INTERNAL, Flag.DOWNLOADS),
    "rss.delete_feed": _mark(Effect.IRREVERSIBLE, Flag.SETTINGS),
    # R5：送出 torrent 的。
    "rss.release_item": _mark(Effect.REVERSIBLE, Flag.DOWNLOADS),
    "rss.bind_series": _mark(Effect.REVERSIBLE, Flag.DOWNLOADS, inverse="rss.unbind_series"),
    "rss.poll_feed": _mark(Effect.REVERSIBLE, Flag.DOWNLOADS),
    "rss.prime_feed": _mark(Effect.IRREVERSIBLE, Flag.DOWNLOADS),
    "rss.subscribe_mikan": _mark(Effect.REVERSIBLE, Flag.DOWNLOADS),
    "rss.set_feed_routes": _mark(Effect.REVERSIBLE, Flag.SETTINGS, Flag.DOWNLOADS),
    "downloading.add_manual_download": _mark(Effect.REVERSIBLE, Flag.DOWNLOADS),
    # R6：改設定的。
    "notify.set_bot_token": _mark(Effect.REVERSIBLE, Flag.SETTINGS, inverse="notify.set_bot_token"),
    "notify.set_berth_url": _mark(Effect.REVERSIBLE, Flag.SETTINGS, inverse="notify.set_berth_url"),
    "notify.set_mine": _mark(Effect.REVERSIBLE, Flag.SETTINGS, inverse="notify.set_mine"),
    "indexer.apply_default_indexers": _mark(Effect.REVERSIBLE, Flag.SETTINGS),
    "indexer.add_recommended_indexers": _mark(Effect.REVERSIBLE, Flag.SETTINGS),
    "indexer.skip_indexers": _mark(
        Effect.REVERSIBLE, Flag.SETTINGS, inverse="indexer.skip_indexers"
    ),
    "indexer.remove_indexer": _mark(
        Effect.REVERSIBLE, Flag.SETTINGS, inverse="indexer.apply_default_indexers"
    ),
    "indexer.set_interface_login": _mark(
        Effect.REVERSIBLE, Flag.SETTINGS, inverse="indexer.set_interface_login"
    ),
    "qbittorrent.set_interface_login": _mark(
        Effect.REVERSIBLE, Flag.SETTINGS, inverse="qbittorrent.set_interface_login"
    ),
    "search.remember_names": _mark(
        Effect.REVERSIBLE, Flag.SETTINGS, inverse="search.remember_names"
    ),
    "rss.add_feed": _mark(
        Effect.REVERSIBLE, Flag.CONNECTS_OUT, Flag.SETTINGS, inverse="rss.delete_feed"
    ),
    "rss.set_feed_interval": _mark(
        Effect.REVERSIBLE, Flag.SETTINGS, inverse="rss.set_feed_interval"
    ),
    "rss.set_exclusions": _mark(Effect.REVERSIBLE, Flag.SETTINGS),
    "rss.set_feed_exclusions": _mark(Effect.REVERSIBLE, Flag.SETTINGS),
    "rss.set_series_exclusions": _mark(Effect.REVERSIBLE, Flag.SETTINGS),
    # 對外發訊息的，與不當工具的背景那幾支（研究 05 觀察 5）。
    "notify.send_test": _mark(Effect.IRREVERSIBLE, Flag.SENDS_OUT),
    "notify.queue_ready": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "notify.watch_waiting": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "notify.queue_lingering": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "notify.send_due": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "downloading.download_round": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "downloading.queue_downloading": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "sweep.sweep_once": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "weekly.compose_weekly": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    "leftovers.remove_empty_categories": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SETTINGS),
    "first_batch.confirm_by_batch": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    # 讀的：送出去的只有查詢，不建任何東西（M4 票 09、06e）。
    "indexer.search_indexers": _mark(Effect.READ),
    "indexer.verify_sites": _mark(Effect.READ),
    # 帶著 key 連到傳進來的位址：只給健康檢查用。
    "indexer.probe_indexer": _mark(Effect.READ, Flag.INTERNAL, Flag.CONNECTS_OUT),
    # M5 票 03：要人的。刪檔、移除 torrent；忽略會把問題藏起來，而且沒有命令收回（brief §14）。
    "deletion.delete_job": _mark(Effect.IRREVERSIBLE),
    "issues.ignore_issue": _mark(Effect.IRREVERSIBLE),
    # brief §14 列為可逆、AI 可以自己做的：核准與改寫計劃、rematch、重試、重新入庫。
    "plan_review.approve_plan": _mark(Effect.REVERSIBLE),
    "plan_review.edit_items": _mark(Effect.REVERSIBLE),
    "plan_review.reject_plan": _mark(Effect.REVERSIBLE),
    "plan.replan_job": _mark(Effect.REVERSIBLE),
    "rematch.rematch_file": _mark(Effect.REVERSIBLE),
    "duplicates.decide_duplicate": _mark(Effect.REVERSIBLE),
    "reimport.reimport_job": _mark(Effect.REVERSIBLE),
    "jobs.retry_job": _mark(Effect.REVERSIBLE, Flag.DOWNLOADS),
    # 送 torrent 的底層一支：工具是 `downloading.add_manual_download`，這支只給別的命令叫。
    "jobs.add_download": _mark(Effect.REVERSIBLE, Flag.INTERNAL, Flag.DOWNLOADS),
    "jobs.retry_due": _mark(Effect.REVERSIBLE, Flag.INTERNAL, Flag.DOWNLOADS),
    "jobs.resubmit_job": _mark(Effect.REVERSIBLE, Flag.INTERNAL, Flag.DOWNLOADS),
    # 背景迴圈與啟動的入口。
    "downloads.poll_downloads": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    "importer.sweep_imports": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    "plan.sweep_plans": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    "reconcile.reconcile_once": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    "jobs.fail_interrupted": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    # 排「可以看了」的通知，同 `sweep.sweep_once`。
    "resolver.sweep_resolutions": _mark(Effect.IRREVERSIBLE, Flag.INTERNAL, Flag.SENDS_OUT),
    # 詳情頁的讀：快照是 TMDB 的快取，過期順手重抓不算改東西。按「重新整理」就是要換標題與
    # `folder_name`，算改。
    "media.read_media": _mark(Effect.READ),
    "media.refresh_media": _mark(Effect.REVERSIBLE),
    # Issue 的按鈕（M5 票 04，研究 A3 的 R8、C1）：刪東西的、放棄追蹤的要人（忽略在上面）；
    # 修復的可逆，送出 torrent 的那一顆帶 `downloads`。
    "issues.relink": _mark(Effect.REVERSIBLE),
    "issues.forget": _mark(Effect.IRREVERSIBLE),
    "issues.delete_complete": _mark(Effect.IRREVERSIBLE),
    "issues.mark_sourceless": _mark(Effect.IRREVERSIBLE),
    "issues.replace_with_link": _mark(Effect.IRREVERSIBLE),
    "issues.delete_orphan": _mark(Effect.IRREVERSIBLE),
    "issues.replan": _mark(Effect.REVERSIBLE),
    "issues.relook": _mark(Effect.REVERSIBLE),
    "issues.rescan": _mark(Effect.REVERSIBLE),
    "issues.recheck": _mark(Effect.REVERSIBLE),
    "issues.retry": _mark(Effect.REVERSIBLE),
    "issues.accept_loss": _mark(Effect.IRREVERSIBLE),
    "issues.accept_removal": _mark(Effect.IRREVERSIBLE),
    "issues.resubmit": _mark(Effect.REVERSIBLE, Flag.DOWNLOADS),
    "issues.reimport": _mark(Effect.REVERSIBLE),
    "issues.claim_torrent": _mark(Effect.REVERSIBLE),
    "issues.claim_file": _mark(Effect.REVERSIBLE),
    "issues.record_issue": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    "issues.close_settled": _mark(Effect.REVERSIBLE, Flag.INTERNAL),
    "issues.list_issues": _mark(Effect.READ),
}


class TestTheServices:
    def test_every_rule_holds(self) -> None:
        assert violations(service_modules(), exempt=BEFORE_M3) == []

    def test_every_exempt_module_still_exists(self) -> None:
        """豁免表指著不存在的模組，就是有人拆了檔案卻沒回來收這一格。"""
        assert BEFORE_M3 - {short(module) for module in service_modules()} == set()

    @pytest.mark.parametrize(("name", "expected"), list(NAMED.items()), ids=list(NAMED))
    def test_a_named_command_is_marked_as_decided(self, name: str, expected: CommandMark) -> None:
        module, function = name.split(".")
        found = getattr(importlib.import_module(_PACKAGE + module), function)
        assert mark_of(found) == expected


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

    def test_a_removed_mark_on_an_async_context_manager_is_caught(self) -> None:
        """R2：`@asynccontextmanager` 包過的不是 coroutine function，以前不標也不紅。"""
        source = _SOURCE.replace(
            "@command(Effect.IRREVERSIBLE)\n@asynccontextmanager", "@asynccontextmanager"
        )
        assert check(source) == ["fake.round_of: public command without a mark"]

    def test_a_removed_mark_on_an_async_generator_is_caught(self) -> None:
        source = _SOURCE.replace("@command(Effect.IRREVERSIBLE)\n@asynccontextmanager\n", "")
        assert check(source) == ["fake.round_of: public command without a mark"]

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
