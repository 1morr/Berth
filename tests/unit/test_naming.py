"""命名引擎的純函式（plan §5）。

模板在 M0 票 04 的實驗後**凍結**，所以這裡的期望值不是從程式推出來的，而是抄自 plan §5、
brief §7.1 / §7.2 / §6.7 的範例與那次實測的結論（brief §20.6）。六種模板各自一組。
"""

from __future__ import annotations

from datetime import date

import pytest

from berth.domain import (
    EpisodeSnapshot,
    FileKind,
    Lang,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    SeasonSnapshot,
    Source,
    Tags,
)
from berth.naming import (
    Reading,
    episode_target,
    extension,
    extras_target,
    folder_name,
    movie_target,
    read_target,
    sanitize,
    season_folder,
    subtitle_target,
)


def snapshot(**overrides: object) -> MediaSnapshot:
    defaults: dict[str, object] = {
        "tmdb_id": 120089,
        "kind": MediaKind.TV,
        "title": "SPY×FAMILY 間諜家家酒",
        "title_en": "SPY x FAMILY",
        "title_original": "SPY×FAMILY",
        "year": 2022,
        "first_air_date": date(2022, 4, 9),
    }
    return MediaSnapshot(**{**defaults, **overrides})  # type: ignore[arg-type]


class TestFolderName:
    def test_it_follows_the_frozen_template(self) -> None:
        """`{title} ({year}) [tmdbid-{id}]`（plan §5）。"""
        assert folder_name(snapshot()) == "SPY x FAMILY (2022) [tmdbid-120089]"

    def test_a_film_uses_the_same_template(self) -> None:
        """電影與劇集的資料夾名是同一個模板，差別只在檔名（brief §7.1、§7.2）。"""
        card = snapshot(
            tmdb_id=1241982,
            kind=MediaKind.MOVIE,
            title="海洋奇緣2",
            title_en="Moana 2",
            title_original="Moana 2",
            year=2024,
        )

        assert folder_name(card) == "Moana 2 (2024) [tmdbid-1241982]"


class TestSanitize:
    """plan §5 的 `sanitize`。

    六種模板共用它。`folder_name` 還會被凍結進資料庫（票 09），所以
    `Mission: Impossible` 這種標題一旦被寫成非法路徑就改不掉了。
    """

    def test_it_removes_the_characters_windows_refuses(self) -> None:
        assert sanitize(r'a/b\c:d*e?f"g<h>i|j') == "abcdefghij"

    def test_a_real_title_with_a_colon_survives(self) -> None:
        """`Mission: Impossible` 是這條規則存在的理由。"""
        card = snapshot(tmdb_id=575265, title_en="Mission: Impossible - The Final Reckoning")

        assert folder_name(card) == (
            "Mission Impossible - The Final Reckoning (2022) [tmdbid-575265]"
        )

    def test_it_drops_control_characters(self) -> None:
        assert sanitize("a\u0000b\tc\nd") == "a b c d"

    def test_it_collapses_runs_of_whitespace(self) -> None:
        assert sanitize("a   b \t c") == "a b c"

    def test_it_strips_trailing_dots_and_spaces(self) -> None:
        """Windows 的目錄名不能以 `.` 或空白結尾——建得起來也開不了。"""
        assert sanitize("Dr. Strangelove. . ") == "Dr. Strangelove"

    def test_it_keeps_the_name_within_two_hundred_bytes(self) -> None:
        """上限算的是 UTF-8 **位元組**，不是字元：中文一個字三個位元組。"""
        long_name = sanitize("間諜家家酒" * 40)

        assert len(long_name.encode("utf-8")) <= 200
        # 不從一個字的中間切開——切出半個位元組的話那不是一個字串。
        assert long_name == long_name.encode("utf-8").decode("utf-8")

    def test_it_does_not_cut_a_name_that_already_fits(self) -> None:
        assert sanitize("SPY x FAMILY (2022) [tmdbid-120089]") == (
            "SPY x FAMILY (2022) [tmdbid-120089]"
        )

    def test_a_title_that_already_carries_its_year_does_not_repeat_it(self) -> None:
        """TMDB 上真的有這種標題（`GTO (2026)`，語料 `tv/gto-2026-magicstar`）。
        照字面套模板會變成 `GTO (2026) (2026)`。
        """
        remake = snapshot(tmdb_id=325022, title_en="GTO (2026)", year=2026)

        assert folder_name(remake) == "GTO (2026) [tmdbid-325022]"

    def test_a_different_year_in_the_title_is_not_the_release_year(self) -> None:
        """`Blade Runner 2049` 那個數字不是年份；`(1999)` 版的重製才是這一條要擋的。"""
        older = snapshot(tmdb_id=1, title_en="Show (1999)", year=2020)

        assert folder_name(older) == "Show (1999) (2020) [tmdbid-1]"

    def test_a_name_that_sanitizes_to_nothing_is_still_identifiable(self) -> None:
        """全部是非法字元的標題不能變成空字串——空的資料夾名建不出目錄。"""
        card = snapshot(title_en="///", title_original="///")

        assert folder_name(card) == "(2022) [tmdbid-120089]".strip()


