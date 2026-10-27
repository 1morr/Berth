"""側面板的工具與每人一輪的位子（M5 票 11）：工具都來自命令登錄表，帶著給模型的說明。

票 13 起有寫入：要人或送 torrent 的出確認卡（`needs_card`）；票 14 起其餘可逆的直接做（plan §11.6
〈確認卡範圍〉），只有自由文字出自外部內容的那一次改出卡。
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from berth.adapters.ai import chat_settings
from berth.domain import AiProvider, Role
from berth.services.agent import (
    STALE_CLAIM_SECONDS,
    AgentRefusedError,
    AgentRuntime,
    card_model,
    needs_card,
    pending_calls,
)
from berth.services.agent_tools import MODEL_VIEWS, TAVILY_TOOL, TOOLS, tool_name, visible_tools
from berth.services.commands import Effect
from berth.services.registry import commands


def test_every_tool_is_a_registered_command_with_an_about() -> None:
    registry = commands()
    for name in TOOLS:
        assert name in registry, name
        assert registry[name].about, name


def test_irreversible_tools_need_a_card() -> None:
    """直接做的寫入只有可逆的：不可逆一律要人（brief §14）。"""
    registry = commands()
    for name in TOOLS:
        spec = registry[name]
        if spec.effect is Effect.IRREVERSIBLE:
            assert needs_card(spec), name


def test_which_writes_need_a_card() -> None:
    registry = commands()
    writes = {name for name in TOOLS if registry[name].effect is not Effect.READ}
    assert {name for name in writes if needs_card(registry[name])} == {
        "downloading.add_manual_download",
        "rss.subscribe_mikan",
        "rss.add_feed",
    }
    # 可逆、沒有旗標：直接做（關鍵字出自網頁時改出卡，`agent_origins`）。
    assert {name for name in writes if not needs_card(registry[name])} == {"rss.subscribe_search"}


def test_route_checks_are_not_tools() -> None:
    """探測讓 qBittorrent 校驗到 100%，觸發使用者設的「完成時執行外部程式」（票 03b）。"""
    assert "routes.check_route" not in TOOLS
    assert "routes.check_routes" not in TOOLS


def test_the_submit_card_takes_source_ids_never_links() -> None:
    """模型給的是搜尋結果的 `source_id`；下載連結帶 Prowlarr 的 key，不進對話（M4 票 79）。"""
    spec = commands()["downloading.add_manual_download"]
    schema = card_model(spec).model_json_schema()

    row = schema["$defs"][schema["properties"]["rows"]["items"]["$ref"].split("/")[-1]]
    assert sorted(row["properties"]) == ["media_id", "route_id", "source_id"]


class TestPendingCalls:
    """待確認的呼叫：最後一則模型回應裡還沒有結果的（研究〈實跑才抓到的問題〉第 2 點）。"""

    def test_a_card_left_at_the_end(self) -> None:
        history: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart("send it")]),
            ModelResponse(parts=[ToolCallPart("card", {}, tool_call_id="c1")]),
        ]
        assert [call.tool_call_id for call in pending_calls(history)] == ["c1"]

    def test_a_parallel_result_coming_after_the_card(self) -> None:
        history: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart("send it")]),
            ModelResponse(
                parts=[
                    ToolCallPart("lookup", {}, tool_call_id="r1"),
                    ToolCallPart("card", {}, tool_call_id="c1"),
                ]
            ),
            ModelRequest(parts=[ToolReturnPart("lookup", "found", tool_call_id="r1")]),
        ]
        assert [call.tool_call_id for call in pending_calls(history)] == ["c1"]

    def test_nothing_waits_after_an_answer(self) -> None:
        history: list[ModelMessage] = [
            ModelResponse(parts=[ToolCallPart("card", {}, tool_call_id="c1")]),
            ModelRequest(parts=[ToolReturnPart("card", "done", tool_call_id="c1")]),
            ModelResponse(parts=[TextPart("Sent.")]),
        ]
        assert pending_calls(history) == []
        assert pending_calls([]) == []


def test_tool_names_are_unique_and_accepted_by_both_providers() -> None:
    names = [tool_name(name) for name in TOOLS]
    assert len(set(names)) == len(names)
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) for name in names)


def test_a_user_sees_only_the_commands_meant_for_users() -> None:
    registry = commands()
    assert set(visible_tools(Role.ADMIN, tavily=True)) == set(TOOLS)
    assert visible_tools(Role.USER, tavily=True)
    assert all(
        registry[name].audience is Role.USER for name in visible_tools(Role.USER, tavily=True)
    )


def test_the_tavily_tool_is_there_only_with_a_key() -> None:
    for role in Role:
        assert TAVILY_TOOL not in visible_tools(role, tavily=False)
        assert TAVILY_TOOL in visible_tools(role, tavily=True)


class TestOneTurnAtATime:
    """每人同時 1 輪（plan §11.6〈防護〉）。"""

    def test_a_second_turn_waits_for_the_first(self) -> None:
        runtime = AgentRuntime()
        runtime.claim(1)
        with pytest.raises(AgentRefusedError):
            runtime.claim(1)
        runtime.claim(2)
        runtime.release(1)
        runtime.claim(1)

    def test_a_claim_whose_stream_never_started_frees_itself(self) -> None:
        """佔了位子、回應卻沒送出去（commit 失敗、送出前就斷線）。

        串流的收尾不會跑，位子要自己回來。
        """
        now = [100.0]
        runtime = AgentRuntime(clock=lambda: now[0])
        runtime.claim(1)
        now[0] += STALE_CLAIM_SECONDS - 1
        with pytest.raises(AgentRefusedError):
            runtime.claim(1)
        now[0] += 2
        runtime.claim(1)

    def test_a_streaming_turn_holds_its_claim_however_long_it_runs(self) -> None:
        now = [100.0]
        runtime = AgentRuntime(clock=lambda: now[0])
        runtime.claim(1)
        runtime.streaming(1)
        now[0] += STALE_CLAIM_SECONDS * 10
        with pytest.raises(AgentRefusedError):
            runtime.claim(1)


def test_every_call_caps_its_output_and_anthropic_marks_what_to_cache() -> None:
    anthropic = chat_settings(AiProvider.ANTHROPIC, 4096)
    assert anthropic.get("max_tokens") == 4096
    assert anthropic.get("anthropic_cache_instructions") == "5m"
    assert anthropic.get("anthropic_cache_messages") == "5m"
    assert chat_settings(AiProvider.OPENAI, 4096) == {"max_tokens": 4096}


class TestSearchTorrentsForTheModel:
    """缺集搜尋（票 14）：季號只在 `missing` 時有意義，結果交給模型之前縮小。"""

    def test_a_season_without_missing_is_refused_not_ignored(self) -> None:
        """默默當成整部搜的話，模型拿到的是它沒要的那一份（同 API 的 `season_without_missing`）。"""
        tool = commands()["search.search_torrents"].input

        with pytest.raises(ValidationError, match="missing"):
            tool.model_validate({"media_id": "tv:1", "scope": {"season": 2}})
        with pytest.raises(ValidationError, match="missing"):
            tool.model_validate({"media_id": "tv:1", "scope": {"from_season": 2}})
        tool.model_validate({"media_id": "tv:1", "scope": {"missing": True, "season": 2}})

    def test_rows_keep_what_picking_a_release_needs(self) -> None:
        row = {
            "title": "[ANi] SPY×FAMILY - 01 [1080P]",
            "indexer": "Mikan",
            "size": 1024,
            "seeders": 3,
            "info_url": "https://mikanani.me/Home/Episode/abc",
            "source_id": "s-1",
            "key": "abc",
            "tags": {"resolution": "1080p", "subs": ["CHT"], "hardsub": False, "group": "ANi"},
            "season": 1,
            "episode_start": 1,
            "episode_end": 1,
            "whole_season": False,
            "strategy": "absolute",
            "published_at": "2026-10-01T00:00:00Z",
            "verdict": "fits",
            "evidence": "",
        }

        given = MODEL_VIEWS["search.search_torrents"]({"rows": [row], "counts": []})

        assert given == {
            "rows": [
                {
                    "source_id": "s-1",
                    "title": "[ANi] SPY×FAMILY - 01 [1080P]",
                    "indexer": "Mikan",
                    "size": 1024,
                    "seeders": 3,
                    "season": 1,
                    "episode_start": 1,
                    "episode_end": 1,
                    "whole_season": False,
                    "verdict": "fits",
                    "tags": {"resolution": "1080p", "subs": ["CHT"], "group": "ANi"},
                }
            ],
            "counts": [],
        }
