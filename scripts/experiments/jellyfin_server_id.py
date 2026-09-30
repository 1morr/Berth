#!/usr/bin/env python3
"""M4 票 18：「同一台 Jellyfin」能不能靠 `/System/Info/Public` 的 `Id` 認（brief §20.15）。

對一台跑在 Docker 裡、`/config` 是 bind mount 的 Jellyfin 量三件事：

1. 同一台用不同網址連（`localhost`、`127.0.0.1`、`host.docker.internal`——最後一個從
   另一個容器裡問），`Id` 一不一樣；
2. `docker restart` 之後變不變；
3. `docker compose up -d --force-recreate` 重建容器之後變不變（順便看 `ServerName`，
   它是容器的 hostname）。

會重啟、重建那一台，**只對拿來實驗的容器跑**（2026-09-30 用的是 berth-existing 的
`bad-jellyfin-elsewhere`）：

    uv run python scripts/experiments/jellyfin_server_id.py \\
        --port 58097 --container bad-jellyfin-elsewhere \\
        --compose-dir C:/Users/Roxy/berth-existing/broken --service jellyfin-elsewhere \\
        --probe-from bad-prowlarr-old

`--probe-from` 是另一個有 `curl` 的容器，拿它問 `host.docker.internal`。只印 stdout，不寫檔。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request

PATH = "/System/Info/Public"


def info(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url + PATH, timeout=5) as response:  # 實驗只連本機
        payload: dict[str, object] = json.loads(response.read())
        return payload


def from_container(container: str, port: int) -> dict[str, object]:
    out = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "curl",
            "-s",
            "-m",
            "5",
            f"http://host.docker.internal:{port}{PATH}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    payload: dict[str, object] = json.loads(out)
    return payload


def wait_until_up(port: int, seconds: int = 120) -> dict[str, object]:
    # 起來的途中它會先回一份還沒有 `Id` 的東西（或不是 JSON），等到有 `Id` 才算。
    deadline = time.monotonic() + seconds
    while True:
        try:
            payload = info(f"http://127.0.0.1:{port}")
            if payload.get("Id"):
                return payload
        except (OSError, ValueError):
            pass
        if time.monotonic() > deadline:
            raise TimeoutError(f"no Id from port {port} within {seconds}s")
        time.sleep(2)


def show(label: str, payload: dict[str, object]) -> None:
    print(f"{label:<28} Id={payload.get('Id')}  ServerName={payload.get('ServerName')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--compose-dir", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--probe-from", required=True)
    args = parser.parse_args()

    show("localhost", info(f"http://localhost:{args.port}"))
    show("127.0.0.1", info(f"http://127.0.0.1:{args.port}"))
    show("host.docker.internal", from_container(args.probe_from, args.port))

    subprocess.run(["docker", "restart", args.container], check=True, capture_output=True)
    show("after docker restart", wait_until_up(args.port))

    subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", args.service],
        check=True,
        capture_output=True,
        cwd=args.compose_dir,
    )
    show("after --force-recreate", wait_until_up(args.port))


if __name__ == "__main__":
    main()
