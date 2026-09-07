"""設定：一列一個分組，值是對應的 pydantic model（plan §2.1）。

分組模型是設定的唯一結構來源；DB 只存它們序列化後的 JSON，未設定時回模型的預設值。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import DetectionReason, ServiceKind, ServiceOrigin
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, utcnow


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JsonText)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)


class SettingsGroup(BaseModel):
    """一個設定分組。`KEY` 是它在 `settings` 表的鍵。"""

    #: 舊版本寫下的欄位被移除後仍要讀得回來，所以多餘的鍵忽略而不是報錯。
    model_config = ConfigDict(extra="ignore")

    KEY: ClassVar[str]


class JellyfinSettings(SettingsGroup):
    KEY = "services.jellyfin"

    base_url: str = ""
    api_key: str = ""


class QbittorrentSettings(SettingsGroup):
    KEY = "services.qbittorrent"

    base_url: str = ""
    username: str = ""
    password: str = ""


class IndexerSettings(SettingsGroup):
    KEY = "services.indexer"

    #: Prowlarr 或任意 Torznab 端點（Jackett 之類，plan §9.3 第 5 步）。
    kind: Literal["prowlarr", "torznab"] = "prowlarr"
    base_url: str = ""
    api_key: str = ""


class TmdbSettings(SettingsGroup):
    KEY = "services.tmdb"

    api_key: str = ""


class PathSettings(SettingsGroup):
    KEY = "paths"

    #: qBittorrent 的全域 temp path 與 category save path 的根（brief §4.1）。
    incomplete_root: str = "/data/torrent/incomplete"
    complete_root: str = "/data/torrent/complete"


class SetupAdmin(BaseModel):
    """精靈第 1 步建立的管理員（plan §9.3）。

    密碼是明文的：第 3 步要拿它去建 Jellyfin 管理員，第 4 步要拿它設 qBittorrent 的 WebUI 密碼，
    雜湊做不到這兩件事。Berth 自己從不驗證這組密碼——登入一律走 Jellyfin（brief §11）。
    秘密只靠檔案權限保護，與其他 `settings.services.*` 的 key 與密碼一致（brief §16.2）。
    """

    model_config = ConfigDict(extra="ignore")

    username: str = ""
    password: str = ""
    #: 「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」，預設勾。
    apply_to_services: bool = True


class ServiceProbe(BaseModel):
    """精靈第 2 步對單一服務的判定結果。"""

    model_config = ConfigDict(extra="ignore")

    origin: ServiceOrigin
    reason: DetectionReason
    #: 探測到的實測值：版本號或索引站數量。沒有就是空字串。
    detail: str = ""
    base_url: str = ""
    checked_at: datetime
    #: 這個判定來自使用者填的連線表單，不是探測 compose 主機名的結果。
    #: 重探時要跳過它——它根本不在那個主機名上。
    configured: bool = False


class SetupSettings(SettingsGroup):
    KEY = "setup"

    completed: bool = False
    admin: SetupAdmin = SetupAdmin()
    #: 逐服務的判定；鍵是 `ServiceKind`。
    services: dict[ServiceKind, ServiceProbe] = {}
    #: 本輪輪詢的起點，用來算 2 分鐘上限。全部服務都判定完就清掉。
    probe_started_at: datetime | None = None


#: 所有分組的清單，用來確認每一組都有預設值。
SETTINGS_GROUPS: tuple[type[SettingsGroup], ...] = (
    JellyfinSettings,
    QbittorrentSettings,
    IndexerSettings,
    TmdbSettings,
    PathSettings,
    SetupSettings,
)
