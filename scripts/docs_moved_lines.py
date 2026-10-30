"""Prove a doc split lost nothing: each line removed from a source file shows up in a destination.

    python scripts/docs_moved_lines.py <base-ref> <source> -- <destination>...

"Removed" is what `git diff <base-ref> -- <source>` deletes. Lines are compared stripped; blank
lines and table separator rows (`| --- | --- |`) are skipped. Markdown link targets are compared
without their leading `./` / `../` prefixes, so a file moved one directory deeper still matches
once its relative links gain a `../`. Exits 1 and lists the missing lines
if any is not found.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

_TABLE_RULE = re.compile(r"^\|(\s*:?-+:?\s*\|)+$")
_LINK_PREFIX = re.compile(r"(\]\()(?:\.{1,2}/)+")


def _normalized(line: str) -> str:
    """The line with the `./` / `../` prefix dropped from each markdown link target."""
    return _LINK_PREFIX.sub(r"\1", line.strip())


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
    present = {_normalized(line) for text in destinations for line in text.splitlines()}
    return [line for line in removed if _normalized(line) not in present]


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
    print(f"removed {len(removed)} lines, found {len(removed) - len(lost)}, missing {len(lost)}")
    for line in lost:
        print(f"  missing: {line}")
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
