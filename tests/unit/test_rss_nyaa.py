"""Nyaa 的 RSS mapper（plan §8.5、brief §20.12、研究檔 `rss-sources.md` §3、M3 票 11）。

輸入是票 07 錄下來的原文（`tests/fixtures/http/nyaa/`）：搜尋 feed 與使用者 feed 是同一種格式。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from berth.adapters.http import ProtocolMismatchError
from berth.adapters.rss.nyaa import parse_feed
from tests.conftest import FIXTURES

NYAA = FIXTURES / "http" / "nyaa"


def search() -> bytes:
    return (NYAA / "rss-search.kamiina-botan.xml").read_bytes()


def user() -> bytes:
    return (NYAA / "rss-user.subsplease.kamiina-botan.xml").read_bytes()


class TestTheSearchFeed:
    def test_every_item_comes_through_in_feed_order(self) -> None:
        items = parse_feed(search())

        assert len(items) == 75
        assert items[0].title == (
            "[Doomdos] - Botan Kamiina Fully Blossoms When Drunk - 第12话 - "
            "[1080p BILIBILI COM WEB-DL]"
        )

    def test_the_first_item_field_by_field(self) -> None:
        """plan §8.5 的 Nyaa 那一欄：guid 與單集頁是 `<guid>`，`<link>` 是下載連結。"""
        first = parse_feed(search())[0]

        assert first.guid == "https://nyaa.si/view/2162858"
        assert first.link == "https://nyaa.si/view/2162858"
        assert first.torrent_url == "https://nyaa.si/download/2162858.torrent"
        assert first.magnet == ""
        assert first.info_hash == "838d9bdb7b42d8f8b94331d77489466637a64ca0"
        # `240.5 MiB`：二進位單位，一位小數。
        assert first.size == int(240.5 * 1024**2)
        # `Fri, 18 Sep 2026 03:54:17 -0000`：UTC。
        assert first.published_at == datetime(2026, 9, 18, 3, 54, 17, tzinfo=UTC)

    def test_every_item_has_a_hash_and_a_torrent(self) -> None:
        items = parse_feed(search())

        assert all(len(item.info_hash) == 40 for item in items)
        assert all(item.torrent_url.endswith(".torrent") for item in items)

    def test_a_gibibyte_size_reads_too(self) -> None:
        sizes = [item.size for item in parse_feed(search())]

        assert any(size is not None and size > 1024**3 for size in sizes)


class TestTheUserFeed:
    def test_it_is_the_same_format(self) -> None:
        items = parse_feed(user())

        assert len(items) == 39
        assert all(item.guid.startswith("https://nyaa.si/view/") for item in items)
        assert all(item.title.startswith("[SubsPlease]") for item in items)


class TestMagnetMode:
    """`&m` 開了之後 `<link>` 是 magnet（研究檔 §3.1），沒有 `.torrent` 可抓。"""

    def test_a_magnet_link_is_the_magnet_not_the_torrent(self) -> None:
        magnet = "magnet:?xt=urn:btih:838d9bdb7b42d8f8b94331d77489466637a64ca0&amp;dn=x"
        feed = search().replace(
            b"<link>https://nyaa.si/download/2162858.torrent</link>",
            f"<link>{magnet}</link>".encode(),
        )

        first = parse_feed(feed)[0]

        assert first.torrent_url == ""
        assert first.magnet.startswith("magnet:?xt=urn:btih:838d9bdb")
        assert first.link == "https://nyaa.si/view/2162858"


class TestNotAFeed:
    def test_an_html_page_is_a_protocol_mismatch(self) -> None:
        with pytest.raises(ProtocolMismatchError):
            parse_feed(b"<html><body>Cloudflare</body></html>")
