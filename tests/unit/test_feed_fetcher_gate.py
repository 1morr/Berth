"""命令模組抓 RSS 一律走 `services.clients.feed_fetcher`（M3 票 20）。

`factory.rss()` 給的是沒有記帳的 fetcher：直接呼叫它就繞過了一個站一份的請求預算，而那一站照樣被打。
這裡掃 `berth/services/` 每一個模組的語法樹，`.rss()` 的呼叫只准出現在 `clients.py`（`feed_fetcher`
本身）。最後以兩段原始碼做雙向變異：直接呼叫會紅；換行、改名、呼叫別的同名屬性不紅。
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import berth.services

SERVICES = Path(berth.services.__file__).parent
#: 唯一准許呼叫 `.rss()` 的模組：`feed_fetcher` 住在這裡。
ALLOWED = frozenset({"clients.py"})


def bypasses(source: str) -> list[int]:
    """這段原始碼裡不帶參數呼叫 `<任何東西>.rss()` 的行號。"""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "rss"
        and not node.args
        and not node.keywords
    ]


def test_no_service_module_fetches_rss_around_the_budget() -> None:
    found = {
        path.name: lines
        for path in sorted(SERVICES.glob("*.py"))
        if path.name not in ALLOWED and (lines := bypasses(path.read_text(encoding="utf-8")))
    }

    assert found == {}


class TestTheCheckItself:
    def test_a_direct_call_is_caught(self) -> None:
        source = textwrap.dedent(
            """
            async def poll(factory):
                fetcher = factory.rss()
                return await fetcher.fetch("https://mikanani.me/RSS/MyBangumi")
            """
        )

        assert bypasses(source) == [3]

    def test_layout_and_names_do_not_trip_it(self) -> None:
        source = textwrap.dedent(
            """
            async def poll(clients):
                fetcher = feed_fetcher(
                    clients,
                    BudgetUse.POLL,
                )
                settings.rss_url()
                return await fetcher.fetch(clients.rss_)
            """
        )

        assert bypasses(source) == []
