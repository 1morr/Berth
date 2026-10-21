"""通知的收件人：訂閱了某一種、有 Discord ID 的人（M4 票 125、127、131）。

寫入待送表的每一條路（「可以看了」`notify.queue_ready`、「正在下載」`downloading`、「等你處理」與
週報）都問同一句，所以只有一份。不放在 `notify`：`downloading` 要用它，而 `notify` 經由 `waiting`
依賴 `rss`、`rss` 依賴 `downloading`，放過去就成環。

**這裡只看訂閱與 Discord ID**：媒體庫看不看得到在送出時問 Jellyfin（`notify.send_due`），寫入
多半在別人的寫交易裡，不能打網路。管理員專屬的種類（`ADMIN_ONLY_KINDS`）只給管理員：訂閱是升版
或降級之前存下的也一樣。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import ADMIN_ONLY_KINDS, NotificationKind, Role
from berth.models import User
from berth.services.commands import Effect, command


@command(Effect.READ)
async def subscribers(session: AsyncSession, kind: NotificationKind) -> list[User]:
    """訂閱了 `kind`、有 Discord ID 的人，照 id 排。"""
    query = select(User).where(User.discord_user_id != "").order_by(User.id)
    if kind in ADMIN_ONLY_KINDS:
        query = query.where(User.role == Role.ADMIN)
    return [user for user in await session.scalars(query) if kind.value in user.notify_kinds_json]
