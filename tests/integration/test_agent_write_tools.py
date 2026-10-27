"""側面板的寫入工具與守法（M5 票 14、plan §11.6〈分段〉第 5 段、brief §14〈對話裡的確認卡〉）。

模型是 `FakeAi` 的腳本：它照腳本叫工具，測的是 Berth 擋不擋、出不出卡。

- id 必須出自這段對話已存的工具結果：`TestIdsComeFromToolResults`
- 網址必須逐字出自使用者的話：`TestAddressesComeFromTheUser`（prototype S5 / S6）
- 「讀過外部內容」只標在自由文字出自外部內容的卡：`TestExternalContent`
- 預覽理由在出卡之前擋下（`route_required`、`route_kind_mismatch`）：`TestRefusedBeforeACard`
- 送單的數量與磁碟閘（R5）：`TestHowManyOnOneCard`
"""

from __future__ import annotations

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
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.rss import mikan
from berth.adapters.websearch import WebPage
from berth.config import Config
from berth.models import DiskSettings
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
            tool(
                "rss_subscribe_search", kind="nyaa", term="SPY×FAMILY", media_id=SPY_ID, route_id=99
            ),
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
        season(factory, 12)
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
        season(factory, 12)

        proposal = self.subscribe(client, script)

        assert proposal["preview"]["torrents"] == [12]
        # 只讀：什麼都還沒送、也沒建 Feed。
        assert sent(factory) == []
        assert feeds(client) == []

    def test_a_season_that_cannot_be_read_yet_is_unknown_not_zero(
        self, client: TestClient, script: Script
    ) -> None:
        proposal = self.subscribe(client, script)

        assert proposal["preview"]["torrents"] == [None]

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
    def test_a_reversible_write_runs_directly(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        """可逆、沒有旗標的寫入直接做（plan §11.6〈確認卡範圍〉）：關鍵字是使用者說的。"""
        tv, _ = seen_work(client)
        script.steps = [
            tool(
                "rss_subscribe_search",
                "s1",
                kind="nyaa",
                term="SPY×FAMILY",
                media_id=SPY_ID,
                route_id=tv,
            ),
            say("Subscribed."),
        ]

        chat(client, "Subscribe SPY×FAMILY on nyaa.")

        assert cards(client) == []
        [feed] = feeds(client)
        assert feed["kind"] == "nyaa"
        assert [t.outcome for t in recorded(client)[-1].tools] == ["ok"]

    def test_free_text_taken_from_a_web_page_turns_it_into_a_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        tv, _ = seen_work(client)
        with_tavily(client, factory, PAGE)
        script.steps = [
            call("web_tavily_search", query="SPY FAMILY movie fansub name"),
            tool(
                "rss_subscribe_search",
                "s1",
                kind="nyaa",
                term="SPY x FAMILY Code White",
                media_id=SPY_ID,
                route_id=tv,
            ),
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
        self, client: TestClient, script: Script
    ) -> None:
        _, movies = seen_work(client)
        looked_up(client, {"id": 3310, "subgroups": [{"id": 583}]}, tool="bangumi_read_bangumi")
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
    預覽的集數）；單獨就超過 13 的一列、讀不到集數的一列，自己一張。超出的退回給模型拆下一張。"""

    def propose(self, client: TestClient, script: Script, subgroups: list[int]) -> dict[str, Any]:
        tv, _ = seen_work(client)
        looked_up(
            client,
            {"id": 3310, "subgroups": [{"id": subgroup} for subgroup in subgroups]},
            tool="bangumi_read_bangumi",
        )
        script.steps = [
            tool(
                "rss_subscribe_mikan",
                rows=[
                    {
                        "bangumi_id": 3310,
                        "subgroup_id": subgroup,
                        "media_id": SPY_ID,
                        "route_id": tv,
                    }
                    for subgroup in subgroups
                ],
            )
        ]
        chat(client, "Subscribe these from Mikan.")
        [proposal] = cards(client)
        return proposal

    def test_two_twelve_episode_seasons_do_not_share_a_card(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        season(factory, 12, 583)
        season(factory, 12, 584)

        proposal = self.propose(client, script, [583, 584])

        assert [row["subgroup_id"] for row in proposal["arguments"]] == [583]
        assert proposal["preview"]["torrents"] == [12]
        assert proposal["preview"]["held_back"] == 1

    def test_a_season_over_the_limit_goes_on_a_card_alone(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        season(factory, 24, 583)

        proposal = self.propose(client, script, [583])

        assert proposal["preview"]["torrents"] == [24]
        assert proposal["preview"]["held_back"] == 0

    def test_a_season_over_the_limit_does_not_join_another_row(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        season(factory, 1, 583)
        season(factory, 24, 584)

        proposal = self.propose(client, script, [583, 584])

        assert proposal["preview"]["torrents"] == [1]
        assert proposal["preview"]["held_back"] == 1

    def test_an_unknown_season_goes_alone(
        self, client: TestClient, script: Script, factory: FakeClientFactory
    ) -> None:
        # 584 讀不到：數量要送出時才知道，當成超過。
        proposal = self.propose(client, script, [584])

        assert proposal["preview"]["torrents"] == [None]
        assert proposal["preview"]["held_back"] == 0

    @pytest.mark.parametrize(("subgroups", "kept"), [([584, 583], [584]), ([583, 584], [583])])
    def test_an_unknown_season_does_not_share_a_card(
        self,
        client: TestClient,
        script: Script,
        factory: FakeClientFactory,
        subgroups: list[int],
        kept: list[int],
    ) -> None:
        season(factory, 1, 583)

        proposal = self.propose(client, script, subgroups)

        assert [row["subgroup_id"] for row in proposal["arguments"]] == kept
        assert proposal["preview"]["held_back"] == 1
