"""ADR 的決定者行（`AGENTS.md` 每個 session 的流程第 4 步）。

0017 起的 ADR 要有一行 `決定者：使用者定`、`決定者：使用者同意` 或 `決定者：Agent 定`，
`/1morr:checkpoint` 讀它整理給使用者看的決定清單。0001–0016 寫的時候沒記，不補。

只認行首的 `決定者：` 與三個值，行在檔內哪裡、前後有沒有粗體或清單記號都不管。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parents[2] / "docs" / "adr"
FIRST_WITH_DECIDER = 17
_DECIDER = re.compile(
    r"^[-*\s]*(?:\*\*)?決定者(?:\*\*)?：(?:\*\*)?(使用者定|使用者同意|Agent 定)", re.M
)


def missing_decider(name: str, text: str) -> bool:
    number = int(name.split("-", 1)[0])
    return number >= FIRST_WITH_DECIDER and not _DECIDER.search(text)


def test_new_adrs_name_who_decided() -> None:
    missing = [
        path.name
        for path in sorted(ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))
        if missing_decider(path.name, path.read_text(encoding="utf-8"))
    ]
    assert missing == [], f"這些 ADR 少了「決定者：…」那一行：{missing}"


class TestTheGateItself:
    BODY = "# 標題\n\n內文。\n"

    def test_a_new_adr_without_a_decider_is_caught(self) -> None:
        assert missing_decider("0017-x.md", self.BODY)

    def test_an_unknown_decider_is_caught(self) -> None:
        assert missing_decider("0017-x.md", self.BODY + "決定者：大家\n")

    @pytest.mark.parametrize(
        "line",
        ["決定者：使用者定", "- 決定者：使用者同意（agent 提議兩案）", "**決定者**：Agent 定"],
    )
    def test_a_decider_line_in_any_style_is_not_caught(self, line: str) -> None:
        assert not missing_decider("0017-x.md", f"# 標題\n\n{line}\n\n內文。\n")

    def test_old_adrs_need_no_decider(self) -> None:
        assert not missing_decider("0016-x.md", self.BODY)
