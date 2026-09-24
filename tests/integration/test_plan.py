"""`planner_runner`：完成 → Import Plan（plan §3.1、§3.2、§4、brief §5.1、§6.5、票 11）。

送單那一票之後就沒有人在按按鈕了，這一票是**沒有人在場時做的最大決定**：哪個檔案會被
寫到哪裡、要不要先問一句。所以這裡的斷言分成三組——走到哪一站（狀態機）、寫下了什麼
（`plans` 與 `plan_items`）、以及**什麼時候停下來問人**（信心與 Route 的政策）。

解析器本身在 `tests/unit/test_parser_*.py` 與 `berth bench` 裡驗；這裡驗的是它前後那一段：
檔案清單怎麼變成解析器的輸入、mediainfo 的那一格從哪裡來、算出來的東西怎麼落地。
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.domain import (
    CollectionType,
    Confidence,
    EpisodeSnapshot,
    EventType,
    HealthStatus,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanEngine,
    PlanStatus,
    ReasonCode,
    ReviewReason,
    Role,
    SeasonSnapshot,
    Tags,
    why,
)
from berth.models import Event, Job, JobFile, LedgerEntry, Media, Plan, PlanItem, Route
from berth.naming import episode_target, folder_name
from berth.parser import plan as decide
from berth.pipeline import PlannerRunner
from berth.services.events import EventHub, JobSignal
from berth.services.hints import JobHints
from berth.services.plan import plan_id_of, replan_job, sweep_plans
from berth.services.plan_view import read_plan, reasons_of
from berth.services.setup import complete_setup
from tests.integration.arrange import arrange, factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_media import ORDERING, SEASONS, SPY, SPY_ID, credentialled, tmdb

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
HASH = "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"

#: 三集一包，外加一個 NCOP、一個外掛字幕與一個沒人要的 readme（真實批次的形狀）。
BATCH = "[Group] SPY×FAMILY S01 [01-03][1080p][CHT]"
BATCH_FILES = (
    (f"{BATCH}/[Group] SPY×FAMILY S01E01 [1080p][CHT].mkv", 1_400_000_000),
    (f"{BATCH}/[Group] SPY×FAMILY S01E02 [1080p][CHT].mkv", 1_400_000_000),
    (f"{BATCH}/[Group] SPY×FAMILY S01E03 [1080p][CHT].mkv", 1_400_000_000),
    (f"{BATCH}/[Group] SPY×FAMILY NCOP [1080p].mkv", 90_000_000),
    (f"{BATCH}/Subs/[Group] SPY×FAMILY S01E01 [1080p].cht.ass", 41_000),
    (f"{BATCH}/readme.txt", 900),
)

#: 只寫了集號的單集發佈：兩季的作品上它只能靠累計集數換算，所以信心是 medium
#: （brief §6.5）。medium 的兩條路（自動入庫掛 audit / 被 Route 擋下）都拿它演。
#: 集號要超過第一季的 25 集——沒超過的話它也讀得成第二季的某一集，只會是 low（brief §6.4）。
SINGLE = "[ANi] SPY×FAMILY - 26 [1080P][WEB-DL][AAC AVC][CHT]"
SINGLE_FILES = ((f"{SINGLE}/{SINGLE}.mkv", 1_400_000_000),)

#: 對不到任何一集的東西：解析器答不出季集，所以整份 Plan 停下來等人。
STRAY = "SPY×FAMILY OST Collection"
STRAY_FILES = ((f"{STRAY}/Disc 1/theme.mkv", 400_000_000),)

FIXTURE_VIDEO = Path(__file__).parents[1] / "fixtures" / "mediainfo" / "two-second-episode.mkv"


def _snapshot() -> MediaSnapshot:
    """SPY×FAMILY 的兩季，逐集列到底。

    集數要真的列出來：high 的定義之一是「季/集都存在於 TMDB」（brief §6.5），而快照就是
    解析器唯一看得到的 TMDB。
    """

    def season(number: int, count: int, first: datetime) -> SeasonSnapshot:
        return SeasonSnapshot(
            season_number=number,
            name=f"Season {number}",
            names=(f"Season {number}",),
            episode_count=count,
            air_date=first.date(),
            episodes=tuple(
                EpisodeSnapshot(
                    episode_number=index,
                    name=f"Episode {index}",
                    air_date=(first + timedelta(days=7 * (index - 1))).date(),
                )
                for index in range(1, count + 1)
            ),
        )

    return MediaSnapshot(
        tmdb_id=120089,
        kind=MediaKind.TV,
        title="SPY×FAMILY 間諜家家酒",
        title_en="SPY x FAMILY",
        title_original="SPY×FAMILY",
        year=2022,
        first_air_date=datetime(2022, 4, 9, tzinfo=UTC).date(),
        titles=("SPY x FAMILY", "SPY×FAMILY"),
        seasons=(
            season(1, 25, datetime(2022, 4, 9, tzinfo=UTC)),
            season(2, 12, datetime(2023, 10, 7, tzinfo=UTC)),
        ),
    )


async def _media(session: AsyncSession, *, age: timedelta = timedelta()) -> Media:
    """`age` 是快照有多舊。比的是**真的時鐘**（`services/media._fresh` 用 `datetime.now`），
    所以這裡不能拿測試自己的 `NOW` 去算——兩者差幾個小時，那條 6 小時的規則就測不準。"""
    row = Media(
        id=SPY_ID,
        tmdb_id=120089,
        kind=MediaKind.TV,
        title_en="SPY x FAMILY",
        title_original="SPY×FAMILY",
        year=2022,
        # 送單成功那一刻凍結下來的就是命名模板算出來的這一串（票 09）。
        folder_name=folder_name(_snapshot()),
        folder_frozen=True,
        tmdb_snapshot_json=_snapshot().model_dump(mode="json"),
        tmdb_fetched_at=datetime.now(UTC) - age,
    )
    session.add(row)
    await session.commit()
    return row


async def _route(
    session: AsyncSession, roots: dict[str, Path], *, medium_auto_import: bool = True
) -> Route:
    row = Route(
        slug="anime",
        name="Anime",
        jellyfin_library_id="item-2",
        jellyfin_library_name="Anime",
        collection_type=CollectionType.TVSHOWS,
        target_path=str(roots["library"] / "anime"),
        category="berth-anime",
        medium_auto_import=medium_auto_import,
        health_status=HealthStatus.OK,
    )
    session.add(row)
    await session.commit()
    return row


async def ready(
    session: AsyncSession, roots: dict[str, Path], **route_kwargs: bool
) -> tuple[Media, Route, FakeClientFactory]:
    """精靈跑完、有一部作品與一條 anime Route。`test_importer.py` 從同一個起點接下去。"""
    await arrange(session, roots)
    media = await _media(session)
    route = await _route(session, roots, **route_kwargs)
    return media, route, factory_for(roots)


async def downloaded_job(
    session: AsyncSession,
    media: Media,
    route: Route,
    roots: dict[str, Path],
    *,
    state: JobState = JobState.COMPLETED,
    name: str = BATCH,
    files: tuple[tuple[str, int], ...] = BATCH_FILES,
) -> Job:
    """一筆下載完成的 Job，外加它的檔案清單（票 10 的 `metadata_ready` 留下來的那一份）。"""
    save_path = str(roots["complete"] / "anime")
    job = Job(
        hash=HASH,
        name=name,
        trigger=JobTrigger.MANUAL,
        media_id=media.id,
        route_id=route.id,
        state=state,
        save_path=save_path,
        content_path=f"{save_path}/{name}",
        total_size=sum(size for _, size in files),
        progress=1.0,
        completed_at=NOW,
    )
    session.add(job)
    session.add_all(
        [
            JobFile(job_hash=HASH, rel_path=rel_path, size=size, priority=1)
            for rel_path, size in files
        ]
    )
    await session.commit()
    return job


async def run(
    session: AsyncSession, factory: FakeClientFactory, *, hub: EventHub | None = None
) -> None:
    await sweep_plans(session, factory, hub or EventHub(), now=NOW)


async def already_in_the_library(
    session: AsyncSession,
    media: Media,
    route: Route,
    *,
    season: int,
    episode_start: int,
    episode_end: int,
) -> None:
    """媒體庫裡已經有的一份正片（帳本一列）。涵蓋範圍衝突的另一半在這裡（brief §7.8）。

    路徑用**產品自己的命名模板**算，不手寫：判定以所在資料夾為界（Jellyfin 12 只併同一個季
    資料夾裡的），手寫一條長得不一樣的路徑，測到的就會是「兩個資料夾」而不是這條規則。
    """
    snapshot = MediaSnapshot.model_validate(media.tmdb_snapshot_json)
    relative = episode_target(
        snapshot,
        season=season,
        episode=episode_start,
        episode_end=episode_end,
        tags=Tags(resolution="1080p", group="Old"),
        ext=".mkv",
    )
    target = str(PurePosixPath(route.target_path) / relative)
    # 來源那一側只是個標籤：這一列要的是「媒體庫裡已經有這一段」，不是它從哪一包來的。
    span = f"S{season:02d}E{episode_start:02d}-E{episode_end:02d}"
    session.add(
        LedgerEntry(
            source_rel_path=f"old/{span}.mkv",
            source_abs_path=f"/data/torrent/complete/anime/old/{span}.mkv",
            source_inode="1",
            source_dev="1",
            target_path=target,
            target_inode="1",
            media_id=media.id,
            season=season,
            episode_start=episode_start,
            episode_end=episode_end,
            action=PlanAction.IMPORT,
        )
    )
    await session.commit()


async def items_of(session: AsyncSession, job_hash: str = HASH) -> list[PlanItem]:
    rows = await session.scalars(
        select(PlanItem)
        .join(Plan, Plan.id == PlanItem.plan_id)
        .where(Plan.job_hash == job_hash)
        .order_by(PlanItem.id)
    )
    return list(rows)


async def plan_of(session: AsyncSession, job_hash: str = HASH) -> Plan:
    row = await session.scalar(select(Plan).where(Plan.job_hash == job_hash))
    assert row is not None
    return row


async def events_of(session: AsyncSession, job_hash: str = HASH) -> list[Event]:
    rows = await session.scalars(select(Event).where(Event.job_hash == job_hash).order_by(Event.id))
    return list(rows)


class TestEpisodeSpans:
    """媒體庫裡已經有的那一份（brief §7.8、§20.9）。同一包裡的那一半在 `test_parser_planner.py`。"""

    async def test_a_new_file_clashing_with_the_library_is_skipped_and_waits_for_a_human(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """帳本上已經有 S01E01-E02，新的 S01E01 不能自己進去（Jellyfin 12 會把第 2 集併掉）。

        **略過那一列、其餘照常自動入庫**（M2 票 08，2026-09-23 拍板）：它記著撞上的是帳本哪一列，
        在 Review Queue 上是一列 `duplicate`，不再把整份 Plan 擋在 review。
        """
        media, route, factory = await ready(session, roots)
        await already_in_the_library(
            session, media, route, season=1, episode_start=1, episode_end=2
        )
        (known,) = await session.scalars(select(LedgerEntry))
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        plan = await read_plan(session, await _plan_id(session))
        assert plan is not None
        first = next(item for item in plan.items if item.episode_start == 1)
        assert first.action is PlanAction.SKIP
        assert first.target_path == ""
        assert why(ReasonCode.LIBRARY_SPAN_CLASH, known="S01E01-E02") in first.reasons
        assert plan.status is PlanStatus.AUTO
        row = next(item for item in await items_of(session) if item.id == first.id)
        assert row.duplicate_of == known.id

    async def test_the_subtitle_following_a_skipped_file_is_skipped_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """S01E01 的字幕是照那一集的路徑算的：影片略過了，它也略過（否則 importer 會撞上
        舊的那份）。"""
        media, route, factory = await ready(session, roots)
        await already_in_the_library(
            session, media, route, season=1, episode_start=1, episode_end=2
        )
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        subtitle = next(item for item in await items_of(session) if item.rel_path.endswith(".ass"))
        assert subtitle.action is PlanAction.SKIP
        assert subtitle.target_path == ""
        assert subtitle.duplicate_of is None

    async def test_the_timeline_says_which_files_were_skipped(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        await already_in_the_library(
            session, media, route, season=1, episode_start=1, episode_end=2
        )
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        (event,) = [e for e in await events_of(session) if e.type == EventType.DUPLICATE_SKIPPED]
        assert (event.payload_json or {})["files"] == [BATCH_FILES[0][0].split("/", 1)[1]]

    async def test_the_other_episodes_of_the_batch_keep_their_verdict(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只擋起始集撞上的那一列：同一包的其他集照樣是正片。"""
        media, route, factory = await ready(session, roots)
        await already_in_the_library(
            session, media, route, season=1, episode_start=1, episode_end=2
        )
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        plan = await read_plan(session, await _plan_id(session))
        assert plan is not None
        by_episode = {item.episode_start: item.action for item in plan.items if item.episode_start}
        assert by_episode[2] is PlanAction.IMPORT
        assert by_episode[3] is PlanAction.IMPORT

    async def test_the_same_span_is_a_second_version_not_a_clash(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同起始集**同結束集**是多版本並存，本來就該一起入庫（brief §7.7）。"""
        media, route, factory = await ready(session, roots)
        await already_in_the_library(
            session, media, route, season=1, episode_start=1, episode_end=1
        )
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        plan = await read_plan(session, await _plan_id(session))
        assert plan is not None
        first = next(item for item in plan.items if item.episode_start == 1)
        assert first.action is PlanAction.IMPORT


class TestSameVersion:
    """同一集、同一組 Tags：與媒體庫裡那一份是同一個版本（brief §7.8）。"""

    async def _known(
        self, session: AsyncSession, media: Media, route: Route, *, tags: Tags, job_hash: str | None
    ) -> LedgerEntry:
        snapshot = MediaSnapshot.model_validate(media.tmdb_snapshot_json)
        relative = episode_target(snapshot, season=1, episode=2, tags=tags, ext=".mkv")
        entry = LedgerEntry(
            job_hash=job_hash,
            source_rel_path="old/S01E02.mkv",
            source_abs_path="/data/torrent/complete/anime/old/S01E02.mkv",
            source_inode="1",
            source_dev="1",
            target_path=str(PurePosixPath(route.target_path) / relative),
            target_inode="1",
            media_id=media.id,
            season=1,
            episode_start=2,
            action=PlanAction.IMPORT,
            tags_json=tags.model_dump(mode="json"),
        )
        session.add(entry)
        await session.commit()
        return entry

    async def test_the_same_episode_with_the_same_tags_is_skipped(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        await run(session, factory)
        second = next(item for item in await items_of(session) if item.episode_start == 2)
        tags = Tags.model_validate(second.tags_json or {})
        await session.execute(delete(PlanItem))
        await session.execute(delete(Plan))
        job = await session.get(Job, HASH)
        assert job is not None
        job.state = JobState.COMPLETED
        await session.commit()
        known = await self._known(session, media, route, tags=tags, job_hash="other")

        await run(session, factory)

        row = next(item for item in await items_of(session) if item.episode_start == 2)
        assert row.action is PlanAction.SKIP
        assert row.duplicate_of == known.id
        assert why(ReasonCode.SAME_VERSION, known=PurePosixPath(known.target_path).name) in (
            reasons_of(row)
        )
        # 季集與 Tags 留著：決定「取代」或「保留兩者」時照它們算路徑。
        assert (row.season, row.episode_start) == (1, 2)
        assert (await plan_of(session)).status is PlanStatus.AUTO

    async def test_other_tags_are_a_second_version_not_a_duplicate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Tags 不同就是多版本並存（brief §7.7）。"""
        media, route, factory = await ready(session, roots)
        await self._known(
            session, media, route, tags=Tags(resolution="720p", group="Old"), job_hash="other"
        )
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        row = next(item for item in await items_of(session) if item.episode_start == 2)
        assert row.action is PlanAction.IMPORT
        assert row.duplicate_of is None

    async def test_its_own_earlier_link_is_not_a_duplicate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重新規劃看得到自己上一輪的鏈接：那不是重複，importer 比 inode 就認得出來。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        await run(session, factory)
        second = next(item for item in await items_of(session) if item.episode_start == 2)
        tags = Tags.model_validate(second.tags_json or {})
        job = await session.get(Job, HASH)
        assert job is not None
        job.state = JobState.COMPLETED
        await session.commit()
        await self._known(session, media, route, tags=tags, job_hash=HASH)

        await run(session, factory)

        row = next(item for item in await items_of(session) if item.episode_start == 2)
        assert row.action is PlanAction.IMPORT
        assert row.duplicate_of is None


async def _plan_id(session: AsyncSession) -> int:
    found = await plan_id_of(session, HASH)
    assert found is not None
    return found


class TestPlanning:
    async def test_a_completed_job_walks_to_importing_with_an_auto_plan(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """全 high 而且 Route 允許 → 不必問人（plan §3.1、brief §6.5）。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING
        row = await plan_of(session)
        assert row.status is PlanStatus.AUTO
        assert row.engine is PlanEngine.RULES
        assert row.engine_version

    async def test_every_file_lands_with_its_decision_and_its_reasons(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**一個檔案一列**，包含跳過的那一個：畫面要說得出「這一包裡有什麼」。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        rows = await items_of(session)
        assert [row.rel_path for row in rows] == [
            rel_path.split("/", 1)[1] for rel_path, _ in BATCH_FILES
        ]
        by_action = {row.action for row in rows}
        assert by_action == {
            PlanAction.IMPORT,
            PlanAction.EXTRA,
            PlanAction.SUBTITLE,
            PlanAction.SKIP,
        }
        episode = next(row for row in rows if row.action is PlanAction.IMPORT)
        assert (episode.season, episode.episode_start) == (1, 1)
        assert episode.confidence is Confidence.HIGH
        assert episode.media_id == SPY_ID
        assert episode.target_path.startswith("SPY x FAMILY (2022)")
        assert episode.reasons_json

    async def test_the_paths_are_relative_to_the_content_root_not_the_save_path(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """qBittorrent 報的清單含 torrent 自己的根目錄那一層（brief §20.7）。

        照抄進解析器的話，每一個檔案都會多一層資料夾提示——而那一層是發佈名，
        它已經另外傳給解析器了。
        """
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        rows = await items_of(session)
        assert all(not row.rel_path.startswith(BATCH) for row in rows)
        assert any(row.rel_path.startswith("Subs/") for row in rows)

    async def test_the_plan_item_points_back_at_the_job_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """importer 要從決定走回那個檔案（票 12），所以兩張表在這裡就接起來。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        files = {
            row.id: row.rel_path
            for row in await session.scalars(select(JobFile).where(JobFile.job_hash == HASH))
        }
        for item in await items_of(session):
            assert item.job_file_id is not None
            assert files[item.job_file_id].endswith(item.rel_path)

    async def test_the_event_says_what_it_planned(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        generated = [row for row in await events_of(session) if row.type == "plan_generated"]
        assert len(generated) == 1
        payload = generated[0].payload_json or {}
        assert payload["engine"] == PlanEngine.RULES.value
        assert payload["high"] == 5
        assert payload["files"] == 5

    async def test_the_stream_is_told_after_the_transaction_lands(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """推播是「該去問了」的提示，而那件事只有在真相寫下去之後才成立（票 10 的同一條）。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        seen: list[tuple[str, bool]] = []

        class Spy(EventHub):
            def publish(self, signal: JobSignal) -> None:
                seen.append((signal.state, session.in_transaction()))

        await run(session, factory, hub=Spy())

        assert seen == [(JobState.IMPORTING.value, False)]

    async def test_a_job_that_is_not_completed_is_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.DOWNLOADING
        assert (await plan_of(session)).status is PlanStatus.PREPLAN

    async def test_a_job_stranded_in_planning_is_picked_up_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Berth 在算到一半時被關掉：那一列會停在 `planning`，而只掃 `completed` 的話
        它永遠不會再被碰。掃 `planning` 是這一步唯一的復原路徑（plan §3.3 的重入）。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.PLANNING)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING


class TestReview:
    async def test_a_file_it_cannot_place_stops_the_whole_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, name=STRAY, files=STRAY_FILES)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.REVIEW
        row = await plan_of(session)
        assert row.status is PlanStatus.PENDING_REVIEW
        assert (row.summary_json or {})["review_reason"] == ReviewReason.LOW_CONFIDENCE.value

    async def test_the_reason_reaches_the_timeline(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """M1 沒有審核 UI，所以「為什麼停在這裡」只有時間線說得出口（票 11 的範圍）。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, name=STRAY, files=STRAY_FILES)

        await run(session, factory)

        required = [row for row in await events_of(session) if row.type == "review_required"]
        assert len(required) == 1
        assert (required[0].payload_json or {})["reason"] == ReviewReason.LOW_CONFIDENCE.value
        assert [row.type for row in await events_of(session) if row.type == "plan_generated"] == []

    async def test_a_medium_file_is_imported_and_flagged_for_audit(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """medium 自動入庫，但掛 `audit`——撤銷幾乎零成本，那是敢自動入庫的前提
        （brief §6.5、CONTEXT.md 的 Audit）。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, name=SINGLE, files=SINGLE_FILES)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING
        item = (await items_of(session))[0]
        assert item.confidence is Confidence.MEDIUM
        assert item.action is PlanAction.IMPORT
        assert item.audit is True

    async def test_the_job_says_how_many_imports_wait_for_a_look(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """下載列表那一列要說得出「N 個待確認」：否則它是一個綠色的「已入庫」，而 medium 的
        檔案只寫在展開幾千 px 之後的弱字裡（票 15 的 critique，PRODUCT 原則 3）。"""
        from berth.services.jobs import read_job

        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, name=SINGLE, files=SINGLE_FILES)

        await run(session, factory)

        view = await read_job(session, HASH)
        assert view is not None
        assert view.audits == 1

    async def test_a_job_without_a_plan_waits_for_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        from berth.services.jobs import read_job

        media, route, _ = await ready(session, roots)
        await downloaded_job(session, media, route, roots, state=JobState.SUBMITTED, files=())

        view = await read_job(session, HASH)
        assert view is not None
        assert (view.plan_id, view.audits) == (None, 0)

    async def test_a_route_that_refuses_medium_sends_it_to_review(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`medium_auto_import = false` 時 medium 進 review（票 11 驗收、brief §6.5）。"""
        media, route, factory = await ready(session, roots, medium_auto_import=False)
        job = await downloaded_job(session, media, route, roots, name=SINGLE, files=SINGLE_FILES)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.REVIEW
        row = await plan_of(session)
        assert (row.summary_json or {})["review_reason"] == ReviewReason.MEDIUM_NOT_ALLOWED.value
        # 那一列的處置也跟著改：importer 看的是 action，不是 Route 的設定（票 12）。
        item = (await items_of(session))[0]
        assert item.action is PlanAction.REVIEW
        assert item.audit is False

    async def test_high_is_not_touched_by_that_setting(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots, medium_auto_import=False)
        job = await downloaded_job(session, media, route, roots)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING

    async def test_an_unmatched_special_does_not_hold_the_whole_batch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`unmatched` 不是低信心，是**已經做完的決定**（brief §7.6、plan §3.1 的偏差）。

        動漫批次幾乎每一包都夾著一兩個「發佈方自己編號的 SP」——TMDB 那邊的 season 0 用
        另一套號碼，所以它對不到任何一集。擋下去的話整包 12 集都要人按一次，而 M1 沒有
        審核佇列，那等於誰都入不了庫。
        """
        media, route, factory = await ready(session, roots)
        special = f"{BATCH}/[Group] SPY×FAMILY [SP][03][1080p].mkv"
        job = await downloaded_job(
            session, media, route, roots, files=(*BATCH_FILES, (special, 900_000_000))
        )

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING
        unmatched = next(row for row in await items_of(session) if "[SP][03]" in row.rel_path)
        assert unmatched.action is PlanAction.UNMATCHED
        assert unmatched.confidence is Confidence.LOW
        # 它仍然數得出來：畫面上那一份摘要說得出「有一個檔案沒有著落」。
        assert (await plan_of(session)).summary_json == {
            "actions": {"import": 3, "extra": 1, "subtitle": 1, "skip": 1, "unmatched": 1},
            "files": 5,
            "high": 5,
            "low": 1,
            "medium": 0,
            "review_reason": None,
        }

    async def test_a_torrent_with_nothing_to_import_says_so(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """整包都是「不用管」的檔案：那不是低信心，是**送錯了 torrent**（brief §5.1）。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(
            session,
            media,
            route,
            roots,
            name="SPY×FAMILY OST",
            files=(("SPY×FAMILY OST/01.flac", 30_000_000), ("SPY×FAMILY OST/cover.jpg", 900_000)),
        )

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.REVIEW
        row = await plan_of(session)
        assert (row.summary_json or {})["review_reason"] == ReviewReason.NOTHING_TO_IMPORT.value


class TestPreplan:
    async def test_the_file_list_alone_produces_an_estimate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一拿到檔案清單就先算一份（brief §5.1）：下載中就看得出「這根本不是那一季」。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.METADATA_READY)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.METADATA_READY
        row = await plan_of(session)
        assert row.status is PlanStatus.PREPLAN
        assert len(await items_of(session)) == len(BATCH_FILES)

    async def test_it_writes_one_event_and_not_one_per_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)

        await run(session, factory)
        await run(session, factory)

        assert len([row for row in await events_of(session) if row.type == "preplan"]) == 1

    async def test_the_estimate_becomes_the_real_plan_in_place(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一個 Job 一份「現在的計劃」：重算換的是內容，不是 id（票 11 的重入驗收）。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)
        await run(session, factory)
        estimate = (await plan_of(session)).id

        job.state = JobState.COMPLETED
        await session.commit()
        await run(session, factory)

        row = await plan_of(session)
        assert row.id == estimate
        assert row.status is PlanStatus.AUTO
        assert len(await items_of(session)) == len(BATCH_FILES)

    async def test_a_job_without_files_is_not_preplanned(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`submitted` 的那一刻 qBittorrent 還沒交出清單——空的 Plan 說不出任何事。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, state=JobState.SUBMITTED, files=())

        await run(session, factory)

        assert await session.scalar(select(func.count()).select_from(Plan)) == 0


class TestMediaInfo:
    async def _downloaded(self, roots: dict[str, Path], rel_path: str) -> None:
        """把那份 17 KB 的真影片放到 qBittorrent 說的位置上。"""
        target = roots["complete"] / "anime" / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURE_VIDEO, target)

    async def test_a_two_second_feature_is_demoted_to_an_extra(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """檔名說它是第一集，mediainfo 說它 2 秒（plan §4.1、brief §6.2）。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        await self._downloaded(roots, BATCH_FILES[0][0])

        await run(session, factory)

        demoted = next(row for row in await items_of(session) if "S01E01" in row.rel_path)
        assert demoted.action is PlanAction.EXTRA

    async def test_the_measurement_lands_on_the_job_file(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`completed` → `planning` 的副作用就是這件事（plan §3.1）。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        await self._downloaded(roots, BATCH_FILES[0][0])

        await run(session, factory)

        row = await session.scalar(select(JobFile).where(JobFile.rel_path == BATCH_FILES[0][0]))
        assert row is not None
        assert (row.mediainfo_json or {})["duration_s"] == 2
        assert (row.mediainfo_json or {})["video_codec"] == "AVC"
        assert row.kind is not None

    async def test_a_file_it_cannot_read_only_costs_one_signal(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """檔案不在 Berth 看得到的位置上（掛載對不上）時，Plan 照樣算得出來。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING
        rows = await session.scalars(select(JobFile).where(JobFile.job_hash == HASH))
        assert all(row.mediainfo_json is None for row in rows)

    async def test_the_estimate_does_not_measure_anything(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """pre-plan 那一輪檔案還在下載：量到的一定是半份，而半份比沒有更糟。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)
        await self._downloaded(roots, BATCH_FILES[0][0])

        await run(session, factory)

        estimate = next(row for row in await items_of(session) if "S01E01" in row.rel_path)
        assert estimate.action is PlanAction.IMPORT


class TestSnapshot:
    async def test_a_snapshot_older_than_six_hours_is_refreshed_first(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """新播的集數會變，而 Plan 要拿現在的季集算（plan §8.3）。"""
        await arrange(session, roots)
        media = await _media(session, age=timedelta(hours=7))
        route = await _route(session, roots)
        client = tmdb(details=[SPY], seasons=SEASONS, ordering=ORDERING)
        factory = await credentialled(session, client)
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        assert any(row[0] == f"detail/tv/{SPY.tmdb_id}" for row in client.requests)

    async def test_a_fresh_snapshot_is_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """24 小時的規則在這一步收緊成 6 小時，不是「每次都重抓」。"""
        await arrange(session, roots)
        media = await _media(session, age=timedelta(hours=2))
        route = await _route(session, roots)
        client = tmdb(details=[SPY], seasons=SEASONS, ordering=ORDERING)
        factory = await credentialled(session, client)
        await downloaded_job(session, media, route, roots)

        await run(session, factory)

        assert client.requests == []

    @pytest.mark.parametrize("state", [JobState.COMPLETED, JobState.DOWNLOADING])
    async def test_a_frozen_folder_outlives_a_rename_on_tmdb(
        self, session: AsyncSession, roots: dict[str, Path], state: JobState
    ) -> None:
        """資料夾名在第一次送單成功那一刻凍結，之後 TMDB 改名不動它（brief §4.5、plan §5）。

        否則同一部作品的下一包會入庫到另一個資料夾：Jellyfin 多出第二部同名作品，電影的
        多版本也斷掉（檔名前綴要與資料夾一字不差）。正式計劃與 pre-plan 各讀一次快照，兩條都驗。
        """
        media, route, factory = await ready(session, roots)
        frozen = media.folder_name
        renamed = _snapshot().model_copy(update={"title_en": "Spy Family Code White"})
        media.tmdb_snapshot_json = renamed.model_dump(mode="json")
        await session.commit()
        await downloaded_job(session, media, route, roots, state=state)

        await run(session, factory)

        written = [row for row in await items_of(session) if row.target_path]
        assert written
        assert all(row.target_path.startswith(f"{frozen}/") for row in written)

    async def test_tmdb_being_down_does_not_stop_the_plan(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """存下來的季集仍然是**真的**季集（票 09 的同一條規矩）。"""
        from berth.adapters.http import ServiceUnavailableError

        await arrange(session, roots)
        media = await _media(session, age=timedelta(hours=7))
        route = await _route(session, roots)
        client = tmdb(error=ServiceUnavailableError("tmdb: connection refused"))
        factory = await credentialled(session, client)
        job = await downloaded_job(session, media, route, roots)

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING
        assert (await items_of(session))[0].season == 1


class TestReplan:
    async def test_it_recomputes_the_same_plan_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重跑不產生重複的 plan item（票 11 驗收）。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, name=STRAY, files=STRAY_FILES)
        await run(session, factory)
        first = await plan_of(session)

        view = await replan_job(session, factory, EventHub(), HASH, role=Role.ADMIN)

        assert view.id == first.id
        assert len(await items_of(session)) == len(STRAY_FILES)

    async def test_planning_the_same_job_twice_does_not_duplicate_a_single_item(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**重入**（plan §3.3）：算到一半被關掉的那一列會被掃第二次，而它已經有一份決定了。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.PLANNING)
        await run(session, factory)

        job.state = JobState.PLANNING
        await session.commit()
        await run(session, factory)

        assert await session.scalar(select(func.count()).select_from(Plan)) == 1
        assert len(await items_of(session)) == len(BATCH_FILES)

    async def test_a_job_that_is_already_being_imported_is_not_replanned(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`importing` 的那一份已經被採信了，而 importer 正在照它動檔案（票 12）。

        重算一份會讓「已經鏈接好的」與「計劃裡寫的」指向不同的地方——撤銷的依據就沒了。
        """
        from berth.services.jobs import JobRejectedError

        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        await run(session, factory)

        with pytest.raises(JobRejectedError) as refusal:
            await replan_job(session, factory, EventHub(), HASH, role=Role.ADMIN)

        assert refusal.value.reason == "not_replannable"

    async def test_it_pulls_a_job_back_out_of_review(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`review` 的下一步之一就是「再算一次」（plan §3.1 的 review → completed）。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, name=STRAY, files=STRAY_FILES)
        await run(session, factory)
        assert job.state is JobState.REVIEW

        await replan_job(session, factory, EventHub(), HASH, role=Role.ADMIN)

        await session.refresh(job)
        assert job.state is JobState.REVIEW
        assert len(await items_of(session)) == len(STRAY_FILES)

    async def test_a_job_that_never_finished_downloading_cannot_be_replanned(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        from berth.services.jobs import JobRejectedError

        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)

        with pytest.raises(JobRejectedError) as refusal:
            await replan_job(session, factory, EventHub(), HASH, role=Role.ADMIN)

        assert refusal.value.reason == "not_replannable"


class TestReading:
    async def test_the_view_carries_the_decision_the_confidence_and_the_reasons(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        await run(session, factory)

        view = await read_plan(session, await plan_id_of(session, HASH) or 0)

        assert view is not None
        assert view.job_hash == HASH
        assert view.status is PlanStatus.AUTO
        assert view.summary.files == 5
        first = view.items[0]
        assert first.action is PlanAction.IMPORT
        assert first.confidence is Confidence.HIGH
        assert first.reasons
        assert first.target_path

    async def test_a_job_without_a_plan_has_no_id(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, _ = await ready(session, roots)
        await downloaded_job(session, media, route, roots)

        assert await plan_id_of(session, HASH) is None

    async def test_an_unknown_plan_is_not_a_view(self, session: AsyncSession) -> None:
        assert await read_plan(session, 404) is None


class TestEvents:
    async def test_the_timeline_reads_as_the_job_walked_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """下載中先看到預估，完成之後才是那一份真的計劃。"""
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)
        await run(session, factory)

        job.state = JobState.COMPLETED
        await session.commit()
        await run(session, factory)

        assert [row.type for row in await events_of(session)] == [
            EventType.PREPLAN.value,
            EventType.PLAN_GENERATED.value,
        ]


class TestRunner:
    """迴圈的殼（plan §3.2）：什麼時候該算、例外怎麼接。算什麼在上面那幾組。"""

    async def test_it_does_nothing_until_the_wizard_is_done(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        """精靈跑完之前一條 Route 都還沒有，而 Plan 的目標路徑正是 Route 給的。"""
        media, route, factory = await ready(session, roots)
        await downloaded_job(session, media, route, roots)
        runner = PlannerRunner(
            create_session_factory(engine), factory, EventHub(), JobHints(), import_hints=JobHints()
        )

        assert await runner.tick() is None

    async def test_one_tick_plans_what_is_due(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)
        await complete_setup(session)
        await session.commit()
        runner = PlannerRunner(
            create_session_factory(engine), factory, EventHub(), JobHints(), import_hints=JobHints()
        )

        outcome = await runner.tick()

        assert outcome is not None
        assert outcome.planned == 1
        await session.refresh(job)
        assert job.state is JobState.IMPORTING

    async def test_a_nudge_is_what_wakes_it_early(
        self, session: AsyncSession, roots: dict[str, Path], engine: AsyncEngine
    ) -> None:
        """提示只是「早一點」：等到時間了走的是同一條路（`services/hints.py`）。"""
        hints = JobHints()
        hints.nudge()

        assert await hints.wait(60) is True
        # 用掉了就不再成立——不然迴圈會空轉。
        assert await hints.wait(0.05) is False


class TestRoundIsolation:
    async def test_one_job_that_blows_up_does_not_take_the_round_with_it(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """掃描照 `added_at` 排，所以一筆解析不了的 torrent 會**每一輪都排在最前面**——
        整輪一起放棄的話，它後面那幾筆永遠等不到自己的計劃。"""
        media, route, factory = await ready(session, roots)
        broken = await downloaded_job(session, media, route, roots, name=STRAY, files=STRAY_FILES)
        good = Job(
            hash="b" * 40,
            name=BATCH,
            trigger=JobTrigger.MANUAL,
            media_id=media.id,
            route_id=route.id,
            state=JobState.COMPLETED,
            save_path=str(roots["complete"] / "anime"),
            progress=1.0,
        )
        session.add(good)
        session.add_all(
            [
                JobFile(job_hash=good.hash, rel_path=rel_path, size=size, priority=1)
                for rel_path, size in BATCH_FILES
            ]
        )
        await session.commit()

        def explode(name: str, *args: object, **kwargs: object) -> object:
            if name == STRAY:
                raise ValueError("guessit fell over on this one")
            return decide(name, *args, **kwargs)  # type: ignore[arg-type]

        # 字串形式：`decide` 是 `berth.parser.plan` 的別名，直接取屬性會被 mypy 當成
        # 「這個模組沒有明確匯出它」。
        monkeypatch.setattr("berth.services.plan.decide", explode)

        await run(session, factory)

        await session.refresh(broken)
        await session.refresh(good)
        # 壞掉的那一筆停在 `planning`，下一輪會再試一次；好的那一筆照樣走完。
        assert broken.state is JobState.PLANNING
        assert good.state is JobState.IMPORTING

    async def test_the_failure_lands_on_the_job_and_its_timeline(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """只進 log 的話畫面上那一筆看起來是好的：停在「規劃中」，說不出為什麼（M3 票 02）。

        同一個錯誤下一輪再撞一次不再寫一筆：它每 60 秒重試一次，一天就是一千四百筆一模一樣的事。
        """
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)

        def explode(*args: object, **kwargs: object) -> object:
            raise ValueError("guessit fell over on this one")

        monkeypatch.setattr("berth.services.plan.decide", explode)

        await run(session, factory)
        # 下一輪是一分鐘以後：事件本身的一分鐘去重（plan §3.3）擋不到它，擋得到的只有 `Job.error`。
        await session.execute(
            update(Event)
            .where(Event.job_hash == job.hash)
            .values(created_at=datetime.now(UTC) - timedelta(minutes=2))
        )
        await session.commit()
        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.PLANNING
        assert job.error == "ValueError: guessit fell over on this one"
        failed = list(
            await session.scalars(
                select(Event).where(
                    Event.job_hash == job.hash, Event.type == EventType.ROUND_FAILED.value
                )
            )
        )
        assert [row.payload_json for row in failed] == [
            {"error": "ValueError: guessit fell over on this one"}
        ]

    async def test_the_next_good_round_clears_the_error(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)

        def explode(*args: object, **kwargs: object) -> object:
            raise ValueError("guessit fell over on this one")

        monkeypatch.setattr("berth.services.plan.decide", explode)
        await run(session, factory)
        monkeypatch.undo()

        await run(session, factory)

        await session.refresh(job)
        assert job.state is JobState.IMPORTING
        assert job.error == ""
