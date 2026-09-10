"""從索引站的下載連結取得 info hash 與要交給 qBittorrent 的東西（票 09）。

**為什麼 Berth 自己取而不是把網址丟給 qBittorrent**：`jobs.hash` 是主鍵（plan §2.3），
而索引站不一定報 info hash（實測 ACG.RIP 就不報，brief §20.7）。把網址交給 qBittorrent
的話它是背景抓取——`torrents/add` 一律回 200，抓失敗時 torrent 從此不會出現，而 Berth
連「送單成功了沒」都答不出來（plan §3.1 的 `submit_failed` 因此永遠觸發不到）。
"""

from __future__ import annotations

import hashlib

import pytest

from berth.adapters.torrent import (
    NotATorrentError,
    info_hash_of,
    magnet_info_hash,
)


def bencode(value: object) -> bytes:
    """測試自己的編碼器。產品只解不編，所以這一支住在測試裡。"""
    if isinstance(value, int):
        return b"i" + str(value).encode() + b"e"
    if isinstance(value, bytes):
        return str(len(value)).encode() + b":" + value
    if isinstance(value, str):
        return bencode(value.encode())
    if isinstance(value, list):
        return b"l" + b"".join(bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        body = b"".join(bencode(key) + bencode(item) for key, item in value.items())
        return b"d" + body + b"e"
    raise TypeError(value)


INFO: dict[bytes, object] = {
    b"length": 12,
    b"name": b"Berth.Test.mkv",
    b"piece length": 16384,
    b"pieces": bytes(20),
}


def torrent(**extra: object) -> bytes:
    """一份最小的 `.torrent`。`extra` 是 `info` 之外的鍵，寫成關鍵字只是為了讀起來像 dict。"""
    payload: dict[bytes, object] = {b"announce": b"http://tracker.invalid/announce", b"info": INFO}
    payload |= {key.encode(): value for key, value in extra.items()}
    return bencode(payload)


def test_the_info_hash_is_sha1_of_the_info_dictionary() -> None:
    assert info_hash_of(torrent()) == hashlib.sha1(bencode(INFO)).hexdigest()


def test_the_hash_ignores_everything_outside_the_info_dictionary() -> None:
    """加一個 tracker 或註解不會讓它變成另一個 torrent——那正是 info hash 的定義。"""
    assert info_hash_of(torrent(comment=b"hello", created_by=b"berth")) == info_hash_of(torrent())


def test_the_info_dictionary_is_hashed_as_written_not_re_encoded() -> None:
    """**逐位元組取原文**，不是解出來再編回去。

    重編只在原檔的鍵剛好是排序的時候才等價，而 info hash 是 tracker 與 peer 認得的身分：
    差一個位元組就是另一個 torrent，而且錯了會在下載階段才發現。
    """
    # 鍵故意不照字典序寫（真實的 torrent 幾乎都照序，但規範沒有強制解碼端假設它）。
    unsorted: dict[bytes, object] = {
        b"name": b"Berth.Test.mkv",
        b"length": 12,
        b"piece length": 16384,
    }
    raw = bencode({b"info": unsorted})

    assert info_hash_of(raw) == hashlib.sha1(bencode(unsorted)).hexdigest()


def test_nested_dictionaries_and_lists_inside_info_are_scanned() -> None:
    """多檔 torrent 的 `files` 是一串 dict。掃描器要走得完才找得到 `info` 的結尾。"""
    multi: dict[bytes, object] = {
        b"name": b"Berth.Test.Pack",
        b"piece length": 16384,
        b"files": [{b"length": 1, b"path": [b"A", b"E01.mkv"]}, {b"length": 2, b"path": [b"B"]}],
    }
    raw = bencode({b"info": multi, b"announce-list": [[b"http://a.invalid"]]})

    assert info_hash_of(raw) == hashlib.sha1(bencode(multi)).hexdigest()


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"<!doctype html><title>Sign in</title>", id="an html login page"),
        pytest.param(bencode({b"announce": b"http://tracker.invalid"}), id="no info dictionary"),
        pytest.param(b"d4:infod5:name", id="truncated"),
    ],
)
def test_something_that_is_not_a_torrent_says_so(raw: bytes) -> None:
    """索引站回一頁 HTML 登入表單是真實的失敗樣子（憑證過期）。它要說得出自己不是 torrent。"""
    with pytest.raises(NotATorrentError):
        info_hash_of(raw)


def test_a_magnet_uri_carries_its_own_hash() -> None:
    uri = "magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=Berth.Test"

    assert magnet_info_hash(uri) == "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"


def test_a_base32_magnet_is_normalised_to_hex() -> None:
    """dmhy 的磁力連結寫的是 32 字 base32，Mikan 寫的是同一個 hash 的十六進位
    （brief §20.7）。不正規化的話同一個 torrent 會變成兩個 Job。"""
    uri = "magnet:?xt=urn:btih:JPIPN3Y5HMPDZOY6DNVWYKU4PWHF6CQ3"

    assert magnet_info_hash(uri) == "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"


@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("magnet:?dn=Berth.Test", id="no xt"),
        pytest.param("magnet:?xt=urn:sha1:abc", id="not a btih"),
        pytest.param("https://indexer.invalid/download/1", id="not a magnet"),
    ],
)
def test_a_magnet_without_a_usable_hash_is_empty(uri: str) -> None:
    assert magnet_info_hash(uri) == ""


def test_deep_nesting_is_not_a_torrent_rather_than_a_crash() -> None:
    """刻意做深的巢狀不該冒成 500。

    `_skip` 是遞迴的，而 `RecursionError` **不是** `_MalformedError`——沒有深度上限的話
    它會穿過 `_info_span` 的 `except` 一路往上，把「這份位元組不是 torrent」變成一次當機。
    """
    nested = b"l" * 5000 + b"e" * 5000
    raw = b"d4:info" + nested + b"e"

    with pytest.raises(NotATorrentError):
        info_hash_of(raw)
