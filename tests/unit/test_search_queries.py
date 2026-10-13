"""照作品名搜尋時，chip 上有哪些名字與季、預設開哪幾顆、開了的組出哪幾個查詢（M4 票 84）。

`.scratch/m4/search-choose-shape.md`。輸入是純資料（快照 + 開了哪些），所以不碰資料庫也不打索引站；
預覽與真的送出去的那幾個查詢走同一個函式（`tests/integration/test_search.py` 守那一半）。
"""

from __future__ import annotations

from berth.domain import MediaKind, MediaSnapshot, NameKind, SeasonSnapshot
from berth.services.search_queries import (
    QueryChoice,
    SearchName,
    default_choice,
    search_names,
    season_numbers,
    title_queries,
)

SPY = MediaSnapshot(
    tmdb_id=120089,
    kind=MediaKind.TV,
    title="間諜家家酒",
    title_en="SPY x FAMILY",
    title_original="SPY×FAMILY",
    title_zh_cn="间谍过家家",
    titles=(
        "SPY x FAMILY",
        "SPY×FAMILY",
        "Agent x Ailə",
        "間諜家家酒",
        "间谍过家家",
        "스파이 패밀리",
    ),
    seasons=tuple(SeasonSnapshot(season_number=number) for number in (0, 1, 2, 3)),
)

BEAR = MediaSnapshot(
    tmdb_id=136315,
    kind=MediaKind.TV,
    title="大熊餐廳",
    title_en="The Bear",
    title_original="The Bear",
    titles=("The Bear", "大熊餐廳"),
    seasons=tuple(SeasonSnapshot(season_number=number) for number in (1, 2, 3)),
)

#: `remembered` 的出廠值：英文名與原名開、兩種中文名關（`SearchSettings`）。
FACTORY = {
    NameKind.ENGLISH: True,
    NameKind.ORIGINAL: True,
    NameKind.CHINESE: False,
    NameKind.SIMPLIFIED: False,
}


def test_each_name_says_which_kind_it_is() -> None:
    """一個名字一顆 chip，照英文、原名、中文、簡體中文、別名排；別名去掉已經列過的。"""
    assert search_names(SPY) == (
        SearchName("SPY x FAMILY", (NameKind.ENGLISH,)),
        SearchName("SPY×FAMILY", (NameKind.ORIGINAL,)),
        SearchName("間諜家家酒", (NameKind.CHINESE,)),
        SearchName("间谍过家家", (NameKind.SIMPLIFIED,)),
        SearchName("Agent x Ailə", (NameKind.ALIAS,)),
        SearchName("스파이 패밀리", (NameKind.ALIAS,)),
    )


def test_one_string_that_is_two_kinds_is_one_chip() -> None:
    """`The Bear` 既是英文名也是原名：一顆 chip、兩個標記，不問兩次。"""
    assert search_names(BEAR)[0] == SearchName("The Bear", (NameKind.ENGLISH, NameKind.ORIGINAL))


def test_a_display_title_that_fell_back_to_english_is_not_a_chinese_name() -> None:
    """TMDB 沒有 `zh-TW` 翻譯時顯示名就是英文名——那不是中文名，開中文名的人不該拿到它。"""
    untranslated = BEAR.model_copy(update={"title": "The Bear", "titles": ("The Bear",)})

    assert search_names(untranslated) == (
        SearchName("The Bear", (NameKind.ENGLISH, NameKind.ORIGINAL)),
    )


def test_by_default_the_english_and_original_names_are_on_with_the_latest_season() -> None:
    """出廠預設：英文名與原名；「不指定季」，兩季以上另開最新一季（第 0 季特別篇不算）。"""
    assert default_choice(SPY, FACTORY) == QueryChoice(
        names=("SPY x FAMILY", "SPY×FAMILY"), seasons=(3,), any_season=True
    )


def test_a_remembered_kind_is_on_for_every_work() -> None:
    """在別部作品開了中文名，這一部的中文名預設也開；別名沒有記住這回事。"""
    remembered = {**FACTORY, NameKind.CHINESE: True, NameKind.ORIGINAL: False}

    assert default_choice(SPY, remembered).names == ("SPY x FAMILY", "間諜家家酒")


def test_a_chip_of_two_kinds_is_on_when_either_kind_is() -> None:
    """`The Bear`（英文名 · 原名）：關了原名，英文名還開著，它就還在。"""
    remembered = {**FACTORY, NameKind.ORIGINAL: False}

    assert default_choice(BEAR, remembered).names == ("The Bear",)


def test_a_single_season_show_and_a_movie_open_no_season() -> None:
    """只有一季時沒有「哪一季」要分：第一季的發佈幾乎不寫季號。電影沒有季。"""
    single = BEAR.model_copy(update={"seasons": (SeasonSnapshot(season_number=1),)})
    movie = BEAR.model_copy(update={"kind": MediaKind.MOVIE, "seasons": ()})

    assert default_choice(single, FACTORY).seasons == ()
    assert season_numbers(movie) == ()
    assert season_numbers(SPY) == (1, 2, 3)


def test_the_queries_are_each_name_with_each_season() -> None:
    """名字優先：一個名字問完它的每一季，再換下一個。拉丁字兩種季記號、CJK 字 `第N季`。"""
    choice = QueryChoice(names=("SPY x FAMILY", "間諜家家酒"), seasons=(3,), any_season=True)

    assert title_queries(SPY, choice) == (
        "SPY x FAMILY",
        "SPY x FAMILY S03",
        "SPY x FAMILY Season 3",
        "間諜家家酒",
        "間諜家家酒 第3季",
    )


def test_the_order_is_the_chips_not_the_clicks() -> None:
    """先按中文名再按英文名，問的順序照舊：清單不跟著按的順序跳。"""
    choice = QueryChoice(names=("間諜家家酒", "SPY x FAMILY"), seasons=(), any_season=True)

    assert title_queries(SPY, choice) == ("SPY x FAMILY", "間諜家家酒")


def test_without_any_season_only_the_chosen_seasons_are_asked() -> None:
    choice = QueryChoice(names=("The Bear",), seasons=(1, 3), any_season=False)

    assert title_queries(BEAR, choice) == (
        "The Bear S01",
        "The Bear Season 1",
        "The Bear S03",
        "The Bear Season 3",
    )


def test_an_ampersand_name_also_asks_the_spelled_out_one() -> None:
    """`&` 照票 69：原樣一個、寫成 `and` 一個，兩者各配開了的季。"""
    law = BEAR.model_copy(
        update={"title": "Law & Order", "title_en": "Law & Order", "title_original": "Law & Order"}
    )
    choice = QueryChoice(names=("Law & Order",), seasons=(2,), any_season=True)

    assert title_queries(law, choice) == (
        "Law & Order",
        "Law & Order S02",
        "Law & Order Season 2",
        "Law and Order",
        "Law and Order S02",
        "Law and Order Season 2",
    )


def test_names_and_seasons_the_work_does_not_have_are_not_asked() -> None:
    """網址被手改時：不是這部作品的名字或季不問——要問別的字，打關鍵字那條路一直在。"""
    choice = QueryChoice(names=("The Bear", "Spider-Man"), seasons=(3, 9), any_season=False)

    assert title_queries(BEAR, choice) == ("The Bear S03", "The Bear Season 3")
