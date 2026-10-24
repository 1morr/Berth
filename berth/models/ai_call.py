"""用量記錄：對 provider 的一次請求一列（plan §11.6〈用量記錄〉、CONTEXT.md 的 AI Call）。

- **不掛在 Job 上**：`record_event` 一定要一筆 Job，與 M4 另立 `notifications` 同一個理由。
- **tokens 可以是 `NULL`，那是「不知道」，不是 0**：有的端點不回快取欄位，串流中途斷掉時輸出也還
  不知道（brief §20.24）。用量頁算快取命中率時只算兩格都知道的呼叫。
- **沒成的請求也記一列**（`failure`）：串流中途斷掉的照樣花了輸入的 tokens，用量頁也要說得出
  「這幾次被限流」。
- 不設預算（brief §6.10「用量，不設預算」）：這張表只是看的。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import AiCallOrigin, AiFailure, ApiFormat
from berth.models.base import Base
from berth.models.types import UtcDateTime, enum_column, utcnow


class AiCall(Base):
    __tablename__ = "ai_calls"
    # 用量頁依日期加總。
    __table_args__ = (Index("ix_ai_calls_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 送出請求的那一刻。
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    format: Mapped[ApiFormat] = mapped_column(enum_column(ApiFormat))
    #: base URL 的 `host[:port]`（官方是 `api.anthropic.com`）。換了端點之後舊的列還說得出是哪一台。
    host: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    #: 全部輸入，含快取寫入與讀取。
    input_tokens: Mapped[int | None] = mapped_column(default=None)
    output_tokens: Mapped[int | None] = mapped_column(default=None)
    cache_write_tokens: Mapped[int | None] = mapped_column(default=None)
    cache_read_tokens: Mapped[int | None] = mapped_column(default=None)
    #: 從送出到串流結束（或失敗）。
    duration_ms: Mapped[int] = mapped_column()
    #: 誰叫的：設定頁的測試、對話（票 08）、AI 任務（M6）。
    origin: Mapped[AiCallOrigin] = mapped_column(enum_column(AiCallOrigin))
    #: 按下去的那個人；背景任務沒有人。人刪了，用量還在（`SET NULL`）。
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    #: 沒成的分類；成了是 `None`。
    failure: Mapped[AiFailure | None] = mapped_column(enum_column(AiFailure), default=None)
