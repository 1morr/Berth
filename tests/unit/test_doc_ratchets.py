"""兩個只能減少的數字：文件結構才搬得動，brief 與 plan 才只寫現況。

- 程式碼裡引用 brief / plan 章節號（`plan §3.2`、`brief §20`）的行數。引用了，節就不能
  重排（docs-diet 因此不能動編號）。新程式碼引 ADR 編號或直接寫出理由。
- `docs/design-brief.md`、`docs/plan.md` 裡寫了票號（`票 12`）的行數。票號是歷史，
  留在票、`docs/progress.md` 與 `docs/archive/`。

上限是現況；減少後把常數跟著調低，不調高。只數 git 追蹤的檔，Markdown、`docs/`、
`.scratch/` 與本檔不算程式碼。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECTION_REF = re.compile(r"(?:plan|brief)(?:\.md)?\s*§\s*\d", re.I)
TICKET_NUMBER = re.compile(r"票\s*\d")
NOT_CODE = ("docs/", ".scratch/", "tests/unit/test_doc_ratchets.py")
MAX_SECTION_REF_LINES = 2813
MAX_TICKET_NUMBER_LINES = {"docs/design-brief.md": 161, "docs/plan.md": 42}


def lines_matching(pattern: re.Pattern[str], text: str) -> int:
    return sum(1 for line in text.split("\n") if pattern.search(line))


def is_code(path: str) -> bool:
    return not path.lower().endswith(".md") and not path.startswith(NOT_CODE)


def section_ref_lines(root: Path) -> int:
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode("utf-8")
    total = 0
    for path in filter(None, listed.split("\0")):
        file = root / path
        if not is_code(path) or not file.is_file():
            continue
        data = file.read_bytes()
        if b"\0" not in data:
            total += lines_matching(SECTION_REF, data.decode("utf-8", "replace"))
    return total


def test_code_does_not_gain_section_references() -> None:
    found = section_ref_lines(ROOT)
    assert found <= MAX_SECTION_REF_LINES, (
        f"程式碼引用 brief / plan 章節號的行數 {found}，上限 {MAX_SECTION_REF_LINES}："
        "新加的改引 ADR 編號或直接寫出理由"
    )


def test_brief_and_plan_do_not_gain_ticket_numbers() -> None:
    for path, limit in MAX_TICKET_NUMBER_LINES.items():
        found = lines_matching(TICKET_NUMBER, (ROOT / path).read_text(encoding="utf-8"))
        assert found <= limit, f"{path} 寫了票號的行數 {found}，上限 {limit}：只寫現在的做法"


class TestTheCountsThemselves:
    """違規會多算一行，無關的寫法不會。"""

    def test_section_references_are_counted(self) -> None:
        for line in ("# 見 plan §3.2", "// brief §20.4 的規則", "/* docs/plan.md § 11 */"):
            assert lines_matching(SECTION_REF, f"x = 1\n{line}\n") == 1

    def test_other_pointers_are_not_counted(self) -> None:
        text = "# ADR 0008；plan 與 brief 兩個字本身不算；§ 單獨出現也不算\n# spec §2\n"
        assert lines_matching(SECTION_REF, text) == 0

    def test_ticket_numbers_are_counted(self) -> None:
        assert lines_matching(TICKET_NUMBER, "照 M4 票 12 的做法\n（票3）\n拆票後以票為準\n") == 2

    def test_docs_and_markdown_are_not_code(self) -> None:
        assert is_code("berth/services/jobs.py")
        assert is_code("web/src/api/schemas.ts")
        for path in ("docs/plan.md", "berth/README.md", ".scratch/m6/spec.md", NOT_CODE[-1]):
            assert not is_code(path)
