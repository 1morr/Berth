"""AI 送單的比對（`submit_guard.refusal_of`，M5 票 12）：出處之外的那一半——符合、集、全域標題規則。

出處（只收這則對話搜出來的）與整條路在 `tests/integration/test_assistant_search_submit.py`。
"""

from __future__ import annotations

from berth.domain import MediaKind, SearchVerdict, Tags
from berth.services.submit_guard import SearchResultRow, SubmitRefusal, refusal_of

#: S02 缺 E01–E03。
WANTED = [(2, 1, 3)]


def row(
    season: int | None = 2,
    start: int | None = 1,
    end: int | None = None,
    verdict: SearchVerdict = SearchVerdict.FITS,
    title: str = "[ANi] SPY x FAMILY - 26 [1080P][Baha]",
) -> SearchResultRow:
    return SearchResultRow(
        source_id="s",
        title=title,
        indexer="ACG.RIP",
        size=1,
        seeders=1,
        info_url="",
        published_at=None,
        tags=Tags(),
        season=season,
        episode_start=start,
        episode_end=end,
        whole_season=False,
        strategy=None,
        verdict=verdict,
        evidence="",
        refusal=None,
        refusal_detail="",
    )


def judge(
    found: SearchResultRow,
    *,
    kind: MediaKind = MediaKind.TV,
    wanted: list[tuple[int, int, int]] = WANTED,
    whole: list[int] | None = None,
    rules: tuple[str, ...] = (),
) -> tuple[SubmitRefusal, str] | None:
    return refusal_of(found, kind=kind, wanted=wanted, whole_seasons=whole or [], rules=rules)


def test_a_fitting_row_for_a_wanted_episode_may_be_sent() -> None:
    assert judge(row(start=2)) is None
    assert judge(row(start=1, end=3)) is None


def test_every_estimated_episode_must_be_wanted() -> None:
    """碰到一集就放行的話，只缺幾集時會把整段（或整季）再下載一次。"""
    assert judge(row(start=1, end=12)) == (SubmitRefusal.OTHER_EPISODES, "S02E01-E12")
    assert judge(row(season=1, start=3)) == (SubmitRefusal.OTHER_EPISODES, "S01E03")


def test_a_season_pack_only_when_the_whole_season_is_missing() -> None:
    """2026-10-24 使用者：整季缺時季包正是要的那一筆。"""
    pack = row(start=None)
    assert judge(pack, whole=[2]) is None
    assert judge(pack) == (SubmitRefusal.OTHER_EPISODES, "S02")


def test_a_row_without_a_season_cannot_be_matched_to_episodes() -> None:
    assert judge(row(season=None, start=None)) == (SubmitRefusal.EPISODES_UNKNOWN, "")


def test_a_show_with_nothing_missing_sends_nothing() -> None:
    assert judge(row(), wanted=[]) == (SubmitRefusal.OTHER_EPISODES, "S02E01")


def test_a_movie_has_no_episodes_to_match() -> None:
    assert judge(row(season=None, start=None), kind=MediaKind.MOVIE, wanted=[]) is None


def test_only_fitting_rows_and_the_verdict_is_said() -> None:
    found = row(verdict=SearchVerdict.PARTIAL_TITLE)
    assert judge(found) == (SubmitRefusal.NOT_A_MATCH, "partial_title")


def test_the_global_title_rules_block_with_the_rule() -> None:
    assert judge(row(), rules=("/baha/i",)) == (SubmitRefusal.EXCLUDED, "/baha/i")
    assert judge(row(), rules=("Nyaa",)) is None
