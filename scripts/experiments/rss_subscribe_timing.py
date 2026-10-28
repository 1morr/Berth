"""M4 票 13b：前端 e2e `rss-subscribe` 的第一輪預覽為什麼 5 秒內沒回。

對 `rss` 情境的演練 server 打那條 spec 同一串 API（訂閱 Mikan 番組並補舊集 → 馬上以英文標題建
acg.rip 搜尋 feed → 讀第一輪預覽），每一步計時。`--settle` 秒數讓建搜尋 feed 之前先等補舊集跑完，
對照得出搜尋 feed 慢是在等補舊集，還是自己就慢。`--profile` 改在同一個行程裡起 server，以 cProfile
包住 `preview_feed`，印出累計時間最多的函式（有 profiler 的額外開銷，只看比例）。

M4 票 121b：`--watch` 秒數讓建好搜尋 feed 之後在那段時間裡反覆讀預覽與 `/jobs`，預覽的各狀態筆數、
重複的是哪幾筆（理由）或 Mikan 送出的入庫了幾集一有變化就印一行（自訂閱送出起算的秒數）。看得出
預覽裡的「重複」是不是跟著補舊集的入庫變。

import `berth`（`--profile` 要換掉它的函式）與 httpx，要在 repo 根目錄以 `uv run` 跑：

    uv run python scripts/experiments/rss_subscribe_timing.py [--settle 0] [--port 8620] [--profile]
        [--watch 0]
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
from collections import Counter
from collections.abc import Callable
from typing import Any

import httpx

MEDIA = "tv:262000"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8620)
    parser.add_argument("--settle", type=float, default=0.0)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--watch", type=float, default=0.0)
    args = parser.parse_args()
    if isinstance(sys.stdout, io.TextIOWrapper):  # 繁中 Windows 的主控台預設 cp950，印不出簡體字
        sys.stdout.reconfigure(encoding="utf-8")
    base = f"http://127.0.0.1:{args.port}/api"
    if args.profile:
        profiled(args.port, base, args.settle, args.watch)
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
        run(base, args.settle, args.watch)
    finally:
        server.terminate()
        server.wait()


def profiled(port: int, base: str, settle: float, watch: float) -> None:
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
    run(base, settle, watch)
    out = io.StringIO()
    pstats.Stats(profile, stream=out).sort_stats("cumulative").print_stats(30)
    print(out.getvalue())


def timed(label: str, call: Callable[[], httpx.Response]) -> httpx.Response:
    start = time.perf_counter()
    response = call()
    print(f"{label:<40} {response.status_code} {time.perf_counter() - start:6.2f}s", flush=True)
    return response


def run(base: str, settle: float, watch: float) -> None:
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
        subscribed = time.perf_counter()
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
                    # M5 票 26 起關鍵字訂閱只綁一個字幕組：與 Mikan 那一份同一組。
                    "subgroup": "喵萌奶茶屋&LoliHouse",
                },
            ),
        )
        preview = f"/rss/feeds/{feed.json()['id']}/preview"
        for _ in range(3):
            timed(f"GET {preview}", lambda: client.get(preview))
        watched(client, preview, subscribed, watch)


def watched(client: httpx.Client, preview: str, since: float, seconds: float) -> None:
    """`seconds` 秒內反覆讀預覽與下載列表，有變化才印。"""
    last: tuple[dict[str, int], tuple[str, ...], int, int] | None = None
    until = time.perf_counter() + seconds
    while time.perf_counter() < until:
        items = client.get(preview).json()
        jobs = client.get("/jobs", params={"filter": "all", "media": MEDIA}).json()["jobs"]
        states = dict(sorted(Counter(item["status"] for item in items).items()))
        duplicates = tuple(
            f"{item['title'][:60]} <- {item['skip']['code']} {item['skip']['params']}"
            for item in items
            if item["status"] == "duplicate"
        )
        imported = sum(job["state"] == "imported" for job in jobs)
        now = (states, duplicates, imported, len(jobs))
        if now != last:
            print(
                f"t={time.perf_counter() - since:5.1f}s preview={states} "
                f"mikan jobs imported {imported}/{len(jobs)}",
                flush=True,
            )
            for line in duplicates:
                print(f"    duplicate: {line}", flush=True)
            last = now
        time.sleep(0.5)


if __name__ == "__main__":
    main()
