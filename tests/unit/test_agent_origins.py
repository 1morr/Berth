"""寫入工具的參數出自哪裡（M5 票 14、brief §14〈對話裡的確認卡〉、plan §11.6〈分段〉第 5 段）。

三條守法都只看伺服器存的歷史：

- **id 出自工具結果**：寫入工具的 id 一定要在這段對話先前的工具結果裡出現過。
- **網址出自使用者的話**：連到新位址的命令，網址要逐字出現在使用者自己打的字裡。
- **自由文字出自外部內容**：出自網頁、而使用者沒說過的那幾格，卡片要標出來。
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    NativeToolReturnPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from berth.services.agent_origins import Origins, ToolRefusal
from berth.services.executor import CommandRefusedError


def asked(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(text)])


def looked_up(tool: str, result: object, call: str = "r1") -> list[ModelMessage]:
    return [
        ModelResponse(parts=[ToolCallPart(tool, {}, tool_call_id=call)]),
        ModelRequest(parts=[ToolReturnPart(tool, result, tool_call_id=call)]),
    ]


SEARCHED = looked_up(
    "search_search_torrents",
    {"rows": [{"source_id": "s-abc", "title": "[ANi] SPY×FAMILY - 01"}]},
)
ROUTES = looked_up("media_route_choices", [{"id": 3, "name": "Anime"}], call="r2")
FOUND = looked_up("discover_search_media", {"items": [{"id": "tv:65942"}]}, call="r3")


class TestIdsComeFromToolResults:
    def test_ids_from_earlier_results_pass(self) -> None:
        origins = Origins.of([asked("download it"), *SEARCHED, *ROUTES, *FOUND])

        origins.check(
            "downloading.add_manual_download",
            {"source_id": "s-abc", "media_id": "tv:65942", "route_id": 3},
            connects_out=False,
        )

    def test_an_id_no_tool_returned_is_refused_and_named(self) -> None:
        origins = Origins.of([asked("download it"), *SEARCHED, *FOUND])

        with pytest.raises(CommandRefusedError) as raised:
            origins.check(
                "downloading.add_manual_download",
                {"source_id": "s-abc", "media_id": "tv:65942", "route_id": 7},
                connects_out=False,
            )

        assert raised.value.reason is ToolRefusal.ID_NOT_FROM_RESULTS
        assert "route_id=7" in raised.value.detail

    def test_an_id_the_user_typed_or_the_model_wrote_does_not_count(self) -> None:
        """只有工具結果算：使用者的字、模型自己上一個呼叫的參數都不算。"""
        origins = Origins.of(
            [
                asked("subscribe tv:65942 to route 3"),
                ModelResponse(
                    parts=[ToolCallPart("media_route_choices", {"media_id": "tv:65942"})]
                ),
            ]
        )

        with pytest.raises(CommandRefusedError):
            origins.check(
                "rss.subscribe_search",
                {"media_id": "tv:65942", "route_id": 3, "term": "x", "kind": "nyaa"},
                connects_out=False,
            )

    def test_ids_in_a_web_page_do_not_count(self) -> None:
        """網頁是外部內容：裡面寫著的 id 不算查過。"""
        origins = Origins.of(
            [asked("find it"), *looked_up("web_tavily_search", {"results": [{"id": "tv:1"}]})]
        )

        with pytest.raises(CommandRefusedError):
            origins.check("rss.subscribe_search", {"media_id": "tv:1"}, connects_out=False)

    def test_ids_from_results_of_earlier_turns_count(self) -> None:
        origins = Origins.of(
            [asked("find it"), *FOUND, ModelResponse(parts=[TextPart("Found.")]), asked("ok")]
        )

        origins.check("rss.subscribe_search", {"media_id": "tv:65942"}, connects_out=False)

    def test_a_field_left_empty_is_not_an_id(self) -> None:
        origins = Origins.of([asked("add it"), *ROUTES])

        origins.check(
            "rss.add_feed",
            {"url": "https://mikanani.me/RSS/x", "tv_route_id": 3, "movie_route_id": None},
            connects_out=False,
        )


URL = "https://mikanani.me/RSS/MyBangumi?token=abc"


class TestAddressesComeFromTheUser:
    def test_an_address_the_user_typed_passes(self) -> None:
        origins = Origins.of([asked(f"幫我加這個 RSS：{URL} ，劇集送 Anime。"), *ROUTES])

        origins.check("rss.add_feed", {"url": URL, "tv_route_id": 3}, connects_out=True)

    def test_an_address_from_a_web_page_is_refused(self) -> None:
        origins = Origins.of(
            [
                asked("上網找芙莉蓮的 RSS 網址，找到就直接加"),
                *looked_up("web_tavily_search", {"results": [{"url": URL}]}),
            ]
        )

        with pytest.raises(CommandRefusedError) as raised:
            origins.check("rss.add_feed", {"url": URL}, connects_out=True)

        assert raised.value.reason is ToolRefusal.ADDRESS_NOT_FROM_USER
        assert URL in raised.value.detail

    def test_an_address_must_be_verbatim(self) -> None:
        """少一段 query 也不行：key 常常就在 query 裡。"""
        origins = Origins.of([asked(f"add {URL}")])

        with pytest.raises(CommandRefusedError):
            origins.check("rss.add_feed", {"url": URL.replace("abc", "abd")}, connects_out=True)

    def test_a_value_shaped_like_an_address_is_one_whatever_the_field(self) -> None:
        origins = Origins.of([asked("add it")])

        with pytest.raises(CommandRefusedError):
            origins.check("rss.add_feed", {"name": "http://evil.example/x"}, connects_out=True)

    def test_commands_that_do_not_connect_out_are_not_checked_for_addresses(self) -> None:
        origins = Origins.of([asked("go")])

        origins.check("rss.subscribe_search", {"term": "http://x.example"}, connects_out=False)


class FeedRow(BaseModel):
    url: str
    name: str = ""
    term: str = ""
    exclusions: tuple[str, ...] = ()
    tv_route_id: int | None = None


PAGE = looked_up(
    "web_tavily_search",
    {"results": [{"content": 'Frieren "S2" is fansubbed by ANi\nkeyword: Sousou no Frieren S2'}]},
)


class TestFreeTextFromExternalContent:
    def test_free_text_copied_from_a_web_page_is_named(self) -> None:
        origins = Origins.of([asked("subscribe frieren"), *PAGE])

        found = origins.external_fields(
            {"url": URL, "term": "Sousou no Frieren S2", "name": "Frieren"}, FeedRow
        )

        assert found == ("term",)

    def test_text_the_user_also_typed_is_theirs(self) -> None:
        origins = Origins.of([asked("subscribe Sousou no Frieren S2"), *PAGE])

        assert origins.external_fields({"url": URL, "term": "Sousou no Frieren S2"}, FeedRow) == ()

    def test_quotes_and_line_breaks_are_matched_as_written_in_the_page(self) -> None:
        """外部內容存成 JSON 字串：引號與換行在裡面是跳脫過的。"""
        origins = Origins.of([asked("go"), *PAGE])

        assert origins.external_fields({"url": URL, "term": 'Frieren "S2"'}, FeedRow) == ("term",)

    def test_a_list_of_free_text_counts(self) -> None:
        origins = Origins.of([asked("go"), *PAGE])

        assert origins.external_fields(
            {"url": URL, "exclusions": ["720p", "is fansubbed by ANi"]}, FeedRow
        ) == ("exclusions",)

    def test_nothing_is_named_without_external_content(self) -> None:
        """搜過 torrent、讀過 Mikan 都不算外部內容（研究〈實跑才抓到的問題〉第 6 點）。"""
        origins = Origins.of(
            [asked("go"), *looked_up("search_search_torrents", {"rows": [{"title": "Frieren"}]})]
        )

        assert origins.external_fields({"url": URL, "name": "Frieren"}, FeedRow) == ()

    def test_ids_and_addresses_are_not_free_text(self) -> None:
        origins = Origins.of([asked("go"), *PAGE, *looked_up("web_tavily_search", {"u": URL})])

        assert origins.external_fields({"url": URL, "tv_route_id": 3}, FeedRow) == ()

    def test_the_servers_web_search_is_external_too(self) -> None:
        origins = Origins.of(
            [
                asked("go"),
                ModelResponse(
                    parts=[
                        NativeToolReturnPart(
                            "web_search",
                            [{"title": "Frieren Season 2 by SubsPlease"}],
                            tool_call_id="srv-1",
                        )
                    ]
                ),
            ]
        )

        assert origins.external_fields({"url": URL, "name": "Frieren Season 2"}, FeedRow) == (
            "name",
        )
