"""媒體庫牆的排序選單與 `sortBy`（M1.5 票 06、研究 library-browsing.md §7）。

選單照 jellyfin-web `src/controllers/shows/tvshows.js` 與 `movies/movies.js` 的 `showSortMenu`
（v10.10.7 與 v10.11.11 相同）：兩種媒體庫的選項不同，排序鍵後面接的鍵也不同。
"""

from __future__ import annotations

import pytest

from berth.domain import CollectionType, LibrarySort
from berth.services.jellyfin_access import BrowsableLibrary, SortNotOfferedError


def library(collection_type: CollectionType) -> BrowsableLibrary:
    return BrowsableLibrary(id="library", name="Library", collection_type=collection_type)


def test_a_tv_library_offers_jellyfin_webs_tv_sort_menu() -> None:
    assert library(CollectionType.TVSHOWS).sorts == (
        LibrarySort.SORT_NAME,
        LibrarySort.RANDOM,
        LibrarySort.COMMUNITY_RATING,
        LibrarySort.DATE_CREATED,
        LibrarySort.DATE_LAST_CONTENT_ADDED,
        LibrarySort.SERIES_DATE_PLAYED,
        LibrarySort.OFFICIAL_RATING,
        LibrarySort.PREMIERE_DATE,
    )


def test_a_film_library_offers_jellyfin_webs_film_sort_menu() -> None:
    assert library(CollectionType.MOVIES).sorts == (
        LibrarySort.SORT_NAME,
        LibrarySort.RANDOM,
        LibrarySort.COMMUNITY_RATING,
        LibrarySort.CRITIC_RATING,
        LibrarySort.DATE_CREATED,
        LibrarySort.DATE_PLAYED,
        LibrarySort.OFFICIAL_RATING,
        LibrarySort.PLAY_COUNT,
        LibrarySort.PREMIERE_DATE,
        LibrarySort.RUNTIME,
    )


@pytest.mark.parametrize(
    ("collection_type", "sort", "expected"),
    [
        (CollectionType.TVSHOWS, LibrarySort.SORT_NAME, ("SortName",)),
        (CollectionType.TVSHOWS, LibrarySort.COMMUNITY_RATING, ("CommunityRating", "SortName")),
        (CollectionType.MOVIES, LibrarySort.SORT_NAME, ("SortName", "ProductionYear")),
        (
            CollectionType.MOVIES,
            LibrarySort.DATE_PLAYED,
            ("DatePlayed", "SortName", "ProductionYear"),
        ),
        # 沒指定就是選單第一個：打開牆時的排序。
        (CollectionType.MOVIES, None, ("SortName", "ProductionYear")),
        # 隨機後面不接鍵：jellyfin-web 送的就是 `Random`。
        (CollectionType.TVSHOWS, LibrarySort.RANDOM, ("Random",)),
        (CollectionType.MOVIES, LibrarySort.RANDOM, ("Random",)),
    ],
)
def test_each_sort_is_followed_by_what_breaks_its_ties(
    collection_type: CollectionType, sort: LibrarySort | None, expected: tuple[str, ...]
) -> None:
    assert library(collection_type).sort_by(sort) == expected


@pytest.mark.parametrize(
    ("collection_type", "sort"),
    [
        (CollectionType.TVSHOWS, LibrarySort.DATE_PLAYED),
        (CollectionType.MOVIES, LibrarySort.SERIES_DATE_PLAYED),
    ],
)
def test_a_sort_off_this_kinds_menu_is_refused(
    collection_type: CollectionType, sort: LibrarySort
) -> None:
    """「最近看過」兩種媒體庫各是一個鍵；用錯的那一個 Jellyfin 不報錯，只是默默換一種順序。"""
    with pytest.raises(SortNotOfferedError):
        library(collection_type).sort_by(sort)
