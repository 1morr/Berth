"""整包檔案 → Plan（plan §4.1 的 `plan` 階段、brief §6.5、§7.6）。

逐條規則各自在別的檔案裡釘住了，這裡問的是**處置**：同一個季集結果，什麼時候是
自動入庫、什麼時候是 Unmatched、什麼時候是 review。三者的下一步完全不同。
"""

from __future__ import annotations

from berth.domain import (
    Confidence,
    FileEntry,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    SeasonSnapshot,
)
from berth.parser import plan


def overlord() -> ParseContext:
    return ParseContext(
        media=MediaSnapshot(
            tmdb_id=64196,
            kind=MediaKind.TV,
            title="Overlord",
            title_en="Overlord",
            title_original="オーバーロード",
            titles=("Overlord", "不死者之王"),
            seasons=(
                SeasonSnapshot(season_number=0, name="Specials", episode_count=57),
                SeasonSnapshot(season_number=1, name="Overlord", episode_count=13),
                SeasonSnapshot(season_number=2, name="Overlord II", episode_count=13),
            ),
        )
    )


def entries(*paths: str) -> list[FileEntry]:
    return [FileEntry(rel_path=path, size=1_000_000_000) for path in paths]


TORRENT = "[DBD-Raws][不死者之王 第二季/Overlord Ⅱ][01-13TV全集+SP][1080P][BDRip][简繁外挂]"


