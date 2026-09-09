"""純資料型別與狀態機，無 IO（plan §1.2）。"""

from berth.domain.enums import (
    PROWLARR_LOGIN_STEP,
    CollectionType,
    DetectionReason,
    DiscoverProblem,
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
)

__all__ = [
    "PROWLARR_LOGIN_STEP",
    "CollectionType",
    "DetectionReason",
    "DiscoverProblem",
    "HealthStatus",
    "IndexerKind",
    "JellyfinStep",
    "MediaKind",
    "Profile",
    "QbittorrentStep",
    "Role",
    "RouteCheck",
    "ServiceKind",
    "ServiceOrigin",
    "StepStatus",
]
