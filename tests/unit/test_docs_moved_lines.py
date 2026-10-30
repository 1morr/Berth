"""`scripts/docs_moved_lines.py`：搬走的行都找得到時綠，少一行就紅。

空行、表格分隔列與縮排不算；連結目標只差 `./` `../` 前綴也算找到。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "docs_moved_lines", Path(__file__).parents[2] / "scripts" / "docs_moved_lines.py"
)
assert _SPEC and _SPEC.loader
moved = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(moved)

DIFF = """\
--- a/docs/progress.md
+++ b/docs/progress.md
@@ -3,5 +3,2 @@
-| 2026-09-07 | 文件 | 完成 |
-
-| --- | --- |
-  - 縮排的續行
+| 2026-09-07 | M0 文件 | 完成 |
"""


def test_removed_lines_skip_blank_rules_and_headers() -> None:
    assert moved.removed_lines(DIFF) == ["| 2026-09-07 | 文件 | 完成 |", "- 縮排的續行"]


def test_found_when_every_line_is_in_some_destination() -> None:
    removed = moved.removed_lines(DIFF)
    destinations = ["| 2026-09-07 | 文件 | 完成 |\n", "x\n    - 縮排的續行\n"]
    assert moved.missing_lines(removed, destinations) == []


def test_missing_line_is_reported() -> None:
    removed = moved.removed_lines(DIFF)
    assert moved.missing_lines(removed, ["| 2026-09-07 | 文件 | 完成 |\n"]) == ["- 縮排的續行"]


def test_link_targets_differing_only_in_relative_depth_are_found() -> None:
    removed = [
        "見 [指南](guide/a.md) 與 [README](../README.md#x)。",
        "[外部](https://example.com/a)",
    ]
    moved_deeper = [
        "見 [指南](../guide/a.md) 與 [README](../../README.md#x)。\n[外部](https://example.com/a)"
    ]
    assert moved.missing_lines(removed, moved_deeper) == []


def test_link_text_or_target_name_changes_are_still_missing() -> None:
    removed = ["見 [指南](guide/a.md)。", "[R](../README.md#x)", "[E](https://e.com/a)"]
    changed = ["見 [說明](../guide/a.md)。\n[R](../../README.md#y)\n[E](https://e.com/../a)"]
    assert moved.missing_lines(removed, changed) == removed


def test_main_exits_1_on_a_lost_line_and_0_when_all_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    source = tmp_path / "src.md"
    source.write_text("keep\nmove me\nlose me\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")
    source.write_text("keep\n", encoding="utf-8")
    destination = tmp_path / "dest.md"
    destination.write_text("move me\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    def run() -> int:
        return int(moved.main(["x", "HEAD", "src.md", "--", "dest.md"]))

    assert run() == 1
    destination.write_text("move me\nlose me\n", encoding="utf-8")
    assert run() == 0
