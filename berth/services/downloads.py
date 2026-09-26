"""客戶端狀態驅動的那幾個轉換（plan §3.1、§3.2 的 `qbit_poller`、brief §5.1、票 10）。

送單之後就沒有人在按按鈕了：從 `submitted` 到 `completed` 的每一步都是 qBittorrent 那邊
發生的事，而 qBittorrent **沒有 webhook**（brief §20.2）。所以 Berth 每隔幾秒問一次
`sync/maindata`，把答案套進 plan §3.1 的轉換表。這一支就是那個「套」。

三條規則貫穿整份：

- **轉換一律 compare-and-set**（plan §3.1）。同一列上寫東西的不只這個迴圈：使用者有兩個
  分頁，而重試會把它拉回 `requested`。影響 0 列就放棄本次操作，不覆寫別人的結果。
- **一輪可以走好幾步**。已經做完種的 torrent 加進來時，同一輪裡它會走完
  `submitted → metadata_ready → downloading → completed`——狀態機是逐步的，而輪詢的
  間隔不該決定使用者看到幾個階段。時間線因此仍然說得出它經過了哪些站。
- **事實每一輪都更新，狀態不是。** 進度、client state、save path 只是 qBittorrent 現在
  怎麼說，直接寫；狀態才是 Berth 自己的判斷，走 CAS。

**完成判定**（brief §5.1、§20.2）四條：`progress == 1`、`completion_on > 0`、state 不是
`moving` / `checking*`，再加上「每個要下載的檔案真的在 save path 底下」。前三條由
`TorrentStatus` 回答（協定自己說得出來），第四條要碰檔案系統，所以在這裡。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.qbittorrent import (
    ERROR_STATE,
    MISSING_FILES_STATE,
    QbittorrentClient,
    TorrentFile,
    TorrentStatus,
)
from berth.domain import EventType, IssueType, JobState
from berth.logs import job_context
from berth.models import (
    Event,
    Job,
    JobFile,
    Media,
    PollerSettings,
    QbittorrentSettings,
    Route,
    UnknownTorrent,
)
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.events import EventHub, JobSignal
from berth.services.hints import JobHints
from berth.services.issues import close_settled, record_issue
from berth.services.jobs import freeze, job_locks, record_event, restart_state, transition
from berth.services.qbittorrent import unknown_torrent_detail, unknown_torrents
from berth.services.settings import read_settings, write_settings

logger = logging.getLogger(__name__)

#: 有活躍 job 時的輪詢間隔（plan §3.2）。
ACTIVE_INTERVAL = timedelta(seconds=5)
#: 沒有活躍 job 時。閒著的 Berth 不該每 5 秒吵一次 qBittorrent。
IDLE_INTERVAL = timedelta(seconds=30)
#: 連續失敗時退避的上限（plan §3.2）。
BACKOFF_CEILING = timedelta(minutes=5)

#: `stalledDL` 撐多久才算 `stalled`（plan §3.1 的「超過 N 分鐘」）。
#:
#: 量的是 qBittorrent 自己的 `last_activity`，不是「什麼時候變成 stalledDL 的」——後者要
#: Berth 另外存一個時間戳，而客戶端本來就在量同一件事。10 分鐘是刻意偏長的：追蹤站的
#: 重新 announce 常見是 30 分鐘，但 DHT 與 PEX 讓多數連線在幾分鐘內自己回來，門檻太短
#: 只會讓一列在 `downloading` 與 `stalled` 之間跳來跳去（The One Meaning Rule）。
STALL_AFTER = timedelta(minutes=10)

#: 進度事件的粒度：每跨過一個 25% 寫一筆（plan §3.1）。**不是每一輪一筆**——5 秒一次的
#: 迴圈會在一小時內給一筆 Job 七百多筆事件，那樣的時間線讀不出任何東西。
PROGRESS_STEPS = 4

#: 這些狀態下 Berth 還在等 qBittorrent 動作，所以間隔是 5 秒（plan §3.2 的「活躍」）。
#: `requested` 也算：`add_download` 正在送，而使用者正看著那一列。
ACTIVE_STATES = frozenset(
    {
        JobState.REQUESTED,
        JobState.SUBMITTED,
        JobState.METADATA_READY,
        JobState.DOWNLOADING,
        JobState.STALLED,
    }
)

#: 這些狀態代表「那個 torrent 現在應該在客戶端裡」。不在就是 `client_removed`（plan §3.1）。
#: `requested` 不在其中：那時候 `torrents/add` 都還沒回來。
IN_CLIENT_STATES = frozenset(
    {
        JobState.SUBMITTED,
        JobState.METADATA_READY,
        JobState.DOWNLOADING,
        JobState.STALLED,
    }
)

#: 客戶端裡看到它好好的就接回主幹的幾個狀態（M3 票 02）。沒有人看著的時候（RSS 半夜送的單）
#: 它們不該停在原地等人按：
#:
#: - `submit_failed`：`torrents/add` 逾時或回應讀到一半斷線，而 qBittorrent 其實收下了。它有
#:   Job，所以不是 `unknown_torrent`；不看它的話它永遠停在「送單失敗」而 torrent 照樣在下載。
#: - `missing_files` / `client_error` / `client_removed`：使用者在 qBittorrent 裡自己 recheck、
#:   重新開始、把同一個 torrent 加回去。
#:
#: **不在客戶端裡就什麼都不做**：`submit_failed` 本來就不在那裡，另外三種的 Issue 已經開著。
RECOVERABLE_STATES = frozenset(
    {
        JobState.SUBMIT_FAILED,
        JobState.MISSING_FILES,
        JobState.CLIENT_ERROR,
        JobState.CLIENT_REMOVED,
    }
)

#: poller 每一輪看的全部。
POLLED = IN_CLIENT_STATES | RECOVERABLE_STATES

#: 這一輪可能走到 `submitted → metadata_ready` 的：本來就在 `submitted`，或接回主幹時落在那裡
#: （`submit_failed` 一定是，`client_removed` 在還沒有檔案清單時是）。它們的檔案清單在寫交易之前
#: 先問好（`_listings`）。`missing_files` / `client_error` 不在其中：壞掉的時候多半早就有清單了，
#: 為了少見的例外每一輪替卡住的那幾筆各問一次不值得——真的落在 `submitted` 的話下一輪照常問。
LISTED_STATES = frozenset({JobState.SUBMITTED, JobState.SUBMIT_FAILED, JobState.CLIENT_REMOVED})

#: 客戶端的 state 字串 → Job 的壞掉狀態（plan §3.1）。
#:
#: 鍵用 adapter 的常數而不是字面字串：那兩個字是協定的詞，而**這一份對照是政策**
#: （哪一種客戶端狀態算哪一種問題）。字串只有一個地方寫得出來，政策只有一個地方看得到。
BROKEN_STATES = {
    MISSING_FILES_STATE: (JobState.MISSING_FILES, IssueType.MISSING_FILES),
    ERROR_STATE: (JobState.CLIENT_ERROR, IssueType.CLIENT_ERROR),
}

#: 迴圈自己動的那幾筆事件的 actor（plan §2.3）。
SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class PollOutcome:
    """一輪的結果。"""

    #: 還有 job 在等 qBittorrent。決定 5 秒還是 30 秒。
    active: bool
    #: 這一輪真的動了幾筆狀態。log 與測試看它。
    moved: int
    #: 這一輪在客戶端裡看到幾個無主 torrent。
    unknown: int


async def next_interval(session: AsyncSession) -> timedelta:
    """現在該多久問一次。

    **迴圈每次醒來都重問一次，而不是沿用上一輪算出來的間隔**：使用者按下送單的那一刻
    多半落在一個 30 秒的閒置間隔中間，沿用的話他要對著那一列等最多半分鐘才看到第一個
    變化——而那正是這一票要拿掉的體驗。這與 `health_checker`「醒得比檢查頻繁」是同一個
    形狀，代價也一樣：一次帶索引的 `SELECT ... LIMIT 1`。
    """
    return ACTIVE_INTERVAL if await _has_active(session) else IDLE_INTERVAL


async def _has_active(session: AsyncSession) -> bool:
    return bool(await session.scalar(select(Job.hash).where(Job.state.in_(ACTIVE_STATES)).limit(1)))


def backoff(failures: int) -> timedelta:
    """連續失敗之後下一次多久再試（plan §3.2：退避到 5 分鐘）。

    翻倍到上限為止。第一次失敗仍然等一個完整的閒置間隔——qBittorrent 重啟一次要幾秒，
    立刻重試只會再失敗一次，而每一次失敗都會在健康頁上多記一筆。
    """
    if failures <= 0:
        return IDLE_INTERVAL
    grown: timedelta = IDLE_INTERVAL * (2 ** min(failures - 1, 8))
    return min(grown, BACKOFF_CEILING)


async def poll_downloads(
    session: AsyncSession,
    client: QbittorrentClient,
    hub: EventHub,
    hints: JobHints,
    *,
    now: datetime | None = None,
) -> PollOutcome:
    """問一次 `sync/maindata`，把答案套進 plan §3.1 的轉換表。

    **一輪只問一次客戶端清單**：`sync/maindata` 回的是整台機器的狀態，逐 job 問
    `torrents/info` 會讓一份 40 筆的清單變成 40 次往返。`torrents/files` 是例外——
    只替這一輪可能走出 `submitted` 的那幾筆問（`LISTED_STATES`）。

    **三段，順序就是寫交易紀律**（plan §3.3，M4 票 01）：網路全部問完（`sync`、`files`）→ 這一輪
    要動的每一筆的 `job_lock` 照 hash 排序拿齊 → 才開始寫，一個交易寫完 commit。原本是握著寫交易
    逐筆拿鎖，而 planner 反過來先拿鎖再寫：它握著 Y 的鎖等寫鎖、poller 握著寫鎖等 Y 的鎖，planner
    等滿 `busy_timeout` 就爆 `database is locked`（2026-09-26 試跑）。**不改成逐筆 commit**：一輪
    一個交易才有「Job 接回來與它的 Issue 收掉是同一刻」（`close_settled`），下載中的每一筆每一輪都有
    進度要寫，逐筆 commit 是一輪上百次 fsync；鎖拿齊之後的那一段只剩資料庫，握不了多久。

    **代價在拿鎖那一段**：送單、重試、重新送單握著那一筆的鎖打網路（最久是 `.torrent` 的逾時），
    poller 等它的時候已經握著排序在前的那幾把，那幾筆的 planner、importer 與 API 跟著等——
    是 asyncio 的等待，不是 SQLite 的，所以等得久但不會爆 `database is locked`。
    """
    moment = now or utcnow()
    statuses = {row.hash: row for row in await client.sync()}
    watched = (
        await session.execute(select(Job.hash, Job.state).where(Job.state.in_(POLLED)))
    ).all()
    listings = await _listings(client, statuses, watched)

    moved = 0
    signals: list[JobSignal] = []
    async with job_locks(job_hash for job_hash, _ in watched):
        # 鎖拿齊之後重讀：拿鎖那段時間裡別人（planner、使用者的刪除）可能已經把它推走了。
        jobs = await session.scalars(
            select(Job)
            .where(Job.hash.in_([job_hash for job_hash, _ in watched]), Job.state.in_(POLLED))
            .execution_options(populate_existing=True)
        )
        for job in list(jobs):
            with job_context(job.hash):
                moved += await _advance(
                    session,
                    listings.get(job.hash, ()),
                    signals,
                    job,
                    statuses.get(job.hash),
                    moment,
                )

        unknown = await _record_unknown(session, statuses, moment)
        # 接回主幹的那幾筆（與被別的路徑推走的那幾筆）的管線 Issue 在同一個交易裡收掉：
        # 畫面上不該有一刻是「Job 好了、Issue 還開著」（M3 票 02）。
        await close_settled(session, moment)
        await _remember(session, moment, unknown)
        await session.commit()

    # **推播在 commit 之後。** 反過來的話前端收到「這一筆完成了」就立刻重問一次，而那一次
    # 讀到的是還沒 commit 的舊狀態——畫面因此永遠慢一步（2026-09-10 實跑抓到：每一筆事件
    # 都把畫面推到**上一個**狀態）。推播是「該去問了」的提示，那件事只有在真相已經寫下去
    # 之後才成立。
    for signal in signals:
        hub.publish(signal)

    # 這一輪動了東西就叫醒 `planner_runner`（plan §3.2）。**不挑哪一種轉換**：它自己那兩句
    # 查詢才決定要處理誰，而多醒一次的代價是兩次帶索引的 `SELECT`——少醒一次的代價是
    # 使用者對著「下載完成」等最多一分鐘。
    if moved:
        hints.nudge()

    return PollOutcome(active=await _has_active(session), moved=moved, unknown=len(unknown))


class Downloader:
    """poller 一輪的全部：一條連線、一次 `sync`、一輪轉換。

    **連線握在這裡而不是在迴圈裡**，有兩個理由：

    1. `sync/maindata` 的 `rid` 增量掛在 qBittorrent 那邊的 session 上（2026-09-10 實測：
       不帶 cookie 的話每一輪都回 `full_update`），而 session 就是 HTTP client 的 cookie。
       每輪重造一個 client 等於每輪都要一份全量，那正是 `rid` 要避免的事。
    2. `pipeline` 不可以 import `adapters`（plan §1.3，import-linter 守著），所以「造一個
       qBittorrent client」這件事本來就只能發生在 services。

    失敗那一輪把 client 丟掉：重造就是重新開始，而重新開始本來就會拿到一次全量——
    Berth 這邊的 `MaindataCursor` 與 qBittorrent 那邊的 session 因此自然對齊。
    位址被改掉時同理（使用者在精靈裡換了一台 qBittorrent）。
    """

    def __init__(self, clients: ServiceClientFactory, hub: EventHub, hints: JobHints) -> None:
        self._clients = clients
        self._hub = hub
        self._hints = hints
        self._client: QbittorrentClient | None = None
        self._base_url = ""

    async def poll(self, session: AsyncSession, *, now: datetime | None = None) -> PollOutcome:
        client = await self._connect(session)
        try:
            return await poll_downloads(session, client, self._hub, self._hints, now=now)
        except Exception:
            # 這一輪的失敗可能是 session 過期（403）或連線斷了。下一輪重新開始，
            # 而重新開始的第一件事就是拿一份全量。
            await self.aclose()
            raise

    async def aclose(self) -> None:
        client, self._client = self._client, None
        self._base_url = ""
        if client is not None:
            await client.aclose()

    async def _connect(self, session: AsyncSession) -> QbittorrentClient:
        settings = await read_settings(session, QbittorrentSettings)
        base_url = settings.base_url
        if self._client is not None and self._base_url == base_url:
            return self._client
        await self.aclose()
        client = self._clients.qbittorrent(base_url)
        # **登入失敗在這裡就爆**，與 `sign_in` 不同：那一支刻意吞掉例外，好讓錯誤落在
        # 每個 Route 的纜繩上；這裡沒有纜繩，錯誤就是這個迴圈自己的錯誤，而「被封了」
        # 與「帳密不對」的差別要一路傳到健康頁（`IpBannedError`，plan §8.1）。
        if settings.username:
            await client.login(settings.username, settings.password)
        self._client = client
        self._base_url = base_url
        return client


async def record_poll_failure(session: AsyncSession, error: str) -> int:
    """一輪整個失敗了（連不上、被封、回的東西不對）。回傳連續失敗次數。

    **無主 torrent 的清單留著不動**：這一輪沒問到，不代表它們不在了。清單只有在真的問到
    答案的那一輪才重寫。
    """
    settings = await read_settings(session, PollerSettings)
    settings.failures += 1
    settings.error = error
    settings.checked_at = utcnow()
    await write_settings(session, settings)
    await session.commit()
    return settings.failures


# --- 一筆 Job 的一輪 ----------------------------------------------------


async def _listings(
    client: QbittorrentClient,
    statuses: dict[str, TorrentStatus],
    watched: Sequence[Row[tuple[str, JobState]]],
) -> dict[str, tuple[TorrentFile, ...]]:
    """這一輪可能要建 `job_files` 的那幾筆，先把 `torrents/files` 問好。

    **在拿鎖與寫之前**：問 qBittorrent 的那幾秒不能握著寫交易（plan §3.3）。只讀的請求不必等鎖——
    鎖保證的是「不會做兩次」，而問兩次清單什麼都沒做。
    """
    listings: dict[str, tuple[TorrentFile, ...]] = {}
    for job_hash, state in watched:
        found = statuses.get(job_hash)
        if state in LISTED_STATES and found is not None and found.metadata_ready:
            listings[job_hash] = await client.files(job_hash)
    return listings


async def _advance(
    session: AsyncSession,
    files: tuple[TorrentFile, ...],
    signals: list[JobSignal],
    job: Job,
    status: TorrentStatus | None,
    now: datetime,
) -> int:
    """把一筆 Job 往前推到推不動為止，回傳走了幾步。

    要推播的那幾筆收進 `signals`，由 `poll_downloads` 在 commit 之後才發出去。
    """
    if job.state in RECOVERABLE_STATES:
        if status is None or not await _recover(session, job, status):
            return 0
        recovered = 1
    else:
        recovered = 0

    if status is None:
        # 客戶端裡沒有這一筆了。合併過的清單就是客戶端當下的完整內容（`MaindataCursor`），
        # 所以「不在裡面」不必等 `torrents_removed`——重啟後的第一輪（全量）也成立。
        moved = await _issue(session, job, JobState.CLIENT_REMOVED, IssueType.CLIENT_REMOVED)
        if moved:
            signals.append(JobSignal(hash=job.hash, state=job.state, progress=job.progress))
        return moved

    # 進度門檻比的是**上一輪存下來的值**，所以要在 `_refresh` 蓋掉它之前先拿走。
    # 它已經在資料庫裡，所以這條規則跨得過重啟：Berth 重開之後不會把 25% 那一筆再寫一次。
    was = (job.state, job.progress, job.client_state)
    _refresh(job, status, now)
    steps = 0
    # 上限是狀態總數：一輪最多把一筆 Job 走完整條主幹，走不動就停。有了它，任何一條
    # 意外自我循環的轉換都會被截斷，而不是把迴圈卡死在一筆 Job 上。
    for _ in range(len(JobState)):
        if not await _step(session, files, job, status, now):
            break
        steps += 1
    await _announce_progress(session, job, was[1])
    # **一筆 job 一輪最多一個訊號，而且只有真的變了才推。** 一份 40 筆的下載清單每 5 秒
    # 推 40 次的話，每個開著的分頁就每 5 秒重問一次整份清單——而那正是這條推播要取代的
    # 東西。轉換、進度、client state 三者任一動了才算變了。
    if (job.state, job.progress, job.client_state) != was or recovered:
        signals.append(JobSignal(hash=job.hash, state=job.state, progress=job.progress))
    return steps + recovered


async def _recover(session: AsyncSession, job: Job, status: TorrentStatus) -> bool:
    """客戶端裡看得到它、而且好好的：接回主幹（M3 票 02）。回傳接回了沒有。

    `submit_failed` 與 `client_removed` 看得到就接回——接回之後它若是壞的，下一步照常轉進
    `missing_files` / `client_error`（壞掉優先），那是一件新的、說得對的事。另外兩種要**不再壞**
    才接回：客戶端的狀態字串不是壞掉，而且它說做完了的話檔案真的在磁碟上。後一條是 Berth
    自己發現的那一種 `missing_files`——客戶端說 `stalledUP`，只看字串的話它每一輪都會「恢復」
    再壞一次，時間線與 Issue 清單一起來回翻。

    `submit_failed` 接回 `submitted`，並補上送單成功那一刻該做的：凍結資料夾名、記下「上次用的
    Route」（brief §4.5）——它其實送成功了。
    """
    broken = job.state
    if broken in (JobState.MISSING_FILES, JobState.CLIENT_ERROR):
        if status.state in BROKEN_STATES:
            return False
        missing = await _files_on_disk(session, job, status) if status.complete else []
        if missing:
            return False
    back = (
        JobState.SUBMITTED
        if broken is JobState.SUBMIT_FAILED
        else await restart_state(session, job)
    )
    if not await _to(session, job, back):
        return False
    if broken is JobState.SUBMIT_FAILED:
        await _freeze(session, job)
    await record_event(
        session,
        job,
        EventType.RECOVERED,
        actor=SYSTEM,
        payload={"from": broken.value, "state": back.value, "client_state": status.state},
    )
    logger.info("job recovered", extra={"from": broken.value, "state": back.value})
    return True


async def _freeze(session: AsyncSession, job: Job) -> None:
    media = await session.get(Media, job.media_id) if job.media_id is not None else None
    route = await session.get(Route, job.route_id) if job.route_id is not None else None
    if media is not None and route is not None:
        freeze(media, route)


def _refresh(job: Job, status: TorrentStatus, now: datetime) -> None:
    """qBittorrent 現在怎麼說。**不是狀態轉換**，所以不走 CAS——這幾欄沒有「從哪裡到哪裡」。

    `total_size` 只在客戶端報得出來時才寫：metadata 還沒到的時候它是 `-1`（5.2.3）或
    `0`（4.4.5），照抄會讓畫面上那一格從一個真的大小跳回「—」。
    """
    job.client_state = status.state
    job.progress = status.progress
    job.save_path = status.save_path or job.save_path
    job.content_path = status.content_path or job.content_path
    if status.total_size > 0:
        job.total_size = status.total_size
    job.last_seen_in_client_at = now


async def _step(
    session: AsyncSession,
    files: tuple[TorrentFile, ...],
    job: Job,
    status: TorrentStatus,
    now: datetime,
) -> bool:
    """plan §3.1 中由客戶端狀態觸發的轉換，照表逐條試。走了一步就回 True。

    順序是刻意的：**壞掉優先**——`missingFiles` 的 torrent 也可能 `progress == 1`，
    先問完成的話它會被當成下載好了，而磁碟上根本沒有那些檔案。
    """
    broken = BROKEN_STATES.get(status.state)
    if broken is not None and job.state is not broken[0]:
        return bool(await _issue(session, job, broken[0], broken[1]))

    if job.state is JobState.SUBMITTED:
        return await _metadata_ready(session, files, job, status)

    settled = (JobState.METADATA_READY, JobState.DOWNLOADING, JobState.STALLED)
    if job.state in settled and await _completed(session, job, status, now):
        return True

    if job.state is JobState.METADATA_READY and status.progress > 0:
        return await _to(session, job, JobState.DOWNLOADING)

    if job.state is JobState.DOWNLOADING and _idle_for(status, now) >= STALL_AFTER:
        if not await _to(session, job, JobState.STALLED):
            return False
        await record_event(
            session,
            job,
            EventType.STALLED,
            actor=SYSTEM,
            payload={
                "client_state": status.state,
                "idle_minutes": int(_idle_for(status, now).total_seconds() // 60),
            },
        )
        logger.info("job stalled", extra={"client_state": status.state})
        return True

    if job.state is JobState.STALLED and _idle_for(status, now) < STALL_AFTER:
        # 又動起來了。回 `downloading` 並寫一筆 `progress`——時間線上要看得出它恢復了，
        # 而恢復的那一刻多半沒有剛好跨過一個 25%。
        if not await _to(session, job, JobState.DOWNLOADING):
            return False
        await record_event(
            session,
            job,
            EventType.PROGRESS,
            actor=SYSTEM,
            payload={"progress": round(status.progress, 4), "resumed": True},
        )
        return True

    return False


async def _metadata_ready(
    session: AsyncSession, files: tuple[TorrentFile, ...], job: Job, status: TorrentStatus
) -> bool:
    """`submitted` → `metadata_ready`：檔案清單到手（plan §3.1）。

    兩個條件缺一不可（plan §3.1 的原文）：state 不是 `metaDL`，而且 `torrents/files` 非空。
    只看 state 不行——`checkingResumeData` 也不是 `metaDL`，但那時候清單還沒生出來；
    只看清單也不行——metaDL 期間它回的是 `200` + `[]`，與「這個 torrent 不存在」同形。

    **pre-plan 不在這一票**（plan §3.1 的另一半副作用）：`plans` 表要到票 11 才建。

    `files` 是寫交易之前就問好的那一份（`_listings`）；這一輪沒問到的是空的，下一輪再問。
    """
    if not status.metadata_ready or not files:
        return False
    if not await _to(session, job, JobState.METADATA_READY):
        return False
    await _store_files(session, job, files)
    total = sum(row.size for row in files if row.wanted)
    if total > 0:
        job.total_size = total
    await record_event(
        session,
        job,
        EventType.METADATA_RECEIVED,
        actor=SYSTEM,
        payload={"file_count": len(files), "total_size": total},
    )
    logger.info("job metadata received", extra={"file_count": len(files)})
    return True


async def _store_files(session: AsyncSession, job: Job, files: tuple[TorrentFile, ...]) -> None:
    """建 `job_files`（plan §3.1）。

    `rel_path` 存的是 `torrents/files[].name` **原樣**——它相對 `save_path` 且含 torrent
    自己的根目錄那一層（brief §20.7，2026-09-10 對兩版再驗一次）。不在這裡接成絕對路徑：
    `save_path` 會變（使用者搬 category），而相對路徑不會。

    重入安全（plan §3.3）：`(job_hash, rel_path)` 是 unique，所以已經在的不再插一次——
    這一支在 CAS 成功之後才跑，理論上一筆 Job 只跑一次，但重入是這一整層的規矩。
    """
    existing = set(
        await session.scalars(select(JobFile.rel_path).where(JobFile.job_hash == job.hash))
    )
    for row in files:
        if row.name in existing:
            continue
        session.add(
            JobFile(
                job_hash=job.hash,
                rel_path=row.name,
                size=row.size,
                priority=row.priority,
            )
        )
    await session.flush()


async def _completed(
    session: AsyncSession,
    job: Job,
    status: TorrentStatus,
    now: datetime,
) -> bool:
    """完成判定（brief §5.1、§20.2）。第四條在這裡：檔案真的在 save path 底下。"""
    if not status.complete:
        return False
    if missing := await _files_on_disk(session, job, status):
        # 客戶端說做完了，而 Berth 看得到那個目錄、裡面卻沒有那些檔案。這正是
        # `missingFiles` 說的那件事，只是這一次是 Berth 自己發現的。
        return bool(
            await _issue(
                session,
                job,
                JobState.MISSING_FILES,
                IssueType.MISSING_FILES,
                # 少了哪幾個放在 `detail`，不是 `path`：這一種的冪等鍵是那一筆下載
                # （`SUBJECT_OF` 上寫了理由），而畫面上要說得出少了什麼。
                detail={"missing": missing},
            )
        )
    if not await _to(session, job, JobState.COMPLETED):
        return False
    job.completed_at = now
    await record_event(
        session,
        job,
        EventType.COMPLETED,
        actor=SYSTEM,
        payload={"total_size": job.total_size, "content_path": status.content_path},
    )
    logger.info("job completed", extra={"total_size": job.total_size})
    return True


async def _files_on_disk(session: AsyncSession, job: Job, status: TorrentStatus) -> list[str]:
    """`stat` 不到的那幾個檔案（brief §5.1 的第四條）。全部都在就是空 list。

    **回的是哪幾個而不是成不成**：`missing_files` 那一種 Issue 的冪等鍵是檔案的路徑
    （plan §2.4），而畫面上那一句要說得出少了什麼——只回一個 bool 的話，兩邊都只剩
    「有東西不見了」。

    **Berth 看不到那個 save path 時視為通過。** 那不是這一筆 torrent 的問題，而是掛載對不上
    ——Berth 與 qBittorrent 必須把同一個宿主目錄掛在同一個容器路徑（brief §16.4），而那件事
    本來就有專門的檢查在報：Route 的 `download_path` 纜繩（plan §9.5）。在這裡把它翻譯成
    `missing_files` 會讓每一筆 Job 都紅著，而紅的理由指向錯的地方（PRODUCT 原則 4）。

    「看得到」的第一個條件是**這條路徑在這台機器上是完整的**。qBittorrent 報的一律是容器裡
    的 POSIX 路徑，而 Windows 上 `/downloads/complete` 少了磁碟機代號——`Path` 會把它當成
    「目前磁碟機的根目錄底下」，於是那台機器上剛好有一個同名目錄時這一支就會拿一條
    完全不相干的目錄去比對（2026-09-10 在 Windows 上實跑當場踩到：完成的 torrent 被判成
    `missing_files`）。`is_absolute()` 在 Windows 上對這種路徑回 False，那正是「這台機器
    解析不了它」的答案。

    路徑用 `PurePosixPath` 接：`save_path` 與 `name` 都是**容器裡的 POSIX 路徑**，
    在 Windows 上用 `Path` 接會把分隔符換掉，接出來的字串就不是那一條了。
    """
    root = status.save_path or job.save_path
    if not root or not Path(root).is_absolute() or not Path(root).is_dir():
        return []
    rows = await session.scalars(
        select(JobFile).where(JobFile.job_hash == job.hash, JobFile.priority != 0)
    )
    wanted = list(rows)
    if not wanted:
        return []
    missing: list[str] = []
    for row in wanted:
        target = str(PurePosixPath(root) / row.rel_path)
        try:
            fs.stat(Path(target))
        except OSError:
            logger.warning("completed torrent is missing a file", extra={"path": target})
            missing.append(target)
    return missing


async def _issue(
    session: AsyncSession,
    job: Job,
    state: JobState,
    kind: IssueType,
    *,
    path: str = "",
    detail: dict[str, Any] | None = None,
) -> int:
    """轉進一個「需要人處理」的狀態，並**兩邊都寫**（brief §5.2、plan §2.4、M2 票 05）。

    事件是歷史（時間線上那一行），Issue 是「要有人決定」的那一件（`/issues` 上那一列）。
    M1 只有前者，因為 `issues` 表要到 M2 才有；從票 05 起兩邊都寫，而 `type` 是**同一個**
    封閉集合（`IssueType`）——加一種型別到事件而沒加到表是不可能的，因為只有一份定義。
    """
    if job.state is state:
        return 0
    if not await _to(session, job, state):
        return 0
    payload = {"type": kind.value, "client_state": job.client_state, **(detail or {})}
    await record_event(session, job, EventType.ISSUE_DETECTED, actor=SYSTEM, payload=payload)
    # Issue 多帶一個名字：清單上那一列沒有路徑可以認，只剩 hash 的話使用者分不出是哪一筆
    # （時間線不需要——它就掛在那一筆 Job 底下）。與 `unknown_torrent` 同一個鍵。
    await record_issue(
        session, kind, path=path, job_hash=job.hash, detail={**payload, "name": job.name}
    )
    logger.warning("job issue detected", extra={"issue": kind.value, "state": state.value})
    return 1


async def _to(session: AsyncSession, job: Job, state: JobState) -> bool:
    """compare-and-set，`expected` 就是這一列現在的狀態（plan §3.1）。

    `transition` 與送單共用一份實作：**轉換一律 compare-and-set** 這條規則只能有一個地方
    寫得出來，兩份的話其中一份遲早會少掉 `WHERE state = :from`。
    """
    return await transition(session, job, state, expected=job.state)


async def _announce_progress(session: AsyncSession, job: Job, before: float) -> None:
    """每跨過一個 25% 寫一筆 `progress`（plan §3.1）。

    只在**還在跑**的狀態寫：走到 `completed` 的那一輪已經有一筆 `completed` 事件，
    再補一筆「100%」是同一件事說兩次。
    """
    if job.state not in (JobState.DOWNLOADING, JobState.STALLED):
        return
    if _bucket(job.progress) <= _bucket(before):
        return
    await record_event(
        session,
        job,
        EventType.PROGRESS,
        actor=SYSTEM,
        payload={"progress": round(job.progress, 4)},
    )


def _bucket(progress: float) -> int:
    """0.0–1.0 → 0–4。跨過一格就是跨過一個 25%。"""
    return min(int(progress * PROGRESS_STEPS), PROGRESS_STEPS)


def _idle_for(status: TorrentStatus, now: datetime) -> timedelta:
    """多久沒有任何資料在動。不是 `stalledDL` 的話一律是 0——它現在正在跑。"""
    if not status.idle:
        return timedelta()
    since = status.idle_since
    if since <= 0:
        return timedelta()
    return max(now - datetime.fromtimestamp(since, tz=UTC), timedelta())


# --- 無主 torrent -------------------------------------------------------


async def _record_unknown(
    session: AsyncSession, statuses: dict[str, TorrentStatus], now: datetime
) -> list[UnknownTorrent]:
    """客戶端裡掛著 Berth 記號、而 Berth 沒有 Job 的那幾筆（plan §3.2 的 `unknown_torrent`）。

    **兩道篩子的聯集**：category 是 Berth 某一條 Route 的，或 tag 是 `berth`。只認 category
    的話，Route 被刪掉之後它送出去的那些 torrent 就再也沒有人認領；只認 tag 的話，使用者
    自己丟進 Berth category 的 torrent 看不見——而那一筆之後會被 importer 撿走。

    事件**一個 hash 只寫一次**：這個迴圈每 5 秒跑一輪，每輪一筆的話一天就是一萬七千筆。
    「現在還在不在」由 `settings.poller` 那份清單回答（每一輪重寫）。
    """
    if not statuses:
        return []
    orphans = await unknown_torrents(session, statuses.values())
    if not orphans:
        return []

    reported = set(
        await session.scalars(
            select(Event.job_hash).where(
                Event.type == EventType.ISSUE_DETECTED.value,
                Event.job_hash.in_([row.hash for row in orphans]),
            )
        )
    )
    for row in orphans:
        payload = unknown_torrent_detail(row)
        # Issue 那一邊**每一輪都寫**：它自己是冪等的（同一個 hash 更新那一列的
        # `detected_at`），而「上一次看到它是什麼時候」正是清單上要說的那一句。
        await record_issue(
            session, IssueType.UNKNOWN_TORRENT, job_hash=row.hash, detail=payload, now=now
        )
        if row.hash in reported:
            continue
        session.add(
            Event(
                job_hash=row.hash,
                type=EventType.ISSUE_DETECTED.value,
                actor=SYSTEM,
                payload_json=payload,
                created_at=now,
            )
        )
        logger.warning(
            "unknown torrent in the client",
            extra={"job_id": row.hash, "category": row.category},
        )
    await session.flush()
    return [
        UnknownTorrent(hash=row.hash, name=row.name, category=row.category, state=row.state)
        for row in orphans
    ]


async def _remember(session: AsyncSession, now: datetime, unknown: list[UnknownTorrent]) -> None:
    """這一輪成功了：清掉失敗計數與上一次的錯誤，換上這一輪的無主清單。"""
    settings = await read_settings(session, PollerSettings)
    settings.checked_at = now
    settings.failures = 0
    settings.error = ""
    settings.unknown_torrents = unknown
    await write_settings(session, settings)
