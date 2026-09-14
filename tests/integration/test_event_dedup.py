"""事件去重（plan §3.3、票 12）。

規則是 `(job_hash, type, payload hash)` 在同一分鐘內只寫一次。它存在的理由是**重啟**：
迴圈的一輪可能在寫完事件之後、在下一步之前被關掉，而重啟後的第一輪會把同一件事再做一次。
時間線是使用者判斷「發生了什麼」的唯一依據，同一件事出現兩次讀起來就是發生了兩次。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import EventType, JobState, JobTrigger
from berth.models import Event, Job
from berth.models.types import utcnow
from berth.services.jobs import record_event

pytestmark = pytest.mark.asyncio

HASH = "0123456789abcdef0123456789abcdef01234567"


async def _job(session: AsyncSession) -> Job:
    job = Job(hash=HASH, name="x", trigger=JobTrigger.MANUAL, state=JobState.DOWNLOADING)
    session.add(job)
    await session.commit()
    return job


async def _types(session: AsyncSession) -> list[str]:
    rows = await session.scalars(
        select(Event.type).where(Event.job_hash == HASH).order_by(Event.id)
    )
    return list(rows)


async def test_a_retry_starts_a_new_attempt(session: AsyncSession) -> None:
    """重試之後又同樣失敗的那一次，與重試之前的一模一樣——但它真的又發生了一次。

    不設這條界線的話，時間線會停在「重試」而狀態是入庫失敗（code-review 抓到）。
    """
    job = await _job(session)
    failure = {"file": "E01.mkv", "error": "Invalid cross-device link"}
    retry = {"state": "importing"}

    await record_event(session, job, EventType.LINK_FAILED, actor="system", payload=failure)
    await record_event(session, job, EventType.RETRIED, actor="user", payload=retry)
    await record_event(session, job, EventType.LINK_FAILED, actor="system", payload=failure)
    await record_event(session, job, EventType.RETRIED, actor="user", payload=retry)

    assert await _types(session) == ["link_failed", "retried", "link_failed", "retried"]


async def test_the_same_event_twice_within_a_minute_is_written_once(
    session: AsyncSession,
) -> None:
    job = await _job(session)

    await record_event(session, job, EventType.COMPLETED, actor="system", payload={"size": 10})
    await record_event(session, job, EventType.COMPLETED, actor="system", payload={"size": 10})

    assert await _types(session) == ["completed"]


async def test_a_different_payload_is_a_different_event(session: AsyncSession) -> None:
    """`linked` 一個檔案一筆：同型別、不同檔案的兩筆都要留下。"""
    job = await _job(session)

    await record_event(session, job, EventType.LINKED, actor="system", payload={"file": "a.mkv"})
    await record_event(session, job, EventType.LINKED, actor="system", payload={"file": "b.mkv"})

    assert await _types(session) == ["linked", "linked"]


async def test_key_order_does_not_make_a_payload_different(session: AsyncSession) -> None:
    """比的是**內容**，不是 dict 恰好的鍵順序——兩個呼叫端組 payload 的順序不必一樣。"""
    job = await _job(session)

    await record_event(
        session, job, EventType.LINKED, actor="system", payload={"file": "a", "target": "b"}
    )
    await record_event(
        session, job, EventType.LINKED, actor="system", payload={"target": "b", "file": "a"}
    )

    assert await _types(session) == ["linked"]


async def test_the_same_event_after_the_minute_is_written_again(session: AsyncSession) -> None:
    job = await _job(session)
    session.add(
        Event(
            job_hash=HASH,
            type=EventType.COMPLETED.value,
            actor="system",
            payload_json={"size": 10},
            created_at=utcnow() - timedelta(minutes=2),
        )
    )
    await session.commit()

    await record_event(session, job, EventType.COMPLETED, actor="system", payload={"size": 10})

    assert await _types(session) == ["completed", "completed"]


async def test_another_jobs_event_does_not_count(session: AsyncSession) -> None:
    job = await _job(session)
    other = Job(hash="f" * 40, name="y", trigger=JobTrigger.MANUAL)
    session.add(other)
    await session.commit()

    await record_event(session, other, EventType.COMPLETED, actor="system", payload={})
    await record_event(session, job, EventType.COMPLETED, actor="system", payload={})

    assert await _types(session) == ["completed"]
