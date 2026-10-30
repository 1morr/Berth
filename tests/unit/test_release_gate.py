"""發版的閘門：推 image 與建 Release 的 job，要先等這個 tag 的 CI 與 e2e 都綠。

0.4.0 以前 `release.yml`、`e2e.yml` 各自由 `v*` tag 觸發、互不等待：image 三分鐘就推上 `:latest`，
真服務的 e2e 要再跑半小時多；e2e 紅了，使用者早就拉到那一版。現在 `release.yml` 用 `uses:` 呼叫
`ci.yml` 與 `e2e.yml`，發佈的 job 經 `needs` 等它們。這裡讀真正的 workflow 檔；`TestTheGateItself`
造違規證明會紅、改無關的寫法證明不紅。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
GATES = ("ci.yml", "e2e.yml")


def _load(text: str) -> dict[str, Any]:
    workflow: dict[Any, Any] = yaml.safe_load(text)
    # PyYAML 照 YAML 1.1 把 `on` 讀成 True。
    if True in workflow:
        workflow["on"] = workflow.pop(True)
    return workflow


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    on = workflow.get("on") or {}
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return dict.fromkeys(on)
    return dict(on)


def _publishes(job: dict[str, Any]) -> bool:
    """推 image 或建 Release 的 job。"""
    for step in job.get("steps", []):
        if str(step.get("uses", "")).startswith("docker/build-push-action") and step.get(
            "with", {}
        ).get("push"):
            return True
        if "gh release" in step.get("run", ""):
            return True
    return False


def _upstream(jobs: dict[str, Any], name: str) -> set[str]:
    """`name` 經 `needs` 直接或間接等的 job。"""
    seen: set[str] = set()
    todo = [name]
    while todo:
        needs = jobs[todo.pop()].get("needs", [])
        for need in [needs] if isinstance(needs, str) else needs:
            if need not in seen:
                seen.add(need)
                todo.append(need)
    return seen


def problems(release: str, called: dict[str, str]) -> list[str]:
    found: list[str] = []
    jobs: dict[str, Any] = _load(release)["jobs"]
    calls = {
        name: str(job["uses"]).removeprefix("./.github/workflows/")
        for name, job in jobs.items()
        if "uses" in job
    }
    publishing = [name for name, job in jobs.items() if _publishes(job)]
    if not publishing:
        found.append("release.yml has no job that pushes the image or creates the Release")
    for name in publishing:
        waited = {calls[up] for up in _upstream(jobs, name) if up in calls}
        for gate in GATES:
            if gate not in waited:
                found.append(f"release.yml job `{name}` publishes without waiting for {gate}")
    for gate, text in called.items():
        triggers = _triggers(_load(text))
        if "workflow_call" not in triggers:
            found.append(f"{gate} cannot be called by release.yml (no workflow_call)")
        tags = (triggers.get("push") or {}).get("tags")
        if tags:
            found.append(f"{gate} also runs on tag push: a second, ungated run of the same tag")
    return found


def _read(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_release_publishes_only_after_ci_and_e2e() -> None:
    assert problems(_read("release.yml"), {gate: _read(gate) for gate in GATES}) == []


class TestTheGateItself:
    """違規會紅，無關的改動不會。"""

    def _real(self) -> tuple[str, dict[str, str]]:
        return _read("release.yml"), {gate: _read(gate) for gate in GATES}

    def test_publishing_before_e2e_is_caught(self) -> None:
        release, called = self._real()
        cut = release.replace("    needs: e2e\n", "    needs: ci\n", 1)
        assert cut != release
        assert problems(cut, called) == [
            "release.yml job `image` publishes without waiting for e2e.yml",
            "release.yml job `release` publishes without waiting for e2e.yml",
        ]

    def test_a_gate_that_cannot_be_called_is_caught(self) -> None:
        release, called = self._real()
        called["ci.yml"] = called["ci.yml"].replace("  workflow_call:\n", "", 1)
        assert problems(release, called) == [
            "ci.yml cannot be called by release.yml (no workflow_call)"
        ]

    def test_e2e_triggered_by_tags_again_is_caught(self) -> None:
        release, called = self._real()
        called["e2e.yml"] = called["e2e.yml"].replace(
            "  workflow_dispatch:\n", "  workflow_dispatch:\n  push:\n    tags: ['v*']\n", 1
        )
        assert problems(release, called) == [
            "e2e.yml also runs on tag push: a second, ungated run of the same tag"
        ]

    def test_unrelated_edits_stay_green(self) -> None:
        release, called = self._real()
        # 改 job 的顯示名稱、加註解、`needs` 改寫成清單：都不影響順序。
        edited = release.replace("    name: image\n", "    name: publish image\n", 1).replace(
            "    needs: e2e\n", "    # gate\n    needs: [e2e]\n", 1
        )
        assert edited != release
        assert problems(edited, called) == []
