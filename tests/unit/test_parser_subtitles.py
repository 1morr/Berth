"""外掛字幕附掛到影片（plan §4.1 的 `match_subtitle`、brief §6.7）。

字幕自己說不出它是第幾集——它只說得出「我跟哪一個影片是一對」。所以這一層問的是
**配對**，不是季集：配對成功就繼承那個影片的答案，配不到就是 Unmatched（brief §6.7 第 4 點）。
"""

from __future__ import annotations

from berth.domain import Confidence, FileEntry, FileKind, Lang, PlanAction, PlanItem
from berth.parser.subtitles import match_subtitle

VIDEO = "[DBD-Raws][不死者之王 第二季][01][1080P][BDRip][HEVC-10bit][FLAC].mkv"


def subtitle(path: str) -> FileEntry:
    return FileEntry(rel_path=path, size=40_000, kind=FileKind.SUBTITLE)


def video(rel_path: str = VIDEO, *, season: int = 2, episode: int = 1) -> PlanItem:
    return PlanItem(
        rel_path=rel_path,
        kind=FileKind.VIDEO,
        action=PlanAction.IMPORT,
        season=season,
        episode_start=episode,
        confidence=Confidence.HIGH,
    )


class TestStemMatch:
    """brief §6.7 第 1 點：去掉語言後綴後檔名主幹完全相同。"""

    def test_a_language_suffix_still_names_the_same_stem(self) -> None:
        found = match_subtitle(subtitle(VIDEO.replace(".mkv", ".tc.ass")), [video()])

        assert found is not None
        assert (found.video, found.langs) == (VIDEO, (Lang.CHT,))

    def test_the_simplified_sidecar_goes_to_the_same_video(self) -> None:
        found = match_subtitle(subtitle(VIDEO.replace(".mkv", ".sc.ass")), [video()])

        assert found is not None
        assert (found.video, found.langs) == (VIDEO, (Lang.CHS,))

    def test_an_iso_style_suffix_is_understood_too(self) -> None:
        """真實語料寫的是 `.Cht` / `.Chs` / `.Jpn` / `.Eng`（`tv/gto-2026-magicstar`）。"""
        name = "GTO.2026.EP08.1080p.NF.WEB-DL.AAC2.0.H.264-MagicStar"
        videos = [video(f"{name}.mkv", season=1, episode=8)]

        assert [
            match_subtitle(subtitle(f"{name}.{suffix}.srt"), videos).langs  # type: ignore[union-attr]
            for suffix in ("Cht", "Chs", "Jpn", "Eng")
        ] == [(Lang.CHT,), (Lang.CHS,), (Lang.JP,), (Lang.EN,)]

    def test_a_sidecar_without_a_suffix_matches_as_well(self) -> None:
        """`Squid.Game.S02E01.ENG.….srt` 與影片同名，語言寫在主幹裡
        （`tv/squid-game-s02-y2flix`）。
        """
        name = "Squid.Game.S02E01.ENG.1080p.NF.x264-[y2flix.cc]"
        found = match_subtitle(subtitle(f"{name}.srt"), [video(f"{name}.mp4", season=2, episode=1)])

        assert found is not None
        assert (found.video, found.langs) == (f"{name}.mp4", (Lang.EN,))

    def test_it_says_why(self) -> None:
        found = match_subtitle(subtitle(VIDEO.replace(".mkv", ".tc.ass")), [video()])

        assert found is not None and found.reasons


class TestEpisodeMatch:
    """brief §6.7 第 2 點：字幕資料夾裡的檔名含集號 → 以集號對應影片。"""

    def test_a_subtitle_folder_lets_the_episode_number_decide(self) -> None:
        found = match_subtitle(subtitle("Subs/[Group] Show - 01.ass"), [video()])

        assert found is not None and found.video == VIDEO

    def test_a_language_folder_counts_as_a_subtitle_folder(self) -> None:
        found = match_subtitle(subtitle("字幕/繁體/[Group] Show - 01.ass"), [video()])

        assert found is not None
        assert (found.video, found.langs) == (VIDEO, (Lang.CHT,))

    def test_a_loose_episode_number_is_not_enough(self) -> None:
        """沒有那個資料夾就只剩一個數字。一包裡任何帶數字的檔案都會對到某一集。"""
        assert match_subtitle(subtitle("[Group] Show - 01.ass"), [video()]) is None

    def test_two_versions_of_the_same_episode_leave_it_undecided(self) -> None:
        """同一集兩個版本時，這一份字幕是誰旁邊的那一個，路徑沒有說（brief §7.7）。"""
        versions = [video(), video("[Other] Overlord - 01 [720p].mkv")]

        assert match_subtitle(subtitle("Subs/[Group] Show - 01.ass"), versions) is None


class TestUnmatched:
    def test_a_subtitle_with_no_video_matches_nothing(self) -> None:
        """對不到影片的字幕 → Unmatched（brief §6.7 第 4 點）。"""
        assert match_subtitle(subtitle("[Group] Other Show - 03.tc.ass"), [video()]) is None

    def test_an_empty_torrent_matches_nothing(self) -> None:
        assert match_subtitle(subtitle("anything.ass"), []) is None
