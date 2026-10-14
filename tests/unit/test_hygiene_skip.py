"""CI hygiene job 的 `SKIP` 與 `.pre-commit-config.yaml` 裡「靠本機工具」的 hook 一致。

hygiene job 只補檔案衛生，`language: system` 的 hook（mypy、eslint 等）由別的 job 跑，所以得 SKIP。
新增這類 hook 卻忘了加進 SKIP，CI 會紅在 hygiene（web-knip 發生過）。
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def system_hooks(config: dict[str, Any]) -> set[str]:
    """`language: system` 且會在 pre-commit 階段跑的 hook id。"""
    found: set[str] = set()
    for repo in config["repos"]:
        for hook in repo["hooks"]:
            stages = hook.get("stages")
            if hook.get("language") == "system" and (not stages or "pre-commit" in stages):
                found.add(hook["id"])
    return found


def hygiene_skip(workflow: dict[str, Any]) -> set[str]:
    for step in workflow["jobs"]["hygiene"]["steps"]:
        if "pre-commit run" in step.get("run", ""):
            return {s.strip() for s in step["env"]["SKIP"].split(",") if s.strip()}
    raise AssertionError("hygiene job has no `pre-commit run` step with env.SKIP")


def mismatch(config: dict[str, Any], workflow: dict[str, Any]) -> set[str]:
    """兩邊只在一邊出現的 hook id。"""
    return system_hooks(config) ^ hygiene_skip(workflow)


def _load() -> tuple[dict[str, Any], dict[str, Any]]:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    return config, workflow


def test_hygiene_skip_matches_local_only_hooks() -> None:
    config, workflow = _load()
    assert mismatch(config, workflow) == set(), (
        "ci.yml hygiene `SKIP` and the `language: system` hooks in .pre-commit-config.yaml "
        "differ; add the new hook id to SKIP (or run it in its own CI job first)"
    )


def test_a_new_system_hook_is_reported() -> None:
    config, workflow = _load()
    config = copy.deepcopy(config)
    config["repos"][-1]["hooks"].append({"id": "fake-tool", "language": "system"})
    assert mismatch(config, workflow) == {"fake-tool"}


def test_a_stale_skip_entry_is_reported() -> None:
    config, workflow = _load()
    workflow = copy.deepcopy(workflow)
    step = next(
        s for s in workflow["jobs"]["hygiene"]["steps"] if "pre-commit run" in s.get("run", "")
    )
    step["env"]["SKIP"] += ",gone"
    assert mismatch(config, workflow) == {"gone"}


def test_order_and_whitespace_of_skip_do_not_matter() -> None:
    config, workflow = _load()
    workflow = copy.deepcopy(workflow)
    step = next(
        s for s in workflow["jobs"]["hygiene"]["steps"] if "pre-commit run" in s.get("run", "")
    )
    step["env"]["SKIP"] = " , ".join(reversed(step["env"]["SKIP"].split(",")))
    assert mismatch(config, workflow) == set()


def test_commit_msg_stage_hook_is_not_required_in_skip() -> None:
    config = {
        "repos": [
            {
                "hooks": [
                    {"id": "commit-msg", "language": "python", "stages": ["commit-msg"]},
                    {"id": "tool", "language": "system", "stages": ["commit-msg", "pre-commit"]},
                    {"id": "msg-only", "language": "system", "stages": ["commit-msg"]},
                ]
            }
        ]
    }
    assert system_hooks(config) == {"tool"}
