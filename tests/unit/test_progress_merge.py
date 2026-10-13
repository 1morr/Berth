"""`docs/progress.md` 用 git 的 union 合併（`.gitattributes`）之後的閘門。

平行的票各在 session 紀錄與「偏差與決定」的結尾追加一行，union 讓合併時兩邊都留、不停下來問。
它的失效方式是安靜的：兩邊改的位置靠得太近時，git 把它們當成同一塊，整段（含 `##` 標題）抄兩份、
不報衝突。所以這裡守兩件事：三個 `##` 段各出現一次、依序；非空行沒有重複（表格的分隔列除外，
每張表都有一條一樣的）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "docs" / "progress.md"
SECTIONS = ["里程碑與閱讀指引", "Session 紀錄", "偏差與決定"]
_TABLE_RULE = re.compile(r"^\|(\s*:?-+:?\s*\|)+$")


def problems(text: str) -> list[str]:
    found: list[str] = []
    headings = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    if headings != SECTIONS:
        found.append(f"## 段應該是 {SECTIONS}，實際是 {headings}")
    seen: set[str] = set()
    for line in text.splitlines():
        key = line.rstrip()
        if not key or _TABLE_RULE.match(key):
            continue
        if key in seen:
            found.append(f"重複的一行：{key[:80]}")
        seen.add(key)
    return found


def test_progress_has_no_union_merge_duplicates() -> None:
    assert problems(PROGRESS.read_text(encoding="utf-8")) == []


def test_gate_catches_a_duplicated_stretch() -> None:
    """union 把靠得太近的兩處當成一塊時的樣子（2026-10-13 在暫存 repo 重現過）。"""
    text = PROGRESS.read_text(encoding="utf-8")
    tail = text[text.index("## 偏差與決定") :]
    assert problems(text + "\n| 2026-10-13 | 另一邊的一列 |\n\n" + tail) != []


def test_gate_ignores_unrelated_formatting() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    reformatted = text.replace("\n\n", "\n\n\n").replace("| --- |", "|:---|")
    assert problems(reformatted) == []
