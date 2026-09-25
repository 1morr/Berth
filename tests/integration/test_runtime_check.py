"""片長驗證走到 `/review`（M3 票 15、plan §11.4 的「三道程式檢查」②）。

起點同 `test_air_date_check.py`：票 07 錄下來的 Mikan 聚合 feed，《与你相恋》的 11、12 兩集，
播出日對得上。快照每一集補上 24 分鐘的片長；mediainfo 換成替身，照檔名的集號回答量到幾秒——
下載替身寫到磁碟上的只是幾個位元組，真的 libmediainfo 讀不出片長。

- 12 分鐘的 SP 被當成第 11 集：送審核，理由說得出兩個片長；
- 90 秒的 NCOP 被當成第 11 集：分類器自己降成 extra（brief §6.2，2026-09-26 使用者拍板保留），
  照常入庫，走不到片長驗證；
- 片長對得上、TMDB 沒有片長：照常入庫。

手動送單走同一個 torrent，同一條檢查。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import mediainfo
from berth.domain import (
    EventType,
    JobState,
    MediaInfoSummary,
    MediaSnapshot,
    PlanAction,
    ReasonCode,
    ReviewReason,
    why,
)
from berth.models import Event, LedgerEntry, PlanItem
from berth.services.review import PlanRow, review_queue
from tests.integration.test_air_date_check import (
    delivered_by_rss,
    held_reasons,
    jobs,
    submit_manually,
)
from tests.integration.test_rss import kimi_snapshot

pytestmark = pytest.mark.asyncio


def with_runtime(minutes: int | None) -> MediaSnapshot:
    """《与你相恋》的快照，每一集 `minutes` 分鐘。"""
    snapshot = kimi_snapshot()
    season = snapshot.seasons[0]
    episodes = tuple(row.model_copy(update={"runtime": minutes}) for row in season.episodes)
    return snapshot.model_copy(
        update={"seasons": (season.model_copy(update={"episodes": episodes}),)}
    )


def measuring(monkeypatch: pytest.MonkeyPatch, seconds: Mapping[str, int]) -> None:
    """mediainfo 的替身：檔名裡寫著 ` - 11 ` 的量到 `seconds["11"]` 秒，其餘 24 分鐘。"""

    def probe(path: Path) -> MediaInfoSummary:
        episode = path.name.split(" - ")[1].split(" ")[0]
        return MediaInfoSummary(duration_s=seconds.get(episode, 24 * 60), width=1920)

    monkeypatch.setattr(mediainfo, "probe", probe)


class TestRss:
    async def test_a_matching_runtime_imports_as_usual(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        measuring(monkeypatch, {"11": 23 * 60 + 40})

        await delivered_by_rss(session, roots, with_runtime(24))

        assert {job.state for job in await jobs(session)} == {JobState.IMPORTED}
        assert await held_reasons(session) == []

    async def test_a_special_parsed_as_an_episode_waits_in_review_with_both_runtimes(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        measuring(monkeypatch, {"11": 12 * 60 + 5})

        await delivered_by_rss(session, roots, with_runtime(24))

        states = {job.name.split(" - ")[1][:2]: job.state for job in await jobs(session)}
        assert states == {"11": JobState.REVIEW, "12": JobState.IMPORTED}
        [reasons] = await held_reasons(session)
        assert reasons[-1] == why(
            ReasonCode.RUNTIME_MISMATCH, episode="S01E11", measured="12:05", minutes=24
        ).model_dump(mode="json")
        assert (
            await session.scalar(select(LedgerEntry.id).where(LedgerEntry.episode_start == 11))
            is None
        )

        plans = [row for row in (await review_queue(session)).rows if isinstance(row, PlanRow)]
        assert [row.reason for row in plans] == [ReviewReason.RUNTIME_CONFLICT]
        events = await session.scalars(
            select(Event).where(Event.type == EventType.REVIEW_REQUIRED.value)
        )
        assert [(event.payload_json or {})["reason"] for event in events] == ["runtime_conflict"]

    async def test_a_ninety_second_opening_is_left_to_the_classifier(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """短於五分鐘的「正片」由分類器降成 extra、照常入庫：片長驗證只看分類器看不出來的。"""
        measuring(monkeypatch, {"11": 90})

        await delivered_by_rss(session, roots, with_runtime(24))

        assert {job.state for job in await jobs(session)} == {JobState.IMPORTED}
        actions = {
            row.rel_path.split(" - ")[1][:2]: row.action
            for row in await session.scalars(select(PlanItem))
        }
        assert actions == {"11": PlanAction.EXTRA, "12": PlanAction.IMPORT}

    async def test_no_runtime_on_tmdb_imports_and_says_so(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        measuring(monkeypatch, {"11": 12 * 60})

        await delivered_by_rss(session, roots, with_runtime(None))

        assert {job.state for job in await jobs(session)} == {JobState.IMPORTED}
        eleven = await session.scalar(select(PlanItem).where(PlanItem.rel_path.contains(" - 11 ")))
        assert eleven is not None
        assert why(ReasonCode.RUNTIME_MISSING, episode="S01E11").model_dump(mode="json") in (
            eleven.reasons_json or []
        )


class TestManual:
    async def test_two_episodes_in_one_file_wait_in_review(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """手動送單走同一條：量到兩集長的第 12 集停下來。"""
        measuring(monkeypatch, {"12": 48 * 60})

        job = await submit_manually(session, roots, with_runtime(24), None)

        assert job.state is JobState.REVIEW
        [reasons] = await held_reasons(session)
        assert reasons[-1]["code"] == ReasonCode.RUNTIME_MISMATCH.value

    async def test_a_matching_runtime_imports(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        measuring(monkeypatch, {"12": 24 * 60 + 20})

        job = await submit_manually(session, roots, with_runtime(24), None)

        assert job.state is JobState.IMPORTED
