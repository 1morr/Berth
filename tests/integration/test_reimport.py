"""重新入庫：以一個 complete 目錄為 Import Source 再走一次 planning → importing
（brief §9.3、M2 票 10）。

M2 驗收第一條就在這裡：**刪掉 library 之後一鍵重建**。起點照舊是真的走完一輪入庫
（`test_deletion.imported`：五個硬鏈接真的在媒體庫裡、帳本五列、來源還在 complete），然後
把媒體庫整個刪掉，按一次重新入庫，讓規劃器與 importer 照常的一輪接手。

斷言貼著磁碟與帳本：檔案回到媒體庫而且與來源同一個 inode、帳本還是那五列（以來源冪等，
不是多長一份）、Jellyfin 被通知到每一條路徑。
"""

from __future__ import annotations

import copy
import shutil
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import EventType, IssueStatus, IssueType, JobRefusal, JobState, LedgerStatus
from berth.models import Issue, Job, JobFile, LedgerEntry, Media, Route
from berth.models.types import utcnow
from berth.services.events import EventHub
from berth.services.jobs import JobRejectedError, read_job
from berth.services.plan import sweep_plans
from berth.services.reconcile import reconcile_once
from berth.services.reimport import reimport_job
from berth.services.resolver import sweep_resolutions
from tests.integration.factories import FakeClientFactory
from tests.integration.test_deletion import LINKS, imported
from tests.integration.test_importer import ledger_of, run, same_file, state_of
from tests.integration.test_plan import NOW, events_of
from tests.integration.test_reconcile import issues_of
from tests.integration.test_reconcile_checks import SPY, features, open_of, scanned

pytestmark = pytest.mark.asyncio

ACTOR = "7"


def wipe_library(route: Route) -> None:
    """把這條 Route 底下的東西整個刪掉——使用者在 Jellyfin 或檔案總管裡刪了整個媒體庫。

    Route 的目標本身留著：那是 Jellyfin 媒體庫的路徑（brief §4.1），刪掉的是它底下的作品資料夾。
    """
    for child in Path(route.target_path).iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()


async def reimported(session: AsyncSession, factory: FakeClientFactory, job: Job) -> None:
    """按一次重新入庫，然後讓規劃器與 importer 照常的一輪接手。"""
    await reimport_job(session, job.hash, actor=ACTOR)
    await sweep_plans(session, factory, EventHub(), now=NOW)
    await run(session, factory)


