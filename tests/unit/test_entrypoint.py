"""容器入口腳本的擁有者接手行為（plan §9.1）。

`/config` 全是 Berth 自己的檔案，換過 `PUID` 就要遞迴跟著換；`/data` 是使用者的媒體根，
只有在它還是空目錄（Docker 剛替 bind mount 建好，Linux 上是 `root:root`）時才接手。
兩個 `chown` 的參數形狀不同，而形狀錯了在 Windows 上看不出來——那裡 `chown` 本來就會失敗，
腳本印一行警告就繼續，Berth 照樣寫得進去。所以這裡把 `chown` 換成會記錄參數的替身。

`BERTH_CONFIG_DIR` / `BERTH_DATA_DIR` 只是測試用的 seam（同 `BERTH_QBITTORRENT_CONF`）。
刻意不叫 `CONFIG_ROOT` / `DATA_ROOT`——那兩個名字在 `deploy/.env.example` 裡是宿主路徑。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import host_bash

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "entrypoint.sh"

BASH = host_bash()

pytestmark = pytest.mark.skipif(BASH is None, reason="入口腳本要有讀得到宿主路徑的 bash 才能跑")

#: 腳本在真的容器裡會用到、但在測試主機上不存在或需要 root 的指令。
STUBS = {
    # 假裝以 root 起、image 內的 berth 已經是 1000:1000，所以 usermod / groupmod 不會被呼叫。
    "id": '#!/bin/sh\nif [ "$#" -eq 2 ]; then echo 1000; else echo 0; fi\n',
    "getent": "#!/bin/sh\necho berth:x:1000:\n",
    "groupmod": "#!/bin/sh\nexit 0\n",
    "usermod": "#!/bin/sh\nexit 0\n",
    # 每一次呼叫記一行參數，測試看的就是這份紀錄。
    "chown": '#!/bin/sh\necho "$*" >> "${CHOWN_LOG}"\n',
    # 真的 setpriv 會降權；這裡只要把它的三個旗標吃掉再執行後面的指令。
    "setpriv": '#!/bin/sh\nshift 5\nexec "$@"\n',
}


def run_entrypoint(
    tmp_path: Path,
    *,
    data_files: tuple[str, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    assert BASH is not None
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    for name, body in STUBS.items():
        stub = stub_dir / name
        stub.write_text(body, encoding="utf-8", newline="\n")
        stub.chmod(0o755)

    config_root = tmp_path / "config"
    data_root = tmp_path / "data"
    config_root.mkdir()
    data_root.mkdir()
    for name in data_files:
        (data_root / name).write_text("", encoding="utf-8")

    chown_log = tmp_path / "chown.log"
    chown_log.touch()

    result = subprocess.run(
        [BASH, SCRIPT.as_posix(), "echo", "started"],
        env={
            **os.environ,
            "PATH": f"{stub_dir.as_posix()}{os.pathsep}{os.environ['PATH']}",
            "CHOWN_LOG": chown_log.as_posix(),
            "BERTH_CONFIG_DIR": config_root.as_posix(),
            "BERTH_DATA_DIR": data_root.as_posix(),
            "PUID": "1000",
            "PGID": "1000",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    return result, chown_log.read_text(encoding="utf-8").splitlines()


def test_hands_the_empty_media_root_over_to_the_run_user(tmp_path: Path) -> None:
    # Docker 替 bind mount 新建的目錄是 root:root。不接手的話 Berth 連 /data/library
    # 都建不出來，精靈第 3 步就死在乾淨的 Linux 宿主上。
    _, chowns = run_entrypoint(tmp_path)

    data_root = (tmp_path / "data").as_posix()
    assert f"berth:berth {data_root}" in chowns


def test_takes_the_config_directory_recursively(tmp_path: Path) -> None:
    _, chowns = run_entrypoint(tmp_path)

    config_root = (tmp_path / "config").as_posix()
    assert f"-R berth:berth {config_root}" in chowns


def test_leaves_a_media_root_that_already_has_content_alone(tmp_path: Path) -> None:
    # 媒體根可能是 NAS 上別的帳號擁有的共用目錄，改擁有者是沒人要的意外。
    _, chowns = run_entrypoint(tmp_path, data_files=("existing.mkv",))

    data_root = (tmp_path / "data").as_posix()
    assert not [line for line in chowns if line.endswith(data_root)]


def test_runs_the_given_command(tmp_path: Path) -> None:
    result, _ = run_entrypoint(tmp_path)

    assert result.stdout.strip() == "started"
