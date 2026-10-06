"""真服務 e2e 與同一台機器上的試跑環境並存（M4 票 34、README〈e2e〉）。

- **名字與宿主資源全部換掉**：專案名、每個容器名、網路名與子網、每個發佈到宿主的 port，都與
  `deploy/docker-compose.yml`（照它的預設值展開）不同；產品那一份掛宿主路徑（`CONFIG_ROOT` /
  `DATA_ROOT`）的每一條，在 e2e 都落到它自己宣告的 named volume。少換一個，`up` 就會撞上或掛進
  試跑環境的容器、網路或資料。
- **compose 的變數不外洩、也不被呼叫端蓋掉**：`stack.compose_env` 是呼叫端環境的拷貝，`e2e.env`
  的值優先；`stack.main` 不改呼叫端的環境，而且不論測試結果都 `down --volumes`。

比對的是展開之後的資料（`test_deploy_ports.render`），排版、註解與錨點不影響。
"""

from __future__ import annotations

import ipaddress
import os
import subprocess
from collections.abc import Callable, Mapping
from typing import Any

import pytest
import yaml

from tests.e2e import harness, stack
from tests.unit.test_deploy_ports import REQUIRED, render


def _loader() -> type[yaml.SafeLoader]:
    """compose 的合併標籤 `!override` 在這裡只要它底下的值。"""

    class Loader(yaml.SafeLoader):
        pass

    def plain(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node, deep=True)
        return loader.construct_scalar(node)  # type: ignore[arg-type]  # 只剩 ScalarNode

    Loader.add_constructor("!override", plain)
    return Loader


