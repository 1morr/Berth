"""每個 session 第一份讀的兩個檔有大小上限（單位：字元，Python `len`）。

- `CLAUDE.md` ≤ 6,000 字：每個 session 都整份讀。
- `docs/progress.md` ≤ 20,000 字：一次 Read、不帶 offset 就讀得完。

只比總字數；換行、空行重排而字數不變，結果不變。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD_LIMIT = 6_000
PROGRESS_LIMIT = 20_000


def test_claude_md_within_budget() -> None:
    size = len((ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    assert size <= CLAUDE_MD_LIMIT, (
        f"CLAUDE.md {size} 字，超過上限 {CLAUDE_MD_LIMIT} 字（多 {size - CLAUDE_MD_LIMIT}）："
        "先刪打開程式碼就查得到的段落，不要靠縮短措辭湊數"
    )


def test_progress_md_within_budget() -> None:
    size = len((ROOT / "docs" / "progress.md").read_text(encoding="utf-8"))
    assert size <= PROGRESS_LIMIT, (
        f"docs/progress.md {size} 字，超過上限 {PROGRESS_LIMIT} 字（多 {size - PROGRESS_LIMIT}）："
        "把進行中里程碑的舊列與條也封存到 docs/archive/<里程碑>.md"
        "（做法見該檔〈寫法與封存〉，用 scripts/docs_moved_lines.py 證明沒丟）"
    )
