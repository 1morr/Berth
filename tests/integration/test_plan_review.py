"""停在 review 的 Plan：逐列改、核准、拒絕（plan §3.1 `review` 的出邊、M2 票 07）。

起點是**規劃器真的算出來的**一份低信心 Plan（`- 05` 只有集號、沒超過第一季的 25 集，所以
讀得成兩種意思，brief §6.4），不是手寫的幾列：驗收要的是「畫面上看到的路徑就是 importer 寫的
那一條」，而那句話只有在兩邊都走產品自己的程式碼時才驗得出來。

入庫的斷言貼著磁碟（同 `test_importer.py`）：帳本說鏈接了不算，媒體庫裡那個檔案真的在才算。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.domain import (
    Confidence,
    JobState,
    PlanAction,
    PlanEngine,
    PlanRefusal,
    PlanStatus,
    ReasonCode,
    why,
)
from berth.models import Job, Route
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.plan import sweep_plans
from berth.services.plan_review import (
    ItemEdit,
    PlanRejectedError,
    approve_plan,
    edit_items,
    reject_plan,
)
from berth.services.plan_view import PlanView, read_plan
from berth.services.review import undo_audit
from tests.integration.factories import FakeClientFactory
from tests.integration.test_importer import _put_on_disk, ledger_of, state_of
from tests.integration.test_plan import (
    NOW,
    STRAY,
    STRAY_FILES,
    downloaded_job,
    events_of,
    items_of,
    plan_of,
    ready,
)
from tests.integration.test_review import audited

pytestmark = pytest.mark.asyncio

ACTOR = "7"

#: 只寫了集號、沒超過第一季的集數：讀得成 S01E05，也讀得成後面某季重新從 01 數的第 5 集
#: ——所以是 low，提案是 S01E05（brief §6.4、§6.5）。外掛字幕同名，跟著影片走。
LOW = "[ANi] SPY×FAMILY - 05 [1080P][WEB-DL][AAC AVC][CHT]"
LOW_FILES = (
    (f"{LOW}/{LOW}.mkv", 1_400_000_000),
    (f"{LOW}/{LOW}.cht.ass", 41_000),
)


async def held(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    name: str = LOW,
    files: tuple[tuple[str, int], ...] = LOW_FILES,
) -> tuple[Job, Route, FakeClientFactory, int]:
    """一筆停在 review 的 Job，Plan 是規劃器算的，檔案真的在 complete 底下。"""
    media, route, factory = await ready(session, roots)
    job = await downloaded_job(session, media, route, roots, name=name, files=files)
    await sweep_plans(session, factory, EventHub(), now=NOW)
    assert await state_of(session, job) is JobState.REVIEW
    _put_on_disk(roots, files)
    return job, route, factory, (await plan_of(session)).id


def by_name(view: PlanView, suffix: str) -> int:
    return next(item.id for item in view.items if item.rel_path.endswith(suffix))


async def view_of(session: AsyncSession, plan_id: int) -> PlanView:
    view = await read_plan(session, plan_id)
    assert view is not None
    return view


class TestTheHeldPlan:
    async def test_it_shows_where_each_row_would_land_if_approved(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """待審核的列沒有寫出去的路徑，但畫面要看得到「照提案入庫」會落在哪裡（使用者拍板）。"""
        _, _, _, plan_id = await held(session, roots)

        video, sidecar = (await view_of(session, plan_id)).items

        assert (video.action, video.confidence) == (PlanAction.REVIEW, Confidence.LOW)
        assert "Season 01" in video.target_path and " - S01E05" in video.target_path
        assert sidecar.target_path.endswith(".CHT.zh.ass")
        assert video.actions == (
            PlanAction.IMPORT,
            PlanAction.EXTRA,
            PlanAction.UNMATCHED,
            PlanAction.SKIP,
        )
        assert sidecar.actions == (PlanAction.SUBTITLE, PlanAction.SKIP)


class TestEditing:
    async def test_a_new_episode_moves_the_row_and_its_sidecar_at_once(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, _, plan_id = await held(session, roots)
        video = by_name(await view_of(session, plan_id), ".mkv")

        view = await edit_items(
            session,
            plan_id,
            [ItemEdit(id=video, action=PlanAction.IMPORT, season=2, episode_start=5)],
            actor=ACTOR,
        )

        moved, sidecar = view.items
        assert (moved.action, moved.season, moved.episode_start) == (PlanAction.IMPORT, 2, 5)
        assert "Season 02" in moved.target_path and " - S02E05" in moved.target_path
        assert sidecar.action is PlanAction.SUBTITLE
        assert sidecar.target_path.startswith(moved.target_path.removesuffix(".mkv"))
        assert why(ReasonCode.SET_BY_USER) in moved.reasons
        assert view.engine is PlanEngine.USER

    async def test_the_path_it_shows_is_the_path_the_importer_writes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 07 驗收：改完那一列顯示的路徑 == `apply_plan` 真的寫出來的（同一份命名函式）。"""
        job, route, factory, plan_id = await held(session, roots)
        video = by_name(await view_of(session, plan_id), ".mkv")
        shown = await edit_items(
            session,
            plan_id,
            [ItemEdit(id=video, action=PlanAction.IMPORT, season=2, episode_start=5)],
            actor=ACTOR,
        )

        await approve_plan(session, EventHub(), plan_id, actor=ACTOR)
        await sweep_imports(session, factory, EventHub(), now=NOW)

        assert await state_of(session, job) is JobState.IMPORTED
        written = sorted(entry.target_path for entry in await ledger_of(session))
        expected = sorted(f"{route.target_path}/{item.target_path}" for item in shown.items)
        assert written == expected
        assert all(Path(path).exists() for path in written)

    @pytest.mark.parametrize(
        ("edit", "reason"),
        [
            (
                {"action": PlanAction.IMPORT, "season": 1, "episode_start": 6, "episode_end": 5},
                PlanRefusal.EPISODE_RANGE_REVERSED,
            ),
            ({"action": PlanAction.IMPORT, "season": 1}, PlanRefusal.EPISODE_REQUIRED),
            ({"action": PlanAction.SKIP, "season": 1}, PlanRefusal.EPISODE_NOT_ALLOWED),
            ({"action": PlanAction.SUBTITLE}, PlanRefusal.ACTION_NOT_ALLOWED),
            ({"action": PlanAction.REVIEW}, PlanRefusal.ACTION_NOT_ALLOWED),
        ],
    )
    async def test_an_edit_that_does_not_make_sense_is_refused_and_writes_nothing(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        edit: dict[str, object],
        reason: PlanRefusal,
    ) -> None:
        _, _, _, plan_id = await held(session, roots)
        before = await view_of(session, plan_id)
        video = by_name(before, ".mkv")

        with pytest.raises(PlanRejectedError) as refused:
            await edit_items(session, plan_id, [ItemEdit(id=video, **edit)], actor=ACTOR)  # type: ignore[arg-type]  # 參數化的 dict 帶的就是 ItemEdit 的欄位

        assert refused.value.reason is reason
        assert await view_of(session, plan_id) == before

    async def test_a_subtitle_cannot_become_an_episode(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """動作與檔案分類矛盾（票 07 驗收的第二種）。"""
        _, _, _, plan_id = await held(session, roots)
        sidecar = by_name(await view_of(session, plan_id), ".ass")

        with pytest.raises(PlanRejectedError) as refused:
            await edit_items(
                session,
                plan_id,
                [ItemEdit(id=sidecar, action=PlanAction.IMPORT, season=1, episode_start=5)],
                actor=ACTOR,
            )

        assert refused.value.reason is PlanRefusal.ACTION_NOT_ALLOWED

    async def test_a_row_of_another_plan_is_not_here(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, _, plan_id = await held(session, roots)

        with pytest.raises(PlanRejectedError) as refused:
            await edit_items(
                session, plan_id, [ItemEdit(id=999, action=PlanAction.SKIP)], actor=ACTOR
            )

        assert refused.value.reason is PlanRefusal.ITEM_MISSING

    async def test_two_rows_that_would_land_on_one_path_are_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """字幕改成跟著影片、影片改成特典——兩列都不衝突；兩個影片指到同一集才衝突。"""
        files = (*LOW_FILES, (f"{LOW}/copy/{LOW}.mkv", 1_400_000_000))
        _, _, _, plan_id = await held(session, roots, files=files)
        view = await view_of(session, plan_id)
        first, second = (item.id for item in view.items if item.rel_path.endswith(".mkv"))

        with pytest.raises(PlanRejectedError) as refused:
            await edit_items(
                session,
                plan_id,
                [
                    ItemEdit(id=first, action=PlanAction.IMPORT, season=1, episode_start=7),
                    ItemEdit(id=second, action=PlanAction.IMPORT, season=1, episode_start=7),
                ],
                actor=ACTOR,
            )

        assert refused.value.reason is PlanRefusal.TARGET_CLASH
        assert " - S01E07" in refused.value.detail


class TestApproving:
    async def test_approving_as_it_stands_imports_the_proposal(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """批次核准＝照提案入庫：沒改過任何一列也入得了庫，落在畫面說的那一條路徑。"""
        job, route, factory, plan_id = await held(session, roots)
        shown = await view_of(session, plan_id)

        approved = await approve_plan(session, EventHub(), plan_id, actor=ACTOR)

        assert approved.status is PlanStatus.APPROVED
        assert await state_of(session, job) is JobState.IMPORTING
        decided = [row for row in await events_of(session) if row.type == "review_decided"]
        assert [row.payload_json for row in decided] == [
            {"plan": plan_id, "decision": "approved", "files": 2}
        ]
        assert (await plan_of(session)).decided_by == ACTOR

        await sweep_imports(session, factory, EventHub(), now=NOW)

        assert await state_of(session, job) is JobState.IMPORTED
        written = sorted(entry.target_path for entry in await ledger_of(session))
        assert written == sorted(f"{route.target_path}/{item.target_path}" for item in shown.items)
        assert all(Path(path).exists() for path in written)

    async def test_a_row_nobody_decided_holds_the_approval(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """沒有提案的待審核列擋住核准，說出是哪一個檔案；改成略過之後就放行。"""
        job, _, _, plan_id = await held(session, roots, name=STRAY, files=STRAY_FILES)

        with pytest.raises(PlanRejectedError) as refused:
            await approve_plan(session, EventHub(), plan_id, actor=ACTOR)

        assert refused.value.reason is PlanRefusal.UNDECIDED
        assert refused.value.detail == "theme.mkv"
        assert await state_of(session, job) is JobState.REVIEW

        (item,) = (await view_of(session, plan_id)).items
        await edit_items(
            session, plan_id, [ItemEdit(id=item.id, action=PlanAction.SKIP)], actor=ACTOR
        )
        await approve_plan(session, EventHub(), plan_id, actor=ACTOR)

        assert await state_of(session, job) is JobState.IMPORTING

    async def test_a_plan_decided_already_is_not_pending(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, _, plan_id = await held(session, roots)
        await approve_plan(session, EventHub(), plan_id, actor=ACTOR)

        for press in (
            approve_plan(session, EventHub(), plan_id, actor=ACTOR),
            reject_plan(session, EventHub(), plan_id, actor=ACTOR),
            edit_items(session, plan_id, [], actor=ACTOR),
        ):
            with pytest.raises(PlanRejectedError) as refused:
                await press
            assert refused.value.reason is PlanRefusal.NOT_PENDING

    async def test_a_missing_plan_is_said_so(self, session: AsyncSession) -> None:
        with pytest.raises(PlanRejectedError) as refused:
            await approve_plan(session, EventHub(), 404, actor=ACTOR)

        assert refused.value.reason is PlanRefusal.PLAN_MISSING


class TestRejecting:
    async def test_it_goes_back_to_completed_and_is_planned_again_from_scratch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """plan §3.1：`review → completed`，規劃器下一輪整份重算——改過的列不留。"""
        job, _, factory, plan_id = await held(session, roots)
        video = by_name(await view_of(session, plan_id), ".mkv")
        await edit_items(
            session, plan_id, [ItemEdit(id=video, action=PlanAction.SKIP)], actor=ACTOR
        )

        await reject_plan(session, EventHub(), plan_id, actor=ACTOR)

        assert await state_of(session, job) is JobState.COMPLETED
        assert (await plan_of(session)).status is PlanStatus.REJECTED
        decided = [row for row in await events_of(session) if row.type == "review_decided"]
        assert [row.payload_json for row in decided] == [{"plan": plan_id, "decision": "rejected"}]

        await sweep_plans(session, factory, EventHub(), now=NOW)

        assert await state_of(session, job) is JobState.REVIEW
        # 重算那一份的 `review_required` 與第一份一字不差，但它在拒絕之後——是真的又停了一次，
        # 不是同一件事寫兩次（`record_event` 的去重以使用者的決定為界，同重試）。
        assert [row.type for row in await events_of(session)] == [
            "review_required",
            "review_decided",
            "review_required",
        ]
        assert [item.action for item in await items_of(session)] == [
            PlanAction.REVIEW,
            PlanAction.REVIEW,
        ]


class TestTwoTabs:
    async def test_approving_and_rejecting_at_once_lets_exactly_one_through(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩個分頁同時按：先到的成立，後到的得到 `not_pending`，不是兩筆互相矛盾的事件。"""
        job, _, _, plan_id = await held(session, roots)
        sessions = create_session_factory(engine)

        async def press(which: str) -> PlanRefusal | None:
            async with sessions() as own:
                try:
                    if which == "approve":
                        await approve_plan(own, EventHub(), plan_id, actor=ACTOR)
                    else:
                        await reject_plan(own, EventHub(), plan_id, actor=ACTOR)
                except PlanRejectedError as refused:
                    return refused.reason
                return None

        outcomes = await asyncio.gather(press("approve"), press("reject"))

        assert sorted(outcomes, key=str) == sorted([None, PlanRefusal.NOT_PENDING], key=str)
        decided = [row for row in await events_of(session) if row.type == "review_decided"]
        assert len(decided) == 1
        assert await state_of(session, job) in {JobState.IMPORTING, JobState.COMPLETED}


class TestAfterAnUndo:
    async def test_an_undone_row_has_to_be_decided_again_before_approving(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """撤銷說的是「這一列不對」（`ReviewReason.AUDIT_UNDONE`）：原樣再核准會把剛拆掉的
        鏈接鏈回同一條路徑。所以那一列回到「沒有提案」，核准被擋到管理員決定它為止
        （票 07 code-review）。"""
        job, entry = await audited(session, roots)
        await undo_audit(session, entry.id, actor=ACTOR)
        plan_id = (await plan_of(session)).id

        (row,) = (await view_of(session, plan_id)).items
        assert (row.action, row.season, row.episode_start, row.target_path) == (
            PlanAction.REVIEW,
            None,
            None,
            "",
        )
        with pytest.raises(PlanRejectedError) as refused:
            await approve_plan(session, EventHub(), plan_id, actor=ACTOR)
        assert refused.value.reason is PlanRefusal.UNDECIDED

        await edit_items(
            session,
            plan_id,
            [ItemEdit(id=row.id, action=PlanAction.IMPORT, season=2, episode_start=2)],
            actor=ACTOR,
        )
        await approve_plan(session, EventHub(), plan_id, actor=ACTOR)
        assert await state_of(session, job) is JobState.IMPORTING
