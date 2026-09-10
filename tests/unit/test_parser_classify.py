"""檔案分類（brief §6.2、plan §4.1）。

語料（`tests/fixtures/parser/`）已經逐檔釘住 20 個 torrent 的 `kind`，這裡補的是**語料涵蓋
不到的規則**：`sample` 的兩個條件（v0 的 20 筆真實 torrent 一個 sample 檔都沒有——現在的
發佈幾乎不再附 sample）、`disc` 的兩種結構，以及 `SPs/` 那條「有 SP 編號的不是 extra」。
"""

from __future__ import annotations

from berth.domain import FileEntry, FileKind
from berth.parser import classify

GIGABYTE = 1_000_000_000


def entries(*files: tuple[str, int]) -> tuple[FileEntry, ...]:
    return tuple(FileEntry(rel_path=path, size=size) for path, size in files)


def kinds(*files: tuple[str, int]) -> list[FileKind]:
    return [entry.kind for entry in classify(entries(*files))]


class TestByExtension:
    def test_it_reads_the_extension_table(self) -> None:
        assert kinds(
            ("Show - 01.mkv", GIGABYTE),
            ("Show - 01.ass", 40_000),
            ("Fonts/font.ttf", 200_000),
            ("CDs/01.flac", 30_000_000),
            ("poster.jpg", 50_000),
            ("Subs.zip", 900_000),
            ("release.nfo", 1_000),
        ) == [
            FileKind.VIDEO,
            FileKind.SUBTITLE,
            FileKind.FONT,
            FileKind.AUDIO,
            FileKind.IMAGE,
            FileKind.ARCHIVE,
            FileKind.OTHER,
        ]

    def test_the_extension_is_matched_case_insensitively(self) -> None:
        assert kinds(("Show - 01.MKV", GIGABYTE)) == [FileKind.VIDEO]

    def test_a_file_without_an_extension_is_other(self) -> None:
        """BitComet 的 `_____padding_file_0_____` 是真實語料裡會出現的東西。"""
        assert kinds(("_____padding_file_0_____", 16_000)) == [FileKind.OTHER]


class TestSample:
    """檔名含 sample **而且**遠小於同目錄最大的影片（brief §6.2）。兩個條件缺一不可。"""

    def test_a_small_file_named_sample_is_a_sample(self) -> None:
        assert kinds(
            ("Movie.2019.1080p.mkv", GIGABYTE),
            ("Sample/movie-sample.mkv", 20_000_000),
        ) == [FileKind.VIDEO, FileKind.SAMPLE]

    def test_a_sample_is_measured_against_the_biggest_video_in_the_torrent(self) -> None:
        """同目錄沒有別的影片時比的是整包最大的那一個——sample 通常自己一個資料夾。"""
        assert kinds(
            ("Movie.2019.1080p.mkv", GIGABYTE),
            ("Sample/sample.mkv", int(GIGABYTE * 0.09)),
        ) == [FileKind.VIDEO, FileKind.SAMPLE]

    def test_a_big_file_named_sample_is_not_a_sample(self) -> None:
        """`Sample Man (2019).mkv` 是一部片，不是預覽片段。"""
        assert kinds(
            ("Show - 01.mkv", GIGABYTE),
            ("Show - 02 sample.mkv", GIGABYTE),
        ) == [FileKind.VIDEO, FileKind.VIDEO]

    def test_ten_percent_is_the_line(self) -> None:
        assert kinds(
            ("Show - 01.mkv", 1000),
            ("sample.mkv", 100),
        ) == [FileKind.VIDEO, FileKind.VIDEO]
        assert kinds(
            ("Show - 01.mkv", 1000),
            ("sample.mkv", 99),
        ) == [FileKind.VIDEO, FileKind.SAMPLE]

    def test_sample_inside_a_word_does_not_count(self) -> None:
        assert kinds(
            ("Show - 01.mkv", GIGABYTE),
            ("Resampled - 02.mkv", 1_000),
        ) == [FileKind.VIDEO, FileKind.VIDEO]

    def test_a_lone_video_is_never_a_sample(self) -> None:
        """只有它自己時沒有東西可以說它「小」。"""
        assert kinds(("sample.mkv", 1_000)) == [FileKind.VIDEO]


class TestDisc:
    """`BDMV/`、`VIDEO_TS/` 結構 → 整包 disc（brief §6.2）。"""

    def test_a_bdmv_tree_makes_the_whole_torrent_a_disc(self) -> None:
        """`CERTIFICATE/` 沒有 `BDMV` 這個字，但它是同一張碟的另一半。"""
        assert kinds(
            ("BDMV/STREAM/00000.m2ts", 20 * GIGABYTE),
            ("BDMV/index.bdmv", 180),
            ("CERTIFICATE/id.bdmv", 100),
        ) == [FileKind.DISC, FileKind.DISC, FileKind.DISC]

    def test_video_ts_counts_too(self) -> None:
        assert kinds(("VIDEO_TS/VTS_01_1.VOB", GIGABYTE)) == [FileKind.DISC]

    def test_a_plain_release_is_not_a_disc(self) -> None:
        assert kinds(("Movie.2019.1080p.BluRay.mkv", GIGABYTE)) == [FileKind.VIDEO]


