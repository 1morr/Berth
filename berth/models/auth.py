"""使用者與登入 session（plan §2.1）。

身分的來源是 Jellyfin：`users` 只是本地鏡射，密碼永遠不存在這裡。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import Language, Role
from berth.models.base import Base
from berth.models.types import UtcDateTime, enum_column, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    jellyfin_user_id: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(enum_column(Role))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: 收通知的 Discord user ID（snowflake，17–20 位數字）。空字串是不收（M4 票 123）。
    #: `server_default` 是 migration 原生 `ADD COLUMN` 留下來的（不重建表）。
    discord_user_id: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: 通知用哪個語言寫：存 Discord ID 那一刻的介面語言（`domain.Language`）。
    notify_language: Mapped[Language] = mapped_column(
        enum_column(Language), default=Language.ZH_HANT, server_default=Language.ZH_HANT.value
    )


class UserSession(Base):
    """名稱刻意不叫 `Session`，避免與 SQLAlchemy 的 `AsyncSession` 混淆。"""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
