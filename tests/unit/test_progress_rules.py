"""`docs/progress.md` 與 `docs/decisions.md` 的寫法規則（兩個檔各自的〈寫法〉段）。

- progress.md 的 `##` 段就是〈寫法與封存〉〈Session 紀錄〉，各一次、依序；session 紀錄是一整張表。
  做票的分支不改這兩個檔（合併的人在 main 寫），所以不再靠 union 合併，也不必守它抄重複的情況。
- session 紀錄的每一列、決定的每一條，整行 ≤ 200 字（Python `len`）。
- 每一列 / 每一條開頭標 `docs/roadmap.md` 里程碑表裡的里程碑：票欄 `<里程碑> <票號> <短標題>`，
  決定 `- <日期> <里程碑> 票 <NN>：…`。
- 標的里程碑不是「已驗收」：已驗收的，列與決定都搬去 `docs/archive/<里程碑>.md`。
- session 紀錄最後一列的「下一步」含反引號包住、`/` 開頭的指令，或以 `等使用者：` 開頭。
  紀錄是空的不算違規（封存後會空）。
- 2026-11-12 起的決定標決定者：`（使用者定）`、`（使用者同意）` 或 `（Agent 定）`。
  之前的條目不補（當時沒記，補了也是猜）。

只比字數、開頭的標記與最後一列的下一步，不比措辭；空行、表格分隔列的寫法都不影響結果，
列的順序只決定哪一列算最後一列。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "docs" / "progress.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
DECISIONS = ROOT / "docs" / "decisions.md"
SECTIONS = ["寫法與封存", "Session 紀錄"]
MAX_LENGTH = 200
_DECISION = re.compile(r"- \d{4}-\d\d-\d\d (\S+?)(?:（|：|\s|$)")
_ROW = re.compile(r"\| \d{4}-\d\d-\d\d \|")
_COMMAND = re.compile(r"`/[^`\s][^`]*`")
_WAITING = "等使用者："
DECIDERS = ("（使用者定）", "（使用者同意）", "（Agent 定）")
DECIDER_SINCE = "2026-11-12"


def _section(text: str, heading: str) -> list[str]:
    """`## heading` 那一段的內容；只認行首的標題，內文裡提到同樣的字不算。"""
    parts = re.split(rf"(?m)^## {re.escape(heading)}[ \t]*$", text, maxsplit=1)
    return parts[1].split("\n## ", 1)[0].splitlines() if len(parts) == 2 else []


def _milestone_rows(roadmap: str) -> list[list[str]]:
    rows = []
    for line in _section(roadmap, "里程碑"):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("| ") and len(cells) == 5 and cells[2].startswith("`.scratch/"):
            rows.append(cells)
    return rows


def accepted_milestones(roadmap: str) -> set[str]:
    """里程碑表裡狀態以「已驗收」開頭的那些。"""
    return {cells[0] for cells in _milestone_rows(roadmap) if cells[4].startswith("已驗收")}


def table_milestones(roadmap: str) -> set[str]:
    """里程碑表第一欄：標記只認這張表，新增里程碑不必改這裡。"""
    return {cells[0] for cells in _milestone_rows(roadmap)}


def problems(progress: str, roadmap: str, decisions: str) -> list[str]:
    found: list[str] = []
    accepted, known = accepted_milestones(roadmap), table_milestones(roadmap)

    headings = [line[3:].strip() for line in progress.splitlines() if line.startswith("## ")]
    if headings != SECTIONS:
        found.append(f"progress.md 的 ## 段應該是 {SECTIONS}，實際是 {headings}")
    tables = re.findall(r"(?:^\|.*\n?)+", "\n".join(_section(progress, "Session 紀錄")), flags=re.M)
    if len(tables) > 1:
        found.append(f"session 紀錄應該是一整張表，實際被空行切成 {len(tables)} 段")

    def check(line: str, tag: str | None) -> None:
        shown = line[:60]
        if len(line) > MAX_LENGTH:
            found.append(f"{len(line)} 字，上限 {MAX_LENGTH}：{shown}")
        if tag not in known:
            found.append(f"開頭沒有標里程碑表裡的里程碑（{tag}）：{shown}")
        elif tag in accepted:
            found.append(f"{tag} 已驗收，該搬去 docs/archive：{shown}")

    rows = [line for line in _section(progress, "Session 紀錄") if _ROW.match(line)]
    for line in rows:
        ticket = line.split("|")[2].strip()
        check(line, ticket.split(" ")[0])
    if rows:
        next_step = rows[-1].rstrip().rstrip("|").rsplit("|", 1)[-1].strip()
        if not (_COMMAND.search(next_step) or next_step.startswith(_WAITING)):
            found.append(f"最後一列的下一步沒有指令也不是「{_WAITING}」：{next_step[:60]}")
    for line in _section(decisions, "紀錄"):
        if line.startswith("- "):
            match = _DECISION.match(line)
            check(line, match.group(1) if match else None)
            if line[2:12] >= DECIDER_SINCE and not any(mark in line for mark in DECIDERS):
                found.append(f"沒標決定者（{'、'.join(DECIDERS)}）：{line[:60]}")
    return found


def test_progress_and_decisions_follow_the_writing_rules() -> None:
    assert (
        problems(
            PROGRESS.read_text(encoding="utf-8"),
            ROADMAP.read_text(encoding="utf-8"),
            DECISIONS.read_text(encoding="utf-8"),
        )
        == []
    )


class TestTheGatesThemselves:
    """違規會紅，無關的格式改動不會。"""

    def text(self) -> str:
        return PROGRESS.read_text(encoding="utf-8")

    def roadmap(self) -> str:
        return ROADMAP.read_text(encoding="utf-8")

    def decisions(self) -> str:
        return DECISIONS.read_text(encoding="utf-8")

    def with_row(self, row: str) -> str:
        return self.text().rstrip("\n") + f"\n{row}\n"

    def check(self, progress: str | None = None, decision: str | None = None) -> list[str]:
        decisions = self.decisions() + (f"{decision}\n" if decision else "")
        return problems(self.text() if progress is None else progress, self.roadmap(), decisions)

    def test_an_over_long_row_is_caught(self) -> None:
        row = "| 2026-10-31 | M6 99 太長 | " + "字" * 200 + " | 下一步 |"
        assert len(row) > MAX_LENGTH
        assert any("上限" in item for item in self.check(self.with_row(row)))

    def test_an_over_long_decision_is_caught(self) -> None:
        line = "- 2026-10-31 M6 票 99：" + "字" * 200
        assert any("上限" in item for item in self.check(decision=line))

    def test_a_row_without_a_milestone_is_caught(self) -> None:
        row = "| 2026-10-31 | 99 沒標里程碑 | 結果 | 下一步 |"
        assert any("沒有標里程碑表裡的里程碑" in item for item in self.check(self.with_row(row)))

    def test_a_decision_without_a_milestone_is_caught(self) -> None:
        assert any(
            "沒有標里程碑表裡的里程碑" in item
            for item in self.check(decision="- 2026-10-31 票 99：沒標")
        )

    def test_a_row_for_an_accepted_milestone_is_caught(self) -> None:
        row = "| 2026-10-31 | M4 999 已驗收的里程碑 | 結果 | 下一步 |"
        assert any("已驗收" in item for item in self.check(self.with_row(row)))

    def test_a_decision_for_an_accepted_milestone_is_caught(self) -> None:
        assert any(
            "已驗收" in item for item in self.check(decision="- 2026-10-31 M4 票 999：已驗收")
        )

    def test_a_milestone_missing_from_the_table_is_caught(self) -> None:
        roadmap = "\n".join(
            line for line in self.roadmap().splitlines() if not line.startswith("| M6 |")
        )
        progress = self.with_row("| 2026-10-31 | M6 1 甲 | 結果 | `/implement 甲` |")
        assert any("M6" in item for item in problems(progress, roadmap, self.decisions()))

    def test_a_heading_quoted_inside_a_rule_is_not_the_section(self) -> None:
        quoted = "- 封存時搬到 `## Session 紀錄` 與 `## 紀錄`。\n"
        progress = self.text().replace("## 寫法與封存\n", "## 寫法與封存\n\n" + quoted, 1)
        row = "| 2026-10-31 | 99 沒標里程碑 | 結果 | `/implement 甲` |"
        found = problems(progress.rstrip("\n") + f"\n{row}\n", self.roadmap(), self.decisions())
        assert any("沒有標里程碑表裡的里程碑" in item for item in found)

    def test_an_extra_or_repeated_section_is_caught(self) -> None:
        assert any("## 段" in item for item in self.check(self.text() + "\n## 偏差與決定\n"))
        doubled = self.text() + "\n## Session 紀錄\n"
        assert any("## 段" in item for item in self.check(doubled))

    def test_a_row_after_a_blank_line_is_caught(self) -> None:
        progress = (
            self.text().rstrip("\n") + "\n\n| 2099-10-31 | M6 1 甲 | 結果 | `/implement 甲` |\n"
        )
        assert any("一整張表" in item for item in self.check(progress))

    def test_unrelated_formatting_is_not_caught(self) -> None:
        def reformat(text: str) -> str:
            return text.replace("\n\n", "\n\n\n").replace("| --- |", "|:---|")

        found = problems(
            reformat(self.text()), reformat(self.roadmap()), reformat(self.decisions())
        )
        assert found == []

    def test_reordering_rows_is_not_caught(self) -> None:
        rows = (
            "| 2099-10-31 | M6 1 甲 | 結果 | `/implement 甲` |\n"
            "| 2099-11-01 | M6 2 乙 | 結果 | `/implement 乙` |"
        )
        lines = self.with_row(rows).splitlines()
        first = next(i for i, line in enumerate(lines) if line.startswith("| 2099-10-31 |"))
        lines[first], lines[first + 1] = lines[first + 1], lines[first]
        assert self.check("\n".join(lines)) == []

    def next_step_problems(self, next_step: str) -> list[str]:
        row = f"| 2099-10-31 | M6 1 甲 | 結果 | {next_step} |"
        return [item for item in self.check(self.with_row(row)) if "下一步" in item]

    @pytest.mark.parametrize(
        "next_step",
        [
            "下一張票",
            "/implement .scratch/m6/issues/02-x.md",
            "開工 `docs/roadmap.md`",
            "`implement`",
            "先等使用者：要不要發版",
            "",
        ],
    )
    def test_a_last_row_without_a_next_command_is_caught(self, next_step: str) -> None:
        assert self.next_step_problems(next_step) != []

    @pytest.mark.parametrize(
        "next_step",
        [
            "`/implement .scratch/m6/issues/02-x.md`",
            "新 session 下 `/to-tickets docs/roadmap.md 拆 M6 的票`",
            "等使用者：要不要發版",
        ],
    )
    def test_a_named_next_step_is_not_caught(self, next_step: str) -> None:
        assert self.next_step_problems(next_step) == []

    def test_only_the_last_row_needs_a_next_command(self) -> None:
        rows = (
            "| 2099-10-31 | M6 1 甲 | 結果 | 寫成散文的舊列 |\n"
            "| 2099-11-01 | M6 2 乙 | 結果 | `/implement 乙` |"
        )
        assert self.check(self.with_row(rows)) == []

    def test_an_empty_log_is_not_caught(self) -> None:
        lines = [line for line in self.text().splitlines() if not _ROW.match(line)]
        assert self.check("\n".join(lines)) == []

    def decider_problems(self, line: str) -> list[str]:
        return [item for item in self.check(decision=line) if "決定者" in item]

    def test_a_new_decision_without_a_decider_is_caught(self) -> None:
        assert self.decider_problems("- 2026-11-12 M6 票 99：改了門檻") != []
        assert self.decider_problems("- 2099-01-01 M6 票 99：使用者定了門檻") != []

    @pytest.mark.parametrize("mark", DECIDERS)
    def test_a_decider_anywhere_in_the_line_is_not_caught(self, mark: str) -> None:
        assert self.decider_problems(f"- 2026-11-12 M6 票 99：改了門檻{mark}，改 plan §1。") == []
        assert self.decider_problems(f"- 2026-11-12 M6{mark}：改了門檻。") == []

    def test_decisions_before_the_rule_need_no_decider(self) -> None:
        assert self.decider_problems("- 2026-11-11 M6 票 99：改了門檻") == []
