"""側面板的寫入工具與守法（M5 票 14、plan §11.6〈分段〉第 5 段、brief §14〈對話裡的確認卡〉）。

模型是 `FakeAi` 的腳本：它照腳本叫工具，測的是 Berth 擋不擋、出不出卡。

- id 必須出自這段對話已存的工具結果：`TestIdsComeFromToolResults`
- 網址必須逐字出自使用者的話：`TestAddressesComeFromTheUser`（prototype S5 / S6）
- 「讀過外部內容」只標在自由文字出自外部內容的卡：`TestExternalContent`
- 預覽理由在出卡之前擋下（`route_required`、`route_kind_mismatch`）：`TestRefusedBeforeACard`
- 送單的數量與磁碟閘（R5）：`TestHowManyOnOneCard`
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.rss import acgrip, mikan
from berth.adapters.websearch import WebPage
from berth.config import Config
from berth.domain import CollectionType
from berth.models import DiskSettings, Media, Route, RssSeries
from berth.services.jobs import JobSource
from berth.services.settings import write_settings
from berth.services.sources import SourceCache
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import BROWSER, KEY, Script, Step, call, chat, recorded, say
from tests.integration.test_agent_cards import (
    berth_services,
    card,
    cards,
    decide,
    in_db,
    looked_up,
    magnet,
    outcome_of,
    resume,
    returned,
    route_of,
    rows,
    running_berth,
    sent,
)
from tests.integration.test_media import SPY_ID
from tests.integration.test_rss_screen import mikan_feed
from tests.integration.test_rss_screen import release as synthetic
from tests.integration.test_rss_subscribe import ACGRIP_FEED, TERM

URL = "https://mikanani.me/RSS/MyBangumi?token=m5prototype"


@pytest.fixture
def script() -> Script:
    return Script()


@pytest.fixture
def factory(roots: dict[str, Path], script: Script) -> FakeClientFactory:
    return berth_services(roots, script)


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """同確認卡的測試：精靈跑完、Route 都在、AI 開著，管理員登入著。"""
    yield from running_berth(config, tmp_path, roots, factory)


FOUND_URL = "https://mikanani.me/RSS/Bangumi?bangumiId=3310&subgroupid=583"


def feeds(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/rss/feeds")
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def refusal(script: Script) -> dict[str, Any]:
    """模型最後拿到的那一筆工具結果（被擋下的那一句）。"""
    content = _last_return(script.seen[-1]).content
    assert isinstance(content, dict)
    return content


def _last_return(messages: list[ModelMessage]) -> ToolReturnPart:
    return [
        part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ][-1]


def tool(name: str, call_id: str = "card-1", **args: object) -> Step:
    return lambda _messages, _info: ModelResponse(
        parts=[ToolCallPart(name, dict(args), tool_call_id=call_id)]
    )


def add_feed_from_routes(url: str, *, movies: bool = True, name: str = "") -> Step:
    """看上一筆 `routes_list_routes` 的結果挑 Route，再加 Feed（prototype S5 的那一步）。"""

    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        listed = _last_return(messages).content
        assert isinstance(listed, list)
        by_slug = {row["route"]["slug"]: row["route"]["id"] for row in listed}
        args: dict[str, object] = {"url": url, "tv_route_id": by_slug["tv"], "name": name}
        if movies:
            args["movie_route_id"] = by_slug["movies"]
        return ModelResponse(parts=[ToolCallPart("rss_add_feed", {"rows": [args]}, "card-1")])

    return step


def with_tavily(client: TestClient, factory: FakeClientFactory, *pages: WebPage) -> None:
    body = {
        "enabled": True,
        "provider": "openai",
        "base_url": "",
        "model": "deepseek-flash",
        "api_key": KEY,
        "tavily_api_key": "tvly-dev-write-tools",
    }
    response = client.put("/api/settings/ai", json=body, headers=BROWSER)
    assert response.status_code == 200, response.text
    factory.web_search_.pages = list(pages)


def used_before(client: TestClient, route: int) -> None:
    """SPY×FAMILY 送過單、上次用 `route`（`default_route_id`）。"""

    async def write(session: AsyncSession) -> None:
        media = await session.get(Media, SPY_ID)
        assert media is not None
        media.default_route_id = route
        await session.commit()

    in_db(client, write)


def tv_routes(client: TestClient) -> list[int]:
    """啟用中、收劇集的 Route（這台 Berth 有 TV 與 Anime 兩條）。"""

    async def read(session: AsyncSession) -> list[int]:
        found = await session.scalars(
            select(Route.id).where(
                Route.collection_type == CollectionType.TVSHOWS, Route.enabled.is_(True)
            )
        )
        return list(found)

    return in_db(client, read)


def seen_work(client: TestClient) -> tuple[int, int]:
    """這段對話查過作品與它的 Route。

    真的模型會先叫 `discover_search_media`、`media_route_choices`。
    """
    tv, movies = route_of(client, "tv"), route_of(client, "movies")
    looked_up(client, {"items": [{"id": SPY_ID}]}, tool="discover_search_media")
    looked_up(client, [{"id": tv}, {"id": movies}], tool="media_route_choices")
    return tv, movies


# ---------------------------------------------------------------- id


class TestIdsComeFromToolResults:
    def test_a_route_no_tool_returned_gets_no_card(
        self, client: TestClient, script: Script
    ) -> None:
        looked_up(client, {"items": [{"id": SPY_ID}]}, tool="discover_search_media")
        script.steps = [
            tool("rss_subscribe_search", rows=[keyword_row(99)]),
            say("I need the routes first."),
        ]

        chat(client, "Subscribe SPY×FAMILY on nyaa.")

        assert refusal(script)["refused"] == "id_not_from_results"
        assert "route_id=99" in refusal(script)["detail"]
        assert cards(client) == []
        assert feeds(client) == []
        assert [t.outcome for t in recorded(client)[-1].tools] == ["refused"]

    def test_a_mikan_subgroup_the_model_made_up_gets_no_card(
        self, client: TestClient, script: Script
    ) -> None:
        tv, _ = seen_work(client)
        looked_up(client, {"id": 3310, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi")
        row = {"bangumi_id": 3310, "subgroup_id": 999, "media_id": SPY_ID, "route_id": tv}
        script.steps = [tool("rss_subscribe_mikan", rows=[row]), say("Let me read the groups.")]

        chat(client, "Subscribe it from Mikan.")

        assert refusal(script)["refused"] == "id_not_from_results"
        assert "subgroup_id=999" in refusal(script)["detail"]
        assert cards(client) == []

    def test_ids_from_tool_results_make_a_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        tv, _ = seen_work(client)
        looked_up(client, {"id": 3310, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi")
        bangumi(factory, {583: 12})
        row = {"bangumi_id": 3310, "subgroup_id": 583, "media_id": SPY_ID, "route_id": tv}
        script.steps = [tool("rss_subscribe_mikan", rows=[row])]

        chat(client, "Subscribe it from Mikan.")

        [proposal] = cards(client)
        assert proposal["command"] == "rss.subscribe_mikan"
        assert proposal["preview"]["flags"] == ["downloads"]


def season(factory: FakeClientFactory, episodes: int, subgroup: int = 583) -> None:
    """番組 3310 × 這個字幕組的單一 feed 上有 `episodes` 集。沒給的字幕組讀不到。"""
    factory.rss_.pages[mikan.bangumi_feed_url(3310, subgroup)] = mikan_feed(
        [synthetic(subgroup, "ANi", f"{episode:02d}") for episode in range(1, episodes + 1)]
    )


def bangumi(factory: FakeClientFactory, groups: dict[int, int], bangumi_id: int = 3310) -> None:
    """番組 `bangumi_id` 的番組頁：每個字幕組（id → 發佈數）一欄（票 26：Mikan 卡的字幕組選項與
    集數照它）。"""
    names = "".join(
        f'<a class="subgroup-name subgroup-{group}">Group {group}</a>'
        f'<span class="date">09/24/2026 12:00</span>'
        for group in groups
    )
    tables = "".join(
        f'<div class="subgroup-text" id="{group}">'
        + "".join(
            f'<a class="magnet-link-wrap">[Group {group}] SPY×FAMILY - {episode:02d}</a>'
            for episode in range(releases, 0, -1)
        )
        + "</div>"
        for group, releases in groups.items()
    )
    page = f'<p class="bangumi-title">SPY×FAMILY</p>{names}{tables}'
    factory.rss_.pages[mikan.bangumi_url(bangumi_id)] = page.encode()


def keyword_row(route: int, subgroup: str = "ANi") -> dict[str, object]:
    """關鍵字訂閱卡的一列（票 26）：《与你相恋》的 acg.rip 搜尋，模型建議 `subgroup`。"""
    return {
        "kind": "acgrip",
        "term": TERM,
        "subgroup": subgroup,
        "media_id": SPY_ID,
        "route_id": route,
    }


def serve_search(factory: FakeClientFactory) -> None:
    factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED


class TestWhatACardSends:
    """按卡的人要知道自己要送多少（協調者 2026-10-27）：訂閱 Mikan 按下去就當場送整季。"""

    def subscribe(self, client: TestClient, script: Script) -> dict[str, Any]:
        tv, _ = seen_work(client)
        looked_up(client, {"id": 3310, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi")
        row = {"bangumi_id": 3310, "subgroup_id": 583, "media_id": SPY_ID, "route_id": tv}
        script.steps = [tool("rss_subscribe_mikan", rows=[row])]
        chat(client, "Subscribe it from Mikan.")
        [proposal] = cards(client)
        return proposal

    def test_a_mikan_subscription_says_how_many_episodes_the_season_sends(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        bangumi(factory, {583: 12})

        proposal = self.subscribe(client, script)

        assert proposal["preview"]["torrents"] == [12]
        # 只讀：什麼都還沒送、也沒建 Feed。
        assert sent(factory) == []
        assert feeds(client) == []

    def test_with_more_subgroups_it_counts_the_biggest_one_could_pick(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        """票 26：卡上可以改選字幕組，所以數量閘看的是選項裡最多的那一個。"""
        bangumi(factory, {583: 12, 584: 15})

        proposal = self.subscribe(client, script)

        assert proposal["preview"]["torrents"] == [15]

    def test_a_bangumi_page_that_cannot_be_read_gets_no_card(
        self, client: TestClient, script: Script
    ) -> None:
        """字幕組要人選，番組頁讀不到就列不出選項：不出卡，把理由交給模型。"""
        tv, _ = seen_work(client)
        looked_up(client, {"id": 3310, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi")
        row = {"bangumi_id": 3310, "subgroup_id": 583, "media_id": SPY_ID, "route_id": tv}
        script.steps = [tool("rss_subscribe_mikan", rows=[row]), say("Mikan is down.")]

        chat(client, "Subscribe it from Mikan.")

        assert cards(client) == []
        assert refusal(script)["refused"] == "feed_unreachable"
        assert refusal(script)["row"] == 0

    def test_each_submit_row_is_one_torrent(self, client: TestClient, script: Script) -> None:
        script.steps = [card(rows(client, 1, 2))]
        chat(client, "Download 1 and 2.")

        [proposal] = cards(client)
        assert proposal["preview"]["torrents"] == [1, 1]


# ---------------------------------------------------------------- 網址


class TestAddressesComeFromTheUser:
    def test_a_feed_the_user_pasted_gets_a_card(self, client: TestClient, script: Script) -> None:
        """prototype S5：「幫我加這個 RSS：<網址>」。"""
        script.steps = [call("routes_list_routes"), add_feed_from_routes(URL)]

        chat(client, f"幫我加這個 RSS：{URL} ，劇集送 tv。")

        [proposal] = cards(client)
        assert proposal["command"] == "rss.add_feed"
        assert proposal["arguments"][0]["url"] == URL
        assert proposal["preview"]["flags"] == ["connects_out", "settings"]
        assert proposal["preview"]["external_fields"] == [[]]
        assert feeds(client) == []

    def test_a_feed_found_on_the_web_is_refused(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        """prototype S6：「上網找網址直接加」。網頁裡的網址不是使用者的話。"""
        with_tavily(client, factory, WebPage("Frieren on Mikan", FOUND_URL, f"RSS: {FOUND_URL}"))
        script.steps = [
            call("web_tavily_search", query="Frieren Mikan RSS"),
            call("routes_list_routes"),
            add_feed_from_routes(FOUND_URL),
            say("I can only add an address you paste yourself."),
        ]

        chat(client, "幫我上網找《葬送的芙莉蓮》第二季的 Mikan RSS 網址，找到就直接加進 Berth。")

        assert refusal(script)["refused"] == "address_not_from_user"
        assert FOUND_URL in refusal(script)["detail"]
        assert cards(client) == []
        assert feeds(client) == []


# ---------------------------------------------------------------- 外部內容


PAGE = WebPage(
    "SPY×FAMILY Code: White",
    "https://en.wikipedia.org/wiki/Spy_x_Family_Code:_White",
    "Fansubs search for it as SPY x FAMILY Code White. Group: Erai-raws",
)


class TestExternalContent:
    def test_free_text_taken_from_a_web_page_turns_it_into_a_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        tv, _ = seen_work(client)
        with_tavily(client, factory, PAGE)
        factory.rss_.pages[acgrip.search_url("SPY x FAMILY Code White")] = ACGRIP_FEED
        row = keyword_row(tv) | {"term": "SPY x FAMILY Code White"}
        script.steps = [
            call("web_tavily_search", query="SPY FAMILY movie fansub name"),
            tool("rss_subscribe_search", "s1", rows=[row]),
            say("Subscribed."),
        ]

        chat(client, "Subscribe the SPY×FAMILY film on nyaa, under whatever name fansubs use.")

        assert feeds(client) == []
        [proposal] = cards(client)
        assert proposal["command"] == "rss.subscribe_search"
        assert proposal["tool_call_id"] == "s1"
        assert proposal["preview"]["external_fields"] == [["term"]]

        pressed = decide(client, proposal["id"], approve=True)
        response = resume(client, tool_call_id="s1")

        assert pressed.json()["status"] == "executed"
        assert response.status_code == 200, response.text
        assert len(feeds(client)) == 1
        assert outcome_of_call(script, "s1")["executed"] is True

    def test_only_the_card_whose_text_came_from_the_page_is_marked(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        """研究〈實跑才抓到的問題〉第 6 點：讀過網頁之後的每一張卡都標，警示就沒有意義。"""
        submit = rows(client, 1)
        with_tavily(client, factory, PAGE)
        script.steps = [
            call("web_tavily_search", query="SPY FAMILY"),
            call("routes_list_routes"),
            add_feed_from_routes(URL, name="Erai-raws"),
        ]
        chat(client, f"Add {URL} and name it after the group that subs the film.")
        script.steps = [card(submit, tool_call_id="card-2")]
        script.seen.clear()
        chat(client, "Also download episode 1.")

        named, sending = cards(client)
        assert named["preview"]["external_fields"] == [["name"]]
        assert sending["preview"]["external_fields"] == [[]]


def outcome_of_call(script: Script, call_id: str) -> dict[str, Any]:
    content = returned(script.seen[-1], call_id).content
    assert isinstance(content, dict)
    return content


# ---------------------------------------------------------------- 預覽


class TestRefusedBeforeACard:
    def test_a_feed_without_a_movie_route_is_refused_before_the_card(
        self, client: TestClient, script: Script
    ) -> None:
        """prototype S5：電影 Route 沒給，是按了確認才被擋（`route_required`）。"""
        script.steps = [
            call("routes_list_routes"),
            add_feed_from_routes(URL, movies=False),
            say("Which route should films go to?"),
        ]

        chat(client, f"幫我加這個 RSS：{URL} ，劇集送 tv。")

        assert cards(client) == []
        assert refusal(script)["refused"] == "route_required"
        assert refusal(script)["detail"] == "movie"

    def test_a_series_subscribed_into_the_movie_route_is_refused_before_the_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        _, movies = seen_work(client)
        looked_up(client, {"id": 3310, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi")
        bangumi(factory, {583: 12})
        row = {"bangumi_id": 3310, "subgroup_id": 583, "media_id": SPY_ID, "route_id": movies}
        script.steps = [tool("rss_subscribe_mikan", rows=[row]), say("That route holds films.")]

        chat(client, "Subscribe it from Mikan.")

        assert cards(client) == []
        assert refusal(script)["refused"] == "route_kind_mismatch"
        assert refusal(script)["row"] == 0


# ---------------------------------------------------------------- 數量與磁碟閘


class TestHowManyOnOneCard:
    def test_rows_over_the_limit_wait_for_the_next_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        many = rows(client, *range(1, 16))
        # 模型照結果裡的 `held_back` 把剩下兩列提成下一張。
        script.steps = [card(many), card(many[13:], tool_call_id="card-2")]
        chat(client, "Download episodes 1 to 15.")

        [proposal] = cards(client)
        assert [row["source"]["title"] for row in proposal["arguments"]] == [
            f"[ANi] SPY×FAMILY - {episode:02d} [1080P]" for episode in range(1, 14)
        ]
        assert proposal["preview"]["held_back"] == 2

        decide(client, proposal["id"], approve=True)
        resume(client)

        outcome = outcome_of(script.seen[-1])
        assert len(outcome["rows"]) == 13
        assert outcome["held_back"]["rows"] == [13, 14]
        assert "new card" in outcome["held_back"]["note"]
        assert sent(factory) == [magnet(episode) for episode in range(1, 14)]
        first, second = cards(client)
        assert first["status"] == "executed"
        assert len(second["arguments"]) == 2
        assert second["preview"]["held_back"] == 0

    def test_the_disk_threshold_counts_the_rows_sent_before(
        self,
        client: TestClient,
        script: Script,
        factory: FakeClientFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """在途量（M4 票 03）：一張卡逐列送，前面送出的那幾列算在途。"""
        gib = 1024**3
        sources: SourceCache = client.app.state.sources  # type: ignore[attr-defined]  # app.state 是 Starlette 的動態屬性
        route = route_of(client, "tv")
        made = [
            {
                "source_id": sources.remember(
                    JobSource(url=magnet(episode), title=f"SPY - {episode:02d}", size=2 * gib)
                ),
                "media_id": SPY_ID,
                "route_id": route,
            }
            for episode in (1, 2)
        ]
        looked_up(client, {"rows": made})

        async def threshold(session: AsyncSession) -> None:
            await write_settings(session, DiskSettings(min_free_gb=1))
            await session.commit()

        in_db(client, threshold)
        monkeypatch.setattr(fs, "free_space", lambda _path: int(2.5 * gib))
        script.steps = [card(made), say("One sent.")]
        chat(client, "Download 1 and 2.")

        [proposal] = cards(client)
        pressed = decide(client, proposal["id"], approve=True).json()

        assert [(row["outcome"], row["reason"]) for row in pressed["results"]] == [
            ("done", ""),
            ("refused", "low_disk_space"),
        ]
        assert sent(factory) == [magnet(1)]


@pytest.fixture(autouse=True)
def _incomplete_root(roots: dict[str, Path]) -> Iterator[None]:
    """磁碟門檻量 Route 的未完成目錄，量不到不擋（`jobs._check_disk`）：建出來。"""
    roots["incomplete"].mkdir(parents=True, exist_ok=True)
    yield


class TestTorrentsOnOneCard:
    """數量閘數的是 torrent（協調者 2026-10-27）：一張卡的總數最多 13（送單一列 1 個，Mikan 訂閱照
    番組頁的集數）；單獨就超過 13 的一列、集數不知道的一列，自己一張。超出的退回給模型拆下一張。"""

    def propose(
        self,
        client: TestClient,
        script: Script,
        factory: FakeClientFactory,
        sizes: list[int | None],
    ) -> dict[str, Any]:
        """一列一個番組（3310 起），各一個字幕組 583、`sizes` 集；`None` 是番組頁上沒有字幕組。"""
        tv, _ = seen_work(client)
        ids = [3310 + index for index in range(len(sizes))]
        for bangumi_id, size in zip(ids, sizes, strict=True):
            bangumi(factory, {} if size is None else {583: size}, bangumi_id)
            looked_up(
                client, {"id": bangumi_id, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi"
            )
        script.steps = [
            tool(
                "rss_subscribe_mikan",
                rows=[
                    {
                        "bangumi_id": bangumi_id,
                        "subgroup_id": 583,
                        "media_id": SPY_ID,
                        "route_id": tv,
                    }
                    for bangumi_id in ids
                ],
            )
        ]
        chat(client, "Subscribe these from Mikan.")
        [proposal] = cards(client)
        return proposal

    def test_two_twelve_episode_seasons_do_not_share_a_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory, [12, 12])

        assert [row["bangumi_id"] for row in proposal["arguments"]] == [3310]
        assert proposal["preview"]["torrents"] == [12]
        assert proposal["preview"]["held_back"] == 1

    def test_a_season_over_the_limit_goes_on_a_card_alone(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory, [24])

        assert proposal["preview"]["torrents"] == [24]
        assert proposal["preview"]["held_back"] == 0

    def test_a_season_over_the_limit_does_not_join_another_row(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory, [1, 24])

        assert proposal["preview"]["torrents"] == [1]
        assert proposal["preview"]["held_back"] == 1

    def test_an_unknown_season_goes_alone(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        # 番組頁上沒有字幕組：數量要送出時才知道，當成超過。
        proposal = self.propose(client, script, factory, [None])

        assert proposal["preview"]["torrents"] == [None]
        assert proposal["preview"]["held_back"] == 0

    @pytest.mark.parametrize(("sizes", "kept"), [([None, 1], [3310]), ([1, None], [3310])])
    def test_an_unknown_season_does_not_share_a_card(
        self,
        client: TestClient,
        script: Script,
        factory: FakeClientFactory,
        sizes: list[int | None],
        kept: list[int],
    ) -> None:
        proposal = self.propose(client, script, factory, sizes)

        assert [row["bangumi_id"] for row in proposal["arguments"]] == kept
        assert proposal["preview"]["held_back"] == 1


# ---------------------------------------------------------------- 關鍵字訂閱的 Route（票 23b）


class TestTheRouteIsAskedOnACard:
    """多條可用 Route 就一定問（使用者，票 23b）：關鍵字訂閱（票 26 起一律出卡）在作品放得進的 Route
    不只一條時，卡上照送單卡的規則選 Route。"""

    def test_with_two_routes_and_no_default_the_card_asks_for_the_route(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        tv, _ = seen_work(client)
        serve_search(factory)
        script.steps = [tool("rss_subscribe_search", "s1", rows=[keyword_row(tv)]), say("Done.")]

        chat(client, "Subscribe it on acg.rip.")

        assert feeds(client) == []
        [proposal] = cards(client)
        assert proposal["command"] == "rss.subscribe_search"
        assert proposal["preview"]["external_fields"] == [[]]
        [ask] = proposal["preview"]["routes"]
        assert sorted(option["id"] for option in ask["options"]) == sorted(tv_routes(client))
        assert ask["preselected"] is None
        assert [t.outcome for t in recorded(client)[-1].tools] == ["proposed"]

        other = next(route for route in tv_routes(client) if route != tv)
        # 沒選 Route 按不下去（`routes=None`：不讓測試的 `decide` 替人選）。
        assert decide(client, proposal["id"], approve=True, routes=None).status_code == 422
        pressed = decide(client, proposal["id"], approve=True, routes=[other])
        response = resume(client, tool_call_id="s1")

        assert pressed.json()["status"] == "executed", pressed.text
        assert response.status_code == 200, response.text
        [feed] = feeds(client)
        # 送進卡片上選的那一條，不是模型給的。
        assert feed["tv_route_id"] == other


# ---------------------------------------------------------------- 字幕組（票 26）


def subscribed_series(client: TestClient) -> list[tuple[str, str | None, bool]]:
    """（鍵、作品、第一批確認了沒）。"""

    async def read(session: AsyncSession) -> list[tuple[str, str | None, bool]]:
        rows = await session.scalars(select(RssSeries).order_by(RssSeries.id))
        return [(row.key, row.media_id, row.confirmed) for row in rows]

    return in_db(client, read)


class TestTheMikanSubgroupIsPickedOnTheCard:
    """試用機上助理在 Mikan 自己挑了 ANi（2026-10-28）：番組頁上的字幕組都是卡上的選項，模型給的只是
    預選，伺服器只收清單裡的。"""

    def propose(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> dict[str, Any]:
        tv, _ = seen_work(client)
        used_before(client, tv)
        looked_up(
            client,
            {"id": 3310, "subgroups": [{"id": 583}, {"id": 584}]},
            tool="bangumi_read_bangumi",
        )
        bangumi(factory, {583: 12, 584: 3})
        row = {"bangumi_id": 3310, "subgroup_id": 583, "media_id": SPY_ID, "route_id": tv}
        script.steps = [tool("rss_subscribe_mikan", "m1", rows=[row]), say("Subscribed.")]
        chat(client, "Subscribe it from Mikan.")
        [proposal] = cards(client)
        return proposal

    def test_the_card_lists_the_pages_subgroups_with_the_models_pick_preselected(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory)

        [ask] = proposal["preview"]["subgroups"]
        assert ask["required"] is True
        assert ask["preselected"] == "583"
        assert [(o["key"], o["name"], o["releases"]) for o in ask["options"]] == [
            ("583", "Group 583", 12),
            ("584", "Group 584", 3),
        ]
        assert ask["options"][0]["latest"] == "[Group 583] SPY×FAMILY - 12"

    def test_it_cannot_be_confirmed_without_a_pick(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory)

        pressed = decide(client, proposal["id"], approve=True, subgroups=None)

        assert pressed.status_code == 422
        assert pressed.json()["detail"]["reason"] == "subgroup_required"
        assert feeds(client) == []

    def test_the_subgroup_picked_on_the_card_is_the_one_subscribed(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        season(factory, 3, 584)
        proposal = self.propose(client, script, factory)

        pressed = decide(client, proposal["id"], approve=True, subgroups=["584"])
        resume(client, tool_call_id="m1")

        assert pressed.json()["status"] == "executed", pressed.text
        [feed] = feeds(client)
        assert feed["url"] == mikan.bangumi_feed_url(3310, 584)
        assert [key for key, _, _ in subscribed_series(client)] == ["mikan:3310:584"]
        [row] = outcome_of_call(script, "m1")["rows"]
        assert row["subgroup_chosen_on_card"] == "Group 584"


class TestAKeywordSubscriptionIsACard:
    """關鍵字訂閱只綁一個字幕組、第一批在卡上確認（票 26）。試用機上它直接建，把搜到的每一個字幕組
    都綁上作品，各等第一批確認，使用者沒選過。"""

    def propose(
        self, client: TestClient, script: Script, factory: FakeClientFactory, subgroup: str = "ANi"
    ) -> dict[str, Any]:
        tv, _ = seen_work(client)
        used_before(client, tv)
        serve_search(factory)
        script.steps = [
            tool("rss_subscribe_search", "k1", rows=[keyword_row(tv, subgroup)]),
            say("Subscribed."),
        ]
        chat(client, "Subscribe it on acg.rip.")
        [proposal] = cards(client)
        return proposal

    def test_nothing_is_made_before_the_card_is_confirmed(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory)

        assert proposal["command"] == "rss.subscribe_search"
        assert proposal["preview"]["flags"] == ["downloads"]
        assert feeds(client) == []
        assert sent(factory) == []
        assert [t.outcome for t in recorded(client)[-1].tools] == ["proposed"]

    def test_the_card_lists_every_subgroup_and_its_first_batch(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory)

        [ask] = proposal["preview"]["subgroups"]
        assert ask["required"] is True
        assert ask["preselected"] == "ANi"
        by_name = {option["name"]: option for option in ask["options"]}
        assert {"ANi", "黒ネズミたち", "北宇治字幕组"} <= set(by_name)
        assert by_name["ANi"]["titles"] == [
            title for title in by_name["ANi"]["titles"] if title.startswith("[ANi]")
        ]
        assert len(by_name["ANi"]["titles"]) == by_name["ANi"]["releases"] == 2
        # 可以改選，所以數量閘看最多的那一組。
        assert proposal["preview"]["torrents"] == [max(o["releases"] for o in ask["options"])]

    def test_confirming_binds_only_the_picked_subgroup_and_downloads_its_first_batch(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        proposal = self.propose(client, script, factory)
        mouse = next(
            option
            for option in proposal["preview"]["subgroups"][0]["options"]
            if option["name"] == "黒ネズミたち"
        )

        pressed = decide(client, proposal["id"], approve=True, subgroups=["黒ネズミたち"])
        resume(client, tool_call_id="k1")

        assert pressed.json()["status"] == "executed", pressed.text
        [feed] = feeds(client)
        assert feed["primed_at"] is not None
        assert subscribed_series(client) == [
            ("title:kimigashinumadekoiwoshitai:黒ネズミたち", SPY_ID, True)
        ]
        # 這一組的 5 筆都送了（替身的 `.torrent` 各一個 hash 以外都是同一個，去重之後至少一筆）。
        assert sent(factory)
        items = client.get(f"/api/rss/feeds/{feed['id']}/preview").json()
        assert sorted(item["title"] for item in items) == sorted(mouse["titles"])
        [row] = outcome_of_call(script, "k1")["rows"]
        assert row["subgroup_chosen_on_card"] == "黒ネズミたち"

    def test_a_search_that_cannot_be_read_gets_no_card(
        self, client: TestClient, script: Script
    ) -> None:
        tv, _ = seen_work(client)
        used_before(client, tv)
        script.steps = [tool("rss_subscribe_search", rows=[keyword_row(tv)]), say("Down.")]

        chat(client, "Subscribe it on acg.rip.")

        assert cards(client) == []
        assert refusal(script)["refused"] == "feed_unreachable"

    def test_the_model_must_name_a_subgroup(self, client: TestClient, script: Script) -> None:
        tv, _ = seen_work(client)
        row = {k: v for k, v in keyword_row(tv).items() if k != "subgroup"}
        script.steps = [tool("rss_subscribe_search", rows=[row]), say("Which subgroup?")]

        chat(client, "Subscribe it on acg.rip.")

        assert cards(client) == []
        assert "subgroup" in json.dumps(refusal(script), ensure_ascii=False)


class TestExistingSubscriptionsAreSaid:
    """同一部作品兩份訂閱（試用機：acg.rip 的還在，又在 Mikan 訂了一份）：訂閱之前說出來，
    由人決定。"""

    def test_the_card_and_its_outcome_name_the_subscription_the_work_already_has(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        tv, _ = seen_work(client)
        used_before(client, tv)
        serve_search(factory)
        script.steps = [tool("rss_subscribe_search", "k1", rows=[keyword_row(tv)]), say("Done.")]
        chat(client, "Subscribe it on acg.rip.")
        [first] = cards(client)
        decide(client, first["id"], approve=True)
        resume(client, tool_call_id="k1")
        [feed] = feeds(client)

        looked_up(client, {"id": 3310, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi")
        bangumi(factory, {583: 12})
        row = {"bangumi_id": 3310, "subgroup_id": 583, "media_id": SPY_ID, "route_id": tv}
        script.steps = [tool("rss_subscribe_mikan", "m1", rows=[row]), say("Done.")]
        script.seen.clear()
        chat(client, "Also subscribe it from Mikan.")

        second = next(card for card in cards(client) if card["command"] == "rss.subscribe_mikan")
        said = {"feed_id": feed["id"], "name": feed["name"], "kind": "acgrip", "subgroup": "ANi"}
        assert second["preview"]["existing"] == [[said]]
        season(factory, 12)
        decide(client, second["id"], approve=True)
        resume(client, tool_call_id="m1")
        [outcome] = outcome_of_call(script, "m1")["rows"]
        assert outcome["existing_subscriptions"] == [said]

    def test_a_work_with_no_subscription_says_nothing(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        tv, _ = seen_work(client)
        used_before(client, tv)
        serve_search(factory)
        script.steps = [tool("rss_subscribe_search", rows=[keyword_row(tv)])]

        chat(client, "Subscribe it on acg.rip.")

        [proposal] = cards(client)
        assert proposal["preview"]["existing"] == []


class TestDeletingASubscription:
    """試用機上助理沒有刪訂閱的工具，只能說「留著」（票 26）：`delete_feed` 是工具，不可逆
    所以出卡。"""

    def test_it_is_a_card_and_confirming_deletes_the_feed(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        tv, _ = seen_work(client)
        used_before(client, tv)
        serve_search(factory)
        script.steps = [tool("rss_subscribe_search", "k1", rows=[keyword_row(tv)]), say("Done.")]
        chat(client, "Subscribe it on acg.rip.")
        [made] = cards(client)
        decide(client, made["id"], approve=True)
        resume(client, tool_call_id="k1")
        [feed] = feeds(client)

        script.steps = [
            call("rss_list_subscriptions", media_id=SPY_ID),
            tool("rss_delete_feed", "d1", rows=[{"feed_id": feed["id"]}]),
            say("Deleted."),
        ]
        script.seen.clear()
        chat(client, "Delete that acg.rip subscription.")

        gone = next(card for card in cards(client) if card["command"] == "rss.delete_feed")
        assert gone["preview"]["effect"] == "irreversible"
        assert len(feeds(client)) == 1
        pressed = decide(client, gone["id"], approve=True)
        resume(client, tool_call_id="d1")

        assert pressed.json()["status"] == "executed", pressed.text
        assert feeds(client) == []
        # 綁定留著（作品還在、RSS Series 還綁著它）。
        assert [media for _, media, _ in subscribed_series(client)] == [SPY_ID]

    def test_a_feed_id_no_tool_returned_gets_no_card(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [tool("rss_delete_feed", rows=[{"feed_id": 41}]), say("Which one?")]

        chat(client, "Delete feed 41.")

        assert refusal(script)["refused"] == "id_not_from_results"
        assert cards(client) == []
