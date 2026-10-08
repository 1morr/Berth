"""qBittorrent preseed 腳本的行為（plan §9.2）。

腳本在 linuxserver 的 `custom-cont-init.d` 裡跑，而那時 image 自己的
`init-qbittorrent-config` 已經把 `/defaults/qBittorrent.conf` 複製進 `/config`。
規則因此不是「檔案不存在才寫」，而是「缺哪個鍵補哪個鍵，已經有值的一律不動」。

腳本寫在部署用 compose 的頂層 `configs.qbittorrent-preseed.content` 裡（M4 票 71、brief §20.18），
這裡從 compose 抽出來、把 `$$` 還原成 `$` 再跑——跑的就是 Compose 寫進容器的那一份。另外守兩件
compose 不會報錯、只會讓 Berth 進不去的事：

- `content` 裡每個 `$` 都寫成 `$$`：漏一個，Compose 拿宿主的變數展開它（`${CONF}` 變成空字串）；
- qbittorrent 把它放到 `/custom-cont-init.d/` 並帶執行位元：image 只跑 `-x` 的檔，`content`
  預設 0444，漏了 `mode` 只在 log 留一行 `is not an executable file`。
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from tests.conftest import host_bash
from tests.unit.test_deploy_ports import COMPOSE

CONFIG = "qbittorrent-preseed"
INIT_DIR = PurePosixPath("/custom-cont-init.d")

BASH = host_bash()

needs_bash = pytest.mark.skipif(BASH is None, reason="preseed 腳本要有讀得到宿主路徑的 bash 才能跑")

WHITELIST_ENABLED = r"WebUI\AuthSubnetWhitelistEnabled=true"
BERTH_IP = "172.28.0.2"
WHITELIST = rf"WebUI\AuthSubnetWhitelist={BERTH_IP}/32"

#: linuxserver image 的 `/defaults/qBittorrent.conf`，2026-09-07 從 image 內抄出。
LSIO_DEFAULT = r"""[AutoRun]
enabled=false
program=

[LegalNotice]
Accepted=true

