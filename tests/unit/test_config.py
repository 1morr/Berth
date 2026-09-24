"""環境變數解析：`CONFIG_ROOT`、`DATA_ROOT`、`WEB_ROOT`、`PORT`、`JELLYFIN_PORT`、
`QBITTORRENT_WEBUI_PORT` 是對外承諾的介面。"""

from __future__ import annotations

from pathlib import Path

import pytest

from berth.config import (
    DEFAULT_JELLYFIN_PORT,
    DEFAULT_PORT,
    DEFAULT_QBITTORRENT_WEBUI_PORT,
    Config,
    load_config,
)


def test_defaults_match_the_container_layout() -> None:
    config = load_config({})

    assert config.config_root == Path("/config")
    assert config.data_root == Path("/data")
    assert config.port == DEFAULT_PORT == 8383


def test_bundled_service_ports_default_to_the_ones_the_compose_file_publishes() -> None:
    """compose 沒傳這兩個變數時（`.env` 還是舊的那一份）就是套件原本的 8096 與 8080。"""
    config = load_config({})

    assert config.jellyfin_port == DEFAULT_JELLYFIN_PORT == 8096
    assert config.qbittorrent_webui_port == DEFAULT_QBITTORRENT_WEBUI_PORT == 8080


def test_web_root_defaults_to_the_vite_build_output_next_to_the_package() -> None:
    config = load_config({})

    assert config.web_root.name == "dist"
    assert config.web_root.parent.name == "web"


def test_every_path_and_port_can_be_overridden(tmp_path: Path) -> None:
    config = load_config(
        {
            "CONFIG_ROOT": str(tmp_path / "cfg"),
            "DATA_ROOT": str(tmp_path / "media"),
            "WEB_ROOT": str(tmp_path / "dist"),
            "PORT": "9000",
            "JELLYFIN_PORT": "18096",
            "QBITTORRENT_WEBUI_PORT": "18080",
        }
    )

    assert config.config_root == tmp_path / "cfg"
    assert config.data_root == tmp_path / "media"
    assert config.web_root == tmp_path / "dist"
    assert config.port == 9000
    assert config.jellyfin_port == 18096
    assert config.qbittorrent_webui_port == 18080


def test_database_lives_directly_under_config_root(tmp_path: Path) -> None:
    config = load_config({"CONFIG_ROOT": str(tmp_path)})

    assert config.database_path == tmp_path / "berth.db"


@pytest.mark.parametrize("name", ["PORT", "JELLYFIN_PORT", "QBITTORRENT_WEBUI_PORT"])
def test_non_numeric_port_names_the_offending_variable(name: str) -> None:
    with pytest.raises(ValueError, match=f"^{name} must be an integer"):
        load_config({name: "not-a-port"})


def test_config_is_immutable() -> None:
    config = load_config({})

    with pytest.raises(AttributeError):
        # 下面的 ignore 是刻意的：這一行就是要證明 frozen dataclass 會擋下賦值。
        config.port = 1  # type: ignore[misc]


def test_load_config_reads_os_environ_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CONFIG_ROOT", str(tmp_path))

    assert load_config().config_root == tmp_path


def test_config_can_be_built_directly_without_the_environment(tmp_path: Path) -> None:
    config = Config(
        config_root=tmp_path,
        data_root=tmp_path,
        ext_root=tmp_path,
        web_root=tmp_path,
        port=DEFAULT_PORT,
        jellyfin_port=DEFAULT_JELLYFIN_PORT,
        qbittorrent_webui_port=DEFAULT_QBITTORRENT_WEBUI_PORT,
    )

    assert config.database_path == tmp_path / "berth.db"