class TestRebuildingADeletedLibrary:
    """M2 驗收第一條：刪掉 library 之後一鍵重建（brief §9.3）。"""

    async def test_every_file_is_back_as_a_hard_link_of_its_source(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory = await imported(session, roots)
        wipe_library(route)

        await reimported(session, factory, job)

        assert await state_of(session, job) is JobState.IMPORTED
        entries = await ledger_of(session)
        assert len(entries) == LINKS
        for entry in entries:
            assert same_file(Path(entry.source_abs_path), Path(entry.target_path))

    async def test_the_ledger_grows_back_as_the_same_rows(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """以來源相對路徑冪等：同一個來源還是同一列，不是刪了再長一份。"""
        job, route, factory = await imported(session, roots)
        before = {entry.source_rel_path: entry.id for entry in await ledger_of(session)}
        wipe_library(route)

        await reimported(session, factory, job)

        after = {entry.source_rel_path: entry.id for entry in await ledger_of(session)}
        assert after == before
        assert {entry.status for entry in await ledger_of(session)} == {LedgerStatus.OK}

    async def test_the_ledger_grows_back_after_it_was_cleared_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「承認刪除並清帳本」之後帳本一列都不剩，重新入庫把它長回來。"""
        job, route, factory = await imported(session, roots)
        wipe_library(route)
        for entry in await ledger_of(session):
            await session.delete(entry)
        await session.commit()

        await reimported(session, factory, job)

        entries = await ledger_of(session)
        assert len(entries) == LINKS
        assert {entry.job_hash for entry in entries} == {job.hash}

    async def test_jellyfin_is_told_about_every_path(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory = await imported(session, roots)
        wipe_library(route)
        factory.jellyfin_.notified.clear()

        await reimported(session, factory, job)

        assert sorted(factory.jellyfin_.notified) == sorted(
            entry.target_path for entry in await ledger_of(session)
        )

    async def test_jellyfin_finds_every_episode_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收的最後一段：Jellyfin 掃得到。鏈接是新的，所以上一次反查到的 item 不算數——
        每一集重新排進反查，Jellyfin 掃完之後帳本指著它現在的那一個。"""
        job, route, factory = await imported(session, roots)
        wipe_library(route)

        await reimported(session, factory, job)
        factory.jellyfin_.items_ = scanned(route, await features(session), tmdb_id=SPY)
        await sweep_resolutions(session, factory, now=utcnow() + timedelta(minutes=1))

        found = [entry.jellyfin_item_id for entry in await features(session)]
        assert len(found) == 3
        assert all(found)

    async def test_the_timeline_says_it_was_reimported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`retried` 是事件去重的界線：重算出來的 `plan_generated` 與第一次一字不差也要寫。"""
        job, route, factory = await imported(session, roots)
        wipe_library(route)

        await reimported(session, factory, job)

        types = [row.type for row in await events_of(session)]
        retried = types.index(EventType.RETRIED.value)
        assert EventType.PLAN_GENERATED.value in types[retried:]
        assert EventType.LINKED.value in types[retried:]


class TestWithoutTheTorrent:
    """Import Source 是 complete 裡的那個目錄，**不要求 torrent 仍存在**（brief §9.3）。"""

    async def test_it_goes_through_when_the_torrent_is_gone_from_the_client(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = ()
        await session.execute(
            update(Job).where(Job.hash == job.hash).values(state=JobState.CLIENT_REMOVED)
        )
        await session.commit()
        wipe_library(route)

        await reimported(session, factory, job)

        assert await state_of(session, job) is JobState.IMPORTED
        assert len(await ledger_of(session)) == LINKS

    async def test_the_files_are_read_from_the_folder_not_from_the_torrent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """資料夾裡少了一集就少規劃一集，多了一個就多一個——磁碟是事實，不是 qBittorrent 的清單。"""
        job, route, factory = await imported(session, roots)
        episode = next(Path(job.content_path).glob("*S01E03*.mkv"))
        episode.unlink()
        wipe_library(route)

        await reimported(session, factory, job)

        assert await state_of(session, job) is JobState.IMPORTED
        listed = set(
            await session.scalars(select(JobFile.rel_path).where(JobFile.job_hash == job.hash))
        )
        assert not any("S01E03" in path for path in listed)
        # 那一集的帳本列留著說它不在了（對帳的 `source_missing` 那一條路），其餘四條鏈接回來了。
        back = [entry for entry in await ledger_of(session) if Path(entry.target_path).exists()]
        assert len(back) == LINKS - 1
        assert not any("S01E03" in str(entry.target_path) for entry in back)


class TestRepeating:
    async def test_reimporting_twice_does_not_grow_a_second_ledger(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        before = [entry.id for entry in await ledger_of(session)]

        await reimported(session, factory, job)
        await reimported(session, factory, job)

        assert [entry.id for entry in await ledger_of(session)] == before

    async def test_a_new_name_moves_the_same_row_and_takes_the_old_link_away(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """TMDB 在兩次之間改了集名：目標路徑換了，帳本仍是同一列，舊的那條鏈接不留在媒體庫裡。

        以目標路徑冪等的話這裡會多長一列，而舊的那條會變成 Jellyfin 上同一集的第二個版本。
        """
        job, _, factory = await imported(session, roots)
        (first, *_) = [e for e in await ledger_of(session) if "S01E01" in e.target_path]
        old_target = Path(first.target_path)
        await _rename_episode(session, job, season=1, episode=1, name="A Brand New Title")

        await reimported(session, factory, job)

        await session.refresh(first)
        assert "A Brand New Title" in first.target_path
        assert same_file(Path(first.source_abs_path), Path(first.target_path))
        assert not old_target.exists()
        assert len(await ledger_of(session)) == LINKS


class TestTheIssuesItHeals:
    """重新入庫把鏈接接回來之後，說「這一條鏈接不見了」的那幾件 Issue 不再是事實，由系統收掉
    （`resolved_by = system`）。不收的話一鍵重建之後 `/issues` 還掛著十幾件按什麼都沒有結果的事。"""

    async def test_the_missing_link_issues_are_closed_once_the_links_are_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory = await imported(session, roots)
        wipe_library(route)
        await reconcile_once(session, factory, now=NOW)
        assert await open_of(session, IssueType.LIBRARY_LINK_MISSING) != []

        await reimported(session, factory, job)

        assert await open_of(session, IssueType.LIBRARY_LINK_MISSING) == []
        closed = [
            row for row in await issues_of(session) if row.type is IssueType.LIBRARY_LINK_MISSING
        ]
        assert {(row.status, row.resolved_by) for row in closed} == {
            (IssueStatus.RESOLVED, "system")
        }

    async def test_an_issue_on_the_old_name_is_closed_when_the_row_moves(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """TMDB 改了集名：那一列換到新路徑。舊路徑上那一件「鏈接遺失」說的仍是同一列
        （`ledger_id`），而那一列的鏈接已經接回來了。"""
        job, route, factory = await imported(session, roots)
        wipe_library(route)
        await reconcile_once(session, factory, now=NOW)
        await _rename_episode(session, job, season=1, episode=1, name="A Brand New Title")

        await reimported(session, factory, job)

        assert await open_of(session, IssueType.LIBRARY_LINK_MISSING) == []

    async def test_a_job_whose_ledger_grows_back_is_no_longer_without_files(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        await session.execute(delete(LedgerEntry))
        await session.commit()
        await reconcile_once(session, factory, now=NOW)
        assert await open_of(session, IssueType.JOB_WITHOUT_FILES) != []

        await reimported(session, factory, job)

        assert await open_of(session, IssueType.JOB_WITHOUT_FILES) == []

    async def test_an_issue_on_another_row_stays_open(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只收重新入庫真的接回來的那幾列：這一包以外的鏈接遺失照舊等人決定。"""
        job, route, factory = await imported(session, roots)
        wipe_library(route)
        await reconcile_once(session, factory, now=NOW)
        (kept, *_) = await open_of(session, IssueType.LIBRARY_LINK_MISSING)
        await session.execute(
            update(Issue).where(Issue.id == kept.id).values(ledger_id=10_000, subject="/elsewhere")
        )
        await session.commit()

        await reimported(session, factory, job)

        assert [row.id for row in await open_of(session, IssueType.LIBRARY_LINK_MISSING)] == [
            kept.id
        ]


class TestRefusals:
    async def test_a_job_still_downloading_cannot_be_reimported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, _ = await imported(session, roots)
        await session.execute(
            update(Job).where(Job.hash == job.hash).values(state=JobState.DOWNLOADING)
        )
        await session.commit()

        with pytest.raises(JobRejectedError) as refusal:
            await reimport_job(session, job.hash, actor=ACTOR)

        assert refusal.value.reason is JobRefusal.NOT_REIMPORTABLE
        assert await state_of(session, job) is JobState.DOWNLOADING

    async def test_a_download_removed_before_it_finished_cannot_be_reimported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """torrent 在下載到一半時被移出 qBittorrent：complete 裡那幾個檔案是殘件（稀疏檔、只寫了
        幾個 piece），不是 Import Source。按下去的話規劃器照樣算得出 Plan，殘件就被硬鏈進媒體庫。"""
        job, _, _ = await imported(session, roots)
        await session.execute(
            update(Job)
            .where(Job.hash == job.hash)
            .values(state=JobState.CLIENT_REMOVED, completed_at=None)
        )
        await session.commit()

        view = await read_job(session, job.hash)
        assert view is not None
        assert view.reimportable is False
        with pytest.raises(JobRejectedError) as refusal:
            await reimport_job(session, job.hash, actor=ACTOR)

        assert refusal.value.reason is JobRefusal.NOT_REIMPORTABLE
        assert await state_of(session, job) is JobState.CLIENT_REMOVED

    async def test_a_folder_that_is_gone_is_refused_before_anything_moves(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, _ = await imported(session, roots)
        shutil.rmtree(job.content_path)

        with pytest.raises(JobRejectedError) as refusal:
            await reimport_job(session, job.hash, actor=ACTOR)

        assert refusal.value.reason is JobRefusal.CONTENT_MISSING
        assert await state_of(session, job) is JobState.IMPORTED

    async def test_an_unknown_job_is_missing(self, session: AsyncSession) -> None:
        with pytest.raises(JobRejectedError) as refusal:
            await reimport_job(session, "0" * 40, actor=ACTOR)

        assert refusal.value.reason is JobRefusal.JOB_MISSING


async def _rename_episode(
    session: AsyncSession, job: Job, *, season: int, episode: int, name: str
) -> None:
    """TMDB 那邊改了一集的名字：快照裡那一集換名，而且快照是新的（規劃不會再去抓）。"""
    media = await session.get(Media, job.media_id)
    assert media is not None
    snapshot = copy.deepcopy(media.tmdb_snapshot_json or {})
    for known in snapshot["seasons"]:
        if known["season_number"] != season:
            continue
        for row in known["episodes"]:
            if row["episode_number"] == episode:
                row["name"] = name
    media.tmdb_snapshot_json = snapshot
    await session.commit()
