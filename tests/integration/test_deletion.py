"""刪除範圍：四個旗標與空間估算（brief §9.2、plan §3.1 的 `delete_job`、M2 票 04）。

**這是產品第二個會刪掉使用者東西的地方**，而且它刪的是媒體庫與下載目錄裡真的檔案。所以
這一份的斷言貼著磁碟，不是貼著回傳值：每一條都去看那幾條路徑還在不在、inode 還是不是
同一個、qBittorrent 收到了什麼。

四個旗標各自只做它那一件事，所以測試也是逐個組合各驗一條（票上那一條驗收）：只移除鏈接 /
移除 torrent 不刪檔 / 刪檔（含 torrent）/ 全勾。四條共用同一個起點——一筆真的入庫完的
Job，五個硬鏈接真的在媒體庫裡。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceUnavailableError
from berth.db import create_session_factory
from berth.domain import EventType, JobRefusal, JobState, LedgerStatus
from berth.models import Event, Job, JobFile, LedgerEntry, Plan, Route
from berth.services.deletion import DeleteOutcome, DeleteScope, delete_job, estimate_deletion
from berth.services.jobs import JobRejectedError
from tests.integration.factories import FakeClientFactory
from tests.integration.test_importer import importing, ledger_of, run, state_of
from tests.integration.test_plan import HASH, events_of

pytestmark = pytest.mark.asyncio

#: 這一包裡真的被鏈接出去的五個（三集、一個 NCOP、一條字幕）。readme 是 skip，不入庫。
LINKS = 5

#: 這一包在 complete 底下的六個檔案。**比鏈接多一個**：沒人要的 readme 也是下載下來的東西，
#: 而「刪除 complete 檔案」刪的是這一包，不是入庫那幾個（brief §9.2）。
SOURCES = 6


async def imported(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Job, Route, FakeClientFactory]:
    """一筆走完入庫的 Job：五個硬鏈接真的在媒體庫裡，帳本五列，來源還在 complete。"""
    job, route, factory = await importing(session, roots)
    await run(session, factory)
    assert await state_of(session, job) is JobState.IMPORTED
    assert len(await ledger_of(session)) == LINKS
    return job, route, factory


async def targets(session: AsyncSession) -> list[Path]:
    return [Path(row.target_path) for row in await ledger_of(session)]


async def sources(session: AsyncSession) -> list[Path]:
    """這一包在 complete 底下的每一個檔案，包含沒有進 Plan 的那幾個。"""
    rows = await session.scalars(select(JobFile).where(JobFile.job_hash == HASH))
    return [fs.under(str(await _save_path(session)), row.rel_path) for row in rows]


async def _save_path(session: AsyncSession) -> str:
    job = await session.get(Job, HASH)
    assert job is not None
    return job.save_path


def alive(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


async def deleted_event(session: AsyncSession) -> Event:
    rows = [row for row in await events_of(session) if row.type == EventType.DELETED.value]
    assert len(rows) == 1, [row.type for row in await events_of(session)]
    return rows[0]


class TestTheCombinationThatIsRefused:
    """「刪除 complete 檔案」要求先移除 torrent，否則拒絕（brief §9.2）。

    **擋在後端不是擋在對話框**：qBittorrent 還握著那個 torrent 時把檔案抽走，它會報
    `missingFiles` 然後在下一次重新檢查時把整包再抓一遍——刪了等於沒刪。
    """

    async def test_deleting_files_without_removing_the_torrent_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)

        with pytest.raises(JobRejectedError) as refusal:
            await delete_job(
                session, factory, job.hash, DeleteScope(delete_files=True), actor="user"
            )

        assert refusal.value.reason is JobRefusal.DELETE_FILES_REQUIRES_REMOVE_TORRENT

    async def test_the_refusal_happens_before_anything_is_touched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """拒絕是「還沒開始就停住」：勾在一起的移除鏈接也不可以先做掉一半。"""
        job, _, factory = await imported(session, roots)

        with pytest.raises(JobRejectedError):
            await delete_job(
                session,
                factory,
                job.hash,
                DeleteScope(unlink=True, delete_files=True),
                actor="user",
            )

        assert len(alive(await targets(session))) == LINKS
        assert len(alive(await sources(session))) == SOURCES
        assert await state_of(session, job) is JobState.IMPORTED

    async def test_a_job_that_is_not_there_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)

        with pytest.raises(JobRejectedError) as refusal:
            await delete_job(session, factory, "nosuchhash", DeleteScope(), actor="user")

        assert refusal.value.reason is JobRefusal.JOB_MISSING


class TestEachFlagDoesOnlyItsOwnThing:
    async def test_unlink_removes_the_library_links_and_nothing_else(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        client = factory.qbittorrent_

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        assert alive(await targets(session)) == []
        assert len(alive(await sources(session))) == SOURCES
        assert client.deleted == []

    async def test_unlink_leaves_the_ledger_as_history_saying_it_was_unlinked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """帳本不跟著消失（brief §9.2：清除帳本是**另一個**旗標），但它說得出現況：是使用者
        拆掉的（`unlinked`），不是對帳自己看到的 `target_missing`（M3 票 01）。"""
        job, _, factory = await imported(session, roots)

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        rows = await ledger_of(session)
        assert len(rows) == LINKS
        assert {row.status for row in rows} == {LedgerStatus.UNLINKED}

    async def test_unlink_takes_the_folders_it_emptied_with_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """留著 `Show/Season 01/` 兩層空目錄的話，Jellyfin 的牆上那部作品還在。"""
        job, route, factory = await imported(session, roots)

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        assert Path(route.target_path).is_dir()
        assert list(Path(route.target_path).iterdir()) == []

    async def test_removing_the_torrent_keeps_every_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        client = factory.qbittorrent_

        await delete_job(session, factory, job.hash, DeleteScope(remove_torrent=True), actor="user")

        assert client.deleted == [(job.hash, False)]
        assert len(alive(await targets(session))) == LINKS
        assert len(alive(await sources(session))) == SOURCES

    async def test_deleting_files_removes_the_sources_and_leaves_the_library(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只有這一格是「刪來源」。媒體庫那五個檔案照樣看得了——硬鏈接的另一半還在。"""
        job, _, factory = await imported(session, roots)

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(remove_torrent=True, delete_files=True),
            actor="user",
        )

        assert alive(await sources(session)) == []
        assert len(alive(await targets(session))) == LINKS

    async def test_deleting_files_never_asks_qbittorrent_to_delete_them(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Berth 自己逐檔刪，所以它數得出刪了幾個、空出多少；qBittorrent 只收到「移除」。"""
        job, _, factory = await imported(session, roots)
        client = factory.qbittorrent_

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(remove_torrent=True, delete_files=True),
            actor="user",
        )

        assert client.deleted == [(job.hash, False)]

    async def test_deleting_files_marks_the_ledger_source_missing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(remove_torrent=True, delete_files=True),
            actor="user",
        )

        assert {row.status for row in await ledger_of(session)} == {LedgerStatus.SOURCE_MISSING}

    async def test_all_four_leave_nothing_behind(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        library, source = await targets(session), await sources(session)
        client = factory.qbittorrent_

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(unlink=True, remove_torrent=True, delete_files=True, purge=True),
            actor="user",
        )

        assert alive(library) == []
        assert alive(source) == []
        assert client.deleted == [(job.hash, False)]
        assert await session.get(Job, job.hash) is None

    async def test_none_of_them_checked_changes_nothing_but_the_state(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """四個預設全不勾（brief §9.2），所以「什麼都沒勾」是一條走得完的路：它把這一筆
        從清單上收掉，磁碟上一個檔案都不動。"""
        job, _, factory = await imported(session, roots)

        await delete_job(session, factory, job.hash, DeleteScope(), actor="user")

        assert len(alive(await targets(session))) == LINKS
        assert len(alive(await sources(session))) == SOURCES
        assert await state_of(session, job) is JobState.REMOVED


class TestPurge:
    async def test_purge_takes_the_ledger_the_events_and_the_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「清除帳本與 Job 紀錄（否則保留為歷史）」——歷史沒了，所以時間線也沒了。"""
        job, _, factory = await imported(session, roots)

        await delete_job(session, factory, job.hash, DeleteScope(purge=True), actor="user")

        assert await ledger_of(session) == []
        assert await events_of(session) == []
        assert await session.get(Job, job.hash) is None
        assert await session.scalar(select(Plan).where(Plan.job_hash == HASH)) is None

    async def test_without_purge_the_job_stays_as_history(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        assert await state_of(session, job) is JobState.REMOVED
        assert len(await ledger_of(session)) == LINKS


class TestTheTimelineSaysWhatWasDeleted:
    async def test_the_state_becomes_removed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        assert await state_of(session, job) is JobState.REMOVED

    async def test_the_event_counts_what_actually_happened(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(unlink=True, remove_torrent=True, delete_files=True),
            actor="user",
        )

        payload = (await deleted_event(session)).payload_json or {}
        assert payload["links"] == LINKS
        assert payload["sources"] == SOURCES
        assert payload["torrent"] is True
        assert payload["purged"] is False

    async def test_it_reports_what_happened_not_what_was_ticked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """勾了「移除鏈接」而那幾個檔案早就被人在 Jellyfin 裡刪掉了：時間線上是 0 個。"""
        job, _, factory = await imported(session, roots)
        for target in await targets(session):
            target.unlink()

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        assert ((await deleted_event(session)).payload_json or {})["links"] == 0

    async def test_the_freed_bytes_are_only_the_ones_really_given_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只移除鏈接時來源還在，那些位元組一個都沒回到檔案系統（brief §9.2）。"""
        job, _, factory = await imported(session, roots)

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        assert ((await deleted_event(session)).payload_json or {})["freed"] == 0

    async def test_the_same_file_under_two_spellings_is_still_one_name(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同一個檔案被兩條寫法不同的路徑指到時，它仍然只是**一個**名字。

        「會空出多少」問的是「要刪的名字數等於這份資料全部的名字數嗎」。重複的那一條若也
        算一格，只刪來源看起來就像連最後一個名字都刪掉了——時間線於是報出一個根本沒發生的
        釋放量，而媒體庫那一半明明還在。`Path` 收得掉分隔符的差異，收不掉 `..`。
        """
        job, _, factory = await imported(session, roots)
        entry = await session.scalar(select(LedgerEntry).order_by(LedgerEntry.id))
        assert entry is not None
        source = Path(entry.source_abs_path)
        entry.source_abs_path = str(source.parent / ".." / source.parent.name / source.name)
        await session.commit()
        # 那一條仍然指到同一個檔案，只是字串不同。
        assert Path(entry.source_abs_path).stat().st_ino == source.stat().st_ino
        # 大小要在刪掉之前量：那個檔案等一下就不在了。
        readme = _readme_size(roots)

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(remove_torrent=True, delete_files=True),
            actor="user",
        )

        # 媒體庫那五個鏈接一個都沒動，所以那五個檔案一個位元組都沒有回到磁碟；
        # 真的空出來的只有沒人鏈接過的 readme。
        assert len(alive(await targets(session))) == LINKS
        freed = ((await deleted_event(session)).payload_json or {})["freed"]
        assert freed == readme

    async def test_the_last_name_of_a_file_frees_its_bytes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        size = sum(path.stat().st_size for path in await sources(session))

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(unlink=True, remove_torrent=True, delete_files=True),
            actor="user",
        )

        assert ((await deleted_event(session)).payload_json or {})["freed"] == size


