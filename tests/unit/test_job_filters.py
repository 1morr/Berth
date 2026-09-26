"""下載列表的「需要人」＝前端塗 `blocked` 與 `assigned` 的那幾個狀態（M4 票 04）。

同一條規則寫在兩個語言：後端 `services/jobs.FILTER_STATES` 決定哪幾筆進「需要人」這一組，
前端 `web/src/jobs/jobState.ts` 的 `JOB_SIGNAL` 決定哪幾列塗上需要人的漆。兩邊對不上的話，
「需要人 3」點進去看到的會是另外幾列。

讀的是 `jobState.ts` 的原文，所以讀法本身在最後做雙向變異：改一個狀態的漆要讀得出來，
改一次無關的排版（換行、空白、註解）不能讀出不同的東西。
"""

from __future__ import annotations

import re
from pathlib import Path

from berth.domain import JobFilter, JobState
from berth.services.jobs import FILTER_STATES

JOB_STATE_TS = Path(__file__).parents[2] / "web" / "src" / "jobs" / "jobState.ts"

#: `JOB_SIGNAL` 那一塊：宣告到它的收尾 `}`。
_TABLE = re.compile(r"JOB_SIGNAL: Record<JobState, Signal> = \{(?P<body>.*?)\n\}", re.S)
#: 一列：`state: 'signal',`。
_ROW = re.compile(r"(?P<state>\w+):\s*'(?P<signal>\w+)'")
#: 需要人的兩罐漆（DESIGN.md 的 The One Meaning Rule：`assigned` 需要你、`blocked` 阻擋）。
_NEEDS_SOMEONE = {"assigned", "blocked"}


def painted(source: str) -> set[str]:
    """`JOB_SIGNAL` 裡塗需要人那兩罐漆的狀態。讀不到那一塊就是空集合，閘門照樣會紅。"""
    found = _TABLE.search(source)
    if found is None:
        return set()
    body = re.sub(r"//[^\n]*", "", found["body"])
    return {row["state"] for row in _ROW.finditer(body) if row["signal"] in _NEEDS_SOMEONE}


def test_needing_someone_is_what_the_list_paints_as_needing_someone() -> None:
    attention = FILTER_STATES[JobFilter.ATTENTION]
    assert attention is not None
    assert {state.value for state in attention} == painted(JOB_STATE_TS.read_text("utf-8"))


def test_every_state_is_painted() -> None:
    """讀法讀得到整張表：每一個狀態都有一列（否則上一條可能是兩邊都少了同一個）。"""
    source = JOB_STATE_TS.read_text("utf-8")
    found = _TABLE.search(source)
    assert found is not None
    assert {row["state"] for row in _ROW.finditer(found["body"])} == {s.value for s in JobState}


class TestTheReading:
    """`painted` 自己的雙向變異。"""

    SOURCE = JOB_STATE_TS.read_text("utf-8")

    def test_repainting_a_state_is_caught(self) -> None:
        repainted = self.SOURCE.replace("stalled: 'assigned'", "stalled: 'working'")
        assert repainted != self.SOURCE
        assert painted(repainted) == painted(self.SOURCE) - {"stalled"}

    def test_painting_one_more_state_is_caught(self) -> None:
        repainted = self.SOURCE.replace("downloading: 'working'", "downloading: 'blocked'")
        assert repainted != self.SOURCE
        assert painted(repainted) == painted(self.SOURCE) | {"downloading"}

    def test_reformatting_is_not_caught(self) -> None:
        reformatted = self.SOURCE.replace(
            "review: 'assigned',", "review:   'assigned', // 等一個決定"
        ).replace("  requested: 'working',\n", "  requested:\n    'working',\n")
        assert reformatted != self.SOURCE
        assert painted(reformatted) == painted(self.SOURCE)
