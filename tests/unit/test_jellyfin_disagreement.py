"""Jellyfin 回驗的比對本身（`resolver.disagreement`，M3 票 17）：季號、集號範圍、作品的 TMDB id；
與比之前先問的那一題——Jellyfin 認完了沒（`resolver.still_identifying`，M4 票 02）。

整條路（反查、對帳、收掉）在 `tests/integration/test_jellyfin_verify.py`；這裡只守比對的邊角。
"""

from __future__ import annotations

from berth.adapters.jellyfin import ITEM_EPISODE, ITEM_MOVIE, JellyfinItem
from berth.models import LedgerEntry
from berth.services.resolver import disagreement, still_identifying


class TestDisagreement:
    """比對本身（純函式）：季號、集號範圍、作品的 TMDB id。"""

    def entry(
        self, season: int | None = None, start: int | None = None, end: int | None = None
    ) -> LedgerEntry:
        return LedgerEntry(
            target_path="/data/library/x.mkv", season=season, episode_start=start, episode_end=end
        )

    def item(
        self, season: int | None = None, start: int | None = None, end: int | None = None
    ) -> JellyfinItem:
        return JellyfinItem(
            id="i",
            type=ITEM_EPISODE,
            name="n",
            path="/p",
            tmdb_id="",
            season=season,
            episode_start=start,
            episode_end=end,
        )

    def test_a_single_episode_without_an_end_agrees_with_an_end_equal_to_its_start(self) -> None:
        """帳本與 Jellyfin 對單集檔的 `episode_end` 寫法不一定相同（`None` 或等於起始集）。"""
        entry = self.entry(season=1, start=3, end=3)
        item = self.item(season=1, start=3)

        assert disagreement(entry, item, ledger_tmdb="1", jellyfin_tmdb="1") is None

    def test_jellyfin_reading_no_numbers_still_describes_both_sides(self) -> None:
        """認不出編號時比對照樣說得出兩邊各是什麼：六次都還認不出時開的那一件就是它
        （「還在認」由 `still_identifying` 先擋，M4 票 02）。"""
        entry = self.entry(season=1, start=3)
        item = self.item()

        found = disagreement(entry, item, ledger_tmdb="1", jellyfin_tmdb="1")

        assert found is not None
        assert found["differs"] == ["season", "episode"]

    def test_a_movie_compares_only_the_work(self) -> None:
        entry = self.entry()
        movie = JellyfinItem(id="m", type=ITEM_MOVIE, name="n", path="/p", tmdb_id="2")

        assert disagreement(entry, movie, ledger_tmdb="2", jellyfin_tmdb="2") is None
        found = disagreement(entry, movie, ledger_tmdb="2", jellyfin_tmdb="3")
        assert found is not None
        assert found["differs"] == ["tmdb"]

    def test_a_row_without_a_work_does_not_compare_the_work(self) -> None:
        """帳本沒有作品（Media 被刪了）時說不出該是哪一部，不拿空字串去比。"""
        entry = self.entry(season=1, start=3)
        item = self.item(season=1, start=3)

        assert disagreement(entry, item, ledger_tmdb="", jellyfin_tmdb="9") is None


class TestStillIdentifying:
    """Jellyfin 還沒認完剛掃進來的檔案：季集是 `None`、Series 沒有 TMDB id（2026-09-26 試跑）。

    那不是「認得不一樣」，是「還沒認出」——照還沒找到的節奏再問，不開 Issue（M4 票 02）。
    """

    def episode(
        self, season: int | None = None, start: int | None = None, tmdb: str = ""
    ) -> JellyfinItem:
        return JellyfinItem(
            id="i",
            type=ITEM_EPISODE,
            name="BLACK TORCH",
            path="/p",
            tmdb_id=tmdb,
            season=season,
            episode_start=start,
        )

    def test_the_trial_reading_is_still_identifying(self) -> None:
        """試跑記下的那一份：Name 是作品名、季集 `None`、Series 沒有 Tmdb。"""
        assert still_identifying(self.episode(), ledger_tmdb="1", jellyfin_tmdb="")

    def test_no_numbers_is_still_identifying_even_with_a_work(self) -> None:
        assert still_identifying(self.episode(), ledger_tmdb="1", jellyfin_tmdb="1")
        assert still_identifying(self.episode(season=1), ledger_tmdb="1", jellyfin_tmdb="1")

    def test_a_series_without_a_tmdb_id_is_still_identifying(self) -> None:
        assert still_identifying(self.episode(season=1, start=3), ledger_tmdb="1", jellyfin_tmdb="")

    def test_a_full_reading_is_identified_even_when_it_differs(self) -> None:
        """認成別的季集、別的作品是「認得不一樣」，照樣開 Issue。"""
        assert not still_identifying(
            self.episode(season=2, start=9), ledger_tmdb="1", jellyfin_tmdb="999"
        )

    def test_a_row_without_a_work_does_not_wait_for_the_work(self) -> None:
        """帳本說不出作品時不比作品（`disagreement`），也就不必等 Jellyfin 認出作品。"""
        assert not still_identifying(
            self.episode(season=1, start=3), ledger_tmdb="", jellyfin_tmdb=""
        )

    def test_a_movie_has_no_numbers_to_wait_for(self) -> None:
        movie = JellyfinItem(id="m", type=ITEM_MOVIE, name="n", path="/p", tmdb_id="")

        assert not still_identifying(movie, ledger_tmdb="2", jellyfin_tmdb="2")
        assert still_identifying(movie, ledger_tmdb="2", jellyfin_tmdb="")
