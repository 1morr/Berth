#!/usr/bin/env python3
"""M1 票 14c：Route 的 profile（`standard` / `anime`）對解析結果到底有沒有作用。

benchmark 語料以四種組合重算——原樣、每筆翻轉、全部 `standard`、全部 `anime`——逐檔比
`bench.bucket` 的差異，並側錄 `mapping._from_number` 每一次走了哪一個分支。profile 只在
那一段被讀（「只有集號、TMDB 上不只一季」時把集號當絕對編號換算），所以桶一格都沒動時，
要先看的是那一段有沒有被走到，而不是 profile 有沒有用。

與同目錄其他腳本不同，這一支 **import `berth`**：它量的就是 Berth 自己的解析器與語料，
搬到別台機器上跑沒有意義。不連線、不寫檔，語料與快照都是 repo 裡凍結的那一份：

    uv run python scripts/experiments/profile_effect.py

結論在 `docs/research/profile-effect.md`。
"""

from __future__ import annotations

import io
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal
from unittest import mock

from berth.domain import Candidate, MappingStrategy, MediaSnapshot, ParseContext, Profile
from berth.parser import mapping, plan
from berth.services import bench

REPO_ROOT = Path(__file__).resolve().parents[2]

_FLIP = {Profile.STANDARD: Profile.ANIME, Profile.ANIME: Profile.STANDARD}

#: `_from_number` 的兩個分支。
Branch = Literal["single_season", "absolute"]

#: 四種組合：名稱 → 這一筆語料在這一輪用哪一個 profile。
VARIANTS: tuple[tuple[str, Callable[[bench.Fixture], Profile]], ...] = (
    ("original", lambda fixture: fixture.profile),
    ("flipped", lambda fixture: _FLIP[fixture.profile]),
    ("all-standard", lambda _fixture: Profile.STANDARD),
    ("all-anime", lambda _fixture: Profile.ANIME),
)


@dataclass(frozen=True, slots=True)
class Call:
    """`_from_number` 被呼叫一次。`branch` 由回傳的策略判定：兩個分支產的策略不重疊。"""

    fixture: str
    episode: int
    branch: Branch
    strategies: tuple[str, ...]
    #: 排第一的候選（planner 採用的那一個），`S22E1089` 這種寫法；沒有候選時是空字串。
    first: str


@dataclass(frozen=True, slots=True)
class Result:
    report: bench.Report
    #: `(語料 id, 檔案路徑)` → 桶。
    buckets: dict[tuple[str, str], bench.Bucket]
    calls: tuple[Call, ...]


@contextmanager
def spying(calls: list[Call], fixture: str) -> Iterator[None]:
    """把 `mapping._from_number` 換成照常回傳、順手記一筆的版本。"""
    original = mapping._from_number

    def spy(
        media: MediaSnapshot,
        context: ParseContext,
        span: mapping._Span,
        check: mapping._Check,
    ) -> tuple[Candidate, ...]:
        found = original(media, context, span, check)
        strategies = tuple(candidate.strategy.value for candidate in found)
        single = MappingStrategy.SINGLE_SEASON.value in strategies
        calls.append(
            Call(
                fixture=fixture,
                episode=span.start,
                branch="single_season" if single else "absolute",
                strategies=strategies,
                first=_label(found[0]) if found else "",
            )
        )
        return found

    with mock.patch.object(mapping, "_from_number", spy):
        yield


def _label(candidate: Candidate) -> str:
    return f"S{candidate.season:02d}E{candidate.episode_start:02d}"


def measure(
    fixtures: tuple[bench.Fixture, ...],
    snapshots: dict[str, MediaSnapshot],
    choose: Callable[[bench.Fixture], Profile],
) -> Result:
    overall = bench.Counts()
    by_category = dict.fromkeys(bench.CATEGORIES, bench.Counts())
    buckets: dict[tuple[str, str], bench.Bucket] = {}
    calls: list[Call] = []
    for fixture in fixtures:
        variant = replace(fixture, profile=choose(fixture))
        snapshot = snapshots[fixture.tmdb]
        # 指錯快照的語料會安靜地拿別部作品的集數去算；`bench.run` 擋這個，這裡也要。
        bench._check_pairing(fixture, snapshot)
        counts = bench.score(variant, snapshot)
        overall = bench._add(overall, counts)
        by_category[fixture.category] = bench._add(by_category[fixture.category], counts)

        # `bench.score` 只回計數；逐檔的桶要自己再跑一次，側錄也只包這一次，才不會記兩遍。
        with spying(calls, fixture.id):
            items = plan(variant.torrent_name, variant.files, variant.context(snapshot))
        produced = {item.rel_path: item for item in items}
        for expected in variant.expected:
            buckets[(fixture.id, expected.path)] = bench.bucket(expected, produced[expected.path])
    report = bench.Report(fixtures=len(fixtures), overall=overall, by_category=by_category)
    return Result(report=report, buckets=buckets, calls=tuple(calls))


