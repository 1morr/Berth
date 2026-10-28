"""側面板的防護裡不靠模型的那幾塊（M5 票 20）：工具結果截斷，以及防護的預設值（M5 票 23）。"""

from __future__ import annotations

import json
from typing import Any

from berth.services.agent import Limits
from berth.services.agent_guards import Cut, clip


def size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False))


class TestClip:
    def test_a_result_under_the_limit_is_left_alone(self) -> None:
        value = {"items": [{"name": "Frieren"}], "total": 1}

        clipped = clip(value, 1000)

        assert clipped.value == value
        assert clipped.cuts == ()

    def test_a_long_list_keeps_its_first_items_and_says_how_many_more(self) -> None:
        value: dict[str, Any] = {
            "items": [{"name": f"Release {n:03d}"} for n in range(100)],
            "total": 100,
        }

        clipped = clip(value, 600)

        assert size(clipped.value) <= 600
        assert isinstance(clipped.value, dict)
        kept = clipped.value["items"]
        assert kept == value["items"][: len(kept)]
        assert clipped.value["total"] == 100
        assert clipped.cuts == (Cut(at="items", shown=len(kept), more=100 - len(kept)),)

    def test_the_input_is_not_changed(self) -> None:
        value = {"items": list(range(500))}

        clip(value, 100)

        assert value == {"items": list(range(500))}

    def test_the_biggest_list_goes_first(self) -> None:
        value = {
            "seasons": [1, 2, 3],
            "releases": [{"name": "x" * 50} for _ in range(40)],
        }

        clipped = clip(value, 900)

        assert isinstance(clipped.value, dict)
        assert clipped.value["seasons"] == [1, 2, 3]
        assert [cut.at for cut in clipped.cuts] == ["releases"]

    def test_lists_inside_lists_have_their_own_paths(self) -> None:
        value = [{"files": [f"file-{n}.mkv" for n in range(200)]}]

        clipped = clip(value, 300)

        assert [cut.at for cut in clipped.cuts] == ["[0].files"]
        assert size(clipped.value) <= 300

    def test_a_long_text_is_cut_with_how_many_characters_are_left(self) -> None:
        value = {"overview": "あ" * 5000}

        clipped = clip(value, 1000)

        assert isinstance(clipped.value, dict)
        assert size(clipped.value) <= 1000
        [cut] = clipped.cuts
        assert cut.at == "overview"
        assert cut.unit == "chars"
        assert cut.shown + cut.more == 5000
        assert clipped.value["overview"] == "あ" * cut.shown

    def test_what_cannot_be_cut_down_becomes_a_preview(self) -> None:
        value = {f"key-{n}": n for n in range(1000)}

        clipped = clip(value, 200)

        assert isinstance(clipped.value, str)
        assert len(clipped.value) <= 200
        [cut] = clipped.cuts
        assert cut.at == "$"
        assert cut.unit == "chars"


def test_the_default_limits_are_the_ones_in_the_plan() -> None:
    """plan §11.6〈防護〉那張表：整合測試都換成小的數字，預設值只在這裡守（M5 驗收）。"""
    limits = Limits()

    assert limits.max_tokens == 4096
    assert limits.requests == 20
    assert (limits.input_tokens, limits.output_tokens) == (400_000, 30_000)
    assert (limits.warn_at, limits.block_at, limits.abort_at) == (2, 3, 4)
    assert limits.stale_steps == 3
    assert limits.result_chars == 12_000
    assert limits.web_searches == 5
