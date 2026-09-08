"""integration 測試共用的 fixture。"""

from __future__ import annotations

from pathlib import Path

import pytest


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
