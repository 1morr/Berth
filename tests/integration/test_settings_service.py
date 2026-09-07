"""設定分組的讀寫（票 02 驗收）。"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.models import JellyfinSettings, PathSettings, Setting, SetupSettings
from berth.services.settings import read_settings, write_settings

pytestmark = pytest.mark.asyncio


async def test_unset_groups_read_back_their_defaults(session: AsyncSession) -> None:
    assert await read_settings(session, JellyfinSettings) == JellyfinSettings()
    assert (await read_settings(session, PathSettings)).complete_root == "/data/torrent/complete"
    assert (await read_settings(session, SetupSettings)).completed is False


async def test_a_written_group_reads_back(session: AsyncSession) -> None:
    await write_settings(session, JellyfinSettings(base_url="http://jellyfin:8096", api_key="k"))
    await session.commit()

    stored = await read_settings(session, JellyfinSettings)

    assert stored == JellyfinSettings(base_url="http://jellyfin:8096", api_key="k")


async def test_writing_the_same_group_twice_updates_one_row(session: AsyncSession) -> None:
    await write_settings(session, SetupSettings(current_step=2))
    await session.commit()
    await write_settings(session, SetupSettings(current_step=5, completed=True))
    await session.commit()

    rows = await session.scalar(
        select(func.count()).select_from(Setting).where(Setting.key == SetupSettings.KEY)
    )

    assert rows == 1
    assert await read_settings(session, SetupSettings) == SetupSettings(
        current_step=5, completed=True
    )


async def test_groups_do_not_overwrite_each_other(session: AsyncSession) -> None:
    await write_settings(session, JellyfinSettings(api_key="jellyfin"))
    await write_settings(session, PathSettings(complete_root="/mnt/complete"))
    await session.commit()

    assert (await read_settings(session, JellyfinSettings)).api_key == "jellyfin"
    assert (await read_settings(session, PathSettings)).complete_root == "/mnt/complete"


async def test_nothing_is_persisted_until_the_caller_commits(session: AsyncSession) -> None:
    """services 不自己 commit：一次精靈步驟的多筆寫入要能一起成功或一起失敗。"""
    await write_settings(session, JellyfinSettings(api_key="rolled-back"))
    await session.rollback()

    assert await read_settings(session, JellyfinSettings) == JellyfinSettings()
