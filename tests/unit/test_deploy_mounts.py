"""部署用 compose 的宿主路徑一律不相對（M4 票 71、brief §19 E4、§20.18）。

部署只剩 compose 檔加 `.env`：使用者把它貼進 Unraid 的 Compose Manager（檔案在隨身碟上的
`/boot/config/plugins/compose.manager/projects/<名稱>/`），或放進任何一個資料夾。compose 字面寫的
相對路徑因此指到一個沒有東西的地方——`docker compose up` 不報錯，Docker 替它建一個空目錄（票 70
之前的 `./preseed/qbittorrent` 就是這樣讓 Berth 進不去 qBittorrent），或把資料寫進隨身碟。

所以每個宿主路徑（bind 掛載的來源、頂層 `configs` / `secrets` 的 `file`）都得是 `${變數}`
開頭或絕對路徑。比對的是展開之後的資料：兩個資料根給絕對路徑，展開之後還是相對的，就是
compose 字面寫死的。`.env.example` 的 `./data`、`./config` 是使用者的值，不歸這裡管（它的註解說了
Unraid 要用絕對路徑）。
named volume 不是宿主路徑，不算。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import yaml

from tests.unit.test_deploy_ports import COMPOSE, render

#: 兩個資料根給絕對路徑，展開之後剩下的相對路徑就只有 compose 字面寫的那幾條。
ABSOLUTE_ROOTS = {"CONFIG_ROOT": "/config-root", "DATA_ROOT": "/data-root"}


def _is_host_path(source: str) -> bool:
    """compose 短語法的來源：有 `/` 或以 `.` / `~` 開頭是宿主路徑，否則是 named volume 的名字。"""
    return "/" in source or source.startswith((".", "~"))


def host_paths(compose: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for service in compose.get("services", {}).values():
        for volume in service.get("volumes", []):
            if isinstance(volume, Mapping):
                if volume.get("type") == "bind":
                    paths.append(str(volume.get("source", "")))
                continue
            source = str(volume).split(":", 1)[0]
            if _is_host_path(source):
                paths.append(source)
    for top in ("configs", "secrets"):
        for definition in (compose.get(top) or {}).values():
            if "file" in definition:
                paths.append(str(definition["file"]))
    return paths


def violations(compose: str) -> list[str]:
    return [
        f"relative host path: {path}"
        for path in host_paths(render(compose, ABSOLUTE_ROOTS))
        if not path.startswith("/")
    ]


def test_every_host_path_in_the_deploy_compose_is_a_variable_or_absolute() -> None:
    assert violations(COMPOSE.read_text(encoding="utf-8")) == []


# --- 規則本身的變異驗證：造一個違規證明它會紅，改一次無關的寫法證明它不會紅。 ---


def _edited(change: Callable[[dict[str, Any]], None]) -> str:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    change(data)
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=True)


def test_a_relative_short_syntax_mount_is_caught() -> None:
    compose = _edited(lambda data: data["services"]["berth"]["volumes"].append("./x:/y"))

    assert violations(compose) == ["relative host path: ./x"]


def test_a_relative_long_syntax_bind_is_caught() -> None:
    def change(data: dict[str, Any]) -> None:
        data["services"]["qbittorrent"]["volumes"].append(
            {"type": "bind", "source": "preseed/qbittorrent", "target": "/custom-cont-init.d"}
        )

    assert violations(_edited(change)) == ["relative host path: preseed/qbittorrent"]


def test_a_config_read_from_a_relative_file_is_caught() -> None:
    def change(data: dict[str, Any]) -> None:
        data["configs"]["qbittorrent-preseed"] = {"file": "./10-berth.sh"}

    assert violations(_edited(change)) == ["relative host path: ./10-berth.sh"]


def test_renaming_a_service_and_editing_a_comment_is_not_a_violation() -> None:
    def rename(data: dict[str, Any]) -> None:
        data["services"]["indexer"] = data["services"].pop("prowlarr")

    commented = COMPOSE.read_text(encoding="utf-8").replace(
        "# berth has no profile and always starts.", "# berth starts every time, profile or not."
    )

    assert commented != COMPOSE.read_text(encoding="utf-8")
    assert violations(commented) == []
    assert violations(_edited(rename)) == []


def test_named_volumes_and_absolute_paths_are_not_violations() -> None:
    def change(data: dict[str, Any]) -> None:
        data["services"]["berth"]["volumes"] += ["berth-cache:/cache", "/etc/localtime:/x:ro"]

    assert violations(_edited(change)) == []