def render(fixtures: tuple[bench.Fixture, ...], results: dict[str, Result]) -> str:
    lines = [f"# profile effect: {len(fixtures)} fixtures", ""]
    for name, result in results.items():
        lines += [f"## {name}", "", "```", bench.render(result.report), "```", ""]

    baseline = results["original"]
    lines += ["## per-file bucket changes against original", ""]
    for name, result in results.items():
        if name == "original":
            continue
        changed = [
            (key, baseline.buckets[key], bucket)
            for key, bucket in result.buckets.items()
            if bucket is not baseline.buckets[key]
        ]
        lines.append(f"### {name}: {len(changed)} file(s) changed")
        lines.append("")
        for (owner, path), before, after in changed:
            lines.append(f"- `{owner}` `{path}`: {before.value} -> {after.value}")
        lines.append("")

    lines += ["## `_from_number` branches", ""]
    same = all(result.calls == baseline.calls for result in results.values())
    lines.append(f"identical across the four variants: {'yes' if same else 'NO'}")
    lines.append("")
    lines.append(
        "| fixture | profile | calls | single_season | absolute | strategies | first candidates |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for fixture in fixtures:
        mine = [call for call in baseline.calls if call.fixture == fixture.id]
        branches = Counter(call.branch for call in mine)
        strategies = sorted({strategy for call in mine for strategy in call.strategies})
        absolute = [call for call in mine if call.branch == "absolute"]
        converted = _span_of(absolute)
        lines.append(
            f"| `{fixture.id}` | {fixture.profile.value} | {len(mine)} "
            f"| {branches['single_season']} | {branches['absolute']} "
            f"| {', '.join(strategies) if absolute else ''} | {converted} |"
        )
    lines.append("")

    lines += ["## buckets of the fixtures that reach the absolute branch", ""]
    lines.append("| fixture | " + " | ".join(results) + " |")
    lines.append("| --- |" + " --- |" * len(results))
    reached = {call.fixture for call in baseline.calls if call.branch == "absolute"}
    for fixture in fixtures:
        if fixture.id not in reached:
            continue
        cells = [_tally(fixture.id, result.buckets) for result in results.values()]
        lines.append(f"| `{fixture.id}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _span_of(calls: list[Call]) -> str:
    """`#1089→S22E1089 … #1104→S22E1104` 這種摘要。只有一筆時就寫那一筆。"""
    if not calls:
        return ""
    ordered = sorted(calls, key=lambda call: call.episode)
    head = f"#{ordered[0].episode}→{ordered[0].first or '∅'}"
    if len(ordered) == 1:
        return head
    return f"{head} … #{ordered[-1].episode}→{ordered[-1].first or '∅'}"


def _tally(fixture: str, buckets: dict[tuple[str, str], bench.Bucket]) -> str:
    counted = Counter(bucket.value for (owner, _), bucket in buckets.items() if owner == fixture)
    return ", ".join(f"{name} {count}" for name, count in sorted(counted.items()))


def main() -> int:
    # 語料裡有中文與 `Pokémon`，Windows 主控台預設是 cp950（`record_tmdb_snapshots.py` 同一個坑）。
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    corpus, snapshot_root, _baseline = bench.paths(REPO_ROOT)
    fixtures = bench.load_corpus(corpus)
    snapshots = {
        fixture.tmdb: bench.load_snapshot(snapshot_root, fixture.tmdb) for fixture in fixtures
    }
    results = {name: measure(fixtures, snapshots, choose) for name, choose in VARIANTS}
    print(render(fixtures, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
