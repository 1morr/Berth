"""e2e 的 M1 那三包怎麼送進 Berth（M4 票 79、`tests/e2e/sites.py` 的 `m1_feed`）。

送單只收搜尋或一次性連結記下的結果，所以 e2e 先把 `sites` 冒充的 acg.rip 上那一條 feed 當一次性
連結讀，再照它送。這一條 feed 要與票 79 之前直接送網址時**送進去的是同一件事**：

- 三包各一筆，發佈名是語料的 `torrent_name`（`conftest.submitted` 照它找 `source_id`）；
- 下載連結指到 `torrents` 那一台的 `<route>.torrent`；
- **沒有發佈時間**：之前送單不帶它，播出日比對照「來源沒給」略過（M3 票 14）。給一個日子的話，
  早於那一季播出的那幾包會被擋在審核，M1 那一輪就不是「不經人工入庫」（票 79 第一次跑 e2e 抓到：
  寫了 `2024-01-01`，The Bear S03 是 2024-06 播的）。
"""

from __future__ import annotations

from berth.adapters.rss.acgrip import parse_feed
from berth.domain import FeedKind
from berth.services.rss import kind_of
from tests.conftest import FIXTURES
from tests.e2e.harness import corpus
from tests.e2e.payload import PACKS
from tests.e2e.sites import M1_URL, TORRENTS, m1_feed


def test_the_m1_link_is_one_berth_reads_as_acgrip() -> None:
    assert kind_of(M1_URL) is FeedKind.ACGRIP


def test_each_pack_is_one_item_named_as_the_corpus_names_it() -> None:
    items = parse_feed(m1_feed(FIXTURES))

    assert [item.title for item in items] == [corpus(pack)["torrent_name"] for pack in PACKS]
    assert [item.torrent_url for item in items] == [
        f"{TORRENTS}/{pack.route_slug}.torrent" for pack in PACKS
    ]


def test_no_item_says_when_it_was_published() -> None:
    """說了的話播出日比對就會比（M3 票 14），而那三包的語料沒有發佈時間可以照抄。"""
    items = parse_feed(m1_feed(FIXTURES))

    assert [item.published_at for item in items] == [None] * len(PACKS)
