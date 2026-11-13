"""`docs/` 第一層的每個檔與資料夾，名字都出現在 `CLAUDE.md`。

指令檔沒提到的文件，agent 不知道它存在；固定的檔名與位置也讓別的 skill 找得到檔
（`CLAUDE.md`〈文件〉）。資料夾比對 `名字/`，檔案比對完整檔名；只看有沒有出現，不比措辭。
`docs/research/` 第一層檔名裡的日期放在最後（`<主題>-YYYY-MM-DD`）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATE_LAST = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def unlisted(docs: Path, guide: str) -> list[str]:
    found = []
    for entry in sorted(docs.iterdir()):
        name = entry.name + ("/" if entry.is_dir() else "")
        if not entry.name.startswith(".") and name not in guide:
            found.append(name)
    return found


def misdated(research: Path) -> list[str]:
    found = []
    for entry in sorted(research.iterdir()):
        stem = entry.name if entry.is_dir() else entry.name.split(".")[0]
        if _DATE.search(stem) and not _DATE_LAST.search(stem):
            found.append(entry.name)
    return found


def test_every_top_level_doc_is_listed_in_the_instructions() -> None:
    assert unlisted(ROOT / "docs", (ROOT / "CLAUDE.md").read_text(encoding="utf-8")) == []


def test_dated_research_files_end_with_the_date() -> None:
    assert misdated(ROOT / "docs" / "research") == []


class TestTheChecksThemselves:
    def test_an_unlisted_file_or_directory_is_caught(self, tmp_path: Path) -> None:
        (tmp_path / "notes.md").write_text("x", encoding="utf-8")
        (tmp_path / "design").mkdir()
        (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
        assert unlisted(tmp_path, "只提到 `docs/progress.md`") == ["design/", "notes.md"]
        assert unlisted(tmp_path, "`docs/design/` 與 `docs/notes.md`，措辭隨意。") == []

    def test_a_directory_needs_its_slash(self, tmp_path: Path) -> None:
        (tmp_path / "design").mkdir()
        assert unlisted(tmp_path, "提到 design 這個字但不是路徑") == ["design/"]

    def test_a_date_that_is_not_last_is_caught(self, tmp_path: Path) -> None:
        for name in (
            "2026-01-02-audit.md",
            "audit-2026-01-02.md",
            "audit-2026-01-02.json",
            "topic.md",
        ):
            (tmp_path / name).write_text("x", encoding="utf-8")
        (tmp_path / "trial-2026-01-02").mkdir()
        assert misdated(tmp_path) == ["2026-01-02-audit.md"]