def _readme_size(roots: dict[str, Path]) -> int:
    """那一包裡唯一沒有被鏈接出去的檔案。它只有一個名字，所以刪掉它是真的釋放。"""
    readme = next(roots["complete"].rglob("readme.txt"))
    return readme.stat().st_size


class TestWhenQbittorrentCannotBeReached:
    async def test_it_refuses_before_deleting_anything(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """移除 torrent 做不到時整次刪除不做——否則檔案刪了而 torrent 還在做種，
        qBittorrent 下一次重新檢查就把整包再抓一遍。"""
        job, _, factory = await imported(session, roots)
        factory.qbittorrent_.error = ServiceUnavailableError("down")

        with pytest.raises(JobRejectedError) as refusal:
            await delete_job(
                session,
                factory,
                job.hash,
                DeleteScope(unlink=True, remove_torrent=True, delete_files=True),
                actor="user",
            )

        assert refusal.value.reason is JobRefusal.CLIENT_UNREACHABLE
        assert len(alive(await targets(session))) == LINKS
        assert len(alive(await sources(session))) == SOURCES
        assert await state_of(session, job) is JobState.IMPORTED


class TestTwoTabs:
    """兩個分頁同時刪同一筆（M3 票 01）。後拿到鎖的那一個讀到的是先到的那一個的結果：
    它按下去時看到的狀態已經不是現在的狀態，compare-and-set 輸了就是**失敗**——不是回報
    「刪好了、0 個鏈接」，也不是在時間線上多寫一筆 `deleted`。"""

    @pytest.mark.parametrize("purge", [False, True])
    async def test_the_second_one_is_refused(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        engine: AsyncEngine,
        purge: bool,
    ) -> None:
        job, _, factory = await imported(session, roots)
        sessions = create_session_factory(engine)
        scope = DeleteScope(unlink=True, purge=purge)

        async def press() -> DeleteOutcome:
            async with sessions() as own:
                return await delete_job(own, factory, job.hash, scope, actor="user")

        results = await asyncio.gather(press(), press(), return_exceptions=True)

        refused = [row for row in results if isinstance(row, BaseException)]
        assert len(refused) == 1, results
        assert isinstance(refused[0], JobRejectedError), results
        # 勾了清除紀錄的話先到的那一個連這一列都收走了，後到的那一個讀不到它。
        assert refused[0].reason is (JobRefusal.JOB_MISSING if purge else JobRefusal.MOVED_ON)
        assert len(alive(await targets(session))) == 0
        if not purge:
            await deleted_event(session)


class TestTheEstimate:
    """逐一 `stat` 每一個來源與目標，不用來源大小去猜（brief §9.2）。"""

    async def test_it_counts_both_sides(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, _ = await imported(session, roots)

        estimate = await estimate_deletion(session, job.hash)

        assert (estimate.links, estimate.sources) == (LINKS, SOURCES)
        assert estimate.links_missing == 0
        assert estimate.sources_missing == 0

    async def test_it_measures_the_files_instead_of_trusting_the_torrent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`job_files` 上那幾個大小是 qBittorrent 報的（1.4 GB 一集）；磁碟上這幾個是
        測試寫進去的幾十個位元組。估算說的是後者——那才是刪掉之後真的會空出來的。"""
        job, _, _ = await imported(session, roots)
        on_disk = sum(path.stat().st_size for path in await sources(session))

        estimate = await estimate_deletion(session, job.hash)

        assert estimate.source_bytes == on_disk
        assert estimate.reclaimable == on_disk

    async def test_a_file_something_else_also_holds_is_not_reclaimable(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Berth 不知道的第三個鏈接握著它時，刪掉來源與媒體庫那兩個名字也不會釋放。"""
        job, _, _ = await imported(session, roots)
        held = (await sources(session))[0]
        elsewhere = roots["complete"] / "kept-by-someone-else.mkv"
        fs.link(held, elsewhere, roots=[roots["complete"]])

        estimate = await estimate_deletion(session, job.hash)

        assert estimate.held == held.stat().st_size
        assert estimate.reclaimable == estimate.source_bytes - held.stat().st_size

    async def test_a_target_that_is_already_gone_is_counted_as_missing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, _ = await imported(session, roots)
        (await targets(session))[0].unlink()

        estimate = await estimate_deletion(session, job.hash)

        assert (estimate.links, estimate.links_missing) == (LINKS - 1, 1)

    async def test_a_job_that_is_not_there_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await imported(session, roots)

        with pytest.raises(JobRejectedError) as refusal:
            await estimate_deletion(session, "nosuchhash")

        assert refusal.value.reason is JobRefusal.JOB_MISSING


class TestPathsItWillNotTouch:
    async def test_a_ledger_row_pointing_outside_every_route_is_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """刪除與鏈接同一道守衛（plan §8.6）：帳本被改壞、指到媒體庫外面的那一條不刪，
        而同一次刪除裡其他四條照樣做完——一列壞掉不該讓整次刪除停住。"""
        job, _, factory = await imported(session, roots)
        outsider = roots["complete"] / "not-in-any-route.mkv"
        outsider.write_bytes(b"someone else's file")
        row = (await ledger_of(session))[0]
        row.target_path = str(outsider)
        await session.commit()

        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        assert outsider.exists()
        assert ((await deleted_event(session)).payload_json or {})["links"] == LINKS - 1

    async def test_a_source_outside_the_complete_root_is_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        outsider = roots["library"] / "not-a-download.mkv"
        outsider.write_bytes(b"someone else's file")
        row = await session.scalar(select(LedgerEntry).order_by(LedgerEntry.id))
        assert row is not None
        row.source_abs_path = str(outsider)
        await session.commit()

        await delete_job(
            session,
            factory,
            job.hash,
            DeleteScope(remove_torrent=True, delete_files=True),
            actor="user",
        )

        assert outsider.exists()
