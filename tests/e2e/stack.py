"""e2e 那一整套 compose 的起停（M4 票 34）：`uv run --env-file .env python -m tests.e2e.stack`。

一條指令走完 docs/development.md〈e2e〉那一串：先拆掉上一輪留下的 → build → `up`（不加 `--wait`，
冷啟動閘門）→ `pytest -m e2e tests/e2e` → 失敗時印出容器狀態與 log → 不論結果都 `down --volumes`。
多給的參數原樣交給 pytest（`-k`、`-x`）。

**與同一台機器上的試跑環境並存**：專案名、容器名、網路與子網在 `compose.yml` 換掉，host port 與
`DATA_ROOT` / `CONFIG_ROOT` 在 `e2e.env`（`tests/unit/test_e2e_stack.py` 守著兩邊都換乾淨）。
compose 的變數只放進子程序的環境（`compose_env`），而且蓋過呼叫端 shell 裡的同名變數——
compose 讓 shell 的值優先於 `--env-file`，一個沒清掉的 `DATA_ROOT` 就會把 e2e 掛到別人的媒體庫
上（票 15 的坑反過來）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_COMPOSE = ROOT / "deploy" / "docker-compose.yml"
E2E_COMPOSE = ROOT / "tests" / "e2e" / "compose.yml"
ENV_FILE = ROOT / "tests" / "e2e" / "e2e.env"

#: 與 `compose.yml` 的 `name` 相同；命令列上再給一次，呼叫端的 `COMPOSE_PROJECT_NAME` 才蓋不過它。
PROJECT = "berth-e2e"


def read_env_file(path: Path) -> dict[str, str]:
    """`KEY=VALUE` 列；註解與空行略過。"""
    pairs = (
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return {key.strip(): value.strip() for key, value in pairs}


E2E_ENV = read_env_file(ENV_FILE)


def compose_command() -> list[str]:
    """`-p` 與 `-f` 都寫在命令列：它們優先於呼叫端的 `COMPOSE_PROJECT_NAME` / `COMPOSE_FILE`。

    沒有 `--env-file`：`e2e.env` 的值只走 `compose_env` 那一條。
    """
    return [
        "docker",
        "compose",
        "--project-name",
        PROJECT,
        "--file",
        str(PRODUCT_COMPOSE),
        "--file",
        str(E2E_COMPOSE),
    ]


def compose_env(caller: Mapping[str, str]) -> dict[str, str]:
    """給 compose 子程序的環境：呼叫端的一份**拷貝**，`e2e.env` 的每個鍵蓋過去。"""
    return {**caller, **E2E_ENV}


def main(pytest_args: Sequence[str], caller: Mapping[str, str]) -> int:
    env = compose_env(caller)

    def explain() -> None:
        compose("ps", "--all")
        compose("logs", "--no-color", "--timestamps")

    def compose(*args: str) -> int:
        command = [*compose_command(), *args]
        return subprocess.run(command, env=env, cwd=ROOT, check=False).returncode

    # 精靈走完就不能再走一遍：上一輪中斷時留下的容器與 volume 先拆掉。
    compose("down", "--volumes", "--remove-orphans")
    try:
        # 先 build，`up` 才是所有容器同時從零啟動（冷啟動閘門，票 06h）；缺的 image `up` 會先
        # 拉完才啟動任何一個。**不 `pull`**：`lscr.io/linuxserver/*` 的 tag 是試跑環境共用的，
        # 拉新的會讓它下一次 `up -d` 換 image（票 34 實測，連釘住的 Jellyfin tag 也有重建）。
        if compose("build") or compose("up", "--detach"):
            explain()
            return 1
        # pytest 拿的是呼叫端原本的環境（`TMDB_API_KEY`），位址由 harness 自己讀 `e2e.env`。
        tests = [sys.executable, "-m", "pytest", "-m", "e2e", "tests/e2e", "-rA", *pytest_args]
        code = subprocess.run(tests, env=dict(caller), cwd=ROOT, check=False).returncode
        if code:
            explain()
        return code
    finally:
        compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