def load(text: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.load(text, Loader=_loader())  # SafeLoader 的子類
    return data


#: 產品那一份裡指向宿主路徑的兩個變數，展開成認得出來的記號：掛載來源含記號的那幾條要換掉。
_HOST_PATHS = {"CONFIG_ROOT": "@CONFIG_ROOT@", "DATA_ROOT": "@DATA_ROOT@"}


def _host_port(mapping: str) -> str:
    """`28080:28080/udp` → `28080/udp`；`127.0.0.1:8383:8383` → `8383/tcp`。"""
    *host, _target = mapping.split(":")
    protocol = mapping.rsplit("/", 1)[1] if "/" in mapping else "tcp"
    return f"{host[-1]}/{protocol}"


def _mounts(service: Mapping[str, Any]) -> dict[str, str]:
    """掛載點 → 來源（只認短寫法 `source:target[:mode]`，兩份檔案都是這樣寫）。"""
    pairs = (str(entry).split(":") for entry in service.get("volumes") or [])
    return {parts[1]: parts[0] for parts in pairs}


def violations(product_text: str, e2e_text: str, e2e_env: Mapping[str, str]) -> list[str]:
    product = render(product_text, REQUIRED)
    e2e = load(e2e_text)
    problems: list[str] = []

    if e2e.get("name") in (None, product.get("name")):
        problems.append(f"project name: {e2e.get('name')!r}")

    network = e2e.get("networks", {}).get("default", {})
    product_network = product["networks"]["default"]
    if network.get("name") in (None, product_network.get("name")):
        problems.append(f"network name: {network.get('name')!r}")
    subnets = [row["subnet"] for row in network.get("ipam", {}).get("config", [])]
    product_subnets = [row["subnet"] for row in product_network["ipam"]["config"]]
    overlaps = [
        (mine, theirs)
        for mine in subnets
        for theirs in product_subnets
        if ipaddress.ip_network(mine).overlaps(ipaddress.ip_network(theirs))
    ]
    if not subnets or overlaps:
        problems.append(f"subnet: {subnets!r} vs {product_subnets!r}")

    services = e2e.get("services", {})
    berth_ip = services.get("berth", {}).get("networks", {}).get("default", {}).get("ipv4_address")
    if not berth_ip or not any(
        ipaddress.ip_address(berth_ip) in ipaddress.ip_network(subnet) for subnet in subnets
    ):
        problems.append(f"berth ipv4_address: {berth_ip!r} not in {subnets!r}")
    whitelisted = services.get("qbittorrent", {}).get("environment", {}).get("BERTH_IP")
    if whitelisted != berth_ip:
        problems.append(f"qbittorrent BERTH_IP: {whitelisted!r} != berth {berth_ip!r}")

    product_names = {service.get("container_name") for service in product["services"].values()}
    for name in product["services"]:
        mine = services.get(name, {}).get("container_name")
        if mine is None or mine in product_names:
            problems.append(f"{name} container_name: {mine!r}")

    rendered = render(product_text, {**REQUIRED, **e2e_env})["services"]
    declared = set(e2e.get("volumes") or {})
    taken = {
        _host_port(str(row))
        for service in product["services"].values()
        for row in service.get("ports") or []
    }
    marked = render(product_text, _HOST_PATHS)["services"]
    for name, service in marked.items():
        for row in rendered[name].get("ports") or []:
            if (host := _host_port(str(row))) in taken:
                problems.append(f"{name} publishes the product's host port {host}")
        overridden = _mounts(services.get(name, {}))
        for target, source in _mounts(service).items():
            if not any(marker in source for marker in _HOST_PATHS.values()):
                continue
            effective = overridden.get(target, _mounts(rendered[name])[target])
            if effective not in declared:
                problems.append(f"{name} {target}: {effective!r} is not an e2e volume")
    return problems


def test_the_e2e_stack_shares_no_name_port_or_path_with_the_product() -> None:
    assert (
        violations(
            stack.PRODUCT_COMPOSE.read_text(encoding="utf-8"),
            stack.E2E_COMPOSE.read_text(encoding="utf-8"),
            stack.E2E_ENV,
        )
        == []
    )


def test_the_names_the_tests_use_are_the_compose_ones() -> None:
    """命令列的專案名與 harness 敲的容器名，都是 `compose.yml` 換過的那一組。"""
    e2e = load(stack.E2E_COMPOSE.read_text(encoding="utf-8"))
    names = {name: service.get("container_name") for name, service in e2e["services"].items()}

    assert e2e["name"] == stack.PROJECT
    assert {
        "berth": harness.BERTH_CONTAINER,
        "jellyfin": harness.JELLYFIN_CONTAINER,
        "qbittorrent": harness.QBITTORRENT_CONTAINER,
        "torrents": harness.TORRENTS_CONTAINER,
    }.items() <= names.items()


# --- 規則本身的變異驗證：造一個違規證明它會紅，改一次無關的寫法證明它不會紅。 ---

type Change = Callable[[dict[str, Any], dict[str, str]], None]


def _check(change: Change) -> list[str]:
    """把 e2e 那一份讀成資料、改一處、寫回 YAML（註解與 `!override` 標籤都沒了，排版也換了）。"""
    e2e = load(stack.E2E_COMPOSE.read_text(encoding="utf-8"))
    env = dict(stack.E2E_ENV)
    change(e2e, env)
    return violations(
        stack.PRODUCT_COMPOSE.read_text(encoding="utf-8"),
        yaml.safe_dump(e2e, allow_unicode=True, sort_keys=True),
        env,
    )


def _keep_jellyfin_container_name(e2e: dict[str, Any], env: dict[str, str]) -> None:
    del e2e["services"]["jellyfin"]["container_name"]


def _reuse_berth_container_name(e2e: dict[str, Any], env: dict[str, str]) -> None:
    e2e["services"]["berth"]["container_name"] = "berth"


def _keep_project_name(e2e: dict[str, Any], env: dict[str, str]) -> None:
    del e2e["name"]


def _keep_network_name(e2e: dict[str, Any], env: dict[str, str]) -> None:
    e2e["networks"]["default"]["name"] = "berth"


def _overlap_subnet(e2e: dict[str, Any], env: dict[str, str]) -> None:
    e2e["networks"]["default"]["ipam"]["config"] = [{"subnet": "172.28.128.0/17"}]


def _whitelist_the_product_ip(e2e: dict[str, Any], env: dict[str, str]) -> None:
    e2e["services"]["qbittorrent"]["environment"]["BERTH_IP"] = "172.28.0.2"


def _keep_the_product_ip(e2e: dict[str, Any], env: dict[str, str]) -> None:
    e2e["services"]["berth"]["networks"]["default"]["ipv4_address"] = "172.28.0.2"


def _default_berth_port(e2e: dict[str, Any], env: dict[str, str]) -> None:
    env["BERTH_PORT"] = "8383"


def _forget_bt_port(e2e: dict[str, Any], env: dict[str, str]) -> None:
    del env["QBITTORRENT_BT_PORT"]


def _jellyfin_config_on_the_host(e2e: dict[str, Any], env: dict[str, str]) -> None:
    del e2e["services"]["jellyfin"]["volumes"]


def _data_on_the_host(e2e: dict[str, Any], env: dict[str, str]) -> None:
    env["DATA_ROOT"] = "/srv/berth-trial/data"


@pytest.mark.parametrize(
    ("change", "complaint"),
    [
        (_keep_jellyfin_container_name, "jellyfin container_name"),
        (_reuse_berth_container_name, "berth container_name"),
        (_keep_project_name, "project name"),
        (_keep_network_name, "network name"),
        (_overlap_subnet, "subnet"),
        (_whitelist_the_product_ip, "qbittorrent BERTH_IP"),
        (_keep_the_product_ip, "berth ipv4_address"),
        (_default_berth_port, "berth publishes the product's host port 8383/tcp"),
        (_forget_bt_port, "qbittorrent publishes the product's host port 6881/udp"),
        (_jellyfin_config_on_the_host, "jellyfin /config"),
        (_data_on_the_host, "berth /data"),
    ],
)
def test_a_shared_name_port_or_path_is_caught(change: Change, complaint: str) -> None:
    assert any(problem.startswith(complaint) for problem in _check(change)), _check(change)


def _rename_e2e_only_volume(e2e: dict[str, Any], env: dict[str, str]) -> None:
    e2e["volumes"]["jellyfin-cfg"] = e2e["volumes"].pop("jellyfin-config")
    e2e["services"]["jellyfin"]["volumes"] = ["jellyfin-cfg:/config"]


def _move_every_port(e2e: dict[str, Any], env: dict[str, str]) -> None:
    for key in ("BERTH_PORT", "JELLYFIN_PORT", "QBITTORRENT_WEBUI_PORT", "PROWLARR_PORT"):
        env[key] = str(int(env[key]) + 1)


def _unrelated_environment(e2e: dict[str, Any], env: dict[str, str]) -> None:
    e2e["services"]["berth"]["environment"]["BERTH_LOG_LEVEL"] = "debug"


@pytest.mark.parametrize(
    "change",
    [lambda e2e, env: None, _rename_e2e_only_volume, _move_every_port, _unrelated_environment],
)
def test_rewriting_without_sharing_anything_stays_green(change: Change) -> None:
    assert _check(change) == []


# --- 呼叫端的環境：不外洩、不蓋過 e2e、跑完一定拆掉 ---

#: 試跑環境的 shell 裡可能還留著的變數（票 15 的坑：e2e 的 export 被試跑環境的 `up` 繼承；反過來
#: 也一樣——compose 讓 shell 的值優先於 `--env-file`）。
TRIAL_SHELL = {
    "CONFIG_ROOT": "C:/Users/someone/berth-trial/config",
    "DATA_ROOT": "C:/Users/someone/berth-trial/data",
    "BERTH_PORT": "18383",
    "COMPOSE_PROJECT_NAME": "berth",
    "COMPOSE_FILE": "docker-compose.yml",
    "TMDB_API_KEY": "key-from-the-caller",
}


def test_compose_gets_the_e2e_values_over_the_callers() -> None:
    caller = dict(TRIAL_SHELL)

    env = stack.compose_env(caller)

    assert {key: env[key] for key in ("CONFIG_ROOT", "DATA_ROOT", "BERTH_PORT")} == {
        key: stack.E2E_ENV[key] for key in ("CONFIG_ROOT", "DATA_ROOT", "BERTH_PORT")
    }
    assert env["TMDB_API_KEY"] == "key-from-the-caller"
    assert caller == TRIAL_SHELL


def test_the_command_line_names_the_project_and_files() -> None:
    """`-p` 與 `-f` 優先於呼叫端的 `COMPOSE_PROJECT_NAME` / `COMPOSE_FILE`。"""
    command = stack.compose_command()

    assert command[command.index("--project-name") + 1] == stack.PROJECT
    files = [command[at + 1] for at, word in enumerate(command) if word == "--file"]
    assert files == [str(stack.PRODUCT_COMPOSE), str(stack.E2E_COMPOSE)]


class _Recorder:
    def __init__(self, pytest_code: int) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.pytest_code = pytest_code

    def __call__(self, args: list[str], *, env: dict[str, str], **_: object) -> Any:
        self.calls.append((list(args), dict(env)))
        code = self.pytest_code if "pytest" in args else 0
        return subprocess.CompletedProcess(args, code)

    def compose(self) -> list[str]:
        prefix = len(stack.compose_command())
        return [" ".join(args[prefix:]) for args, _ in self.calls if "compose" in args]


@pytest.mark.parametrize("pytest_code", [0, 1])
def test_a_run_leaves_the_caller_alone_and_no_containers_behind(
    monkeypatch: pytest.MonkeyPatch, pytest_code: int
) -> None:
    recorder = _Recorder(pytest_code)
    monkeypatch.setattr(subprocess, "run", recorder)
    for key, value in TRIAL_SHELL.items():
        monkeypatch.setenv(key, value)

    # 與 `python -m tests.e2e.stack` 一樣，交出去的是這個程序自己的環境。
    code = stack.main(["-x"], os.environ)

    assert code == pytest_code
    assert {key: os.environ[key] for key in TRIAL_SHELL} == TRIAL_SHELL
    composed = recorder.compose()
    assert composed[:3] == ["down --volumes --remove-orphans", "build", "up --detach"]
    assert composed[-1] == "down --volumes --remove-orphans"
    assert ("logs --no-color --timestamps" in composed) == bool(pytest_code)
    (tests,) = [(args, env) for args, env in recorder.calls if "pytest" in args]
    assert tests[0][-1] == "-x"
    # pytest 拿呼叫端原本的環境（`TMDB_API_KEY`）；位址由 harness 讀 e2e.env。
    assert TRIAL_SHELL.items() <= tests[1].items()
    composed_envs = [env for args, env in recorder.calls if "compose" in args]
    assert all(env["DATA_ROOT"] == stack.E2E_ENV["DATA_ROOT"] for env in composed_envs)


def test_a_failed_start_still_takes_the_stack_down(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder(0)

    def failing_up(args: list[str], *, env: dict[str, str], **rest: object) -> Any:
        result = recorder(args, env=env, **rest)
        return subprocess.CompletedProcess(args, 1 if "up" in args else result.returncode)

    monkeypatch.setattr(subprocess, "run", failing_up)

    assert stack.main([], dict(TRIAL_SHELL)) == 1
    assert not [args for args, _ in recorder.calls if "pytest" in args]
    assert "logs --no-color --timestamps" in recorder.compose()
    assert recorder.compose()[-1] == "down --volumes --remove-orphans"
