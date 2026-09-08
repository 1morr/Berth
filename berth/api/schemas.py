"""跨 router 共用的回應形狀（plan §6）。

一條纜繩、一個 Route、一個 qBittorrent 偏好差異這三種東西同時出現在精靈、健康頁與設定頁。
形狀寫兩份的話，改了一邊另一邊會悄悄回舊欄位，而前端的型別只會抓到其中一個。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from berth.domain import (
    CollectionType,
    HealthStatus,
    Profile,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.services.health import CHECK_INTERVAL, HealthReport, Status


class StepOut(BaseModel):
    """一條纜繩：精靈的一步，或一個 Route 的一項檢查。"""

    model_config = ConfigDict(from_attributes=True)

    step: str
    status: StepStatus
    #: 實測值：版本號、建了哪幾個媒體庫、任務 id。UI 直接顯示，不翻譯。
    detail: str
    #: 失敗時服務回的原文（英文）。
    error: str


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    #: Jellyfin 媒體庫的名字。
    library: str
    collection_type: CollectionType
    target_path: str
    category: str
    #: 這個 category 的 save path，也就是硬鏈接的來源目錄。
    save_path: str
    profile: Profile
    enabled: bool
    health: HealthStatus
    #: 逐項檢查，`step` 是 `RouteCheck`。形狀與其他泊位的纜繩一樣。
    checks: list[StepOut]
    #: 硬鏈接回 `EXDEV`：兩個目錄在 Berth 內是不同掛載（brief §4.4）。
    cross_device: bool
    checked_at: datetime | None
    #: 最後一次五條纜繩全綠的時間（brief §16.2）。
    last_ok_at: datetime | None


class PreferenceDiffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: `app/setPreferences` 的鍵名。畫面顯示的與送出去的是同一個字串。
    key: str
    current: str
    recommended: str
    differs: bool


class QbittorrentOut(BaseModel):
    """精靈第 4 步與設定頁的漂移還原共用（brief §16.3）。"""

    model_config = ConfigDict(from_attributes=True)

    origin: ServiceOrigin
    base_url: str
    version: str
    webapi_version: str
    supported: bool
    blocked: bool
    reachable: bool
    diffs: list[PreferenceDiffOut]
    steps: list[StepOut]
    temp_path_warning: bool
    sets_password: bool
    error: str


class ServiceHealthOut(BaseModel):
    """健康頁與設定頁上一個服務那一列。"""

    model_config = ConfigDict(from_attributes=True)

    kind: ServiceKind
    #: 套件內還是既有。修正建議分兩種，畫面照它挑。
    origin: ServiceOrigin
    base_url: str
    status: HealthStatus
    #: 實測值：版本號、索引站數量。UI 直接顯示，不翻譯。
    detail: str
    #: 失敗時服務回的原文（英文）。
    error: str
    checked_at: datetime | None
    #: 最後一次成功的時間（brief §16.2）。
    last_ok_at: datetime | None
    failures: int
    #: 有連線資訊可以檢查。索引站那一步可跳過，所以它可能是 False。
    configured: bool
    #: 被改掉的建議偏好鍵（qBittorrent 專有，brief §16.3）。
    drift: list[str]


class HealthDetailOut(BaseModel):
    """四項檢查的明細。健康頁與設定頁讀的是同一份——同一件事不該有兩種說法。"""

    model_config = ConfigDict(from_attributes=True)

    #: 與匿名那一支的 `status` 同一個判定。
    status: Status
    checked_at: datetime | None
    #: 檢查間隔（秒）。畫面用它說「上次檢查」落後多久才算不新鮮。
    interval_seconds: int
    services: list[ServiceHealthOut]
    #: 第四項：所有 Route 的總結。
    routes_status: HealthStatus
    routes: list[RouteOut]


def health_detail(report: HealthReport) -> HealthDetailOut:
    return HealthDetailOut(
        status="degraded" if report.degraded else "ok",
        checked_at=report.checked_at,
        interval_seconds=int(CHECK_INTERVAL.total_seconds()),
        services=[ServiceHealthOut.model_validate(row) for row in report.services],
        routes_status=report.routes_status,
        routes=[RouteOut.model_validate(row) for row in report.routes],
    )
