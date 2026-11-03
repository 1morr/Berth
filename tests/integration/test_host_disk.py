"""跑測試那台機器的磁碟不決定測試的結果（2026-11-03 CI run 41715817195）。

送單前的磁碟門檻量的是真的檔案系統（`fs.free_space`，預設門檻 10 GiB）。CI 機器那一刻只剩十幾
GiB，扣掉在途的幾集就低於門檻，RSS 補舊集送到一半整輪停下，12 條測試各少送幾集；同一個 commit
重跑就綠。integration 測試因此預設看到充足的空間（`conftest.ample_disk`），要測門檻的自己設。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import NamedTuple

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import JobState, label_of
from berth.services.jobs import add_download
from tests.integration.test_jobs import _ready, _source

pytestmark = pytest.mark.asyncio


class Usage(NamedTuple):
    total: int
    used: int
    free: int


async def test_a_nearly_full_host_disk_does_not_hold_back_a_submission(
    session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """這台機器只剩 1 GiB（低於預設的 10 GiB 門檻），沒自己設剩餘空間的測試照樣送得出去。"""
    gib = 1024**3
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Usage(100 * gib, 99 * gib, gib))
    media, route, factory = await _ready(session, roots)

    outcome = await add_download(
        session,
        factory,
        source=_source(),
        media_id=media.id,
        route_id=route.id,
        user_id=None,
        actor=label_of(None),
    )

    assert outcome.job.state is JobState.SUBMITTED
