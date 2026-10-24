"""AI 活動頁（M5 票 14，`.scratch/m5/ai-activity-shape.md`）：送單（票 12）與確認卡（票 10）。

`GET /api/ai-activity` 從對話本身撈（工具結果、確認卡、撤銷），不另寫日誌。斷言走 HTTP：
頁面上列得出何時、代誰、哪個工具、輸入、理由、這次回覆的 tokens、出自哪則對話；撤銷走結果卡
同一支端點，撤了之後那一列說已撤銷。訂閱（票 11）在 `test_ai_activity_rss.py`。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from berth.adapters.ai import TurnEnded, Usage
from berth.services import ai_activity
from tests.integration.factories import FakeClientFactory
from tests.integration.test_ai_settings_api import BROWSER
from tests.integration.test_assistant_search_submit import (
    call,
    first_sendable,
    indexer,
    outputs,
    submits,
)
from tests.integration.test_conversations_api import ai_ready, says, send
from tests.integration.test_media import SPY_ID
from tests.integration.test_search_api import ADMIN, CREW, client, factory, sign_in

__all__ = ["client", "factory", "indexer"]


def spent(turn: TurnEnded, tokens: int) -> TurnEnded:
    """那一次呼叫回報的用量：輸入 `tokens`、輸出十分之一。"""
    return replace(turn, usage=Usage(input_tokens=tokens, output_tokens=tokens // 10))


def submit_flow(client: TestClient, factory: FakeClientFactory, text: str) -> int:
    """缺集 → 搜尋 → 送單，回這則對話的 id。每一次模型呼叫 100 個輸入 tokens。"""

    def submit(request: Any) -> TurnEnded:
        return spent(submits(first_sendable)(request), 100)

    factory.ai_.replies = [
        spent(call("missing_episodes", media=SPY_ID), 100),
        spent(call("search_indexers", media=SPY_ID, season=2), 100),
        submit,
        spent(says("Sent."), 100),
    ]
    streamed = send(client, text)
    assert [o["outcome"] for o in outputs(streamed)] == ["done", "done", "done"]
    conversation = streamed[0]["conversation_id"]
    assert isinstance(conversation, int)
    return conversation


def activity(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/ai-activity")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def undo(client: TestClient, entry: dict[str, Any]) -> Any:
    """活動頁上那一列的撤銷：與結果卡同一支端點，位址是那一列帶著的。"""
    return client.post(
        f"/api/conversations/{entry['conversation_id']}/messages/{entry['message_id']}"
        f"/tools/{entry['call_id']}/undo",
        headers=BROWSER,
    )


class TestASubmit:
    def test_who_when_which_tool_why_and_what_the_reply_cost(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        conversation = submit_flow(client, factory, "Download the missing season 2.")

        body = activity(client)

        # 讀取的工具（缺集、搜尋）不列：這一頁是寫入。
        [entry] = body["entries"]
        assert body["truncated"] is False
        assert (entry["tool"], entry["via"], entry["result_type"]) == (
            "submit_search_result",
            "ai",
            "SubmittedJob",
        )
        assert (entry["conversation_id"], entry["own"]) == (conversation, True)
        assert entry["conversation_title"] == "Download the missing season 2."
        assert entry["user_name"] == ADMIN["username"]
        assert entry["reason"] == "The user asked for it."
        # 輸入照模型給的，理由另外一格、不重複。
        assert entry["arguments"]["media"] == SPY_ID
        assert "source_id" in entry["arguments"] and "reason" not in entry["arguments"]
        # 這次回覆的四次模型呼叫加總。
        assert entry["tokens"] == {"input": 400, "output": 40}
        assert entry["undo"] == "undoable" and entry["undone_at"] is None

    def test_a_reply_with_a_call_that_reported_nothing_is_unknown_not_a_smaller_sum(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """一次回覆裡有一次呼叫沒回報用量：加起來只是一部分，說不知道，不印一個看起來像總數的數。"""
        ai_ready(client)
        factory.ai_.replies = [
            spent(call("missing_episodes", media=SPY_ID), 100),
            call("search_indexers", media=SPY_ID, season=2),
            lambda request: spent(submits(first_sendable)(request), 100),
            spent(says("Sent."), 100),
        ]
        send(client, "Download the missing season 2.")

        [entry] = activity(client)["entries"]

        assert entry["tokens"] == {"input": None, "output": None}

    def test_undone_from_the_page_the_job_is_gone_and_the_entry_says_so(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        submit_flow(client, factory, "Download the missing season 2.")
        [entry] = activity(client)["entries"]
        name = entry["result"]["hash"]

        undone = undo(client, entry)

        assert undone.status_code == 200, undone.text
        assert undone.json()["result_type"] == "SubmissionUndone", undone.text
        assert client.get(f"/api/jobs/{name}").status_code == 404
        [after] = activity(client)["entries"]
        assert after["undo"] == "undone" and after["undone_at"] is not None
        # 同一筆不撤第二次。
        assert undo(client, after).status_code == 409

    def test_only_the_newest_are_listed_and_it_says_more_are_older(
        self, client: TestClient, factory: FakeClientFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ai_activity, "LIMIT", 1)
        ai_ready(client)
        submit_flow(client, factory, "First.")
        submit_flow(client, factory, "Second.")

        body = activity(client)

        assert [e["conversation_title"] for e in body["entries"]] == ["Second."]
        assert body["truncated"] is True


class TestEachPersonsOwn:
    def test_a_user_sees_only_their_own_and_an_admin_sees_everyones(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        submit_flow(client, factory, "Admin's download.")
        sign_in(client, CREW)
        submit_flow(client, factory, "Crew's download.")

        theirs = activity(client)["entries"]
        assert [(e["user_name"], e["conversation_title"]) for e in theirs] == [
            (CREW["username"], "Crew's download.")
        ]
        # 送單撤銷是刪 Job，只有管理員（票 12）：一般使用者看得到這一筆、按不到。
        assert theirs[0]["undo"] == "not_allowed"

        sign_in(client)
        everyone = activity(client)["entries"]
        # 新的在前；別人的對話不是你的，連不過去。
        assert [(e["user_name"], e["own"]) for e in everyone] == [
            (CREW["username"], False),
            (ADMIN["username"], True),
        ]

    def test_an_admin_undoes_someone_elses_and_their_conversation_knows(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        sign_in(client, CREW)
        conversation = submit_flow(client, factory, "Crew's download.")
        sign_in(client)
        [entry] = activity(client)["entries"]

        assert undo(client, entry).status_code == 200

        sign_in(client, CREW)
        [after] = activity(client)["entries"]
        assert after["undo"] == "undone"
        kinds = [
            m["kind"] for m in client.get(f"/api/conversations/{conversation}").json()["messages"]
        ]
        assert kinds[-1] == "decision"

    def test_a_user_cannot_undo_even_their_own_submit(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        sign_in(client, CREW)
        submit_flow(client, factory, "Crew's download.")
        [entry] = activity(client)["entries"]

        assert undo(client, entry).status_code == 403


class TestConfirmedCards:
    def test_a_confirmed_irreversible_card_is_listed_without_an_undo(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """確認卡由人按、以他執行（票 10）：照樣是 AI 提出的寫入，列出來；不可逆的沒有反向命令。
        被拒絕的卡什麼都沒做，不列。"""
        ai_ready(client)
        factory.ai_.replies = [
            call("add_indexer", site="nyaasi", reason="For anime."),
            says("Press confirm."),
            call("add_indexer", site="dmhy", reason="Also this."),
            says("Press confirm."),
        ]
        first = send(client, "add nyaa")
        [card] = outputs(first)
        assert isinstance(card["result"], dict)
        confirmed = client.post(f"/api/proposals/{card['result']['id']}/confirm", headers=BROWSER)
        assert confirmed.json()["status"] == "confirmed", confirmed.text
        conversation = first[0]["conversation_id"]
        assert isinstance(conversation, int)
        [other] = outputs(send(client, "and dmhy", conversation))
        assert isinstance(other["result"], dict)
        client.post(f"/api/proposals/{other['result']['id']}/reject", headers=BROWSER)

        [entry] = activity(client)["entries"]

        assert (entry["tool"], entry["via"], entry["reason"]) == (
            "add_indexer",
            "confirmed",
            "For anime.",
        )
        assert entry["arguments"] == {"site": "nyaasi"}
        assert entry["undo"] == "no_inverse"


class TestGate:
    def test_signed_out_gets_nothing(self, client: TestClient) -> None:
        assert client.get("/api/ai-activity").status_code == 401

    def test_nothing_yet_is_an_empty_list(self, client: TestClient) -> None:
        sign_in(client, CREW)
        assert activity(client) == {"entries": [], "truncated": False}
