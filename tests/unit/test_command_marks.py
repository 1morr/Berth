"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05 立下）。

M5 的命令登錄表要讀每一個命令的副作用等級與反向命令：可逆的 AI 自己做、不可逆的永遠要人。
登錄表本身在 M5 做，**標記現在就要標**——M3 起新增的命令一出生就帶著它，M5 不必回頭逐一猜。

這一條測試守兩件事：

1. 標了反向命令的，反向命令本身也是一個已標記的命令（寫錯名字、指到沒標的函式都紅）。
2. 每一個 service 模組裡，公開的命令函式（模組自己定義的公開 `async def`，包括被
   `asynccontextmanager` 包過的）都有標記。沒有豁免表（M5 票 05 拆掉）：新命令一出生就被守。
3. 寫到外部服務、撤不回的命令，與改設定、Route 的命令，等級是 `irreversible`（逐條列出）。

檢查本身在最後做雙向變異：以一段原始碼載成假的 service 模組，拿掉一個標記、寫錯反向命令名
會紅；改一個無關的函式名或排版不紅。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
import textwrap
from collections.abc import Callable, Iterable
from types import ModuleType

import pytest

import berth.services
from berth.services.commands import Effect, mark_of

#: 寫到外部服務、Berth 撤不回的命令（brief §16.4 物件表「在 Berth 能撤回嗎：不能」那幾列）。
#: 標成可逆的話登錄表會讓 AI 不經人就做，所以逐條鎖住等級。名單是封閉的：新命令寫到外部服務時
#: 要自己加進來（`violations` 只守「有標」，不守「標對」）。
EXTERNAL_IRREVERSIBLE = frozenset(
    {
        "ai.run_ai_test",  # 花掉的 tokens 收不回來
        "ai_calls.call_model",
        "auth.sign_in",  # Jellyfin 的裝置紀錄
        "deletion.delete_job",  # 從 qBittorrent 移除 torrent
        "indexer.add_recommended_indexers",  # Prowlarr 的站
        "indexer.apply_default_indexers",
        "indexer.remove_indexer",
        "indexer.set_interface_login",  # 介面登入：只能再設一組蓋過
        "jellyfin.add_berth_paths",  # 媒體庫上的 Berth 路徑
        "jellyfin.bootstrap_jellyfin",  # 媒體庫
        "jellyfin.claim_jellyfin",  # 管理員帳號、初始設定、API key
        "jellyfin.connect_jellyfin",  # API key
        "jellyfin.create_libraries",
        "jellyfin.resolve_interface_login",  # 同 `auth.sign_in`
        "jellyfin_access.jellyfin_access",  # 停用的帳號結束 session，同 `auth.end_sessions`
        "leftovers.remove_empty_categories",
        "notify.send_due",  # Discord 訊息送出去收不回來
        "notify.send_test",
        "qbittorrent.apply_qbittorrent",
        "qbittorrent.set_interface_login",
        "routes.build_routes",  # 新的 `berth-*` 分類（刪 Route 不刪分類）
        "routes.check_route",  # 探針觸發 qBittorrent 的「完成時執行外部程式」
        "routes.check_routes",
        "routes.create_route",
        "routes.update_route",
        "setup.choose_service",  # 換台時移除空的分類
        "setup.claim_owner",
        "setup.sign_in_existing_owner",
    }
)

