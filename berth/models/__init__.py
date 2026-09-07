"""SQLAlchemy ORM 與設定分組模型（plan §2）。

M0 只建這五張表；其餘在需要它們的里程碑用 Alembic 增量加（progress.md 偏差與決定）。
"""

from berth.models.auth import User, UserSession
from berth.models.base import Base
from berth.models.event import Event
from berth.models.route import Route
from berth.models.setting import (
    SETTINGS_GROUPS,
    IndexerSettings,
    JellyfinSettings,
    PathSettings,
    QbittorrentSettings,
    Setting,
    SettingsGroup,
    SetupSettings,
    TmdbSettings,
)

__all__ = [
    "SETTINGS_GROUPS",
    "Base",
    "Event",
    "IndexerSettings",
    "JellyfinSettings",
    "PathSettings",
    "QbittorrentSettings",
    "Route",
    "Setting",
    "SettingsGroup",
    "SetupSettings",
    "TmdbSettings",
    "User",
    "UserSession",
]
