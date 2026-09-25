"""RSS Series 的季號與 offset：第一批審核、套用到整個 Series、確認後不再 audit（M3 票 13）。

起點同 `test_rss.py`：票 07 錄下來的 Mikan 聚合 feed，《与你相恋》喵萌奶茶屋&LoliHouse 的
11、12 兩集一路走到帳本。**split-cour** 用另一份快照：TMDB 把兩個 cour 併成一季 24 集，
字幕組的第二 cour 從 01 重數——feed 上的 11、12 其實是 S01E23、S01E24，而解析器只看得到
「只有集號、TMDB 一季、那一集存在」，照字面落在 S01E11、S01E12（medium，錯的）。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss.fake import FakeFeedFetcher
from berth.domain import (
    AuditReason,
    EpisodeSnapshot,
    JobState,
    JobTrigger,
    MediaSnapshot,
    PlanAction,
    PlanEngine,
    PlanRefusal,
    PlanStatus,
    RematchRefusal,
    ReviewReason,
)
from berth.models import Job, LedgerEntry, Plan, PlanItem, RssSeries
from berth.services.events import EventHub
from berth.services.importer import sweep_imports
from berth.services.plan_review import ItemEdit, PlanRejectedError, approve_plan, edit_items
from berth.services.rematch import Assignment, RematchRejectedError
from berth.services.review import AuditRow, PlanRow, review_queue, undo_audit
from berth.services.rss import add_feed, bind_series, poll_feed
from berth.services.series_review import (
    confirm_series,
    correct_series,
    correct_series_from_plan,
)
from tests.integration.arrange import arrange, factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_air_date_check import airing_split_cour
from tests.integration.test_plan_review import held
from tests.integration.test_rss import (
    FEED,
    FEED_URL,
    KIMI_KEY,
    NOW,
    anime_route,
    episode_pages,
    kimi,
    kimi_snapshot,
    run_pipeline,
    series_by_key,
    torrents,
)

pytestmark = pytest.mark.asyncio

ACTOR = "1"


def split_cour() -> MediaSnapshot:
    """TMDB 併成一季的 split-cour：第一 cour 1–12（一月起）、第二 cour 13–24（七月起）。

    **播完一年之後 feed 才帶到它**（feed 上的兩集發佈於 2026-09）：這一份測的是改正與套用，要第一批
    真的照字面入庫錯。放在連載中的話，播出日比對的規則二會先把它擋進審核（票 14，
    `test_air_date_check.py`）——那正是規則二要抓的東西。
    """
    first, second = date(2025, 1, 9), date(2025, 7, 3)
    episodes = tuple(
        EpisodeSnapshot(
            episode_number=number,
            name=f"Episode {number}",
            air_date=(first + timedelta(days=7 * (number - 1)))
            if number <= 12
            else (second + timedelta(days=7 * (number - 13))),
        )
        for number in range(1, 25)
    )
    season = (
        kimi_snapshot()
        .seasons[0]
        .model_copy(update={"episode_count": 24, "air_date": first, "episodes": episodes})
    )
    return kimi_snapshot().model_copy(update={"first_air_date": first, "seasons": (season,)})


async def delivered(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    snapshot: MediaSnapshot | None = None,
    season: int | None = None,
    offset: int | None = None,
    confirmed: bool = False,
) -> tuple[RssSeries, FakeClientFactory]:
    """feed 輪一次 → 綁定 → 兩集下載完、規劃、入庫。Series 的值在綁定之前設好。"""
    await arrange(session, roots)
    media = await kimi(session, snapshot=snapshot)
    route = await anime_route(session, roots)
    factory = factory_for(roots)
    factory.rss_ = FakeFeedFetcher({FEED_URL: FEED, **episode_pages()})
    factory.torrent_ = torrents()
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=NOW)
    series = await series_by_key(session, KIMI_KEY)
    series.season = season
    series.episode_offset = offset
    series.confirmed = confirmed
    await session.commit()
    await bind_series(session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1)
    await run_pipeline(session, factory, roots)
    return series, factory


async def ledger(session: AsyncSession) -> list[LedgerEntry]:
    rows = await session.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.action == PlanAction.IMPORT)
        .order_by(LedgerEntry.source_rel_path)
    )
    return list(rows)


async def audits(session: AsyncSession) -> list[AuditRow]:
    queue = await review_queue(session)
    return [row for row in queue.rows if isinstance(row, AuditRow)]


class TestThePlanRemembers:
    async def test_each_plan_records_the_season_and_offset_it_used(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots, snapshot=split_cour(), season=1, offset=12)

        plans = list(await session.scalars(select(Plan).where(Plan.job_hash.is_not(None))))
        assert len(plans) == 2
        assert {(p.rss_series_id, p.season_hint, p.episode_offset) for p in plans} == {
            (series.id, 1, 12)
        }
        assert sorted((row.season, row.episode_start) for row in await ledger(session)) == [
            (1, 23),
            (1, 24),
        ]

    async def test_a_series_without_values_records_that_it_had_none(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots)

        plans = list(await session.scalars(select(Plan).where(Plan.job_hash.is_not(None))))
        assert {(p.rss_series_id, p.season_hint, p.episode_offset) for p in plans} == {
            (series.id, None, None)
        }


class TestTheFirstBatch:
    async def test_it_waits_for_a_look_even_when_high(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Series 帶了季號時解析器給 high；第一批照樣進 audit，理由說的是第一批而不是 medium。"""
        series, _ = await delivered(session, roots, season=1)

        items = list(await session.scalars(select(PlanItem).where(PlanItem.action == "import")))
        assert {item.confidence.value for item in items} == {"high"}
        rows = await audits(session)
        assert len(rows) == 2
        assert {(row.series.id if row.series else None) for row in rows} == {series.id}
        assert {row.reason for row in rows} == {AuditReason.FIRST_BATCH}

    async def test_confirming_the_series_confirms_its_rows_and_the_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, _ = await delivered(session, roots)
        ids = [row.ledger_id for row in await audits(session)]

        outcome = await confirm_series(session, series.id, ids, actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (2, 0)
        await session.refresh(series)
        assert series.confirmed is True
        assert await audits(session) == []
        assert {row.audit for row in await ledger(session)} == {False}

    async def test_nothing_confirmed_leaves_the_series_unconfirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送來的列都已被別處撤銷：沒有人看過任何一集，Series 不算確認過。"""
        series, _ = await delivered(session, roots)
        ids = [row.ledger_id for row in await audits(session)]
        for ledger_id in ids:
            await undo_audit(session, ledger_id, actor=ACTOR)

        outcome = await confirm_series(session, series.id, ids, actor=ACTOR)

        assert (outcome.confirmed, outcome.skipped) == (0, 2)
        await session.refresh(series)
        assert series.confirmed is False

    async def test_only_the_rows_on_screen_are_confirmed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同票 05 的整段確認：送來的 id 才算，按下前一刻才進來的留著等人。"""
        series, _ = await delivered(session, roots)
        first, second = await audits(session)

        await confirm_series(session, series.id, [first.ledger_id], actor=ACTOR)

        assert [row.ledger_id for row in await audits(session)] == [second.ledger_id]


class TestAfterConfirmation:
    """已確認的 Series 的 medium 入庫不進 audit 清單；未確認的照舊進（雙向，M3 驗收最後一條）。"""

    async def test_a_confirmed_series_imports_medium_without_audit(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await delivered(session, roots, confirmed=True)

        items = list(await session.scalars(select(PlanItem).where(PlanItem.action == "import")))
        assert {item.confidence.value for item in items} == {"medium"}
        assert {row.audit for row in await ledger(session)} == {False}
        assert await audits(session) == []

    async def test_an_unconfirmed_series_still_audits_medium(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await delivered(session, roots, confirmed=False)

        items = list(await session.scalars(select(PlanItem).where(PlanItem.action == "import")))
        assert {item.confidence.value for item in items} == {"medium"}
        assert {row.audit for row in await ledger(session)} == {True}
        assert len(await audits(session)) == 2


class TestApplyingToTheSeries:
    """split-cour：第一批換算錯 → 改一集並套用到 Series → 其餘未確認的跟著對，鏈接搬到正確路徑。"""

    async def test_one_correction_fixes_the_rest(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        assert [(row.season, row.episode_start) for row in (eleven, twelve)] == [(1, 11), (1, 12)]
        old_paths = [Path(row.target_path) for row in (eleven, twelve)]

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        await session.refresh(series)
        assert (series.season, series.episode_offset) == (1, 12)
        assert (outcome.season, outcome.episode_offset, outcome.moved) == (1, 12, 1)
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 23), (1, 24)]
        assert all(Path(row.target_path).exists() for row in rows)
        assert not any(path.exists() for path in old_paths)
        # 人改的那一集是人決定的；跟著重算的那一集還沒有人看過，留在第一批裡等「全部確認」。
        assert [row.audit for row in rows] == [False, True]
        assert series.confirmed is False

    async def test_a_held_job_of_the_series_is_planned_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """撤銷過、停在 review 的那一筆走重新規劃：讀到新的值，照常入庫。"""
        _, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await undo_audit(session, twelve.id, actor=ACTOR)
        held = await session.get(Job, twelve.job_hash)
        assert held is not None
        assert held.state is JobState.REVIEW

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        assert outcome.replanned == 1
        await session.refresh(held)
        plan = await session.scalar(select(Plan).where(Plan.job_hash == held.hash))
        assert plan is not None
        assert (plan.status, plan.season_hint, plan.episode_offset) == (PlanStatus.AUTO, 1, 12)
        await sweep_imports(session, factory, EventHub(), now=NOW)
        rows = await ledger(session)
        assert sorted((row.season, row.episode_start) for row in rows) == [(1, 23), (1, 24)]

    async def test_a_held_plan_a_person_edited_is_not_planned_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """停在 review、管理員逐列改過的那一份（`engine = user`）是人的決定：
        重新規劃會把它整份換掉，所以不動它。"""
        _, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await undo_audit(session, twelve.id, actor=ACTOR)
        plan = await session.scalar(select(Plan).where(Plan.job_hash == twelve.job_hash))
        assert plan is not None
        row = await session.scalar(
            select(PlanItem).where(PlanItem.plan_id == plan.id, PlanItem.action == "review")
        )
        assert row is not None
        await edit_items(
            session,
            plan.id,
            [ItemEdit(id=row.id, action=PlanAction.IMPORT, season=1, episode_start=20)],
            actor=ACTOR,
        )

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        assert outcome.replanned == 0
        edited = await session.get(PlanItem, row.id, populate_existing=True)
        assert edited is not None
        assert (edited.season, edited.episode_start) == (1, 20)

    async def test_confirmed_rows_are_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「還沒確認的集數」才重算：確認過的那一集是人說對的。"""
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await confirm_series(session, series.id, [twelve.id], actor=ACTOR)

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
            actor=ACTOR,
        )

        assert outcome.moved == 0
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 23), (1, 12)]

    async def test_a_slot_held_by_a_sibling_that_also_moves_is_waited_for(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """offset 小於這一批的集數時，人要的那一格正被同一批的另一集佔著（01–12 放錯、正解 07–18，
        改第 1 集 → E07 時 E07 上是還沒搬的第 7 集）。它也要搬走，所以等它先走，不是拒絕。"""
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, _ = await ledger(session)

        outcome = await correct_series(
            session,
            factory,
            EventHub(),
            eleven.id,
            to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=12),
            actor=ACTOR,
        )

        assert (outcome.episode_offset, outcome.moved, outcome.left) == (1, 1, 0)
        assert outcome.rematched is not None
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 12), (1, 13)]
        assert all(Path(row.target_path).exists() for row in rows)
        await session.refresh(series)
        assert series.episode_offset == 1

    async def test_a_slot_held_by_a_confirmed_episode_is_refused_before_anything(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """擋路的是確認過的那一集：它不會搬，人說的與它互相矛盾——什麼都不動，交給人。"""
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, twelve = await ledger(session)
        await confirm_series(session, series.id, [twelve.id], actor=ACTOR)

        with pytest.raises(RematchRejectedError) as refused:
            await correct_series(
                session,
                factory,
                EventHub(),
                eleven.id,
                to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=12),
                actor=ACTOR,
            )

        assert refused.value.reason is RematchRefusal.TARGET_TAKEN
        await session.refresh(series)
        assert (series.season, series.episode_offset) == (None, None)
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 11), (1, 12)]

    async def test_a_file_not_sent_by_a_series_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, factory = await delivered(session, roots, snapshot=split_cour())
        eleven, _ = await ledger(session)
        job = await session.get(Job, eleven.job_hash)
        assert job is not None
        job.trigger_ref = "0"
        await session.commit()

        with pytest.raises(RematchRejectedError) as refused:
            await correct_series(
                session,
                factory,
                EventHub(),
                eleven.id,
                to=Assignment(action=PlanAction.IMPORT, season=1, episode_start=23),
                actor=ACTOR,
            )

        assert refused.value.reason is RematchRefusal.NOT_FROM_SERIES
        await session.refresh(series)
        assert (series.season, series.episode_offset) == (None, None)


async def held_row(session: AsyncSession, episode: int) -> tuple[int, int]:
    """停在 review 的那一集（檔名的 `- NN`）：回它那一份 Plan 的 id 與影片那一列的 id。"""
    row = await session.scalar(
        select(PlanItem).where(
            PlanItem.rel_path.contains(f" - {episode:02d} "), PlanItem.rel_path.endswith(".mkv")
        )
    )
    assert row is not None
    return row.plan_id, row.id


def edit_to(row_id: int, season: int, episode: int) -> ItemEdit:
    return ItemEdit(id=row_id, action=PlanAction.IMPORT, season=season, episode_start=episode)


class TestApplyingFromReview:
    """連載中的 split-cour（M3 票 14b）：第一批被播出日比對整批擋在審核，一集都沒入庫——
    改一列並套用到 Series，其餘各集重新規劃、通過比對、入庫（仍在第一批裡）。"""

    async def test_one_row_corrected_in_review_lets_the_rest_through(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, factory = await delivered(session, roots, snapshot=airing_split_cour())
        assert {job.state for job in await session.scalars(select(Job))} == {JobState.REVIEW}
        queue = await review_queue(session)
        assert {row.reason for row in queue.rows if isinstance(row, PlanRow)} == {
            ReviewReason.AIR_DATE_CONFLICT
        }
        plan_id, row_id = await held_row(session, 11)

        outcome = await correct_series_from_plan(
            session, factory, EventHub(), plan_id, edit_to(row_id, 1, 23), actor=ACTOR
        )

        await session.refresh(series)
        assert (series.season, series.episode_offset) == (1, 12)
        assert (outcome.season, outcome.episode_offset) == (1, 12)
        assert (outcome.moved, outcome.replanned, outcome.left) == (0, 1, 0)
        # 人改的那一列照人說的；這一份仍等人核准（逐列改從來不代替核准）。
        edited = next(item for item in outcome.plan.items if item.id == row_id)
        assert (edited.action, edited.season, edited.episode_start) == (PlanAction.IMPORT, 1, 23)
        assert outcome.plan.status is PlanStatus.PENDING_REVIEW
        assert outcome.plan.series is not None
        assert (outcome.plan.series.season, outcome.plan.series.episode_offset) == (1, 12)

        # 另一集重新規劃：offset 對了，播出日比對放行、自動入庫——仍在第一批裡等「全部確認」。
        other = await session.scalar(
            select(Plan).where(Plan.id != plan_id, Plan.job_hash.is_not(None))
        )
        assert other is not None
        assert (other.status, other.season_hint, other.episode_offset) == (PlanStatus.AUTO, 1, 12)
        await sweep_imports(session, factory, EventHub(), now=NOW)
        assert [(row.season, row.episode_start, row.audit) for row in await ledger(session)] == [
            (1, 24, True)
        ]

        await approve_plan(session, EventHub(), plan_id, actor=ACTOR)
        await sweep_imports(session, factory, EventHub(), now=NOW)
        rows = await ledger(session)
        assert [(row.season, row.episode_start) for row in rows] == [(1, 23), (1, 24)]
        assert all(Path(row.target_path).exists() for row in rows)

    async def test_a_held_plan_a_person_edited_is_not_planned_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await delivered(session, roots, snapshot=airing_split_cour())
        other_plan, other_row = await held_row(session, 12)
        await edit_items(session, other_plan, [edit_to(other_row, 1, 20)], actor=ACTOR)
        plan_id, row_id = await held_row(session, 11)

        outcome = await correct_series_from_plan(
            session, factory, EventHub(), plan_id, edit_to(row_id, 1, 23), actor=ACTOR
        )

        assert outcome.replanned == 0
        kept = await session.get(PlanItem, other_row, populate_existing=True)
        assert kept is not None
        assert (kept.season, kept.episode_start) == (1, 20)
        plan = await session.get(Plan, other_plan, populate_existing=True)
        assert plan is not None
        assert (plan.status, plan.engine) == (PlanStatus.PENDING_REVIEW, PlanEngine.USER)

    async def test_a_plan_not_sent_by_a_series_is_refused_before_anything(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        series, factory = await delivered(session, roots, snapshot=airing_split_cour())
        plan_id, row_id = await held_row(session, 11)
        plan = await session.get(Plan, plan_id)
        assert plan is not None and plan.job_hash is not None
        job = await session.get(Job, plan.job_hash)
        assert job is not None
        job.trigger_ref = "0"
        await session.commit()

        with pytest.raises(PlanRejectedError) as refused:
            await correct_series_from_plan(
                session, factory, EventHub(), plan_id, edit_to(row_id, 1, 23), actor=ACTOR
            )

        assert refused.value.reason is PlanRefusal.NOT_FROM_SERIES
        await session.refresh(series)
        assert (series.season, series.episode_offset) == (None, None)
        row = await session.get(PlanItem, row_id, populate_existing=True)
        assert row is not None
        assert (row.action, row.season, row.episode_start) == (PlanAction.REVIEW, 1, 11)

    async def test_a_refused_edit_leaves_the_series_as_it_was(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """改動本身不成立時（這裡是那一列不在這份 Plan 裡），Series 也不寫回。"""
        series, factory = await delivered(session, roots, snapshot=airing_split_cour())
        plan_id, _ = await held_row(session, 11)
        _, elsewhere = await held_row(session, 12)

        with pytest.raises(PlanRejectedError) as refused:
            await correct_series_from_plan(
                session, factory, EventHub(), plan_id, edit_to(elsewhere, 1, 23), actor=ACTOR
            )

        assert refused.value.reason is PlanRefusal.ITEM_MISSING
        await session.refresh(series)
        assert (series.season, series.episode_offset) == (None, None)

    async def test_a_plan_decided_meanwhile_leaves_the_series_as_it_was(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """另一個分頁先核准了（在 Job 的鎖裡才讀得到的拒絕）：Series 與其餘的計劃都不動。"""
        series, factory = await delivered(session, roots, snapshot=airing_split_cour())
        plan_id, row_id = await held_row(session, 11)
        await approve_plan(session, EventHub(), plan_id, actor=ACTOR)

        with pytest.raises(PlanRejectedError) as refused:
            await correct_series_from_plan(
                session, factory, EventHub(), plan_id, edit_to(row_id, 1, 23), actor=ACTOR
            )

        assert refused.value.reason is PlanRefusal.NOT_PENDING
        await session.refresh(series)
        assert (series.season, series.episode_offset) == (None, None)
        other = await session.scalar(
            select(Plan).where(Plan.id != plan_id, Plan.job_hash.is_not(None))
        )
        assert other is not None
        assert other.status is PlanStatus.PENDING_REVIEW


#: 一包三集、只寫集號：讀得成第一季，也讀得成後面某季重新數的，所以停在 review（brief §6.4）。
SPY_BATCH = "[ANi] SPY×FAMILY [01-03][1080P]"
SPY_BATCH_FILES = tuple(
    (f"{SPY_BATCH}/[ANi] SPY×FAMILY - {number:02d} [1080P][WEB-DL][CHT].mkv", 1_400_000_000)
    for number in (1, 2, 3)
)


class TestTheCorrectedPlanItself:
    """被改的那一份：人改的列照人說的，沒有人碰過的列跟著 Series 的新值重算（同票 13 的規則）。"""

    async def test_untouched_rows_follow_and_rows_a_person_set_stay(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, route, factory, plan_id = await held(
            session, roots, name=SPY_BATCH, files=SPY_BATCH_FILES
        )
        series = RssSeries(
            key="title:spy-family:ani",
            title_raw="SPY×FAMILY",
            media_id=job.media_id,
            route_id=route.id,
        )
        session.add(series)
        await session.flush()
        job.trigger, job.trigger_ref = JobTrigger.RSS, str(series.id)
        await session.commit()
        first, second, third = [(await held_row(session, number))[1] for number in (1, 2, 3)]
        await edit_items(session, plan_id, [edit_to(third, 1, 10)], actor=ACTOR)

        outcome = await correct_series_from_plan(
            session, factory, EventHub(), plan_id, edit_to(first, 2, 1), actor=ACTOR
        )

        assert (outcome.season, outcome.episode_offset) == (2, None)
        placed = {item.id: (item.season, item.episode_start) for item in outcome.plan.items}
        assert placed == {first: (2, 1), second: (2, 2), third: (1, 10)}
        followed = next(item for item in outcome.plan.items if item.id == second)
        assert followed.action is PlanAction.IMPORT
