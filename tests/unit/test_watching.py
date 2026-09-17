"""繼續觀看與下一集的一格怎麼從 Jellyfin 的 item 推出來（M1.5 票 07）。

**取圖照 jellyfin-web 的橫卡**（v10.11.11 `cardBuilder.getCardImageUrl`，首頁兩列
`preferThumb: true`、`inheritThumb` 預設成立，研究 §7）：自己的 Thumb → 劇的 Thumb → 父層的 Thumb
→ 自己的 Backdrop → 父層的 Backdrop（只有集）→ 集自己的 Primary。電影的 Primary 是 2:3 海報，
塞進 16:9 會被裁掉大半，所以不取。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SERIES,
    JellyfinItem,
    JellyfinUserData,
    ParentImage,
)
from berth.domain import JellyfinImageType, MediaKind
from berth.services.watching import CardImage, WatchingCard, landscape, watching_cards

EPISODE = "cd2f059cd4fdef1da23617e86514232e"
SERIES = "2a9857e656bbd18b7c3c3a3b4ee5eef1"
SEASON = "e287646874088d4b73b9578d6fc51da6"
FILM = "aaad8034da2f8c4db82f7aa3e26a4e3e"
TAGS = {
    name: f"{index:032x}"
    for index, name in enumerate(
        ("thumb", "series_thumb", "parent_thumb", "backdrop", "parent_backdrop", "primary"),
        start=1,
    )
}

#: Alpha Show 第一季第二集，每一種圖都有。
EVERY_IMAGE = JellyfinItem(
    id=EPISODE,
    type=ITEM_EPISODE,
    name="The Second One",
    path="/media/tv/Alpha Show (2022)/Season 01/Alpha Show (2022) - S01E02.mkv",
    tmdb_id="",
    series_id=SERIES,
    series_name="Alpha Show",
    season=1,
    episode_start=2,
    thumb_tag=TAGS["thumb"],
    series_thumb_tag=TAGS["series_thumb"],
    parent_thumb=ParentImage(item_id=SEASON, tag=TAGS["parent_thumb"]),
    backdrop_tag=TAGS["backdrop"],
    parent_backdrop=ParentImage(item_id=SERIES, tag=TAGS["parent_backdrop"]),
    primary_tag=TAGS["primary"],
)

#: Foxtrot Movie，看到一半。
FOXTROT = JellyfinItem(
    id=FILM,
    type=ITEM_MOVIE,
    name="Foxtrot Movie",
    path="/media/movies/Foxtrot Movie (2018)/Foxtrot Movie (2018).mkv",
    tmdb_id="157336",
    year=2018,
    user_data=JellyfinUserData(played=False, played_percentage=50.0, unplayed_item_count=None),
)

#: 一格一格拿掉，照取圖順序。
WITHOUT = (
    {"thumb_tag": ""},
    {"series_thumb_tag": ""},
    {"parent_thumb": None},
    {"backdrop_tag": ""},
    {"parent_backdrop": None},
    {"primary_tag": ""},
)


def without(count: int) -> JellyfinItem:
    changes = {key: value for step in WITHOUT[:count] for key, value in step.items()}
    return replace(EVERY_IMAGE, **changes)  # type: ignore[arg-type]  # 欄位名來自上面那張表


@pytest.mark.parametrize(
    ("dropped", "expected"),
    [
        (0, CardImage(EPISODE, JellyfinImageType.THUMB, TAGS["thumb"])),
        (1, CardImage(SERIES, JellyfinImageType.THUMB, TAGS["series_thumb"])),
        (2, CardImage(SEASON, JellyfinImageType.THUMB, TAGS["parent_thumb"])),
        (3, CardImage(EPISODE, JellyfinImageType.BACKDROP, TAGS["backdrop"])),
        (4, CardImage(SERIES, JellyfinImageType.BACKDROP, TAGS["parent_backdrop"])),
        (5, CardImage(EPISODE, JellyfinImageType.PRIMARY, TAGS["primary"])),
        (6, None),
    ],
)
def test_an_episode_takes_the_first_wide_image_in_jellyfin_webs_order(
    dropped: int, expected: CardImage | None
) -> None:
    assert landscape(without(dropped)) == expected


def test_a_film_takes_its_own_thumb_then_its_own_backdrop() -> None:
    film = replace(FOXTROT, thumb_tag=TAGS["thumb"], backdrop_tag=TAGS["backdrop"])

    assert landscape(film) == CardImage(FILM, JellyfinImageType.THUMB, TAGS["thumb"])
    assert landscape(replace(film, thumb_tag="")) == CardImage(
        FILM, JellyfinImageType.BACKDROP, TAGS["backdrop"]
    )


def test_a_film_never_borrows_a_parents_backdrop_or_crops_its_poster() -> None:
    """jellyfin-web 只讓集借父層的 Backdrop；電影的 Primary 是 2:3 海報。"""
    film = replace(
        FOXTROT,
        parent_backdrop=ParentImage(item_id=SERIES, tag=TAGS["parent_backdrop"]),
        primary_tag=TAGS["primary"],
    )

    assert landscape(film) is None


def test_an_episode_card_names_the_show_the_episode_and_how_far_in() -> None:
    under_way = replace(
        EVERY_IMAGE,
        user_data=JellyfinUserData(played=False, played_percentage=30.0, unplayed_item_count=None),
    )

    assert watching_cards([under_way]) == (
        WatchingCard(
            item_id=EPISODE,
            kind=MediaKind.TV,
            title="Alpha Show",
            episode_name="The Second One",
            season=1,
            episode_start=2,
            episode_end=None,
            year=None,
            progress=30,
            image=CardImage(EPISODE, JellyfinImageType.THUMB, TAGS["thumb"]),
        ),
    )


def test_a_film_card_is_its_own_name_and_year() -> None:
    [card] = watching_cards([FOXTROT])

    assert (card.kind, card.title, card.episode_name, card.season, card.year, card.progress) == (
        MediaKind.MOVIE,
        "Foxtrot Movie",
        "",
        None,
        2018,
        50,
    )


def test_a_film_watched_before_and_rewatched_part_way_still_shows_how_far_in() -> None:
    """這一列說的是「看到哪」：看過又重看到一半，牆上說「已看」，這一格照樣說 42%。"""
    again = replace(
        FOXTROT,
        user_data=JellyfinUserData(played=True, played_percentage=42.0, unplayed_item_count=None),
    )

    [card] = watching_cards([again])

    assert card.progress == 42


def test_an_episode_not_started_has_no_progress() -> None:
    """下一集那一列：`enableResumable=false`，沒有看到一半的集。"""
    [card] = watching_cards([EVERY_IMAGE])

    assert card.progress is None


def test_only_episodes_and_films_are_cards() -> None:
    """Resume 帶 `mediaTypes=Video` 仍可能有家庭影片、音樂錄影帶：卡片說不出它們是什麼。"""
    others = [
        JellyfinItem(id="a" * 32, type="Video", name="Birthday", path="/home/b.mkv", tmdb_id=""),
        JellyfinItem(id="b" * 32, type="MusicVideo", name="Song", path="/mv/s.mkv", tmdb_id=""),
        JellyfinItem(id="c" * 32, type=ITEM_SERIES, name="Alpha Show", path="/tv/a", tmdb_id=""),
    ]

    cards = watching_cards([others[0], EVERY_IMAGE, *others[1:], FOXTROT])

    assert [card.item_id for card in cards] == [EPISODE, FILM]
