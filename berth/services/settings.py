"""讀寫 `settings` 分組（plan §2.1）。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from berth.models import Setting, SettingsGroup


async def read_settings[G: SettingsGroup](session: AsyncSession, group: type[G]) -> G:
    """回這個分組的目前值；沒寫過就回模型的預設值。"""
    row = await session.get(Setting, group.KEY)
    if row is None:
        return group()
    return group.model_validate(row.value_json)


async def write_settings(session: AsyncSession, value: SettingsGroup) -> None:
    """整組覆寫。呼叫端負責 commit。"""
    payload = value.model_dump(mode="json")
    row = await session.get(Setting, value.KEY)
    if row is None:
        session.add(Setting(key=value.KEY, value_json=payload))
    else:
        row.value_json = payload
