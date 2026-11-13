"""`.scratch/` 下沒驗收的目錄，都是開工 session 做完三步的結果（`CLAUDE.md`〈Skills〉）。

- 同時有含五段的 `spec.md` 和 `issues/` 裡至少一張票：擋掉「有票沒 spec」和「還沒開工就預建 spec」。
- 它在 plan §11 的那一節縮成一行、連到 spec：內容只留一份，標題與編號留給程式碼引用。
  不在 §11 的目錄（docs-diet 這類）沒有這一節，不查。
- 在 §11 有一節的里程碑，`issues/` 裡有一張 `-acceptance.md` 結尾的驗收票；只看有沒有，
  不看編號（驗收後補的票照樣放行）。它的 spec 有一個「使用者試」標題：驗收票封存前
  使用者要親手試的清單（`CLAUDE.md`〈每個 session 的流程〉第 5 步）。

「已驗收」與目錄名都讀 `docs/progress.md` 的里程碑表：M0–M5 與 docs-diet 是歷史快照，
新增里程碑不必改這裡。只比段落標題與連結，不比措辭；標題層級、多的段落、旁邊的 shape 檔
都不影響結果。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / ".scratch"
PROGRESS = ROOT / "docs" / "progress.md"
PLAN = ROOT / "docs" / "plan.md"
SPEC_SECTIONS = ("目標", "範圍", "共同規則", "驗收", "票序")
USER_TRIAL = "使用者試"
_TABLE_ROW = re.compile(
    r"^\|\s*(\S+)\s*\|\s*`\.scratch/([^/`]+)/[^|]*\|[^|]*\|\s*(.*?)\s*\|\s*$", re.M
)
_HEADING = re.compile(r"^#+\s+(.+?)\s*$", re.M)


def _plan_section(plan: str, milestone: str) -> str | None:
    match = re.search(
        rf"^### 11\.\S+ {re.escape(milestone)} .*?\n(.*?)(?=^##|\Z)", plan, flags=re.M | re.S
    )
    return match.group(1) if match else None


def problems(scratch: Path, progress: str, plan: str) -> list[str]:
    rows = _TABLE_ROW.findall(progress)
    accepted = {directory for _, directory, note in rows if note.startswith("已驗收")}
    milestones = {directory: name for name, directory, _ in rows}
    found: list[str] = []
    for directory in sorted(path for path in scratch.iterdir() if path.is_dir()):
        name = directory.name
        if name in accepted:
            continue
        spec = directory / "spec.md"
        headings: list[str] = []
        if spec.is_file():
            headings = _HEADING.findall(spec.read_text(encoding="utf-8"))
            missing = [section for section in SPEC_SECTIONS if section not in headings]
            if missing:
                found.append(f"{name}/spec.md 缺段落：{missing}")
        else:
            found.append(f"{name} 沒有 spec.md")
        if not any((directory / "issues").glob("*.md")):
            found.append(f"{name}/issues/ 沒有票")
        section = _plan_section(plan, milestones.get(name, name))
        if section is not None and not any((directory / "issues").glob("*-acceptance.md")):
            found.append(f"{name}/issues/ 沒有驗收票：里程碑最後一張是 NN-{name}-acceptance.md")
        if section is not None and spec.is_file() and USER_TRIAL not in headings:
            found.append(f"{name}/spec.md 的〈驗收〉底下沒有「### {USER_TRIAL}」")
        if section is not None:
            body = [line for line in section.splitlines() if line.strip()]
            if len(body) != 1 or f".scratch/{name}/spec.md" not in body[0]:
                found.append(f"plan §11 裡 {name} 那一節沒有縮成一行連到 spec")
    return found


def test_scratch_directories_follow_the_kickoff() -> None:
    progress = PROGRESS.read_text(encoding="utf-8")
    assert problems(SCRATCH, progress, PLAN.read_text(encoding="utf-8")) == []


class TestTheGateItself:
    """違規會紅，無關的格式改動不會。里程碑表用真的，目錄樹與 plan 是假的。"""

    PLAN_DONE = (
        "### 11.7 M6 人工接管開關\n\n內容在 `.scratch/m6/spec.md`。\n\n"
        "### 11.8 M7 Discord 與 MCP\n\n範圍：還沒開工。\n驗收：還沒開工。\n"
    )

    def progress(self) -> str:
        return PROGRESS.read_text(encoding="utf-8")

    def kicked_off(self, scratch: Path, name: str = "m6", acceptance: bool = True) -> Path:
        directory = scratch / name
        (directory / "issues").mkdir(parents=True)
        (directory / "issues" / "01-first.md").write_text("# 01\n", encoding="utf-8")
        if acceptance:
            ticket = directory / "issues" / f"02-{name}-acceptance.md"
            ticket.write_text("# 02\n", encoding="utf-8")
        spec = "".join(f"## {section}\n\n內文\n\n" for section in SPEC_SECTIONS)
        spec = spec.replace("## 票序\n", f"### {USER_TRIAL}\n\n無。\n\n## 票序\n")
        (directory / "spec.md").write_text(spec, encoding="utf-8")
        return directory

    def check(self, scratch: Path, plan: str = PLAN_DONE) -> list[str]:
        return problems(scratch, self.progress(), plan)

    def test_tickets_without_a_spec_are_caught(self, tmp_path: Path) -> None:
        (self.kicked_off(tmp_path) / "spec.md").unlink()
        assert any("沒有 spec.md" in item for item in self.check(tmp_path))

    def test_a_spec_without_tickets_is_caught(self, tmp_path: Path) -> None:
        (self.kicked_off(tmp_path, acceptance=False) / "issues" / "01-first.md").unlink()
        assert any("沒有票" in item for item in self.check(tmp_path))

    def test_a_spec_without_an_issues_directory_is_caught(self, tmp_path: Path) -> None:
        directory = self.kicked_off(tmp_path, acceptance=False)
        (directory / "issues" / "01-first.md").unlink()
        (directory / "issues").rmdir()
        assert any("沒有票" in item for item in self.check(tmp_path))

    @pytest.mark.parametrize("section", SPEC_SECTIONS)
    def test_a_spec_missing_a_section_is_caught(self, tmp_path: Path, section: str) -> None:
        spec = self.kicked_off(tmp_path) / "spec.md"
        text = spec.read_text(encoding="utf-8").replace(f"## {section}\n", "## 別的\n")
        spec.write_text(text, encoding="utf-8")
        assert any(section in item for item in self.check(tmp_path))

    def test_a_section_named_only_in_prose_is_caught(self, tmp_path: Path) -> None:
        spec = self.kicked_off(tmp_path) / "spec.md"
        text = spec.read_text(encoding="utf-8").replace("## 票序\n", "票序\n")
        spec.write_text(text, encoding="utf-8")
        assert any("票序" in item for item in self.check(tmp_path))

    def test_a_milestone_spec_without_the_user_trial_is_caught(self, tmp_path: Path) -> None:
        spec = self.kicked_off(tmp_path) / "spec.md"
        for replacement in ("### 人工檢查\n", f"{USER_TRIAL}\n"):
            text = spec.read_text(encoding="utf-8")
            spec.write_text(text.replace(f"### {USER_TRIAL}\n", replacement), encoding="utf-8")
            assert any(USER_TRIAL in item for item in self.check(tmp_path))
            spec.write_text(text, encoding="utf-8")

    def test_a_directory_missing_from_the_table_is_caught(self, tmp_path: Path) -> None:
        (tmp_path / "someday").mkdir()
        assert self.check(tmp_path) != []

    def test_an_accepted_milestone_needs_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "m0").mkdir()
        (tmp_path / "docs-diet").mkdir()
        assert self.check(tmp_path) == []

    def test_a_milestone_not_marked_accepted_is_checked(self, tmp_path: Path) -> None:
        (tmp_path / "m4").mkdir()
        progress = self.progress().replace("| 已驗收（2026-10-23）", "| 進行中（2026-10-23）")
        assert problems(tmp_path, progress, self.PLAN_DONE) != []

    def test_a_plan_section_left_in_full_is_caught(self, tmp_path: Path) -> None:
        self.kicked_off(tmp_path)
        plan = self.PLAN_DONE.replace("內容在 `.scratch/m6/spec.md`。", "範圍：\n驗收：")
        assert any("縮成一行" in item for item in self.check(tmp_path, plan))

    def test_a_plan_line_without_the_link_is_caught(self, tmp_path: Path) -> None:
        self.kicked_off(tmp_path)
        plan = self.PLAN_DONE.replace("內容在 `.scratch/m6/spec.md`。", "內容搬走了。")
        assert any("縮成一行" in item for item in self.check(tmp_path, plan))

    def test_a_milestone_without_an_acceptance_ticket_is_caught(self, tmp_path: Path) -> None:
        self.kicked_off(tmp_path, acceptance=False)
        assert any("驗收票" in item for item in self.check(tmp_path))

    def test_the_acceptance_ticket_may_be_renumbered_rewritten_or_followed(
        self, tmp_path: Path
    ) -> None:
        issues = self.kicked_off(tmp_path) / "issues"
        (issues / "02-m6-acceptance.md").rename(issues / "07-m6-acceptance.md")
        (issues / "07-m6-acceptance.md").write_text("# 07 驗收\n\n別的內文\n", encoding="utf-8")
        (issues / "08-after.md").write_text("# 08\n", encoding="utf-8")
        assert self.check(tmp_path) == []

    def test_a_complete_kickoff_is_not_caught(self, tmp_path: Path) -> None:
        self.kicked_off(tmp_path)
        assert self.check(tmp_path) == []

    def test_a_directory_outside_plan_11_only_needs_spec_and_tickets(self, tmp_path: Path) -> None:
        spec = self.kicked_off(tmp_path, "someday", acceptance=False) / "spec.md"
        text = spec.read_text(encoding="utf-8").replace(f"### {USER_TRIAL}\n\n無。\n\n", "")
        spec.write_text(text, encoding="utf-8")
        assert self.check(tmp_path) == []

    def test_unrelated_formatting_is_not_caught(self, tmp_path: Path) -> None:
        directory = self.kicked_off(tmp_path)
        spec = directory / "spec.md"
        text = spec.read_text(encoding="utf-8").replace("## ", "### ")
        spec.write_text("# M6\n\n" + text + "## 附錄\n", encoding="utf-8")
        (directory / "agent-shape.md").write_text("# shape\n", encoding="utf-8")
        (tmp_path / ".DS_Store").write_text("", encoding="utf-8")
        progress = self.progress().replace("\n\n", "\n\n\n").replace("| --- |", "|:---|")
        plan = self.PLAN_DONE.replace("\n\n", "\n\n\n")
        assert problems(tmp_path, progress, plan) == []
