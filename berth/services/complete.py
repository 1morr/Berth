"""complete 目錄裡哪一項有主（brief §9.1 的 `orphan_complete`、M2 票 09）。

**兩個呼叫端問同一題**：對帳那一輪要列出沒主的那幾項，「刪除」那一顆按下去的那一刻要再問一次
——偵測與按下去之間隔了一段時間，而刪錯的代價是別人正在做種的資料。判準只能有一份。

**只看每一條 Route 的 complete 子目錄**（`<complete>/<route-slug>/`，brief §4.1），不看整個
complete root：它可能與 Sonarr 之類的共用（brief §16.4），別人 category 底下的東西不是 Berth
能判斷有沒有主的。一項就是一個 torrent 的內容根——多檔的是目錄，單檔的是那個檔案。

「有主」的三個來源，任一個指著它就算：

- **qBittorrent 上任何一個 torrent**，不只掛著 Berth 記號的那些：使用者自己手動加、而且剛好存
  到這裡的 torrent 也在做種。
- **Berth 的某一筆 Job**：torrent 已經不在客戶端、帳本也清掉了，但 Job 還在的那一包是
  `reimport` 的材料（brief §9.3），不是沒人要的東西。
- **帳本上的一列**：來源在這裡，媒體庫裡的那一份就是它的硬鏈接。
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.qbittorrent import TorrentStatus
from berth.models import Job, LedgerEntry, PathSettings, Route
from berth.services.routes import save_path_of
from berth.services.settings import read_settings


async def route_folders(session: AsyncSession) -> list[Path]:
    """每一條 Route 的 complete 子目錄（`save_path_of`，一個地方算）。停用的也算：停用說的是
    「不要再往這裡送單」，不是「裡面的東西沒人管」。"""
    paths = await read_settings(session, PathSettings)
    slugs = await session.scalars(select(Route.slug).order_by(Route.id))
    return [Path(save_path_of(paths.complete_root, slug)) for slug in slugs]


async def claimed(
    session: AsyncSession, torrents: Iterable[TorrentStatus], folders: list[Path]
) -> set[str]:
    """`folders` 底下有主的那幾項（`fs.path_key`）。`torrents` 是 qBittorrent 現在的全部。"""
    owners = [Path(row.content_path) for row in torrents if row.content_path]
    owners += [Path(path) for path in await session.scalars(select(Job.content_path)) if path]
    owners += [Path(path) for path in await session.scalars(select(LedgerEntry.source_abs_path))]
    found: set[str] = set()
    for owner in owners:
        top = fs.top_level_under(owner, folders)
        if top is not None:
            found.add(fs.path_key(top))
    return found
