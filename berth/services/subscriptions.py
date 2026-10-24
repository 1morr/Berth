"""撤銷一個訂閱（M5 票 11）：以網址加 Feed、以搜尋詞訂閱、訂閱 Mikan 番組 × 字幕組的反向命令。

**撤到哪裡**（2026-10-24 使用者選定）：停掉訂閱，並撤回這個訂閱送出、還沒下載完的 Job——照 AI
送單的撤銷（`jobs.UNDOABLE`：移除 torrent、刪下載下來的檔、清紀錄）；已經下載完的留著（規劃器隨時
接手入庫，要刪去 Job 頁看清楚範圍），回報留了幾筆。

- **Berth 新建的 Feed**：刪掉它（Item 一起），它長出來、刪完之後一筆 Item 都不剩的 RSS Series 也刪掉
  ——那是這個訂閱帶進來的，留著的話再訂一次會撞上 `series_bound`。別的 Feed 也帶到的 Series 不動。
- **就地綁上的 Mikan Series**（它本來就在使用者的聚合 feed 裡待綁定）：聚合 feed 不能刪，解綁
  （`rss.unbind_series`）；Job 被撤回的那幾筆 Item 回到待綁定，再綁一次會重新送。

「這個訂閱送出的」看 Item：狀態是已送出、`job_hash` 指著的那一筆（別的 Feed 先送過、這裡記成重複的
不算）。向 qBittorrent 移除失敗（連不上）時整個停下、不刪 Feed：撤銷沒做成，再按一次會接著做。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import FeedItemStatus, JobRefusal, RssRefusal
from berth.models import Job, RssFeed, RssItem, RssSeries
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.deletion import withdraw_job
from berth.services.jobs import UNDOABLE, JobRejectedError
from berth.services.rss import RssRejectedError, delete_feed, unbind_series


class Unsubscribed(BaseModel):
    """撤銷了一個訂閱：助理的結果卡照它說撤回了什麼（`services/tools.py` 的撤銷直接回這一份）。"""

    #: 撤回了幾筆還沒下載完的 Job。
    removed: int
    #: 已經下載完、留著的幾筆（要刪去 Job 頁）。
    kept: int


@command(Effect.IRREVERSIBLE)
async def unsubscribe(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    feed_id: int | None = None,
    series_id: int | None = None,
    since: datetime | None = None,
    actor: str,
) -> Unsubscribed:
    """撤銷一個訂閱：`feed_id` 是它新建的 Feed，`series_id` 是它就地綁上的 Series，兩者給一個。
    就地綁上的只撤 `since`（訂閱那一刻）之後送出的：之前綁過又解綁時送的不是這次訂閱的。"""
    if (feed_id is None) == (series_id is None):
        raise ValueError("unsubscribe takes a feed it made or a series it bound, not both")
    if feed_id is not None and await session.get(RssFeed, feed_id) is None:
        raise RssRejectedError(RssRefusal.FEED_MISSING, str(feed_id))
    if series_id is not None and await session.get(RssSeries, series_id) is None:
        raise RssRejectedError(RssRefusal.SERIES_MISSING, str(series_id))
    scope = RssItem.feed_id == feed_id if feed_id is not None else RssItem.series_id == series_id
    sent = list(
        await session.scalars(
            select(RssItem).where(
                scope, RssItem.status == FeedItemStatus.DOWNLOADED, RssItem.job_hash != ""
            )
        )
    )
    removed, gone, kept = await _withdraw(session, factory, sent, since, actor)

    if feed_id is not None:
        grown = set(
            await session.scalars(
                select(RssItem.series_id)
                .where(RssItem.feed_id == feed_id, RssItem.series_id.is_not(None))
                .distinct()
            )
        )
        await delete_feed(session, feed_id)
        for grown_id in grown:
            left = await session.scalar(
                select(func.count()).select_from(RssItem).where(RssItem.series_id == grown_id)
            )
            if not left:
                await session.execute(delete(RssSeries).where(RssSeries.id == grown_id))
        await session.commit()
    else:
        assert series_id is not None
        # 撤回的，與上一次撤到一半已經撤回的（Job 不在了）：回到待綁定，再綁一次會重送。
        for item in await session.scalars(
            select(RssItem).where(RssItem.id.in_([item.id for item in (*removed, *gone)]))
        ):
            item.status = FeedItemStatus.UNBOUND
            item.job_hash = ""
        await unbind_series(session, series_id)
    return Unsubscribed(removed=len(removed), kept=kept)


async def _withdraw(
    session: AsyncSession,
    factory: ServiceClientFactory,
    sent: list[RssItem],
    since: datetime | None,
    actor: str,
) -> tuple[list[RssItem], list[RssItem], int]:
    """撤回還沒下載完的那幾筆 Job。回（撤回了的 Item、Job 已經不在的 Item、留著的筆數）。"""
    removed: list[RssItem] = []
    gone: list[RssItem] = []
    kept = 0
    for item in sent:
        job = await session.get(Job, item.job_hash, populate_existing=True)
        if job is None:
            # 上一次撤到一半時已經撤回了，或在 Job 頁清掉了紀錄：沒有東西可撤，Item 照樣要放回去。
            gone.append(item)
            continue
        if since is not None and job.added_at < since:
            continue
        if job.state not in UNDOABLE:
            kept += 1
            continue
        try:
            await withdraw_job(session, factory, job.hash, actor=actor)
        except JobRejectedError as exc:
            # 讀到之後它往前走了（下載完了）：照留著算。其餘（連不上 qBittorrent）整個停下。
            if exc.reason not in (JobRefusal.MOVED_ON, JobRefusal.NOT_UNDOABLE):
                raise
            kept += 1
            continue
        removed.append(item)
    return removed, gone, kept
