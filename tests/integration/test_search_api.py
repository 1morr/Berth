"""搜尋端點（plan §6 search 群組、票 08 驗收）。

命令本身在 `test_search.py`；這裡驗的是形狀、參數語意與「誰進得來」——`/api/search` 沒有在
門禁的白名單上，所以匿名一律 401，而搜尋**不是**管理動作（送單本來就是一般使用者做的事，
brief §11）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from berth.adapters.indexer import IndexerResult
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import create_app
from berth.models import TmdbSettings
from berth.services.jobs import JobSource
from berth.services.routes import build_routes
from berth.services.settings import write_settings
from berth.services.setup import complete_setup
from berth.services.sources import SourceCache
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_media import MOANA as MOANA_DETAIL
from tests.integration.test_media import MOANA_ID, ORDERING, SEASONS, SPY, SPY_ID

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
#: `arrange` 寫進 `IndexerSettings` 的那一把：Prowlarr 的代理連結帶的就是它。
PROWLARR_KEY = "key-prowlarr-0"
ADMIN = {"username": "skipper", "password": "harbour"}
CREW = {"username": "deckhand", "password": "rope"}

#: 三種命名風格各一筆，形狀取自 2026-09-10 對真索引站錄下來的回應
#: （`tests/fixtures/http/prowlarr/search.*.json`）。集號改成這份 TMDB 替身涵蓋得到的範圍
#: ——絕對編號 26 在它的 episode group 上是 S02E01，所以預估那一欄才驗得出東西。
ANIME = IndexerResult(
    title=(
        "[ANi] SPY x FAMILY /  SPY×FAMILY 間諜家家酒 - 26 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]"
    ),
    indexer="ACG.RIP",
    size=524288000,
    seeders=42,
    leechers=3,
    info_hash="a" * 40,
    info_url="https://acg.rip/t/344604",
    # Prowlarr 的代理連結長這樣：帶著它自己的 API key（`arrange` 寫進設定的那一把，brief §20.7）。
    download_url=f"http://prowlarr:9696/2/download?apikey={PROWLARR_KEY}&link=bm9uY2U",
    published_at=datetime(2026, 9, 24, 13, 1, tzinfo=UTC),
)
#: 同一部作品的西方 scene 命名（形狀抄自錄下來的 The Pirate Bay 那一筆；季號改成這份
#: TMDB 替身有的那幾季）。
SCENE = IndexerResult(
    title="SPY X FAMILY S02E01 1080p WEB H264-SKYANiME",
    indexer="The Pirate Bay",
    size=1073741824,
    seeders=9,
    leechers=1,
    info_hash="b" * 40,
    # 磁力站沒有 `downloadUrl`，`magnetUrl` 一樣被包成 Prowlarr 的代理網址（brief §20.7）。
    download_url=f"http://prowlarr:9696/5/download?apikey={PROWLARR_KEY}&link=bWFnbmV0",
)
#: **The Pirate Bay 對搜不到的關鍵字會回它的熱門清單。** 這一筆是 2026-09-10 搜
#: SPY×FAMILY 時真的排在第一的那個東西——六千個做種，與這部作品毫無關係。
NOISE = IndexerResult(
    title="Spider-Man: Brand New Day 2026.1080p.HQ Pre.Multi.AAC 2.0.x264",
    indexer="The Pirate Bay",
    size=3758096384,
    seeders=6055,
    leechers=120,
    info_hash="c" * 40,
)
FILM = IndexerResult(
    title="Moana 2 (2024) 1080p WEBRip 5.1 x264 -YTS",
    indexer="YTS",
    size=2147483648,
    seeders=120,
    leechers=8,
    info_hash="d" * 40,
)


@pytest.fixture
def indexer() -> FakeIndexerSearch:
    return FakeIndexerSearch(results=(ANIME, SCENE, NOISE, FILM))


@pytest.fixture
def factory(roots: dict[str, Path], indexer: FakeIndexerSearch) -> FakeClientFactory:
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]),
            admin=(ADMIN["username"], ADMIN["password"]),
            users={CREW["username"]: CREW["password"]},
        ),
        tmdb=FakeTmdbClient(
            details=[SPY, MOANA_DETAIL],
            seasons=SEASONS,
            ordering=ORDERING,
            translations={120089: "SPY×FAMILY 間諜家家酒"},
        ),
        indexer_search=indexer,
    )


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _seed(running, roots, factory)
        yield running


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    async def run() -> None:
        # `TestClient.app` 是 Starlette 的 `ASGIApp`，型別上沒有 `state`（實際是 FastAPI）。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await write_settings(
                session,
                TmdbSettings(api_key=TMDB_API_KEY, image_base_url="https://image.tmdb.org/t/p/"),
            )
            await session.commit()
            await build_routes(session, factory, ())
            await complete_setup(session)

    asyncio.run(run())


def sign_in(client: TestClient, who: dict[str, str] = ADMIN) -> httpx.Response:
    response: httpx.Response = client.post("/api/auth/login", json=who, headers=BROWSER)
    return response


class TestGate:
    def test_search_needs_a_session(self, client: TestClient) -> None:
        assert client.get(f"/api/search?media={SPY_ID}").status_code == 401

    def test_an_ordinary_user_may_search(self, client: TestClient) -> None:
        """搜尋不是管理動作——送單本來就是一般使用者做的事（brief §11）。"""
        sign_in(client, CREW)

        assert client.get(f"/api/search?media={SPY_ID}").status_code == 200


class TestResults:
    def test_a_row_carries_every_column_the_table_shows(self, client: TestClient) -> None:
        """大小、做種、來源、Tags、預估——brief §13 列的那五樣，加上發佈時間（M3 票 14）。"""
        sign_in(client)

        body = client.get(f"/api/search?media={SPY_ID}").json()

        row = next(row for row in body["rows"] if row["indexer"] == "ACG.RIP")
        assert (row["size"], row["seeders"]) == (524288000, 42)
        assert row["info_url"] == "https://acg.rip/t/344604"
        assert row["tags"]["resolution"] == "1080p"
        assert row["tags"]["source"] == "WEB"
        assert row["tags"]["subs"] == ["CHT"]
        assert row["tags"]["group"] == "ANi"
        # 絕對編號 26 換算成 S02E01（TMDB 的 absolute episode group，brief §20.3）。
        assert (row["season"], row["episode_start"], row["episode_end"]) == (2, 1, 1)
        assert row["whole_season"] is False
        assert row["published_at"] == "2026-09-24T13:01:00Z"
        # 站沒報的那一格是 null，畫面顯示 `—`。
        scene = next(r for r in body["rows"] if r["indexer"] == "The Pirate Bay")
        assert scene["published_at"] is None
        assert body["problem"] is None

    def test_both_naming_styles_come_back_with_their_tags(self, client: TestClient) -> None:
        """中文字幕組與西方 scene 兩種命名都要解得出 Tags（plan T1.2 驗收）。"""
        sign_in(client)

        rows = {
            row["indexer"]: row for row in client.get(f"/api/search?media={SPY_ID}").json()["rows"]
        }

        assert rows["ACG.RIP"]["tags"]["subs"] == ["CHT"]
        assert rows["ACG.RIP"]["tags"]["group"] == "ANi"
        scene = rows["The Pirate Bay"]
        assert (scene["tags"]["source"], scene["tags"]["resolution"]) == ("WEB", "1080p")
        assert (scene["season"], scene["episode_start"]) == (2, 1)

    def test_the_indexers_own_popular_list_does_not_reach_the_table(
        self, client: TestClient
    ) -> None:
        """**The Pirate Bay 對搜不到的關鍵字會回它的熱門清單**（2026-09-10 實跑）。

        那些東西動輒五六千個做種，依做種排序時會把真正的結果整批擠出前 100 筆。丟掉，
        但把丟掉幾筆說出來——「索引站什麼都沒回」與「回了一堆但沒有一筆是這部作品」
        的下一步不同。
        """
        sign_in(client)

        body = client.get(f"/api/search?media={SPY_ID}").json()

        assert [row["title"] for row in body["rows"] if "Spider-Man" in row["title"]] == []
        assert body["total"] == 2
        # 電影那一筆與 Spider-Man 都不是這部作品。
        assert body["discarded"] == 2
        # 名字對上、年份與類型也對得上的不另收（M4 票 49）。
        assert (body["set_aside"], body["set_aside_total"]) == ([], 0)

    def test_a_typed_keyword_turns_the_filter_off(self, client: TestClient) -> None:
        """自己打字時他要的就是那一串字，不是這部作品——那時 Berth 沒有資格篩。"""
        sign_in(client)

        body = client.get(f"/api/search?media={SPY_ID}&q=Spider-Man").json()

        assert [row["title"] for row in body["rows"] if "Spider-Man" in row["title"]] != []
        assert body["discarded"] == 0

    def test_the_attempts_name_every_keyword_that_went_out(self, client: TestClient) -> None:
        """逐個查詢的成敗看得見——一個垮了不代表整張表是空的（票 08 驗收）。"""
        sign_in(client)

        body = client.get(f"/api/search?media={SPY_ID}").json()

        assert [attempt["status"] for attempt in body["attempts"]] == ["ok"] * len(body["attempts"])
        assert "SPY x FAMILY" in [attempt["step"] for attempt in body["attempts"]]

    def test_a_typed_keyword_replaces_the_titles(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        sign_in(client)

        client.get(f"/api/search?media={SPY_ID}&q=Spy+Family+BDRip")

        assert [query.text for query in indexer.queries] == ["Spy Family BDRip"]

    def test_the_route_only_steers_this_one_search(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        """`route` 是搜尋用的偏好：它換掉查詢變體，不寫進 `media`（票 04b、08 驗收）。"""
        sign_in(client)
        anime = next(
            row
            for row in client.get(f"/api/media/{SPY_ID}").json()["routes"]
            if row["slug"] == "anime"
        )

        client.get(f"/api/search?media={SPY_ID}&route={anime['id']}")

        assert any("Season" in query.text for query in indexer.queries)
        assert client.get(f"/api/media/{SPY_ID}").json()["problem"] is None

    def test_a_film_searches_too(self, client: TestClient) -> None:
        """電影是第三種類型，而它的結果表沒有季集——預估那一欄說的是「電影」。"""
        sign_in(client)

        body = client.get(f"/api/search?media={MOANA_ID}").json()

        assert body["problem"] is None
        assert [row["title"] for row in body["rows"]] == [FILM.title]
        assert (body["rows"][0]["strategy"], body["rows"][0]["season"]) == ("movie", None)
        assert body["rows"][0]["tags"]["resolution"] == "1080p"


class TestQueryPreview:
    """按下搜尋之前畫面要說的那句話（PRODUCT 原則 2：動手前先給看）。"""

    def test_it_lists_the_keywords_without_touching_the_indexer(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        sign_in(client)

        body = client.get(f"/api/search/queries?media={SPY_ID}").json()

        assert body["queries"][:2] == ["SPY x FAMILY", "SPY×FAMILY"]
        # 季號變體與真的搜尋同一份規則（`search_titles`），不看 Route（票 14e）。
        assert "SPY x FAMILY Season 2" in body["queries"]
        assert indexer.queries == []

    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert client.get(f"/api/search/queries?media={SPY_ID}").status_code == 401


class TestMissingEpisodes:
    """缺集一鍵搜（M1.5 票 10）：季表上的缺集直接變成查詢，規則在後端一份。

    這份替身的 SPY×FAMILY 三季都還沒有任何一集入庫，所以每一季都是「整季缺」。
    """

    def test_the_preview_lists_the_gaps_without_touching_the_indexer(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        sign_in(client)

        body = client.get(f"/api/search/queries?media={SPY_ID}&missing=true").json()

        assert body["queries"][:3] == [
            "SPY x FAMILY S00",
            "SPY x FAMILY S01",
            "SPY x FAMILY S02",
        ]
        assert indexer.queries == []

    def test_the_search_asks_exactly_what_the_preview_said(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        sign_in(client)
        preview = client.get(f"/api/search/queries?media={SPY_ID}&missing=true").json()["queries"]

        body = client.get(f"/api/search?media={SPY_ID}&missing=true").json()

        assert [query.text for query in indexer.queries] == preview
        assert [attempt["step"] for attempt in body["attempts"]] == preview

    def test_one_season_narrows_it(self, client: TestClient, indexer: FakeIndexerSearch) -> None:
        """展開區那一顆按鈕：只問那一季（shape §4）。"""
        sign_in(client)

        body = client.get(f"/api/search/queries?media={SPY_ID}&missing=true&season=2").json()

        assert body["queries"][0] == "SPY x FAMILY S02"
        assert all("S00" not in query and "S01" not in query for query in body["queries"])

    def test_a_season_without_the_missing_flag_is_refused(self, client: TestClient) -> None:
        """`season` 是「缺集搜尋收到那一季」的參數，單獨帶著沒有意義——照實拒絕，
        不要默默當成整部作品搜（那會在手改網址時搜出使用者沒有要的東西）。"""
        sign_in(client)

        refusal = client.get(f"/api/search/queries?media={SPY_ID}&season=2")

        assert refusal.status_code == 422
        assert refusal.json()["detail"]["reason"] == "season_without_missing"

    def test_a_from_season_without_the_missing_flag_is_refused(self, client: TestClient) -> None:
        """`from_season` 也是缺集搜尋的參數（M3 票 20），同一個規矩。"""
        sign_in(client)

        refusal = client.get(f"/api/search?media={SPY_ID}&from_season=6")

        assert refusal.status_code == 422
        assert refusal.json()["detail"]["reason"] == "from_season_without_missing"

    def test_the_search_says_which_batch_it_asked(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        """三季都缺、放得下一批：一共一批，沒有下一批（M3 票 20）。"""
        sign_in(client)

        body = client.get(f"/api/search?media={SPY_ID}&missing=true").json()

        assert body["batch"] == {
            "seasons": [0, 1, 2],
            "later": 0,
            "next_seasons": [],
            "next_at": None,
        }
        assert body["retry_at"] is None


class TestProblems:
    def test_an_indexer_that_was_skipped_is_not_an_error(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """第 6 步跳過時結果表要說得出下一步，不是一張空清單（票 08 驗收）。"""
        sign_in(client)
        _skip_indexer(client)

        body = client.get(f"/api/search?media={SPY_ID}").json()

        assert body["problem"] == "not_configured"
        assert body["rows"] == []

    def test_the_preview_already_says_the_indexer_was_skipped(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        """按下搜尋之前就說得出來（M2 票 13）：沒接索引站時，預覽仍列出會問的名字，但同時帶
        `not_configured`——不然使用者按下去才知道，而畫面在那之前一直說「會拿這幾個名字去問」。"""
        sign_in(client)
        _skip_indexer(client)

        body = client.get(f"/api/search/queries?media={SPY_ID}").json()

        assert body["problem"] == "not_configured"
        assert body["queries"][:2] == ["SPY x FAMILY", "SPY×FAMILY"]
        assert indexer.queries == []

    def test_a_configured_indexer_has_no_problem_in_the_preview(self, client: TestClient) -> None:
        """預覽不打索引站，所以連不上、憑證錯這幾種要按下去才知道；它只說不必問就知道的那一種。"""
        sign_in(client)

        body = client.get(f"/api/search/queries?media={SPY_ID}").json()

        assert body["problem"] is None


def _skip_indexer(client: TestClient) -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            from berth.models import SetupSettings
            from berth.services.settings import read_settings

            setup = await read_settings(session, SetupSettings)
            setup.indexer.skipped = True
            await write_settings(session, setup)
            await session.commit()

    asyncio.run(run())


class TestInfoHash:
    """`key` 是「這一列的身分」（info hash **或** guid），而送單要的是真的 hash——兩者混用的話，
    不報 hash 的站（實測 ACG.RIP）會把一條 guid 當成 hash 送出去。送單的那一份記在伺服器上
    （M4 票 79），所以這裡讀的是它記下的 hash。"""

    def test_a_row_remembers_the_indexers_info_hash_separately_from_its_key(
        self, client: TestClient
    ) -> None:
        sign_in(client)

        rows = client.get(f"/api/search?media={SPY_ID}").json()["rows"]

        row = next(row for row in rows if row["indexer"] == "ACG.RIP")
        assert remembered(client, row["source_id"]).info_hash == "a" * 40
        assert row["key"] == "a" * 40

    def test_a_site_that_reports_no_hash_leaves_it_empty(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        indexer._results = (replace(ANIME, info_hash="", guid="https://acg.rip/t/344604"),)
        sign_in(client)

        rows = client.get(f"/api/search?media={SPY_ID}").json()["rows"]

        assert remembered(client, rows[0]["source_id"]).info_hash == ""
        assert rows[0]["key"] == "https://acg.rip/t/344604"


def remembered(client: TestClient, source_id: str) -> JobSource:
    sources: SourceCache = client.app.state.sources  # type: ignore[attr-defined]  # app.state 是 Starlette 的動態屬性
    return sources.recall(source_id)


class TestTheIndexerKeyStaysOnTheServer:
    """M4 票 79：下載連結是 Prowlarr 的代理網址、帶著它的 API key，而 `/search` 一般使用者也打得到。

    連結記在伺服器上（`services/sources.py`），結果的每一列只帶一個不透明的 `source`，送單收它。
    """

    def test_an_ordinary_users_search_never_carries_the_prowlarr_key(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        # 前提：索引站真的回了帶 key 的連結，否則下面那行搜不到是理所當然。
        assert all(PROWLARR_KEY in row.download_url for row in (ANIME, SCENE))
        sign_in(client, CREW)

        response = client.get(f"/api/search?media={SPY_ID}")

        assert response.status_code == 200
        assert len(response.json()["rows"]) == 2
        assert PROWLARR_KEY not in response.text
        assert "apikey" not in response.text
        assert all("download_url" not in row for row in response.json()["rows"])

    def test_the_rows_aside_do_not_carry_it_either(
        self, client: TestClient, indexer: FakeIndexerSearch
    ) -> None:
        """收起來的那一份（M4 票 49）也是同一種列。"""
        indexer._results = (replace(SCENE, title="SPY X FAMILY 1998 1080p WEB H264-OLD"),)
        sign_in(client, CREW)

        response = client.get(f"/api/search?media={SPY_ID}")

        assert response.json()["set_aside_total"] == 1
        assert PROWLARR_KEY not in response.text

    def test_an_ordinary_user_submits_a_row_by_its_source(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """送單只帶 id；伺服器換回那一條代理連結去要 torrent，發佈名與 hash 也是它記著的那一份。"""
        sign_in(client, CREW)
        row = next(
            row
            for row in client.get(f"/api/search?media={SPY_ID}").json()["rows"]
            if row["indexer"] == "ACG.RIP"
        )
        tv = next(
            route["id"]
            for route in client.get(f"/api/media/{SPY_ID}").json()["routes"]
            if route["slug"] == "tv"
        )

        response = client.post(
            "/api/jobs",
            json={"source_id": row["source_id"], "media": SPY_ID, "route": tv},
            headers=BROWSER,
        )

        assert response.status_code == 200, response.text
        assert response.json()["job"]["name"] == ANIME.title
        # 索引站報了 hash，重複檢查拿它短路；沒有同一筆，所以照樣去要那一份 torrent。
        assert factory.torrent_.requested == [ANIME.download_url]
