"""Jellyfin 回驗的比對本身（`resolver.disagreement`，M3 票 17）：季號、集號範圍、作品的 TMDB id。

整條路（反查、對帳、收掉）在 `tests/integration/test_jellyfin_verify.py`；這裡只守比對的邊角。
"""

from __future__ import annotations

from berth.adapters.jellyfin import ITEM_EPISODE, ITEM_MOVIE, JellyfinItem
from berth.models import LedgerEntry
from berth.services.resolver import disagreement


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

    def test_jellyfin_reading_no_numbers_disagrees(self) -> None:
        """認不出編號（沒被認成正片的那一種）也是不一致。"""
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
