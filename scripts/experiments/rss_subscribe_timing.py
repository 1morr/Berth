"""M4 票 13b：前端 e2e `rss-subscribe` 的第一輪預覽為什麼 5 秒內沒回。

對 `rss` 情境的演練 server 打那條 spec 同一串 API（訂閱 Mikan 番組並補舊集 → 馬上以英文標題建
acg.rip 搜尋 feed → 讀第一輪預覽），每一步計時。`--settle` 秒數讓建搜尋 feed 之前先等補舊集跑完，
對照得出搜尋 feed 慢是在等補舊集，還是自己就慢。`--profile` 改在同一個行程裡起 server，以 cProfile
包住 `preview_feed`，印出累計時間最多的函式（有 profiler 的額外開銷，只看比例）。

import `berth`（`--profile` 要換掉它的函式）與 httpx，要在 repo 根目錄以 `uv run` 跑：

    uv run python scripts/experiments/rss_subscribe_timing.py [--settle 0] [--port 8620] [--profile]
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

MEDIA = "tv:262000"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8620)
    parser.add_argument("--settle", type=float, default=0.0)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}/api"
    if args.profile:
        profiled(args.port, base, args.settle)
        return
    server = subprocess.Popen(
        [
            sys.executable,
            "scripts/fake_setup_server.py",
            "--scenario",
            "rss",
            "--port",
            str(args.port),
        ]
    )
    try:
        run(base, args.settle)
    finally:
        server.terminate()
        server.wait()


def profiled(port: int, base: str, settle: float) -> None:
    sys.path[:0] = ["scripts"]
    import fake_setup_server
    import uvicorn

    from berth.api import rss
    from berth.services.rss import preview_feed

    profile = cProfile.Profile()

    async def wrapped(*args: Any, **kwargs: Any) -> Any:  # 包住任何簽名，只為了計時
        profile.enable()
        try:
            return await preview_feed(*args, **kwargs)
        finally:
            profile.disable()

    # API 層 import 的是名字本身，換的是它那一份。
    vars(rss)["preview_feed"] = wrapped

    def serve(app: Any, host: str, port: int, log_level: str) -> None:  # 換掉 uvicorn.run
        config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
        threading.Thread(target=uvicorn.Server(config).run, daemon=True).start()

    vars(uvicorn)["run"] = serve
    fake_setup_server.main(["--scenario", "rss", "--port", str(port)])
    run(base, settle)
    out = io.StringIO()
    pstats.Stats(profile, stream=out).sort_stats("cumulative").print_stats(30)
    print(out.getvalue())


def timed(label: str, call: Callable[[], httpx.Response]) -> httpx.Response:
    start = time.perf_counter()
    response = call()
    print(f"{label:<40} {response.status_code} {time.perf_counter() - start:6.2f}s", flush=True)
    return response


def run(base: str, settle: float) -> None:
    with httpx.Client(
        base_url=base, timeout=60, headers={"X-Requested-With": "XMLHttpRequest"}
    ) as client:
        for _ in range(120):
            try:
                if client.get("/health").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.5)
        client.post("/auth/login", json={"username": "skipper", "password": "harbour"})
        timed("GET /media", lambda: client.get(f"/media/{MEDIA}"))
        route = next(
            r["route"]["id"] for r in client.get("/routes").json() if r["route"]["name"] == "Anime"
        )
        bangumi = timed(
            "GET /rss/mikan/bangumi/4009", lambda: client.get("/rss/mikan/bangumi/4009")
        )
        subgroup = next(g for g in bangumi.json()["subgroups"] if "LoliHouse" in g["name"])
        timed(
            "POST /rss/subscriptions/mikan",
            lambda: client.post(
                "/rss/subscriptions/mikan",
                json={
                    "media": MEDIA,
                    "route": route,
                    "bangumi": 4009,
                    "subgroup": subgroup["id"],
                    "subgroup_name": subgroup["name"],
                },
            ),
        )
        time.sleep(settle)
        feed = timed(
            "POST /rss/subscriptions/search",
            lambda: client.post(
                "/rss/subscriptions/search",
                json={
                    "media": MEDIA,
                    "route": route,
                    "kind": "acgrip",
                    "term": "Kimi ga Shinu made Koi wo Shitai",
                },
            ),
        )
        preview = f"/rss/feeds/{feed.json()['id']}/preview"
        for _ in range(3):
            timed(f"GET {preview}", lambda: client.get(preview))


if __name__ == "__main__":
    main()