def spy_family() -> MediaSnapshot:
    """SPY×FAMILY 的一小塊快照。集名抄自 TMDB，不是編出來的。"""
    return snapshot(
        seasons=(
            SeasonSnapshot(
                season_number=1,
                name="Season 1",
                episode_count=25,
                episodes=(
                    EpisodeSnapshot(episode_number=1, name="Operation Strix"),
                    EpisodeSnapshot(episode_number=2, name="Secure a Wife"),
                    EpisodeSnapshot(episode_number=3, name="Episode 3"),
                    EpisodeSnapshot(episode_number=4, name=""),
                ),
            ),
        )
    )


ANIME_TAGS = Tags(
    source=Source.BD,
    resolution="1080p",
    subs=(Lang.CHT, Lang.JP),
    group="Sakurato",
)


class TestSeasonFolder:
    """`Season {season:02d}`（plan §5）。Jellyfin 不接受 `S01`（brief §20.1）。"""

    def test_it_is_always_two_digits(self) -> None:
        assert season_folder(1) == "Season 01"

    def test_specials_live_in_season_zero(self) -> None:
        """brief §7.1：Specials 放 `Season 00`，集號沿用 TMDB season 0。"""
        assert season_folder(0) == "Season 00"

    def test_a_long_running_show_keeps_going(self) -> None:
        assert season_folder(12) == "Season 12"


