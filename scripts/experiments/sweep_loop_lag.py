"""M4 票 129（票 130 加 RSS 的三項）：每日巡檢一輪佔用事件迴圈多久。

M4 票 13b 量到規劃與輪詢的解析 CPU 跑在事件迴圈上，一批規劃時別的請求慢 340–520 ms；巡檢跑在
同一個迴圈，所以先量再決定要不要移出去（門檻 100 ms，票面）。

做法：在一個暫時的資料庫上灌一份比實際大的資料（RSS Series、Job、事件、開著的 Issue、等你處理的
清單；票 130 起每部作品一季的 TMDB 快照、已入庫的 Job 各一列帳本，每個 Series 留一個洞、一半撞
一集，每 20 個 Series 一個一直失敗的 Feed），跑 `sweep_once` 一輪；同時另一個 coroutine 每 1 ms
醒一次，記下每一次醒得比預定晚多少——最晚的那一次就是巡檢一次佔住迴圈最久的那一段（aiosqlite
的 IO 在自己的執行緒，佔住迴圈的是 SQLAlchemy 組列與 Python 這一側的計算）。

它量的是 Berth 自己，所以 import `berth`、要在 repo 根目錄以 `uv run` 跑。不連網。
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from berth.config import load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.domain import (
    EpisodeSnapshot,
    EventType,
    FeedKind,
    IssueType,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    SeasonSnapshot,
)
from berth.models import Event, Job, LedgerEntry, Media, NotifyWatchSettings, RssFeed, RssSeries
from berth.services.issues import record_issue
from berth.services.settings import write_settings
from berth.services.sweep import sweep_once

NOW = datetime(2026, 10, 22, 5, 0, tzinfo=UTC)


async def seed(sessions, *, series: int, jobs_per: int, events_per: int, issues: int) -> None:  # type: ignore[no-untyped-def]  # 一次性腳本
    async with sessions() as session:
        for index in range(series):
            media = f"tv:{100000 + index}"
            session.add(
                Media(
                    id=media,
                    tmdb_id=100000 + index,
                    kind=MediaKind.TV,
                    title_en=f"Show {index}",
                    title_original=f"Show {index}",
                    year=2025,
                    folder_name=f"Show {index} (2025)",
                    tmdb_snapshot_json=MediaSnapshot(
                        tmdb_id=100000 + index,
                        kind=MediaKind.TV,
                        title=f"Show {index}",
                        title_en=f"Show {index}",
                        title_original=f"Show {index}",
                        year=2025,
                        seasons=(
                            SeasonSnapshot(
                                season_number=1,
                                episode_count=jobs_per,
                                episodes=tuple(
                                    EpisodeSnapshot(
                                        episode_number=number,
                                        air_date=(NOW - timedelta(weeks=jobs_per - number)).date(),
                                    )
                                    for number in range(1, jobs_per + 1)
                                ),
                            ),
                        ),
                    ).model_dump(mode="json"),
                )
            )
            if index % 20 == 0:
                session.add(
                    RssFeed(
                        name=f"Feed {index}",
                        url=f"https://mikanani.me/RSS/Bangumi?bangumiId={index}",
                        kind=FeedKind.MIKAN,
                        poll_error="connection refused",
                        poll_failing_since=NOW - timedelta(days=2),
                    )
                )
            row = RssSeries(
                key=f"mikan:{index}:1",
                title_raw=f"[Group] Show {index} - 01 [1080p]",
                reasons_json=[],
                media_id=media,
                # 一半還沒確認：巡檢要逐一看的那一半。
                confirmed=index % 2 == 0,
            )
            session.add(row)
            await session.flush()
            for number in range(jobs_per):
                job_hash = f"{index:020x}{number:020x}"
                # 每個 Series 一筆停住、其餘在路上或已入庫。
                state = JobState.SUBMIT_FAILED if number == 0 else JobState.IMPORTED
                session.add(
                    Job(
                        hash=job_hash,
                        # 標題裡不放數字：`Show 11 - 10` 會被讀成第 11 集（撞集那一項量不到）。
                        name=f"[Group] Show {_letters(index)} - {number:02d} [1080p]",
                        trigger=JobTrigger.RSS,
                        trigger_ref=str(row.id),
                        state=state,
                        added_at=NOW - timedelta(days=3),
                    )
                )
                # 第 3 集沒入庫（洞）；奇數 Series 的最後一筆被對到前一集（撞集）。
                if state is JobState.IMPORTED and number != 3:
                    episode = number - 1 if index % 2 and number == jobs_per - 1 else number
                    session.add(
                        LedgerEntry(
                            job_hash=job_hash,
                            source_rel_path=f"{job_hash}.mkv",
                            source_abs_path=f"/data/complete/{job_hash}.mkv",
                            source_dev="1",
                            target_path=f"/data/library/tv/Show {index}/{job_hash}.mkv",
                            target_inode="1",
                            media_id=media,
                            season=1,
                            episode_start=episode,
                            episode_end=episode,
                            tags_json={},
                            action=PlanAction.IMPORT,
                            created_at=NOW - timedelta(days=10),
                        )
                    )
                for step in range(events_per):
                    session.add(
                        Event(
                            job_hash=job_hash,
                            type=(
                                EventType.SUBMIT_FAILED.value
                                if state is JobState.SUBMIT_FAILED
                                else EventType.PROGRESS.value
                            ),
                            actor="system",
                            payload_json={"step": step},
                            created_at=NOW - timedelta(days=3, minutes=step),
                        )
                    )
            await session.commit()
        for index in range(issues):
            await record_issue(
                session,
                IssueType.ORPHAN_COMPLETE,
                path=f"/data/torrent/complete/anime/orphan {index}",
                now=NOW - timedelta(days=5),
            )
        await session.commit()
        await write_settings(
            session,
            NotifyWatchSettings(
                seen=[f"issue:{n + 1}" for n in range(issues)],
                since={f"issue:{n + 1}": NOW - timedelta(days=5) for n in range(issues)},
            ),
        )
        await session.commit()


def _letters(index: int) -> str:
    """0 → `A`、26 → `BA`：不帶數字的標題。"""
    out = ""
    while True:
        index, rest = divmod(index, 26)
        out = chr(ord("A") + rest) + out
        if index == 0:
            return out


async def probe(lags: list[float], stop: asyncio.Event) -> None:
    """每 1 ms 醒一次，記下比預定晚了多少毫秒。"""
    while not stop.is_set():
        expected = time.perf_counter() + 0.001
        await asyncio.sleep(0.001)
        lags.append((time.perf_counter() - expected) * 1000)


async def main(series: int, jobs_per: int, events_per: int, issues: int) -> None:
    with tempfile.TemporaryDirectory() as root:
        config = load_config({"CONFIG_ROOT": root})
        Path(root).mkdir(exist_ok=True)
        engine = create_engine(config)
        await upgrade_to_head(engine)
        sessions = create_session_factory(engine)
        started = time.perf_counter()
        await seed(sessions, series=series, jobs_per=jobs_per, events_per=events_per, issues=issues)
        print(
            f"seeded {series} series × {jobs_per} jobs × {events_per} events, {issues} issues "
            f"in {time.perf_counter() - started:.1f}s"
        )

        for round_ in range(3):
            lags: list[float] = []
            stop = asyncio.Event()
            probing = asyncio.create_task(probe(lags, stop))
            await asyncio.sleep(0.05)
            baseline = len(lags)
            started = time.perf_counter()
            async with sessions() as session:
                outcome = await sweep_once(session, now=NOW + timedelta(days=round_))
            elapsed = (time.perf_counter() - started) * 1000
            stop.set()
            await probing
            during = lags[baseline:]
            print(
                f"round {round_ + 1}: {elapsed:.0f} ms wall; stuck={outcome.stuck} "
                f"failing={outcome.failing} missing={outcome.missing} "
                f"colliding={outcome.colliding} reminded={outcome.reminded}; "
                f"loop lag max {max(during):.1f} ms, "
                f"p95 {statistics.quantiles(during, n=20)[-1]:.1f} ms over {len(during)} wakes"
            )
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", type=int, default=400)
    parser.add_argument("--jobs", type=int, default=12, help="每個 Series 幾筆 Job")
    parser.add_argument("--events", type=int, default=8, help="每筆 Job 幾筆事件")
    parser.add_argument("--issues", type=int, default=300)
    args = parser.parse_args()
    asyncio.run(main(args.series, args.jobs, args.events, args.issues))
