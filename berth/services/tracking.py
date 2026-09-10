"""「Berth 為這部作品做過事嗎」——Tracked Media 的推導（`CONTEXT.md`、票 04b、09）。

`CONTEXT.md` 說 Tracked Media 是「Berth 曾為其下載、訂閱或入庫過的 Media」。那是一個
**推導出來的結果**，不是一顆按鈕、也不是 `media` 上的一個欄位（票 04b 把那個欄位刪掉了）：
點進詳情頁就會寫下一列 `media`（快照要有地方放），所以「有這一列」什麼都不代表。

推導的來源會長大——票 09 是 `EXISTS(jobs)`，票 12 加帳本，M3 加 Rule。**三個來源要在同一支
函式裡長**：探索牆的卡片與詳情頁讀的是同一份答案，各寫一份 SQL 的話其中一份遲早會少算一種。
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.models import Job


async def tracked_media(session: AsyncSession, media_ids: Iterable[str]) -> frozenset[str]:
    """這幾部作品裡，哪幾部 Berth 已經為它做過事。

    一次問一整面牆而不是逐格問：探索頁一次畫 20 格，逐格一句 `EXISTS` 是 20 次往返。
    """
    wanted = {media_id for media_id in media_ids if media_id}
    if not wanted:
        return frozenset()
    rows = await session.scalars(select(Job.media_id).where(Job.media_id.in_(wanted)).distinct())
    return frozenset(media_id for media_id in rows if media_id is not None)


async def is_tracked(session: AsyncSession, media_id: str) -> bool:
    """一部作品的版本。詳情頁只問一部，不必湊一個集合。"""
    return media_id in await tracked_media(session, [media_id])
