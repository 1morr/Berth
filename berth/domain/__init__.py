"""純資料型別與狀態機，無 IO（plan §1.2）。"""

from berth.domain.enums import (
    CollectionType,
    DetectionReason,
    HealthStatus,
    Profile,
    Role,
    ServiceKind,
    ServiceOrigin,
)

__all__ = [
    "CollectionType",
    "DetectionReason",
    "HealthStatus",
    "Profile",
    "Role",
    "ServiceKind",
    "ServiceOrigin",
]
