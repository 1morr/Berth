"""commit-msg hook (`scripts/check_commit_msg.py`) 雙向驗證：違規會紅，合法與無關格式不會紅。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_commit_msg", Path(__file__).parents[2] / "scripts" / "check_commit_msg.py"
)
assert _SPEC and _SPEC.loader
check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check)


@pytest.mark.parametrize(
    "subject",
    [
        "feat: add thing",
        "fix(parser): handle empty title",
        "feat(api)!: drop the old route",
        "merge: ticket 62 jellyfin scan scope",
        "chore: release 0.2.7",
        "Merge branch 'main' into x",
        'Revert "feat: add thing"',
        "fixup! feat: add thing",
        "squash! feat: add thing",
        "amend! feat: add thing",
        "feat: " + "x" * 66,  # exactly 72
    ],
)
def test_valid_subjects_pass(subject: str) -> None:
    assert len(subject) <= 72
    assert check.problems(subject) == []


@pytest.mark.parametrize(
    "subject",
    [
        "feat: " + "x" * 67,  # 73
        "feat: Add thing",
        "add thing",
        "wip: add thing",
        "feat:add thing",
        "feat:  add thing",
        "feat(): add thing",
        "",
    ],
)
def test_invalid_subjects_fail(subject: str) -> None:
    assert check.problems(subject)


def test_subject_is_first_non_comment_line() -> None:
    message = (
        "# Please enter the commit message\n# more\nfix: real subject\n\nBody Line.\n# trailing\n"
    )
    assert check.subject_of(message) == "fix: real subject"
    assert check.problems(check.subject_of(message)) == []


def test_body_and_blank_lines_do_not_matter() -> None:
    bad = "Fix: Bad subject\n\nfeat: looks fine in the body\n"
    assert check.problems(check.subject_of(bad))


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = tmp_path / "good"
    good.write_text("fix: ok\n", encoding="utf-8")
    bad = tmp_path / "bad"
    bad.write_text("Fix: nope\n", encoding="utf-8")
    assert check.main(["x", str(good)]) == 0
    assert check.main(["x", str(bad)]) == 1
    assert "Fix: nope" in capsys.readouterr().err
