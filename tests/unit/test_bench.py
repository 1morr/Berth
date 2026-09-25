"""解析基準測試本身（plan §4.6、§10、brief §6.9）。

**這一支就是 CI 的門檻**：`berth bench` 與這裡跑的是同一個 `services/bench.py`，
所以 CI 不需要多一個 job——`uv run pytest` 紅了就是 benchmark 掉了（plan §10）。
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path

import pytest

from berth.domain import Confidence, FileKind, PlanAction, PlanItem, Tags
from berth.services.bench import (
    CATEGORIES,
    GUARDED,
    Baseline,
    Bucket,
    Counts,
    Expected,
    Report,
    bucket,
    load_baseline,
    load_corpus,
    load_snapshot,
    paths,
    regressions,
    render,
    run,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT, SNAPSHOT_ROOT, BASELINE_PATH = paths(REPO_ROOT)

#: 會被寫進媒體庫的三種處置。它們一定有目標路徑，其餘一定沒有（plan §5）。
_WRITTEN = frozenset({PlanAction.IMPORT, PlanAction.EXTRA, PlanAction.SUBTITLE})

TARGET = "Show (2020) [tmdbid-1]/Season 01/Show (2020) - S01E02.mkv"

#: 語料的組成（plan §4.6、brief §20.4 的樣本清單）。v0 是 20 筆（動漫 8 / 劇集 8 / 電影 4），
#: 票 06 補了三筆動漫：篇章名、cour 偏移與單檔多集（brief §6.6）；
#: 票 14c 補了「只有集號、TMDB 上多季」的動漫三筆、劇集兩筆（brief §20.4）；
#: 票 14d 補了「集號 ≤ 第一季集數」兩個方向的動漫各一筆（每 cour 重數、第一季的無季號發佈）；
#: 票 14f 補了「季號剛好等於方括號集號」的動漫兩筆（TMDB 一季、多季各一）；
#: M2 票 01 補了「`Season 3 - 50` 的破折號集號」的動漫兩筆（guessit 各錯一種寫法）；
#: M3 票 16 補了「每輪從 01 重數、發佈時間說得出是哪一輪」的動漫四筆。
CORPUS_SHAPE = {"anime": 24, "tv": 10, "movie": 4}


@pytest.fixture(scope="module")
def report() -> Report:
    return run(CORPUS_ROOT, SNAPSHOT_ROOT)


class TestCorpus:
    def test_it_has_the_v0_shape(self) -> None:
        fixtures = load_corpus(CORPUS_ROOT)
        counted = {name: sum(f.category == name for f in fixtures) for name in CATEGORIES}

        assert counted == CORPUS_SHAPE
        assert len(fixtures) == sum(CORPUS_SHAPE.values())

    def test_every_fixture_cites_its_source(self) -> None:
        """語料是真實 torrent 的檔案清單（brief §6.9）；沒有出處的一筆無法回頭查證。"""
        for fixture in load_corpus(CORPUS_ROOT):
            assert fixture.source_url.startswith("https://"), fixture.id

    def test_every_fixture_expects_something_for_every_file(self) -> None:
        for fixture in load_corpus(CORPUS_ROOT):
            assert [e.path for e in fixture.expected] == [f.rel_path for f in fixture.files]

    def test_every_file_that_gets_written_says_where(self) -> None:
        """import / extra / subtitle 一定有目標路徑，其餘一定沒有（plan §5、brief §7.4）。

        少寫一條的話那一筆就變成「不比對路徑」，而路徑正是票 07 加進來要守的東西。
        """
        for fixture in load_corpus(CORPUS_ROOT):
            for expected in fixture.expected:
                assert bool(expected.target) is (expected.action in _WRITTEN), (
                    fixture.id,
                    expected.path,
                )

    def test_no_two_files_in_one_fixture_share_a_target(self) -> None:
        """同一包裡兩個檔案指到同一條路徑是衝突（brief §6.4 第 5 點），不是正確答案。"""
        for fixture in load_corpus(CORPUS_ROOT):
            targets = [e.target for e in fixture.expected if e.target]

            assert len(targets) == len(set(targets)), fixture.id

    def test_every_fixture_has_a_frozen_tmdb_snapshot(self) -> None:
        """`tests/fixtures/tmdb/` 錄一次即凍結，測試不打外部（plan §4.6、§10）。

        指到哪一份由 `run()` 自己檢查（`_check_pairing`）；這裡確認檔案真的在。
        """
        for fixture in load_corpus(CORPUS_ROOT):
            assert load_snapshot(SNAPSHOT_ROOT, fixture.tmdb).tmdb_id > 0

    def test_the_publish_time_reaches_the_parser(self, tmp_path: Path) -> None:
        """M3 票 16：只有集號時解析器拿發佈時間推測是哪一輪播出，語料要帶得進去。"""
        _write_fixture(tmp_path, published_at="2024-12-30T02:15:00+08:00")

        (fixture,) = load_corpus(tmp_path)
        context = fixture.context(load_snapshot(SNAPSHOT_ROOT, "tv-30984"))

        assert context.published_at == datetime(2024, 12, 29, 18, 15, tzinfo=UTC)

    def test_a_fixture_without_a_publish_time_has_none(self, tmp_path: Path) -> None:
        _write_fixture(tmp_path)

        (fixture,) = load_corpus(tmp_path)

        assert fixture.published_at is None

    def test_a_publish_time_without_a_time_zone_is_refused(self, tmp_path: Path) -> None:
        """Mikan 寫 UTC+8、Nyaa 寫 UTC：沒寫時區的話推測會安靜地差出一天。"""
        _write_fixture(tmp_path, published_at="2024-12-30T02:15:00")

        with pytest.raises(ValueError, match="no time zone"):
            load_corpus(tmp_path)


class TestReport:
    def test_the_buckets_add_up_to_the_file_count(self, report: Report) -> None:
        """八個桶互斥且窮盡——加不起來的報表會讓沒被數到的檔案看起來不存在。"""
        counts = report.overall

        assert sum(getattr(counts, field.value) for field in Bucket) == counts.files

    def test_every_guarded_number_names_a_counter_and_a_baseline_field(self) -> None:
        """`GUARDED` 是字串加 `getattr`，型別檢查看不到它——錯字只會在 CI 跑 bench 時
        以「找不到欄位」炸掉，所以在這裡先炸。
        """
        assert set(GUARDED) <= {f.name for f in fields(Counts)}
        assert set(GUARDED) <= {f.name for f in fields(Baseline)}

    def test_every_bucket_names_a_counter(self) -> None:
        """`Bucket` 的值直接當 `Counts` 的欄位名用，錯字只會在執行期炸——所以在這裡先炸。"""
        assert {field.value for field in Bucket} <= {f.name for f in fields(Counts)}

    def test_it_reports_each_category(self, report: Report) -> None:
        assert sum(report.by_category[name].files for name in CATEGORIES) == report.overall.files
        for name in CATEGORIES:
            assert report.by_category[name].files > 0

    def test_it_renders_the_columns_plan_4_6_asks_for(self, report: Report) -> None:
        rendered = render(report)

        for column in Bucket:
            assert column.value in rendered
        for name in CATEGORIES:
            assert name in rendered
        assert "high:" in rendered and "medium:" in rendered


class TestThresholds:
    """語料是紅燈的來源（`mattpocock-skills:tdd`）：這三條就是它守住的東西。"""

    def test_classification_is_right_for_every_file(self, report: Report) -> None:
        assert report.overall.kind_correct == report.overall.files

    def test_every_tag_the_corpus_writes_down_renders_the_same(self, report: Report) -> None:
        assert report.overall.tags_correct == report.overall.tags_checked

    def test_nothing_is_auto_applied_wrongly(self, report: Report) -> None:
        """brief §6.9 的第一目標：誤自動入庫率趨近 0。"""
        assert report.overall.auto_wrong == 0

    def test_it_holds_the_baseline(self, report: Report) -> None:
        assert regressions(report, load_baseline(BASELINE_PATH)) == ()

    def test_the_report_agrees_it_is_clean(self, report: Report) -> None:
        assert report.failures == ()


class TestRegressions:
    """plan §4.6 的兩條 CI 規則。"""

    def test_more_wrong_imports_is_a_regression(self) -> None:
        report = _report(Counts(files=1, auto_wrong=1))

        assert regressions(report, _baseline(auto_wrong=0))

    def test_one_lost_auto_import_is_forgiven(self) -> None:
        """語料會長大：新加一筆難的不該擋住 PR。"""
        report = _report(Counts(files=10, auto_correct=9))

        assert regressions(report, _baseline(auto_correct=10)) == ()

    def test_two_lost_auto_imports_are_not(self) -> None:
        report = _report(Counts(files=10, auto_correct=8))

        assert regressions(report, _baseline(auto_correct=10))

    def test_subtitles_that_stop_matching_are_a_regression_too(self) -> None:
        """字幕與 extras 也是自動搬進媒體庫的檔案（票 07）。它們掉光了不會讓
        `auto_wrong` 動一格——沒有這一條，那種退步在 CI 上是看不見的。
        """
        report = _report(Counts(files=10, subtitle_correct=5))

        assert regressions(report, _baseline(subtitle_correct=10))

    def test_extras_that_stop_matching_are_a_regression_too(self) -> None:
        report = _report(Counts(files=10, extra_correct=5))

        assert regressions(report, _baseline(extra_correct=10))


class TestScoring:
    """歸桶的規則（plan §4.6）。`bucket` 是報表唯一的判斷，所以逐條釘住。"""

    def test_a_correct_automatic_import_counts_as_auto_correct(self) -> None:
        assert (
            bucket(_expected(PlanAction.IMPORT, 1, 2), _item(PlanAction.IMPORT, 1, 2))
            is Bucket.AUTO_CORRECT
        )

    def test_a_wrong_episode_counts_as_auto_wrong(self) -> None:
        assert (
            bucket(_expected(PlanAction.IMPORT, 1, 2), _item(PlanAction.IMPORT, 1, 99))
            is Bucket.AUTO_WRONG
        )

    def test_a_wrong_season_counts_as_auto_wrong(self) -> None:
        assert (
            bucket(_expected(PlanAction.IMPORT, 1, 2), _item(PlanAction.IMPORT, 2, 2))
            is Bucket.AUTO_WRONG
        )

    def test_low_confidence_lands_in_review_even_when_the_answer_is_right(self) -> None:
        item = _item(PlanAction.IMPORT, 1, 2, confidence=Confidence.LOW)

        assert bucket(_expected(PlanAction.IMPORT, 1, 2), item) is Bucket.REVIEW

    def test_medium_still_counts_as_automatic(self) -> None:
        """high 與 medium 都自動入庫（brief §6.5）。"""
        item = _item(PlanAction.IMPORT, 1, 2, confidence=Confidence.MEDIUM)

        assert bucket(_expected(PlanAction.IMPORT, 1, 2), item) is Bucket.AUTO_CORRECT

    def test_an_extra_the_corpus_agrees_with(self) -> None:
        assert bucket(_expected(PlanAction.EXTRA), _item(PlanAction.EXTRA)) is Bucket.EXTRA_CORRECT

    def test_filing_an_episode_as_an_extra_is_auto_wrong(self) -> None:
        """自動做了而且做錯，嚴重度與入錯集數一樣。"""
        assert (
            bucket(_expected(PlanAction.IMPORT, 1, 2), _item(PlanAction.EXTRA)) is Bucket.AUTO_WRONG
        )

    def test_parking_an_episode_as_unmatched_is_a_miss_not_a_wrong_import(self) -> None:
        assert (
            bucket(_expected(PlanAction.IMPORT, 1, 2), _item(PlanAction.UNMATCHED)) is Bucket.MISSED
        )

    def test_an_unmatched_file_the_corpus_agrees_with(self) -> None:
        assert (
            bucket(_expected(PlanAction.UNMATCHED), _item(PlanAction.UNMATCHED))
            is Bucket.UNMATCHED_CORRECT
        )

    def test_both_sides_agreeing_to_ignore_a_file(self) -> None:
        assert bucket(_expected(PlanAction.SKIP), _item(PlanAction.SKIP)) is Bucket.SKIPPED

    def test_silently_skipping_an_episode_is_a_miss(self) -> None:
        assert bucket(_expected(PlanAction.IMPORT, 1, 2), _item(PlanAction.SKIP)) is Bucket.MISSED

    def test_tags_are_compared_when_the_corpus_writes_them_down(self) -> None:
        expected = _expected(PlanAction.IMPORT, 1, 2, tags=Tags(resolution="1080p", group="Group"))
        item = _item(PlanAction.IMPORT, 1, 2, tags=Tags(resolution="720p", group="Group"))

        assert bucket(expected, item) is Bucket.AUTO_WRONG

    def test_the_same_episode_written_to_the_wrong_path_is_auto_wrong(self) -> None:
        """季集對了但檔名錯了，Jellyfin 那一端還是入錯（票 07）。"""
        item = _item(PlanAction.IMPORT, 1, 2, target=TARGET.replace("S01E02", "S01E02 - Wrong"))

        assert bucket(_expected(PlanAction.IMPORT, 1, 2), item) is Bucket.AUTO_WRONG

    def test_a_subtitle_the_corpus_agrees_with(self) -> None:
        assert (
            bucket(_expected(PlanAction.SUBTITLE, 1, 2), _item(PlanAction.SUBTITLE, 1, 2))
            is Bucket.SUBTITLE_CORRECT
        )

    def test_a_subtitle_hung_on_the_wrong_episode_is_auto_wrong(self) -> None:
        """字幕也是自動搬進媒體庫的檔案，掛錯與入錯集數一樣嚴重。"""
        item = _item(PlanAction.SUBTITLE, 1, 99, target=TARGET.replace("E02", "E99"))

        assert bucket(_expected(PlanAction.SUBTITLE, 1, 2), item) is Bucket.AUTO_WRONG

    def test_an_extra_written_somewhere_else_is_auto_wrong(self) -> None:
        item = _item(PlanAction.EXTRA, target="Other Show [tmdbid-2]/extras/a.mkv")

        assert bucket(_expected(PlanAction.EXTRA), item) is Bucket.AUTO_WRONG

    def test_a_confidence_below_the_expectation_is_not_an_error(self) -> None:
        """`min_confidence` 不參與比對：少自動化一點不等於做錯事。"""
        expected = _expected(PlanAction.IMPORT, 1, 2)
        item = _item(PlanAction.IMPORT, 1, 2, confidence=Confidence.MEDIUM)

        assert bucket(expected, item) is Bucket.AUTO_CORRECT


def _write_fixture(root: Path, **extra: str) -> None:
    raw = {
        "id": "anime/example",
        "source_url": "https://example.org/1",
        "torrent_name": "[Group] Bleach - 01",
        "tmdb": "tv-30984",
        "context": {"media": "tv:30984"},
        "files": [{"path": "[Group] Bleach - 01.mkv", "size": 1}],
        "expected": [],
        **extra,
    }
    (root / "example.json").write_text(json.dumps(raw), encoding="utf-8")


def _baseline(**overrides: int) -> Baseline:
    fields_ = {"auto_correct": 0, "auto_wrong": 0, "extra_correct": 0, "subtitle_correct": 0}
    return Baseline(**{**fields_, **overrides})


def _report(counts: Counts) -> Report:
    return Report(fixtures=1, overall=counts, by_category=dict.fromkeys(CATEGORIES, Counts()))


def _expected(
    action: PlanAction,
    season: int | None = None,
    episode: int | None = None,
    *,
    tags: Tags | None = None,
    target: str = TARGET,
) -> Expected:
    return Expected(
        path="Show - 02.mkv",
        kind=FileKind.VIDEO,
        action=action,
        season=season,
        episode=episode,
        episode_end=None,
        tags=tags,
        target=target if action in _WRITTEN else "",
    )


def _item(
    action: PlanAction,
    season: int | None = None,
    episode: int | None = None,
    *,
    tags: Tags | None = None,
    confidence: Confidence = Confidence.HIGH,
    target: str = TARGET,
) -> PlanItem:
    return PlanItem(
        rel_path="Show - 02.mkv",
        kind=FileKind.VIDEO,
        action=action,
        season=season,
        episode_start=episode,
        tags=tags or Tags(),
        confidence=confidence,
        target_path=target if action in _WRITTEN else "",
    )
