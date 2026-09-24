"""執行環境設定：路徑常數與 port，全部可用環境變數覆寫（plan §1.1）。

預設值是容器內的佈局（`/config`、`/data`）；本機開發時覆寫成可寫的目錄。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

PACKAGE_NAME = "berth"
VERSION = version(PACKAGE_NAME)

DEFAULT_CONFIG_ROOT = Path("/config")
DEFAULT_DATA_ROOT = Path("/data")
#: 其他服務唯讀掛進來的設定目錄；目前只有 `prowlarr/config.xml`（plan §9.1）。
DEFAULT_EXT_ROOT = Path("/ext")
DEFAULT_PORT = 8383
#: 套件內 Jellyfin 與 qBittorrent WebUI 在宿主上發佈的 port（compose 的 `JELLYFIN_PORT`、
#: `QBITTORRENT_WEBUI_PORT`，plan §9.1）。Berth 在容器裡看不到宿主那一側，只能由 compose 傳進來。
DEFAULT_JELLYFIN_PORT = 8096
DEFAULT_QBITTORRENT_WEBUI_PORT = 8080

#: repo 佈局下 `pnpm -C web build` 的產出；container 內由 `WEB_ROOT` 指向 image 的複製位置。
DEFAULT_WEB_ROOT = Path(__file__).resolve().parent.parent / "web" / "dist"

DATABASE_FILENAME = "berth.db"


@dataclass(frozen=True, slots=True)
class Config:
    """一次載入、之後唯讀；需要它的模組以參數接收，不從全域抓。"""

    config_root: Path
    data_root: Path
    ext_root: Path
    web_root: Path
    port: int
    #: 瀏覽器開深連結用的 port；容器內的 Jellyfin 永遠在 8096（`services/deeplink.py`）。
    jellyfin_port: int
    #: 內外兩側同一個號碼：Host 檢查連 port 都比對（plan §9.2），所以 compose 內網也在這一個上。
    qbittorrent_webui_port: int

    @property
    def database_path(self) -> Path:
        return self.config_root / DATABASE_FILENAME

    @property
    def prowlarr_config_path(self) -> Path:
        return self.ext_root / "prowlarr" / "config.xml"


def load_config(environ: Mapping[str, str] | None = None) -> Config:
    env = os.environ if environ is None else environ

    return Config(
        config_root=_path(env, "CONFIG_ROOT", DEFAULT_CONFIG_ROOT),
        data_root=_path(env, "DATA_ROOT", DEFAULT_DATA_ROOT),
        ext_root=_path(env, "EXT_ROOT", DEFAULT_EXT_ROOT),
        web_root=_path(env, "WEB_ROOT", DEFAULT_WEB_ROOT),
        port=_port(env, "PORT", DEFAULT_PORT),
        jellyfin_port=_port(env, "JELLYFIN_PORT", DEFAULT_JELLYFIN_PORT),
        qbittorrent_webui_port=_port(env, "QBITTORRENT_WEBUI_PORT", DEFAULT_QBITTORRENT_WEBUI_PORT),
    )


def _path(env: Mapping[str, str], name: str, default: Path) -> Path:
    raw = env.get(name)
    return default if raw is None or not raw.strip() else Path(raw)


def _port(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
