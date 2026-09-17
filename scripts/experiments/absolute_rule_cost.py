#!/usr/bin/env python3
"""M1 票 14d 第 1 步：規則 1（集號 ≤ 第一季集數 → 送審核）擋下的，是對的多還是錯的多。

規則 1 的理由是「這個數字同時讀得成第一季第 N 集，與後面某季從 01 重數的第 N 集」
（`docs/research/profile-effect.md` §6.1）。它的代價是多季作品第一季、檔名沒有季號的發佈
也一起送審核，而那個量沒人量過。這一支用 M1 票 01 那批以**發佈時間**判定過正解的真實發佈
（`anime_episode_source.py`）回答：

- 走到絕對編號換算、集號 ≤ 第一季集數的檔案裡，正解是第一季的（A，規則 1 擋下的對）
  與正解是後面某季的（B，規則 1 擋下的錯）各有幾個；
- 集號 > 第一季集數那一側，現行換算對與錯各有幾個；
- 收窄規則 R「集號 ≤ 第一季集數**而且**標題有認不出的多餘字」在 A 裡放行幾個、在 B 裡漏掉幾個。

與 `profile_effect.py` 一樣 **import `berth`**（量的就是 Berth 自己的解析器），另外 import 同目錄的
`anime_episode_source.py` 取正解。要 `TMDB_API_KEY`（那一支的快取鍵不含憑證，但它要求環境變數在）；
快取在 `.local/experiments/cache/anime_episode_source/`，被清掉的話重抓約十分鐘：

    uv run --env-file .env python scripts/experiments/absolute_rule_cost.py

只印 stdout，不寫檔。結論在 `docs/research/profile-effect.md` §6.1。
"""

from __future__ import annotations

import io
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from unittest import mock

import anime_episode_source as source

from berth.domain import (
    Candidate,
    FileEntry,
    MappingStrategy,
    MediaSnapshot,
    ParseContext,
    ReleaseInfo,
)
from berth.parser import mapping, plan, planner
from berth.parser.mapping import map_episode
from berth.parser.structure import StructureHints
from berth.parser.title import normalize_title
from berth.services import bench

REPO_ROOT = Path(__file__).resolve().parents[2]

#: 票 01 的 10 部裡 TMDB 上有 ≥ 2 個正規季的 5 部 → repo 裡的快照。另外 5 部只有一季，
#: 走 `single_season`，規則 1 碰不到（`main` 會照票 01 的資料再數一次季數，對不上就停）。
SAMPLE: dict[str, str] = {
    "spy-family": "tv-120089",
    "mushoku-tensei": "tv-94664",
    "demon-slayer": "tv-85937",
    "attack-on-titan": "tv-1429",
    "one-piece": "tv-37854",
}

#: Mikan 只給標題，沒有檔案清單。每筆發佈當成「以標題為檔名的單檔 torrent」，大小隨便給一個
#: 正片的量級——單檔 torrent 沒有同資料夾的影片可以比，`sample` 的判定用不到它。
FILE_SIZE = 1 << 30

_ABSOLUTE = frozenset({MappingStrategy.ABSOLUTE_GROUP, MappingStrategy.ABSOLUTE_CUMULATIVE})


class Cell(StrEnum):
    """一個檔案落在哪一格。前五格是「沒走到換算、或判不了對錯」，不進規則 1 的分母。"""

    NOT_VIDEO = "not_video"
    NO_CANDIDATE = "no_candidate"
    OTHER_BRANCH = "other_branch"
    #: 票 01 的標題解析與 Berth 讀到的集號不同，這一集的正解對不到 Berth 的哪一次換算。
    MISREAD = "misread"
    #: 票 01 對不出這一集在 TMDB 的座標（`coord_for_ordinal` 的 `no_source`），沒有正解可比。
    NO_TRUTH = "no_truth"
    #: 集號 ≤ 第一季集數：正解在第一季（A）與正解在後面某季（B）。
    A = "A"
    B = "B"
    #: 集號 > 第一季集數：現行換算（排第一的候選）對與錯。
    OVER_RIGHT = "over_right"
    OVER_WRONG = "over_wrong"


_JUDGED = (Cell.A, Cell.B, Cell.OVER_RIGHT, Cell.OVER_WRONG)


