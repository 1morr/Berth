"""帳本從磁碟上長回來：`berth rebuild-ledger` 與三顆「認領」
（plan §11.3 決定 9、brief §9.1、M2 票 10）。

起點照舊是**真的走完一輪入庫**（`test_deletion.imported`），然後把帳本或 Job 拿掉、讓磁碟上的
事實還在，再看它長不長得回來。斷言貼著帳本與磁碟，按完之後**再對帳一輪**：修好了，而不是被記成
resolved 而已。

兩條驗收在這裡釘：配得上的季、集、Tags 從目標路徑反解出來、與命名函式的輸出一致
（`TestRebuildingTheLedger`）；配不到的一筆都不猜（`TestWhatIsNeverGuessed`）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.domain import (
    ACTION_DELETES,
    ClaimMiss,
    IssueAction,
    IssueRefusal,
    IssueStatus,
    IssueType,
    JobState,
    JobTrigger,
    LedgerStatus,
    MediaSnapshot,
    PlanAction,
    Tags,
)
from berth.models import Issue, Job, LedgerEntry, Media, Route, TmdbSettings
from berth.naming import episode_target
from berth.services.claims import reimport_hash
from berth.services.deletion import DeleteScope, delete_job
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.issues import IssueRejectedError, list_issues, resolve_issue
from berth.services.ledger_rebuild import rebuild_ledger
from berth.services.plan import sweep_plans
from berth.services.reconcile import reconcile_once
from berth.services.reimport import reimport_job
from berth.services.settings import write_settings
from tests.conftest import TMDB_API_KEY
from tests.integration.factories import FakeClientFactory
from tests.integration.test_deletion import LINKS, imported
from tests.integration.test_importer import ledger_of, same_file, state_of
from tests.integration.test_issue_repairs import LATER
from tests.integration.test_media import SPY_ID, tmdb
from tests.integration.test_plan import NOW, downloaded_job
from tests.integration.test_reconcile import issues_of
from tests.integration.test_reconcile_checks import open_of, torrent
from tests.integration.test_reimport import wipe_library

pytestmark = pytest.mark.asyncio

#: 誰按的。`actor` 是 user id 的字串，而這幾個測試沒有登入的人（Job 的 `user_id` 是外鍵）。
ACTOR = "system"
UNKNOWN = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"

#: 帳本上一列說的每一件事，除了 id、時間與 Jellyfin 那幾格（重新反查會從頭來）。
Row = tuple[str, str | None, str, PlanAction, int | None, int | None, int | None, str]


def row_of(entry: LedgerEntry) -> Row:
    return (
        entry.target_path,
        entry.job_hash,
        entry.source_rel_path,
        entry.action,
        entry.season,
        entry.episode_start,
        entry.episode_end,
        json.dumps(entry.tags_json, sort_keys=True),
    )


async def forget_everything(session: AsyncSession) -> None:
    """帳本整個沒了（資料庫還原到舊備份、手動清掉），磁碟上的鏈接與來源都還在。"""
    await session.execute(delete(LedgerEntry))
    await session.commit()


async def nothing_left(session: AsyncSession, factory: FakeClientFactory) -> None:
    await reconcile_once(session, factory, now=LATER)
    assert [row.type for row in await issues_of(session) if row.status is IssueStatus.OPEN] == []


async def press(
    session: AsyncSession,
    factory: FakeClientFactory,
    issue: Issue,
    action: IssueAction,
    *,
    media: str = "",
) -> None:
    await resolve_issue(session, factory, issue.id, action, actor=ACTOR, media=media)


async def refused(
    session: AsyncSession,
    factory: FakeClientFactory,
    issue: Issue,
    action: IssueAction,
    *,
    media: str = "",
) -> IssueRejectedError:
    with pytest.raises(IssueRejectedError) as refusal:
        await press(session, factory, issue, action, media=media)
    await session.refresh(issue)
    assert issue.status is IssueStatus.OPEN
    return refusal.value


def hand_placed(route: Route, name: str, content: bytes = b"put here by hand") -> Path:
    path = Path(route.target_path) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# --- berth rebuild-ledger ---------------------------------------------------


class TestRebuildingTheLedger:
    """配得上的重建完整一列：季、集、Tags 從目標路徑反解，與命名函式的輸出一致。"""

    async def test_every_link_grows_back_as_the_row_the_importer_wrote(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        written = {row_of(entry) for entry in await ledger_of(session)}
        await forget_everything(session)

        report = await rebuild_ledger(session, factory, now=NOW)

        rebuilt = await ledger_of(session)
        assert report.claimed == LINKS
        assert {entry.status for entry in rebuilt} == {LedgerStatus.OK}
        # 正片那幾列一字不差（Tags 也是）；特典與字幕的路徑上沒有它們自己的 Tags，只比處置與季集。
        features = {row_of(entry) for entry in rebuilt if entry.action is PlanAction.IMPORT}
        assert features == {row for row in written if row[3] is PlanAction.IMPORT}
        assert {(row[0], row[3], row[4], row[5]) for row in map(row_of, rebuilt)} == {
            (row[0], row[3], row[4], row[5]) for row in written
        }

    async def test_what_it_read_is_what_the_naming_function_writes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同一份規則往返：讀回來的季、集、Tags 丟回命名函式，得到的就是那一條路徑。"""
        _, route, factory = await imported(session, roots)
        await forget_everything(session)

        await rebuild_ledger(session, factory, now=NOW)

        media = await session.get(Media, SPY_ID)
        assert media is not None
        snapshot = MediaSnapshot.model_validate(media.tmdb_snapshot_json)
        for entry in await ledger_of(session):
            if entry.action is not PlanAction.IMPORT:
                continue
            assert entry.season is not None and entry.episode_start is not None
            relative = PurePosixPath(entry.target_path).relative_to(route.target_path)
            assert (
                episode_target(
                    snapshot,
                    season=entry.season,
                    episode=entry.episode_start,
                    episode_end=entry.episode_end,
                    tags=Tags.model_validate(entry.tags_json),
                    ext=relative.suffix,
                )
                == relative.as_posix()
            )

    async def test_a_second_run_changes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        await forget_everything(session)
        await rebuild_ledger(session, factory, now=NOW)
        before = [(entry.id, row_of(entry)) for entry in await ledger_of(session)]

        report = await rebuild_ledger(session, factory, now=LATER)

        assert (report.claimed, report.known) == (0, LINKS)
        assert [(entry.id, row_of(entry)) for entry in await ledger_of(session)] == before

    async def test_the_next_reconcile_finds_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        await forget_everything(session)
        await reconcile_once(session, factory, now=NOW)
        assert len(await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)) == LINKS

        await rebuild_ledger(session, factory, now=NOW)

        # 長回帳本的那幾件 Issue 跟著收掉，而下一輪對帳不再開。
        assert await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE) == []
        await nothing_left(session, factory)

    async def test_a_source_whose_job_is_gone_is_measured_from_its_route_folder(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 與帳本一起清掉了（刪除範圍只勾「清除紀錄」）：長回來的那一列沒有 Job，
        來源路徑相對它那一條 Route 的 complete 子目錄——正是 qBittorrent 當時的 save path。"""
        job, _, factory = await imported(session, roots)
        written = {entry.target_path: entry.source_rel_path for entry in await ledger_of(session)}
        await delete_job(session, factory, job.hash, DeleteScope(purge=True), actor=ACTOR)

        await rebuild_ledger(session, factory, now=NOW)

        rebuilt = await ledger_of(session)
        assert {entry.job_hash for entry in rebuilt} == {None}
        assert {entry.target_path: entry.source_rel_path for entry in rebuilt} == written
        await nothing_left(session, factory)

    async def test_a_row_grown_back_without_a_job_is_not_its_own_duplicate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 清掉之後長回來的無 Job 列，在同一包再回到管線時（認領 torrent 之後 poller 走到
        下載完成）不能被當成「媒體庫裡已經有的另一個版本」：來源就是這一包自己的檔案。"""
        job, route, factory = await imported(session, roots)
        await delete_job(session, factory, job.hash, DeleteScope(purge=True), actor=ACTOR)
        await rebuild_ledger(session, factory, now=NOW)
        media = await session.get(Media, SPY_ID)
        assert media is not None
        again = await downloaded_job(session, media, route, roots)

        await sweep_plans(session, factory, EventHub(), now=NOW)
        await sweep_imports(session, factory, EventHub(), now=NOW)

        assert await state_of(session, again) is JobState.IMPORTED
        entries = await ledger_of(session)
        assert len(entries) == LINKS
        assert {entry.job_hash for entry in entries} == {again.hash}

    async def test_a_work_without_a_snapshot_is_fetched_before_reading(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """作品那一列在，但快照從沒抓到過（送單時 TMDB 沒接上）：先要一份，不是判成不知道。"""
        _, _, factory = await imported(session, roots)
        media = await session.get(Media, SPY_ID)
        assert media is not None
        media.tmdb_snapshot_json = None
        await session.commit()
        await forget_everything(session)
        await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
        await session.commit()
        factory.tmdb_ = tmdb()

        report = await rebuild_ledger(session, factory, now=NOW)

        assert report.unmatched.get(ClaimMiss.UNKNOWN_WORK, 0) == 0
        assert report.claimed > 0

    async def test_a_source_that_vanishes_mid_scan_is_skipped_not_fatal(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """complete 裡一個檔案在走訪之後、量 inode 之前不見了：那一個配不到，其餘照樣長回來，
        而不是整次中斷、前面長回來的全部作廢。"""
        _, _, factory = await imported(session, roots)
        await forget_everything(session)
        real = fs.stat

        def vanishing(path: Path) -> fs.PathFacts:
            if path.name == "readme.txt":
                raise FileNotFoundError(path)
            return real(path)

        monkeypatch.setattr(fs, "stat", vanishing)

        report = await rebuild_ledger(session, factory, now=NOW)

        assert report.claimed == LINKS

    async def test_an_unreadable_complete_lists_nothing_as_sourceless(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """complete 那一條子目錄讀不到（權限、掛載掉了）：問不到不算不見了（brief §16.2）。那一輪
        說不出媒體庫裡哪個檔案沒有來源，所以一件 `no_source` 都不開，並說出是哪一條沒讀到。"""
        _, _, factory = await imported(session, roots)
        await forget_everything(session)
        real = fs.files_under

        def unreadable(folder: Path) -> list[Path]:
            if folder.is_relative_to(roots["complete"]):
                raise PermissionError(folder)
            return real(folder)

        monkeypatch.setattr(fs, "files_under", unreadable)

        report = await rebuild_ledger(session, factory, now=NOW)

        assert await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE) == []
        assert report.unmatched == {}
        assert report.claimed == 0
        assert report.undecided == LINKS
        assert any(str(roots["complete"]) in line for line in report.unread_complete)
        assert await ledger_of(session) == []


class TestWhatIsNeverGuessed:
    """配不到的**一筆都不猜**：沒有帳本列，每一個都是一件 `unmanaged_library_file`，
    理由寫在上面。"""

    async def test_a_link_whose_name_does_not_read_back_writes_no_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """與來源同一個 inode（真的是硬鏈接），但名字不是命名模板寫得出來的那一條。"""
        _, _, factory = await imported(session, roots)
        (entry,) = [e for e in await ledger_of(session) if "S01E02" in e.target_path]
        renamed = Path(entry.target_path).with_name("Episode two, renamed by hand.mkv")
        Path(entry.target_path).replace(renamed)
        await forget_everything(session)

        report = await rebuild_ledger(session, factory, now=NOW)

        assert report.claimed == LINKS - 1
        assert not any(Path(row.target_path) == renamed for row in await ledger_of(session))
        (issue,) = await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)
        assert Path(issue.path) == renamed
        assert (issue.detail_json or {})["reason"] == ClaimMiss.NOT_BERTH_NAMING.value
        assert same_file(renamed, Path(entry.source_abs_path))

    async def test_a_copy_has_no_source_to_point_at(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        stranger = hand_placed(
            route, "Hand Placed (2020) [tmdbid-1]/Hand Placed (2020) [tmdbid-1].mkv"
        )

        report = await rebuild_ledger(session, factory, now=NOW)

        assert report.unmatched == {ClaimMiss.NO_SOURCE: 1}
        assert len(await ledger_of(session)) == LINKS
        (issue,) = await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)
        assert (Path(issue.path), (issue.detail_json or {})["reason"]) == (
            stranger,
            ClaimMiss.NO_SOURCE.value,
        )
        assert stranger.exists()

    async def test_a_folder_that_names_no_work(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """硬鏈接到一個真的來源，但作品資料夾沒有 `[tmdbid-…]`：不猜是哪一部。"""
        job, route, factory = await imported(session, roots)
        source = next(Path(job.content_path).glob("readme.txt"))
        target = Path(route.target_path) / "Some Show" / "readme.txt"
        target.parent.mkdir()
        os.link(source, target)

        report = await rebuild_ledger(session, factory, now=NOW)

        assert report.unmatched == {ClaimMiss.UNKNOWN_WORK: 1}
        assert len(await ledger_of(session)) == LINKS


# --- 三顆認領 ---------------------------------------------------------------


class TestClaimingOneFile:
    """`unmanaged_library_file` 的「認領進帳本」：單一檔案的 `rebuild-ledger`。"""

    async def test_it_grows_the_row_back_and_the_next_reconcile_is_quiet(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        (entry,) = [
            e
            for e in await ledger_of(session)
            if "S01E01" in e.target_path and e.action is PlanAction.IMPORT
        ]
        written = row_of(entry)
        await session.delete(entry)
        await session.commit()
        await reconcile_once(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)

        await press(session, factory, issue, IssueAction.CLAIM_FILE)

        assert written in {row_of(row) for row in await ledger_of(session)}
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        await nothing_left(session, factory)

    async def test_a_file_that_does_not_match_is_refused_and_stays_listed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """配不到的照舊只列出：拒絕、那一件開著、檔案一個位元組都不動。"""
        _, route, factory = await imported(session, roots)
        stranger = hand_placed(route, "stray.mkv")
        await reconcile_once(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)

        refusal = await refused(session, factory, issue, IssueAction.CLAIM_FILE)

        assert (refusal.reason, refusal.detail) == (
            IssueRefusal.UNCLAIMABLE,
            ClaimMiss.NO_SOURCE.value,
        )
        assert stranger.read_bytes() == b"put here by hand"
        assert len(await ledger_of(session)) == LINKS

    async def test_none_of_the_claims_deletes_anything(self) -> None:
        assert not any(
            ACTION_DELETES[action]
            for action in (IssueAction.ADOPT, IssueAction.CLAIM_TORRENT, IssueAction.CLAIM_FILE)
        )


async def orphaned(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Path, Route, FakeClientFactory, Issue]:
    """一包入庫過的東西只剩 complete 裡那個目錄：鏈接拆掉、Job 與帳本清掉（torrent 早就不在了）。"""
    job, route, factory = await imported(session, roots)
    folder = Path(job.content_path)
    await delete_job(session, factory, job.hash, DeleteScope(unlink=True, purge=True), actor=ACTOR)
    await reconcile_once(session, factory, now=NOW)
    (issue,) = await open_of(session, IssueType.ORPHAN_COMPLETE)
    assert Path(issue.path) == folder
    return folder, route, factory, issue


class TestAdoptingAnOrphanFolder:
    """`orphan_complete` 的「重新入庫」：以那個目錄為 Import Source 走目錄版 `reimport`。"""

    async def test_the_folder_is_imported_and_the_next_reconcile_is_quiet(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        folder, route, factory, issue = await orphaned(session, roots)
        assert not any(Path(route.target_path).iterdir())

        await press(session, factory, issue, IssueAction.ADOPT, media=SPY_ID)
        await sweep_plans(session, factory, EventHub(), now=NOW)
        await sweep_imports(session, factory, EventHub(), now=NOW)

        job = await session.get(Job, reimport_hash(folder))
        assert job is not None
        assert (job.state, job.trigger, job.trigger_ref) == (
            JobState.IMPORTED,
            JobTrigger.REIMPORT,
            str(folder),
        )
        entries = await ledger_of(session)
        assert len(entries) == LINKS
        for entry in entries:
            assert same_file(Path(entry.source_abs_path), Path(entry.target_path))
        await nothing_left(session, factory)

    async def test_pressing_it_again_is_the_same_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory, issue = await orphaned(session, roots)
        await press(session, factory, issue, IssueAction.ADOPT, media=SPY_ID)
        await reconcile_once(session, factory, now=LATER)

        # 那個目錄現在有主了（一筆 Job 指著它），所以不會再開一件同樣的事。
        assert await open_of(session, IssueType.ORPHAN_COMPLETE) == []
        assert len(list(await session.scalars(select(Job)))) == 1

    async def test_reimporting_the_adopted_folder_again_grows_no_second_ledger(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收：重複重新入庫同一個目錄不會產生第二份帳本列——認領來的那一筆也一樣。"""
        folder, route, factory, issue = await orphaned(session, roots)
        await press(session, factory, issue, IssueAction.ADOPT, media=SPY_ID)
        await sweep_plans(session, factory, EventHub(), now=NOW)
        await sweep_imports(session, factory, EventHub(), now=NOW)
        before = [row_of(entry) for entry in await ledger_of(session)]
        wipe_library(route)

        await reimport_job(session, reimport_hash(folder), actor=ACTOR)
        await sweep_plans(session, factory, EventHub(), now=NOW)
        await sweep_imports(session, factory, EventHub(), now=NOW)

        assert [row_of(entry) for entry in await ledger_of(session)] == before
        assert all(Path(entry.target_path).exists() for entry in await ledger_of(session))

    async def test_without_a_work_it_is_refused_before_anything_moves(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory, issue = await orphaned(session, roots)

        refusal = await refused(session, factory, issue, IssueAction.ADOPT)

        assert refusal.reason is IssueRefusal.MEDIA_REQUIRED
        assert list(await session.scalars(select(Job))) == []


class TestClaimingAnUnknownTorrent:
    """`unknown_torrent` 的「認領」：替 qBittorrent 上那一筆建 Job，交給 poller 與規劃器。"""

    async def test_it_gets_a_job_and_the_next_reconcile_is_quiet(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (torrent(route, roots, "Not Ours", info_hash=UNKNOWN),)
        await reconcile_once(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.UNKNOWN_TORRENT)

        await press(session, factory, issue, IssueAction.CLAIM_TORRENT, media=SPY_ID)

        job = await session.get(Job, UNKNOWN)
        assert job is not None
        # `submitted` 是送單成功之後那一站：接下來的每一步是 poller 照常的一輪（plan §3.1）。
        assert (job.state, job.media_id, job.route_id) == (JobState.SUBMITTED, SPY_ID, route.id)
        assert job.save_path == str(roots["complete"] / route.slug)
        await reconcile_once(session, factory, now=LATER)
        assert await open_of(session, IssueType.UNKNOWN_TORRENT) == []

    async def test_a_torrent_whose_category_is_no_route_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只掛著 `berth` tag、category 不是任何一條 Route 的：說不出要入庫到哪裡，不猜。"""
        from dataclasses import replace

        _, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (
            replace(torrent(route, roots, "Tagged Only", info_hash=UNKNOWN), category="other"),
        )
        await reconcile_once(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.UNKNOWN_TORRENT)

        refusal = await refused(session, factory, issue, IssueAction.CLAIM_TORRENT, media=SPY_ID)

        assert refusal.reason is IssueRefusal.ROUTE_UNUSABLE
        assert await session.get(Job, UNKNOWN) is None

    async def test_a_torrent_that_left_the_client_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (torrent(route, roots, "Not Ours", info_hash=UNKNOWN),)
        await reconcile_once(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.UNKNOWN_TORRENT)
        factory.qbittorrent_.torrents = ()

        refusal = await refused(session, factory, issue, IssueAction.CLAIM_TORRENT, media=SPY_ID)

        assert refusal.reason is IssueRefusal.ACTION_NOT_AVAILABLE


class TestWhereThePickerStarts:
    """選作品的搜尋框預填解析器從名字讀出的標題（`IssueView.query`）：Berth 不猜作品，但要管理員
    從頭打一次名字也不必。沒有選作品那兩顆的列是空字串。"""

    async def test_an_orphan_folder_starts_from_the_title_in_its_name(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        folder = roots["complete"] / route.slug / "[Old] SPY×FAMILY - 04 [1080P][CHT]"
        folder.mkdir(parents=True)
        (folder / "episode.mkv").write_bytes(b"left behind")
        await reconcile_once(session, factory, now=NOW)

        (view,) = [v for v in await list_issues(session) if v.type is IssueType.ORPHAN_COMPLETE]

        assert view.query == "SPY×FAMILY"

    async def test_an_unknown_torrent_starts_from_the_title_in_its_name(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (
            torrent(route, roots, "[Sub] SPY×FAMILY - 07 [1080P]", info_hash=UNKNOWN),
        )
        await reconcile_once(session, factory, now=NOW)

        (view,) = [v for v in await list_issues(session) if v.type is IssueType.UNKNOWN_TORRENT]

        assert view.query == "SPY×FAMILY"

    async def test_a_row_without_a_picker_has_none(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        hand_placed(route, "Hand Placed (2020)/Hand Placed (2020).mkv")
        await reconcile_once(session, factory, now=NOW)

        views = await list_issues(session)

        assert [v.type for v in views] == [IssueType.UNMANAGED_LIBRARY_FILE]
        assert views[0].query == ""
