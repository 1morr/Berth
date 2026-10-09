"""`ProwlarrSearch` 對 `tests/fixtures/http/` 錄製回應的契約測試（票 08）。

錄製來源與日期見 `tests/fixtures/http/README.md`。驗的是「真服務回這個，adapter 解成那個」，
所以斷言貼著錄下來的值。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import respx

from berth.adapters.indexer import SearchQuery, SearchSite
from berth.adapters.indexer.prowlarr import ProwlarrSearch
from tests.conftest import read_fixture

PROWLARR_URL = "http://prowlarr:9696"
API_KEY = "00000000000000000000000000000001"
#: 錄製那台 Prowlarr 對外報的位址。下載網址由它自己組，與 Berth 打過去的位址無關。
RECORDED_HOST = "http://localhost:19696"


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_search_reads_the_columns_the_results_table_needs() -> None:
    """大小、做種、來源、發佈名、頁面連結——結果表的五欄都從這一支來（brief §13）。"""
    respx.get(f"{PROWLARR_URL}/api/v1/search").respond(
        200, text=read_fixture("http/prowlarr/search.spy-x-family.json")
    )

    search = ProwlarrSearch(PROWLARR_URL, API_KEY)
    try:
        rows = await search.search(SearchQuery(text="SPY x FAMILY"))
    finally:
        await search.aclose()

    first = rows[0]
    assert first.title.endswith("[简繁内封字幕][Fin]")
    assert first.indexer == "ACG.RIP"
    assert first.size == 5153960755
    assert first.seeders == 1
    assert first.leechers == 1
    assert first.info_url == "https://acg.rip/t/351871"
    assert first.published_at == datetime(2026, 4, 14, 14, 51, 24, tzinfo=UTC)
    # ACG.RIP 一列都不報 info hash，所以這一筆的身分只剩 guid。
    assert first.info_hash == ""
    assert first.key == "https://acg.rip/t/351871.torrent"


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_search_normalises_the_two_info_hash_spellings() -> None:
    """同一個發佈在 Mikan 是十六進位、在 dmhy 是 base32，正規化後才看得出是同一個。"""
    respx.get(f"{PROWLARR_URL}/api/v1/search").respond(
        200, text=read_fixture("http/prowlarr/search.spy-x-family.json")
    )

    search = ProwlarrSearch(PROWLARR_URL, API_KEY)
    try:
        rows = await search.search(SearchQuery(text="SPY x FAMILY"))
    finally:
        await search.aclose()

    by_indexer = {row.indexer: row for row in rows}
    assert by_indexer["Mikan"].info_hash == "4bd0f6ef8a1a55b38b7a4d4f7b10458cfa8b8d3f"
    assert by_indexer["dmhy"].info_hash == by_indexer["Mikan"].info_hash
    assert by_indexer["dmhy"].key == by_indexer["Mikan"].key


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_search_takes_the_proxy_download_url_that_qbittorrent_will_fetch() -> None:
    """磁力站沒有 `downloadUrl`，Prowlarr 把磁力也包成自己的代理網址（票 09 送的就是它）。

    網址的主機是**錄的時候那台 Prowlarr 自己的**（`localhost:19696`），不是 Berth 打過去的
    那一個——它由 Prowlarr 的 `config/host` 決定，所以原樣帶走，不重組。
    """
    respx.get(f"{PROWLARR_URL}/api/v1/search").respond(
        200, text=read_fixture("http/prowlarr/search.spy-x-family.json")
    )

    search = ProwlarrSearch(PROWLARR_URL, API_KEY)
    try:
        rows = await search.search(SearchQuery(text="SPY x FAMILY"))
    finally:
        await search.aclose()

    by_indexer = {row.indexer: row for row in rows}
    assert by_indexer["ACG.RIP"].download_url.startswith(f"{RECORDED_HOST}/2/download?")
    # dmhy 這一筆沒有 `downloadUrl`，只有被包成代理網址的 `magnetUrl`。
    assert by_indexer["dmhy"].download_url.startswith(f"{RECORDED_HOST}/6/download?")


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_search_returns_nothing_rather_than_failing_when_no_site_has_it() -> None:
    """搜不到不是錯誤：那個關鍵字在這些站上就是沒有東西（錄自真的空回應）。"""
    respx.get(f"{PROWLARR_URL}/api/v1/search").respond(
        200, text=read_fixture("http/prowlarr/search.no-results.json")
    )

    search = ProwlarrSearch(PROWLARR_URL, API_KEY)
    try:
        rows = await search.search(SearchQuery(text="zzqqxx-no-such-release-zzqqxx"))
    finally:
        await search.aclose()

    assert rows == ()


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_search_asks_only_the_sites_it_is_given() -> None:
    """試搜逐站問（票 06e）：`indexerIds` 限定那一站，一站失敗才不會拖垮其他站。"""
    route = respx.get(f"{PROWLARR_URL}/api/v1/search").respond(
        200, text=read_fixture("http/prowlarr/search.no-results.json")
    )

    search = ProwlarrSearch(PROWLARR_URL, API_KEY)
    try:
        await search.search(SearchQuery(text="", indexer_ids=(3,)))
    finally:
        await search.aclose()

    params = route.calls.last.request.url.params
    assert params.get_list("indexerIds") == ["3"]
    assert params["query"] == ""


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_search_reaches_the_sites_of_its_enabled_indexers() -> None:
    """一個查詢打到 Prowlarr 上每一個啟用中的站（M3 票 20）：請求預算以站的主機名記帳，
    與 RSS 打 `mikanani.me` 的是同一份。停用的站不算。帶著 indexer id 與名字：預算放不下的站
    這次不問，靠 `indexerIds` 只問其他站（M4 票 77）。"""
    rows = json.loads(read_fixture("http/prowlarr/indexer.defaults-added.json"))
    rows[-1]["enable"] = False  # yts
    respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(200, json=rows)

    search = ProwlarrSearch(PROWLARR_URL, API_KEY)
    try:
        sites = await search.sites()
    finally:
        await search.aclose()

    assert sites == (
        SearchSite(indexer_id=2, name="ACG.RIP", site="acg.rip"),
        SearchSite(indexer_id=6, name="dmhy", site="share.dmhy.org"),
        SearchSite(indexer_id=3, name="Mikan", site="mikanani.me"),
        SearchSite(indexer_id=5, name="The Pirate Bay", site="thepiratebay.org"),
    )


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_search_reaches_the_base_url_the_indexer_was_set_to() -> None:
    """換過 Base Url 的站（鏡像）打的是那一個，不是清單上的第一個。"""
    rows = json.loads(read_fixture("http/prowlarr/indexer.defaults-added.json"))
    tpb = next(row for row in rows if row["definitionName"] == "thepiratebay")
    base = next(field for field in tpb["fields"] if field["name"] == "baseUrl")
    base["value"] = "https://tpb.party/"
    respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(200, json=[tpb])

    search = ProwlarrSearch(PROWLARR_URL, API_KEY)
    try:
        sites = await search.sites()
    finally:
        await search.aclose()

    assert [site.site for site in sites] == ["tpb.party"]
