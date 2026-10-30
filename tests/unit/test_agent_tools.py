"""側面板的工具與每人一輪的位子（M5 票 11）：工具都來自命令登錄表，帶著給模型的說明。

票 13 起有寫入：要人或送 torrent 的出確認卡（`needs_card`）；票 14 起其餘可逆的直接做（plan §11.6
〈確認卡範圍〉），只有自由文字出自外部內容的那一次改出卡。
"""

from __future__ import annotations

import re
from datetime import date, timedelta

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
    """每一支寫入工具都出卡（M5 票 26 起關鍵字訂閱也是：字幕組要人選、第一批在卡上確認）。"""
    registry = commands()
    writes = {name for name in TOOLS if registry[name].effect is not Effect.READ}
    assert writes == {
        "downloading.add_manual_download",
        "rss.subscribe_mikan",
        "rss.subscribe_search",
        "rss.add_feed",
        "rss.delete_feed",
    }
    assert all(needs_card(registry[name]) for name in writes)


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
        runtime.claim(1, "c1")
        with pytest.raises(AgentRefusedError):
            runtime.claim(1, "c1")
        runtime.claim(2, "c1")
        runtime.release(1)
        runtime.claim(1, "c1")


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
                    # 票 26：模型要算得出各字幕組多久出一集。
                    "published_at": "2026-10-01T00:00:00Z",
                }
            ],
            "counts": [],
        }

    def test_only_the_first_rows_reach_the_model_and_it_is_told_how_many_more(self) -> None:
        """票 23d 實跑：找種子那一輪搜了 19 次、13 次被截在 12,000 字，每次呼叫多約 7K input，
        Re:Zero 撞到每輪 400K。列已照「符合」在前排好，`counts` 有各類的總數；給模型前幾列就夠，
        要更準的用 `query` 再搜。"""
        rows = [
            {"source_id": f"s-{n}", "title": f"[Grp] Show - {n:02d} [1080p]", "verdict": verdict}
            for n, verdict in enumerate(["fits"] * 12 + ["other"] * 30, start=1)
        ]

        given = MODEL_VIEWS["search.search_torrents"]({"rows": rows, "counts": []})

        assert isinstance(given, dict)
        assert [row["source_id"] for row in given["rows"]] == [f"s-{n}" for n in range(1, 11)]
        assert given["rows_not_shown"] == 32

    def test_later_rows_come_in_only_for_episodes_not_yet_shown(self) -> None:
        """補缺集一季只搜一次：前 10 列沒蓋到的集，後面「符合」的列照樣給；重複的、不符合的不給。"""

        def row(
            n: int, start: int, *, verdict: str = "fits", whole: bool = False
        ) -> dict[str, object]:
            return {
                "source_id": f"s-{n}",
                "verdict": verdict,
                "season": 1,
                "episode_start": None if whole else start,
                "episode_end": None if whole else start,
                "whole_season": whole,
            }

        first_ten = [row(n, 1 + n % 5) for n in range(10)]  # 只蓋第 1–5 集
        later = [
            row(10, 3),  # 第 3 集已經有了
            row(11, 6),  # 新的
            row(12, 7, verdict="other"),  # 不符合
            row(13, 6),  # 第 6 集剛剛有了
            row(14, 0, whole=True),  # 整季包：新的
            row(15, 8),  # 整季包已經蓋到
        ]

        given = MODEL_VIEWS["search.search_torrents"]({"rows": first_ten + later, "counts": []})

        assert isinstance(given, dict)
        shown = [r["source_id"] for r in given["rows"]]
        assert shown == [f"s-{n}" for n in range(10)] + ["s-11", "s-14"]
        assert given["rows_not_shown"] == 4

    def test_a_short_search_is_given_whole(self) -> None:
        rows = [{"source_id": "s-1", "title": "x", "verdict": "fits"}]
        given = MODEL_VIEWS["search.search_torrents"]({"rows": rows, "counts": []})
        assert isinstance(given, dict)
        assert "rows_not_shown" not in given


