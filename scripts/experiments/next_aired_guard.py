"""候選守衛「發佈時對到那一集的下一集已經播了就不擔保」會多擋幾筆已擔保的第一批（M5.5 票 05）。

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
from berth.parser import RELEASE_TOLERANCE, episode_span

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


def _next_aired(items: tuple[PlanItem, ...], snapshot: MediaSnapshot, at: datetime) -> bool:
    """整份最後一集的下一集，在發佈日加 `RELEASE_TOLERANCE` 之前已經播了。"""
    spans = [span for item in items if (span := episode_span(item)) is not None]
    if not spans:
        return False
    season, _, end = max(spans)
    found = snapshot.episode(season, end + 1)
    return (
        found is not None
        and found.air_date is not None
        and (found.air_date <= at.date() + RELEASE_TOLERANCE)
    )


def _vouch(
    name: str, entries: tuple[FileEntry, ...], snapshot: MediaSnapshot, at: datetime
) -> tuple[tuple[PlanItem, ...], tuple[tuple[int, int, int], ...] | None]:
    items, vouched = original(name, entries, snapshot, at)
    if vouched is not None:
        reading = rule._reading(items)
        hits[f"{reading}: vouched"] += 1
        if _next_aired(items, snapshot, at):
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
