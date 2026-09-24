"""部署套件的五個對外 port 在 `.env`（票 06b、plan §9.1）。

Berth 在容器裡看不到宿主那一側，所以對外 port 只能由 compose 從 `.env` 讀、再傳給需要它的
容器。這裡守三件事：

- 五個變數都在 `deploy/.env.example`，預設值是套件原本的號碼；compose 裡省略時也是它們。
- `JELLYFIN_PORT` 與 `QBITTORRENT_WEBUI_PORT` 同時傳給 `berth`（深連結的 port、套件內 qBittorrent
  的位址）。
- qBittorrent 的兩個 port 內外兩側一起換：WebUI 的 Host 檢查連 port 都比對（plan §9.2），BT 對外
  公告的 port 要與實際連得進來的一致。

比對的是 compose **展開之後**的值，不是原始碼裡的字串——排版、註解、錨點怎麼寫都不影響。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
COMPOSE = DEPLOY / "docker-compose.yml"
ENV_EXAMPLE = DEPLOY / ".env.example"

DEFAULTS = {
    "BERTH_PORT": "8383",
    "JELLYFIN_PORT": "8096",
    "QBITTORRENT_WEBUI_PORT": "8080",
    "QBITTORRENT_BT_PORT": "6881",
    "PROWLARR_PORT": "9696",
}

#: 與預設值兩兩不同的一組，展開之後才分得出每個位置用的是哪一個變數。
MOVED = {
    "BERTH_PORT": "18383",
    "JELLYFIN_PORT": "18096",
    "QBITTORRENT_WEBUI_PORT": "18080",
    "QBITTORRENT_BT_PORT": "16881",
    "PROWLARR_PORT": "19696",
}

#: compose 用 `:?` 要求一定要有的兩個；與 port 無關，只是展開得下去。
REQUIRED = {"CONFIG_ROOT": "./config", "DATA_ROOT": "./data"}

_INTERPOLATION = re.compile(r"\$\$|\$\{(\w+)(?:(:?[-?])([^}]*))?\}")


def interpolate(value: str, env: Mapping[str, str]) -> str:
    """compose 的 `${VAR}`、`${VAR:-default}`、`${VAR-default}`、`${VAR:?message}` 與 `$$`。"""

    def expand(match: re.Match[str]) -> str:
        if match.group(0) == "$$":
            return "$"
        name, operator, argument = match.groups()
        value = env.get(name)
        unset = value is None or (operator is not None and operator.startswith(":") and not value)
        if unset and operator in (":-", "-"):
            return str(argument)
        if unset and operator in (":?", "?"):
            raise KeyError(f"{name}: {argument}")
        return value or ""

    return _INTERPOLATION.sub(expand, value)


def render(compose: str, env: Mapping[str, str]) -> dict[str, Any]:
    """讀 YAML（錨點與 `<<` 由 YAML 自己合併），再把每個字串照 `env` 展開。"""

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {key: walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(value) for value in node]
        if isinstance(node, str):
            return interpolate(node, env)
        return node

    rendered: dict[str, Any] = walk(yaml.safe_load(compose))
    return rendered


def env_file(text: str) -> dict[str, str]:
    """`.env` 的 `KEY=VALUE` 列；註解與空行略過。"""
    pairs = (
        line.split("=", 1)
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return {key.strip(): value.strip() for key, value in pairs}


def published(compose: str, env: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """每個服務展開之後的 port 與環境變數（全部轉成字串，YAML 的 `8080` 是 int）。"""
    services = render(compose, {**REQUIRED, **env})["services"]
    return {
        name: {
            "ports": sorted(str(port) for port in service.get("ports", [])),
            "environment": {
                key: str(value) for key, value in (service.get("environment") or {}).items()
            },
            "healthcheck": " ".join(service.get("healthcheck", {}).get("test", [])),
        }
        for name, service in services.items()
    }


def violations(compose: str, env_example: str) -> list[str]:
    problems: list[str] = []
    example = env_file(env_example)
    for name, default in DEFAULTS.items():
        if example.get(name) != default:
            problems.append(f".env.example: {name} should be {default}, got {example.get(name)}")

    # 沒設（舊的 `.env`）與照 `.env.example` 設，都要是套件原本的號碼。
    for label, env in (("unset", {}), (".env.example", example)):
        problems += [f"{label}: {problem}" for problem in _placed(compose, env, DEFAULTS)]
    problems += [f"moved: {problem}" for problem in _placed(compose, MOVED, MOVED)]
    return problems


def _placed(compose: str, env: Mapping[str, str], ports: Mapping[str, str]) -> list[str]:
    services = published(compose, env)
    berth, qbittorrent = services["berth"], services["qbittorrent"]
    webui, bt = ports["QBITTORRENT_WEBUI_PORT"], ports["QBITTORRENT_BT_PORT"]
    expected: list[tuple[str, object, object]] = [
        ("berth ports", berth["ports"], [f"{ports['BERTH_PORT']}:8383"]),
        ("jellyfin ports", services["jellyfin"]["ports"], [f"{ports['JELLYFIN_PORT']}:8096"]),
        ("prowlarr ports", services["prowlarr"]["ports"], [f"{ports['PROWLARR_PORT']}:9696"]),
        (
            "berth JELLYFIN_PORT",
            berth["environment"].get("JELLYFIN_PORT"),
            ports["JELLYFIN_PORT"],
        ),
        ("berth QBITTORRENT_WEBUI_PORT", berth["environment"].get("QBITTORRENT_WEBUI_PORT"), webui),
        (
            "qbittorrent ports",
            qbittorrent["ports"],
            sorted([f"{webui}:{webui}", f"{bt}:{bt}", f"{bt}:{bt}/udp"]),
        ),
        ("qbittorrent WEBUI_PORT", qbittorrent["environment"].get("WEBUI_PORT"), webui),
        ("qbittorrent TORRENTING_PORT", qbittorrent["environment"].get("TORRENTING_PORT"), bt),
        (
            "qbittorrent healthcheck",
            f"localhost:{webui}/" in qbittorrent["healthcheck"],
            True,
        ),
    ]
    return [f"{what}: {got!r} != {want!r}" for what, got, want in expected if got != want]


def test_the_deploy_files_publish_every_port_from_the_env_file() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert violations(compose, env_example) == []


# --- 規則本身的變異驗證：造一個違規證明它會紅，改一次無關的寫法證明它不會紅。 ---


type Change = Callable[[dict[str, Any]], None]


def mutated(change: Change) -> str:
    """把 compose 讀成資料、改一處、寫回 YAML（註解與錨點全部沒了，排版也換了）。"""
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    change(data["services"])
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=True)


def _drop_berth_jellyfin_port(services: dict[str, Any]) -> None:
    del services["berth"]["environment"]["JELLYFIN_PORT"]


def _drop_berth_qbittorrent_port(services: dict[str, Any]) -> None:
    del services["berth"]["environment"]["QBITTORRENT_WEBUI_PORT"]


def _webui_inside_fixed(services: dict[str, Any]) -> None:
    services["qbittorrent"]["ports"] = [
        re.sub(r":\$\{QBITTORRENT_WEBUI_PORT[^}]*\}$", ":8080", str(port))
        for port in services["qbittorrent"]["ports"]
    ]


def _webui_setting_fixed(services: dict[str, Any]) -> None:
    services["qbittorrent"]["environment"]["WEBUI_PORT"] = 8080


def _bt_inside_fixed(services: dict[str, Any]) -> None:
    services["qbittorrent"]["ports"] = [
        re.sub(r":\$\{QBITTORRENT_BT_PORT[^}]*\}", ":6881", str(port))
        for port in services["qbittorrent"]["ports"]
    ]


def _healthcheck_fixed(services: dict[str, Any]) -> None:
    services["qbittorrent"]["healthcheck"]["test"] = [
        "CMD-SHELL",
        "curl -fsS http://localhost:8080/ >/dev/null",
    ]


def _published_fixed(service: str, port: str) -> Change:
    def change(services: dict[str, Any]) -> None:
        services[service]["ports"] = [port]

    change.__name__ = f"_{service}_published_fixed"
    return change


@pytest.mark.parametrize(
    "change",
    [
        _drop_berth_jellyfin_port,
        _drop_berth_qbittorrent_port,
        _webui_inside_fixed,
        _webui_setting_fixed,
        _bt_inside_fixed,
        _healthcheck_fixed,
        _published_fixed("berth", "8383:8383"),
        _published_fixed("jellyfin", "8096:8096"),
        _published_fixed("prowlarr", "9696:9696"),
    ],
    ids=lambda change: change.__name__,
)
def test_a_port_that_does_not_follow_the_env_file_is_caught(change: Change) -> None:
    compose = mutated(change)
    assert compose != mutated(lambda services: None), "the mutation did not change anything"

    assert violations(compose, ENV_EXAMPLE.read_text(encoding="utf-8")) != []


def test_a_variable_missing_from_the_env_example_is_caught() -> None:
    env_example = ENV_EXAMPLE.read_text(encoding="utf-8")
    without = "\n".join(
        line for line in env_example.splitlines() if not line.startswith("PROWLARR_PORT=")
    )
    assert without != env_example

    assert violations(COMPOSE.read_text(encoding="utf-8"), without) != []


def test_rewriting_the_yaml_and_the_comments_is_not_a_violation() -> None:
    """錨點展開、鍵排序、註解全沒了的同一份 compose；`.env.example` 的註解整段換掉。"""
    compose = mutated(lambda services: None)
    env_example = re.sub(
        r"^#.*$",
        "# reworded",
        ENV_EXAMPLE.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert compose != COMPOSE.read_text(encoding="utf-8")

    assert violations(compose, env_example) == []
