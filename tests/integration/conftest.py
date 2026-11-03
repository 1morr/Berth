"""integration 測試共用的 fixture。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.models import PathSettings, Setting
from berth.services import setup as setup_module


@pytest.fixture
def roots(tmp_path: Path) -> dict[str, Path]:
    """一個宿主目錄底下的三層路徑（brief §4.1）。硬鏈接要成立就得同一個掛載。"""
    data = tmp_path / "data"
    paths = {
        "library": data / "library",
        "complete": data / "torrent" / "complete",
        "incomplete": data / "torrent" / "incomplete",
    }
    for path in paths.values():
        path.mkdir(parents=True)
    return paths


#: 沒自己設剩餘空間的測試看到的可用空間：遠高於預設門檻（10 GiB）加上任何一條測試的在途量，
#: 又低於門檻測試用的「比任何磁碟都大」（1 PB）。
AMPLE_DISK = 1024**4


@pytest.fixture(autouse=True)
def ample_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    """送單門檻與 `low_disk_space` 量的不是跑測試這台機器的磁碟（`test_host_disk.py`）。

    量真的磁碟時，CI 機器只剩十幾 GiB 的那一刻，RSS 補舊集送到一半就整輪停下（2026-11-03 CI run
    41715817195，12 條各少送幾集，重跑就綠）。要測門檻的測試自己再 `monkeypatch` 一次
    `fs.free_space`，後設的那一個生效。
    """
    monkeypatch.setattr(fs, "free_space", lambda _path: AMPLE_DISK)


@pytest.fixture(autouse=True)
def host_data_off_limits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """路徑設定沒寫過的測試，頁 2 的探針不碰這台機器上的 `/data`（Windows 上是目前磁碟的 `data`）。

    `PathSettings` 的預設值是容器裡的 `/data/...`；在跑測試的機器上它可能真的存在，探針就會寫進去
    （M4 票 46）。沒寫過路徑設定時改指到這一輪一個不存在的目錄，探針因此不問；要問的測試自己寫
    路徑設定。
    """
    original = setup_module._data_root

    async def scoped(session: AsyncSession) -> Path:
        if await session.get(Setting, PathSettings.KEY) is None:
            return tmp_path / "no-data"
        return await original(session)

    monkeypatch.setattr(setup_module, "_data_root", scoped)
