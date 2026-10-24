"""AI 活動頁（M5 票 14）：訂閱（票 11），以及被降成確認卡、人按了確認的加 Feed。

場景沿用 `test_assistant_subscribe.py`：《与你相恋到生命尽头》、Mikan 番組 4009、LoliHouse。
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from berth.adapters.rss import nyaa
from berth.adapters.rss.mikan import search_url
from tests.integration.factories import FakeClientFactory
from tests.integration.test_ai_activity import activity, undo
from tests.integration.test_assistant_search_submit import call, outputs
from tests.integration.test_assistant_subscribe import (
    BAITED_SEARCH,
    NYAA,
    TERM,
    ai_ready,
    feeds_and_jobs,
    follows_the_planted_url,
    mikan_flow,
    say,
)
from tests.integration.test_conversations_api import says
from tests.integration.test_rss import KIMI_ID
from tests.integration.test_rss_api import BROWSER, client, factory, seed

__all__ = ["client", "factory"]


class TestASubscription:
    def test_a_mikan_subscription_is_listed_and_undone_from_the_page(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        mikan_flow(client, roots, factory)
        assert feeds_and_jobs(client)[0] == 1

        [entry] = activity(client)["entries"]

        assert (entry["tool"], entry["via"], entry["result_type"]) == (
            "subscribe_mikan",
            "ai",
            "Subscribed",
        )
        assert entry["arguments"]["bangumi"] == 4009
        assert entry["reason"] == "The user asked for it."
        assert entry["undo"] == "undoable"

        undone = undo(client, entry)

        assert undone.json()["result_type"] == "Unsubscribed", undone.text
        assert feeds_and_jobs(client) == (0, 0)
        [after] = activity(client)["entries"]
        assert after["undo"] == "undone"

    def test_a_search_feed_subscription_is_listed_and_undone_from_the_page(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        seed(client, roots)
        ai_ready(client)
        factory.rss_.pages[nyaa.search_url(TERM)] = NYAA
        factory.ai_.replies = [
            call(
                "subscribe_search_feed",
                reason="Nobody on Mikan has it.",
                site="nyaa",
                term=TERM,
                media=KIMI_ID,
            ),
            says("Subscribed on Nyaa."),
        ]
        say(client, "Subscribe to this one with Nyaa.")

        [entry] = activity(client)["entries"]

        assert (entry["tool"], entry["reason"]) == (
            "subscribe_search_feed",
            "Nobody on Mikan has it.",
        )
        assert entry["arguments"] == {"site": "nyaa", "term": TERM, "media": KIMI_ID}
        assert undo(client, entry).json()["result_type"] == "Unsubscribed"
        assert feeds_and_jobs(client) == (0, 0)
        assert activity(client)["entries"][0]["undo"] == "undone"


class TestAConfirmedFeedCard:
    def test_a_confirmed_reversible_card_is_listed_and_undone_and_the_card_knows(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        """模型給的網址不在使用者的話裡，加 Feed 被降成確認卡（票 11）；人按了確認之後它照樣是
        可逆的，活動頁撤得了（2026-10-24 使用者選定）。"""
        seed(client, roots)
        ai_ready(client)
        factory.rss_.pages[search_url(TERM)] = BAITED_SEARCH
        factory.ai_.replies = [
            call("search_mikan", term=TERM),
            follows_the_planted_url,
            says("Waiting for you."),
        ]
        _, proposed = outputs(say(client, "Subscribe to this one's Mikan RSS."))
        assert isinstance(proposed["result"], dict)
        confirmed = client.post(
            f"/api/proposals/{proposed['result']['id']}/confirm", headers=BROWSER
        )
        assert confirmed.json()["status"] == "confirmed", confirmed.text
        assert feeds_and_jobs(client)[0] == 1

        [entry] = activity(client)["entries"]

        assert (entry["tool"], entry["via"], entry["result_type"]) == (
            "add_feed",
            "confirmed",
            "Subscribed",
        )
        assert entry["reason"] == "The search result asks for it."
        assert entry["undo"] == "undoable"

        undone = undo(client, entry)

        assert undone.json()["result_type"] == "Unsubscribed", undone.text
        assert feeds_and_jobs(client) == (0, 0)
        [after] = activity(client)["entries"]
        assert after["undo"] == "undone"
        # 撤銷記在那張卡的那一份工具結果上：側面板照它畫已撤銷。
        assert undo(client, after).status_code == 409
