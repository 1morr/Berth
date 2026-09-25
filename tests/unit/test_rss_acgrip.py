"""acg.rip 的 RSS mapper（plan §8.5、brief §20.12、研究檔 `rss-sources.md` §4、M3 票 11）。

輸入是票 07 錄下來的兩份搜尋 feed（`tests/fixtures/http/acgrip/`）。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from berth.adapters.http import ProtocolMismatchError
from berth.adapters.rss.acgrip import parse_feed
from tests.conftest import FIXTURES

ACGRIP = FIXTURES / "http" / "acgrip"


def kimi() -> bytes:
    return (ACGRIP / "rss-search.kimi-ga-shinu.xml").read_bytes()


class TestTheSearchFeed:
    def test_every_item_comes_through_in_feed_order(self) -> None:
        items = parse_feed(kimi())

        assert len(items) == 30
        assert items[0].guid == "https://acg.rip/t/363905"

    def test_the_lolihouse_twelfth_field_by_field(self) -> None:
        """研究檔 §4 的範例那一筆（第三筆）。"""
        third = parse_feed(kimi())[2]

        assert third.title.startswith("[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头")
        assert third.guid == "https://acg.rip/t/363901"
        assert third.link == "https://acg.rip/t/363901"
        assert third.torrent_url == "https://acg.rip/t/363901.torrent"
        assert third.magnet == ""
        # acg.rip 不報 info hash：送單時由 `TorrentFetcher` 從 `.torrent` 算（plan §8.5）。
        assert third.info_hash == ""
        assert third.size == 518645760
        # `Thu, 24 Sep 2026 01:08:02 -0700`。
        assert third.published_at == datetime(2026, 9, 24, 8, 8, 2, tzinfo=UTC)

    def test_the_other_search_feed_reads_too(self) -> None:
        items = parse_feed((ACGRIP / "rss-search.kamiina-botan.xml").read_bytes())

        assert len(items) == 30
        assert all(item.torrent_url.endswith(".torrent") for item in items)


class TestNotAFeed:
    def test_an_html_page_is_a_protocol_mismatch(self) -> None:
        with pytest.raises(ProtocolMismatchError):
            parse_feed(b"<html><body>502</body></html>")
