"""Mikan 的 RSS mapper（plan §8.5、brief §20.12、M3 票 08）。

輸入全是票 07 錄下來的原文（`tests/fixtures/http/mikan/`），不是手寫的 payload。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime

import pytest

from berth.adapters.http import ProtocolMismatchError
from berth.adapters.rss.mikan import (
    MikanBangumi,
    bangumi_page,
    bangumi_url,
    parse_feed,
    published_at,
    series_key,
)
from tests.conftest import FIXTURES, read_fixture

MIKAN = FIXTURES / "http" / "mikan"

#: 喵萌奶茶屋&LoliHouse《与你相恋到生命尽头》第 12 集——聚合 feed 的第一筆。
EP12_HASH = "85c93c23143bbeb98f9c0895d31ab18ceeed4090"


def mybangumi() -> bytes:
    return (MIKAN / "rss-mybangumi.xml").read_bytes()


class TestTheAggregatedFeed:
    def test_every_item_comes_through_in_feed_order(self) -> None:
        items = parse_feed(mybangumi())

        assert len(items) == 12
        assert items[0].guid == EP12_HASH

    def test_the_dedup_key_is_the_info_hash_not_the_title_guid(self) -> None:
        """Mikan 的 `<guid>` 就是標題（brief §20.12）——字幕組改標題就變，不能拿來去重。"""
        first = parse_feed(mybangumi())[0]

        assert first.guid == first.info_hash == EP12_HASH
        assert "Kimi ga Shinu made Koi wo Shitai" in first.title
        assert first.guid not in first.title

    def test_the_torrent_and_the_episode_page_come_from_the_enclosure_and_the_link(self) -> None:
        first = parse_feed(mybangumi())[0]

        assert first.torrent_url == (f"https://mikanani.me/Download/20260924/{EP12_HASH}.torrent")
        assert first.link == f"https://mikanani.me/Home/Episode/{EP12_HASH}"

    def test_the_size_comes_from_the_description_not_the_content_length(self) -> None:
        """`contentLength` 不是位元組（研究檔 §2.4）；描述結尾的 `[518.65 MB]` 是十進位的 MB。"""
        first = parse_feed(mybangumi())[0]

        assert first.size == int(518.65 * 1000**2)
        assert first.magnet == ""

    def test_every_hash_is_lower_case_hex(self) -> None:
        assert all(len(item.info_hash) == 40 for item in parse_feed(mybangumi()))
        assert all(item.info_hash == item.info_hash.lower() for item in parse_feed(mybangumi()))

    def test_the_single_feed_is_the_same_format(self) -> None:
        items = parse_feed((MIKAN / "rss-bangumi.4009-370.xml").read_bytes())

        assert len(items) == 12
        assert all(item.torrent_url.endswith(".torrent") for item in items)


class TestPublishedAt:
    """`<torrent><pubDate>` 不帶時區、實際是 UTC+8（brief §20.11、票 08 的驗收）。"""

    def test_it_is_read_as_utc_plus_eight_and_stored_as_utc(self) -> None:
        first = parse_feed(mybangumi())[0]

        # 原文 `2026-09-24T16:08:01.389`。
        assert first.published_at == datetime(2026, 9, 24, 8, 8, 1, 389000, tzinfo=UTC)

    def test_it_agrees_with_acg_rip_on_the_same_release(self) -> None:
        """同一個發佈在 acg.rip 是 `Thu, 24 Sep 2026 01:08:02 -0700`（研究檔 §5）。

        當成 UTC 讀的話兩邊差 8 小時；照 UTC+8 讀差不到一秒（發佈工具幾乎同時貼到兩站）。
        """
        acgrip = read_fixture("http/acgrip/rss-search.kimi-ga-shinu.xml")
        assert "Thu, 24 Sep 2026 01:08:02 -0700" in acgrip
        there = parsedate_to_datetime("Thu, 24 Sep 2026 01:08:02 -0700")

        here = parse_feed(mybangumi())[0].published_at

        assert here is not None
        assert abs(here - there) < timedelta(seconds=1)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026-09-24T13:11:00", datetime(2026, 9, 24, 5, 11, tzinfo=UTC)),
            ("2026-09-24T21:01:00.760219", datetime(2026, 9, 24, 13, 1, 0, 760219, tzinfo=UTC)),
            # 哪天 Mikan 寫出帶時區的值，就照它寫的讀。
            ("2026-09-24T13:11:00+00:00", datetime(2026, 9, 24, 13, 11, tzinfo=UTC)),
        ],
    )
    def test_zero_three_and_six_fraction_digits_all_read(
        self, raw: str, expected: datetime
    ) -> None:
        assert published_at(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "yesterday"])
    def test_what_it_cannot_read_is_none(self, raw: object) -> None:
        assert published_at(raw) is None


class TestNotAFeed:
    def test_an_html_page_is_a_protocol_mismatch_not_an_empty_feed(self) -> None:
        """登入頁或錯誤頁回 200 時，「這週沒更新」與「網址錯了」要分得開。"""
        with pytest.raises(ProtocolMismatchError):
            parse_feed((MIKAN / "home-episode.85c93c23.html").read_bytes())

    def test_a_feed_with_no_items_is_just_empty(self) -> None:
        empty = b'<rss version="2.0"><channel><title>Mikan</title></channel></rss>'

        assert parse_feed(empty) == ()


class TestSeriesKey:
    def test_the_episode_page_gives_the_bangumi_and_the_subgroup(self) -> None:
        page = read_fixture("http/mikan/home-episode.85c93c23.html")

        assert series_key(page) == (4009, 370)

    def test_a_page_without_the_rss_link_gives_nothing(self) -> None:
        assert series_key("<html><a href='/RSS/Classic'>rss</a></html>") is None

    def test_only_the_mikan_rss_link_counts(self) -> None:
        """同一頁的別處也可能連到 `/RSS/Bangumi`；認的是 `a.mikan-rss` 那一顆。"""
        page = (
            '<a href="/RSS/Bangumi?bangumiId=1&subgroupid=2">other</a>'
            '<a class="x mikan-rss" href="/RSS/Bangumi?bangumiId=4009&amp;subgroupid=370">rss</a>'
        )

        assert series_key(page) == (4009, 370)


class TestBangumiPage:
    """番組頁的中文名與「放送开始」（研究檔 §2.7，票 09 自動綁定的線索）。"""

    def test_the_title_and_the_premiere_come_from_the_desktop_block(self) -> None:
        page = read_fixture("http/mikan/home-bangumi.4009.html")

        assert bangumi_page(page) == MikanBangumi(
            title="与你相恋到生命尽头", premiere=date(2026, 7, 7)
        )

    def test_the_premiere_is_month_first(self) -> None:
        """`7/6/2026` 是 7 月 6 日：番組頁寫的星期對得上 M/D，對不上 D/M（研究檔 §2.7）。"""
        page = '<p class="bangumi-title">X</p><p class="bangumi-info">放送开始：7/6/2026</p>'

        assert bangumi_page(page).premiere == date(2026, 7, 6)

    @pytest.mark.parametrize(
        "info",
        [
            "",
            '<p class="bangumi-info">放送开始：</p>',
            '<p class="bangumi-info">放送开始：13/40/2026</p>',
        ],
    )
    def test_a_missing_or_unreadable_premiere_is_none(self, info: str) -> None:
        assert bangumi_page(f'<p class="bangumi-title">X</p>{info}').premiere is None

    def test_a_page_without_a_title_gives_an_empty_title(self) -> None:
        assert bangumi_page("<html></html>") == MikanBangumi(title="", premiere=None)

    def test_the_page_address_is_built_from_the_bangumi_id(self) -> None:
        assert bangumi_url(4009) == "https://mikanani.me/Home/Bangumi/4009"
