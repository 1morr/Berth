"""對帳的其餘六種檢查與 Jellyfin 那一方（brief §9.1、plan §3.2、M2 票 09）。

`test_reconcile.py` 釘的是**一輪的形狀**（四方先問完、問不到就跳過並說出來）；這一份逐種造出
那個破壞，斷言開出來的 Issue 的 `type` 與 `subject`，再連跑兩輪斷言只有一筆 `open`。

起點都是 importer 真的跑完的那一包（`test_deletion.imported`）：五個硬鏈接真的在媒體庫裡、
來源在 `complete/anime/<包名>/` 底下。破壞也是真的碰磁碟。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinItem, JellyfinSource
from berth.adapters.qbittorrent import BERTH_TAG, TorrentStatus
from berth.domain import (
    IssueStatus,
    IssueType,
    JellyfinPresence,
    JobState,
    LedgerStatus,
    PlanAction,
    ReconcileSide,
)
from berth.models import Issue, Job, LedgerEntry, Plan, PlanItem, Route
from berth.services.deletion import DeleteScope, delete_job
from berth.services.reconcile import reconcile_once
from tests.integration.factories import FakeClientFactory
from tests.integration.test_deletion import imported
from tests.integration.test_importer import ledger_of
from tests.integration.test_inventory import wall
from tests.integration.test_plan import NOW
from tests.integration.test_reconcile import issues_of, side

pytestmark = pytest.mark.asyncio

LATER = NOW + timedelta(days=1)
STRANGER = "0123456789abcdef0123456789abcdef01234567"


async def open_of(session: AsyncSession, kind: IssueType) -> list[Issue]:
    return [
        row
        for row in await issues_of(session)
        if row.type is kind and row.status is IssueStatus.OPEN
    ]


async def features(session: AsyncSession) -> list[LedgerEntry]:
    return [entry for entry in await ledger_of(session) if entry.action is PlanAction.IMPORT]


async def twice(session: AsyncSession, factory: FakeClientFactory) -> None:
    """同一個破壞連跑兩輪（acceptance：只有一筆 `open`）。"""
    await reconcile_once(session, factory, now=NOW)
    await reconcile_once(session, factory, now=LATER)


def torrent(
    route: Route, roots: dict[str, Path], name: str, *, info_hash: str = STRANGER
) -> TorrentStatus:
    """qBittorrent 上的一個 torrent，下載到那條 Route 的 complete 子目錄。"""
    save_path = str(roots["complete"] / route.slug)
    return TorrentStatus(
        hash=info_hash,
        name=name,
        state="stalledUP",
        category=route.category,
        tags=(BERTH_TAG,),
        progress=1.0,
        completion_on=int(NOW.timestamp()),
        last_activity=int(NOW.timestamp()),
        added_on=int(NOW.timestamp()),
        save_path=save_path,
        content_path=f"{save_path}/{name}",
        total_size=1,
    )


def stray_folder(roots: dict[str, Path], route: Route, name: str = "Someone Else") -> Path:
    """complete 的 Route 子目錄裡一個誰都不認得的目錄（qBittorrent 刪了 torrent、檔案留著）。"""
    folder = roots["complete"] / route.slug / name
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "a.mkv").write_bytes(b"stray")
    return folder


class TestSourceMissing:
    """帳本有、來源檔不在了，而媒體庫那一份還在（torrent 被移除且刪檔）。"""

    async def test_it_is_detected_by_the_target_path(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        entry = (await ledger_of(session))[0]
        Path(entry.source_abs_path).unlink()

        await reconcile_once(session, factory, now=NOW)

        (issue,) = await open_of(session, IssueType.SOURCE_MISSING)
        assert (issue.subject, issue.path, issue.ledger_id) == (
            entry.target_path,
            entry.target_path,
            entry.id,
        )
        assert (issue.detail_json or {})["source"] == entry.source_abs_path

    async def test_twice_is_still_one(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, _, factory = await imported(session, roots)
        Path((await ledger_of(session))[0].source_abs_path).unlink()

        await twice(session, factory)

        assert len(await open_of(session, IssueType.SOURCE_MISSING)) == 1

    async def test_a_missing_link_is_not_also_a_missing_source(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩邊都不在時只有一件：`library_link_missing` 的「重新鏈接」會說出來源也不在
        （brief §9.1 的「library 檔保留」說的是媒體庫那一份還在的情況）。"""
        _, _, factory = await imported(session, roots)
        entry = (await ledger_of(session))[0]
        Path(entry.source_abs_path).unlink()
        Path(entry.target_path).unlink()

        await reconcile_once(session, factory, now=NOW)

        assert [row.type for row in await issues_of(session)] == [IssueType.LIBRARY_LINK_MISSING]

    async def test_a_row_already_marked_sourceless_is_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """刪除範圍只勾了「刪 complete 檔案」之後就是這個樣子（票 04）：那是使用者的決定。"""
        _, _, factory = await imported(session, roots)
        entry = (await ledger_of(session))[0]
        Path(entry.source_abs_path).unlink()
        entry.status = LedgerStatus.SOURCE_MISSING
        await session.commit()

        await reconcile_once(session, factory, now=NOW)

        assert await issues_of(session) == []


