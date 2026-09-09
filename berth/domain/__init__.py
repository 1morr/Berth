"""純資料型別與狀態機，無 IO（plan §1.2）。"""

from berth.domain.enums import (
    PROWLARR_LOGIN_STEP,
    CollectionType,
    DetectionReason,
    HealthStatus,
    IndexerKind,
    JellyfinStep,
    MediaKind,
    Profile,
    QbittorrentStep,
    Role,
    RouteCheck,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
    TmdbProblem,
    collection_type_for,
)
from berth.domain.media import EpisodeSnapshot, MediaSnapshot, SeasonSnapshot

__all__ = [
    "PROWLARR_LOGIN_STEP",
    "CollectionType",
    "DetectionReason",
    "EpisodeSnapshot",
    "HealthStatus",
    "IndexerKind",
    "JellyfinStep",
    "MediaKind",
    "MediaSnapshot",
    "Profile",
    "QbittorrentStep",
    "Role",
    "RouteCheck",
    "SeasonSnapshot",
    "ServiceKind",
    "ServiceOrigin",
    "StepStatus",
    "TmdbProblem",
    "collection_type_for",
]
