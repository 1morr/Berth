"""`docs/progress.md` 的寫法規則（該檔〈寫法與封存〉）：每列 / 每條的長度與里程碑標記。

分工：`test_progress_merge.py` 守 union 合併不弄壞檔案結構（段落、重複、表格連續）；
這裡守內容的三條：

- session 紀錄的每一列、偏差的每一條，整行 ≤ 200 字（Python `len`）。
- 每一列 / 每一條開頭標里程碑：票欄 `<里程碑> <票號> <短標題>`，
  偏差 `- <日期> <里程碑> 票 <NN>：…`。
- 標的里程碑在里程碑表裡不是「已驗收」：已驗收的搬去 `docs/archive/<里程碑>.md`，
  不再追加在這裡。

只比字數與開頭的標記，不比措辭；空行、表格分隔列的寫法、列的順序都不影響結果。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "docs" / "progress.md"
MAX_LENGTH = 200
_MILESTONE = r"(M1\.5|M[0-7]|docs-diet)"
_SESSION_TAG = re.compile(_MILESTONE + r"(?=\s|$)")
_DEVIATION_TAG = re.compile(r"- \d{4}-\d\d-\d\d " + _MILESTONE + r"(?=\s|：)")


def _section(text: str, heading: str) -> list[str]:
    body = text.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    return body.splitlines()


def accepted_milestones(text: str) -> set[str]:
    """里程碑表裡備註以「已驗收」開頭的那些。"""
    found = set()
    for line in _section(text, "里程碑與閱讀指引"):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("| ") and len(cells) == 4 and cells[3].startswith("已驗收"):
            found.add(cells[0])
    return found


def table_milestones(text: str) -> set[str]:
    return {
        line.split("|")[1].strip()
        for line in _section(text, "里程碑與閱讀指引")
        if re.match(r"\| " + _MILESTONE + r" \|", line)
    }


def problems(text: str) -> list[str]:
    found: list[str] = []
    accepted, known = accepted_milestones(text), table_milestones(text)

    def check(line: str, tag: re.Match[str] | None) -> None:
        shown = line[:60]
        if len(line) > MAX_LENGTH:
            found.append(f"{len(line)} 字，上限 {MAX_LENGTH}：{shown}")
        if tag is None:
            found.append(f"開頭沒有標里程碑：{shown}")
        elif tag.group(1) not in known:
            found.append(f"{tag.group(1)} 不在里程碑表：{shown}")
        elif tag.group(1) in accepted:
            found.append(f"{tag.group(1)} 已驗收，該搬去 docs/archive：{shown}")

    for line in _section(text, "Session 紀錄"):
        if re.match(r"\| \d{4}-\d\d-\d\d \|", line):
            ticket = line.split("|")[2].strip()
            check(line, _SESSION_TAG.match(ticket))
    for line in _section(text, "偏差與決定"):
        if line.startswith("- "):
            check(line, _DEVIATION_TAG.match(line))
    return found


def test_progress_follows_the_writing_rules() -> None:
    assert problems(PROGRESS.read_text(encoding="utf-8")) == []


class TestTheGatesThemselves:
    """違規會紅，無關的格式改動不會。"""

    def text(self) -> str:
        return PROGRESS.read_text(encoding="utf-8")

    def with_row(self, row: str) -> str:
        return self.text().replace("\n\n## 偏差與決定", f"\n{row}\n\n## 偏差與決定", 1)

    def test_an_over_long_row_is_caught(self) -> None:
        row = "| 2026-10-31 | docs-diet 99 太長 | " + "字" * 200 + " | 下一步 |"
        assert len(row) > MAX_LENGTH
        assert any("上限" in item for item in problems(self.with_row(row)))

    def test_an_over_long_deviation_is_caught(self) -> None:
        line = "- 2026-10-31 docs-diet 票 99：" + "字" * 200
        assert any("上限" in item for item in problems(self.text() + line + "\n"))

    def test_a_row_without_a_milestone_is_caught(self) -> None:
        row = "| 2026-10-31 | 99 沒標里程碑 | 結果 | 下一步 |"
        assert any("沒有標里程碑" in item for item in problems(self.with_row(row)))

    def test_a_deviation_without_a_milestone_is_caught(self) -> None:
        assert problems(self.text() + "- 2026-10-31 票 99：沒標\n") != []

    def test_a_row_for_an_accepted_milestone_is_caught(self) -> None:
        row = "| 2026-10-31 | M4 999 已驗收的里程碑 | 結果 | 下一步 |"
        assert any("已驗收" in item for item in problems(self.with_row(row)))

    def test_a_deviation_for_an_accepted_milestone_is_caught(self) -> None:
        assert problems(self.text() + "- 2026-10-31 M4 票 999：已驗收\n") != []

    def test_a_milestone_missing_from_the_table_is_caught(self) -> None:
        text = "\n".join(
            line for line in self.text().splitlines() if not line.startswith("| docs-diet |")
        )
        assert any("不在里程碑表" in item for item in problems(text))

    def test_unrelated_formatting_is_not_caught(self) -> None:
        text = self.text()
        reformatted = text.replace("\n\n", "\n\n\n").replace("| --- |", "|:---|")
        assert problems(reformatted) == []

    def test_reordering_rows_is_not_caught(self) -> None:
        lines = self.text().splitlines()
        first = next(i for i, line in enumerate(lines) if line.startswith("| 2026-10-30 |"))
        lines[first], lines[first + 1] = lines[first + 1], lines[first]
        assert problems("\n".join(lines)) == []
