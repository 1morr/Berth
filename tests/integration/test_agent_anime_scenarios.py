"""側面板的兩個動漫情境，用假模型從頭走到尾（M5 票 16、plan §11.6〈分段〉第 6 段）。

模型是 `FakeAi` 的腳本（`test_agent_api.Script`），不打網路：

- AniList、Fribb、Bangumi 用**真的 adapter**，回應是錄下來的 fixture（`respx` 攔 `httpx`；
  TestClient 走 `httpx2`，不會被它攔到）。閘門與快取各測試自己一份、時鐘是假的，沒有東西真的在等。
- TMDB、索引站、Mikan 是替身。Mikan 的兩頁是錄下來的**別部作品**（搜尋頁是葬送的芙莉莲、番組頁是
  4009），測試只看流程與守法，不看那兩頁的內容。

情境 1「這季有什麼好看的新番」：skill → 季表 + 放送表 → 使用者挑 → 找 TMDB → 找 Mikan → 確認卡。
情境 2「Re:Zero 全系列」：skill → 搜尋 → 走系列（一層問一次）→ Fribb 換算 → 守法 → 總覽卡。

守法的重點（`agent_origins`）：Fribb 與 AniList 的結果是**外部內容**，裡面的 `tv:65942` 不算
「出自工具結果」；模型要先 `media_read_media` 讀過才寫得了。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
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
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo

from berth.adapters.anilist import API_URL, AnimeEntry, AnimeTitle
from berth.adapters.anilist.client import HttpAniList, Throttle
from berth.adapters.anilist.fake import FakeAniList
from berth.adapters.bgm import API_URL as BGM_URL
from berth.adapters.bgm.client import HttpBgm
from berth.adapters.fribb import LIST_URL
from berth.adapters.fribb.client import HttpFribb, list_path
from berth.adapters.indexer import IndexerResult
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.rss.mikan import bangumi_feed_url, bangumi_url, search_url
from berth.adapters.tmdb import TmdbDetail, TmdbEntry, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.ttl import TtlCache
from berth.config import Config
from berth.domain import MediaKind
from berth.services.agent_tools import EXTERNAL_TOOLS
from berth.services.skills import catalog
from tests.conftest import FIXTURES, read_fixture
from tests.integration.arrange import sign_in_crew
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import Script, call, chat, recorded, say, stored_history
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

    def layers(self) -> list[list[int]]:
        """走系列圖時每一次問的 `ids`。"""
        return [asked["ids"] for asked in self.asked if "ids" in asked]


@dataclass
class Outside:
    """三個動漫資料來源的錄製回應，加上 `respx` 的路由。"""

    router: respx.MockRouter
    anilist: AniListServer
    fribb: respx.Route
    bgm: respx.Route


@pytest.fixture
def outside(tmp_path: Path) -> Iterator[Outside]:
    anilist = AniListServer()
    anilist.load(
        "search.rezero",
        "season.fall-2026",
        *(f"entries.rezero.{layer}" for layer in range(5)),
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(API_URL).mock(side_effect=anilist)
        fribb = router.get(LIST_URL).mock(
            return_value=httpx.Response(
                200, content=read_fixture("http/fribb/anime-list-full.excerpt.json").encode()
            )
        )
        bgm = router.get(f"{BGM_URL}/calendar").mock(
            return_value=httpx.Response(
                200,
                json=json.loads(read_fixture("http/bgm/calendar.json"))["body"],
                headers={"cache-control": "max-age=3600"},
            )
        )
        yield Outside(router, anilist, fribb, bgm)


def anime_sources(factory: FakeClientFactory, tmp_path: Path) -> None:
    """換上真的 adapter：每個測試自己的閘門（假時鐘）、快取與 Fribb 檔。"""
    time_ = FakeTime()
    factory.anilist_ = HttpAniList(
        throttle=Throttle(clock=time_.time, sleep=time_.sleep),
        cache=TtlCache(ttl=60, size=64, clock=time_.time),
    )
    factory.anime_ids_ = HttpFribb(list_path(tmp_path / "config"))
    factory.bgm_ = HttpBgm(cache=TtlCache(ttl=60, size=4, clock=time_.time))


# ---------------------------------------------------------------- 安排：TMDB、索引站、Mikan

EDGERUNNERS_ID = "tv:105248"
REZERO_ID = "tv:65942"
#: TMDB 上的劇場版 Memory Snow（研究 08 §1.3）。
MEMORY_SNOW = 532321
#: Re:Zero 的 TMDB 第 1 季集數：AniList 五輪的集數加起來 25 + 13 + 12 + 16 + 19。
REZERO_S1_EPISODES = 85
REZERO_SPECIALS = 2


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
    """Edgerunners（情境 1 挑的那部）與 Re:Zero（情境 2）在 TMDB 上的樣子。"""
    tmdb = factory.tmdb_
    edgerunners = tv(
        105248, "Cyberpunk: Edgerunners", "サイバーパンク エッジランナーズ", 2022,
        season_entry(1, 10, 2022), season_entry(2, 10, 2026),
    )  # fmt: skip
    rezero = tv(
        65942, "Re:ZERO -Starting Life in Another World-", "Re:ゼロから始める異世界生活", 2016,
        season_entry(0, REZERO_SPECIALS, 2018), season_entry(1, REZERO_S1_EPISODES, 2016),
    )  # fmt: skip
    for detail in (edgerunners, rezero):
        tmdb.details[(detail.kind, detail.tmdb_id)] = detail
    tmdb.season_rows[(105248, 1)] = season_rows(1, 10, 2022)
    tmdb.season_rows[(105248, 2)] = season_rows(2, 10, 2026)
    tmdb.season_rows[(65942, 0)] = season_rows(0, REZERO_SPECIALS, 2018)
    tmdb.season_rows[(65942, 1)] = season_rows(1, REZERO_S1_EPISODES, 2016)
    tmdb.search_results["cyberpunk: edgerunners 2"] = (
        TmdbEntry(105248, MediaKind.TV, "Cyberpunk: Edgerunners", "サイバーパンク", 2022, ""),
    )
    tmdb.search_results["re:zero"] = (
        TmdbEntry(65942, MediaKind.TV, "Re:ZERO", "Re:ゼロから始める異世界生活", 2016, ""),
    )
    # Memory Snow：AniList 把它算在 OVA 條目 100049 裡，Fribb 對到 Specials，TMDB 上是獨立的電影。
    tmdb.search_results["re:zero memory snow"] = (
        TmdbEntry(MEMORY_SNOW, MediaKind.MOVIE, "Re:ZERO Memory Snow", "Memory Snow", 2018, ""),
    )
    tmdb.details[(MediaKind.MOVIE, MEMORY_SNOW)] = TmdbDetail(
        tmdb_id=MEMORY_SNOW,
        kind=MediaKind.MOVIE,
        title="Re:ZERO -Starting Life in Another World- Memory Snow",
        original_title="Re:ゼロから始める異世界生活 Memory Snow",
        year=2018,
        first_air_date=date(2018, 10, 6),
        overview="",
        poster_path="",
        runtime=60,
    )


def arrange_mikan(factory: FakeClientFactory) -> None:
    """Mikan 的搜尋頁把前一個番組換成 4009，番組頁與單一 feed 是 4009 × 字幕組 370 的錄製頁。"""
    search = (MIKAN / "home-search.frieren.html").read_text(encoding="utf-8")
    search = search.replace("/Home/Bangumi/3141", "/Home/Bangumi/4009")
    pages = factory.rss_.pages
    pages[search_url("Cyberpunk Edgerunners 2")] = search.encode()
    pages[bangumi_url(4009)] = (MIKAN / "home-bangumi.4009.html").read_bytes()
    pages[bangumi_feed_url(4009, 370)] = (MIKAN / "rss-bangumi.4009-370.xml").read_bytes()


def arrange_indexer(factory: FakeClientFactory) -> None:
    factory.indexer_search_ = FakeIndexerSearch(results=[REZERO_PACK])


REZERO_PACK = IndexerResult(
    title="[Sub] Re:Zero kara Hajimeru Isekai Seikatsu - S01 [BD 1080p]",
    indexer="nyaa",
    size=40_000_000_000,
    seeders=30,
    download_url="https://nyaa.example/download/rezero-s01.torrent",
    guid="rezero-s01",
)


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


def first_value(node: object, key: str) -> Any:
    """結果裡第一個叫 `key` 的值：模型從工具結果裡抄 id 就是這樣抄的。"""
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = first_value(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = first_value(value, key)
            if found is not None:
                return found
    return None


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


# ---------------------------------------------------------------- 情境 1


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
    arrange_indexer(made)
    return made


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

REZERO = "Re:Zero kara Hajimeru Isekai Seikatsu"
FRANCHISE = [21355, 100049, 108632, 119661, 163134, 189046]


def add_download(messages: list[ModelMessage]) -> dict[str, Any]:
    """總覽卡的一列：作品、Route、搜尋結果的一列都抄自前面的工具結果。"""
    searched = last_result(messages, "search_search_torrents")
    return {
        "rows": [
            {
                "source_id": first_value(searched, "source_id"),
                "media_id": REZERO_ID,
                "route_id": tv_route(messages),
            }
        ]
    }


def to_fribb(script: Script) -> list[Any]:
    """情境 2 到 Fribb 為止的腳本（後面接各測試自己的結尾）。"""
    return [
        call("skills_load_skill", name="series-mapping"),
        call("anilist_search_anime", query=REZERO),
        call("anilist_read_franchise", anilist_id=21355),
        call("fribb_lookup_anime", anilist_ids=FRANCHISE),
    ]


def unmapped_mark() -> str:
    """`series-mapping` 要模型在沒經對照表的列上標的那幾個字（skill 改了，這條測試跟著紅）。"""
    skill = next(skill for skill in catalog() if skill.name == "series-mapping")
    assert "If `fribb_lookup_anime` fails" in skill.body
    found = re.search(r'"(未經對照表[^"]*)"', skill.body)
    assert found is not None, "series-mapping no longer says how to mark rows without Fribb"
    return found.group(1)


def table_and_card(table: str) -> Callable[..., Any]:
    """同一則回覆：先把表給使用者看，再提一張總覽卡（卡片沒有備註格，標記在表上）。"""

    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                TextPart(table),
                ToolCallPart(
                    "downloading_add_manual_download", add_download(messages), tool_call_id="card-1"
                ),
            ]
        )

    return step


def skill_mark(starts: str) -> str:
    """`series-mapping` 要模型標的那幾個字（skill 改了，用到它的測試跟著紅）。"""
    skill = next(skill for skill in catalog() if skill.name == "series-mapping")
    found = re.search(rf'"({starts}[^"]*)"', skill.body)
    assert found is not None, f"series-mapping no longer says to mark {starts}"
    return found.group(1)


def tv_entries(walked: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in walked["entries"] if e["format"] == "TV"]


def by_table(mapped: dict[str, Any], walked: dict[str, Any]) -> dict[int, tuple[int, int]]:
    """A：Fribb 的 `first_tmdb_episode` 加 AniList 的集數。"""
    counts = {e["anilist_id"]: e["episodes"] for e in tv_entries(walked)}
    return {
        e["anilist_id"]: (
            e["first_tmdb_episode"],
            e["first_tmdb_episode"] + counts[e["anilist_id"]] - 1,
        )
        for e in mapped["entries"]
        if e["anilist_id"] in counts
    }


def by_chaining(walked: dict[str, Any]) -> dict[int, tuple[int, int]]:
    """B：照開播順序從 E01 串（Re:Zero 全在 TMDB 第 1 季）。"""
    chained, cursor = {}, 1
    for entry in tv_entries(walked):
        chained[entry["anilist_id"]] = (cursor, cursor + entry["episodes"] - 1)
        cursor += entry["episodes"]
    return chained


def season_table(messages: list[ModelMessage], mark: str) -> str:
    """模型照 skill 寫的表：兩種範圍並列，第 1 季有一列不一致，整季每一列都標。"""
    walked = last_result(messages, "anilist_read_franchise")
    mapped = last_result(messages, "fribb_lookup_anime")
    a, b = by_table(mapped, walked), by_chaining(walked)
    rows = [
        f"| {i} | S01E{a[i][0]:02d}–E{a[i][1]:02d} | S01E{b[i][0]:02d}–E{b[i][1]:02d} | {mark} |"
        for i in a
    ]
    return "| AniList | A | B | |\n" + "\n".join(rows)


def assistant_texts(client: TestClient) -> list[str]:
    return [
        part.content
        for message in stored_history(client)
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, TextPart)
    ]


FRUBA_ANILIST = 105334
FRUBA_ID = "tv:85991"


def arrange_fruits_basket(factory: FakeClientFactory) -> None:
    """AniList 上的 2019 年版（替身，沒有錄這一部），TMDB 上同名的三部。"""
    entry = AnimeEntry(
        id=FRUBA_ANILIST,
        mal_id=38680,
        title=AnimeTitle("Fruits Basket: 1st Season", "Fruits Basket (2019)", "フルーツバスケット"),
        format="TV",
        status="FINISHED",
        episodes=25,
        season="SPRING",
        season_year=2019,
        start_date="2019-04-06",
        average_score=79,
        popularity=300000,
        genres=("Drama",),
    )
    factory.anilist_ = FakeAniList(
        known={FRUBA_ANILIST: entry}, found={"Fruits Basket 2019": [entry]}
    )
    tmdb = factory.tmdb_
    tmdb.search_results["fruits basket (2019)"] = (
        TmdbEntry(36941, MediaKind.TV, "Fruits Basket", "フルーツバスケット", 2001, "", True),
        TmdbEntry(900001, MediaKind.TV, "Fruits Basket", "Fruits Basket", 2019, "", False),
        TmdbEntry(85991, MediaKind.TV, "Fruits Basket", "フルーツバスケット", 2019, "", True),
    )
    detail = tv(85991, "Fruits Basket", "フルーツバスケット", 2019, season_entry(1, 25, 2019))
    tmdb.details[(detail.kind, detail.tmdb_id)] = detail
    tmdb.season_rows[(85991, 1)] = season_rows(1, 25, 2019)


def picked(messages: list[ModelMessage]) -> str:
    """照 skill 的規則從搜尋結果挑：只留動畫，首播年最接近 AniList 第一季開播的那一年。"""
    walked = last_result(messages, "anilist_read_franchise")
    started = int(str(tv_entries(walked)[0]["start_date"])[:4])
    found = last_result(messages, "discover_search_media")
    animated = [item for item in found["items"] if item["animation"] is True]
    return str(min(animated, key=lambda item: abs(item["year"] - started))["id"])


def guarded_write(script: Script) -> list[Any]:
    """查了 Route、搜了 torrent，但**沒讀過**作品：`tv:65942` 只在 Fribb 的結果裡。"""
    return [
        *to_fribb(script),
        call("media_route_choices", media_id=REZERO_ID),
        call("search_search_torrents", media_id=REZERO_ID, query="Re:Zero S01"),
        call_with(
            "downloading_add_manual_download",
            lambda messages: {
                "rows": [
                    {
                        "source_id": first_value(
                            last_result(messages, "search_search_torrents"), "source_id"
                        ),
                        "media_id": REZERO_ID,
                        "route_id": first_value(last_result(messages, "media_route_choices"), "id"),
                    }
                ]
            },
        ),
    ]


class TestWholeFranchise:
    def test_the_walk_asks_once_per_layer_and_the_model_sees_six_entries_oldest_first(
        self, client: TestClient, script: Script, outside: Outside
    ) -> None:
        script.steps = [*to_fribb(script), say("Here is the table.")]

        response = chat(client, "幫我把 Re:Zero 全系列都抓下來")

        assert response.status_code == 200, response.text
        [found] = returned(script, "anilist_search_anime")
        assert found["entries"][0]["anilist_id"] == 21355
        [franchise] = returned(script, "anilist_read_franchise")
        assert [entry["anilist_id"] for entry in franchise["entries"]] == FRANCHISE
        assert [entry["format"] for entry in franchise["entries"]] == [
            "TV", "OVA", "TV", "TV", "TV", "TV",
        ]  # fmt: skip
        assert [entry["episodes"] for entry in franchise["entries"]] == [25, 2, 13, 12, 16, 19]
        assert franchise["truncated"] is False
        assert franchise["external_content"]
        # 一層問一次：搜尋 1 次 + 五層 = 6 次 POST，走圖只佔 5 次（原型一個節點問一次要 12 次）。
        assert outside.anilist.layers() == [
            [21355], [100049, 108632], [119661], [163134], [189046],
        ]  # fmt: skip
        assert len(outside.anilist.asked) == 1 + 5
        assert outside.router.calls.call_count >= 6

    def test_fribb_gives_the_raw_offsets_the_skill_tells_the_model_to_fix(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [*to_fribb(script), say("Here is the table.")]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        [mapped] = returned(script, "fribb_lookup_anime")
        assert mapped["unmapped"] == []
        assert mapped["external_content"]
        by_id = {entry["anilist_id"]: entry for entry in mapped["entries"]}
        assert {entry["media_ids"][0] for entry in by_id.values()} == {REZERO_ID}
        tv_cours = [21355, 108632, 119661, 163134, 189046]
        assert [by_id[i]["tmdb_season"] for i in tv_cours] == [1, 1, 1, 1, 1]
        # offset + 1：第 2 季寫 26，所以 E27 起——與 E26 差一集，要模型用集數串起來改正。
        assert [by_id[i]["first_tmdb_episode"] for i in tv_cours] == [1, 27, 39, 51, 67]
        # 改正之後 25 + 13 + 12 + 16 + 19 剛好是 TMDB 第 1 季的 85 集；OVA 在 Specials。
        assert (by_id[100049]["tmdb_season"], by_id[100049]["first_tmdb_episode"]) == (0, 1)

    def test_without_the_mapping_table_the_model_chains_counts_and_marks_the_rows(
        self, client: TestClient, script: Script, outside: Outside, factory: FakeClientFactory
    ) -> None:
        """Fribb 的表還沒下載過、這一刻又下載不到：工具失敗交給模型，模型照 `series-mapping`
        第 3 步改用 AniList 的集數串、對 TMDB 那一季的總集數，表上標「未經對照表」，卡片照樣出。"""
        outside.fribb.mock(return_value=httpx.Response(503))
        mark = unmapped_mark()
        table = (
            f"| AniList entry | episodes | TMDB | |\n"
            f"| Re:Zero | 25 | S01E01–E25 | {mark} |\n"
            f"| 2nd Season | 13 | S01E26–E38 | {mark} |"
        )
        script.steps = [
            *to_fribb(script),
            call("discover_search_media", query="Re:Zero"),
            call("media_read_media", media_id=REZERO_ID),
            call("search_search_torrents", media_id=REZERO_ID, query="Re:Zero S01"),
            table_and_card(table),
        ]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        [failed] = returned(script, "fribb_lookup_anime")
        assert "503" in failed["error"]
        assert ("fribb.lookup_anime", "failed") in commands_of(client)
        [work] = returned(script, "media_read_media")
        assert {s["season_number"]: s["episode_count"] for s in work["seasons"]}[1] == 85
        [proposal] = cards(client)
        assert proposal["command"] == "downloading.add_manual_download"
        assert proposal["arguments"][0]["media_id"] == REZERO_ID
        replies = [
            part.content
            for message in stored_history(client)
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, TextPart)
        ]
        assert any(mark in reply for reply in replies)

    def test_when_the_table_and_chaining_disagree_the_whole_season_is_marked(
        self, client: TestClient, script: Script
    ) -> None:
        """Fribb 可用時也串接一次（`series-mapping` 第 3 步）：Re:Zero 第 2 季 Fribb 給 E27 起、串接
        給 E26 起，兩種不一致，TMDB 第 1 季整季標「兩種算法不一致」，不自己挑一邊；卡片照樣出。"""
        mark = skill_mark("兩種算法不一致")
        script.steps = [
            *to_fribb(script),
            call("media_read_media", media_id=REZERO_ID),
            call("search_search_torrents", media_id=REZERO_ID, query="Re:Zero S01"),
            lambda messages, info: table_and_card(season_table(messages, mark))(messages, info),
        ]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        # 模型看得到的兩種算法真的不一致：A 從 Fribb 的結果算、B 從 AniList 的集數串。
        [walked] = returned(script, "anilist_read_franchise")
        [mapped] = returned(script, "fribb_lookup_anime")
        a, b = by_table(mapped, walked), by_chaining(walked)
        assert a[108632] == (27, 39) and b[108632] == (26, 38)
        [proposal] = cards(client)
        assert proposal["command"] == "downloading.add_manual_download"
        reply = "\n".join(assistant_texts(client))
        # 整季都標：第 1 季的五個條目每一列都有標記，不只不一致的那一列。
        assert reply.count(mark) == len(a)

    def test_without_the_table_a_remake_is_found_by_animation_and_the_closest_year(
        self, client: TestClient, script: Script, outside: Outside, factory: FakeClientFactory
    ) -> None:
        """Fribb 抓不到、作品只能靠標題搜：「Fruits Basket」在 TMDB 有 2001 年的舊作、2019 年的
        重製版與同年的真人版。照 skill 只留動畫、取首播年最接近 AniList 第一季（2019）的那一部。"""
        outside.fribb.mock(return_value=httpx.Response(503))
        arrange_fruits_basket(factory)
        skill = next(skill for skill in catalog() if skill.name == "series-mapping")
        assert "`animation: true`" in skill.body and "`year` is closest" in skill.body
        script.steps = [
            call("skills_load_skill", name="series-mapping"),
            call("anilist_search_anime", query="Fruits Basket 2019"),
            call("anilist_read_franchise", anilist_id=FRUBA_ANILIST),
            call("fribb_lookup_anime", anilist_ids=[FRUBA_ANILIST]),
            call("discover_search_media", query="Fruits Basket (2019)"),
            lambda messages, info: ModelResponse(
                parts=[ToolCallPart("media_read_media", {"media_id": picked(messages)})]
            ),
            call("search_search_torrents", media_id=FRUBA_ID, query="Fruits Basket 2019"),
            call_with(
                "downloading_add_manual_download",
                lambda messages: {
                    "rows": [
                        {
                            "source_id": first_value(
                                last_result(messages, "search_search_torrents"), "source_id"
                            ),
                            "media_id": picked(messages),
                            "route_id": tv_route(messages),
                        }
                    ]
                },
            ),
        ]

        chat(client, "幫我把 Fruits Basket 2019 全部抓下來")

        [found] = returned(script, "discover_search_media")
        # 三部都在結果裡、各帶首播年與「是不是動畫」：規則才挑得出來。
        assert [(item["id"], item["year"], item["animation"]) for item in found["items"]] == [
            ("tv:36941", 2001, True),
            ("tv:900001", 2019, False),
            (FRUBA_ID, 2019, True),
        ]
        [proposal] = cards(client)
        assert proposal["arguments"][0]["media_id"] == FRUBA_ID

    def test_an_ova_that_fribb_puts_in_specials_is_found_as_a_movie_by_title(
        self, client: TestClient, script: Script
    ) -> None:
        """票面：劇場版在 TMDB 是獨立的 movie，Fribb 對不到時用標題搜尋
        （`series-mapping` 第 4 步）。"""
        script.steps = [
            *to_fribb(script),
            call("discover_search_media", query="Re:Zero Memory Snow"),
            call("media_read_media", media_id=f"movie:{MEMORY_SNOW}"),
            say("Memory Snow is its own TMDB movie: matched by title, please check."),
        ]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        [found] = returned(script, "discover_search_media")
        assert [first_value(item, "id") for item in found["items"]] == [f"movie:{MEMORY_SNOW}"]
        [work] = returned(script, "media_read_media")
        assert (work["id"], work["kind"], work["seasons"]) == (f"movie:{MEMORY_SNOW}", "movie", [])
        skill = next(skill for skill in catalog() if skill.name == "series-mapping")
        assert "matched by title" in skill.body

    def test_an_id_seen_only_in_the_fribb_result_gets_no_card(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [*guarded_write(script), say("I need to read the work first.")]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        refused = last_result(script.seen[-1], "downloading_add_manual_download")
        assert refused["refused"] == "id_not_from_results"
        # 被擋的只有作品 id：Route 與 torrent 都出自前面的（非外部）工具結果。
        assert refused["detail"].startswith(f"media_id={REZERO_ID} did not come from")
        assert cards(client) == []
        assert commands_of(client)[-1] == ("downloading.add_manual_download", "refused")

    def test_reading_the_work_first_makes_one_overview_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        script.steps = [
            *to_fribb(script),
            call("media_read_media", media_id=REZERO_ID),
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
        assert proposal["preview"]["torrents"] == [1]
        assert factory.qbittorrent_.added == []
        assert [command for command, _ in commands_of(client)][-3:] == [
            "media.read_media",
            "search.search_torrents",
            "downloading.add_manual_download",
        ]
        assert commands_of(client)[-1][1] == "proposed"

    # 票 16 實跑抓到的：一季一集一筆的集表讓 85 集的一季超過截斷上限，`seasons` 被砍到只剩
    # Specials。給模型的那一份改成「狀態 → 集數範圍」（`agent_tools.MODEL_VIEWS`）。
    def test_the_model_sees_the_tmdb_episode_count_of_the_long_season(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [
            *to_fribb(script),
            call("media_read_media", media_id=REZERO_ID),
            say("Checking the ranges."),
        ]

        chat(client, "幫我把 Re:Zero 全系列都抓下來")

        [seen_work] = returned(script, "media_read_media")
        seasons = seen_work.get("result", seen_work)["seasons"]
        # 改正之後 25 + 13 + 12 + 16 + 19 剛好是 TMDB 第 1 季的 85 集；OVA 在 Specials。
        assert {s["season_number"]: s["episode_count"] for s in seasons} == {
            0: REZERO_SPECIALS,
            1: REZERO_S1_EPISODES,
        }


# ---------------------------------------------------------------- 一般使用者


class TestWhatAUserSees:
    ANIME_TOOLS: ClassVar[set[str]] = {
        "anilist_search_anime",
        "anilist_read_franchise",
        "anilist_read_season",
        "fribb_lookup_anime",
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


def test_the_five_anime_tools_are_external_content() -> None:
    assert {
        "anilist.search_anime",
        "anilist.read_franchise",
        "anilist.read_season",
        "fribb.lookup_anime",
        "bgm.read_calendar",
    } <= set(EXTERNAL_TOOLS)
