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