class TestEpisodeTarget:
    def test_it_follows_the_frozen_template(self) -> None:
        """`{title} ({year}) - S{s:02d}E{e:02d}[ - {episode_title}][ {tags}].{ext}`（plan §5）。

        作品資料夾帶 `[tmdbid-…]`，**集檔名不帶**（brief §7.1 的範例）。
        """
        assert episode_target(spy_family(), season=1, episode=1, tags=ANIME_TAGS, ext=".mkv") == (
            "SPY x FAMILY (2022) [tmdbid-120089]/Season 01/"
            "SPY x FAMILY (2022) - S01E01 - Operation Strix [BD][1080p][CHT+JP][Sakurato].mkv"
        )

    def test_a_multi_episode_file_carries_both_numbers(self) -> None:
        """`S01E01-E02`：Jellyfin 支援的單檔多集寫法（brief §6.6、§20.1）。"""
        target = episode_target(
            spy_family(), season=1, episode=1, episode_end=2, tags=ANIME_TAGS, ext=".mkv"
        )

        assert "S01E01-E02 - Operation Strix" in target

    def test_without_tags_the_name_ends_at_the_episode_title(self) -> None:
        target = episode_target(spy_family(), season=1, episode=2, tags=Tags(), ext=".mkv")

        assert target.endswith("SPY x FAMILY (2022) - S01E02 - Secure a Wife.mkv")

    def test_a_placeholder_episode_title_is_left_out(self) -> None:
        """TMDB 還沒有正式集名時回 `Episode 3`；那不是標題（brief §7.1）。"""
        target = episode_target(spy_family(), season=1, episode=3, tags=Tags(), ext=".mkv")

        assert target.endswith("SPY x FAMILY (2022) - S01E03.mkv")

    def test_an_empty_episode_title_is_left_out(self) -> None:
        target = episode_target(spy_family(), season=1, episode=4, tags=Tags(), ext=".mkv")

        assert target.endswith("SPY x FAMILY (2022) - S01E04.mkv")

    def test_a_very_long_episode_title_is_cut_at_eighty_characters(self) -> None:
        """plan §5 的上限。集名是給人看的，一整段劇情摘要當檔名沒有比較好認。"""
        wordy = snapshot(
            seasons=(
                SeasonSnapshot(
                    season_number=1,
                    episodes=(EpisodeSnapshot(episode_number=1, name="A" * 200),),
                ),
            )
        )

        name = episode_target(wordy, season=1, episode=1, tags=Tags(), ext=".mkv").split("/")[2]

        assert name == "SPY x FAMILY (2022) - S01E01 - " + "A" * 80 + ".mkv"

    def test_an_episode_tmdb_has_never_heard_of_still_gets_a_name(self) -> None:
        """快照裡沒有這一集也要產得出路徑——那個檔案還是要有地方去。"""
        target = episode_target(spy_family(), season=1, episode=9, tags=Tags(), ext=".mkv")

        assert target.endswith("SPY x FAMILY (2022) - S01E09.mkv")


def moana() -> MediaSnapshot:
    return snapshot(
        tmdb_id=1241982,
        kind=MediaKind.MOVIE,
        title="海洋奇緣2",
        title_en="Moana 2",
        title_original="Moana 2",
        year=2024,
        seasons=(),
    )


class TestMovieTarget:
    """brief §7.2 與 §20.6 的實測結論。這幾條是**已經被 Jellyfin 打過臉的**寫法。"""

    def test_the_name_before_the_dash_is_the_folder_name(self) -> None:
        """**含 `[tmdbid-…]`**。少了它 Jellyfin 就當成兩部獨立的電影，不是多版本
        （2026-09-07 實測，brief §7.2 原本的範例是錯的）。
        """
        target = movie_target(
            moana(),
            tags=Tags(source=Source.BD, resolution="2160p", subs=(Lang.CHT,), group="CMCT"),
            ext=".mkv",
        )

        assert target == (
            "Moana 2 (2024) [tmdbid-1241982]/"
            "Moana 2 (2024) [tmdbid-1241982] - [BD][2160p][CHT][CMCT].mkv"
        )

    def test_every_version_shares_the_prefix_with_the_folder(self) -> None:
        """同一部片的兩個版本只差 ` - ` 之後那一段——這是多版本唯一的條件。"""
        movie = moana()
        folder = folder_name(movie)
        versions = [
            movie_target(movie, tags=Tags(source=Source.BD, resolution="2160p"), ext=".mkv"),
            movie_target(movie, tags=Tags(source=Source.WEB, resolution="1080p"), ext=".mp4"),
        ]

        assert [target.split("/")[1].split(" - ")[0] for target in versions] == [folder, folder]

    def test_without_tags_the_file_is_named_after_the_folder(self) -> None:
        """沒有 tag 就沒有版本標籤，也就沒有那個 ` - `（plan §5）。"""
        target = movie_target(moana(), tags=Tags(), ext=".mkv")

        assert target == "Moana 2 (2024) [tmdbid-1241982]/Moana 2 (2024) [tmdbid-1241982].mkv"


EPISODE = (
    "SPY x FAMILY (2022) [tmdbid-120089]/Season 01/"
    "SPY x FAMILY (2022) - S01E01 - Operation Strix [BD][1080p][CHT+JP][Sakurato].mkv"
)


