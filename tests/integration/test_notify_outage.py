"""Discord 整個連不上時，一筆 Job 從送單到入庫照樣走完（M4 票 128）。

plan §11.5：「管道壞了不阻塞任何管線」。

起點同 `test_air_date_check.submit_manually`：《与你相恋》12 那一集手動送單 → 下載完 → 規劃 →
入庫 → Jellyfin 認出來（寫「可以看了」）。Discord 那一頭是真的 `HttpDiscordBot`，每一個請求都連不上
（`httpx.ConnectError`）；每一步之間送出迴圈都跑一輪。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.notify.discord import HttpDiscordBot
from berth.config import DEFAULT_DISCORD_API_URL
from berth.domain import EventType, JobState, NotificationStatus
from berth.models import Job, Notification
from berth.services.jobs import JobSource, add_download
from berth.services.notify import read_channel, send_due
from berth.services.resolver import sweep_resolutions
from tests.integration.test_notify_failures import ADMIN_ID, CONTENT, person, queued, with_bot
from tests.integration.test_plan import events_of
from tests.integration.test_resolver import FIRST, scanned
from tests.integration.test_rss import KIMI, NOW, harbour, run_pipeline

pytestmark = pytest.mark.asyncio


@respx.mock
async def test_a_job_goes_from_submit_to_ready_while_discord_is_unreachable(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    down = respx.route(url__startswith=DEFAULT_DISCORD_API_URL).mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    media, route, factory = await harbour(session, roots)
    factory.discord = HttpDiscordBot  # type: ignore[method-assign]  # 只有 Discord 是真的 adapter
    await with_bot(session)
    skipper = await person(session, "skipper", ADMIN_ID)
    factory.jellyfin_.users["skipper"] = "harbour"
    # 一則早先寫下、還沒送的：送出迴圈從頭到尾都在打 Discord、退避。
    earlier = await queued(
        session, skipper, at=NOW, content={**CONTENT, "library": route.jellyfin_library_id}
    )
    await send_due(session, factory, now=NOW)

    item = next(item for item in KIMI if " - 12 " in item.title)
    outcome = await add_download(
        session,
        factory,
        source=JobSource(url=item.torrent_url, title=item.title, info_hash=item.info_hash),
        media_id=media.id,
        route_id=route.id,
        user_id=None,
    )
    await send_due(session, factory, now=NOW)
    await run_pipeline(session, factory, roots)
    await send_due(session, factory, now=NOW + FIRST)

    await scanned(session, route, factory)
    # `scanned` 擺的是 SPY×FAMILY 的 Series，換成這一部的 TMDB id，回驗才對得上。
    factory.jellyfin_.items_[0] = replace(factory.jellyfin_.items_[0], tmdb_id="262000")
    await sweep_resolutions(session, factory, now=NOW + FIRST)
    await send_due(session, factory, now=NOW + FIRST * 10)

    job = await session.get(Job, outcome.job.hash)
    assert job is not None
    await session.refresh(job)
    assert job.state is JobState.IMPORTED
    assert EventType.JELLYFIN_ITEM_RESOLVED in [e.type for e in await events_of(session, job.hash)]

    # 「可以看了」寫下了，與早先那一則一起留著等 Discord 回來。
    ready = await session.scalar(select(Notification).where(Notification.id != earlier.id))
    assert ready is not None
    assert ready.status is NotificationStatus.PENDING
    await session.refresh(earlier)
    assert earlier.status is NotificationStatus.PENDING
    assert "unavailable" in earlier.error
    assert down.called
    assert (await read_channel(session)).failures >= 2
