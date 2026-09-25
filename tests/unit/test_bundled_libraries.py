"""套件內 Jellyfin 的媒體庫清單規則（M3 票 06f）。

精靈的剖面在送出之前用同一組規則擋（`web/src/setup/libraryRules.ts` 與它的測試），這裡守
後端那一份：每一種拒絕都指得出是哪一列，前後空白不算數，已經建好的那幾列不能被改掉。
"""

from __future__ import annotations

import pytest

from berth.domain import BundledLibraryRefusal, CollectionType
from berth.models import DEFAULT_BUNDLED_LIBRARIES, BundledLibrary
from berth.services.jellyfin import BundledLibraryRejectedError, check_bundled_libraries

MOVIES = CollectionType.MOVIES
SHOWS = CollectionType.TVSHOWS


def row(name: str, folder: str, collection_type: CollectionType = SHOWS) -> BundledLibrary:
    return BundledLibrary(name=name, collection_type=collection_type, folder=folder)


def refusal(
    rows: list[BundledLibrary], built: tuple[BundledLibrary, ...] = ()
) -> tuple[BundledLibraryRefusal, int | None]:
    with pytest.raises(BundledLibraryRejectedError) as caught:
        check_bundled_libraries(rows, built=built)
    return caught.value.reason, caught.value.row


def test_the_default_three_pass() -> None:
    assert check_bundled_libraries(list(DEFAULT_BUNDLED_LIBRARIES), built=()) == (
        DEFAULT_BUNDLED_LIBRARIES
    )


def test_any_list_of_named_folders_passes() -> None:
    rows = [row("電影", "films", MOVIES), row("電視劇（華語）", "tv-zh"), row("紀錄片", "紀錄片")]

    assert check_bundled_libraries(rows, built=()) == tuple(rows)


def test_surrounding_spaces_are_dropped_not_kept() -> None:
    """名稱與資料夾各自修掉前後空白：`" tv "` 在 Windows 上建不出來，名稱也會對不上 Jellyfin。"""
    (kept,) = check_bundled_libraries([row("  TV ", " tv  ")], built=())

    assert (kept.name, kept.folder) == ("TV", "tv")


def test_an_empty_list_is_refused() -> None:
    assert refusal([]) == (BundledLibraryRefusal.EMPTY, None)


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([row("Movies", "movies"), row(" ", "tv")], (BundledLibraryRefusal.NAME_MISSING, 1)),
        ([row("Movies", "movies"), row("TV", " ")], (BundledLibraryRefusal.FOLDER_MISSING, 1)),
        # 不分大小寫：Jellyfin 認得出「TV」與「tv」是同一個名字嗎不可知，寧可先擋。
        ([row("TV", "tv"), row("tv", "tv-2")], (BundledLibraryRefusal.NAME_TAKEN, 1)),
        ([row("TV", "tv"), row("劇集", "TV")], (BundledLibraryRefusal.FOLDER_TAKEN, 1)),
    ],
)
def test_missing_and_repeated_values_point_at_their_row(
    rows: list[BundledLibrary], expected: tuple[BundledLibraryRefusal, int]
) -> None:
    assert refusal(rows) == expected


@pytest.mark.parametrize("folder", ["..", ".", "../elsewhere", "/data/tv", "tv/anime", "tv\\anime"])
def test_a_folder_must_stay_one_level_under_the_library_root(folder: str) -> None:
    assert refusal([row("TV", folder)]) == (BundledLibraryRefusal.FOLDER_OUTSIDE_ROOT, 0)


@pytest.mark.parametrize("folder", ["tv:zh", "tv?", 'tv"', "tv|zh", "tv<", "tv*", "tv\x01"])
def test_a_folder_windows_cannot_hold_is_refused(folder: str) -> None:
    assert refusal([row("TV", folder)]) == (BundledLibraryRefusal.FOLDER_CHARACTERS, 0)


def test_a_built_row_may_stay_while_new_rows_come_and_go() -> None:
    built = (row("Movies", "movies", MOVIES),)

    rows = [row("Movies", "movies", MOVIES), row("紀錄片", "docs")]

    assert check_bundled_libraries(rows, built=built) == tuple(rows)


@pytest.mark.parametrize(
    "rows",
    [
        # 刪掉：Berth 不刪 Jellyfin 的東西，清單上少了它只會讓人以為它不在了。
        [row("TV", "tv")],
        # 改名：同名認得的規則下，重跑會多建一個指向同一個資料夾的媒體庫。
        [row("電影", "movies", MOVIES), row("TV", "tv")],
        [row("Movies", "films", MOVIES), row("TV", "tv")],
        [row("Movies", "movies", SHOWS), row("TV", "tv")],
    ],
)
def test_a_built_row_cannot_be_changed_or_dropped(rows: list[BundledLibrary]) -> None:
    built = (row("Movies", "movies", MOVIES),)

    reason, _ = refusal(rows, built=built)

    assert reason is BundledLibraryRefusal.BUILT_CHANGED