class TestSubtitleTarget:
    """`{影片檔名主幹}.{SUBTOKEN}.{lang}.{ext}`（plan §5、brief §6.7、§20.6 實測）。"""

    def test_it_sits_next_to_its_video(self) -> None:
        assert subtitle_target(EPISODE, langs=(Lang.CHT,), ext=".ass") == (
            "SPY x FAMILY (2022) [tmdbid-120089]/Season 01/"
            "SPY x FAMILY (2022) - S01E01 - Operation Strix [BD][1080p][CHT+JP][Sakurato]"
            ".CHT.zh.ass"
        )

    def test_simplified_chinese_differs_only_in_the_free_text_title(self) -> None:
        """Jellyfin 沒有分得出繁簡的語言碼，所以繁簡在標題欄位（brief §6.7、§20.1）。"""
        assert subtitle_target(EPISODE, langs=(Lang.CHS,), ext=".ass").endswith(".CHS.zh.ass")

    def test_it_never_writes_zh_hant(self) -> None:
        """`zh-Hant` 只有 10.11 認得，10.10 整個不認（2026-09-07 實測，brief §20.6）。"""
        for langs in ((Lang.CHT,), (Lang.CHS,), (Lang.CHT, Lang.CHS)):
            assert "zh-Hant" not in subtitle_target(EPISODE, langs=langs, ext=".ass")
            assert "zh-Hans" not in subtitle_target(EPISODE, langs=langs, ext=".ass")

    def test_japanese_and_english_only_need_a_language_code(self) -> None:
        """繁簡才需要自由文字欄位；`ja` 與 `en` 兩個版本都認得（brief §6.7）。"""
        assert subtitle_target(EPISODE, langs=(Lang.JP,), ext=".ass").endswith(".ja.ass")
        assert subtitle_target(EPISODE, langs=(Lang.EN,), ext=".srt").endswith(".en.srt")

    def test_a_bilingual_subtitle_keeps_both_tokens(self) -> None:
        """`JPTC` 是一個檔案裡兩種語言（brief §6.7 第 3 點）。語言碼取中文那一個。"""
        assert subtitle_target(EPISODE, langs=(Lang.JP, Lang.CHT), ext=".ass").endswith(
            ".CHT+JP.zh.ass"
        )

    def test_an_unknown_language_still_lands_next_to_the_video(self) -> None:
        """後綴、資料夾、檔名都沒說語言時不猜——沒有語言碼的側掛字幕仍然掛得上。"""
        assert subtitle_target(EPISODE, langs=(), ext=".ass") == EPISODE[: -len(".mkv")] + ".ass"


class TestExtrasTarget:
    """`{作品資料夾}/extras/{原檔名}`（plan §5、brief §7.3；2026-09-07 對兩個版本實測）。"""

    def test_it_keeps_the_original_file_name(self) -> None:
        assert extras_target(spy_family(), "[Sakurato] NCOP [1080P].mkv") == (
            "SPY x FAMILY (2022) [tmdbid-120089]/extras/[Sakurato] NCOP [1080P].mkv"
        )

    def test_the_original_name_is_still_sanitized(self) -> None:
        """來源檔名是別人取的。非法字元照樣不能寫進 library（brief §4.5）。"""
        assert extras_target(spy_family(), "PV: teaser?.mkv").endswith("/extras/PV teaser.mkv")


class TestLongNames:
    """上限（200 位元組）算在**每一段**上，不是整條路徑（plan §5、brief §4.5）。"""

    def test_a_long_episode_name_keeps_its_extension(self) -> None:
        """截斷不能吃掉副檔名——`.mk` 不是影片檔，Jellyfin 連掃都不會掃它。"""
        long_show = snapshot(title_en="Long " * 60, seasons=())

        name = episode_target(long_show, season=1, episode=1, tags=Tags(), ext=".mkv").split("/")[2]

        assert name.endswith(".mkv")
        assert len(name.encode("utf-8")) <= 200

    def test_a_long_chinese_extras_name_keeps_its_extension(self) -> None:
        name = extras_target(spy_family(), "特典映像" * 60 + ".mkv").split("/")[2]

        assert name.endswith(".mkv")
        assert len(name.encode("utf-8")) <= 200
        assert name == name.encode("utf-8").decode("utf-8")


