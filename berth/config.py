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
DEFAULT_PORT = 8383

#: repo 佈局下 `pnpm -C web build` 的產出；container 內由 `WEB_ROOT` 指向 image 的複製位置。
DEFAULT_WEB_ROOT = Path(__file__).resolve().parent.parent / "web" / "dist"

DATABASE_FILENAME = "berth.db"


@dataclass(frozen=True, slots=True)
class Config:
    """一次載入、之後唯讀；需要它的模組以參數接收，不從全域抓。"""

    config_root: Path
    data_root: Path
    web_root: Path
    port: int

    @property
    def database_path(self) -> Path:
        return self.config_root / DATABASE_FILENAME


def load_config(environ: Mapping[str, str] | None = None) -> Config:
    env = os.environ if environ is None else environ

    return Config(
        config_root=_path(env, "CONFIG_ROOT", DEFAULT_CONFIG_ROOT),
        data_root=_path(env, "DATA_ROOT", DEFAULT_DATA_ROOT),
        web_root=_path(env, "WEB_ROOT", DEFAULT_WEB_ROOT),
        port=_port(env),
    )


def _path(env: Mapping[str, str], name: str, default: Path) -> Path:
    raw = env.get(name)
    return default if raw is None or not raw.strip() else Path(raw)


def _port(env: Mapping[str, str]) -> int:
    raw = env.get("PORT")
    if raw is None or not raw.strip():
        return DEFAULT_PORT
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"PORT must be an integer, got {raw!r}") from exc
