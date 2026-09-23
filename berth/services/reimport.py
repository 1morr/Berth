"""重新入庫：以 complete 裡的一包為 Import Source 再走一次 planning → importing
（brief §9.3、M2 票 10）。

**不另開一條入庫的路**：這一支只把那一包放回管線的入口（`completed`），算與鏈是規劃器與
importer 照常的一輪（plan §3.1）。帳本以來源冪等（`services/importer._ledger_rows`），所以
「刪了 library、保留 complete、再重新入庫」是一鍵動作，按兩次也不會長出第二份帳本。

**Import Source 是磁碟上的那一包，不是 qBittorrent 的清單**：`job_files` 照資料夾裡現在的樣子
重寫一次。torrent 可能早就不在客戶端了（brief §9.3「不要求 torrent 仍存在」），而資料夾裡少了
一集的話，照 torrent 的清單規劃只會讓 importer 在那一集上失敗、整筆停在 `import_failed`。
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import EventType, JobRefusal, JobState
from berth.logs import job_context
from berth.models import Job, JobFile
from berth.models.types import utcnow
from berth.services.jobs import (
    REIMPORTABLE,
    JobRejectedError,
    JobView,
    job_lock,
    read_job,
    record_event,
    transition,
)

logger = logging.getLogger(__name__)

#: 時間線上那一筆 `retried` 的 `action`：畫面憑它說「重新入庫」而不是「重新規劃」。
REIMPORT = "reimport"


async def reimport_job(session: AsyncSession, job_hash: str, *, actor: str) -> JobView:
    """`POST /jobs/{hash}/reimport`：那一筆的 complete 目錄重新走一次（plan §3.1）。

    **先讀磁碟才動 Job**：那一包不在了、或裡面一個檔案都沒有時什麼都不改——退回 `completed` 只會
    得到一份空的 Plan，而那一筆原本的狀態（`imported`、`removed`…）說的仍然是事實。

    時間線寫一筆 `retried`：它是事件去重的界線（plan §3.3），重算出來的 `plan_generated` 與上一次
    一字不差時才不會被吞掉。呼叫端在 commit 之後叫醒規劃器；沒叫也修得好，它每 60 秒自己掃一次。
    """
    job = await session.get(Job, job_hash)
    if job is None:
        raise JobRejectedError(JobRefusal.JOB_MISSING, job_hash)
    if job.state not in REIMPORTABLE:
        raise JobRejectedError(JobRefusal.NOT_REIMPORTABLE, job.state.value)
    with job_context(job.hash):
        async with job_lock(job.hash):
            files = contents_on_disk(job.save_path, job.content_path)
            if not files:
                raise JobRejectedError(JobRefusal.CONTENT_MISSING, job.content_path)
            was = job.state
            await _restate_files(session, job, files)
            if not await transition(session, job, JobState.COMPLETED, expected=was):
                # 另一個分頁先按了，或它自己在這中間動了。剛才重寫的檔案清單一起丟掉。
                await session.rollback()
                raise JobRejectedError(JobRefusal.NOT_REIMPORTABLE, job.state.value)
            await record_event(
                session,
                job,
                EventType.RETRIED,
                actor=actor,
                payload={
                    "state": JobState.COMPLETED.value,
                    "action": REIMPORT,
                    "source": job.content_path,
                },
            )
            await session.commit()
            logger.info("job reimported", extra={"state": job.state.value, "from": was.value})
    view = await read_job(session, job_hash)
    assert view is not None  # 剛剛才 commit 的那一列。
    return view


def contents_on_disk(save_path: str, content_path: str) -> list[tuple[str, int]]:
    """一包在磁碟上現在有哪些檔案：`(相對 save path 的路徑, 大小)`，與 `job_files` 同形。

    多檔的一包是一個目錄（含它自己的根目錄那一層，brief §20.7），單檔的就是那個檔案。
    讀不到、不在、不在 save path 底下都是空的——呼叫端把空的當成「沒有東西可以入庫」。
    """
    if not save_path or not content_path:
        return []
    base, content = Path(save_path), Path(content_path)
    try:
        if content.is_file():
            found = [content]
        elif content.is_dir():
            found = sorted(path for path in content.rglob("*") if path.is_file())
        else:
            return []
        return [(path.relative_to(base).as_posix(), path.stat().st_size) for path in found]
    except (OSError, ValueError) as exc:
        # `ValueError` 是那一包不在 save path 底下：`job_files` 的路徑一律相對 save path，
        # 這樣的一包寫不成那個形狀。
        logger.warning("the import source could not be read", extra={"error": str(exc)})
        return []


async def _restate_files(session: AsyncSession, job: Job, files: list[tuple[str, int]]) -> None:
    """`job_files` 照磁碟上現在的樣子重寫：不在的刪掉、新的補上、還在的留著它的 id 與優先序。

    **留著 id**：mediainfo 量過的結果掛在那一列上，重新入庫不必再量一次。**留著優先序**：
    qBittorrent 上設成不下載的檔案，磁碟上可能有一個只寫了幾個 piece 的殘骸，它仍然不該進 Plan。
    """
    rows = {
        row.rel_path: row
        for row in await session.scalars(select(JobFile).where(JobFile.job_hash == job.hash))
    }
    present = dict(files)
    for rel_path, row in rows.items():
        if rel_path not in present:
            await session.delete(row)
    now = utcnow()
    for rel_path, size in files:
        known = rows.get(rel_path)
        if known is None:
            session.add(JobFile(job_hash=job.hash, rel_path=rel_path, size=size, priority=1))
        elif known.size != size:
            known.size = size
            known.updated_at = now
    await session.flush()
