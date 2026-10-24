"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05 立下）。

M5 的命令登錄表要讀每一個命令的副作用等級與反向命令：可逆的 AI 自己做、不可逆的永遠要人。
登錄表本身在 M5 做，**標記先標**——每個命令一出生就帶著它，登錄表不必回頭逐一猜。

這一條測試守兩件事：

1. 標了反向命令的，反向命令本身也是一個已標記的命令（寫錯名字、指到沒標的函式都紅）。
2. 每一個 service 模組裡，公開的命令函式（模組自己定義的公開 `async def`，包了
   `asynccontextmanager` 的、公開類別上的公開 async 方法也算）都有標記。沒有豁免表
   （M5 票 04 標完最後一批、拆掉 `BEFORE_M3`）：**新模組、新命令不必登記就被守**。

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

    公開類別的公開 async 方法也算，名字是 `<類別>.<方法>`（M5 票 04）：API 直接呼叫的寫入
    也住在類別上（`jellyfin_access.JellyfinAccess.mark_played`）。底線開頭的類別是內部零件。
    """
    found = {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and _is_async(value)
        and getattr(value, "__module__", None) == module.__name__
    }
    for class_name, owner in vars(module).items():
        if class_name.startswith("_") or not inspect.isclass(owner):
            continue
        if owner.__module__ != module.__name__:
            continue
        found |= {
            f"{class_name}.{name}": value
            for name, value in vars(owner).items()
            if not name.startswith("_") and _is_async(value)
        }
    return found


def _is_async(value: object) -> bool:
    if inspect.iscoroutinefunction(value):
        return True
    wrapped = getattr(value, "__wrapped__", None) if inspect.isfunction(value) else None
    return inspect.isasyncgenfunction(wrapped)


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


class TestTheServices:
    def test_every_rule_holds(self) -> None:
        assert violations(service_modules()) == []

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

    def test_writes_to_other_services_that_berth_cannot_take_back_are_irreversible(
        self,
    ) -> None:
        """寫到別人服務上、Berth 撤不回來的（brief §16.4 物件表「在 Berth 能撤回嗎：不能」）。

        登入 Jellyfin 留下裝置「Berth」；分類重建了就留著（刪 Route 不刪分類）；Route 檢查的探針
        校驗到 100% 會觸發使用者 qBittorrent 的「完成時執行外部程式」（brief §20.2），頁 2 的探針
        在 5.x 觸發「加入時執行」（`setup._data_sight`）。
        """
        leaves_behind = (
            "auth.sign_in",  # Jellyfin 的裝置「Berth」
            "jellyfin.resolve_interface_login",  # 同上
            "jellyfin.claim_jellyfin",  # 管理員、初始設定、API key
            "jellyfin.connect_jellyfin",  # API key
            "jellyfin.bootstrap_jellyfin",  # 媒體庫
            "jellyfin.create_libraries",  # 媒體庫
            "jellyfin.add_berth_paths",  # 媒體庫上的 Berth 路徑
            "jellyfin_access.JellyfinAccess.mark_played",  # 標為未看清掉觀看次數
            "setup.claim_owner",  # 管理員、API key
            "setup.sign_in_existing_owner",  # API key
            "setup.choose_service",  # 移除舊那一台空的分類；探針
            "setup.retest_service",  # 探針
            "qbittorrent.apply_qbittorrent",  # 介面登入
            "qbittorrent.set_interface_login",  # 同上
            "indexer.apply_default_indexers",  # Prowlarr 的站
            "indexer.add_recommended_indexers",  # 同上
            "indexer.remove_indexer",  # 移除的那一站
            "indexer.set_interface_login",  # 介面登入
            "routes.build_routes",  # 分類、探針
            "routes.create_route",  # 同上
            "routes.update_route",  # 同上
            "routes.check_route",  # 同上
            "routes.check_routes",  # 同上
            "health.check_health",  # 重建的分類
        )
        assert {name: _effect(name) for name in leaves_behind} == dict.fromkeys(
            leaves_behind, Effect.IRREVERSIBLE
        )

    def test_changing_settings_and_routes_is_irreversible(self) -> None:
        """brief §14「改設定與 Route 永遠要人」照字面標（M5 票 04 定案；票 03 的 `set_min_free`
        先這樣標，同一類的另幾支原本標可逆）。設定是管理員在設定頁或精靈上存下的值；跟著使用
        留下的偏好（`search.remember_names`）、Feed 自己的屬性（`rss.set_feed_interval`）與排除條件
        （`rss.set_exclusions`，brief §14 要 AI 寫回的記憶）不算。"""
        settings = (
            "settings.write_settings",
            "settings.update_settings",
            "setup.complete_setup",
            "jellyfin.save_bundled_libraries",
            "deeplink.set_public_url",
            "tmdb.verify_tmdb",
            "health_issues.set_min_free",
            "indexer.skip_indexers",
            "notify.set_bot_token",
            "notify.set_mine",
            "notify.set_berth_url",
            "routes.delete_route",
        )
        assert {name: _effect(name) for name in settings} == dict.fromkeys(
            settings, Effect.IRREVERSIBLE
        )
        for name in settings:
            mark = mark_of(_command(name))
            assert mark is not None and mark.inverse is None, name


def _command(name: str) -> object:
    """`"<模組>.<函式>"` 或 `"<模組>.<類別>.<方法>"`。"""
    module, *path = name.split(".")
    found: object = importlib.import_module(_PACKAGE + module)
    for part in path:
        found = getattr(found, part)
    return found


def _effect(name: str) -> Effect | None:
    mark = mark_of(_command(name))
    return None if mark is None else mark.effect


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


class Access:
    @command(Effect.IRREVERSIBLE)
    async def write(self, item): ...

    async def _peek(self): ...


class _Part:
    async def run(self): ...
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

    def test_a_misspelled_inverse_is_caught(self) -> None:
        source = _SOURCE.replace('inverse="fake.take_back"', 'inverse="fake.takeback"')
        assert check(source) == ["fake.settle: inverse fake.takeback is not a marked command"]

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

    def test_a_removed_mark_on_a_method_is_caught(self) -> None:
        """公開類別上的公開 async 方法是命令；底線開頭的方法與類別不是。"""
        source = _SOURCE.replace(
            "    @command(Effect.IRREVERSIBLE)\n    async def write", "    async def write"
        )
        assert check(source) == ["fake.Access.write: public command without a mark"]

    def test_renaming_an_unrelated_function_is_not_caught(self) -> None:
        source = (
            _SOURCE.replace("_helper", "_other_helper")
            .replace("def plain", "def simple")
            .replace("_peek", "_glance")
            .replace("class _Part", "class _Piece")
        )
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