#: 改設定與 Route：回得去，但 brief §14 列為「永遠要人」，plan §11.6 的登錄表直接讀標記決定出不出
#: 確認卡，所以標 `irreversible`（M5 票 05）。
SETTINGS_IRREVERSIBLE = frozenset(
    {
        "ai.set_ai",  # 清掉的 key 只寫不讀、回不來
        "deeplink.set_public_url",
        "health_issues.set_min_free",
        "notify.set_berth_url",
        "notify.set_bot_token",
        "routes.delete_route",
        "settings.update_settings",
        "settings.write_settings",
        "setup.complete_setup",
        "tmdb.verify_tmdb",
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

    `asynccontextmanager` 包過的回的是一個普通函式，裡面那一層才是 `async def`（async generator），
    所以要拆開看；`functools.wraps` 把 `__module__` 抄到外層，歸屬照樣認得出來。
    """
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and inspect.isfunction(value)
        and value.__module__ == module.__name__
        and (
            inspect.iscoroutinefunction(value) or inspect.isasyncgenfunction(inspect.unwrap(value))
        )
    }


def violations(modules: Iterable[ModuleType]) -> list[str]:
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
        for name in commands_of(module)
        if f"{short(module)}.{name}" not in marked
    ]
    return found


def not_irreversible(names: Iterable[str]) -> set[str]:
    """名單裡等級不是 `irreversible` 的（沒標、名字寫錯的也算）。"""
    found = set()
    for name in names:
        module, _, function = name.partition(".")
        mark = mark_of(commands_of(importlib.import_module(_PACKAGE + module)).get(function))
        if mark is None or mark.effect is not Effect.IRREVERSIBLE:
            found.add(name)
    return found


class TestTheServices:
    def test_every_rule_holds(self) -> None:
        assert violations(service_modules()) == []

    def test_external_writes_that_cannot_be_undone_are_irreversible(self) -> None:
        assert not_irreversible(EXTERNAL_IRREVERSIBLE) == set()

    def test_settings_and_route_changes_are_irreversible(self) -> None:
        assert not_irreversible(SETTINGS_IRREVERSIBLE) == set()

    def test_the_hand_marked_context_manager_is_seen(self) -> None:
        """`download_round` 在檢查看得到 `asynccontextmanager` 之前是手動標的（M4 票 126）。"""
        from berth.services import downloading

        assert "download_round" in commands_of(downloading)


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
async def holding(session):
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


def check(source: str) -> list[str]:
    return violations([load(source)])


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

    def test_a_removed_mark_on_a_context_manager_is_caught(self) -> None:
        source = _SOURCE.replace(
            "@command(Effect.IRREVERSIBLE)\n@asynccontextmanager", "@asynccontextmanager"
        )
        assert check(source) == ["fake.holding: public command without a mark"]

    def test_a_mark_inside_the_context_manager_still_counts(self) -> None:
        """標記貼在 `asynccontextmanager` 底下也算：`functools.wraps` 連 `__dict__` 抄到外層。"""
        source = _SOURCE.replace(
            "@command(Effect.IRREVERSIBLE)\n@asynccontextmanager",
            "@asynccontextmanager\n@command(Effect.IRREVERSIBLE)",
        )
        assert check(source) == []

    def test_a_private_context_manager_is_not_caught(self) -> None:
        source = _SOURCE.replace(
            "@command(Effect.IRREVERSIBLE)\n@asynccontextmanager", "@asynccontextmanager"
        )
        assert check(source.replace("holding", "_holding")) == []

    def test_a_misspelled_inverse_is_caught(self) -> None:
        source = _SOURCE.replace('inverse="fake.take_back"', 'inverse="fake.takeback"')
        assert check(source) == ["fake.settle: inverse fake.takeback is not a marked command"]

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


class TestTheIrreversibleList:
    """名單那一條也是雙向：等級降了、名字寫錯會紅，排版不紅。"""

    @pytest.fixture
    def install(self, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
        def put(source: str) -> None:
            monkeypatch.setitem(sys.modules, _PACKAGE + "fake", load(source))

        return put

    def test_the_untouched_module_passes(self, install: Callable[[str], None]) -> None:
        install(_SOURCE)
        assert not_irreversible({"fake.holding"}) == set()

    def test_a_lowered_effect_is_caught(self, install: Callable[[str], None]) -> None:
        install(_SOURCE.replace("@command(Effect.IRREVERSIBLE)", "@command(Effect.REVERSIBLE)"))
        assert not_irreversible({"fake.holding"}) == {"fake.holding"}

    def test_a_misspelled_name_is_caught(self, install: Callable[[str], None]) -> None:
        install(_SOURCE)
        assert not_irreversible({"fake.hold"}) == {"fake.hold"}

    def test_reformatting_is_not_caught(self, install: Callable[[str], None]) -> None:
        install(
            _SOURCE.replace(
                "@command(Effect.IRREVERSIBLE)", "@command(\n    Effect.IRREVERSIBLE\n)"
            )
        )
        assert not_irreversible({"fake.holding"}) == set()