class TestWhatTheModelSeesOfAWork:
    """`media.read_media` 給模型的那一份（票 16）：逐集換成狀態 → 集數範圍。"""

    def test_episodes_become_ranges_per_status_and_jobs_stay(self) -> None:
        statuses = ["imported"] * 3 + ["missing", "imported", "downloading", "unaired"]
        episodes = [
            {
                "episode_number": n,
                "name": f"E{n}",
                "status": s,
                "job": "abc" if s == "downloading" else None,
            }
            for n, s in enumerate(statuses, start=1)
        ]
        work = {
            "id": "tv:1",
            "poster_url": "https://image.tmdb.org/x.jpg",
            "seasons": [{"season_number": 1, "episode_count": 7, "episodes": episodes}],
            "files": [
                {
                    "season": 1,
                    "episode_start": 1,
                    "episode_end": 3,
                    "target_path": "/data/x",
                    "status": "linked",
                }
            ],
        }

        seen = MODEL_VIEWS["media.read_media"](work)

        assert isinstance(seen, dict)
        assert "poster_url" not in seen
        [season] = seen["seasons"]
        assert season["episode_count"] == 7
        assert season["episodes"] == {
            "imported": "1-3, 5",
            "missing": "4",
            "downloading": "6",
            "unaired": "7",
        }
        assert season["jobs"] == {"6": "abc"}
        assert seen["files"] == [
            {"season": 1, "episode_start": 1, "episode_end": 3, "status": "linked"}
        ]

    def test_jellyfin_episodes_matching_nothing_become_ranges_per_season(self) -> None:
        """Jellyfin 認不到 metadata 時整部劇每一集都對不上（票 28）：長篇是上千筆，照季收成範圍，
        沒有編號的只說幾集。"""
        unmatched = [
            {"season": 1, "episode_start": n, "episode_end": None, "premiere_date": None}
            for n in (*range(1, 200), 250)
        ]
        unmatched += [
            {"season": 2, "episode_start": 1, "episode_end": 2, "premiere_date": "2024-01-01"},
            {"season": None, "episode_start": None, "episode_end": None, "premiere_date": None},
        ]

        seen = MODEL_VIEWS["media.read_media"]({"seasons": [], "jellyfin_unmatched": unmatched})

        assert isinstance(seen, dict)
        assert seen["jellyfin_unmatched"] == {"1": "1-199, 250", "2": "1-2", "no_number": 1}

    def test_an_eighty_five_episode_season_fits_far_under_the_clip(self) -> None:
        episodes = [
            {"episode_number": n, "name": "x" * 40, "status": "missing"} for n in range(1, 86)
        ]
        seen = MODEL_VIEWS["media.read_media"](
            {"seasons": [{"season_number": 1, "episodes": episodes}]}
        )
        assert isinstance(seen, dict)
        assert seen["seasons"][0]["episodes"] == {"missing": "1-85"}

    def test_airing_gaps_split_a_season_into_blocks(self) -> None:
        """票 23d：沒有網路搜尋時 `series-mapping` 靠 TMDB 各集的播出日切段，給模型的那一份要
        留得下。
        像無職轉生第 1 季：E01–E11 冬季每週一集（E03 之後停播一週不算斷開）、E12–E23 秋季；
        還沒定播出日的 E24 不進任何一段。"""
        winter = [date(2021, 1, 11) + timedelta(weeks=n + (n >= 3)) for n in range(11)]
        autumn = [date(2021, 10, 4) + timedelta(weeks=n) for n in range(12)]
        aired = [*winter, *autumn]
        episodes = [
            {
                "episode_number": n,
                "status": "missing",
                "air_date": aired[n - 1].isoformat() if n <= len(aired) else None,
            }
            for n in range(1, 25)
        ]
        seen = MODEL_VIEWS["media.read_media"](
            {"seasons": [{"season_number": 1, "episodes": episodes}]}
        )
        assert isinstance(seen, dict)
        assert seen["seasons"][0]["aired_blocks"] == [
            {"episodes": "1-11", "from": "2021-01-11", "to": "2021-03-29"},
            {"episodes": "12-23", "from": "2021-10-04", "to": "2021-12-20"},
        ]
