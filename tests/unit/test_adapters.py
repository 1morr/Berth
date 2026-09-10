"""adapter 的純函式：錯誤分類與 Prowlarr 設定檔解析。"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from berth.adapters.http import is_dns_failure
from berth.adapters.prowlarr.config_file import API_KEY_ENV, read_api_key, read_api_key_from_config
from berth.adapters.qbittorrent import (
    BERTH_TAG,
    CategoryOutcome,
    QbittorrentCategory,
    QbittorrentVersion,
    TorrentAdd,
    add_form,
    ensure_category,
)
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


class TestAddTorrentForm:
    """`torrents/add` 送出去的那一份表單（plan §8.1、brief §20.7）。

    **版本判斷是必要條件不是最佳化**：2026-09-07 實測 4.4.5 只認 `paused`、5.2.3 只認
    `stopped`，而 `torrents/add` 對不認得的參數**不報錯**（一律 200 `Ok.`）。送錯的那一個
    被靜默忽略，該起跑的 torrent 就停在那裡，或該停的就開始下載——兩個方向都看不出來。
    """

    @pytest.mark.parametrize(
        ("webapi", "expected"),
        [
            pytest.param("2.8.4", "paused", id="the supported floor"),
            pytest.param("2.8.5", "paused", id="qBittorrent 4.4.5 as measured"),
            pytest.param("2.10.4", "paused", id="just below the rename"),
            pytest.param("2.11.0", "stopped", id="the version that renamed it"),
            pytest.param("2.15.1", "stopped", id="qBittorrent 5.2.3 as measured"),
        ],
    )
    def test_the_start_parameter_follows_the_web_api_version(
        self, webapi: str, expected: str
    ) -> None:
        version = QbittorrentVersion(app="v5.2.3", webapi=webapi)

        form = add_form(TorrentAdd(category="berth-tv", magnet="magnet:?xt=urn:btih:aa"), version)

        # 兩個都送也會動（各版本只認得自己那一個），但那樣就沒有人在做判斷了——
        # 下一次改名時同樣不會報錯，而擋得住它的只有一個明確的版本閘門。
        assert form[expected] == "false"
        assert ({"paused", "stopped"} - {expected}).isdisjoint(form)

    def test_berth_asks_for_the_download_to_start(self) -> None:
        """值是 `false`：qBittorrent 有一個「加入後不自動開始」的全域偏好，而 Berth 的
        狀態機（plan §3.1）假設送出去的 torrent 會自己走到 `metadata_ready`。不明講的話，
        開著那個偏好的使用者身上每一筆 Job 都會永遠停在 `submitted`。
        """
        version = QbittorrentVersion(app="v5.2.3", webapi="2.15.1")

        form = add_form(TorrentAdd(category="berth-tv", magnet="magnet:?xt=urn:btih:aa"), version)

        assert form["stopped"] == "false"

    def test_the_fixed_parameters_come_from_the_plan(self) -> None:
        version = QbittorrentVersion(app="v5.2.3", webapi="2.15.1")

        form = add_form(TorrentAdd(category="berth-tv", magnet="magnet:?xt=urn:btih:aa"), version)

        assert form["category"] == "berth-tv"
        assert form["tags"] == BERTH_TAG
        assert form["contentLayout"] == "Original"
        assert form["autoTMM"] == "true"

    def test_no_save_path_is_sent_because_the_category_owns_it(self) -> None:
        """`autoTMM=true` 時路徑由 category 決定（brief §4.1：`<complete root>/<slug>`）。
        同時送一個 `savepath` 只會讓「路徑是誰決定的」有兩個答案。"""
        version = QbittorrentVersion(app="v5.2.3", webapi="2.15.1")

        form = add_form(TorrentAdd(category="berth-tv", magnet="magnet:?xt=urn:btih:aa"), version)

        assert "savepath" not in form

    def test_a_magnet_goes_in_urls_and_a_torrent_file_does_not(self) -> None:
        version = QbittorrentVersion(app="v5.2.3", webapi="2.15.1")

        magnet = add_form(TorrentAdd(category="berth-tv", magnet="magnet:?xt=urn:btih:aa"), version)
        uploaded = add_form(TorrentAdd(category="berth-tv", content=b"d4:infod1:xi1eee"), version)

        assert magnet["urls"] == "magnet:?xt=urn:btih:aa"
        # `.torrent` 走 multipart 的檔案欄位，不是表單值——所以這裡不該有它。
        assert "urls" not in uploaded
