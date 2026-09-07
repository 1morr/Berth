"""qBittorrent preseed 腳本的行為（plan §9.2）。

腳本在 linuxserver 的 `custom-cont-init.d` 裡跑，而那時 image 自己的
`init-qbittorrent-config` 已經把 `/defaults/qBittorrent.conf` 複製進 `/config`。
規則因此不是「檔案不存在才寫」，而是「缺哪個鍵補哪個鍵，已經有值的一律不動」。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "preseed" / "qbittorrent" / "10-berth.sh"

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="preseed 腳本要有 bash 才能跑")

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
        [BASH, SCRIPT.as_posix()],
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


def test_fails_loudly_when_the_config_file_is_missing(tmp_path: Path) -> None:
    # image 的 init 一定先把 /defaults 的設定檔複製好；沒有的話是環境壞了，不是要自己補一份。
    conf = tmp_path / "qBittorrent" / "qBittorrent.conf"

    result = run_preseed(conf, check=False)

    assert result.returncode != 0
    assert "not found" in result.stderr
    assert not conf.exists()


def test_fails_loudly_without_the_berth_address(tmp_path: Path) -> None:
    # 位址只有 compose 知道；少了它就別猜，猜錯等於開錯或關錯白名單。
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text(LSIO_DEFAULT, encoding="utf-8")

    result = run_preseed(conf, berth_ip=None, check=False)

    assert result.returncode != 0
    assert "BERTH_IP" in result.stderr
    assert conf.read_text(encoding="utf-8") == LSIO_DEFAULT


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


def test_takes_the_berth_address_from_the_environment(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text(LSIO_DEFAULT, encoding="utf-8")

    run_preseed(conf, berth_ip="10.9.0.7")

    lines = conf.read_text(encoding="utf-8").splitlines()
    assert r"WebUI\AuthSubnetWhitelist=10.9.0.7/32" in lines


def test_leaves_an_already_preseeded_file_untouched(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    conf.write_text(LSIO_DEFAULT, encoding="utf-8")
    run_preseed(conf)
    after_first = conf.read_bytes()

    run_preseed(conf)
    run_preseed(conf)

    assert conf.read_bytes() == after_first


def test_never_overwrites_a_value_the_user_already_chose(tmp_path: Path) -> None:
    conf = tmp_path / "qBittorrent.conf"
    existing = LSIO_DEFAULT + WHITELIST_ENABLED.replace("true", "false") + "\n"
    existing += r"WebUI\AuthSubnetWhitelist=192.168.0.0/16" + "\n"
    conf.write_text(existing, encoding="utf-8")

    run_preseed(conf)

    assert conf.read_text(encoding="utf-8") == existing


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