class TestExtension:
    def test_it_lowercases(self) -> None:
        assert extension("A.MKV") == ".mkv"

    def test_a_name_without_a_dot_has_none(self) -> None:
        assert extension("README") == ""

    def test_a_long_episode_name_keeps_its_tags(self) -> None:
        """截斷從**集名**下手，不是從尾巴。

        tags 是「同一集的兩個版本」唯一的差別（brief §7.7）。從尾端截會把兩個版本截成
        同一個檔名，於是 `plan()` 判它們衝突、兩個都不入庫——本來該並存的兩個版本一個都進不去。
        """
        long_show = snapshot(title_en="Long " * 45, seasons=())
        tags = Tags(source=Source.BD, resolution="1080p", group="SweetSub")

        name = episode_target(long_show, season=1, episode=1, tags=tags, ext=".mkv").split("/")[2]

        assert name.endswith("[BD][1080p][SweetSub].mkv")
        assert len(name.encode("utf-8")) <= 200

    def test_two_versions_of_a_long_named_episode_stay_apart(self) -> None:
        long_show = snapshot(title_en="Long " * 45, seasons=())

        targets = {
            episode_target(
                long_show,
                season=1,
                episode=1,
                tags=Tags(source=Source.BD, resolution="1080p", group=group),
                ext=".mkv",
            )
            for group in ("SweetSub", "Kitauji")
        }

        assert len(targets) == 2

    def test_a_long_movie_name_still_starts_with_its_folder(self) -> None:
        """` - ` 之前少一個字，Jellyfin 就當成兩部片（brief §7.2、§20.6 實測）。

        資料夾名與檔名如果各自截在不同的位置，長標題的電影就會裂成兩部。
        """
        long_film = snapshot(
            tmdb_id=7, kind=MediaKind.MOVIE, title_en="Long " * 45, year=2024, seasons=()
        )

        target = movie_target(long_film, tags=Tags(source=Source.BD), ext=".mkv")

        assert target.split("/")[1].startswith(folder_name(long_film))

    def test_a_sidecar_keeps_the_whole_video_stem(self) -> None:
        """字幕靠**完整的主幹**與影片配對，所以它不能為了上限被截短（brief §20.1）。

        代價是側掛字幕最多會比上限多出一個語言段（`.CHS+CHT+JP+EN.zh` = 22 位元組），
        仍然遠低於 ext4 的 255。截短會讓 Jellyfin 認不出它屬於哪一個影片，那才是壞掉。
        """
        long_show = snapshot(title_en="Long " * 60, seasons=())
        video = episode_target(long_show, season=1, episode=1, tags=Tags(), ext=".mkv")

        sidecar = subtitle_target(video, langs=(Lang.CHT, Lang.JP), ext=".ass")

        assert sidecar.startswith(video[: -len(".mkv")])
        assert len(sidecar.split("/")[2].encode("utf-8")) <= 255


class TestPunctuationInsideNames:
    """尾端的 `.` 只有在**後面沒有東西**時才是問題（plan §5、brief §4.5）。"""

    def test_an_episode_title_keeps_its_ellipsis(self) -> None:
        """`It Didn't Have to Be Magic...` 是 TMDB 的集名原文（語料
        `anime/frieren-7acg-bd-batch`）。去掉那三個點是把集名改掉。
        """
        wordy = snapshot(
            seasons=(
                SeasonSnapshot(
                    season_number=1,
                    episodes=(EpisodeSnapshot(episode_number=2, name="It Didn't Have to Be..."),),
                ),
            )
        )

        target = episode_target(wordy, season=1, episode=2, tags=Tags(), ext=".mkv")

        assert target.endswith("SPY x FAMILY (2022) - S01E02 - It Didn't Have to Be....mkv")

    def test_an_extras_file_keeps_the_dots_before_its_extension(self) -> None:
        """extras 照抄原檔名。`Trailer...mkv` 的結尾是 `v`，那不是 Windows 擋的形狀。"""
        assert extras_target(spy_family(), "Coming Soon....mkv").endswith(
            "/extras/Coming Soon....mkv"
        )

    def test_a_name_with_nothing_after_it_still_loses_its_trailing_dot(self) -> None:
        """資料夾名後面沒有副檔名。Windows 上以 `.` 結尾的目錄建得起來也開不了。"""
        assert sanitize("Dr. Strangelove.") == "Dr. Strangelove"