class TestActions:
    def test_an_episode_is_imported(self) -> None:
        files = entries("[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert (item.action, item.season, item.episode_start) == (PlanAction.IMPORT, 2, 3)

    def test_a_special_with_its_own_numbering_is_unmatched(self) -> None:
        """對不到而且像正片 → Unmatched，等人工指派（brief §7.6）。"""
        files = entries("SP/[DBD-Raws][不死者之王 第二季][SP][01][1080P][BDRip][FLAC].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert item.action is PlanAction.UNMATCHED

    def test_an_unmatched_file_says_why(self) -> None:
        files = entries("SP/[DBD-Raws][不死者之王 第二季][SP][01][1080P][BDRip][FLAC].mkv")

        assert plan(TORRENT, files, overlord())[0].reasons

    def test_an_extra_never_reaches_the_mapping(self) -> None:
        files = entries("NCOP&NCED/[DBD-Raws][不死者之王 第二季][NCOP][1080P][BDRip].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert (item.action, item.season) == (PlanAction.EXTRA, None)

    def test_without_a_media_snapshot_everything_waits_for_a_human(self) -> None:
        """沒有可以對照的季集時，任何數字都只是檔名的複述。"""
        files = entries("[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv")

        item = plan(TORRENT, files)[0]

        assert (item.action, item.confidence) == (PlanAction.REVIEW, Confidence.LOW)

    def test_a_low_confidence_answer_is_still_written_down(self) -> None:
        """進 review 不代表沒有提案——畫面上要看得到「它猜的是第幾集」。"""
        files = entries("[DBD-Raws][不死者之王 第二季][99][1080P][BDRip][FLAC].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert (item.action, item.season, item.episode_start) == (PlanAction.REVIEW, 2, 99)


class TestEpisodeSpans:
    """多集檔與同起始集的單集（brief §7.8、§20.9，2026-09-15 使用者拍板）。"""

    def test_a_multi_episode_file_and_a_single_episode_both_wait_for_a_human(self) -> None:
        """Jellyfin 12 的分組鍵只有季號與集號，兩者會被併成一集、第 4 集消失。"""
        files = entries(
            "[DBD-Raws][不死者之王 第二季][03-04][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
        )

        items = plan(TORRENT, files, overlord())

        assert {item.action for item in items} == {PlanAction.REVIEW}
        assert {item.confidence for item in items} == {Confidence.LOW}

    def test_the_reason_says_what_would_happen_in_jellyfin(self) -> None:
        """理由不是「重複」，而是「後面那一集會從集列表上消失」（使用者拍板的要求）。"""
        files = entries(
            "[DBD-Raws][不死者之王 第二季][03-04][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
        )

        reasons = [reason for item in plan(TORRENT, files, overlord()) for reason in item.reasons]

        assert any("disappear from the season" in reason for reason in reasons)

    def test_the_target_path_is_kept_so_the_choice_is_visible(self) -> None:
        """兩個檔案各有各的路徑，都寫得出去——停下來只是因為該由人挑一份。"""
        files = entries(
            "[DBD-Raws][不死者之王 第二季][03-04][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
        )

        items = plan(TORRENT, files, overlord())

        assert all(item.target_path for item in items)
        assert len({item.target_path for item in items}) == 2

    def test_two_versions_of_one_episode_still_import_by_themselves(self) -> None:
        """同起始集**同結束集**是多版本並存，本來就該一起入庫（brief §7.7）。"""
        files = entries(
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "[Lilith-Raws] Overlord II - 03 [WebDL][720p][CHS].mkv",
        )

        items = plan(TORRENT, files, overlord())

        assert {item.action for item in items} == {PlanAction.IMPORT}

    def test_a_different_episode_is_not_dragged_in(self) -> None:
        files = entries(
            "[DBD-Raws][不死者之王 第二季][03-04][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][05][1080P][BDRip][FLAC].mkv",
        )

        by_episode = {item.episode_start: item.action for item in plan(TORRENT, files, overlord())}

        assert by_episode[5] is PlanAction.IMPORT


class TestTargets:
    """目標路徑（plan §5）。Plan 說得出「這個檔案會被放到哪裡」才審核得了。"""

    def test_an_imported_episode_lands_in_its_season_folder(self) -> None:
        files = entries("[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert item.target_path == (
            "Overlord [tmdbid-64196]/Season 02/Overlord - S02E03 [BD][1080p][CHS+CHT][DBD-Raws].mkv"
        )

    def test_an_extra_lands_in_the_extras_folder_under_its_own_name(self) -> None:
        files = entries("NCOP&NCED/[DBD-Raws][不死者之王 第二季][NCOP][1080P][BDRip].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert item.target_path == (
            "Overlord [tmdbid-64196]/extras/[DBD-Raws][不死者之王 第二季][NCOP][1080P][BDRip].mkv"
        )

    def test_a_file_that_is_not_going_anywhere_has_no_target(self) -> None:
        """Unmatched 留在 complete 原位（brief §7.4）。有目標路徑會讓人以為它入庫了。"""
        files = entries("SP/[DBD-Raws][不死者之王 第二季][SP][01][1080P][BDRip][FLAC].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert (item.action, item.target_path) == (PlanAction.UNMATCHED, "")

    def test_a_review_item_has_no_target_either(self) -> None:
        files = entries("[DBD-Raws][不死者之王 第二季][99][1080P][BDRip][FLAC].mkv")

        item = plan(TORRENT, files, overlord())[0]

        assert (item.action, item.target_path) == (PlanAction.REVIEW, "")


class TestSubtitles:
    """外掛字幕（brief §6.7）。字幕跟著影片走——影片去哪裡它就去哪裡。"""

    def test_a_sidecar_follows_its_video(self) -> None:
        files = entries(
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].tc.ass",
        )

        item = plan(TORRENT, files, overlord())[1]

        assert (item.action, item.season, item.episode_start) == (PlanAction.SUBTITLE, 2, 3)
        assert item.target_path == (
            "Overlord [tmdbid-64196]/Season 02/"
            "Overlord - S02E03 [BD][1080p][CHS+CHT][DBD-Raws].CHT.zh.ass"
        )

    def test_the_two_language_sidecars_do_not_collide(self) -> None:
        """简繁外掛是一集兩個字幕檔。繁簡在自由文字標題裡，所以檔名不同（brief §6.7）。"""
        files = entries(
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].tc.ass",
            "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].sc.ass",
        )

        targets = [item.target_path for item in plan(TORRENT, files, overlord())]

        assert targets[1].endswith(".CHT.zh.ass") and targets[2].endswith(".CHS.zh.ass")

    def test_a_sidecar_of_an_unmatched_video_is_unmatched_too(self) -> None:
        """影片沒有入庫，字幕就沒有地方掛（`anime/overlord-s2-dbd-raws` 的 `SP/`）。"""
        files = entries(
            "SP/[DBD-Raws][不死者之王 第二季][SP][01][1080P][BDRip][FLAC].mkv",
            "SP/[DBD-Raws][不死者之王 第二季][SP][01][1080P][BDRip][FLAC].tc.ass",
        )

        item = plan(TORRENT, files, overlord())[1]

        assert (item.action, item.target_path) == (PlanAction.UNMATCHED, "")

    def test_a_sidecar_with_no_video_is_unmatched(self) -> None:
        """brief §6.7 第 4 點。"""
        files = entries("[Other] Some Other Show - 03 [1080p].tc.ass")

        item = plan(TORRENT, files, overlord())[0]

        assert item.action is PlanAction.UNMATCHED


class TestConflicts:
    """brief §6.4 第 5 點。比的是**目標路徑**：會不會蓋掉對方，看的是檔名。"""

    def test_two_files_that_would_be_written_to_one_path_both_go_to_review(self) -> None:
        """誰對誰錯檔名裡沒有答案，而蓋掉是不可逆的，所以兩個都不自動入庫。"""
        files = entries(
            "CD1/[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "CD2/[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
        )

        items = plan(TORRENT, files, overlord())

        assert [item.action for item in items] == [PlanAction.REVIEW, PlanAction.REVIEW]
        assert all(item.target_path == "" for item in items)

    def test_it_says_which_path_they_are_fighting_over(self) -> None:
        files = entries(
            "CD1/[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "CD2/[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
        )

        assert any("S02E03" in reason for reason in plan(TORRENT, files, overlord())[0].reasons)

    def test_the_rest_of_the_torrent_is_untouched(self) -> None:
        files = entries(
            "CD1/[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "CD2/[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv",
            "[DBD-Raws][不死者之王 第二季][04][1080P][BDRip][FLAC].mkv",
        )

        assert plan(TORRENT, files, overlord())[2].action is PlanAction.IMPORT

    def test_two_extras_with_the_same_file_name_are_a_conflict_too(self) -> None:
        """extras 的檔名是原檔名，兩個資料夾各有一個 `menu.mkv` 就會撞在一起。"""
        files = entries("PV/menu.mkv", "menu/menu.mkv")

        items = plan(TORRENT, files, overlord())

        assert [item.action for item in items] == [PlanAction.REVIEW, PlanAction.REVIEW]


def oppenheimer() -> ParseContext:
    return ParseContext(
        media=MediaSnapshot(
            tmdb_id=872585,
            kind=MediaKind.MOVIE,
            title="奧本海默",
            title_en="Oppenheimer",
            title_original="Oppenheimer",
            year=2023,
        )
    )


class TestMovies:
    def test_a_movie_lands_beside_its_folder_name(self) -> None:
        """檔名在 ` - ` 之前與資料夾名一字不差，否則 Jellyfin 當成兩部片（brief §7.2）。"""
        files = entries("Oppenheimer.2023.1080p.BluRay.x264.AAC5.1-[YTS.MX].mp4")

        item = plan("Oppenheimer (2023) [1080p] [BluRay] [5.1]", files, oppenheimer())[0]

        assert item.target_path == (
            "Oppenheimer (2023) [tmdbid-872585]/"
            "Oppenheimer (2023) [tmdbid-872585] - [BD][1080p][YTS.MX].mp4"
        )
