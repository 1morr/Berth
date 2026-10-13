"""媒體庫名 → slug（M4 票 08）：空白換成 `-`，中日文照留。

slug 同時是 qBittorrent 的分類名（`berth-<slug>`）、complete 底下的子目錄與「加入 Berth 路徑」加的
那一條，帶空白的話三處都帶空白（`berth-tv shows`、`/complete/tv shows`）。
"""

from __future__ import annotations

import json

import pytest

from berth.services.jellyfin import library_slug
from tests.conftest import FIXTURES

#: 與前端 `librarySlug` 同一份例子（`web/src/setup/newLibrary.test.ts` 讀同一個檔；
#: vite 不讓前端測試讀 `web/` 以外的檔，所以放在那邊）。
SHARED = json.loads(
    (FIXTURES.parents[1] / "web" / "src" / "setup" / "librarySlug.examples.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(("name", "slug"), SHARED["cases"])
def test_the_examples_shared_with_the_frontend(name: str, slug: str) -> None:
    """空白換成一個 `-`、中日文照留、`/` 與 Windows 不收的字元換成 `-`、全被修掉時是 `berth`。"""
    assert library_slug(name) == slug


@pytest.mark.parametrize(
    ("name", "slug"),
    [("Movies", "movies"), ("tv-zh", "tv-zh"), ("a--b", "a--b"), ("電影", "電影"), ("", "berth")],
)
def test_names_without_whitespace_keep_their_slug(name: str, slug: str) -> None:
    """沒有空白的名字算出來的與改之前一樣：已經建好的 Route、分類與 Berth 路徑都對得上。"""
    assert library_slug(name) == slug


@pytest.mark.parametrize("names", SHARED["collisions"])
def test_different_names_can_share_a_slug(names: list[str]) -> None:
    """撞名：名字不同、slug 相同（M4 票 64）。

    slug 規則不改——改了既有 Route 的分類與 Berth 路徑就對不上。撞到的由 `services.jellyfin` 擋：
    同一個資料夾不給第二個媒體庫（新建與加 Berth 路徑都是）。
    """
    assert len({library_slug(name) for name in names}) == 1
