"""RSS Series 自動綁定的理由：後端的 code + 參數 ↔ 前端兩份語言的句子（M3 票 09）。

與 `test_reason_codes.py` 同一個守法：句子只在前端（`web/src/i18n/resources.ts` 的
`rss.grounds.*`），`tsc` 守得住「每一個 code 都有一句」，守不住「句子裡的佔位符就是後端送的
那幾個參數」。讀法（`sentences`）借那一份；這裡對 `grounds` 這一塊與 `BIND_PARAMS` 再做一次雙向
變異。
"""

from __future__ import annotations

import pytest

from berth.domain import BIND_PARAMS, BindReasonCode, because
from tests.unit.test_reason_codes import _PLACEHOLDER, RESOURCES, sentences


def mismatches(table: dict[str, str]) -> dict[str, tuple[set[str], set[str]]]:
    """句子的佔位符與參數表對不上的那幾句：code → （該有的, 實際寫的）。缺句子也算。"""
    found: dict[str, tuple[set[str], set[str]]] = {}
    for code, expected in BIND_PARAMS.items():
        text = table.get(code.value)
        written = set(_PLACEHOLDER.findall(text)) if text is not None else {"<missing>"}
        if written != set(expected):
            found[code.value] = (set(expected), written)
    return found


class TestTheBackendSide:
    def test_every_code_has_a_parameter_list(self) -> None:
        assert set(BIND_PARAMS) == set(BindReasonCode)

    def test_no_parameter_is_called_count(self) -> None:
        assert not any("count" in params for params in BIND_PARAMS.values())

    def test_a_reason_missing_a_parameter_is_refused_when_it_is_made(self) -> None:
        with pytest.raises(ValueError, match="only_route"):
            because(BindReasonCode.ONLY_ROUTE)

    def test_a_reason_with_a_stray_parameter_is_refused_too(self) -> None:
        with pytest.raises(ValueError):
            because(BindReasonCode.NO_CANDIDATE, title="x")

    def test_a_reason_with_exactly_its_parameters_is_made(self) -> None:
        assert because(BindReasonCode.ONLY_ROUTE, route="Anime").params == {"route": "Anime"}


class TestTheSentences:
    def test_both_languages_are_read(self) -> None:
        tables = sentences(RESOURCES.read_text(encoding="utf-8"), "grounds")

        assert len(tables) == 2
        assert all(len(table) == len(BindReasonCode) for table in tables)

    @pytest.mark.parametrize("index", [0, 1])
    def test_every_sentence_names_exactly_the_parameters_it_gets(self, index: int) -> None:
        table = sentences(RESOURCES.read_text(encoding="utf-8"), "grounds")[index]

        assert mismatches(table) == {}
        assert set(table) == {code.value for code in BindReasonCode}


class TestReadingTheSource:
    """`mismatches` 自己的雙向變異：造一句違規要紅，改一次無關的排版不能紅。"""

    SOURCE = """
    grounds: {
      only_route: '收得下它的 Route 只有 {{route}}',
      premiere_far:
        '名字相同的是 {{title}}，但沒有一季在 {{premiere}} 前後首播',
    },
"""

    def test_a_renamed_placeholder_is_caught(self) -> None:
        (table,) = sentences(self.SOURCE.replace("{{route}}", "{{routes}}"), "grounds")

        assert mismatches(table)["only_route"] == ({"route"}, {"routes"})

    def test_a_missing_sentence_is_caught(self) -> None:
        (table,) = sentences(self.SOURCE, "grounds")

        assert mismatches(table)["no_candidate"] == (set(), {"<missing>"})

    def test_the_layout_does_not_change_what_is_read(self) -> None:
        folded = self.SOURCE.replace("only_route: '", "only_route:\n        '").replace(
            "{{title}}", "{{ title }}"
        )

        (table,) = sentences(folded, "grounds")

        assert "only_route" not in mismatches(table)
        assert "premiere_far" not in mismatches(table)
