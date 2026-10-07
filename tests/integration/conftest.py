"""integration 測試共用的 fixture。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
