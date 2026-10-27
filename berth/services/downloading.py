"""「正在下載」寫進待送表（plan §11.5〈通知〉、M4 票 126）。

**一輪一則**：試跑時一次 Mikan 綁定 11 分鐘送出 144 個 torrent，一個 torrent 一則會洗版。所以 RSS
那一頭的每一輪（一個 Feed 的一次輪詢、綁定後的補送、訂閱、「全部下載」）開一個 `download_round`，
送成的 Job 記在它身上，輪結束時依收件人與作品（+ Route）合成一則。輪中途出例外也照寫已經送出去的
那幾筆：torrent 已經在 qBittorrent 裡了。

**人在場按的不告訴他**：手動送單（`add_manual_download`）與人按出來的那幾輪記下按的人（`presser`），
他不收；其他訂閱者照收。

收件人規則與「可以看了」相同（`services.notify`）：訂閱了、有 Discord ID 的人在寫入時看，Jellyfin
看不看得到那個媒體庫在送出時問。組字也在送出時（`notify._render`），這裡只存事實。

**不在 `services.notify` 裡**：`rss` 與手動送單都要呼叫這裡，而 `notify` 經由 `waiting` 依賴 `rss`、
經由 `issues` 依賴 `jobs`，放進去會成環。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import JobRefusal, JobState, MediaKind, NotificationKind
from berth.models import Job, Media, Notification, Route, RssSeries
from berth.models.types import utcnow
from berth.parser import episode_span
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, Flag, command
from berth.services.jobs import (
    AddDownloadOutcome,
    JobSource,
    add_download,
    check_submit,
    series_id_of,
)
from berth.services.plan import guess_from_title
from berth.services.recipients import subscribers

logger = logging.getLogger(__name__)

#: 沒送進 qBittorrent 的不算「正在下載」：還在送（`requested`）與送不成（`submit_failed`）。
_NOT_SENT = frozenset({JobState.REQUESTED, JobState.SUBMIT_FAILED})


@dataclass(slots=True)
class DownloadRound:
    """一輪送出去的 Job（`download_round` 給的）。`presser` 是在場按的人，`None` 是沒有人按。"""

    presser: int | None
    sent: list[str] = field(default_factory=list)

    def note(self, outcome: AddDownloadOutcome) -> None:
        """這一次送單建了新的 Job 就記下；本來就在的那一筆不是這一輪送的。"""
        if outcome.created:
            self.sent.append(outcome.job.hash)


# 寫下的那幾則一旦送出就收不回來，同 `queue_downloading`。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL, Flag.SENDS_OUT})
@asynccontextmanager
async def download_round(
    session: AsyncSession, *, presser: int | None, now: datetime
) -> AsyncIterator[DownloadRound]:
    """一輪的範圍。結束時把送成的那幾筆寫成「正在下載」並 commit；裡面的送單各自已經 commit 過。

    例外時先 rollback 那一刻沒寫完的，照寫已經送出去的，再把**原本的**例外丟回去：寫通知也失敗
    （原本的例外就是資料庫壞了）只記 log，不蓋掉它。只接 `Exception`：關機時的 cancel 不在這裡碰
    資料庫，那一輪已送出的就沒有這一則。
    """
    batch = DownloadRound(presser)
    try:
        yield batch
    except Exception:
        if batch.sent:
            try:
                await session.rollback()
                await _close(session, batch, now)
            except Exception:
                logger.exception(
                    "downloading notifications of a broken round not queued",
                    extra={"jobs": len(batch.sent)},
                )
        raise
    await _close(session, batch, now)


async def _close(session: AsyncSession, batch: DownloadRound, now: datetime) -> None:
    if not batch.sent:
        return
    await queue_downloading(session, batch.sent, presser=batch.presser, now=now)
    await session.commit()


# 撤銷是刪 Job（它有自己的刪除範圍）。排出去的「正在下載」收不回來，但與 RSS 那幾個送單的命令
# （`rss.bind_series` 等）同一個標法：等級看命令的主效果。
@command(
    Effect.REVERSIBLE,
    flags={Flag.DOWNLOADS},
    about=(
        "Send one torrent from search results to qBittorrent and track it as a job for the "
        "work. The route must hold the work's kind (tv into a tvshows library, movie into a "
        "movies library) and be enabled and healthy; a full download disk refuses it."
    ),
    refusals=(JobRefusal,),
    validate=check_submit,
)
async def add_manual_download(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    source: JobSource,
    media_id: str,
    route_id: int,
    user_id: int | None,
) -> AddDownloadOutcome:
    """人手按的下載（搜尋結果、作品頁）：`jobs.add_download`，送成了就告訴其他訂閱者。"""
    outcome = await add_download(
        session, factory, source=source, media_id=media_id, route_id=route_id, user_id=user_id
    )
    async with download_round(session, presser=user_id, now=utcnow()) as batch:
        batch.note(outcome)
    return outcome


# 寫下的那幾則一旦送出就收不回來（送出迴圈不等人）。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL, Flag.SENDS_OUT})
async def queue_downloading(
    session: AsyncSession, job_hashes: Sequence[str], *, presser: int | None, now: datetime
) -> int:
    """這幾筆 Job 的「正在下載」：依作品與 Route 合成，給每一位訂閱了、有 Discord ID、不是 `presser`
    的人各排一則，回排了幾則。沒送進 qBittorrent 的（`_NOT_SENT`）不算。**不 commit**。

    最早送出時間就是 `now`：一輪已經是合成過的單位，不再等合併。

    **寫不成也不拖垮送單那一輪**（同 `notify.queue_ready`）：讀不出內容時記 log、不排，回 0。
    """
    try:
        with session.no_autoflush:
            recipients = [
                user
                for user in await subscribers(session, NotificationKind.DOWNLOADING)
                if user.id != presser
            ]
            if not recipients:
                return 0
            jobs = list(
                await session.scalars(
                    select(Job)
                    .where(Job.hash.in_(job_hashes), Job.state.not_in(_NOT_SENT))
                    .order_by(Job.added_at, Job.hash)
                )
            )
            works: dict[tuple[str, int], list[Job]] = {}
            for job in jobs:
                if job.media_id is not None and job.route_id is not None:
                    works.setdefault((job.media_id, job.route_id), []).append(job)
            contents = [
                (f"{media_id}@{route_id}", content)
                for (media_id, route_id), sent in works.items()
                if (content := await _content(session, media_id, route_id, sent)) is not None
            ]
    except Exception:
        logger.exception("downloading notifications not queued", extra={"jobs": len(job_hashes)})
        return 0
    for user in recipients:
        for key, content in contents:
            session.add(
                Notification(
                    user_id=user.id,
                    kind=NotificationKind.DOWNLOADING,
                    content_json=content,
                    merge_key=key,
                    not_before=now,
                    created_at=now,
                )
            )
    return len(recipients) * len(contents)


async def _content(
    session: AsyncSession, media_id: str, route_id: int, jobs: Sequence[Job]
) -> dict[str, Any] | None:
    """與「可以看了」同一個形狀（`notify._ready_content`）：作品的兩種標題、Route 與它的媒體庫、
    季集。季集是每一筆從發佈名猜的（`plan.guess_from_title`，還沒有檔案清單），猜不到的那一筆不寫；
    組字時再合成連續的範圍。"""
    media = await session.get(Media, media_id)
    route = await session.get(Route, route_id)
    if media is None or route is None:
        return None
    # 標題照畫面那一份（沒抓過 TMDB 也湊得出名字），猜季集只用真的抓過的快照。
    shown, snapshot = media.snapshot(), media.stored_snapshot()
    episodes: list[list[int]] = []
    if media.kind is not MediaKind.MOVIE:
        for job in jobs:
            series_id = series_id_of(job)
            series = await session.get(RssSeries, series_id) if series_id is not None else None
            guess = guess_from_title(
                job.name, snapshot=snapshot, series=series, published=job.published_at
            )
            span = episode_span(guess)
            if span is not None:
                episodes.append(list(span))
    return {
        "media": media.id,
        "kind": media.kind.value,
        "title": shown.title,
        "title_en": shown.title_en,
        "route": route.name,
        "library": route.jellyfin_library_id,
        "episodes": sorted(episodes),
    }