# --- 反解（M2 票 10） -----------------------------------------------------------------

#: 往返要走過的 Tags。每一格都有出現過，也有「只有發佈組」「只有版本名」「兩者都有」三種，
#: 因為 `render()` 對它們不是一對一的，讀法要選定正規的那一種（`read_target`）。
ROUND_TRIP_TAGS = (
    Tags(),
    Tags(resolution="1080p"),
    Tags(source=Source.BD, resolution="1080p", subs=(Lang.CHS, Lang.CHT), group="VCB-Studio"),
    Tags(source=Source.WEB, resolution="2160p", hardsub=True, group="ANi", version="v2"),
    Tags(subs=(Lang.JP,), group="Old", edition="2"),
    Tags(resolution="720p", version="v3", edition="Director's Cut"),
    Tags(source=Source.REMUX, subs=(Lang.CHT, Lang.JP, Lang.EN)),
)


def titled() -> MediaSnapshot:
    """集名在檔名中間，而且其中一集自己以方括號結尾——那一格最容易被當成 Tags。"""
    return snapshot(
        seasons=(
            SeasonSnapshot(
                season_number=1,
                episodes=(
                    EpisodeSnapshot(episode_number=1, name="Operation Strix"),
                    EpisodeSnapshot(episode_number=2, name="Secure a Wife [Part 1]"),
                    EpisodeSnapshot(episode_number=3, name="Episode 3"),
                ),
            ),
        )
    )


class TestReadingAPathBack:
    """`read_target` 是命名模板的反函式（plan §11.3 決定 9）：**同一份規則往返**。"""

    @pytest.mark.parametrize("tags", ROUND_TRIP_TAGS)
    @pytest.mark.parametrize(("episode", "end"), [(1, None), (2, None), (3, None), (1, 2)])
    def test_an_episode_reads_back_as_what_wrote_it(
        self, tags: Tags, episode: int, end: int | None
    ) -> None:
        media = titled()
        path = episode_target(
            media, season=1, episode=episode, episode_end=end, tags=tags, ext=".mkv"
        )

        reading = read_target(media, path, kind=FileKind.VIDEO)

        assert reading == Reading(
            PlanAction.IMPORT,
            season=1,
            episode_start=episode,
            episode_end=end,
            tags=tags,
        )
        assert reading is not None
        assert (
            episode_target(
                media,
                season=1,
                episode=episode,
                episode_end=reading.episode_end,
                tags=reading.tags,
                ext=".mkv",
            )
            == path
        )

    @pytest.mark.parametrize("tags", ROUND_TRIP_TAGS)
    def test_a_film_reads_back_as_what_wrote_it(self, tags: Tags) -> None:
        film = snapshot(tmdb_id=1241982, kind=MediaKind.MOVIE, title_en="Moana 2", year=2024)
        path = movie_target(film, tags=tags, ext=".mkv")

        assert read_target(film, path, kind=FileKind.VIDEO) == Reading(PlanAction.IMPORT, tags=tags)

    @pytest.mark.parametrize(
        "langs", [(), (Lang.CHT,), (Lang.CHS, Lang.CHT), (Lang.JP,), (Lang.EN,)]
    )
    def test_a_subtitle_reads_back_as_the_episode_it_follows(self, langs: tuple[Lang, ...]) -> None:
        media = titled()
        tags = Tags(resolution="1080p", group="Group")
        video = episode_target(media, season=1, episode=1, tags=tags, ext=".mkv")
        path = subtitle_target(video, langs=langs, ext=".ass")

        reading = read_target(media, path, kind=FileKind.SUBTITLE, siblings=[video, path])

        assert reading == Reading(
            PlanAction.SUBTITLE, season=1, episode_start=1, episode_end=None, tags=tags
        )

    def test_an_extra_reads_back_by_its_folder(self) -> None:
        media = titled()
        path = extras_target(media, "[Group] SPY×FAMILY NCOP [1080p].mkv")

        assert read_target(media, path, kind=FileKind.VIDEO) == Reading(PlanAction.EXTRA)


