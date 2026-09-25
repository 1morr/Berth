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
    ReasonCode,
    SeasonSnapshot,
    why,
)
from berth.parser import plan, promote, revise, written_episode


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

        # 後果那半句由畫面照 code 說（`web` 的 `span_clash` 句子），這裡釘的是 code。
        assert why(ReasonCode.SPAN_CLASH) in reasons

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

        contested = [
            reason
            for reason in plan(TORRENT, files, overlord())[0].reasons
            if reason.code is ReasonCode.TARGET_CONTESTED
        ]
        assert contested and "S02E03" in str(contested[0].params["target"])

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


VIDEO = "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].mkv"
SIDECAR = "[DBD-Raws][不死者之王 第二季][03][1080P][BDRip][FLAC].tc.ass"


class TestRevising:
    """人在 Review Queue 改過之後（M2 票 07）：路徑與字幕由同一份規則重算。"""

    def test_moving_a_video_moves_its_target_and_its_sidecar_follows(self) -> None:
        context = overlord()
        video, sidecar = plan(TORRENT, entries(VIDEO, SIDECAR), context)

        moved = video.model_copy(update={"season": 1, "episode_start": 5})
        revised = revise((moved, sidecar), context.media)

        assert revised[0].target_path == (
            "Overlord [tmdbid-64196]/Season 01/Overlord - S01E05 [BD][1080p][CHS+CHT][DBD-Raws].mkv"
        )
        assert revised[1].target_path == (
            "Overlord [tmdbid-64196]/Season 01/"
            "Overlord - S01E05 [BD][1080p][CHS+CHT][DBD-Raws].CHT.zh.ass"
        )

    def test_revising_an_untouched_plan_changes_nothing(self) -> None:
        """同一份規則：沒改過的 Plan 重算一次必須一字不差，否則畫面與 importer 會分岔。"""
        context = overlord()
        items = plan(TORRENT, entries(VIDEO, SIDECAR), context)

        assert revise(items, context.media) == items

    def test_a_settled_file_keeps_the_path_it_was_linked_at(self) -> None:
        """已經鏈接進去的那一列，路徑是磁碟上的事實（brief §7.1：不自動改名）。"""
        context = overlord()
        (video,) = plan(TORRENT, entries(VIDEO), context)
        linked = video.model_copy(update={"target_path": "somewhere/already.mkv"})

        (kept,) = revise((linked,), context.media, settled={VIDEO})

        assert kept.target_path == "somewhere/already.mkv"

    def test_skipping_a_video_skips_its_sidecar(self) -> None:
        """字幕留在 review 的話，一份人已經決定完的 Plan 會被它擋住。"""
        context = overlord()
        video, sidecar = plan(TORRENT, entries(VIDEO, SIDECAR), context)

        skipped = video.model_copy(update={"action": PlanAction.SKIP})
        revised = revise((skipped, sidecar), context.media)

        assert [item.action for item in revised] == [PlanAction.SKIP, PlanAction.SKIP]
        assert [item.target_path for item in revised] == ["", ""]

    def test_a_sidecar_someone_skipped_stays_skipped(self) -> None:
        context = overlord()
        video, sidecar = plan(TORRENT, entries(VIDEO, SIDECAR), context)
        dropped = sidecar.model_copy(update={"action": PlanAction.SKIP, "target_path": ""})

        revised = revise((video, dropped), context.media)

        assert (revised[1].action, revised[1].target_path) == (PlanAction.SKIP, "")


class TestPromoting:
    """核准＝照提案入庫（2026-09-23 使用者拍板）。"""

    def test_a_held_row_with_a_proposal_becomes_an_import(self) -> None:
        context = overlord()
        (video,) = plan(TORRENT, entries(VIDEO), context)
        held = video.model_copy(update={"action": PlanAction.REVIEW, "target_path": ""})

        (promoted,) = revise(promote((held,), context.media), context.media)

        assert promoted.action is PlanAction.IMPORT
        assert promoted.target_path == video.target_path

    def test_a_row_without_a_season_and_episode_stays_held(self) -> None:
        context = overlord()
        (video,) = plan(TORRENT, entries(VIDEO), context)
        held = video.model_copy(
            update={"action": PlanAction.REVIEW, "season": None, "episode_start": None}
        )

        assert promote((held,), context.media) == (held,)

    def test_a_disc_structure_is_never_promoted(self) -> None:
        """電影的路徑不需要季集，但光碟結構第一階段不拆（brief §6.2）。"""
        context = oppenheimer()
        (disc,) = plan("Oppenheimer.2023.BluRay", entries("BDMV/STREAM/00001.m2ts"), context)

        assert disc.action is PlanAction.REVIEW
        assert promote((disc,), context.media) == (disc,)


class TestWrittenEpisode:
    """改正一集時 offset 的基準（M3 票 13）：檔名寫的集號，Series 的 offset 加上去之前。"""

    def test_it_is_the_number_the_file_says(self) -> None:
        assert written_episode(TORRENT, "Overlord II/[DBD-Raws][Overlord II][05][1080P].mkv") == 5

    def test_it_reads_the_same_number_planning_would_shift(self) -> None:
        """與規劃同一個讀法：offset 加在這個數字上，重算時才落在人說的那一集。"""
        name = "[LoliHouse] Kimi ga Shinu made Koi wo Shitai - 11 [1080p].mkv"
        written = written_episode("", name)
        assert written == 11
        shifted = ParseContext(media=overlord().media, season_hint=2, episode_offset=13 - written)

        (item,) = plan("", entries(name), shifted)

        assert (item.season, item.episode_start) == (2, 13)

    def test_a_file_without_a_number_has_none(self) -> None:
        assert written_episode("", "Overlord Movie [1080P].mkv") is None
