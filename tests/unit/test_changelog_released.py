"""CHANGELOG 已發版的段落不准改：條目只能寫在 `[Unreleased]`。

拿最近的 `v*` tag 上的 CHANGELOG.md 對工作目錄的：tag 裡有的版本段，現在必須原封不動在。
發版把 `[Unreleased]` 改名成新版本是新增一段，不算改動。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_HEADING = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)


def sections(text: str) -> dict[str, str]:
    """版本字串 -> 該段到下一個 `## [` 之前的全文；`Unreleased` 不算。"""
    matches = list(_HEADING.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        if m.group(1) != "Unreleased":
            out[m.group(1)] = text[m.start() : end]
    return out


def changed_released(old_text: str, new_text: str) -> list[str]:
    """old 裡有的版本，new 裡缺了或內容不同。"""
    new = sections(new_text)
    return [v for v, body in sections(old_text).items() if new.get(v) != body]


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AssertionError(
            f"`git {' '.join(args)}` failed ({exc}). This gate needs git and the v* tags "
            "(CI: actions/checkout with fetch-depth: 0); it must not be skipped."
        ) from exc
    return result.stdout


def test_released_sections_are_untouched() -> None:
    tag = _git("describe", "--tags", "--abbrev=0", "--match", "v*").strip()
    old = _git("show", f"{tag}:CHANGELOG.md")
    new = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    changed = changed_released(old, new)
    assert not changed, (
        f"CHANGELOG sections already released in {tag} were edited: {changed}. "
        "New entries belong under `## [Unreleased]`."
    )


_SAMPLE = """# Changelog

## [Unreleased]

- pending

## [0.2.0] - 2026-01-02

### Changed

- a thing

## [0.1.0] - 2026-01-01

- first
"""


def test_sections_skips_unreleased_and_splits_on_headings() -> None:
    got = sections(_SAMPLE)
    assert list(got) == ["0.2.0", "0.1.0"]
    assert "a thing" in got["0.2.0"] and "first" not in got["0.2.0"]


def test_editing_a_released_section_is_reported() -> None:
    assert changed_released(_SAMPLE, _SAMPLE.replace("a thing", "a thinG")) == ["0.2.0"]


def test_removing_a_released_section_is_reported() -> None:
    assert changed_released(_SAMPLE, _SAMPLE.split("## [0.1.0]")[0]) == ["0.1.0"]


def test_unreleased_edits_are_not_reported() -> None:
    assert changed_released(_SAMPLE, _SAMPLE.replace("- pending", "- pending\n- more")) == []


def test_renaming_unreleased_into_a_new_release_is_not_reported() -> None:
    new = _SAMPLE.replace(
        "## [Unreleased]\n\n- pending\n",
        "## [Unreleased]\n\n## [9.9.9] - 2026-02-01\n\n- pending\n",
    )
    assert changed_released(_SAMPLE, new) == []
