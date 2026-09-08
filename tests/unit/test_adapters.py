"""adapter 的純函式：錯誤分類與 Prowlarr 設定檔解析。"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from berth.adapters.http import is_dns_failure
from berth.adapters.prowlarr.config_file import API_KEY_ENV, read_api_key, read_api_key_from_config
from berth.adapters.qbittorrent import CategoryOutcome, QbittorrentCategory, ensure_category
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from tests.conftest import FIXTURES

RECORDED_CONFIG = FIXTURES / "prowlarr" / "config.xml"


def test_dns_failure_found_through_the_cause_chain() -> None:
    root = socket.gaierror(-2, "Name or service not known")
    middle = OSError("connect failed")
    middle.__cause__ = root
    top = ConnectionError("all connection attempts failed")
    top.__cause__ = middle

    assert is_dns_failure(top) is True


def test_dns_failure_found_through_the_context_chain() -> None:
    """httpcore 在 `except` 區塊裡重拋，接點是 `__context__` 不是 `__cause__`（實測）。"""
    root = socket.gaierror(-5, "No address associated with hostname")
    middle = ConnectionError("httpcore connect error")
    middle.__context__ = root
    top = ConnectionError("httpx connect error")
    top.__cause__ = middle

    assert is_dns_failure(top) is True


def test_connection_refused_is_not_a_dns_failure() -> None:
    top = ConnectionError("connection refused")
    top.__cause__ = OSError(111, "Connection refused")

    assert is_dns_failure(top) is False


def test_dns_failure_survives_a_self_referential_chain() -> None:
    """壞掉的例外鏈不該讓探測掛住。"""
    looped = ConnectionError("boom")
    looped.__cause__ = looped

    assert is_dns_failure(looped) is False


def test_api_key_read_from_the_mounted_config(tmp_path: Path) -> None:
    assert read_api_key_from_config(RECORDED_CONFIG) == "00000000000000000000000000000001"


def test_missing_config_file_reads_as_no_key(tmp_path: Path) -> None:
    assert read_api_key_from_config(tmp_path / "config.xml") == ""


def test_config_without_an_api_key_element_reads_as_no_key(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    path.write_text("<Config><Port>9696</Port></Config>", encoding="utf-8")

    assert read_api_key_from_config(path) == ""


def test_malformed_config_reads_as_no_key(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    path.write_text("<Config", encoding="utf-8")

    assert read_api_key_from_config(path) == ""


def test_environment_variable_wins_over_the_mounted_config() -> None:
    assert read_api_key(RECORDED_CONFIG, {API_KEY_ENV: "from-env"}) == "from-env"


def test_blank_environment_variable_falls_back_to_the_config() -> None:
    key = read_api_key(RECORDED_CONFIG, {API_KEY_ENV: "   "})

    assert key == "00000000000000000000000000000001"


class TestEnsureCategory:
    """`ensure_category`（plan §8.1）：不存在才建，存在但 save path 不同就回報衝突。

    為什麼不覆寫：autoTMM 開著時改 category 的 savePath 會**自動搬走該分類所有 torrent**
    （brief §20.2）。那是使用者自己的資料，Berth 不替他決定。
    """

    @pytest.mark.asyncio
    async def test_creates_the_category_when_it_is_missing(self) -> None:
        client = FakeQbittorrentClient()

        result = await ensure_category(client, "berth-tv", "/data/torrent/complete/tv")

        assert result == CategoryOutcome(
            name="berth-tv", save_path="/data/torrent/complete/tv", created=True, conflict=False
        )
        assert await client.categories() == (
            QbittorrentCategory(name="berth-tv", save_path="/data/torrent/complete/tv"),
        )

    @pytest.mark.asyncio
    async def test_leaves_a_matching_category_alone(self) -> None:
        client = FakeQbittorrentClient(
            categories=(
                QbittorrentCategory(name="berth-tv", save_path="/data/torrent/complete/tv"),
            )
        )

        result = await ensure_category(client, "berth-tv", "/data/torrent/complete/tv")

        assert result.created is False
        assert result.conflict is False
        assert client.created_categories == []

    @pytest.mark.asyncio
    async def test_a_trailing_slash_is_not_a_difference(self) -> None:
        """4.4 把設進去的路徑讀回來會多一條尾斜線（brief §20.7）。"""
        client = FakeQbittorrentClient(
            categories=(
                QbittorrentCategory(name="berth-tv", save_path="/data/torrent/complete/tv/"),
            )
        )

        result = await ensure_category(client, "berth-tv", "/data/torrent/complete/tv")

        assert result.conflict is False
        assert client.created_categories == []

    @pytest.mark.asyncio
    async def test_reports_a_different_save_path_without_touching_it(self) -> None:
        client = FakeQbittorrentClient(
            categories=(QbittorrentCategory(name="berth-tv", save_path="/mnt/old/tv"),)
        )

        result = await ensure_category(client, "berth-tv", "/data/torrent/complete/tv")

        assert result == CategoryOutcome(
            name="berth-tv", save_path="/mnt/old/tv", created=False, conflict=True
        )
        assert client.created_categories == []
