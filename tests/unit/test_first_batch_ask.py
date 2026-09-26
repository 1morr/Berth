"""第一批在問什麼（M4 票 11、`services.first_batch`）：季集怎麼讀出來的（`basis_of`）與蓋到的集數
（`spans_of`）。兩支都是純函式；查資料庫的那一半在 `tests/integration/test_first_batch.py`。"""

from __future__ import annotations

import pytest

from berth.domain import FirstBatchBasis, ItemReason, why
from berth.domain import ReasonCode as Code
from berth.services.first_batch import Span, basis_of, spans_of

TITLE = why(Code.TITLE_EXACT, title="BLACK TORCH")


def run(number: int) -> ItemReason:
    return why(Code.PUBLISHED_IN_RUN, published="2026-07-20", run=number, runs=2, episode="S01E01")


class TestBasis:
    @pytest.mark.parametrize(
        ("reasons", "expected"),
        [
            ((why(Code.SINGLE_SEASON), TITLE), FirstBatchBasis.LITERAL),
            ((why(Code.SEASON_FROM_RELEASE, season=2), TITLE), FirstBatchBasis.LITERAL),
            ((run(1), TITLE), FirstBatchBasis.LITERAL),
            ((run(2), TITLE), FirstBatchBasis.RUNS),
            ((why(Code.AIR_DATE_RUN, season=2, runs=2, episode="S01E13"),), FirstBatchBasis.RUNS),
            (
                (
                    why(
                        Code.COUR_OFFSET,
                        season=3,
                        part=2,
                        first="S03E13",
                        number=1,
                        episode="S03E13",
                    ),
                ),
                FirstBatchBasis.RUNS,
            ),
            (
                (why(Code.ABSOLUTE_CUMULATIVE, number="28", episode="S02E04"),),
                FirstBatchBasis.ABSOLUTE,
            ),
            ((why(Code.ABSOLUTE_GROUP, number="28", episode="S02E04"),), FirstBatchBasis.ABSOLUTE),
            ((why(Code.SEASON_FROM_ARC, arc="柱訓練篇", season=4),), FirstBatchBasis.ARC),
            ((why(Code.FINAL_SEASON, season=4),), FirstBatchBasis.ARC),
            ((why(Code.SEASON_FROM_JOB, season=1),), FirstBatchBasis.SERIES),
            ((why(Code.SERIES_CORRECTED, season=1, offset="+12"),), FirstBatchBasis.SERIES),
        ],
        ids=lambda value: value.value if isinstance(value, FirstBatchBasis) else "",
    )
    def test_the_reasons_say_how(
        self, reasons: tuple[ItemReason, ...], expected: FirstBatchBasis
    ) -> None:
        assert basis_of(None, None, reasons) is expected

    def test_values_on_the_series_win(self) -> None:
        literal = (why(Code.SINGLE_SEASON),)
        assert basis_of(1, None, literal) is FirstBatchBasis.SERIES
        assert basis_of(None, 12, literal) is FirstBatchBasis.SERIES

    def test_a_replanned_row_cannot_tell(self) -> None:
        """帳本那一列的 Plan Item 被重新規劃換掉：看不出是怎麼讀的。"""
        assert basis_of(None, None, None) is FirstBatchBasis.MIXED


class TestSpans:
    def test_consecutive_episodes_in_a_season_are_one_span(self) -> None:
        assert spans_of([(1, 1), (1, 2), (1, 3), (1, 5), (2, 1)]) == (
            Span(1, 1, 3),
            Span(1, 5, 5),
            Span(2, 1, 1),
        )

    def test_nothing(self) -> None:
        assert spans_of([]) == ()
