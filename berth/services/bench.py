"""解析基準測試（plan §4.6、brief §6.9）。

語料與 TMDB 快照都凍在 repo 裡（`tests/fixtures/parser/`、`tests/fixtures/tmdb/`），
所以這一支**不連線**：讀檔、跑解析器、數數字。`berth bench` 與單元測試跑的是同一支
（plan §10「benchmark 是單元測試的一部分」）。

**最重要的數字是 `auto_wrong`**：high 或 medium 自動入庫但入錯（brief §6.9「誤自動入庫率
趨近 0」）。`auto_correct` 是其次——先不要弄錯，再談多做一點。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from berth.domain import (
    Confidence,
    FileEntry,
    FileKind,
    Lang,
    MediaSnapshot,
    PlanAction,
    PlanItem,
    Source,
    Tags,
)
from berth.parser import plan

#: 語料的分類。id 的前綴就是它（`anime/frieren-…`），所以不另外存一個欄位。
CATEGORIES: tuple[str, ...] = ("anime", "tv", "movie")

#: high 與 medium 都自動入庫（brief §6.5）。
AUTO: frozenset[Confidence] = frozenset({Confidence.HIGH, Confidence.MEDIUM})


class Bucket(StrEnum):
    """一個檔案落在哪一格。**值就是 `Counts` 的欄位名**，歸桶與計數之間不必再多一張對照表。

    七格互斥且窮盡：加起來就是檔案數。plan §4.6 只點名了前五格，`MISSED` 與 `SKIPPED` 是補
    上去的——少了它們，報表的欄位加不到總數，那種報表會讓沒被數到的檔案看起來不存在。
    """

    #: 自動入庫而且對（brief §6.9）。
    AUTO_CORRECT = "auto_correct"
    #: 自動處置了但錯。**最嚴重的一格。**
    AUTO_WRONG = "auto_wrong"
    #: 交給人看。沒做錯事，只是沒幫上忙。
    REVIEW = "review"
    #: 該入庫的被丟成 unmatched / skip：人不一定看得到，但也沒有東西入錯。
    MISSED = "missed"
    UNMATCHED_CORRECT = "unmatched_correct"
    EXTRA_CORRECT = "extra_correct"
    #: 雙方都同意可以忽略（字型、海報、nfo）。
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class Expected:
    """語料裡對一個檔案的期望（plan §4.6）。

    語料另外寫了 `min_confidence`（期望的信心下限）與 `context.profile`，這一層**還沒有讀**：
    前者不參與比對（見 `_matches`），後者要到季集對應才用得上。票 06 接手時再讀進來——
    現在讀進來只會是兩個沒有人看的欄位。
    """

    path: str
    kind: FileKind
    action: PlanAction
    season: int | None
    episode: int | None
    episode_end: int | None
    #: `None` = 這一筆不檢查 tag（字幕與 extras 不帶 tag）。
    tags: Tags | None


@dataclass(frozen=True, slots=True)
class Fixture:
    id: str
    source_url: str
    torrent_name: str
    tmdb: str
    #: 上下文（brief §6.1 的第一個訊號）：Job 是從哪個 Media 送出的。
    #: 季集對應（票 06）吃它；現在用它確認語料與它指到的快照說的是同一部作品。
    context_media: str
    files: tuple[FileEntry, ...]
    expected: tuple[Expected, ...]

    @property
    def category(self) -> str:
        return self.id.split("/")[0]


@dataclass(frozen=True, slots=True)
class Counts:
    """一個分類（或整體）的計數。七個桶的定義見 `Bucket`。"""

    files: int = 0
    kind_correct: int = 0
    #: 語料寫了 tag 的檔案數，以及其中渲染對的（brief §6.8）。
    #: 與桶是**另一個軸**：季集還沒接上的時候，tag 對不對是唯一量得到的東西。
    tags_checked: int = 0
    tags_correct: int = 0
    #: 以下七格與 `Bucket` 同名同義。
    auto_correct: int = 0
    auto_wrong: int = 0
    review: int = 0
    missed: int = 0
    unmatched_correct: int = 0
    extra_correct: int = 0
    skipped: int = 0
    high_total: int = 0
    high_wrong: int = 0
    medium_total: int = 0
    medium_wrong: int = 0

    def plus(self, **deltas: int) -> Counts:
        return replace(self, **{key: getattr(self, key) + value for key, value in deltas.items()})


@dataclass(frozen=True, slots=True)
class Report:
    fixtures: int
    overall: Counts
    by_category: dict[str, Counts]

    @property
    def failures(self) -> tuple[str, ...]:
        """報表自己說得出來的問題：分類錯的，以及自動入錯的。"""
        problems: list[str] = []
        if self.overall.kind_correct != self.overall.files:
            wrong = self.overall.files - self.overall.kind_correct
            problems.append(f"{wrong} file(s) classified with the wrong kind")
        if self.overall.auto_wrong:
            problems.append(f"{self.overall.auto_wrong} file(s) auto-applied wrongly")
        if self.overall.tags_correct != self.overall.tags_checked:
            wrong = self.overall.tags_checked - self.overall.tags_correct
            problems.append(f"{wrong} file(s) rendered the wrong tags")
        return tuple(problems)


def load_corpus(corpus_root: Path) -> tuple[Fixture, ...]:
    """`tests/fixtures/parser/**/*.json`。`baseline.json` 不是語料。"""
    paths = sorted(p for p in corpus_root.rglob("*.json") if p.name != "baseline.json")
    return tuple(_fixture(json.loads(path.read_text(encoding="utf-8"))) for path in paths)


def load_snapshot(snapshot_root: Path, name: str) -> MediaSnapshot:
    """語料指到的 TMDB 快照（plan §4.6）。錄一次即凍結，測試不打外部。

    票 06 起 `map_episode` 吃它；現在讀它是為了讓「語料加了一筆卻忘了錄快照」在
    benchmark 就紅，而不是等到季集對應上線才發現。
    """
    return MediaSnapshot.model_validate_json(
        (snapshot_root / f"{name}.json").read_text(encoding="utf-8")
    )


def run(corpus_root: Path, snapshot_root: Path) -> Report:
    fixtures = load_corpus(corpus_root)
    overall = Counts()
    by_category = dict.fromkeys(CATEGORIES, Counts())
    for fixture in fixtures:
        _check_pairing(fixture, load_snapshot(snapshot_root, fixture.tmdb))
        counts = score(fixture)
        overall = _add(overall, counts)
        by_category[fixture.category] = _add(by_category[fixture.category], counts)
    return Report(fixtures=len(fixtures), overall=overall, by_category=by_category)


def _check_pairing(fixture: Fixture, snapshot: MediaSnapshot) -> None:
    """語料的上下文與它指到的那份快照，說的要是同一部作品。

    加了一筆語料卻指錯快照時，季集對應（票 06）會安靜地拿另一部作品的集數去算。
    在這裡就炸，而不是等到那時候才發現。
    """
    media_id = f"{snapshot.kind.value}:{snapshot.tmdb_id}"
    if media_id != fixture.context_media:
        raise ValueError(f"{fixture.id}: {fixture.tmdb} is {media_id}, not {fixture.context_media}")


def score(fixture: Fixture) -> Counts:
    """跑解析器，逐檔歸桶。"""
    produced = {item.rel_path: item for item in plan(fixture.torrent_name, fixture.files)}
    counts = Counts()
    for expected in fixture.expected:
        item = produced[expected.path]
        counts = counts.plus(files=1, kind_correct=int(item.kind is expected.kind))
        if expected.tags is not None:
            counts = counts.plus(tags_checked=1, tags_correct=int(item.tags == expected.tags))
        counts = counts.plus(**{bucket(expected, item).value: 1})
        counts = _add_confidence(counts, expected, item)
    return counts


def bucket(expected: Expected, item: PlanItem) -> Bucket:
    """一個檔案落在哪一格。**報表唯一的判斷**，所以它是公開的：計分規則要能被直接測。

    `auto_wrong` 收的不只是「入錯集數」，還有「把正片當成 extra 自動搬走」——
    自動做了而且做錯，嚴重度是一樣的（brief §6.9）。
    """
    if item.action is PlanAction.IMPORT and item.confidence in AUTO:
        return Bucket.AUTO_CORRECT if _matches(expected, item) else Bucket.AUTO_WRONG
    if item.action is PlanAction.EXTRA:
        return Bucket.EXTRA_CORRECT if expected.action is PlanAction.EXTRA else Bucket.AUTO_WRONG
    if item.action is PlanAction.SKIP:
        return Bucket.SKIPPED if expected.action is PlanAction.SKIP else Bucket.MISSED
    if item.action is PlanAction.UNMATCHED:
        if expected.action is PlanAction.UNMATCHED:
            return Bucket.UNMATCHED_CORRECT
        return Bucket.MISSED
    return Bucket.REVIEW


def _add_confidence(counts: Counts, expected: Expected, item: PlanItem) -> Counts:
    """high 與 medium 的誤判率分開報（brief §6.5 的取捨要靠這兩個數字回答）。"""
    if item.action is not PlanAction.IMPORT or item.confidence not in AUTO:
        return counts
    wrong = int(not _matches(expected, item))
    if item.confidence is Confidence.HIGH:
        return counts.plus(high_total=1, high_wrong=wrong)
    return counts.plus(medium_total=1, medium_wrong=wrong)


def _matches(expected: Expected, item: PlanItem) -> bool:
    """處置、季、集、集尾都一樣，而且語料有寫 tag 時 tag 也一樣。

    `min_confidence` **不參與**：信心低於期望不是「做錯了」，只是少自動化了一點，
    那件事由 `review` 與 high / medium 的誤判率各自回答。
    """
    if item.action is not expected.action:
        return False
    if (item.season, item.episode_start, item.episode_end) != (
        expected.season,
        expected.episode,
        expected.episode_end,
    ):
        return False
    return expected.tags is None or item.tags == expected.tags


def _add(left: Counts, right: Counts) -> Counts:
    return left.plus(**{f.name: getattr(right, f.name) for f in fields(Counts)})


def _fixture(raw: dict[str, Any]) -> Fixture:
    return Fixture(
        id=raw["id"],
        source_url=raw["source_url"],
        torrent_name=raw["torrent_name"],
        tmdb=raw["tmdb"],
        context_media=raw["context"]["media"],
        files=tuple(FileEntry(rel_path=row["path"], size=row["size"]) for row in raw["files"]),
        expected=tuple(_expected(row) for row in raw["expected"]),
    )


def _expected(raw: dict[str, Any]) -> Expected:
    return Expected(
        path=raw["path"],
        kind=FileKind(raw["kind"]),
        action=PlanAction(raw["action"]),
        season=raw.get("season"),
        episode=raw.get("episode"),
        episode_end=raw.get("episode_end"),
        tags=_tags(raw.get("tags")),
    )


def _tags(raw: dict[str, Any] | None) -> Tags | None:
    if raw is None:
        return None
    return Tags(
        source=Source(raw["source"]) if raw.get("source") else None,
        resolution=raw.get("resolution", ""),
        subs=tuple(Lang(value) for value in raw.get("subs", ())),
        hardsub=raw.get("hardsub", False),
        group=raw.get("group", ""),
        version=raw.get("version", ""),
        edition=raw.get("edition", ""),
    )


# --- baseline（plan §4.6 的 CI 規則） --------------------------------------------------


@dataclass(frozen=True, slots=True)
class Baseline:
    auto_correct: int
    auto_wrong: int


def load_baseline(path: Path) -> Baseline:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Baseline(auto_correct=raw["auto_correct"], auto_wrong=raw["auto_wrong"])


def dump_baseline(path: Path, report: Report, note: str) -> None:
    payload = {
        "note": note,
        "auto_correct": report.overall.auto_correct,
        "auto_wrong": report.overall.auto_wrong,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def regressions(report: Report, baseline: Baseline) -> tuple[str, ...]:
    """plan §4.6 的門檻：`auto_wrong` 不得高於 baseline，`auto_correct` 不得低於 baseline 減 1。

    留一格給 `auto_correct` 是因為語料會長大：新加一筆難的語料而讓一個檔案掉出自動入庫，
    不該擋住 PR。`auto_wrong` 沒有這一格——入錯一個就是入錯。
    """
    problems: list[str] = []
    if report.overall.auto_wrong > baseline.auto_wrong:
        problems.append(
            f"auto_wrong rose from {baseline.auto_wrong} to {report.overall.auto_wrong}"
        )
    if report.overall.auto_correct < baseline.auto_correct - 1:
        problems.append(
            f"auto_correct fell from {baseline.auto_correct} to {report.overall.auto_correct}"
        )
    return tuple(problems)


# --- 報表 ------------------------------------------------------------------------------

#: 報表的欄。桶那七欄的標題就是 `Bucket` 的值——報表與 plan §4.6 用同一組字。
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("files", "files"),
    ("kind_correct", "classify"),
    ("tags_correct", "tags"),
    *((field.value, field.value) for field in Bucket),
)


def render(report: Report) -> str:
    """給人看的一頁。欄位順序即 plan §4.6 的順序，`missed` 與 `skipped` 補在後面。"""
    header = ["category", *(label for _, label in _COLUMNS)]
    rows = [
        _row(name, report.by_category[name])
        for name in CATEGORIES
        if report.by_category[name].files
    ]
    rows.append(_row("overall", report.overall))
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]

    lines = [f"{report.fixtures} fixtures, {report.overall.files} files", ""]
    lines.append("  ".join(cell.ljust(width) for cell, width in zip(header, widths, strict=True)))
    lines.extend(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        for row in rows
    )
    lines.append("")
    lines.append(_rates(report.overall))
    return "\n".join(lines)


def _row(name: str, counts: Counts) -> list[str]:
    cells = [name]
    for field, _ in _COLUMNS:
        value = getattr(counts, field)
        # 分母不同的兩欄寫成分數，其餘是純計數。
        if field == "kind_correct":
            cells.append(f"{value}/{counts.files}")
        elif field == "tags_correct":
            cells.append(f"{value}/{counts.tags_checked}")
        else:
            cells.append(str(value))
    return cells


def _rates(counts: Counts) -> str:
    """high 與 medium 的誤判率分列（brief §6.5 的取捨靠這兩個數字回答）。"""
    return "  ".join(
        f"{label}: {wrong}/{total} wrong ({_pct(wrong, total)})"
        for label, wrong, total in (
            ("high", counts.high_wrong, counts.high_total),
            ("medium", counts.medium_wrong, counts.medium_total),
        )
    )


def _pct(part: int, total: int) -> str:
    return "n/a" if total == 0 else f"{part / total:.1%}"


def paths(repo_root: Path) -> tuple[Path, Path, Path]:
    """語料、快照與 baseline 的位置（plan §1.2）。CLI 與測試共用同一份答案。"""
    fixtures = repo_root / "tests" / "fixtures"
    return fixtures / "parser", fixtures / "tmdb", fixtures / "parser" / "baseline.json"
