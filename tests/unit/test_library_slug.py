"""媒體庫名 → slug（M4 票 08）：空白換成 `-`，中日文照留。

slug 同時是 qBittorrent 的分類名（`berth-<slug>`）、complete 底下的子目錄與「加入 Berth 路徑」加的
那一條，帶空白的話三處都帶空白（`berth-tv shows`、`/complete/tv shows`）。
"""

from __future__ import annotations

import pytest

from berth.services.jellyfin import library_slug


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("TV Shows", "tv-shows"),
        ("Kids  TV", "kids-tv"),
        ("Anime / Old", "anime-old"),
        ("TV: Kids ", "tv-kids"),
        ("動畫　劇集", "動畫-劇集"),
        ("電視劇（華語）", "電視劇（華語）"),
    ],
)
def test_whitespace_becomes_one_hyphen(name: str, slug: str) -> None:
    assert library_slug(name) == slug


@pytest.mark.parametrize(
    ("name", "slug"),
    [("Movies", "movies"), ("tv-zh", "tv-zh"), ("a--b", "a--b"), ("電影", "電影"), ("", "berth")],
)
def test_names_without_whitespace_keep_their_slug(name: str, slug: str) -> None:
    """沒有空白的名字算出來的與改之前一樣：已經建好的 Route、分類與 Berth 路徑都對得上。"""
    assert library_slug(name) == slug
