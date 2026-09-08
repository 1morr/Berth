"""SQLAlchemy ORM 與設定分組模型（plan §2）。

M0 只建這五張表；其餘在需要它們的里程碑用 Alembic 增量加（progress.md 偏差與決定）。
"""

from berth.models.auth import User, UserSession
from berth.models.base import Base
from berth.models.event import Event
from berth.models.route import Route, RouteHealth
from berth.models.setting import (
    ANIME_SLUG,
    MOVIES_SLUG,
    SETTINGS_GROUPS,
    TV_SLUG,
    HealthSettings,
    IndexerSettings,
    JellyfinSettings,
    PathSettings,
    QbittorrentSettings,
    ServiceHealth,
    ServiceProbe,
    Setting,
    SettingsGroup,
    SetupAdmin,
    SetupIndexer,
    SetupJellyfin,
    SetupLibrary,
    SetupQbittorrent,
    SetupSettings,
    SetupStep,
    SetupTmdb,
    TmdbSettings,
)

__all__ = [
    "ANIME_SLUG",
    "MOVIES_SLUG",
    "SETTINGS_GROUPS",
    "TV_SLUG",
    "Base",
    "Event",
    "HealthSettings",
    "IndexerSettings",
    "JellyfinSettings",
    "PathSettings",
    "QbittorrentSettings",
    "Route",
    "RouteHealth",
    "ServiceHealth",
    "ServiceProbe",
    "Setting",
    "SettingsGroup",
    "SetupAdmin",
    "SetupIndexer",
    "SetupJellyfin",
    "SetupLibrary",
    "SetupQbittorrent",
    "SetupSettings",
    "SetupStep",
    "SetupTmdb",
    "TmdbSettings",
    "User",
    "UserSession",
]
