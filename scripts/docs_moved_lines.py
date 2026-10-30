"""Prove a doc split lost nothing: each line removed from a source file shows up in a destination.

    python scripts/docs_moved_lines.py <base-ref> <source> -- <destination>...

"Removed" is what `git diff <base-ref> -- <source>` deletes. Lines are compared stripped; blank
lines and table separator rows (`| --- | --- |`) are skipped. Exits 1 and lists the missing lines
if any is not found.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

_TABLE_RULE = re.compile(r"^\|(\s*:?-+:?\s*\|)+$")


def removed_lines(diff: str) -> list[str]:
    """The stripped, non-trivial lines a unified diff deletes."""
    found = []
    for raw in diff.splitlines():
        if not raw.startswith("-") or raw.startswith("---"):
            continue
        line = raw[1:].strip()
        if line and not _TABLE_RULE.match(line):
            found.append(line)
    return found


def missing_lines(removed: Iterable[str], destinations: Iterable[str]) -> list[str]:
    """The removed lines that appear (stripped) in none of the destination texts."""
    present = {line.strip() for text in destinations for line in text.splitlines()}
    return [line for line in removed if line not in present]


def main(argv: list[str]) -> int:
    if len(argv) < 5 or argv[3] != "--":
        print(__doc__, file=sys.stderr)
        return 2
    base, source, destinations = argv[1], argv[2], argv[4:]
    diff = subprocess.run(
        ["git", "diff", "--no-color", "-U0", base, "--", source],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    removed = removed_lines(diff)
    lost = missing_lines(removed, (Path(path).read_text(encoding="utf-8") for path in destinations))
    print(f"刪 {len(removed)} 行、找到 {len(removed) - len(lost)} 行、遺失 {len(lost)} 行")
    for line in lost:
        print(f"  遺失：{line}")
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