@dataclass(frozen=True, slots=True)
class Reading:
    """Berth 讀一個標題時 `map_episode` 看到的東西，以及它回的候選。"""

    info: ReleaseInfo
    structure: StructureHints
    context: ParseContext
    release_name: str
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True, slots=True)
class Row:
    """一個檔案（合集逐集展開）：票 01 的一次換算，加上 Berth 怎麼讀它。"""

    series: str
    title: str
    number: int
    cell: Cell
    #: 正解是怎麼從 TVDB 對到 TMDB 的（`air_date` / `position`），見票 01 研究 §4.4。
    join: str
    truth: tuple[int, int] | None
    #: Berth 排第一的候選（`S02E01`）；沒走到換算時是空字串。
    got: str
    #: 標題有認不出的多餘字（兩種「已知名字」的範圍，見 `has_extra_words`）。
    extra_all: bool
    extra_main: bool


def read(title: str, snapshot: MediaSnapshot) -> Reading | None:
    """一筆發佈丟進 `plan`，側錄 `map_episode`。分類成非影片時沒有呼叫，回 `None`。"""
    seen: list[Reading] = []
    original = map_episode

    def spy(
        info: ReleaseInfo,
        structure: StructureHints,
        context: ParseContext,
        *,
        release_name: str = "",
    ) -> tuple[Candidate, ...]:
        found = original(info, structure, context, release_name=release_name)
        seen.append(Reading(info, structure, context, release_name, found))
        return found

    with mock.patch.object(planner, "map_episode", spy):
        plan(
            title,
            (FileEntry(rel_path=f"{title}.mkv", size=FILE_SIZE),),
            ParseContext(media=snapshot),
        )
    return seen[0] if seen else None


def convert(reading: Reading, number: int) -> tuple[Candidate, ...]:
    """合集的第 `number` 集單獨換算一次：Berth 對一整包只換算區間的頭，逐集要自己再問。"""
    single = reading.info.model_copy(update={"episode": number, "episode_end": None})
    return map_episode(
        single, reading.structure, reading.context, release_name=reading.release_name
    )


def has_extra_words(info: ReleaseInfo, names: tuple[str, ...]) -> bool:
    """「標題有認不出的多餘字」：guessit 認出的標題候選裡，有任何一個正規化之後不是 `names` 之一。

    **一個候選都沒有也算有**：認不出標題就說不出「沒有多餘字」，而 R 放行的前提是說得出來。
    中文字幕組的方括號堆（`【极影字幕社】【进击的巨人 2】【Shingeki no Kyojin 2】【01】`）
    guessit 常常一個標題都讀不出來，這些一律留在規則 1 裡。

    正規化用解析器自己的 `normalize_title`（NFKC、小寫、只留字母數字與 CJK），所以
    `SPY×FAMILY` 與 `SPY x FAMILY` 差的只是那個 `x`。
    """
    known = {normalize_title(name) for name in names}
    return not info.title_candidates or any(
        normalize_title(candidate) not in known for candidate in info.title_candidates
    )


def all_names(media: MediaSnapshot) -> tuple[str, ...]:
    """快照裡所有叫得出來的名字：三個主標題，加上 `titles`（別名與各語言翻譯）。"""
    return (media.title, media.title_en, media.title_original, *media.titles)


def main_names(media: MediaSnapshot) -> tuple[str, ...]:
    """只有三個主標題。`titles` 裡混著單季的名字（`Mushoku Tensei S3`、
    `Kimetsu no Yaiba: Katanakaji no Sato-hen`），標題等於它們不代表「沒有多餘字」。
    """
    return (media.title, media.title_en, media.title_original)


def first_season_length(media: MediaSnapshot) -> tuple[int, int]:
    """（第一個正規季的季號, 集數）。直接問解析器，規則 1 看的就是這兩個數字。"""
    first = mapping._regular(media)[0]
    return first.season_number, mapping._length(first)


def regular_seasons(counts: dict[int, int]) -> int:
    return sum(1 for season in counts if season > 0)


