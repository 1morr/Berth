"""純資料型別與狀態機，無 IO（plan §1.2）。"""

from berth.domain.enums import (
    CollectionType,
    DetectionReason,
    HealthStatus,
    JellyfinStep,
    Profile,
    Role,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)

__all__ = [
    "CollectionType",
    "DetectionReason",
    "HealthStatus",
    "JellyfinStep",
    "Profile",
    "Role",
    "ServiceKind",
    "ServiceOrigin",
    "StepStatus",
]
