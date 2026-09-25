"""SQLAlchemy ORM 與設定分組模型（plan §2）。

M0 只建這五張表；其餘在需要它們的里程碑用 Alembic 增量加（progress.md 偏差與決定）。
"""

from berth.models.auth import User, UserSession
from berth.models.base import Base
from berth.models.event import Event
from berth.models.issue import Issue, subject_of
from berth.models.job import Job, JobFile
from berth.models.ledger import HARDLINK, LedgerEntry
from berth.models.media import (
    Media,
    MediaCard,
    TmdbCache,
    dump_cards,
    load_cards,
    media_id,
    parse_media_id,
)
from berth.models.plan import Plan, PlanItem
from berth.models.route import Route, RouteHealth
from berth.models.rss import DEFAULT_INTERVAL_SEC, RssFeed, RssItem, RssSeries
from berth.models.setting import (
    DEFAULT_BUNDLED_LIBRARIES,
    SETTINGS_GROUPS,
    BundledLibrary,
    DiskSettings,
    HealthSettings,
    IndexerSettings,
    JellyfinSettings,
    PathSettings,
    PollerSettings,
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
    UnknownTorrent,
)

__all__ = [
    "DEFAULT_BUNDLED_LIBRARIES",
    "DEFAULT_INTERVAL_SEC",
    "HARDLINK",
    "SETTINGS_GROUPS",
    "Base",
    "BundledLibrary",
    "DiskSettings",
    "Event",
    "HealthSettings",
    "IndexerSettings",
    "Issue",
    "JellyfinSettings",
    "Job",
    "JobFile",
    "LedgerEntry",
    "Media",
    "MediaCard",
    "PathSettings",
    "Plan",
    "PlanItem",
    "PollerSettings",
    "QbittorrentSettings",
    "Route",
    "RouteHealth",
    "RssFeed",
    "RssItem",
    "RssSeries",
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
    "TmdbCache",
    "TmdbSettings",
    "UnknownTorrent",
    "User",
    "UserSession",
    "dump_cards",
    "load_cards",
    "media_id",
    "parse_media_id",
    "subject_of",
]