class TestLinksTheUserRemoved:
    """刪除範圍只勾「移除鏈接」之後（M3 票 01）：同 `source_missing` 的先例，是使用者決定過的現況。

    帳本那幾列留著當歷史，說的是 `unlinked` 而不是對帳自己看到的 `target_missing`——
    兩者在磁碟上長得一樣（目標不在），差別只在「有沒有人決定過」。
    """

    async def test_the_rows_it_unlinked_open_no_missing_link(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        await delete_job(session, factory, job.hash, DeleteScope(unlink=True), actor="user")

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.LIBRARY_LINK_MISSING) == []
        assert {row.status for row in await ledger_of(session)} == {LedgerStatus.UNLINKED}

    async def test_a_link_deleted_by_hand_is_still_asked_about(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """對照組：沒有人透過 Berth 決定過的那一條照樣開。"""
        _, _, factory = await imported(session, roots)
        Path((await ledger_of(session))[0].target_path).unlink()

        await reconcile_once(session, factory, now=NOW)

        assert len(await open_of(session, IssueType.LIBRARY_LINK_MISSING)) == 1


class TestInodeMismatch:
    """目標與來源不是同一個 inode：有人用複製取代了硬鏈接，或它被轉碼覆蓋了。"""

    async def test_a_copy_in_place_of_the_link_is_detected(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        entry = (await features(session))[0]
        target = Path(entry.target_path)
        data = target.read_bytes()
        target.unlink()
        target.write_bytes(data)

        await reconcile_once(session, factory, now=NOW)

        (issue,) = await open_of(session, IssueType.INODE_MISMATCH)
        assert (issue.subject, issue.ledger_id) == (entry.target_path, entry.id)
        assert (issue.detail_json or {})["same_size"] is True
        await session.refresh(entry)
        assert entry.status is LedgerStatus.INODE_MISMATCH

    async def test_a_transcoded_file_says_the_sizes_differ(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        entry = (await features(session))[0]
        target = Path(entry.target_path)
        target.unlink()
        target.write_bytes(b"re-encoded and a lot smaller")

        await reconcile_once(session, factory, now=NOW)

        (issue,) = await open_of(session, IssueType.INODE_MISMATCH)
        assert (issue.detail_json or {})["same_size"] is False

    async def test_twice_is_still_one(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, _, factory = await imported(session, roots)
        target = Path((await features(session))[0].target_path)
        data = target.read_bytes()
        target.unlink()
        target.write_bytes(data)

        await twice(session, factory)

        assert len(await open_of(session, IssueType.INODE_MISMATCH)) == 1


class TestOrphanComplete:
    """complete 裡一個目錄既不屬於 qBittorrent 任何 torrent，也不在帳本上。"""

    async def test_a_folder_nobody_claims_is_detected(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        folder = stray_folder(roots, route)

        await reconcile_once(session, factory, now=NOW)

        (issue,) = await open_of(session, IssueType.ORPHAN_COMPLETE)
        assert Path(issue.subject) == folder
        assert issue.path == issue.subject

    async def test_twice_is_still_one(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, route, factory = await imported(session, roots)
        stray_folder(roots, route)

        await twice(session, factory)

        assert len(await open_of(session, IssueType.ORPHAN_COMPLETE)) == 1

    async def test_a_folder_a_torrent_still_holds_is_not_an_orphan(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """qBittorrent 上任何一個 torrent 的內容都不是孤兒——不只是掛著 Berth 記號的那些。"""
        _, route, factory = await imported(session, roots)
        stray_folder(roots, route, "Seeding Elsewhere")
        factory.qbittorrent_.torrents = (
            replace(torrent(route, roots, "Seeding Elsewhere"), category="", tags=()),
        )

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.ORPHAN_COMPLETE) == []

    async def test_the_folder_of_a_job_is_not_an_orphan(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """torrent 已經不在客戶端、帳本也被清掉了，但 Berth 還有那一筆 Job：它是 `reimport`
        的材料（brief §9.3），不是沒人認領的東西。"""
        _, _, factory = await imported(session, roots)
        await session.execute(delete(LedgerEntry))
        await session.commit()

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.ORPHAN_COMPLETE) == []

    async def test_a_probe_left_by_a_route_check_is_not_an_orphan(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Route 的硬鏈接檢查在這一層放探測檔（`fs.probe_file`），對帳剛好撞上的那一刻不算。"""
        _, route, factory = await imported(session, roots)
        (roots["complete"] / route.slug / f"{fs.PROBE_PREFIX}1234").write_bytes(b"berth")

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.ORPHAN_COMPLETE) == []

    async def test_a_client_that_is_down_reports_no_orphans(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """問不到 qBittorrent 就不知道哪些目錄有主——那一刻每一個目錄看起來都是孤兒。"""
        _, route, factory = await imported(session, roots)
        stray_folder(roots, route)
        factory.qbittorrent_.sync_error = ServiceUnavailableError("connection refused")

        report = await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.ORPHAN_COMPLETE) == []
        assert side(report, ReconcileSide.CLIENT).unavailable != ""

    async def test_folders_outside_the_route_subfolders_are_not_looked_at(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """complete root 可能與 Sonarr 共用（brief §16.4）：別人的 category 子目錄不歸 Berth。"""
        _, _, factory = await imported(session, roots)
        (roots["complete"] / "sonarr" / "Some Show").mkdir(parents=True)

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.ORPHAN_COMPLETE) == []


class TestUnknownTorrent:
    """qBittorrent 上掛著 Berth 記號的 torrent 沒有 Job。今天 poller 也寫它，兩邊共用冪等鍵。"""

    async def test_it_is_detected_by_its_hash(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (torrent(route, roots, "Not Ours"),)

        await reconcile_once(session, factory, now=NOW)

        (issue,) = await open_of(session, IssueType.UNKNOWN_TORRENT)
        assert (issue.subject, issue.job_hash) == (STRANGER, STRANGER)
        assert (issue.detail_json or {})["name"] == "Not Ours"

    async def test_twice_is_still_one(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (torrent(route, roots, "Not Ours"),)

        await twice(session, factory)

        assert len(await open_of(session, IssueType.UNKNOWN_TORRENT)) == 1

    async def test_a_torrent_without_berth_marks_is_not_ours_to_report(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (
            replace(torrent(route, roots, "Somebody's"), category="movies", tags=()),
        )

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.UNKNOWN_TORRENT) == []

    async def test_a_torrent_with_a_job_is_not_unknown(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory = await imported(session, roots)
        factory.qbittorrent_.torrents = (torrent(route, roots, job.name, info_hash=job.hash),)

        await reconcile_once(session, factory, now=NOW)

        assert await issues_of(session) == []


class TestUnmanagedLibraryFile:
    """媒體庫裡有一個 Berth 不認得的檔案。**只列出，永不自動刪**（brief §9.1）。"""

    async def test_a_file_the_ledger_does_not_know_is_detected(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        stranger = Path(route.target_path) / "Hand Placed (2020)" / "Hand Placed (2020).mkv"
        stranger.parent.mkdir(parents=True)
        stranger.write_bytes(b"put here by hand")

        await reconcile_once(session, factory, now=NOW)

        (issue,) = await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)
        assert Path(issue.subject) == stranger
        assert issue.ledger_id is None
        assert stranger.exists()

    async def test_twice_is_still_one(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, route, factory = await imported(session, roots)
        (Path(route.target_path) / "stray.mkv").write_bytes(b"x")

        await twice(session, factory)

        assert len(await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)) == 1

    async def test_the_files_in_the_ledger_are_not_reported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """帳本的目標是容器裡的 POSIX 字串，走訪媒體庫拿到的是這台機器的 `Path`——比的時候
        要正規化，否則每一個入庫的檔案都會被當成不認得的。"""
        _, _, factory = await imported(session, roots)

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE) == []

    async def test_a_route_that_is_not_mounted_reports_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        (Path(route.target_path) / "stray.mkv").write_bytes(b"x")
        route.target_path = str(roots["library"] / "not-mounted")
        await session.commit()

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE) == []


class TestJobWithoutFiles:
    """Job 已經 `imported`，帳本上卻一列都沒有。"""

    async def test_it_is_detected_by_the_job_hash(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        await session.execute(delete(LedgerEntry))
        await session.commit()

        await reconcile_once(session, factory, now=NOW)

        (issue,) = await open_of(session, IssueType.JOB_WITHOUT_FILES)
        assert (issue.subject, issue.job_hash) == (job.hash, job.hash)

    async def test_twice_is_still_one(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, _, factory = await imported(session, roots)
        await session.execute(delete(LedgerEntry))
        await session.commit()

        await twice(session, factory)

        assert len(await open_of(session, IssueType.JOB_WITHOUT_FILES)) == 1

    async def test_a_job_whose_plan_had_nothing_to_link_is_fine(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """全是重複的那一包自動落地、一個檔案都不鏈（票 08）：空帳本就是它該有的樣子。"""
        job, _, factory = await imported(session, roots)
        await session.execute(delete(LedgerEntry))
        await session.commit()
        plan_id = await session.scalar(select(Plan.id).where(Plan.job_hash == job.hash))
        for item in await session.scalars(select(PlanItem).where(PlanItem.plan_id == plan_id)):
            item.action = PlanAction.SKIP
        await session.commit()

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.JOB_WITHOUT_FILES) == []

    async def test_a_job_that_is_not_imported_is_not_checked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        await session.execute(delete(LedgerEntry))
        stored = await session.get(Job, job.hash)
        assert stored is not None
        stored.state = JobState.REVIEW
        await session.commit()

        await reconcile_once(session, factory, now=NOW)

        assert await open_of(session, IssueType.JOB_WITHOUT_FILES) == []


# --- Jellyfin 那一方：重新反查 -----------------------------------------


async def resolved_before_ticket_13(session: AsyncSession) -> list[LedgerEntry]:
    """票 13 之前反查完的樣子：item id 有了，Series id 沒有（那一欄是票 13 才加的）。"""
    entries = await features(session)
    for entry in entries:
        entry.jellyfin_item_id = f"episode-{entry.episode_start}"
        entry.jellyfin_series_id = ""
        entry.resolve_after = None
    await session.commit()
    return entries


def scanned(route: Route, entries: list[LedgerEntry], *, tmdb_id: str = "") -> list[JellyfinItem]:
    """Jellyfin 掃完之後：作品資料夾是一個 Series，每一個正片一個 Episode。

    Series 的 `tmdb_id` 預設是空的：媒體庫牆只能靠帳本記著的 Series id 認出它（票 13）。
    """
    root = PurePosixPath(route.target_path)
    folder = root / PurePosixPath(entries[0].target_path).relative_to(root).parts[0]
    return [
        JellyfinItem(
            id="series-1", type="Series", name="SPY x FAMILY", path=str(folder), tmdb_id=tmdb_id
        ),
        *(
            JellyfinItem(
                id=f"episode-{entry.episode_start}",
                type="Episode",
                name=f"Episode {entry.episode_start}",
                path=entry.target_path,
                tmdb_id="",
                sources=(JellyfinSource(path=entry.target_path, name="1080p"),),
                series_id="series-1",
            )
            for entry in entries
        ),
    ]


class TestTheSeriesIdIsFilledIn:
    """票 13 之前反查完的劇集，卡片一直說「還在掃描」且不會自己更新。"""

    async def test_the_column_goes_from_empty_to_the_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        entries = await resolved_before_ticket_13(session)
        factory.jellyfin_.items_ = scanned(route, entries)

        await reconcile_once(session, factory, now=NOW)

        for entry in await features(session):
            assert entry.jellyfin_series_id == "series-1"

    async def test_the_card_stops_saying_it_is_still_scanning(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """畫面跟著變：媒體庫牆認得出這部作品，它不再是一張「還在掃描」的卡片。"""
        _, route, factory = await imported(session, roots)
        entries = await resolved_before_ticket_13(session)
        factory.jellyfin_.items_ = scanned(route, entries)
        titles = [item for item in factory.jellyfin_.items_ if item.type == "Series"]

        before = await wall(session, route.slug, titles)
        assert [card.presence for card in before.tracked] == [JellyfinPresence.SEARCHING]

        await reconcile_once(session, factory, now=NOW)

        after = await wall(session, route.slug, titles)
        assert [(card.jellyfin_item_id, card.presence) for card in after.tracked] == [
            ("series-1", JellyfinPresence.FOUND)
        ]


class TestAMergeMovesThePrimaryItem:
    """Jellyfin 12 把兩個版本併成一集之後，反查到的那一個可能不再是主條目（brief §20.9）。"""

    async def test_the_ledger_follows_the_item_that_now_holds_the_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        entries = await resolved_before_ticket_13(session)
        items = scanned(route, entries)
        first = entries[0]
        # 合併之後：原本的 `episode-1` 成了次要版本，一般查詢濾掉它（帶 `PrimaryVersionId`）；
        # 主條目是另一個 id，而帳本那個檔案只是它底下的第二個來源。
        merged = JellyfinItem(
            id="episode-1-primary",
            type="Episode",
            name="Episode 1",
            path=f"{first.target_path}.other.mkv",
            tmdb_id="",
            sources=(
                JellyfinSource(path=f"{first.target_path}.other.mkv", name="2160p"),
                JellyfinSource(path=first.target_path, name="1080p [CHT]"),
            ),
            series_id="series-1",
        )
        factory.jellyfin_.items_ = [
            item for item in items if item.id != f"episode-{first.episode_start}"
        ] + [merged]

        await reconcile_once(session, factory, now=NOW)

        await session.refresh(first)
        assert (first.jellyfin_item_id, first.jellyfin_version_name) == (
            "episode-1-primary",
            "1080p [CHT]",
        )

    async def test_an_item_jellyfin_no_longer_lists_is_left_as_it_was(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """找不到不是「不在了」：媒體庫那一方比的是檔案，這一方只把找得到的那幾條換新。"""
        _, _, factory = await imported(session, roots)
        await resolved_before_ticket_13(session)
        factory.jellyfin_.items_ = []

        await reconcile_once(session, factory, now=NOW)

        assert [entry.jellyfin_item_id for entry in await features(session)] == [
            "episode-1",
            "episode-2",
            "episode-3",
        ]


class TestWhenJellyfinCannotBeAsked:
    async def test_it_is_skipped_and_said_and_nothing_changes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        entries = await resolved_before_ticket_13(session)
        factory.jellyfin_.items_ = scanned(route, entries)
        factory.jellyfin_.error = ServiceUnavailableError("GET /Items: connection refused")

        report = await reconcile_once(session, factory, now=NOW)

        assert "connection refused" in side(report, ReconcileSide.JELLYFIN).unavailable
        assert {entry.jellyfin_series_id for entry in await features(session)} == {""}

    async def test_nothing_resolved_means_nothing_is_asked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)

        report = await reconcile_once(session, factory, now=NOW)

        assert factory.jellyfin_.item_queries == []
        assert side(report, ReconcileSide.JELLYFIN).counted == 0


class TestAFolderThatFailsHalfwayThrough:
    """`is_dir()` 說在、真的讀的那一刻讀不到（權限、掛載中途掉）：跳過並說出來，不讓整輪垮掉。"""

    async def test_a_route_subfolder_under_complete_makes_the_side_unavailable(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, route, factory = await imported(session, roots)
        stray_folder(roots, route)
        broken = roots["complete"] / route.slug
        iterdir = Path.iterdir

        def flaky(self: Path) -> Iterator[Path]:
            if self == broken:
                raise PermissionError(13, "Permission denied", str(self))
            return iterdir(self)

        monkeypatch.setattr(Path, "iterdir", flaky)

        report = await reconcile_once(session, factory, now=NOW)

        assert "Permission denied" in side(report, ReconcileSide.COMPLETE).unavailable
        assert await open_of(session, IssueType.ORPHAN_COMPLETE) == []

    async def test_a_library_folder_that_cannot_be_walked_skips_that_route(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """走不完的那一條不能讓它的帳本被比成「不見了」，也不能讓別的東西被報成不認得。"""
        _, route, factory = await imported(session, roots)
        await break_one(session)
        rglob = Path.rglob

        def flaky(self: Path, pattern: str) -> Iterator[Path]:
            if self == Path(route.target_path):
                raise PermissionError(13, "Permission denied", str(self))
            return rglob(self, pattern)

        monkeypatch.setattr(Path, "rglob", flaky)

        report = await reconcile_once(session, factory, now=NOW)

        (skipped,) = side(report, ReconcileSide.LIBRARY).skipped
        assert "Permission denied" in skipped
        assert await issues_of(session) == []


async def break_one(session: AsyncSession) -> None:
    Path((await ledger_of(session))[0].target_path).unlink()