def classify(
    series: str,
    trial: source.Trial,
    result: source.SeriesResult,
    reading: Reading | None,
    snapshot: MediaSnapshot,
) -> Row:
    truth, join = source.coord_for_ordinal(
        result.schemes["tmdb"], result.schemes["tvdb_aired"], trial.truth_ordinal
    )
    extra_all = reading is not None and has_extra_words(reading.info, all_names(snapshot))
    extra_main = reading is not None and has_extra_words(reading.info, main_names(snapshot))

    def row(cell: Cell, got: str = "") -> Row:
        return Row(series, trial.title, trial.number, cell, join, truth, got, extra_all, extra_main)

    if reading is None:
        return row(Cell.NOT_VIDEO)
    if not reading.candidates:
        return row(Cell.NO_CANDIDATE)
    if reading.candidates[0].strategy not in _ABSOLUTE:
        return row(Cell.OTHER_BRANCH)
    start = reading.info.episode
    end = reading.info.episode_end or start
    if start is None or end is None or not start <= trial.number <= end:
        return row(Cell.MISREAD)
    if truth is None:
        return row(Cell.NO_TRUTH)

    converted = convert(reading, trial.number)
    got = _label(converted[0]) if converted else ""
    first_season, length = first_season_length(snapshot)
    if trial.number <= length:
        return row(Cell.A if truth[0] == first_season else Cell.B, got)
    right = converted and truth == (converted[0].season, converted[0].episode_start)
    return row(Cell.OVER_RIGHT if right else Cell.OVER_WRONG, got)


def _label(candidate: Candidate) -> str:
    return f"S{candidate.season or 0:02d}E{candidate.episode_start or 0:02d}"


def _truth(row: Row) -> str:
    return f"S{row.truth[0]:02d}E{row.truth[1]:02d}" if row.truth else "?"


def check_sample(token: str) -> list[str]:
    """票 01 的 10 部，照它抓的 TMDB 資料數正規季。挑出來的 5 部要正好是 ≥ 2 季的那些。"""
    lines = ["## sample: regular seasons in ticket 01's TMDB data", ""]
    lines += ["| series | tmdb | regular seasons | episodes per season | measured |"]
    lines += ["| --- | --- | --- | --- | --- |"]
    multi: set[str] = set()
    for series in source.load_sample():
        counts = {k: len(v) for k, v in source.tmdb_scheme(token, series.tmdb_id).seasons().items()}
        if regular_seasons(counts) >= 2:
            multi.add(series.key)
        lines.append(
            f"| {series.key} | {series.tmdb_id} | {regular_seasons(counts)} "
            f"| {[counts[k] for k in sorted(counts)]} | {'yes' if series.key in SAMPLE else ''} |"
        )
    if multi != set(SAMPLE):
        raise SystemExit(
            f"the sample does not match ticket 01's data: {sorted(multi)} have >= 2 seasons"
        )
    return [*lines, ""]


def check_snapshot(result: source.SeriesResult, snapshot: MediaSnapshot) -> list[str]:
    """票 01 抓的 TMDB（2026-09-09）與 repo 快照，各季的集號要一樣。不一樣就記下來。"""
    ours = {
        season.season_number: sorted(row.episode_number for row in season.episodes)
        for season in snapshot.seasons
        if season.season_number > 0
    }
    theirs = {
        season: sorted(episode.number for episode in episodes)
        for season, episodes in result.schemes["tmdb"].seasons().items()
    }
    if ours == theirs:
        return []
    return [
        f"S{season:02d}: ticket 01 has {len(theirs.get(season, []))} episodes, "
        f"snapshot has {len(ours.get(season, []))}"
        for season in sorted(set(ours) | set(theirs))
        if ours.get(season) != theirs.get(season)
    ]


def measure(token: str) -> tuple[list[Row], list[str]]:
    rows: list[Row] = []
    lines = ["## ticket 01's TMDB data against the repo snapshots", ""]
    samples = {series.key: series for series in source.load_sample()}
    _corpus, snapshot_root, _baseline = bench.paths(REPO_ROOT)
    for key, name in SAMPLE.items():
        result = source.collect(samples[key], token, source.DEFAULT_GAP_DAYS)
        snapshot = bench.load_snapshot(snapshot_root, name)
        drift = check_snapshot(result, snapshot)
        lines.append(
            f"- {key} (`{name}`): {'same episodes per season' if not drift else 'DIFFERS'}"
        )
        lines += [f"  - {line}" for line in drift]
        readings = {title: read(title, snapshot) for title in {t.title for t in result.trials}}
        rows += [
            classify(key, trial, result, readings[trial.title], snapshot) for trial in result.trials
        ]
    return rows, [*lines, ""]


