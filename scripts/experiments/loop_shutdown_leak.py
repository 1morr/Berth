"""量關機時背景迴圈留下幾條沒關的 aiosqlite 連線（M4 票 71b 的 repro）。

全套 pytest 偶爾在一條與它無關的測試上紅（`PytestUnraisableExceptionWarning`，裡面是
`aiosqlite.Connection ... was deleted before being closed`）：lifespan 關機時 cancel 落在某個迴圈
剛建好連線、還在跑 SQLAlchemy `connect` handler 的那一段，那條連線沒有人關，GC 時才炸。全套
12 分鐘才偶爾撞到一次，這裡把每個迴圈的間隔壓到 1 ms、反覆啟停 app，每一輪之後 GC，數有幾輪
留下沒關的連線。

    uv run pytest scripts/experiments/loop_shutdown_leak.py -q -p no:cacheprovider -s

`LOOP_SHUTDOWN_CYCLES` 改啟停次數（預設 100）。2026-10-09 在 Windows 上各跑 6 次：修前（`0f28d48`，
與開票時的 `a303406` 只差 README）6 次紅、600 輪 10 輪洩漏；修後 0 / 6、0 / 600。固定的 regression
test 是 `tests/integration/test_loop_shutdown.py`。
"""

from __future__ import annotations

import asyncio
import gc
import os
import sys
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from berth import main
from berth.config import load_config
from berth.db import engine as engine_module
from berth.pipeline import downloads, health, importing, planning, reconciling, resolving
from berth.pipeline.rss import RssPoller

FAST = 0.001
CYCLES = int(os.environ.get("LOOP_SHUTDOWN_CYCLES", "100"))


def test_shutdown_leaves_no_connection_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for module, name in (
        (downloads, "QbitPoller"),
        (health, "HealthChecker"),
        (importing, "Importer"),
        (planning, "PlannerRunner"),
        (reconciling, "Reconciler"),
    ):
        monkeypatch.setattr(getattr(module, name), "tick_seconds", property(lambda _: FAST))
    monkeypatch.setattr(resolving, "TICK", timedelta(seconds=FAST))
    monkeypatch.setattr(
        main, "RssPoller", lambda *a, **k: RssPoller(*a, tick=timedelta(seconds=FAST), **k)
    )

    # 記下每條連線是哪個 task 開的，洩漏時說得出是哪個迴圈。
    real_connect = engine_module._connect

    async def tagged(path: str) -> aiosqlite.Connection:
        connection = await real_connect(path)
        task = asyncio.current_task()
        connection.opened_by = task.get_name() if task else "?"  # type: ignore[attr-defined]  # 實驗用的標記
        return connection

    monkeypatch.setattr(engine_module, "_connect", tagged)
    leaked: list[str] = []
    real_del = aiosqlite.Connection.__del__

    def noting(self: aiosqlite.Connection) -> None:
        if self._connection is not None:
            leaked.append(getattr(self, "opened_by", "?"))
        real_del(self)  # type: ignore[no-untyped-call]  # aiosqlite 的 __del__ 沒有型別

    monkeypatch.setattr(aiosqlite.Connection, "__del__", noting)
    # GC 時的 ResourceWarning 在這裡數，不讓 pytest 把它算成這一條的錯誤。
    unraisable: list[object] = []
    monkeypatch.setattr(sys, "unraisablehook", unraisable.append)

    config = load_config(
        {"CONFIG_ROOT": str(tmp_path / "config"), "DATA_ROOT": str(tmp_path / "data")}
    )
    leaky = 0
    for _ in range(CYCLES):
        before = len(leaked)
        app = main.create_app(replace(config, web_root=tmp_path / "never-built"))
        with TestClient(app) as running:
            running.get("/api/setup/status")
            time.sleep(0.05)
        gc.collect()
        time.sleep(0.02)
        gc.collect()
        leaky += len(leaked) > before

    print(f"leaky cycles: {leaky} / {CYCLES}; opened by: {leaked}")
    assert leaky == 0
