"""兩個 `IndexerSearch` 實作對 `tests/fixtures/http/` 錄製回應的契約測試（票 08）。

錄製來源與日期見 `tests/fixtures/http/README.md`。驗的是「真服務回這個，adapter 解成那個」，
所以斷言貼著錄下來的值。
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from berth.adapters.indexer import SearchQuery
from berth.adapters.indexer.prowlarr import ProwlarrSearch
from berth.adapters.indexer.torznab import TorznabSearch, capability_of
from berth.adapters.torznab import TorznabCaps, TorznabSearchMode
from berth.domain import MediaKind
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


TORZNAB_URL = "http://prowlarr:9696/2/api"


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
async def test_torznab_search_reads_the_same_columns_from_xml() -> None:
    """同一張結果表，換一個協定填。錄自 Prowlarr 的單站 Torznab 網址。"""
    route = respx.get(TORZNAB_URL).respond(200, text=read_fixture("http/torznab/search.acgrip.xml"))

    search = TorznabSearch(TORZNAB_URL, API_KEY)
    try:
        rows = await search.search(SearchQuery(text="SPY x FAMILY"))
    finally:
        await search.aclose()

    first = rows[0]
    assert first.title.endswith("[简繁内封字幕][Fin]")
    assert first.indexer == "ACG.RIP"
    assert first.size == 5153960755
    assert first.seeders == 1
    # Torznab 報的是 `peers`（做種 + 下載），做種要自己扣掉才是下載中的人數。
    assert first.leechers == 1
    assert first.info_url == "https://acg.rip/t/351871"
    assert first.categories == (5000,)
    assert first.download_url.startswith(f"{RECORDED_HOST}/2/download?")
    assert dict(route.calls.last.request.url.params) == {
        "t": "search",
        "apikey": API_KEY,
        "q": "SPY x FAMILY",
    }


@respx.mock
@pytest.mark.asyncio
async def test_torznab_search_normalises_the_base32_info_hash() -> None:
    """dmhy 的 `torznab:attr infohash` 是 base32；Mikan 的同一個發佈是十六進位。"""
    respx.get(TORZNAB_URL).respond(200, text=read_fixture("http/torznab/search.dmhy.xml"))

    search = TorznabSearch(TORZNAB_URL, API_KEY)
    try:
        rows = await search.search(SearchQuery(text="SPY x FAMILY"))
    finally:
        await search.aclose()

    assert rows[0].info_hash == "4bd0f6ef8a1a55b38b7a4d4f7b10458cfa8b8d3f"


@respx.mock
@pytest.mark.asyncio
async def test_torznab_falls_back_to_q_when_caps_do_not_offer_tmdbid() -> None:
    """十個預設公開站一個都不支援 tmdbid（票 08 實測），所以 `q=` 是常態不是例外。"""
    respx.get(TORZNAB_URL).mock(
        side_effect=[
            httpx.Response(200, text=read_fixture("http/torznab/caps.xml")),
            httpx.Response(200, text=read_fixture("http/torznab/search.acgrip.xml")),
        ]
    )

    search = TorznabSearch(TORZNAB_URL, API_KEY)
    try:
        capability = await search.capabilities()
        await search.search(SearchQuery(text="SPY x FAMILY", tmdb_id=None))
    finally:
        await search.aclose()

    assert capability.searchable is True
    assert capability.tmdb_id == frozenset()


@respx.mock
@pytest.mark.asyncio
async def test_torznab_uses_tmdbid_when_the_caller_hands_one_over() -> None:
    """呼叫端只在 caps 說支援時才給 id；給了就用 id 問，不再帶關鍵字。"""
    route = respx.get(TORZNAB_URL).respond(200, text=read_fixture("http/torznab/search.acgrip.xml"))

    search = TorznabSearch(TORZNAB_URL, API_KEY)
    try:
        await search.search(SearchQuery(text="SPY x FAMILY", tmdb_id=120089, kind=MediaKind.TV))
        await search.search(SearchQuery(text="Moana 2", tmdb_id=1241982, kind=MediaKind.MOVIE))
    finally:
        await search.aclose()

    tv, movie = (dict(call.request.url.params) for call in route.calls)
    assert tv == {"t": "tvsearch", "apikey": API_KEY, "tmdbid": "120089"}
    assert movie == {"t": "movie", "apikey": API_KEY, "tmdbid": "1241982"}


@pytest.mark.asyncio
async def test_torznab_capability_reads_tmdbid_out_of_supported_params() -> None:
    """`t=caps` 的 `supportedParams` 決定得了 id 搜尋——十個公開站都沒有，私站才有。

    這一條沒有 fixture：公開站的 caps 裡根本沒有 `tmdbid`（實測 627 份定義裡 93 份支援，
    全部是 private / semiPrivate），而手寫一份「錄製回應」等於偽造證據。所以驗的是
    caps → capability 這個純函式，輸入是 caps 的**值**而不是一份假的 XML。
    """
    caps = TorznabCaps(
        server_title="Aither",
        search=TorznabSearchMode(available=True, params=frozenset({"q"})),
        tv=TorznabSearchMode(available=True, params=frozenset({"q", "season", "ep", "tmdbid"})),
        movie=TorznabSearchMode(available=True, params=frozenset({"q", "imdbid"})),
    )

    assert capability_of(caps).tmdb_id == frozenset({MediaKind.TV})
