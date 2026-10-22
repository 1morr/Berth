"""週報（M4 票 131，plan §11.5〈巡檢〉）：每週存一筆、同一週不重複、推摘要給訂閱的管理員。

斷言只看公開的接縫：產生一週（`compose_weekly`）之後讀回來的那一份（`read_report`、`list_reports`），
與送出的一輪（`send_due`）交給 Discord 什麼。起點直接寫列：帳本的入庫列（入庫的時間就是
`created_at`）、核准與 rematch 的事件、收掉或解決的 Issue，加上產生那一刻還等著的幾件。

一週是週一 05:00（巡檢的時刻，容器時區）到下一個週一 05:00；測試的容器時區是 UTC。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.notify import Link
from berth.domain import (
    EventType,
    IssueStatus,
    IssueType,
    JobState,
    JobTrigger,
    Language,
    MediaKind,
    MediaSnapshot,
    NotificationKind,
    NotificationStatus,
    PlanAction,
    PlanStatus,
    Role,
)
from berth.models import (
    BerthSettings,
    Event,
    Issue,
    Job,
    LedgerEntry,
    Media,
    Notification,
    RssSeries,
    User,
    WeeklyReport,
)
from berth.services.deletion import DeleteScope, delete_job
from berth.services.issues import record_issue
from berth.services.notify import send_due
from berth.services.settings import write_settings
from berth.services.weekly import compose_weekly, list_reports, read_report
from tests.integration.factories import FakeClientFactory
from tests.integration.test_notify import (
    ADMIN_ID,
    CREW_ID,
    SECOND_ADMIN_ID,
    person,
    with_bot,
)

pytestmark = pytest.mark.asyncio

#: 這一週結束的那一刻：2026-10-26 是週一。
END = datetime(2026, 10, 26, 5, 0, tzinfo=UTC)
START = END - timedelta(days=7)
INSIDE = START + timedelta(days=2)

FRIEREN = "tv:209867"
DUNE = "movie:693134"
URL = "https://berth.example.org"


async def works(session: AsyncSession) -> None:
    session.add_all(
        [
            _media(FRIEREN, MediaKind.TV, "葬送的芙莉蓮", "Frieren: Beyond Journey's End"),
            _media(DUNE, MediaKind.MOVIE, "沙丘：第二部", "Dune: Part Two"),
        ]
    )
    await session.commit()


def _media(media_id: str, kind: MediaKind, title: str, title_en: str) -> Media:
    tmdb_id = int(media_id.split(":")[1])
    return Media(
        id=media_id,
        tmdb_id=tmdb_id,
        kind=kind,
        title_en=title_en,
        title_original=title_en,
        year=2024,
        folder_name=title_en,
        tmdb_snapshot_json=MediaSnapshot(
            tmdb_id=tmdb_id,
            kind=kind,
            title=title,
            title_en=title_en,
            title_original=title_en,
            year=2024,
        ).model_dump(mode="json"),
    )


_serial = iter(range(1, 10_000))


async def imported(
    session: AsyncSession,
    media_id: str,
    episode: int | None = None,
    *,
    at: datetime = INSIDE,
    season: int = 1,
    action: PlanAction = PlanAction.IMPORT,
    audit: bool = False,
) -> LedgerEntry:
    """帳本的一列：`at` 那一刻入庫。`episode` 是 `None` 的是電影。"""
    number = next(_serial)
    job_hash = f"{number:040d}"
    entry = LedgerEntry(
        job_hash=job_hash,
        source_rel_path=f"{job_hash}.mkv",
        source_abs_path=f"/data/torrent/complete/{job_hash}.mkv",
        source_dev="1",
        target_path=f"/data/library/{media_id}/{number}.mkv",
        target_inode=str(number),
        media_id=media_id,
        season=season if episode is not None else None,
        episode_start=episode,
        episode_end=episode,
        tags_json={},
        action=action,
        audit=audit,
        created_at=at,
    )
    session.add(entry)
    await session.commit()
    return entry


async def happened(
    session: AsyncSession, kind: EventType, *, at: datetime = INSIDE, **payload: object
) -> None:
    session.add(
        Event(
            job_hash="a" * 40,
            type=kind.value,
            actor="7",
            payload_json=dict(payload),
            created_at=at,
        )
    )
    await session.commit()


async def decided(
    session: AsyncSession,
    kind: IssueType,
    *,
    by: str,
    at: datetime = INSIDE,
    status: IssueStatus = IssueStatus.RESOLVED,
) -> None:
    """一件在 `at` 那一刻決定了的 Issue。`by` 是 `system` 的是條件不在了、系統收掉的。"""
    number = next(_serial)
    session.add(
        Issue(
            type=kind,
            subject=str(number),
            path=f"/data/{number}",
            status=status,
            detected_at=at - timedelta(days=1),
            resolved_at=at,
            resolved_by=by,
        )
    )
    await session.commit()


async def still_open(session: AsyncSession, kind: IssueType, subject: int) -> None:
    await record_issue(
        session,
        kind,
        path=f"/data/torrent/complete/open-{subject}",
        series_id=subject,
        feed_id=subject,
        now=INSIDE,
    )
    await session.commit()


async def unbound(session: AsyncSession) -> None:
    session.add(
        RssSeries(key="mikan:1:2", title_raw="[ANi] 某部新番 - 01 [1080P]", reasons_json=[])
    )
    await session.commit()


async def a_week(session: AsyncSession) -> None:
    """一週的假資料，每一段都有算進去的與不該算進去的。"""
    await works(session)
    # 入庫：芙莉蓮 S01E01–E03、E05，沙丘一部；E04 在上週、E06 在下週、字幕不是入庫。
    for episode in (1, 2, 3, 5):
        await imported(session, FRIEREN, episode, audit=episode == 5)
    await imported(session, FRIEREN, 4, at=START - timedelta(minutes=1))
    await imported(session, FRIEREN, 6, at=END)
    await imported(session, FRIEREN, 1, action=PlanAction.SUBTITLE)
    await imported(session, DUNE)
    # 修了什麼：核准兩份（拒絕的與上週的不算）、rematch 一個檔案。
    await happened(session, EventType.REVIEW_DECIDED, decision=PlanStatus.APPROVED.value)
    await happened(session, EventType.REVIEW_DECIDED, decision=PlanStatus.APPROVED.value)
    await happened(session, EventType.REVIEW_DECIDED, decision=PlanStatus.REJECTED.value)
    await happened(
        session,
        EventType.REVIEW_DECIDED,
        decision=PlanStatus.APPROVED.value,
        at=START - timedelta(hours=1),
    )
    await happened(session, EventType.REMATCHED)
    # Issue：人解決一件、系統收掉兩件；忽略的與上週的不算。
    await decided(session, IssueType.ORPHAN_COMPLETE, by="7")
    await decided(session, IssueType.SERIES_EPISODES_MISSING, by="system")
    await decided(session, IssueType.SERIES_EPISODES_MISSING, by="system")
    await decided(session, IssueType.UNKNOWN_TORRENT, by="7", status=IssueStatus.IGNORED)
    await decided(session, IssueType.ORPHAN_COMPLETE, by="7", at=START - timedelta(hours=1))
    # 還等著的：E05 的 audit（審核一件）、兩個 Issue（其中一個是巡檢開的）、一個待綁定的 Series。
    await still_open(session, IssueType.ORPHAN_COMPLETE, 1)
    await still_open(session, IssueType.SERIES_EPISODES_MISSING, 2)
    await unbound(session)


class TestTheThreeSections:
    async def test_a_week_of_data_reads_back_as_three_sections(self, session: AsyncSession) -> None:
        """驗收第 1 條：這週入庫了什麼（依作品，季集範圍）、修了什麼、還有什麼等人。"""
        await a_week(session)

        made = await compose_weekly(session, ends_at=END)

        assert made is not None
        report = await read_report(session, made.id)
        assert (report.first_day, report.last_day) == (date(2026, 10, 19), date(2026, 10, 25))
        assert [(work.media, work.kind, work.title, work.episodes) for work in report.imported] == [
            (DUNE, MediaKind.MOVIE, "沙丘：第二部", ()),
            (FRIEREN, MediaKind.TV, "葬送的芙莉蓮", ((1, 1, 3), (1, 5, 5))),
        ]
        assert report.imported[1].title_en == "Frieren: Beyond Journey's End"
        assert report.fixed.approved == 2
        assert report.fixed.rematched == 1
        assert report.fixed.resolved == {IssueType.ORPHAN_COMPLETE: 1}
        assert report.fixed.cleared == {IssueType.SERIES_EPISODES_MISSING: 2}
        assert report.waiting.review == 1
        assert report.waiting.issues == {
            IssueType.ORPHAN_COMPLETE: 1,
            IssueType.SERIES_EPISODES_MISSING: 1,
        }
        assert report.waiting.swept == {IssueType.SERIES_EPISODES_MISSING: 1}
        assert report.waiting.rss == 1

    async def test_the_history_line_counts_each_section(self, session: AsyncSession) -> None:
        """歷史清單那一列的三個數：入庫幾部（幾集）、修了幾件、等著幾件。"""
        await a_week(session)
        await compose_weekly(session, ends_at=END)

        (line,) = await list_reports(session)

        assert (line.first_day, line.last_day) == (date(2026, 10, 19), date(2026, 10, 25))
        assert (line.works, line.episodes) == (2, 4)
        # 核准 2、rematch 1、解決 1、收掉 2。
        assert line.fixed == 6
        # 審核 1、Issue 2、待綁定 1（巡檢開的那一件已經在 Issue 裡）。
        assert line.waiting == 4


async def reports(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(WeeklyReport)) or 0)


class TestStoredOnce:
    async def test_purging_a_job_afterwards_leaves_the_report_alone(
        self, session: AsyncSession
    ) -> None:
        """驗收第 2 條：產生之後 purge 一筆 Job（帳本與事件一起刪），存下的週報不變。"""
        await works(session)
        entry = await imported(session, FRIEREN, 1)
        session.add(
            Job(
                hash=entry.job_hash,
                name="[ANi] 葬送的芙莉蓮 - 01 [1080P]",
                trigger=JobTrigger.MANUAL,
                media_id=FRIEREN,
                state=JobState.IMPORTED,
            )
        )
        session.add(
            Event(
                job_hash=entry.job_hash,
                type=EventType.REVIEW_DECIDED.value,
                actor="7",
                payload_json={"decision": PlanStatus.APPROVED.value},
                created_at=INSIDE,
            )
        )
        await session.commit()
        made = await compose_weekly(session, ends_at=END)
        assert made is not None
        before = await read_report(session, made.id)

        await delete_job(
            session, FakeClientFactory(), entry.job_hash or "", DeleteScope(purge=True), actor="7"
        )

        assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 0
        after = await read_report(session, made.id)
        assert after == before
        assert [work.episodes for work in after.imported] == [((1, 1, 1),)]
        assert after.fixed.approved == 1

    async def test_the_same_week_again_writes_nothing(self, session: AsyncSession) -> None:
        """驗收第 3 條：同一週重跑（重啟、補跑）不多一筆，也不再推一次摘要。"""
        await a_week(session)
        await subscribed_admin(session)
        assert await compose_weekly(session, ends_at=END) is not None

        assert await compose_weekly(session, ends_at=END, now=END + timedelta(days=1)) is None

        assert await reports(session) == 1
        assert len(await queued(session)) == 1


async def subscribed_admin(session: AsyncSession, *, language: Language = Language.ZH_HANT) -> User:
    return await person(
        session,
        "skipper",
        discord=ADMIN_ID,
        kinds=(NotificationKind.READY, NotificationKind.WEEKLY),
        language=language,
    )


async def queued(session: AsyncSession) -> list[Notification]:
    return list(
        await session.scalars(
            select(Notification).where(Notification.kind == NotificationKind.WEEKLY)
        )
    )


class TestTheSummary:
    async def test_subscribed_admins_get_a_summary_linking_to_that_week(
        self, session: AsyncSession
    ) -> None:
        """驗收第 4 條：摘要推給訂閱了的管理員，附週報頁那一週的連結。"""
        await with_bot(session)
        await write_settings(session, BerthSettings(public_url=URL))
        admin = await subscribed_admin(session)
        await person(session, "other-admin", discord=SECOND_ADMIN_ID)
        await person(
            session,
            "crew",
            role=Role.USER,
            discord=CREW_ID,
            kinds=(NotificationKind.READY, NotificationKind.WEEKLY),
        )
        await session.commit()
        await a_week(session)
        made = await compose_weekly(session, ends_at=END, now=END)
        assert made is not None
        # 沒訂閱的管理員與一般使用者（訂了也不算）都沒有排。
        assert [row.user_id for row in await queued(session)] == [admin.id]
        factory = FakeClientFactory()

        await send_due(session, factory, now=END + timedelta(seconds=10))

        ((to, message),) = factory.discord_.sent
        assert to == ADMIN_ID
        assert message.title == "週報：10-19 – 10-25"
        assert message.description == "入庫 2 部（4 集）· 修了 6 件 · 等你處理 4 件"
        assert message.links == (Link("打開週報", f"{URL}/weekly/{made.id}"),)

    async def test_the_summary_speaks_the_recipients_language(self, session: AsyncSession) -> None:
        await with_bot(session)
        await subscribed_admin(session, language=Language.EN)
        await session.commit()
        await a_week(session)
        await compose_weekly(session, ends_at=END, now=END)
        factory = FakeClientFactory()

        await send_due(session, factory, now=END + timedelta(seconds=10))

        ((_, message),) = factory.discord_.sent
        assert message.title == "Weekly report: 10-19 – 10-25"
        assert message.description == "2 titles imported (4 episodes) · 6 fixed · 4 waiting"
        # 沒存 Berth 的網址：照送、不附連結。
        assert message.links == ()

    async def test_an_admin_who_lost_the_role_gets_nothing(self, session: AsyncSession) -> None:
        """排下之後收件人不再是管理員（每次登入照 Jellyfin 重寫）：那一則放棄。"""
        await with_bot(session)
        admin = await subscribed_admin(session)
        await session.commit()
        await a_week(session)
        await compose_weekly(session, ends_at=END, now=END)
        admin.role = Role.USER
        await session.commit()
        factory = FakeClientFactory()

        await send_due(session, factory, now=END + timedelta(seconds=10))

        assert factory.discord_.sent == []
        (row,) = await queued(session)
        assert row.status is NotificationStatus.ABANDONED