def render(rows: list[Row]) -> list[str]:
    lines = ["## files per cell (batches expanded)", ""]
    lines.append("| series | " + " | ".join(Cell) + " |")
    lines.append("| --- |" + " --- |" * len(Cell))
    for key in [*SAMPLE, "total"]:
        mine = [row for row in rows if key in ("total", row.series)]
        counted = Counter(row.cell for row in mine)
        lines.append(f"| {key} | " + " | ".join(str(counted[cell]) for cell in Cell) + " |")
    lines.append("")

    joins = Counter((row.cell, row.join) for row in rows if row.cell in _JUDGED)
    lines += ["truth joined by position instead of air date (ticket 01 §4.4, less certain):", ""]
    for cell in _JUDGED:
        total = sum(count for (owner, _), count in joins.items() if owner == cell)
        lines.append(f"- {cell}: {joins[(cell, 'position')]} of {total}")
    lines.append("")

    lines += ["## narrowed rule R: rule 1 only when the title has unrecognised extra words", ""]
    lines += ["| known names | A released | A kept in review | B missed | B caught |"]
    lines += ["| --- | --- | --- | --- | --- |"]
    variants: tuple[tuple[str, Callable[[Row], bool]], ...] = (
        ("all names (`titles` too)", lambda row: row.extra_all),
        ("three main titles only", lambda row: row.extra_main),
    )
    for label, extra in variants:
        a_rows = [row for row in rows if row.cell is Cell.A]
        b_rows = [row for row in rows if row.cell is Cell.B]
        lines.append(
            f"| {label} | {sum(not extra(r) for r in a_rows)} | {sum(extra(r) for r in a_rows)} "
            f"| {sum(not extra(r) for r in b_rows)} | {sum(extra(r) for r in b_rows)} |"
        )
    lines.append("")

    for label, extra in variants:
        missed = Counter(
            (row.series, row.title) for row in rows if row.cell is Cell.B and not extra(row)
        )
        lines += [f"### B missed by R ({label}): {sum(missed.values())} file(s)", ""]
        lines += [f"- {count} × `{title}` ({series})" for (series, title), count in missed.items()]
        lines.append("")

    released = Counter(
        (row.series, row.title) for row in rows if row.cell is Cell.A and not row.extra_main
    )
    lines += [f"### A released by R (three main titles): {len(released)} distinct title(s)", ""]
    lines += [
        f"- {count} × `{title}` ({series})" for (series, title), count in released.most_common(15)
    ]
    lines.append("")

    wrong = [row for row in rows if row.cell is Cell.OVER_WRONG]
    lines += [f"### conversions over the first season that are wrong: {len(wrong)} file(s)", ""]
    grouped = Counter((row.series, row.title) for row in wrong)
    for (series, title), count in grouped.most_common():
        sample = next(row for row in wrong if row.title == title)
        lines.append(
            f"- {count} × `{title}` ({series}): #{sample.number} → {sample.got or '∅'}, "
            f"truth {_truth(sample)} ({sample.join})"
        )
    return lines


#: 「只比三個主標題」在樣本上一筆 B 都沒漏，但無職轉生那 5 筆 `Mushoku Tensei S2 [02]` 是**靠 TMDB
#: 英文標題比羅馬字長**才被擋下的：Berth 在季號等於方括號集號時把季號丟掉（`release._numbers`
#: 的 `The_Final_Season[28]` 那一條），標題只剩 `Mushoku Tensei`。同一個字幕組的同一種寫法換成
#: TMDB 英文標題就是 `SPY x FAMILY` 的作品，正解 S02E02——這一筆是照樣造的，不是真實發佈。
PROBE = ("spy-family", "[桜都字幕组] 间谍过家家 S2 / Spy x Family S2 [02][1080p][简繁内封]")


def probe(snapshot_root: Path) -> list[str]:
    key, title = PROBE
    snapshot = bench.load_snapshot(snapshot_root, SAMPLE[key])
    reading = read(title, snapshot)
    assert reading is not None and reading.candidates
    return [
        "## probe: a later-season restart that the three-main-titles R would release",
        "",
        f"- `{title}` ({key}, truth S02E02)",
        f"  - season read: {reading.info.season}, "
        f"title candidates: {reading.info.title_candidates}",
        f"  - first candidate: {_label(reading.candidates[0])} "
        f"({reading.candidates[0].strategy.value})",
        f"  - extra words against the three main titles: "
        f"{has_extra_words(reading.info, main_names(snapshot))}",
        "",
    ]


def main() -> int:
    # 標題裡有中文與全形符號，Windows 主控台預設是 cp950（`profile_effect.py` 同一個坑）。
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    token = source.tmdb_token()
    lines = check_sample(token)
    rows, drift = measure(token)
    _corpus, snapshot_root, _baseline = bench.paths(REPO_ROOT)
    print("\n".join([*lines, *drift, *render(rows), "", *probe(snapshot_root)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