[Preferences]
Connection\UPnP=false
Downloads\SavePath=/downloads/
WebUI\Address=*
WebUI\ServerDomains=*
"""


def compose_data() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data


def violations(compose: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    content = str(((compose.get("configs") or {}).get(CONFIG) or {}).get("content", ""))
    if not content:
        problems.append(f"configs.{CONFIG} has no content")
    # 去掉每個 `$$` 之後還剩下 `$`，就是 Compose 會拿宿主變數展開的地方。
    for unescaped in sorted(set(re.findall(r"\$\S{0,12}", content.replace("$$", "")))):
        problems.append(f"unescaped {unescaped!r}")

    mounted = [
        entry
        for entry in compose["services"]["qbittorrent"].get("configs", [])
        if isinstance(entry, Mapping) and entry.get("source") == CONFIG
    ]
    if len(mounted) != 1:
        problems.append(f"qbittorrent configs: {CONFIG} given {len(mounted)} times")
        return problems
    target = PurePosixPath(str(mounted[0].get("target", "")))
    if target.parent != INIT_DIR:
        problems.append(f"target {target} is not in {INIT_DIR}")
    mode = mounted[0].get("mode")
    if not isinstance(mode, int) or not mode & 0o111:
        problems.append(f"mode {mode!r} is not executable")
    return problems


def embedded_script(compose: Mapping[str, Any]) -> str:
    """Compose 寫進容器的腳本：`content` 的 `$$` 還原成 `$`。"""
    return str(compose["configs"][CONFIG]["content"]).replace("$$", "$")


def run_preseed(
    conf: Path,
    berth_ip: str | None = BERTH_IP,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    env = {**os.environ, "BERTH_QBITTORRENT_CONF": conf.as_posix()}
    if berth_ip is None:
        env.pop("BERTH_IP", None)
    else:
        env["BERTH_IP"] = berth_ip
    return subprocess.run(
        [BASH, "-c", embedded_script(compose_data()), "10-berth.sh"],
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


@needs_bash
def test_fails_loudly_when_the_config_file_is_missing(tmp_path: Path) -> None:
    # image 的 init 一定先把 /defaults 的設定檔複製好；沒有的話是環境壞了，不是要自己補一份。
    conf = tmp_path / "qBittorrent" / "qBittorrent.conf"

    result = run_preseed(conf, check=False)

    assert result.returncode != 0
    assert "not found" in result.stderr
    assert not conf.exists()


@needs_bash
def test_fails_loudly_without_the_berth_address(tmp_path: Path) -> None:
    # 位址只有 compose 知道；少了它就別猜，猜錯等於開錯或關錯白名單。
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text(LSIO_DEFAULT, encoding="utf-8")

    result = run_preseed(conf, berth_ip=None, check=False)

    assert result.returncode != 0
    assert "BERTH_IP" in result.stderr
    assert conf.read_text(encoding="utf-8") == LSIO_DEFAULT


@needs_bash
def test_adds_the_missing_keys_into_the_existing_preferences_section(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text(LSIO_DEFAULT, encoding="utf-8")

    run_preseed(conf)

    lines = conf.read_text(encoding="utf-8").splitlines()
    assert WHITELIST_ENABLED in lines
    assert WHITELIST in lines
    # 其餘每一行原封不動，包括 image 預設的 `WebUI\ServerDomains=*`：寫死成 `qbittorrent`
    # 會讓使用者從 localhost:8080 進不了 WebUI。
    assert [line for line in lines if line not in {WHITELIST_ENABLED, WHITELIST}] == (
        LSIO_DEFAULT.splitlines()
    )


@needs_bash
def test_takes_the_berth_address_from_the_environment(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text(LSIO_DEFAULT, encoding="utf-8")

    run_preseed(conf, berth_ip="10.9.0.7")

    lines = conf.read_text(encoding="utf-8").splitlines()
    assert r"WebUI\AuthSubnetWhitelist=10.9.0.7/32" in lines


@needs_bash
def test_leaves_an_already_preseeded_file_untouched(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text(LSIO_DEFAULT, encoding="utf-8")
    run_preseed(conf)
    after_first = conf.read_bytes()

    run_preseed(conf)
    run_preseed(conf)

    assert conf.read_bytes() == after_first


@needs_bash
def test_never_overwrites_a_value_the_user_already_chose(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    existing = LSIO_DEFAULT + WHITELIST_ENABLED.replace("true", "false") + "\n"
    existing += r"WebUI\AuthSubnetWhitelist=192.168.0.0/16" + "\n"
    conf.write_text(existing, encoding="utf-8")

    run_preseed(conf)

    assert conf.read_text(encoding="utf-8") == existing


@needs_bash
def test_appends_a_preferences_section_when_the_file_has_none(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text("[LegalNotice]\nAccepted=true\n", encoding="utf-8")

    run_preseed(conf)

    assert conf.read_text(encoding="utf-8").splitlines() == [
        "[LegalNotice]",
        "Accepted=true",
        "[Preferences]",
        WHITELIST_ENABLED,
        WHITELIST,
    ]


# --- compose 那一側：不報錯、只讓 Berth 進不去的兩件事。 ---


def test_the_compose_file_runs_the_embedded_script_as_written() -> None:
    assert violations(compose_data()) == []


def test_a_bare_dollar_in_the_script_is_caught() -> None:
    data = compose_data()
    data["configs"][CONFIG]["content"] += "echo ${CONF}\n"

    assert violations(data) == ["unescaped '${CONF}'"]


def test_a_missing_or_read_only_mode_is_caught() -> None:
    data = compose_data()
    (entry,) = data["services"]["qbittorrent"]["configs"]
    del entry["mode"]
    assert violations(data) == ["mode None is not executable"]

    entry["mode"] = 0o444
    assert violations(data) == [f"mode {0o444!r} is not executable"]


def test_a_target_outside_the_init_directory_is_caught() -> None:
    data = compose_data()
    data["services"]["qbittorrent"]["configs"][0]["target"] = "/config/10-berth.sh"

    assert violations(data) == ["target /config/10-berth.sh is not in /custom-cont-init.d"]


def test_renaming_the_script_and_rewording_a_comment_is_not_a_violation() -> None:
    data = compose_data()
    data["services"]["qbittorrent"]["configs"][0]["target"] = "/custom-cont-init.d/20-berth.sh"
    content = data["configs"][CONFIG]["content"]
    data["configs"][CONFIG]["content"] = content.replace(
        "# A linuxserver custom-cont-init.d script", "# A custom-cont-init.d script for linuxserver"
    )

    assert data["configs"][CONFIG]["content"] != content
    assert violations(data) == []
