"""commit-msg hook: subject follows Conventional Commits and fits in 72 characters."""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_SUBJECT = 72
EXEMPT_PREFIXES = ("Merge ", 'Revert "', "fixup! ", "squash! ", "amend! ")
PATTERN = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|merge)"
    r"(\([^)]+\))?!?: [^A-Z\s]"
)


def subject_of(message: str) -> str:
    """The first line that is not a `#` comment; empty if there is none."""
    for line in message.splitlines():
        if not line.startswith("#"):
            return line
    return ""


def problems(subject: str) -> list[str]:
    if subject.startswith(EXEMPT_PREFIXES):
        return []
    found: list[str] = []
    if len(subject) > MAX_SUBJECT:
        found.append(f"subject is {len(subject)} characters, the limit is {MAX_SUBJECT}")
    if not PATTERN.match(subject):
        found.append(
            "expected `<type>(<scope>)?!?: <lowercase description>` with type one of "
            "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|merge"
        )
    return found


def main(argv: list[str]) -> int:
    subject = subject_of(Path(argv[1]).read_text(encoding="utf-8"))
    found = problems(subject)
    if not found:
        return 0
    print(f"commit message rejected: {subject!r}", file=sys.stderr)
    for reason in found:
        print(f"  - {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
