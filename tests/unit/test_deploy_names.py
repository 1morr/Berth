"""部署套件的容器名與 `berth` 連宿主的那一條（M4 票 16、plan §9.1）。

- 套件內三台的 `container_name` 是 `berth-<服務名>`：同一台主機上既有的容器多半就叫 `jellyfin` /
  `qbittorrent` / `prowlarr`，撞名時 `docker compose up -d` 整套都起不來（brief §20.14）。
  `berth` 維持。
- **compose 服務名不變**：Berth 以服務名（compose 網路上的 DNS 名）連套件內那三台
  （`bundled_targets`），profile 也與它同名（`.env` 的 `COMPOSE_PROFILES`）。
- `berth` 帶 `extra_hosts: host.docker.internal:host-gateway`：Linux 上 Berth 才連得到宿主上的既有
  服務；Docker Desktop 本來就有這個名字（brief §16.4）。

比對的是 compose 展開之後的資料，排版、註解、錨點、`extra_hosts` 寫成清單或對照表都不影響。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import pytest

from berth.config import load_config
from berth.domain.enums import ServiceKind
from berth.services.clients import bundled_targets
from tests.unit.test_deploy_ports import COMPOSE, REQUIRED, Change, mutated, render

HOST_GATEWAY = ("host.docker.internal", "host-gateway")


def extra_hosts(service: Mapping[str, Any]) -> set[tuple[str, str]]:
    """compose 收兩種寫法：`["name:ip"]`（或 `name=ip`）的清單，與 `{name: ip}` 的對照表。"""
    hosts = service.get("extra_hosts") or []
    if isinstance(hosts, Mapping):
        return {(str(name), str(address)) for name, address in hosts.items()}
    pairs = (re.split(r"[:=]", str(entry), maxsplit=1) for entry in hosts)
    return {(name.strip(), address.strip()) for name, address in pairs}


def violations(compose: str) -> list[str]:
    services = render(compose, REQUIRED)["services"]
    problems: list[str] = []

    if services["berth"].get("container_name") != "berth":
        problems.append(f"berth container_name: {services['berth'].get('container_name')!r}")
    if HOST_GATEWAY not in extra_hosts(services["berth"]):
        problems.append(f"berth extra_hosts: {services['berth'].get('extra_hosts')!r}")

    hosts = {kind: urlsplit(url).hostname for kind, url in bundled_targets(load_config({})).items()}
    for kind in ServiceKind:
        service = services.get(hosts[kind])
        if service is None:
            problems.append(f"{kind}: no compose service named {hosts[kind]!r}")
            continue
        if service.get("profiles") != [hosts[kind]]:
            problems.append(f"{kind} profiles: {service.get('profiles')!r}")
        if service.get("container_name") != f"berth-{hosts[kind]}":
            problems.append(f"{kind} container_name: {service.get('container_name')!r}")
    return problems


def test_bundled_containers_are_prefixed_and_berth_reaches_the_host() -> None:
    assert violations(COMPOSE.read_text(encoding="utf-8")) == []


# --- 規則本身的變異驗證：造一個違規證明它會紅，改一次無關的寫法證明它不會紅。 ---


def _unprefixed(kind: str) -> Change:
    def change(services: dict[str, Any]) -> None:
        services[kind]["container_name"] = kind

    change.__name__ = f"_{kind}_unprefixed"
    return change


def _renamed_service(services: dict[str, Any]) -> None:
    """容器名對了，但服務名（Berth 連的 DNS 名）被改成容器名。"""
    services["berth-qbittorrent"] = services.pop("qbittorrent")


def _renamed_profile(services: dict[str, Any]) -> None:
    services["prowlarr"]["profiles"] = ["berth-prowlarr"]


def _berth_renamed(services: dict[str, Any]) -> None:
    services["berth"]["container_name"] = "berth-berth"


def _no_extra_hosts(services: dict[str, Any]) -> None:
    del services["berth"]["extra_hosts"]


def _extra_hosts_elsewhere(services: dict[str, Any]) -> None:
    services["jellyfin"]["extra_hosts"] = services["berth"].pop("extra_hosts")


def _wrong_gateway(services: dict[str, Any]) -> None:
    services["berth"]["extra_hosts"] = ["host.docker.internal:172.28.0.1"]


@pytest.mark.parametrize(
    "change",
    [
        _unprefixed("jellyfin"),
        _unprefixed("qbittorrent"),
        _unprefixed("prowlarr"),
        _renamed_service,
        _renamed_profile,
        _berth_renamed,
        _no_extra_hosts,
        _extra_hosts_elsewhere,
        _wrong_gateway,
    ],
    ids=lambda change: change.__name__,
)
def test_a_name_or_host_that_breaks_the_contract_is_caught(change: Change) -> None:
    compose = mutated(change)
    assert compose != mutated(lambda services: None), "the mutation did not change anything"

    assert violations(compose) != []


def _extra_hosts_as_mapping(services: dict[str, Any]) -> None:
    services["berth"]["extra_hosts"] = {"host.docker.internal": "host-gateway"}


def _extra_hosts_with_equals(services: dict[str, Any]) -> None:
    services["berth"]["extra_hosts"] = ["host.docker.internal=host-gateway"]


@pytest.mark.parametrize(
    "change",
    [lambda services: None, _extra_hosts_as_mapping, _extra_hosts_with_equals],
    ids=["rewritten", "extra_hosts_as_mapping", "extra_hosts_with_equals"],
)
def test_rewriting_the_yaml_is_not_a_violation(change: Change) -> None:
    """錨點展開、鍵排序、註解全沒了的同一份 compose；`extra_hosts` 換成 compose 收的另一種寫法。"""
    compose = mutated(change)
    assert compose != COMPOSE.read_text(encoding="utf-8")

    assert violations(compose) == []
