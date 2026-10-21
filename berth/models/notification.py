"""待送表：送給某一個人的一則通知（plan §11.5〈通知〉、M4 票 123、CONTEXT.md 的 Notification）。

**與觸發它的狀態變更寫在同一筆交易**，由送出迴圈（`pipeline/notifying.py`）另外送：管道壞了
不阻塞任何管線，交易 rollback 時也不會留下一則說「可以看了」的通知。不放寬 `events`：
`record_event` 一定要一筆 Job，而且 purge 會刪列、id 不能當游標（plan §11.5）。

- **`content_json` 存事實，不存句子**：送出那一刻才照收件人的語言組字（`services.notify`），
  票 125 的合併也是把兩份事實併成一份。
- **`merge_key`** 是「同一件事」的鍵（「可以看了」是作品 id）。這一張只寫下它，合併在票 125。
- **`not_before`** 是最早送出時間：這一張寫入當下就到時間，票 125 的合併延後 5 分鐘。
- 收件人是 `users` 的一列（`ON DELETE CASCADE`：人不在了，給他的通知沒有對象）。送的時候才讀
  他的 Discord ID，所以中途改了 ID 的人收在新的那一個。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import NotificationKind, NotificationStatus
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # 送出迴圈每一輪問的那一句：還沒送的、到時間的。
        Index("ix_notifications_status_not_before", "status", "not_before"),
        Index("ix_notifications_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[NotificationKind] = mapped_column(enum_column(NotificationKind))
    content_json: Mapped[dict[str, Any]] = mapped_column(JsonText)
    merge_key: Mapped[str] = mapped_column(Text, default="")
    not_before: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    status: Mapped[NotificationStatus] = mapped_column(
        enum_column(NotificationStatus), default=NotificationStatus.PENDING
    )
    #: 送過幾次沒送到。
    attempts: Mapped[int] = mapped_column(default=0)
    #: 沒送到之後最早什麼時候再送；`None` 是沒失敗過。退避的算法在票 128。
    retry_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: 上一次沒送到的原因（`DeliveryFailure` 的值加 Discord 的原文）。
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
