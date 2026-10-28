"""側面板的兩個動漫情境，用假模型從頭走到尾（M5 票 16、plan §11.6〈分段〉第 6 段）。

模型是 `FakeAi` 的腳本（`test_agent_api.Script`），不打網路：

- AniList、Bangumi 用**真的 adapter**，回應是錄下來的 fixture（`respx` 攔 `httpx`；
  TestClient 走 `httpx2`，不會被它攔到）。閘門與快取各測試自己一份、時鐘是假的，沒有東西真的在等。
- TMDB、索引站、Mikan 是替身。Mikan 的兩頁是錄下來的**別部作品**（搜尋頁是葬送的芙莉莲、番組頁是
  4009），測試只看流程與守法，不看那兩頁的內容。

情境 1「這季有什麼好看的新番」：skill → 季表 + 放送表 → 使用者挑 → 找 TMDB → 找 Mikan → 確認卡。
情境 2「Re:Zero 全系列」（票 23d 起不走 AniList 與 Fribb）：skill → 找 TMDB → 讀作品（季集表與
播出區段）→ 搜種子 → 總覽卡。各季的集數表來自網搜，替身模型演不出來，由真模型的實跑量
（`agent_sources_ab.py`）。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo

from berth.adapters.anilist import API_URL
from berth.adapters.anilist.client import HttpAniList, Throttle
from berth.adapters.bgm import API_URL as BGM_URL
from berth.adapters.bgm.client import HttpBgm
from berth.adapters.indexer import IndexerResult
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.rss.mikan import bangumi_feed_url, bangumi_url, search_url
from berth.adapters.tmdb import TmdbDetail, TmdbEntry, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.ttl import TtlCache
from berth.config import Config
from berth.domain import MediaKind
from berth.services.agent_tools import EXTERNAL_TOOLS
from tests.conftest import FIXTURES, read_fixture
from tests.integration.arrange import sign_in_crew
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import Script, call, chat, recorded, say
from tests.integration.test_agent_cards import (
    berth_services,
    cards,
    route_of,
    running_berth,
)

MIKAN = FIXTURES / "http" / "mikan"

# ---------------------------------------------------------------- 安排：外部服務


class FakeTime:
    """單調時鐘 + 記下來的 sleep：`sleep` 把時鐘往前推，就像真的睡過去（同 AniList 的契約測試）。"""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@dataclass
class AniListServer:
    """錄下來的 AniList：照請求的 `query` 與 `variables` 找回應，並記下每一次問了什麼。"""

    answers: dict[str, httpx.Response] = field(default_factory=dict)
    asked: list[dict[str, Any]] = field(default_factory=list)

    def load(self, *names: str) -> None:
        for name in names:
            recorded_ = json.loads(read_fixture(f"http/anilist/{name}.json"))
            sent = recorded_["request"]
            self.answers[self.key(sent["query"], sent["variables"])] = httpx.Response(
                recorded_["status"], json=recorded_["body"], headers=recorded_["headers"]
            )

    @staticmethod
    def key(query: str, variables: dict[str, Any]) -> str:
        return json.dumps([query, variables], sort_keys=True)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        self.asked.append(sent["variables"])
        found = self.answers.get(self.key(sent["query"], sent["variables"]))
        # 沒錄過的問題：測試的腳本問了不該問的，回 404 讓它當場紅。
        return found if found is not None else httpx.Response(404, json={"errors": []})


@dataclass
class Outside:
    """動漫資料來源的錄製回應，加上 `respx` 的路由。"""

    router: respx.MockRouter
    anilist: AniListServer
    bgm: respx.Route


@pytest.fixture
def outside(tmp_path: Path) -> Iterator[Outside]:
    anilist = AniListServer()
    anilist.load("season.fall-2026")
    with respx.mock(assert_all_called=False) as router:
        router.post(API_URL).mock(side_effect=anilist)
        bgm = router.get(f"{BGM_URL}/calendar").mock(
            return_value=httpx.Response(
                200,
                json=json.loads(read_fixture("http/bgm/calendar.json"))["body"],
                headers={"cache-control": "max-age=3600"},
            )
        )
        yield Outside(router, anilist, bgm)


def anime_sources(factory: FakeClientFactory, tmp_path: Path) -> None:
    """換上真的 adapter：每個測試自己的閘門（假時鐘）與快取。"""
    time_ = FakeTime()
    factory.anilist_ = HttpAniList(
        throttle=Throttle(clock=time_.time, sleep=time_.sleep),
        cache=TtlCache(ttl=60, size=64, clock=time_.time),
    )
    factory.bgm_ = HttpBgm(cache=TtlCache(ttl=60, size=4, clock=time_.time))


# ---------------------------------------------------------------- 安排：TMDB、索引站、Mikan

EDGERUNNERS_ID = "tv:105248"
REZERO_ID = "tv:65942"
STARFALL_ID = "tv:900001"
STARFALL_EPISODES = 14
#: Re:Zero 在 TMDB 第 1 季的五輪：（第一集、集數、開播日）。合計 85 集，各輪之間隔好幾個月。
REZERO_COURS = (
    (1, 25, date(2016, 4, 4)),
    (26, 13, date(2020, 7, 8)),
    (39, 12, date(2021, 1, 6)),
    (51, 16, date(2024, 10, 2)),
    (67, 19, date(2026, 4, 8)),
)


def tv(tmdb_id: int, title: str, original: str, year: int, *seasons: TmdbSeasonEntry) -> TmdbDetail:
    return TmdbDetail(
        tmdb_id=tmdb_id,
        kind=MediaKind.TV,
        title=title,
        original_title=original,
        year=year,
        first_air_date=date(year, 1, 1),
        overview="",
        poster_path="",
        titles=(title, original),
        seasons=seasons,
    )


def season_entry(number: int, episodes: int, year: int) -> TmdbSeasonEntry:
    return TmdbSeasonEntry(
        season_number=number, name=f"Season {number}", episode_count=episodes,
        air_date=date(year, 1, 1),
    )  # fmt: skip


def season_rows(number: int, episodes: int, year: int) -> TmdbSeason:
    return TmdbSeason(
        season_number=number,
        name=f"Season {number}",
        air_date=date(year, 1, 1),
        episodes=tuple(
            TmdbEpisode(
                season_number=number,
                episode_number=n,
                name=f"Episode {n}",
                air_date=date(year, 1, 1),
                runtime=24,
            )
            for n in range(1, episodes + 1)
        ),
    )


def arrange_tmdb(factory: FakeClientFactory) -> None:
    """Edgerunners（挑的那部）在 TMDB 上的樣子。"""
    tmdb = factory.tmdb_
    edgerunners = tv(
        105248, "Cyberpunk: Edgerunners", "サイバーパンク エッジランナーズ", 2022,
        season_entry(1, 10, 2022), season_entry(2, 10, 2026),
    )  # fmt: skip
    tmdb.details[(edgerunners.kind, edgerunners.tmdb_id)] = edgerunners
    rezero = tv(
        65942, "Re:ZERO -Starting Life in Another World-", "Re:ゼロから始める異世界生活", 2016,
        season_entry(1, 85, 2016),
    )  # fmt: skip
    tmdb.details[(rezero.kind, rezero.tmdb_id)] = rezero
    tmdb.season_rows[(65942, 1)] = TmdbSeason(
        season_number=1,
        name="Season 1",
        air_date=date(2016, 4, 4),
        episodes=tuple(
            TmdbEpisode(
                season_number=1,
                episode_number=first + n,
                name=f"Episode {first + n}",
                air_date=start + timedelta(weeks=n),
                runtime=24,
            )
            for first, count, start in REZERO_COURS
            for n in range(count)
        ),
    )
    # 補缺集（票 23d）：一季 14 集、一集都沒有。
    starfall = tv(
        900001, "Starfall Harbor", "星降りの港", 2024, season_entry(1, STARFALL_EPISODES, 2024)
    )
    tmdb.details[(starfall.kind, starfall.tmdb_id)] = starfall
    tmdb.season_rows[(900001, 1)] = season_rows(1, STARFALL_EPISODES, 2024)
    tmdb.search_results["re:zero"] = (
        TmdbEntry(65942, MediaKind.TV, "Re:ZERO", "Re:ゼロから始める異世界生活", 2016, ""),
    )
    tmdb.season_rows[(105248, 1)] = season_rows(1, 10, 2022)
    tmdb.season_rows[(105248, 2)] = season_rows(2, 10, 2026)
    tmdb.search_results["cyberpunk: edgerunners 2"] = (
        TmdbEntry(105248, MediaKind.TV, "Cyberpunk: Edgerunners", "サイバーパンク", 2022, ""),
    )


def arrange_mikan(factory: FakeClientFactory) -> None:
    """Mikan 的搜尋頁把前一個番組換成 4009，番組頁與單一 feed 是 4009 × 字幕組 370 的錄製頁。"""
    search = (MIKAN / "home-search.frieren.html").read_text(encoding="utf-8")
    search = search.replace("/Home/Bangumi/3141", "/Home/Bangumi/4009")
    pages = factory.rss_.pages
    pages[search_url("Cyberpunk Edgerunners 2")] = search.encode()
    pages[bangumi_url(4009)] = (MIKAN / "home-bangumi.4009.html").read_bytes()
    pages[bangumi_feed_url(4009, 370)] = (MIKAN / "rss-bangumi.4009-370.xml").read_bytes()


# ---------------------------------------------------------------- 腳本與斷言的小工具


def returned(script: Script, tool: str) -> list[dict[str, Any]]:
    """模型最後一次呼叫時看得到的、某個工具的每一筆結果（JSON 解回來）。"""
    return [
        part.model_response_object()
        for message in script.seen[-1]
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name == tool
    ]


def last_result(messages: list[ModelMessage], tool: str) -> dict[str, Any]:
    found = [
        part.model_response_object()
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name == tool
    ]
    return found[-1]


def tv_route(messages: list[ModelMessage]) -> int:
    """看 `media_read_media` 的 `routes` 挑 tv 那一條（skill 第 5 步）。"""
    read = last_result(messages, "media_read_media")
    # 長的結果會被截過，真的內容包在 `result` 裡（`agent._given`）。
    routes = read.get("result", read)["routes"]
    return int(next(route["id"] for route in routes if route["slug"] == "tv"))


def call_with(
    tool: str, args: Callable[[list[ModelMessage]], dict[str, Any]]
) -> Callable[..., Any]:
    """參數要看前面的工具結果才組得出來的那一步。"""

    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(tool, args(messages), tool_call_id="card-1")])

    return step


def commands_of(client: TestClient, turn: int = -1) -> list[tuple[str, str]]:
    return [(t.command, t.outcome) for t in recorded(client)[turn].tools]


# ---------------------------------------------------------------- 新番推薦


class Seen(Script):
    """另外記下每次呼叫的 instructions。"""

    instructions: list[str]

    def __init__(self) -> None:
        super().__init__()
        self.instructions = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.instructions.append(info.instructions or "")
        return super().__call__(messages, info)


@pytest.fixture
def script() -> Seen:
    return Seen()


@pytest.fixture
def factory(
    roots: dict[str, Path], script: Script, outside: Outside, tmp_path: Path
) -> FakeClientFactory:
    made = berth_services(roots, script)
    anime_sources(made, tmp_path)
    arrange_tmdb(made)
    arrange_mikan(made)
    made.indexer_search_ = FakeIndexerSearch(results=[REZERO_PACK])
    return made


REZERO_PACK = IndexerResult(
    title="[Sub] Re:Zero kara Hajimeru Isekai Seikatsu - S01 [BD 1080p]",
    indexer="nyaa",
    size=40_000_000_000,
    seeders=30,
    download_url="https://nyaa.example/download/rezero-s01.torrent",
    guid="rezero-s01",
)


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    yield from running_berth(config, tmp_path, roots, factory)


def scorers_of(anilist_id: int) -> int:
    """錄下來的季表裡，某一部的分數分佈加總：獨立於被測的程式再算一次。"""
    page = json.loads(read_fixture("http/anilist/season.fall-2026.json"))["body"]["data"]["Page"]
    [entry] = [media for media in page["media"] if media["id"] == anilist_id]
    return sum(row["amount"] for row in entry["stats"]["scoreDistribution"])


class TestNewSeasonPicks:
    EDGERUNNERS = 195539

    def subscribe(self, messages: list[ModelMessage]) -> dict[str, Any]:
        row = {
            "bangumi_id": last_result(messages, "bangumi_read_bangumi")["id"],
            "subgroup_id": 370,
            "media_id": EDGERUNNERS_ID,
            "route_id": tv_route(messages),
        }
        return {"rows": [row]}

    @pytest.fixture(autouse=True)
    def model(self, script: Script) -> None:
        script.steps = [
            call("skills_load_skill", name="new-season-picks"),
            call("anilist_read_season", season="FALL", year=2026),
            call("bgm_read_calendar"),
            say("Here are this season's picks."),
            call("discover_search_media", query="Cyberpunk: Edgerunners 2"),
            call("media_read_media", media_id=EDGERUNNERS_ID),
            call("bangumi_search_bangumi", term="Cyberpunk Edgerunners 2"),
            call("bangumi_read_bangumi", bangumi_id=4009),
            call_with("rss_subscribe_mikan", self.subscribe),
        ]

    def test_the_model_sees_the_season_with_raters_and_the_calendar_with_votes(
        self, client: TestClient, script: Script, outside: Outside
    ) -> None:
        response = chat(client, "這季有什麼好看的新番？")

        assert response.status_code == 200, response.text
        [season] = returned(script, "anilist_read_season")
        assert (season["season"], season["year"]) == ("FALL", 2026)
        top = season["entries"][0]
        assert (top["anilist_id"], top["title_romaji"]) == (
            self.EDGERUNNERS,
            "Cyberpunk: Edgerunners 2",
        )
        assert top["popularity"] == 107511
        # 打分人數是分佈加總：模型要拿它判斷「分數幾個人給的」（skill 第 2 步）。
        assert top["scorers"] == scorers_of(self.EDGERUNNERS) > 0
        popularity = [entry["popularity"] for entry in season["entries"]]
        assert popularity == sorted(popularity, reverse=True)
        assert season["external_content"]

        [calendar] = returned(script, "bgm_read_calendar")
        edgerunners = next(item for item in calendar["items"] if item["bgm_id"] == 513878)
        assert edgerunners["name_cn"] == "赛博朋克：边缘行者 2"
        assert edgerunners["votes"] == 4518
        votes = [item["votes"] for item in calendar["items"]]
        assert votes == sorted(votes, reverse=True)
        assert calendar["external_content"]
        # 季表問一次、放送表問一次。
        assert outside.anilist.asked == [{"s": "FALL", "y": 2026, "n": 25}]
        assert outside.bgm.call_count == 1

    def test_the_skill_is_what_the_model_followed_and_the_turn_is_recorded(
        self, client: TestClient, script: Script
    ) -> None:
        chat(client, "這季有什麼好看的新番？")

        [loaded] = returned(script, "skills_load_skill")
        assert loaded["name"] == "new-season-picks"
        assert commands_of(client) == [
            ("skills.load_skill", "ok"),
            ("anilist.read_season", "ok"),
            ("bgm.read_calendar", "ok"),
        ]
        assert recorded(client)[0].run.stop_reason == "completed"

    def test_a_name_copied_from_anilist_marks_the_card_as_external_text(
        self, client: TestClient, script: Script
    ) -> None:
        """自由文字出自外部內容的那一格才亮警示（`external_fields`）；id 與使用者說過的不算。"""

        def named(messages: list[ModelMessage]) -> dict[str, Any]:
            [row] = self.subscribe(messages)["rows"]
            title = last_result(messages, "anilist_read_season")["entries"][0]["title_native"]
            return {"rows": [{**row, "name": title}]}

        script.steps[-1] = call_with("rss_subscribe_mikan", named)
        chat(client, "這季有什麼好看的新番？")

        # 使用者沒打片名；日文原名只在 AniList 的季表裡（放送表是別的寫法）。
        chat(client, "我要看人氣第一名那部", earlier=[])

        [proposal] = cards(client)
        assert [row["name"] for row in proposal["arguments"]] == [
            "サイバーパンク: エッジランナーズ2"
        ]
        assert proposal["preview"]["external_fields"] == [["name"]]

    def test_the_pick_ends_in_a_mikan_subscription_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        chat(client, "這季有什麼好看的新番？")

        response = chat(client, "我要看 Cyberpunk: Edgerunners 2", earlier=[])

        assert response.status_code == 200, response.text
        [proposal] = cards(client)
        assert proposal["command"] == "rss.subscribe_mikan"
        assert proposal["status"] == "pending"
        [row] = proposal["arguments"]
        assert (row["bangumi_id"], row["subgroup_id"], row["media_id"]) == (
            4009,
            370,
            EDGERUNNERS_ID,
        )
        assert row["route_id"] == route_of(client, "tv")
        # 預覽：訂下去會當場送 12 集，卡上沒有哪一格自由文字出自外部內容。
        assert proposal["preview"]["torrents"] == [12]
        assert proposal["preview"]["external_fields"] == [[]]
        # 卡片之前什麼都沒訂：Feed 沒建、qBittorrent 沒收到東西。
        assert client.get("/api/rss/feeds").json() == []
        assert factory.qbittorrent_.added == []
        assert commands_of(client) == [
            ("discover.search_media", "ok"),
            ("media.read_media", "ok"),
            ("bangumi.search_bangumi", "ok"),
            ("bangumi.read_bangumi", "ok"),
            ("rss.subscribe_mikan", "proposed"),
        ]
        assert recorded(client)[-1].run.stop_reason == "awaiting_confirmation"


# ---------------------------------------------------------------- 情境 2


def to_the_work(script: Script) -> list[Any]:
    """skill → 找 TMDB → 讀作品（`series-mapping` 第 1、2 步）。"""
    return [
        call("skills_load_skill", name="series-mapping"),
        call("discover_search_media", query="Re:Zero"),
        call("media_read_media", media_id=REZERO_ID),
    ]


def add_download(messages: list[ModelMessage]) -> dict[str, Any]:
    """總覽卡的一列：作品、Route、搜尋結果的一列都抄自前面的工具結果。"""
    searched = last_result(messages, "search_search_torrents")
    return {
        "rows": [
            {
                "source_id": searched["rows"][0]["source_id"],
                "media_id": REZERO_ID,
                "route_id": tv_route(messages),
            }
        ]
    }


class TestWholeSeries:
    # 票 16 實跑抓到的：一季一集一筆的集表讓 85 集的一季超過截斷上限。給模型的那一份改成「狀態 →
    # 集數範圍」（`agent_tools.MODEL_VIEWS`）；票 23d 再留下播出區段，沒有網搜時切段靠它。
    def test_the_model_sees_the_long_season_and_where_its_cours_break(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [*to_the_work(script), say("Checking the ranges.")]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        [seen_work] = returned(script, "media_read_media")
        [season] = seen_work.get("result", seen_work)["seasons"]
        assert season["episode_count"] == 85
        assert season["aired_blocks"] == [
            {"episodes": "1-25", "from": "2016-04-04", "to": "2016-09-19"},
            {"episodes": "26-38", "from": "2020-07-08", "to": "2020-09-30"},
            {"episodes": "39-50", "from": "2021-01-06", "to": "2021-03-24"},
            {"episodes": "51-66", "from": "2024-10-02", "to": "2025-01-15"},
            {"episodes": "67-85", "from": "2026-04-08", "to": "2026-08-12"},
        ]

    def test_reading_the_work_first_makes_one_overview_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [
            *to_the_work(script),
            call("search_search_torrents", media_id=REZERO_ID, query="Re:Zero S01"),
            call_with("downloading_add_manual_download", add_download),
        ]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        [proposal] = cards(client)
        assert proposal["command"] == "downloading.add_manual_download"
        assert proposal["status"] == "pending"
        [row] = proposal["arguments"]
        assert row["media_id"] == REZERO_ID
        assert row["route_id"] == route_of(client, "tv")
        assert factory.qbittorrent_.added == []
        assert commands_of(client)[-1] == ("downloading.add_manual_download", "proposed")


# ---------------------------------------------------------------- 補缺集


def single_episode(group: str, episode: int, seeders: int) -> IndexerResult:
    return IndexerResult(
        title=f"[{group}] Starfall Harbor S01E{episode:02d} [1080p]",
        indexer="nyaa",
        size=1_400_000_000,
        seeders=seeders,
        download_url=f"https://nyaa.example/download/{group}-{episode}.torrent",
        guid=f"{group}-{episode}",
    )


def episodes_of(rows: list[dict[str, Any]]) -> set[int]:
    return {
        episode
        for row in rows
        if row.get("verdict") == "fits" and row.get("episode_start") is not None
        for episode in range(
            row["episode_start"], (row.get("episode_end") or row["episode_start"]) + 1
        )
    }


class TestMissingEpisodes:
    def test_a_season_of_single_episode_releases_is_covered_in_what_the_model_sees(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        """票 23d：種子搜尋只給模型前 10 列之後，一季缺 14 集、每集各自一個發佈（另一組只做了前
        7 集、做種更多，排在前面）時，前 10 列只蓋得到 7 集。補缺集一季只搜一次，模型看不到的那幾集
        就不會上卡。"""
        factory.indexer_search_ = FakeIndexerSearch(
            results=[
                *(single_episode("Fast", n, 200 - n) for n in range(1, 8)),
                *(single_episode("Slow", n, 100 - n) for n in range(1, STARFALL_EPISODES + 1)),
            ]
        )
        script.steps = [
            call("media_read_media", media_id=STARFALL_ID),
            call(
                "search_search_torrents",
                media_id=STARFALL_ID,
                scope={"missing": True, "season": 1},
            ),
            say("Picking releases."),
        ]

        chat(client, "Starfall Harbor 第一季缺的幫我補齊")

        [seen] = returned(script, "search_search_torrents")
        rows = seen.get("result", seen)["rows"]
        assert episodes_of(rows) == set(range(1, STARFALL_EPISODES + 1))


# ---------------------------------------------------------------- 一般使用者


class TestWhatAUserSees:
    ANIME_TOOLS: ClassVar[set[str]] = {
        "anilist_read_season",
        "bgm_read_calendar",
        "discover_read_trending",
    }

    def test_a_user_gets_the_anime_tools_but_not_the_skill_that_needs_rss(
        self, client: TestClient, script: Seen
    ) -> None:
        client.cookies.clear()  # 這一台 Berth 先以管理員登入過
        sign_in_crew(client)
        script.steps = [say("Hi.")]

        chat(client, "這季有什麼好看的新番？")

        assert set(script.tools[0]) >= self.ANIME_TOOLS
        assert "rss_subscribe_mikan" not in script.tools[0]
        instructions = script.instructions[0]
        # `new-season-picks` 用 `rss.*`（只給管理員）；`series-mapping` 的工具一般使用者都有。
        assert "- new-season-picks:" not in instructions
        assert "- series-mapping:" in instructions


def test_the_anime_tools_are_external_content() -> None:
    assert {
        "anilist.read_season",
        "bgm.read_calendar",
    } <= set(EXTERNAL_TOOLS)
