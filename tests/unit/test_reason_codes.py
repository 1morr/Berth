"""Plan Item 的理由：後端的 code + 參數 ↔ 前端兩份語言的句子（M2 票 07）。

理由是封閉集合的 code 加參數，句子只在前端（`web/src/i18n/resources.ts` 的 `jobs.plan.why.*`）。
`tsc` 守得住「每一個 code 都有一句」（鍵從產出的型別來），守不住「句子裡的佔位符就是後端送的
那幾個參數」——參數改了名而句子沒跟上，畫面就印出一個 `{{season}}`。這一份守後面那一半：

- 後端每一種理由都有一張參數表（`REASON_PARAMS`），`why()` 組的那一刻就核對；
- 兩份語言裡每一句的佔位符，都要剛好是那一張表。

讀的是 `resources.ts` 的原文，所以讀法本身在最後做雙向變異：造一句違規要讀得出來，改一次
無關的排版（換行、空白）不能讀出不同的東西。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from berth.domain import REASON_PARAMS, ReasonCode, why

RESOURCES = Path(__file__).parents[2] / "web" / "src" / "i18n" / "resources.ts"

#: `why: {` 那一塊到它自己縮排的收尾 `}`。兩份語言各一塊，順序是 zh-Hant、en。
_BLOCK = re.compile(r"^(?P<indent>[ ]*)why: \{\n(?P<body>.*?)^(?P=indent)\},", re.M | re.S)
#: 一句：`key: '...'`，值可以折到下一行（prettier 超過寬度時會這樣排）。
_SENTENCE = re.compile(r"(?P<key>\w+):\s*'(?P<text>(?:[^'\\]|\\.)*)'")
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def sentences(source: str) -> list[dict[str, str]]:
    """每一份語言的 `jobs.plan.why`：code → 句子。"""
    return [
        {match["key"]: match["text"] for match in _SENTENCE.finditer(block["body"])}
        for block in _BLOCK.finditer(source)
    ]


def mismatches(table: dict[str, str]) -> dict[str, tuple[set[str], set[str]]]:
    """句子的佔位符與參數表對不上的那幾句：code → （該有的, 實際寫的）。缺句子也算。"""
    found: dict[str, tuple[set[str], set[str]]] = {}
    for code, expected in REASON_PARAMS.items():
        text = table.get(code.value)
        written = set(_PLACEHOLDER.findall(text)) if text is not None else {"<missing>"}
        if written != set(expected):
            found[code.value] = (set(expected), written)
    return found


class TestTheBackendSide:
    def test_every_code_has_a_parameter_list(self) -> None:
        assert set(REASON_PARAMS) == set(ReasonCode)

    def test_no_parameter_is_called_count(self) -> None:
        """i18next 看到 `count` 就去找 `_one` / `_other` 那一對鍵，句子會落回原鍵。"""
        assert not any("count" in params for params in REASON_PARAMS.values())

    def test_a_reason_missing_a_parameter_is_refused_when_it_is_made(self) -> None:
        with pytest.raises(ValueError, match="season_from_release"):
            why(ReasonCode.SEASON_FROM_RELEASE)

    def test_a_reason_with_a_stray_parameter_is_refused_too(self) -> None:
        with pytest.raises(ValueError):
            why(ReasonCode.SINGLE_SEASON, season=1)

    def test_a_reason_with_exactly_its_parameters_is_made(self) -> None:
        assert why(ReasonCode.SEASON_FROM_RELEASE, season=2).params == {"season": 2}


class TestTheSentences:
    def test_both_languages_are_read(self) -> None:
        """讀出兩塊、每塊都不是空的：讀法壞掉時下面那條會在空清單上說「沒有不對的」。"""
        tables = sentences(RESOURCES.read_text(encoding="utf-8"))

        assert len(tables) == 2
        assert all(len(table) == len(ReasonCode) for table in tables)

    @pytest.mark.parametrize("language", ["zh-Hant", "en"])
    def test_every_sentence_names_exactly_the_parameters_it_gets(self, language: str) -> None:
        tables = dict(
            zip(["zh-Hant", "en"], sentences(RESOURCES.read_text(encoding="utf-8")), strict=True)
        )

        assert mismatches(tables[language]) == {}
        assert set(tables[language]) == {code.value for code in ReasonCode}


class TestReadingTheSource:
    """`sentences` 與 `mismatches` 自己的雙向變異。"""

    SOURCE = """
    plan: {
      why: {
        season_from_release: '發佈名寫了第 {{season}} 季',
        cour_offset:
          '{{season}} {{part}} {{first}} {{number}} {{episode}}',
      },
    },
"""

    def test_a_renamed_placeholder_is_caught(self) -> None:
        broken = self.SOURCE.replace("{{season}} 季',", "{{seasons}} 季',")

        (table,) = sentences(broken)

        assert mismatches(table)["season_from_release"] == ({"season"}, {"seasons"})

    def test_a_missing_sentence_is_caught(self) -> None:
        (table,) = sentences(self.SOURCE)

        assert mismatches(table)["single_season"] == (set(), {"<missing>"})

    def test_the_layout_does_not_change_what_is_read(self) -> None:
        folded = self.SOURCE.replace(
            "season_from_release: '", "season_from_release:\n          '"
        ).replace("{{part}}", "{{ part }}")

        assert sentences(folded) == [
            {key: text.replace("{{part}}", "{{ part }}") for key, text in table.items()}
            for table in sentences(self.SOURCE)
        ]
        (table,) = sentences(folded)
        assert "season_from_release" not in mismatches(table)
        assert "cour_offset" not in mismatches(table)
