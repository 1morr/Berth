"""Review Queue 與 audit 的兩顆按鈕（plan §6 review 群組、brief §6.5、M2 票 06）。

起點是**真的走完一次 medium 自動入庫**：規劃 → 入庫 → 帳本那一列掛著 `audit`。票上那兩條
驗收（確認之後從佇列消失、撤銷之後硬鏈接與帳本那一列都沒了、Job 回 `review`）要的就是這整條，
所以這裡不自己 `session.add(LedgerEntry(audit=True))` 造一列——造出來的那一列不會告訴你
importer 有沒有把旗標抄過去，也沒有一份 Plan 可以回去等人。

撤銷的斷言貼著磁碟（同 `test_deletion.py`）：「帳本那一列沒了」本身不算撤銷，媒體庫裡那個
檔案真的不在了才算。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.domain import (
    AuditAction,
    IssueStatus,
    IssueType,
    JobState,
    PlanStatus,
    PlanSummary,
    ReviewKind,
    ReviewReason,
    ReviewRefusal,
)
from berth.models import Job, LedgerEntry, PlanItem
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.issues import count_open, record_issue
from berth.services.plan import sweep_plans
from berth.services.review import (
    AuditRow,
    ReviewRejectedError,
    confirm_audit,
    confirm_audits,
    review_queue,
    undo_audit,
)
from tests.integration.test_importer import _put_on_disk, ledger_of, state_of
from tests.integration.test_plan import (
    NOW,
    SINGLE,
    SINGLE_FILES,
    downloaded_job,
    events_of,
    items_of,
    plan_of,
    ready,
)

pytestmark = pytest.mark.asyncio

ACTOR = "7"

#: `confirm_audit` / `undo_audit` 的形狀。
Press = Callable[..., Awaitable[None]]


async def audited(session: AsyncSession, roots: dict[str, Path]) -> tuple[Job, LedgerEntry]:
    """一筆 medium 自動入庫完的 Job：一個硬鏈接真的在媒體庫裡，帳本那一列掛著 `audit`。"""
    media, route, factory = await ready(session, roots)
    job = await downloaded_job(session, media, route, roots, name=SINGLE, files=SINGLE_FILES)
    await sweep_plans(session, factory, EventHub(), now=NOW)
    _put_on_disk(roots, SINGLE_FILES)
    await sweep_imports(session, factory, EventHub(), now=NOW)
    assert await state_of(session, job) is JobState.IMPORTED
    (entry,) = await ledger_of(session)
    assert entry.audit is True
    assert Path(entry.target_path).exists()
    return job, entry


#: 同一包三集，都只寫了絕對集號（同 `SINGLE`）：累計換算成 S02E01–E03，三個都是 medium、都自動
#: 入庫掛 audit。批次確認要的就是「同一個 Job 好幾列」。
PACK = "[ANi] SPY×FAMILY 26-28 [1080P][WEB-DL][AAC AVC][CHT]"
PACK_FILES = tuple(
    (f"{PACK}/[ANi] SPY×FAMILY - {number} [1080P][WEB-DL][AAC AVC][CHT].mkv", 1_400_000_000)
    for number in (26, 27, 28)
)


async def audited_pack(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Job, list[LedgerEntry]]:
    """一筆三個檔案都 medium 自動入庫的 Job：三條硬鏈接、三列帳本都掛著 `audit`。"""
    media, route, factory = await ready(session, roots)
    job = await downloaded_job(session, media, route, roots, name=PACK, files=PACK_FILES)
    await sweep_plans(session, factory, EventHub(), now=NOW)
    _put_on_disk(roots, PACK_FILES)
    await sweep_imports(session, factory, EventHub(), now=NOW)
    assert await state_of(session, job) is JobState.IMPORTED
    entries = await ledger_of(session)
    assert [entry.audit for entry in entries] == [True, True, True]
    return job, entries


async def audit_rows(session: AsyncSession) -> list[AuditRow]:
    return [row for row in (await review_queue(session)).rows if isinstance(row, AuditRow)]


class TestTheQueue:
    async def test_a_medium_import_is_on_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance 前半：medium 自動入庫的那一筆在佇列上看得到，說得出是哪一集、在哪裡。"""
        job, entry = await audited(session, roots)

        (row,) = await audit_rows(session)

        assert row.kind is ReviewKind.AUDIT
        assert row.ledger_id == entry.id
        assert (row.job_hash, row.job_name) == (job.hash, SINGLE)
        assert row.target_path == entry.target_path
        assert (row.season, row.episode_start) == (entry.season, entry.episode_start)
        assert row.title_en == "SPY x FAMILY"
        assert row.actions == (AuditAction.CONFIRM, AuditAction.UNDO)
        # 解析器的理由是英文原文，給人判斷的證據。至少要有一句——medium 從來不是沒有原因的。
        assert row.reasons

    async def test_an_open_issue_is_not_on_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Issue 只在 `/issues`（brief §19，2026-09-24）：`/review` 是「入庫要人決定」，Issue 是
        「Berth 與外界對不上」。佇列上只剩一個數字（`count_open`），畫面連過去。"""
        await ready(session, roots)
        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path="/lib/a.mkv")
        await session.commit()

        queue = await review_queue(session)

        assert (queue.rows, queue.total) == ([], 0)
        assert await count_open(session) == 1

    async def test_a_decided_issue_is_not_counted(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await ready(session, roots)
        recorded = await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path="/lib/a.mkv")
        recorded.issue.status = IssueStatus.IGNORED
        await session.commit()

        assert await count_open(session) == 0

    async def test_within_a_kind_the_oldest_comes_first(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同一類之內是「等得最久的先看」——與 `/issues` 那一頁（剛發生的在前）相反。"""
        _, entries = await audited_pack(session, roots)
        for days, entry in zip((1, 9, 5), entries, strict=True):
            entry.created_at = NOW - timedelta(days=days)
        await session.commit()

        order = [row.ledger_id for row in await audit_rows(session)]

        assert order == [entries[1].id, entries[2].id, entries[0].id]

    async def test_past_the_limit_it_returns_the_first_ones_and_the_total(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """超過上限回前面那幾列並帶 `total`。**不分頁**（plan §6）。"""
        _, entries = await audited_pack(session, roots)

        queue = await review_queue(session, limit=2)

        assert queue.total == 3
        assert [row.kind for row in queue.rows] == [ReviewKind.AUDIT, ReviewKind.AUDIT]
        # 截掉的是最新的那一件，不是隨便一件。
        assert entries[-1].id not in {
            row.ledger_id for row in queue.rows if isinstance(row, AuditRow)
        }

    async def test_the_limit_counts_across_kinds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """前面那一類吃掉的格子，後面那一類就少那幾格；`total` 仍然是各類加起來。撤銷一列讓那一筆
        回到 review：`plan` 排在 `audit` 前面，**即使那兩個 audit 比較舊**——類別先於時間。"""
        _, entries = await audited_pack(session, roots)
        await undo_audit(session, entries[0].id, actor=ACTOR)

        queue = await review_queue(session, limit=2)

        assert queue.total == 3
        assert [row.kind for row in queue.rows] == [ReviewKind.PLAN, ReviewKind.AUDIT]


class TestConfirm:
    async def test_it_leaves_the_queue_and_both_flags_are_cleared(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：按確認之後從佇列消失、`ledger.audit` 清掉。"""
        _, entry = await audited(session, roots)

        await confirm_audit(session, entry.id, actor=ACTOR)

        assert await audit_rows(session) == []
        await session.refresh(entry)
        assert entry.audit is False
        # 兩處旗標是同一件事（CONTEXT.md 的 Audit）：下載列表那一列的「N 個待確認」數的是這一格。
        (item,) = [row for row in await items_of(session) if row.id == entry.plan_item_id]
        assert item.audit is False

    async def test_the_timeline_says_it_was_confirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：時間線有 `audit_confirmed`，說得出是哪一個檔案、誰按的。"""
        _, entry = await audited(session, roots)

        await confirm_audit(session, entry.id, actor=ACTOR)

        (event,) = [row for row in await events_of(session) if row.type == "audit_confirmed"]
        assert event.actor == ACTOR
        assert event.payload_json == {"ledger": entry.id, "target": entry.target_path}

    async def test_the_file_stays_where_it_is(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, entry = await audited(session, roots)

        await confirm_audit(session, entry.id, actor=ACTOR)

        assert Path(entry.target_path).exists()
        assert await state_of(session, job) is JobState.IMPORTED

    async def test_confirming_twice_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """多半是另一個分頁先按了。第二次不寫第二筆事件。"""
        _, entry = await audited(session, roots)
        await confirm_audit(session, entry.id, actor=ACTOR)

        with pytest.raises(ReviewRejectedError) as refused:
            await confirm_audit(session, entry.id, actor=ACTOR)

        assert refused.value.reason is ReviewRefusal.NOT_AUDITED

    async def test_a_ledger_row_that_is_not_there_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await ready(session, roots)

        with pytest.raises(ReviewRejectedError) as refused:
            await confirm_audit(session, 404, actor=ACTOR)

        assert refused.value.reason is ReviewRefusal.LEDGER_MISSING


class TestConfirmMany:
    """「全部確認」：同一個 Job 一組一顆、audit 段整段一顆，後端是同一個命令（M3 票 05）。

    按下去等於逐列按確認、一次做完；已經被別處撤銷或確認的列跳過，不算失敗。範圍是**送來的那幾個
    id**——畫面上列出的那些，不是伺服器端的「全部」。
    """

    async def test_every_row_leaves_the_queue_and_both_flags_are_cleared(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, entries = await audited_pack(session, roots)

        outcome = await confirm_audits(session, [entry.id for entry in entries], actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (3, 0)
        assert await audit_rows(session) == []
        for entry in entries:
            await session.refresh(entry)
        assert [entry.audit for entry in entries] == [False, False, False]
        assert [item.audit for item in await items_of(session)] == [False, False, False]

    async def test_each_row_gets_its_own_line_on_the_timeline(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """逐列按確認的語意：時間線上一列一筆 `audit_confirmed`，不是一筆「確認了三個」。"""
        _, entries = await audited_pack(session, roots)

        await confirm_audits(session, [entry.id for entry in entries], actor=ACTOR)

        confirmed = [row for row in await events_of(session) if row.type == "audit_confirmed"]
        assert [(row.actor, (row.payload_json or {})["ledger"]) for row in confirmed] == [
            (ACTOR, entry.id) for entry in entries
        ]

    async def test_a_row_undone_elsewhere_is_skipped_not_a_failure(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：中途有一列已被撤銷（另一個分頁）時照樣成功，並說出跳過幾列。"""
        _, entries = await audited_pack(session, roots)
        ids = [entry.id for entry in entries]
        await undo_audit(session, ids[1], actor=ACTOR)

        outcome = await confirm_audits(session, ids, actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (2, 1)
        assert await audit_rows(session) == []

    async def test_a_row_confirmed_elsewhere_is_skipped_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, entries = await audited_pack(session, roots)
        ids = [entry.id for entry in entries]
        await confirm_audit(session, ids[0], actor=ACTOR)

        outcome = await confirm_audits(session, ids, actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (2, 1)
        # 跳過的那一列不寫第二筆事件。
        confirmed = [row for row in await events_of(session) if row.type == "audit_confirmed"]
        assert len(confirmed) == 3

    async def test_only_the_ids_sent_are_confirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：按下前一刻才出現的 audit 留在清單上——前端送的是它看到的那幾個 id。"""
        _, entries = await audited_pack(session, roots)
        seen, arrived = [entry.id for entry in entries[:2]], entries[2].id

        outcome = await confirm_audits(session, seen, actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (2, 0)
        assert [row.ledger_id for row in await audit_rows(session)] == [arrived]

    async def test_the_same_id_twice_counts_once(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, entries = await audited_pack(session, roots)

        outcome = await confirm_audits(session, [entries[0].id, entries[0].id], actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (1, 0)

    async def test_nothing_sent_is_nothing_done(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await audited_pack(session, roots)

        outcome = await confirm_audits(session, [], actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (0, 0)
        assert len(await audit_rows(session)) == 3


class TestUndo:
    async def test_the_hard_link_is_gone_and_the_source_stays(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：硬鏈接沒了。complete 裡的來源不動——撤銷的是入庫，不是下載。"""
        _, entry = await audited(session, roots)
        target, source = Path(entry.target_path), Path(entry.source_abs_path)

        await undo_audit(session, entry.id, actor=ACTOR)

        assert not target.exists()
        assert source.exists()
        # 空掉的作品資料夾跟著收：留著的話 Jellyfin 的牆上那部作品還在（`fs.prune_empty_parents`）。
        assert not target.parent.exists()

    async def test_the_ledger_row_is_gone_and_so_is_the_queue_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, entry = await audited(session, roots)

        await undo_audit(session, entry.id, actor=ACTOR)

        assert await ledger_of(session) == []
        assert await audit_rows(session) == []

    async def test_the_job_goes_back_to_review_and_says_why(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：Job 回 `review` 且 `review_reason = audit_undone`。"""
        job, entry = await audited(session, roots)

        await undo_audit(session, entry.id, actor=ACTOR)

        assert await state_of(session, job) is JobState.REVIEW
        plan = await plan_of(session)
        await session.refresh(plan)
        assert plan.status is PlanStatus.PENDING_REVIEW
        summary = PlanSummary.model_validate(plan.summary_json)
        assert summary.review_reason is ReviewReason.AUDIT_UNDONE

    async def test_the_plan_item_no_longer_says_it_was_applied(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """那個檔案不在媒體庫裡了：Plan 上它不再是「套用過、待確認」。"""
        _, entry = await audited(session, roots)
        item_id = entry.plan_item_id

        await undo_audit(session, entry.id, actor=ACTOR)

        item = await session.get(PlanItem, item_id, populate_existing=True)
        assert item is not None
        assert (item.audit, item.applied_at) == (False, None)

    async def test_the_timeline_says_it_was_undone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：時間線寫得出來，而且說的是**真的**拆掉了。"""
        _, entry = await audited(session, roots)
        ledger_id, target = entry.id, entry.target_path

        await undo_audit(session, ledger_id, actor=ACTOR)

        (event,) = [row for row in await events_of(session) if row.type == "audit_undone"]
        assert event.actor == ACTOR
        assert event.payload_json == {
            "ledger": ledger_id,
            "target": target,
            "unlinked": True,
            "unmanaged": False,
        }

    async def test_a_link_someone_already_deleted_is_still_undone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """有人先在 Jellyfin 裡刪掉了它：沒有東西可拆，撤銷照樣成立，事件照實說沒拆到。"""
        job, entry = await audited(session, roots)
        Path(entry.target_path).unlink()

        await undo_audit(session, entry.id, actor=ACTOR)

        assert await ledger_of(session) == []
        assert await state_of(session, job) is JobState.REVIEW
        (event,) = [row for row in await events_of(session) if row.type == "audit_undone"]
        assert (event.payload_json or {})["unlinked"] is False

    async def test_a_link_it_cannot_remove_changes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**拆不掉就什麼都不改**：帳本那一列與 Job 都留著，佇列上它也還在。

        用一條逃出每一條 Route 的目標路徑演（帳本被改壞的樣子）：刪除守衛拒絕它，那是
        `remove_one` 丟得出來、而且不必模擬權限就演得出來的那一種失敗。
        """
        job, entry = await audited(session, roots)
        outside = roots["complete"] / "not-a-library-file.mkv"
        outside.write_bytes(b"x")
        entry.target_path = str(outside)
        await session.commit()

        with pytest.raises(ReviewRejectedError) as refused:
            await undo_audit(session, entry.id, actor=ACTOR)

        assert refused.value.reason is ReviewRefusal.UNLINK_FAILED
        assert outside.exists()
        assert len(await ledger_of(session)) == 1
        assert await state_of(session, job) is JobState.IMPORTED
        assert [row for row in await events_of(session) if row.type == "audit_undone"] == []

    async def test_undoing_twice_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, entry = await audited(session, roots)
        ledger_id = entry.id
        await undo_audit(session, ledger_id, actor=ACTOR)

        with pytest.raises(ReviewRejectedError) as refused:
            await undo_audit(session, ledger_id, actor=ACTOR)

        assert refused.value.reason is ReviewRefusal.LEDGER_MISSING

    async def test_a_confirmed_one_cannot_be_undone_from_the_queue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """確認過的檔案已經不是 audit 了：要拿掉它走的是刪除範圍，不是這一顆。"""
        _, entry = await audited(session, roots)
        await confirm_audit(session, entry.id, actor=ACTOR)

        with pytest.raises(ReviewRejectedError) as refused:
            await undo_audit(session, entry.id, actor=ACTOR)

        assert refused.value.reason is ReviewRefusal.NOT_AUDITED
        assert Path(entry.target_path).exists()


class TestTwoTabs:
    """兩個分頁同時按同一列（code-review Spec 軸抓到）。後按的那一個要得到「另一個分頁先按了」
    的那兩種拒絕，而不是 500——也不能兩個都成立、寫出兩筆互相矛盾的事件。"""

    @pytest.mark.parametrize(
        "first, second",
        [(confirm_audit, undo_audit), (undo_audit, confirm_audit), (confirm_audit, confirm_audit)],
    )
    async def test_the_second_press_is_refused_not_a_crash(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        engine: AsyncEngine,
        first: Press,
        second: Press,
    ) -> None:
        _, entry = await audited(session, roots)
        sessions = create_session_factory(engine)

        async def press(action: Press) -> None:
            async with sessions() as own:
                await action(own, entry.id, actor=ACTOR)

        results = await asyncio.gather(press(first), press(second), return_exceptions=True)

        failures = [row for row in results if row is not None]
        assert len(failures) == 1, results
        assert isinstance(failures[0], ReviewRejectedError), results
        decided = [row for row in await events_of(session) if row.type.startswith("audit_")]
        assert len(decided) == 1