class TestWhatDoesNotReadBack:
    """讀不出來就是沒有：**一筆都不猜**（決定 9）。每一條都是差一點就像的那種。"""

    def test_a_file_someone_dropped_in_the_season_folder(self) -> None:
        media = titled()
        folder = episode_target(media, season=1, episode=1, tags=Tags(), ext=".mkv").rsplit("/", 1)[
            0
        ]

        assert (
            read_target(media, f"{folder}/[Other] Spy x Family - 01.mkv", kind=FileKind.VIDEO)
            is None
        )

    def test_another_works_folder(self) -> None:
        other = snapshot(tmdb_id=1, title_en="Other")
        path = episode_target(other, season=1, episode=1, tags=Tags(), ext=".mkv")

        assert read_target(titled(), path, kind=FileKind.VIDEO) is None

    def test_the_wrong_season_folder(self) -> None:
        media = titled()
        path = episode_target(media, season=1, episode=1, tags=Tags(), ext=".mkv")

        assert (
            read_target(media, path.replace("Season 01", "Season 02"), kind=FileKind.VIDEO) is None
        )

    def test_an_episode_title_that_is_not_the_one_in_the_snapshot(self) -> None:
        """TMDB 改過集名之後寫的那一條與現在的快照對不上：不猜是哪一集的哪一個版本。"""
        media = titled()
        path = episode_target(media, season=1, episode=1, tags=Tags(), ext=".mkv")

        assert (
            read_target(
                media, path.replace("Operation Strix", "Something Else"), kind=FileKind.VIDEO
            )
            is None
        )

    def test_more_tags_than_the_template_has_room_for(self) -> None:
        """三個沒有形狀的 token：發佈組、版本名之後沒有第三格。模板寫不出這一條。"""
        media = titled()
        path = episode_target(media, season=1, episode=3, tags=Tags(), ext=".mkv")

        assert (
            read_target(media, path.replace(".mkv", " [A][B][C].mkv"), kind=FileKind.VIDEO) is None
        )

    def test_a_subtitle_without_its_video(self) -> None:
        media = titled()
        video = episode_target(media, season=1, episode=1, tags=Tags(), ext=".mkv")
        path = subtitle_target(video, langs=(Lang.CHT,), ext=".ass")

        assert read_target(media, path, kind=FileKind.SUBTITLE, siblings=[path]) is None

    def test_a_font_is_never_a_target(self) -> None:
        media = titled()
        path = episode_target(media, season=1, episode=1, tags=Tags(), ext=".ttf")

        assert read_target(media, path, kind=FileKind.FONT) is None

    def test_a_film_whose_tags_the_template_would_write_differently(self) -> None:
        """`[CHT+CHS]` 讀得出兩種語言，但模板寫的是 `[CHS+CHT]`：重算對不上就不是 Berth 寫的。"""
        film = snapshot(tmdb_id=1241982, kind=MediaKind.MOVIE, title_en="Moana 2", year=2024)
        path = movie_target(film, tags=Tags(subs=(Lang.CHS, Lang.CHT)), ext=".mkv")

        assert read_target(film, path.replace("CHS+CHT", "CHT+CHS"), kind=FileKind.VIDEO) is None
