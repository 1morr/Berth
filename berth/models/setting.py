"""設定：一列一個分組，值是對應的 pydantic model（plan §2.1）。

分組模型是設定的唯一結構來源；DB 只存它們序列化後的 JSON，未設定時回模型的預設值。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

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


class SetupSettings(SettingsGroup):
    KEY = "setup"

    completed: bool = False
    #: 精靈的第幾步（plan §9.3 共八步）。
    current_step: int = 1


#: 所有分組的清單，用來確認每一組都有預設值。
SETTINGS_GROUPS: tuple[type[SettingsGroup], ...] = (
    JellyfinSettings,
    QbittorrentSettings,
    IndexerSettings,
    TmdbSettings,
    PathSettings,
    SetupSettings,
)
