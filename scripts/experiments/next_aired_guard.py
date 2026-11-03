"""守衛「發佈時對到那一集的下一集已經播了就不擔保」會多擋幾筆已擔保的第一批（M5.5 票 05 量）。

票 05b 只把它採用在累計編號上（`parser.first_batch._next_aired`），所以現在累計編號那一行的「會擋」
應是 0，照字面那一行量的是「如果也套到照字面」的代價。

不改規則：包住 `first_batch_rule._vouch`，照它的三段（語料、對抗輪、`--online` 的 split-cour
與真 RSS）各跑一次，依讀法（照字面 / 累計編號）數擔保了幾筆、守衛會擋幾筆。TMDB 把前一季多記一集時，
累計編號換算早一集，「下一集」就是真的那一集，一定播過；被擋的照字面列是慢發的字幕組與一週播兩集的
劇，量的是這條的代價。

    uv run --env-file .env python scripts/experiments/next_aired_guard.py [--online]
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from berth.domain import FileEntry, MediaSnapshot, PlanItem
from berth.parser import episode_span

# 規則本身那一支，量的才是同一個條件；底線開頭是因為它只在 parser 內用。
from berth.parser.first_batch import _next_aired

REPO_ROOT = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location(
    "first_batch_rule", REPO_ROOT / "scripts" / "experiments" / "first_batch_rule.py"
)
assert spec is not None and spec.loader is not None
rule = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rule
spec.loader.exec_module(rule)

hits: Counter[str] = Counter()
original = rule._vouch


def _vouch(
    name: str, entries: tuple[FileEntry, ...], snapshot: MediaSnapshot, at: datetime
) -> tuple[tuple[PlanItem, ...], tuple[tuple[int, int, int], ...] | None]:
    items, vouched = original(name, entries, snapshot, at)
    if vouched is not None:
        reading = rule._reading(items)
        hits[f"{reading}: vouched"] += 1
        spans = [span for item in items if (span := episode_span(item)) is not None]
        if spans and _next_aired(snapshot, spans, at):
            hits[f"{reading}: guard would block"] += 1
            print(f"   [guard] {reading} {name[:80]} pub={at.date()} {vouched}")
    return items, vouched


rule._vouch = _vouch  # type: ignore[attr-defined]  # 動態載入的模組，mypy 看不到它的屬性


def main() -> int:
    for label, adversarial in (("corpus", False), ("adversarial", True)):
        hits.clear()
        rule.corpus(adversarial=adversarial)
        print(label, dict(hits))
    if "--online" in sys.argv:
        hits.clear()
        asyncio.run(rule.online())
        print("online", dict(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
