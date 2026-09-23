"""讀寫 `settings` 分組（plan §2.1）。"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from berth.models import Setting, SettingsGroup

#: 一句改不到任何一列的 UPDATE：拿 SQLite 的寫鎖（做法與理由見 `services/routes._write_lock`）。
_TAKE_WRITE_LOCK = text("UPDATE settings SET key = key WHERE key = ''")


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


async def update_settings[G: SettingsGroup](
    session: AsyncSession, group: type[G], change: Callable[[G], None]
) -> G:
    """在寫鎖裡重讀這個分組、只套 `change` 那一半、寫回並 commit，回寫回去的值。

    給「讀、打網路、再寫」的命令用：`write_settings` 是整組覆寫，網路那幾秒裡別人寫進同一組
    的欄位（精靈第 5、6 步在同一頁上，各寫 `settings.setup` 的一半）會被開頭讀到的舊值蓋回去
    （M2 票 15）。先 commit 收掉前一個交易，SQLite 才看得到別人已經 commit 的那一份；
    `populate_existing` 讓 session 不拿身分對照表裡的舊物件充數。
    """
    await session.commit()
    try:
        await session.execute(_TAKE_WRITE_LOCK)
        row = await session.get(Setting, group.KEY, populate_existing=True)
        value = group() if row is None else group.model_validate(row.value_json)
        change(value)
        await write_settings(session, value)
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return value
