"""Feed Item 的跳過理由：後端的 code + 參數 ↔ 前端兩份語言的句子（M3 票 10）。

與 `test_bind_reasons.py` 同一個守法：句子只在前端（`web/src/i18n/resources.ts` 的 `rss.skip.*`），
`tsc` 守得住「每一個 code 都有一句」，守不住「句子裡的佔位符就是後端送的那幾個參數」。讀法
（`sentences`）借 `test_reason_codes.py`；這裡對 `skip` 這一塊與 `SKIP_PARAMS` 再做一次雙向變異。
"""

from __future__ import annotations

import pytest

from berth.domain import SKIP_PARAMS, SkipCode, skipped
from tests.unit.test_reason_codes import _PLACEHOLDER, RESOURCES, sentences


def mismatches(table: dict[str, str]) -> dict[str, tuple[set[str], set[str]]]:
    """句子的佔位符與參數表對不上的那幾句：code → （該有的, 實際寫的）。缺句子也算。"""
    found: dict[str, tuple[set[str], set[str]]] = {}
    for code, expected in SKIP_PARAMS.items():
        text = table.get(code.value)
        written = set(_PLACEHOLDER.findall(text)) if text is not None else {"<missing>"}
        if written != set(expected):
            found[code.value] = (set(expected), written)
    return found


class TestTheBackendSide:
    def test_every_code_has_a_parameter_list(self) -> None:
        assert set(SKIP_PARAMS) == set(SkipCode)

    def test_no_parameter_is_called_count(self) -> None:
        assert not any("count" in params for params in SKIP_PARAMS.values())

    def test_a_reason_missing_a_parameter_is_refused_when_it_is_made(self) -> None:
        with pytest.raises(ValueError, match="feed_rule"):
            skipped(SkipCode.FEED_RULE)

    def test_a_reason_with_a_stray_parameter_is_refused_too(self) -> None:
        with pytest.raises(ValueError):
            skipped(SkipCode.NOT_SINGLE, rule="x")

    def test_a_reason_with_exactly_its_parameters_is_made(self) -> None:
        assert skipped(SkipCode.IN_LIBRARY, known="a.mkv").params == {"known": "a.mkv"}


class TestTheSentences:
    def test_both_languages_are_read(self) -> None:
        tables = sentences(RESOURCES.read_text(encoding="utf-8"), "skip")

        assert len(tables) == 2
        assert all(len(table) == len(SkipCode) for table in tables)

    @pytest.mark.parametrize("index", [0, 1])
    def test_every_sentence_names_exactly_the_parameters_it_gets(self, index: int) -> None:
        table = sentences(RESOURCES.read_text(encoding="utf-8"), "skip")[index]

        assert mismatches(table) == {}
        assert set(table) == {code.value for code in SkipCode}


class TestReadingTheSource:
    """`mismatches` 自己的雙向變異：造一句違規要紅，改一次無關的排版不能紅。"""

    SOURCE = """
    skip: {
      feed_rule: '這個 Feed 的排除條件「{{rule}}」擋下',
      in_library:
        '媒體庫裡已經有同一個版本：{{known}}',
    },
"""

    def test_a_renamed_placeholder_is_caught(self) -> None:
        (table,) = sentences(self.SOURCE.replace("{{rule}}", "{{rules}}"), "skip")

        assert mismatches(table)["feed_rule"] == ({"rule"}, {"rules"})

    def test_a_missing_sentence_is_caught(self) -> None:
        (table,) = sentences(self.SOURCE, "skip")

        assert mismatches(table)["not_single"] == (set(), {"<missing>"})

    def test_the_layout_does_not_change_what_is_read(self) -> None:
        folded = self.SOURCE.replace("feed_rule: '", "feed_rule:\n        '").replace(
            "{{known}}", "{{ known }}"
        )

        (table,) = sentences(folded, "skip")

        assert "feed_rule" not in mismatches(table)
        assert "in_library" not in mismatches(table)