class TestExtra:
    """brief §6.2 的關鍵字與資料夾。"""

    def test_the_keywords(self) -> None:
        assert (
            kinds(
                ("[Group] Show - NCOP [1080p].mkv", 80_000_000),
                ("[Group] Show - NCED [1080p].mkv", 80_000_000),
                ("Show PV 01.mkv", 20_000_000),
                ("Show CM 01.mkv", 5_000_000),
                ("Theatrical Trailer.mkv", 40_000_000),
                ("The Making of Show.mkv", 400_000_000),
                ("Menu Art.mkv", 8_000_000),
                ("Cast Interview.mkv", 90_000_000),
                ("映像特典 01.mkv", 30_000_000),
            )
            == [FileKind.EXTRA] * 9
        )

    def test_a_bare_opening_or_ending_counts(self) -> None:
        assert kinds(("Show - OP.mkv", 40_000_000), ("Show - ED.mkv", 40_000_000)) == [
            FileKind.EXTRA,
            FileKind.EXTRA,
        ]

    def test_the_folders(self) -> None:
        assert (
            kinds(
                ("Extras/whatever.mkv", 40_000_000),
                ("Bonus/whatever.mkv", 40_000_000),
                ("Featurettes/Lamb to Slaughter.mkv", 190_000_000),
                ("Behind the Scenes/b.mkv", 40_000_000),
                ("menu/01.mkv", 11_000_000),
            )
            == [FileKind.EXTRA] * 5
        )

    def test_an_sp_numbered_file_in_sps_is_not_an_extra(self) -> None:
        """`SPs/` 裡帶 SP 編號的可能對得到 TMDB season 0，所以它是特典本體（brief §6.2）。"""
        assert kinds(("SPs/[Group] Show [SP][01][1080p].mkv", 21_000_000)) == [FileKind.VIDEO]

    def test_an_unnumbered_file_in_sps_is_an_extra(self) -> None:
        assert kinds(("SPs/[Group] Show Creditless [1080p].mkv", 21_000_000)) == [FileKind.EXTRA]

    def test_only_video_files_become_extras(self) -> None:
        """`Extras/` 裡的字幕仍然是字幕——它要跟著某個影片走，不是自己入 extras。"""
        assert kinds(("Extras/trailer.ass", 4_000)) == [FileKind.SUBTITLE]

    def test_a_real_episode_is_not_an_extra(self) -> None:
        assert kinds(("[Group] Show - 01 [1080p][CHT].mkv", GIGABYTE)) == [FileKind.VIDEO]


class TestPurity:
    def test_it_does_not_mutate_the_input(self) -> None:
        given = entries(("Show - 01.mkv", GIGABYTE))

        classify(given)

        assert given[0].kind is FileKind.OTHER


class TestDuration:
    """時長 < 5 分鐘的「正片」降為 extra（plan §4.1、brief §6.2、票 11）。

    第一階段的分類器只看得到檔名與大小，所以一個 90 秒的預告只要沒寫 `PV` 就會被當成正片。
    下載完成之後 mediainfo 說得出它多長，而那句話比檔名可信。
    """

    def measured(self, name: str, size: int, duration: int | None) -> FileKind:
        entry = FileEntry(rel_path=name, size=size, duration_s=duration)
        return classify((entry,))[0].kind

    def test_a_short_video_becomes_an_extra(self) -> None:
        assert self.measured("[Group] Show - 01 [1080p].mkv", 90_000_000, 88) is FileKind.EXTRA

    def test_a_real_episode_stays_a_video(self) -> None:
        assert self.measured("[Group] Show - 01 [1080p].mkv", GIGABYTE, 1_421) is FileKind.VIDEO

    def test_an_unmeasured_file_is_left_alone(self) -> None:
        """**沒量到不是量到 0**：pre-plan 那一輪檔案還沒下載完，一個訊號都沒有。

        分不開的話，下載中的每一個檔案都會在預估的 Plan 裡變成 extra。
        """
        assert self.measured("[Group] Show - 01 [1080p].mkv", GIGABYTE, None) is FileKind.VIDEO

    def test_a_measurement_of_zero_is_not_a_reason_either(self) -> None:
        assert self.measured("[Group] Show - 01 [1080p].mkv", GIGABYTE, 0) is FileKind.VIDEO

    def test_it_does_not_promote_anything(self) -> None:
        """一條**單向**的規則：長度只降級，不會把 `Extras/` 裡的一小時特典拉回正片。"""
        assert self.measured("Extras/making-of.mkv", 900_000_000, 3_600) is FileKind.EXTRA
