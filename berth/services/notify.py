"""通知：寫進待送表、送出一輪、通知設定（plan §11.5〈通知〉、M4 票 123）。

**寫入與觸發它的狀態變更同一筆交易**（`queue_ready` 不 commit），送出由獨立的迴圈做
（`pipeline/notifying.py`）：管道壞了不阻塞任何管線，觸發的那一筆 rollback 時也沒有通知。

**這是後端第一個自己組人話的地方**：其餘的句子都在前端（i18n key），可是 Discord 的收件人不在瀏覽器
上。所以待送表存事實（作品、季集、Route），送出那一刻照收件人自己的語言（`users.notify_language`，
存 Discord ID 那一刻的介面語言）組字。兩種語言的句子都在 `_TEXT`，與前端一樣 zh-Hant 與 en 並列。

**收件人**（M4 票 125）：訂閱了那一種、有 Discord ID、而且 Jellyfin 的 `UserViews` 看得到那個媒體庫
的人。前兩條在寫入時看（`queue_ready`），媒體庫在送出時問（`send_due`）：寫入在別人的寫交易裡，不能打
網路；Jellyfin 問不到時那一則延後，不猜。同一個人、同一部作品 5 分鐘內的幾筆在寫入時合成一則。

**故障**（M4 票 128，plan §11.5）分三層，因為下一步不同：

- **管道**：token 被拒（`401`）整個暫停到換了 token；連不上（逾時、5xx）照連續失敗的輪數退避；
  整個管道的限速照 `retry_after` 等。狀態在 `settings.notify_sender`，健康頁的「通知」卡讀它。
- **這一則**：自己的限速照 `retry_after` 延後那一則；Discord 拒收（超長）、組不成句子當場放棄。
- **收件人**：到不了（`50278` / `50007`）那一則當場放棄，原因記在那個人身上，他的通知設定頁說出來。

不管哪一種，滿 `GIVE_UP_AFTER` 還沒送到的就放棄：通知說的是「剛剛發生了什麼」，晚一天才到的
「可以看了」已經不是這個意思；token 壞了幾天、一修好就把積下來的全送出去，比沒收到更吵。
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.notify import Delivery, Link, Message, NotifyChannel
from berth.adapters.notify.discord import invite_url
from berth.domain import (
    ADMIN_ONLY_KINDS,
    DeliveryFailure,
    IssueType,
    Language,
    MediaKind,
    NotificationKind,
    NotificationStatus,
    NotifyRefusal,
    PlanAction,
    Role,
)
from berth.logs import job_context
from berth.models import (
    BerthSettings,
    JellyfinSettings,
    Job,
    LedgerEntry,
    Media,
    Notification,
    NotifySenderSettings,
    NotifySettings,
    NotifyWatchSettings,
    Route,
    User,
)
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.deeplink import (
    BerthPage,
    PublicUrlRejectedError,
    berth_link,
    normalized_public_url,
)
from berth.services.issues import still_ignored
from berth.services.jellyfin_access import (
    AccountDisabledError,
    JellyfinUnreachableError,
    visible_libraries,
)
from berth.services.recipients import subscribers
from berth.services.settings import read_settings, update_settings, write_settings
from berth.services.waiting import LIST_PAGE, Waiting, WaitingSource, waiting_now

logger = logging.getLogger(__name__)

#: Discord 的 user ID 是 snowflake：64 位元整數的十進位，現在是 17–20 位。
_SNOWFLAKE = re.compile(r"\d{17,20}")

_TEXT: dict[Language, dict[str, str]] = {
    Language.ZH_HANT: {
        "ready": "可以看了：{title}",
        "downloading": "正在下載：{title}",
        "open": "在 Berth 打開",
        "test_title": "Berth 測試訊息",
        "test_body": "收到這一則，Berth 的通知就接通了。",
        "waiting": "有 {count} 件等你處理",
        "waiting_new": "新增 {count} 件：{parts}",
        "waiting_gap": "、",
        "review_one": "{count} 件待審核",
        "review_many": "{count} 件待審核",
        "issue_one": "{count} 個 Issue（{types}）",
        "issue_many": "{count} 個 Issue（{types}）",
        "rss_one": "{count} 個 RSS Series 待綁定",
        "rss_many": "{count} 個 RSS Series 待綁定",
        "review_field": "待審核",
        "issue_field": "Issue",
        "rss_field": "待綁定",
        "review_list": "打開審核",
        "issue_list": "打開 Issue",
        "rss_list": "打開 RSS",
        "lingering": "有一件等了 {days} 天",
        "weekly": "週報：{first} – {last}",
        "weekly_body": "入庫 {works} 部（{episodes} 集）· 修了 {fixed} 件 · 等你處理 {waiting} 件",
        "weekly_open": "打開週報",
    },
    Language.EN: {
        "ready": "Ready to watch: {title}",
        "downloading": "Downloading: {title}",
        "open": "Open in Berth",
        "test_title": "Berth test message",
        "test_body": "If you can read this, Berth notifications are working.",
        "waiting": "{count} waiting for you",
        "waiting_new": "{count} new: {parts}",
        "waiting_gap": ", ",
        "review_one": "{count} to review",
        "review_many": "{count} to review",
        "issue_one": "{count} issue ({types})",
        "issue_many": "{count} issues ({types})",
        "rss_one": "{count} RSS series to bind",
        "rss_many": "{count} RSS series to bind",
        "review_field": "To review",
        "issue_field": "Issues",
        "rss_field": "To bind",
        "review_list": "Open review",
        "issue_list": "Open issues",
        "rss_list": "Open RSS",
        "lingering": "Waiting for {days} days",
        "weekly": "Weekly report: {first} – {last}",
        "weekly_body": (
            "{works} titles imported ({episodes} episodes) · {fixed} fixed · {waiting} waiting"
        ),
        "weekly_open": "Open the weekly report",
    },
}

#: 「1 個 Issue（檔案遺失）」括號裡那幾個字：前端 `issues.typeLabel` 的同一組詞（英文那邊前端是
#: 全大寫的標籤，句子裡用小寫）。每一種型別都要有，`tests/unit/test_notify_text.py` 守。
_ISSUE_LABEL: dict[Language, dict[IssueType, str]] = {
    Language.ZH_HANT: {
        IssueType.LIBRARY_LINK_MISSING: "鏈接遺失",
        IssueType.SOURCE_MISSING: "來源遺失",
        IssueType.INODE_MISMATCH: "INODE 不符",
        IssueType.ORPHAN_COMPLETE: "無主目錄",
        IssueType.UNKNOWN_TORRENT: "無主 torrent",
        IssueType.UNMANAGED_LIBRARY_FILE: "非受管檔案",
        IssueType.JOB_WITHOUT_FILES: "帳本為空",
        IssueType.MISSING_FILES: "檔案遺失",
        IssueType.CLIENT_ERROR: "客戶端錯誤",
        IssueType.CLIENT_REMOVED: "已被移除",
        IssueType.JELLYFIN_ITEM_UNRESOLVED: "反查失敗",
        IssueType.JELLYFIN_ITEM_MISMATCH: "回驗不符",
        IssueType.LIBRARY_USES_TVDB: "TVDB",
        IssueType.LOW_DISK_SPACE: "空間不足",
        IssueType.FIRST_BATCH_STUCK: "第一批卡住",
        IssueType.FEED_POLL_FAILING: "輪詢一直失敗",
        IssueType.FEED_BACKFILL_FAILING: "補漏一直失敗",
        IssueType.SERIES_EPISODES_MISSING: "缺集",
        IssueType.SERIES_EPISODES_COLLIDE: "同一集多份",
        IssueType.SUBMIT_FAILED: "送單失敗",
        IssueType.IMPORT_FAILED: "入庫失敗",
        IssueType.STALLED: "停滯",
    },
    Language.EN: {
        IssueType.LIBRARY_LINK_MISSING: "link missing",
        IssueType.SOURCE_MISSING: "source missing",
        IssueType.INODE_MISMATCH: "inode mismatch",
        IssueType.ORPHAN_COMPLETE: "orphan folder",
        IssueType.UNKNOWN_TORRENT: "unknown torrent",
        IssueType.UNMANAGED_LIBRARY_FILE: "unmanaged file",
        IssueType.JOB_WITHOUT_FILES: "empty ledger",
        IssueType.MISSING_FILES: "files missing",
        IssueType.CLIENT_ERROR: "client error",
        IssueType.CLIENT_REMOVED: "removed",
        IssueType.JELLYFIN_ITEM_UNRESOLVED: "not in Jellyfin",
        IssueType.JELLYFIN_ITEM_MISMATCH: "Jellyfin disagrees",
        IssueType.LIBRARY_USES_TVDB: "TVDB",
        IssueType.LOW_DISK_SPACE: "low disk",
        IssueType.FIRST_BATCH_STUCK: "first batch stuck",
        IssueType.FEED_POLL_FAILING: "feed keeps failing",
        IssueType.FEED_BACKFILL_FAILING: "backfill keeps failing",
        IssueType.SERIES_EPISODES_MISSING: "episodes missing",
        IssueType.SERIES_EPISODES_COLLIDE: "episodes collide",
        IssueType.SUBMIT_FAILED: "submit failed",
        IssueType.IMPORT_FAILED: "import failed",
        IssueType.STALLED: "stalled",
    },
}

#: 這幾種是管道本身送不出去，不是這一位收件人的事：這一輪不再送下一則。
_CHANNEL_DOWN = frozenset(
    {DeliveryFailure.UNAUTHORIZED, DeliveryFailure.RATE_LIMITED, DeliveryFailure.UNAVAILABLE}
)

#: 說的是某個媒體庫裡的作品：只送給 Jellyfin 上看得到那個媒體庫的人（M4 票 125）。
_BY_LIBRARY = frozenset({NotificationKind.READY, NotificationKind.DOWNLOADING})

#: 再送也一樣的：那一則當場放棄。
_FINAL = frozenset({DeliveryFailure.RECIPIENT_UNREACHABLE, DeliveryFailure.REJECTED})

#: 寫入之後等多久才送（M4 票 125）：這段時間裡同一個收件人、同一部作品的下一筆併進同一則，
#: 一次入庫一整季時不是一集一則。
MERGE_WINDOW = timedelta(minutes=5)

#: 離最早送出時間不到這麼久的那一則不再併進去，另起一則（M4 票 125 code-review）。送出迴圈讀完
#: 就放開交易、接著打 Discord：併進一則已經被撿走的，新的季集就跟著舊內容一起被標成已送。
#: 判斷到 commit 之間要等寫鎖，30 秒遠大於它，代價只是相隔 4 分半到 5 分鐘的兩筆分成兩則。
_MERGE_GUARD = timedelta(seconds=30)

#: 「有 N 件等你處理」第一件出現之後等多久才送（M4 票 127，plan §11.5）：這段時間裡再出現的併進
#: 同一則。比「可以看了」長：一次對帳、一批 RSS 長出來的那幾件常常隔幾分鐘才一一落地。
WAIT_WINDOW = timedelta(minutes=10)

#: 「等你處理」一個人一則，合併鍵就是種類本身。
_WAITING_KEY = NotificationKind.WAITING.value

#: 「等你處理」那一則的內容只有一格：這一波新出現的那幾件的鍵（`waiting` 的形狀）。
_NEW = "new"

#: 「放太久」的提醒（M4 票 129）：同一種、自己的合併鍵；內容多一格等了幾天。
_LINGER_KEY = f"{NotificationKind.WAITING.value}:lingering"
_DAYS = "days"

#: 一則從最早送出時間（`not_before`）起，滿這麼久還沒送到就放棄（M4 票 128，plan §11.5）。
#: 用時間不用次數：次數管不到「沒設 token」「token 壞了」這種一次都沒送的情況，而這幾種正是
#: 修好之後會一次湧出來的。一天：Discord 的事故多半幾小時內恢復，隔夜的那一則還接得到。
GIVE_UP_AFTER = timedelta(hours=24)

#: 連不上時第一次的退避；之後每一輪加倍，最多 `_BACKOFF_CAP`。
_BACKOFF_FIRST = timedelta(seconds=30)
_BACKOFF_CAP = timedelta(hours=1)

#: 限速卻沒說要等多久時等的秒數（Discord 一定給，這是防回的不是 Discord）。
_RATE_LIMIT_FALLBACK = 1.0

#: 「Route」在兩種介面裡都是這個詞（CONTEXT.md）。
_ROUTE = "Route"


class NotifyRefusedError(Exception):
    """通知設定的命令不做。`reason` 是畫面說哪一句話的依據，`detail` 是 Discord 的原文。"""

    def __init__(self, reason: NotifyRefusal, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class BotView:
    """通知設定頁管理員那一半：bot 與 Berth 的網址（M4 票 125 起與「我的通知」分開）。
    **沒有 token**：只說設定了沒。"""

    bot_configured: bool
    bot_name: str
    invite_url: str | None
    #: Discord 不再接受存著的那一把 token（M4 票 128）：通知暫停到換一把。
    token_rejected: bool
    #: Berth 從外面看的網址（`BerthSettings`）；沒存過是空字串，通知不附連結。
    berth_url: str


@dataclass(frozen=True, slots=True)
class MyNotifyView:
    """「我的通知」：每一位登入的人讀自己的那一份（M4 票 125）。bot 只說有沒有、叫什麼：
    測試鍵與「私訊會從誰來」要用，token 與邀請連結是管理員那一半。"""

    bot_configured: bool
    bot_name: str
    discord_user_id: str
    language: Language
    #: 訂閱的種類，照 `NotificationKind` 的順序。
    kinds: tuple[NotificationKind, ...]
    #: 上一次送給這個人時他到不了（`User.notify_unreachable_at`）；`None` 是沒有。
    unreachable_at: datetime | None
    unreachable_detail: str


@dataclass(frozen=True, slots=True)
class ChannelView:
    """健康頁的「通知」卡（M4 票 128）：管道現在送不送得出去。"""

    #: 設了 bot token 沒有。沒設就什麼都不送，不是壞了。
    configured: bool
    token_rejected: bool
    #: 連續幾輪連不上 Discord。
    failures: int
    #: 最後一次管道層級失敗的原文（英文）。
    error: str
    failed_at: datetime | None
    #: 在這之前不送（退避或整個管道的限速）。
    resume_at: datetime | None
    last_sent_at: datetime | None
    #: 待送表上還沒送、也還沒放棄的。
    pending: int


@dataclass(frozen=True, slots=True)
class SendOutcome:
    sent: int
    failed: int


# --- 設定 -----------------------------------------------------------------


@command(Effect.READ)
async def read_bot(session: AsyncSession) -> BotView:
    settings = await read_settings(session, NotifySettings)
    sender = await read_settings(session, NotifySenderSettings)
    configured = bool(settings.discord_bot_token)
    return BotView(
        bot_configured=configured,
        bot_name=settings.discord_bot_name if configured else "",
        invite_url=(
            invite_url(settings.discord_application_id)
            if configured and settings.discord_application_id
            else None
        ),
        token_rejected=_rejected(settings, sender),
        berth_url=(await read_settings(session, BerthSettings)).public_url,
    )


@command(Effect.READ)
async def read_mine(session: AsyncSession, user_id: int) -> MyNotifyView:
    settings = await read_settings(session, NotifySettings)
    user = await session.get(User, user_id)
    if user is None:
        raise LookupError(f"user {user_id} is gone")
    configured = bool(settings.discord_bot_token)
    return MyNotifyView(
        bot_configured=configured,
        bot_name=settings.discord_bot_name if configured else "",
        discord_user_id=user.discord_user_id,
        language=user.notify_language,
        kinds=_kinds_of(user),
        unreachable_at=user.notify_unreachable_at,
        unreachable_detail=user.notify_unreachable_detail,
    )


def _kinds_of(user: User) -> tuple[NotificationKind, ...]:
    """存的那一份照 `NotificationKind` 的順序；不認得的值（之後拿掉的種類）略過。"""
    stored = set(user.notify_kinds_json)
    return tuple(kind for kind in NotificationKind if kind.value in stored)


@command(Effect.READ)
async def read_channel(session: AsyncSession) -> ChannelView:
    """管道上一輪之後的樣子。**不連 Discord**：健康頁看的是紀錄。"""
    settings = await read_settings(session, NotifySettings)
    sender = await read_settings(session, NotifySenderSettings)
    pending = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.status == NotificationStatus.PENDING)
    )
    return ChannelView(
        configured=bool(settings.discord_bot_token),
        token_rejected=_rejected(settings, sender),
        failures=sender.failures,
        error=sender.error,
        failed_at=sender.failed_at,
        resume_at=sender.resume_at,
        last_sent_at=sender.last_sent_at,
        pending=int(pending or 0),
    )


def _fingerprint(token: str) -> str:
    """認得出「是不是同一把」就夠了，不必能還原：存的是雜湊的前 16 個十六進位字。"""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _rejected(settings: NotifySettings, sender: NotifySenderSettings) -> bool:
    token = settings.discord_bot_token
    return bool(token) and sender.rejected_token == _fingerprint(token)


# 改設定，brief §14 永遠要人（M5 票 04）：換回原本的 token 是人的事。
@command(Effect.IRREVERSIBLE)
async def set_bot_token(
    session: AsyncSession, factory: ServiceClientFactory, token: str
) -> BotView:
    """存 bot token。**先問 Discord 它是哪一個 bot**，問得到才存（順手記下 application id 與名字，
    邀請連結照它組）；空字串是清掉。網路在寫交易之前（plan §3.3）。"""
    token = token.strip()
    if not token:
        await update_settings(session, NotifySettings, _clear_bot)
        logger.info("discord bot token cleared")
        return await read_bot(session)
    try:
        identity = await factory.discord(token).identify()
    except AuthFailedError as exc:
        raise NotifyRefusedError(NotifyRefusal.TOKEN_REJECTED, str(exc)) from exc
    except ServiceError as exc:
        raise NotifyRefusedError(NotifyRefusal.DISCORD_UNREACHABLE, str(exc)) from exc

    def change(settings: NotifySettings) -> None:
        settings.discord_bot_token = token
        settings.discord_application_id = identity.application_id
        settings.discord_bot_name = identity.name

    await update_settings(session, NotifySettings, change)
    logger.info("discord bot token saved", extra={"bot": identity.name})
    return await read_bot(session)


def _clear_bot(settings: NotifySettings) -> None:
    settings.discord_bot_token = ""
    settings.discord_application_id = ""
    settings.discord_bot_name = ""


# 同上：改的是這個人的通知設定。
@command(Effect.IRREVERSIBLE)
async def set_mine(
    session: AsyncSession,
    user_id: int,
    discord_id: str,
    language: Language,
    kinds: Iterable[NotificationKind],
) -> MyNotifyView:
    """存這個人的 Discord user ID、通知語言（存的那一刻的介面語言）與要收的種類。空 ID 是不收。

    **已經排著的不跟著改**（M4 票 125）：取消訂閱之後，合併時間裡那一則照送——那是訂閱時發生的事。
    """
    discord_id = discord_id.strip()
    if discord_id and not _SNOWFLAKE.fullmatch(discord_id):
        raise NotifyRefusedError(NotifyRefusal.DISCORD_ID_INVALID)
    user = await session.get(User, user_id)
    if user is None:
        raise LookupError(f"user {user_id} is gone")
    if discord_id != user.discord_user_id:
        # 「到不了」說的是舊的那一個 ID。
        _clear_unreachable(user)
    user.discord_user_id = discord_id
    user.notify_language = language
    chosen = set(kinds)
    if user.role is not Role.ADMIN:
        # 一般使用者看不到、也收不到這幾種（M4 票 127）：存下來的就是他實際會收的。
        chosen -= ADMIN_ONLY_KINDS
    user.notify_kinds_json = [kind.value for kind in NotificationKind if kind in chosen]
    await session.commit()
    return await read_mine(session, user_id)


# 同上。
@command(Effect.IRREVERSIBLE)
async def set_berth_url(session: AsyncSession, value: str) -> BotView:
    """存 Berth 從外面看的網址（`deeplink.normalized_public_url`：http(s) 的絕對網址、拿掉結尾
    的 `/`）。空字串是清掉，之後的通知不附連結。已經寫進待送表的那幾則也照新的組：
    連結在送出時才組。"""
    try:
        url = normalized_public_url(value)
    except PublicUrlRejectedError as exc:
        raise NotifyRefusedError(NotifyRefusal.BERTH_URL_INVALID, str(exc)) from exc

    def change(settings: BerthSettings) -> None:
        settings.public_url = url

    await update_settings(session, BerthSettings, change)
    return await read_bot(session)


# 送出去的訊息收不回來。
@command(Effect.IRREVERSIBLE)
async def send_test(session: AsyncSession, factory: ServiceClientFactory, user_id: int) -> Delivery:
    """送一則測試訊息給按的人，回 Discord 怎麼說（開 DM channel 恆 200，所以要真的送一則，
    brief §20.23）。**不經過待送表**：結果要當場說，而且它不是任何狀態變更的通知。"""
    settings = await read_settings(session, NotifySettings)
    if not settings.discord_bot_token:
        raise NotifyRefusedError(NotifyRefusal.BOT_MISSING)
    user = await session.get(User, user_id)
    if user is None or not user.discord_user_id:
        raise NotifyRefusedError(NotifyRefusal.DISCORD_ID_MISSING)
    recipient, language = user.discord_user_id, user.notify_language
    # 讀的交易先收掉，送出那幾秒不握著它。
    await session.commit()
    text = _TEXT[language]
    delivery = await factory.discord(settings.discord_bot_token).send(
        recipient, Message(title=text["test_title"], description=text["test_body"])
    )
    if not delivery.delivered:
        logger.warning(
            "discord test message failed",
            extra={"failure": delivery.failure, "detail": delivery.detail},
        )
    # 補好之後按測試就是驗證：收件人那一句跟著結果改。token 被拒也記下（存的那一刻是好的，之後在
    # Discord 被重設，健康頁才說得出來）；限速與連不上不動管道的退避：那是人按的一次，不是一輪。
    moment = utcnow()
    await _note_recipient(session, user_id, delivery, moment)
    if delivery.failure is DeliveryFailure.UNAUTHORIZED:
        await _note_rejected(session, settings.discord_bot_token, delivery, moment)
    return delivery


# --- 寫入 -----------------------------------------------------------------


# 寫下的那幾則一旦送出就收不回來（送出迴圈不等人）。
@command(Effect.IRREVERSIBLE)
async def queue_ready(session: AsyncSession, job: Job, *, now: datetime) -> int:
    """「可以看了」：這一筆的正片在 Jellyfin 全部認出來了（`jellyfin_item_resolved`）。

    給每一位訂閱了、有 Discord ID 的人各排一則，回排了（或併進）幾則。**不 commit**：與寫事件的
    那一筆交易同生死。**看不看得到那個媒體庫在送出時才問 Jellyfin**（`send_due`）：這裡在寫交易裡，
    不打網路（plan §3.3）；而且送出那一刻的權限才是準的。

    **合併**（M4 票 125）：最早送出時間是 `MERGE_WINDOW` 之後；同一個收件人、同一部作品、同一條
    Route 還在那段時間裡的一則存在時，這一筆的季集併進它，不另起一列。Route 也要相同：媒體庫看
    Route，兩條 Route 的同一部作品可能一個人看得到一半。

    **寫不成也不讓那一筆交易失敗**（M4 票 128）：讀不出內容時記 log、不排，回 0。這裡的查詢不
    autoflush：呼叫端還沒 flush 的改動要是有錯，在它自己 commit 時爆，不在這裡被吞掉。
    """
    try:
        with session.no_autoflush:
            route = await session.get(Route, job.route_id) if job.route_id else None
            if route is None:
                # 不知道在哪個媒體庫，就問不了誰看得到；入庫過的 Job 一定有 Route，這是防回的。
                with job_context(job.hash):
                    logger.warning("ready notification not queued: the job has no route")
                return 0
            recipients = await subscribers(session, NotificationKind.READY)
            if not recipients:
                return 0
            content = await _ready_content(session, job, route)
            key = f"{job.media_id}@{route.id}" if job.media_id else job.hash
            gathering = {
                row.user_id: row
                for row in await session.scalars(
                    select(Notification).where(
                        Notification.kind == NotificationKind.READY,
                        Notification.merge_key == key,
                        Notification.status == NotificationStatus.PENDING,
                        # 送出迴圈只撿 `not_before` 已到的；留 `_MERGE_GUARD` 給「判斷之後、commit
                        # 之前」那段時間，不改到送到一半的那一則。
                        Notification.not_before > now + _MERGE_GUARD,
                    )
                )
            }
    except Exception:
        # job id 由上下文蓋上去（`berth.logs`）；`extra={"job": …}` 會撞到它。
        with job_context(job.hash):
            logger.exception("ready notification not queued")
        return 0
    for user in recipients:
        row = gathering.get(user.id)
        if row is not None:
            row.content_json = _merged(row.content_json, content)
            continue
        session.add(
            Notification(
                user_id=user.id,
                kind=NotificationKind.READY,
                content_json=content,
                merge_key=key,
                not_before=now + MERGE_WINDOW,
                created_at=now,
            )
        )
    return len(recipients)


def _merged(gathered: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
    """同一部作品、同一條 Route 的兩份事實：季集範圍合起來，其餘取新的那一份（作品名可能
    剛改過）。"""
    spans = collapse_spans([*(gathered.get("episodes") or []), *(content.get("episodes") or [])])
    return {**content, "episodes": [list(span) for span in spans]}


async def _ready_content(session: AsyncSession, job: Job, route: Route) -> dict[str, Any]:
    """事實，不是句子：作品的兩種標題、季集範圍、Route 名與它的媒體庫。組字在送出時（`_render`），
    誰看得到也在送出時問（`library`，`send_due`）。"""
    media = await session.get(Media, job.media_id) if job.media_id else None
    snapshot = media.snapshot() if media else None
    features = await session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.job_hash == job.hash, LedgerEntry.action == PlanAction.IMPORT
        )
    )
    movie = snapshot is not None and snapshot.kind is MediaKind.MOVIE
    return {
        "media": job.media_id,
        "kind": snapshot.kind.value if snapshot else None,
        "title": snapshot.title if snapshot else job.name,
        "title_en": snapshot.title_en if snapshot else job.name,
        "route": route.name,
        "library": route.jellyfin_library_id,
        "episodes": [] if movie else [list(span) for span in episode_spans(features)],
    }


def episode_spans(entries: Iterable[LedgerEntry]) -> list[tuple[int, int, int]]:
    """帳本的季集收成連續的範圍：E01、E02、E03 是一段，E05 另一段。沒有季集的（電影）不算。"""
    return collapse_spans(
        (entry.season, entry.episode_start, entry.episode_end or entry.episode_start)
        for entry in entries
        if entry.season is not None and entry.episode_start is not None
    )


def collapse_spans(points: Iterable[Sequence[int]]) -> list[tuple[int, int, int]]:
    """`(季, 起, 迄)` 排好、接得上（重疊或相鄰）的併成一段。"""
    spans: list[tuple[int, int, int]] = []
    for season, start, end in sorted((point[0], point[1], point[2]) for point in points):
        if spans and spans[-1][0] == season and start <= spans[-1][2] + 1:
            spans[-1] = (season, spans[-1][1], max(spans[-1][2], end))
        else:
            spans.append((season, start, end))
    return spans


@command(Effect.IRREVERSIBLE)
async def watch_waiting(session: AsyncSession, *, now: datetime | None = None) -> int:
    """「有 N 件等你處理」的看守一輪（M4 票 127）：現在等著的（`waiting.waiting_now`）與上一輪看到的
    （`NotifyWatchSettings.seen`）比，新出現的排給每一位訂閱了、有 Discord ID 的管理員，回排了
    （或併進）幾則。送出迴圈每一輪先跑它。

    - **第一次看**（`seen` 是 `None`）只記下來不排：升級那一刻已經在等的不是「新的一件」。
    - **被忽略、條件仍在而又開的 Issue** 記下來、不排（`issues.still_ignored`）。
    - **合併**：最早送出時間是第一件出現之後 `WAIT_WINDOW`；那段時間裡（離送出還有 `_MERGE_GUARD`
      以上）再出現的併進同一則，理由同 `queue_ready`。
    - 一件處理掉、之後又回到清單上（解除綁定、撤銷之後回審核）就是新的一件：比的是上一輪，不是歷史。

    送什麼在送出時才算（`_render_waiting`）：這裡只記這一波有哪幾件。

    **不 commit**：排下的那幾則與看過的那一份一起落地，由呼叫端 commit（送出迴圈接著跑的
    `send_due` 一開頭就 commit）。一輪只借一次連線：中間多 commit 一次，關機時 cancel 落在兩次之間
    就漏一條連線（`test_loop_shutdown`）。只有這個迴圈寫 `settings.notify_waiting`，不必
    `update_settings` 的寫鎖重讀。
    """
    moment = now or utcnow()
    current = await waiting_now(session)
    watched = await read_settings(session, NotifyWatchSettings)
    if (
        watched.seen is not None
        and set(watched.seen) == set(current)
        and set(watched.since) == set(current)
    ):
        return 0
    seen = set(watched.seen or ())
    appeared = [] if watched.seen is None else [key for key in current if key not in seen]
    quiet = await still_ignored(
        session,
        [current[key].ref for key in appeared if current[key].source is WaitingSource.ISSUE],
    )
    fresh = [
        key
        for key in appeared
        if not (current[key].source is WaitingSource.ISSUE and current[key].ref in quiet)
    ]
    queued = await _queue_waiting(session, fresh, moment) if fresh else 0
    watched.seen = sorted(current)
    watched.since = {key: watched.since.get(key, moment) for key in current}
    await write_settings(session, watched)
    return queued


async def _queue_waiting(session: AsyncSession, fresh: list[str], moment: datetime) -> int:
    recipients = await subscribers(session, NotificationKind.WAITING)
    if not recipients:
        return 0
    gathering = {
        row.user_id: row
        for row in await session.scalars(
            select(Notification).where(
                Notification.kind == NotificationKind.WAITING,
                Notification.merge_key == _WAITING_KEY,
                Notification.status == NotificationStatus.PENDING,
                Notification.not_before > moment + _MERGE_GUARD,
            )
        )
    }
    for user in recipients:
        row = gathering.get(user.id)
        if row is not None:
            before = list(row.content_json.get(_NEW) or [])
            row.content_json = {_NEW: before + [key for key in fresh if key not in before]}
            continue
        session.add(
            Notification(
                user_id=user.id,
                kind=NotificationKind.WAITING,
                content_json={_NEW: list(fresh)},
                merge_key=_WAITING_KEY,
                not_before=moment + WAIT_WINDOW,
                created_at=moment,
            )
        )
    return len(recipients)


# 送出去的訊息收不回來。
@command(Effect.IRREVERSIBLE)
async def queue_lingering(session: AsyncSession, key: str, *, days: int, now: datetime) -> int:
    """「放太久」的提醒（M4 票 129，每日巡檢排）：`key`（`waiting` 的鍵）那一件已經等了 `days` 天，
    給每一位訂閱了「等你處理」、有 Discord ID 的管理員排一則，回排了幾則。

    同一種訂閱、同一條送出的路：內容是只有那一件的一波（`_NEW`），所以送出前它處理掉了就照
    `_settled_wave` 放棄；合併鍵不同（`_LINGER_KEY`），不併進、也不被併進那一則「有新的一件」。
    立刻送：巡檢一天一次，等它的人不必再多等 10 分鐘。**不 commit**。
    """
    recipients = await subscribers(session, NotificationKind.WAITING)
    for user in recipients:
        session.add(
            Notification(
                user_id=user.id,
                kind=NotificationKind.WAITING,
                content_json={_NEW: [key], _DAYS: days},
                merge_key=_LINGER_KEY,
                not_before=now,
                created_at=now,
            )
        )
    return len(recipients)


def describe_spans(spans: Sequence[Sequence[int]]) -> str:
    """`S01E01–E03, E05, S02E01`：同一季接著寫集，換季才再寫季。"""
    parts: list[str] = []
    season_now: int | None = None
    for season, start, end in spans:
        episodes = f"E{start:02d}" if start == end else f"E{start:02d}–E{end:02d}"
        parts.append(episodes if season == season_now else f"S{season:02d}{episodes}")
        season_now = season
    return ", ".join(parts)


# --- 送出 -----------------------------------------------------------------


# 送出去的訊息收不回來。
@command(Effect.IRREVERSIBLE)
async def send_due(
    session: AsyncSession, factory: ServiceClientFactory, *, now: datetime | None = None
) -> SendOutcome:
    """送一輪：先放棄滿 `GIVE_UP_AFTER` 的，再把到時間、還沒送的每一則各送一次。

    **網路不在寫交易裡**（plan §3.3）：先讀完收掉讀的交易，逐則送、逐則 commit 結果——一則幾毫秒的
    寫，不讓一輪的 Discord 往返握著寫鎖。**一則出例外不拖累下一則**：記在那一則上，接著送。
    """
    moment = now or utcnow()
    await _give_up_stale(session, moment)
    settings = await read_settings(session, NotifySettings)
    sender = await read_settings(session, NotifySenderSettings)
    token = settings.discord_bot_token
    paused = sender.resume_at is not None and sender.resume_at > moment
    if not token or paused or _rejected(settings, sender):
        await session.commit()
        return SendOutcome(sent=0, failed=0)
    berth_url = (await read_settings(session, BerthSettings)).public_url
    jellyfin = await read_settings(session, JellyfinSettings)
    rows = list(
        (
            await session.execute(
                select(Notification, User)
                .join(User, User.id == Notification.user_id)
                .where(
                    Notification.status == NotificationStatus.PENDING,
                    Notification.not_before <= moment,
                    or_(Notification.retry_at.is_(None), Notification.retry_at <= moment),
                    User.discord_user_id != "",
                )
                .order_by(Notification.id)
            )
        ).tuples()
    )
    # 「等你處理」送出時重算還剩哪幾件：一輪問一次，在讀的交易裡。
    current = (
        await waiting_now(session)
        if any(notification.kind is NotificationKind.WAITING for notification, _ in rows)
        else {}
    )
    await session.commit()
    if not rows:
        return SendOutcome(sent=0, failed=0)
    libraries, unreachable = await _libraries_of(
        factory,
        jellyfin,
        {
            user.id: user.jellyfin_user_id
            for notification, user in rows
            if notification.kind in _BY_LIBRARY
        },
    )
    bot = factory.discord(token)
    sent = failed = 0
    for notification, user in rows:
        if notification.kind in ADMIN_ONLY_KINDS and _not_admin(notification, user):
            await session.commit()
            continue
        if notification.kind in _BY_LIBRARY and _withheld(notification, libraries, unreachable):
            await session.commit()
            continue
        if notification.kind is NotificationKind.WAITING and _settled_wave(
            notification, user, current
        ):
            await session.commit()
            continue
        delivery = await _deliver(bot, notification, user, berth_url, current)
        if delivery is None:
            failed += 1
            await session.commit()
            continue
        _settle(notification, user, delivery, moment)
        if delivery.delivered:
            sent += 1
        else:
            failed += 1
            logger.warning(
                "notification not delivered",
                extra={
                    "notification": notification.id,
                    "failure": delivery.failure,
                    "detail": delivery.detail,
                },
            )
        await _note_channel(session, token, delivery, moment)
        if delivery.failure in _CHANNEL_DOWN:
            # 管道這一刻送不出任何一則：接著送只會把每一則的 `attempts` 灌高，限速時還多扣額度
            # （失敗的請求也算，brief §20.23）。剩下的留給下一輪。
            break
    return SendOutcome(sent=sent, failed=failed)


async def _libraries_of(
    factory: ServiceClientFactory, settings: JellyfinSettings, people: dict[int, str]
) -> tuple[dict[int, frozenset[str] | None], str]:
    """每一位收件人（`users.id` → Jellyfin user id）現在看得到的媒體庫；帳號停用或刪掉的是 `None`。

    **網路在讀交易之外**（呼叫端已經 commit）。問不到 Jellyfin 就停在那一位：剩下的人這一輪也
    問不到，逐一等逾時只會拖住整輪。沒問到的人不在回的 dict 裡，第二格是問不到的原文。
    """
    if not people:
        return {}, ""
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    found: dict[int, frozenset[str] | None] = {}
    try:
        for user_id, jellyfin_user_id in people.items():
            try:
                found[user_id] = await visible_libraries(client, jellyfin_user_id)
            except AccountDisabledError:
                found[user_id] = None
            except JellyfinUnreachableError as exc:
                logger.warning(
                    "notification recipients unknown: jellyfin unreachable",
                    extra={"detail": exc.detail},
                )
                return found, exc.detail
    finally:
        await client.aclose()
    return found, ""


def _withheld(
    notification: Notification, libraries: dict[int, frozenset[str] | None], unreachable: str
) -> bool:
    """收件人看不到這一則說的那個媒體庫時擋下它、記下原因，回 `True`（M4 票 125）。

    看不到、帳號停用或刪掉的當場放棄；Jellyfin 問不到的**不猜**：不送、也不丟，原因記在 `error`，
    下一輪再問（滿 `GIVE_UP_AFTER` 照樣放棄）。
    """
    if notification.user_id not in libraries:
        notification.error = f"jellyfin: {unreachable}"
        return True
    visible = libraries[notification.user_id]
    if visible is None:
        notification.status = NotificationStatus.ABANDONED
        notification.error = "withheld: the recipient's jellyfin account is disabled or gone"
        return True
    if notification.content_json.get("library") not in visible:
        notification.status = NotificationStatus.ABANDONED
        notification.error = "withheld: the recipient cannot see this library in jellyfin"
        return True
    return False


def _not_admin(notification: Notification, user: User) -> bool:
    """管理員專屬的那幾種（`ADMIN_ONLY_KINDS`），收件人在送出那一刻已經不是管理員（角色每次登入照
    Jellyfin 重寫）：放棄、記下原因，回 `True`。它說的頁面他進不去了。"""
    if user.role is Role.ADMIN:
        return False
    notification.status = NotificationStatus.ABANDONED
    notification.error = "withheld: the recipient is no longer an admin"
    return True


def _settled_wave(notification: Notification, user: User, current: dict[str, Waiting]) -> bool:
    """「等你處理」這一則不送了就放棄它、記下原因，回 `True`（M4 票 127）：這一波新增的在送出前
    都已經處理掉（總數是 0 也在這裡：那時候一件都不剩）。這不是「現在還有幾件」的提醒：沒有新的
    一件要說，人多半正在 Berth 上處理。"""
    if not any(key in current for key in notification.content_json.get(_NEW) or ()):
        notification.status = NotificationStatus.ABANDONED
        notification.error = "withheld: everything in this batch was handled before it was sent"
        return True
    return False


async def _deliver(
    bot: NotifyChannel,
    notification: Notification,
    user: User,
    berth_url: str,
    current: dict[str, Waiting],
) -> Delivery | None:
    """組字、送出。出了例外記在那一則上、回 `None`：組不成句子的再組也一樣，當場放棄；管道丟出來的
    （說好不丟）不知道送到了沒，留著下一輪再送，滿 `GIVE_UP_AFTER` 才放棄。"""
    try:
        if notification.kind is NotificationKind.WAITING:
            message = _render_waiting(notification, user.notify_language, berth_url, current)
        elif notification.kind is NotificationKind.WEEKLY:
            message = _render_weekly(notification, user.notify_language, berth_url)
        else:
            message = _render(notification, user.notify_language, berth_url)
    except Exception as exc:
        logger.exception("notification cannot be rendered", extra={"notification": notification.id})
        notification.status = NotificationStatus.ABANDONED
        notification.error = f"render: {type(exc).__name__}: {exc}"
        return None
    try:
        return await bot.send(user.discord_user_id, message)
    except Exception as exc:
        logger.exception("notify channel raised", extra={"notification": notification.id})
        notification.attempts += 1
        notification.error = f"send: {type(exc).__name__}: {exc}"
        return None


def _settle(notification: Notification, user: User, delivery: Delivery, moment: datetime) -> None:
    """這一則與收件人身上記下什麼。管道那一層在 `_note_channel`。"""
    _mark_recipient(user, delivery, moment)
    if delivery.delivered:
        notification.status = NotificationStatus.SENT
        notification.sent_at = moment
        notification.error = ""
        return
    notification.attempts += 1
    notification.error = f"{delivery.failure}: {delivery.detail}"
    if delivery.failure in _FINAL:
        notification.status = NotificationStatus.ABANDONED
    elif delivery.failure is DeliveryFailure.RATE_LIMITED and not delivery.whole_channel:
        notification.retry_at = moment + _wait(delivery)


def _mark_recipient(user: User, delivery: Delivery, moment: datetime) -> None:
    if delivery.delivered:
        _clear_unreachable(user)
    elif delivery.failure is DeliveryFailure.RECIPIENT_UNREACHABLE:
        user.notify_unreachable_at = moment
        user.notify_unreachable_detail = delivery.detail


def _clear_unreachable(user: User) -> None:
    user.notify_unreachable_at = None
    user.notify_unreachable_detail = ""


async def _note_recipient(
    session: AsyncSession, user_id: int, delivery: Delivery, moment: datetime
) -> None:
    user = await session.get(User, user_id)
    if user is not None:
        _mark_recipient(user, delivery, moment)
    await session.commit()


async def _note_channel(
    session: AsyncSession, token: str, delivery: Delivery, moment: datetime
) -> None:
    """管道那一層記下什麼，連同這一則的改動一起 commit。收件人與這一則自己的失敗不動管道。"""
    failure = delivery.failure
    if failure is DeliveryFailure.UNAUTHORIZED:
        await _note_rejected(session, token, delivery, moment)
        return
    whole = failure is DeliveryFailure.RATE_LIMITED and delivery.whole_channel
    if failure is not None and failure is not DeliveryFailure.UNAVAILABLE and not whole:
        await session.commit()
        return

    def change(sender: NotifySenderSettings) -> None:
        if failure is None:
            sender.failures = 0
            sender.resume_at = None
            sender.error = ""
            sender.last_sent_at = moment
            return
        if failure is DeliveryFailure.UNAVAILABLE:
            sender.failures += 1
            sender.resume_at = moment + backoff(sender.failures)
        else:
            sender.resume_at = moment + _wait(delivery)
        sender.error = delivery.detail
        sender.failed_at = moment

    # `update_settings` 先 commit 這一則的改動，再在寫鎖裡改管道那一列。
    await update_settings(session, NotifySenderSettings, change)


async def _note_rejected(
    session: AsyncSession, token: str, delivery: Delivery, moment: datetime
) -> None:
    """記下被拒的是**哪一把**：送的那幾秒裡管理員換了新的，比的是現在存著的那一把，新的不算被拒。"""
    fingerprint = _fingerprint(token)

    def change(sender: NotifySenderSettings) -> None:
        sender.rejected_token = fingerprint
        sender.error = delivery.detail
        sender.failed_at = moment

    await update_settings(session, NotifySenderSettings, change)
    logger.warning("discord bot token rejected", extra={"detail": delivery.detail})


def backoff(failures: int) -> timedelta:
    """連續第 `failures` 輪連不上之後等多久：30 秒起加倍，最多一小時。"""
    # 上限一小時是第 8 輪；再往上的位移只會更大，先夾住免得算出天文數字。
    return min(_BACKOFF_FIRST * (1 << min(max(failures - 1, 0), 16)), _BACKOFF_CAP)


def _wait(delivery: Delivery) -> timedelta:
    seconds = delivery.retry_after if delivery.retry_after is not None else _RATE_LIMIT_FALLBACK
    return timedelta(seconds=seconds)


async def _give_up_stale(session: AsyncSession, moment: datetime) -> None:
    """滿 `GIVE_UP_AFTER` 還沒送到的放棄，留下上一次沒送到的原因（一次都沒送過的說 not sent）。"""
    stale = list(
        await session.scalars(
            select(Notification).where(
                Notification.status == NotificationStatus.PENDING,
                Notification.not_before <= moment - GIVE_UP_AFTER,
            )
        )
    )
    if not stale:
        return
    hours = int(GIVE_UP_AFTER.total_seconds() // 3600)
    for notification in stale:
        notification.status = NotificationStatus.ABANDONED
        notification.error = f"expired after {hours}h; last: {notification.error or 'not sent'}"
    await session.commit()
    logger.warning("stale notifications given up", extra={"count": len(stale)})


def _render(notification: Notification, language: Language, berth_url: str) -> Message:
    """「可以看了」與「正在下載」（M4 票 126，`services.downloading`）：同一個形狀，標題照種類。
    `berth_url` 是 `BerthSettings.public_url`：連結在送出時照當下存的那一個組。"""
    content = notification.content_json
    text = _TEXT[language]
    title = content["title_en"] if language is Language.EN else content["title"]
    route = content.get("route") or ""
    media = content.get("media")
    url = berth_link(berth_url, BerthPage.MEDIA.format(media_id=media)) if media else None
    return Message(
        title=text[notification.kind.value].format(title=title),
        # 「正在下載」存的是逐筆猜到的季集，在這裡才合成連續的範圍。
        description=describe_spans(collapse_spans(content.get("episodes") or [])),
        fields=((_ROUTE, route),) if route else (),
        links=(Link(text["open"], url),) if url else (),
    )


def _render_waiting(
    notification: Notification, language: Language, berth_url: str, current: dict[str, Waiting]
) -> Message:
    """「有 N 件等你處理」（M4 票 127）：標題是現在的總數，內文是這一波新增、還沒處理掉的那幾件
    （種類與數量），每一種現在幾件放在欄位。只剩一件時連到那一件，否則每一種一條清單連結。"""
    if notification.merge_key == _LINGER_KEY:
        return _render_lingering(notification, language, berth_url, current)
    text = _TEXT[language]
    still = [current[key] for key in notification.content_json.get(_NEW) or () if key in current]
    by_source = {source: [one for one in still if one.source is source] for source in WaitingSource}
    parts = [_part(text, language, source, found) for source, found in by_source.items() if found]
    totals = {
        source: sum(1 for one in current.values() if one.source is source)
        for source in WaitingSource
    }
    if len(still) == 1:
        paths = [(text["open"], still[0].path)]
    else:
        paths = [
            (text[f"{source.value}_list"], LIST_PAGE[source])
            for source, found in by_source.items()
            if found
        ]
    links = tuple(Link(label, url) for label, path in paths if (url := berth_link(berth_url, path)))
    return Message(
        title=text["waiting"].format(count=len(current)),
        description=text["waiting_new"].format(
            count=len(still), parts=text["waiting_gap"].join(parts)
        ),
        fields=tuple(
            (text[f"{source.value}_field"], str(count)) for source, count in totals.items() if count
        ),
        links=links,
    )


def _render_lingering(
    notification: Notification, language: Language, berth_url: str, current: dict[str, Waiting]
) -> Message:
    """「有一件等了 3 天」（M4 票 129）：說出是哪一種、連到那一件，每一種現在幾件放在欄位。
    呼叫之前 `_settled_wave` 已經確定它還在。"""
    text = _TEXT[language]
    (key,) = notification.content_json[_NEW]
    one = current[key]
    url = berth_link(berth_url, one.path)
    totals = {
        source: sum(1 for each in current.values() if each.source is source)
        for source in WaitingSource
    }
    return Message(
        title=text["lingering"].format(days=notification.content_json[_DAYS]),
        description=_part(text, language, one.source, [one]),
        fields=tuple(
            (text[f"{source.value}_field"], str(count)) for source, count in totals.items() if count
        ),
        links=(Link(text["open"], url),) if url else (),
    )


def _render_weekly(notification: Notification, language: Language, berth_url: str) -> Message:
    """週報的摘要（M4 票 131，`services.weekly`）：哪一週、三段各幾件，連到週報頁那一週。日期兩種
    語言都寫 `10-19`：月日的數字不必翻。"""
    content = notification.content_json
    text = _TEXT[language]
    first = date.fromisoformat(content["week_of"])
    last = first + timedelta(days=6)
    url = berth_link(berth_url, BerthPage.WEEKLY.format(report_id=content["report"]))
    return Message(
        title=text["weekly"].format(first=f"{first:%m-%d}", last=f"{last:%m-%d}"),
        description=text["weekly_body"].format(
            works=content["works"],
            episodes=content["episodes"],
            fixed=content["fixed"],
            waiting=content["waiting"],
        ),
        links=(Link(text["weekly_open"], url),) if url else (),
    )


def _part(
    text: dict[str, str], language: Language, source: WaitingSource, found: list[Waiting]
) -> str:
    """一種的那一段：「2 件待審核」「1 個 Issue（檔案遺失）」。Issue 的括號裡照型別數，多的在前，
    同一型別兩件以上寫「×2」。"""
    count = len(found)
    template = text[f"{source.value}_{'one' if count == 1 else 'many'}"]
    if source is not WaitingSource.ISSUE:
        return template.format(count=count)
    tally: dict[IssueType, int] = {}
    for one in found:
        if one.issue_type is not None:
            tally[one.issue_type] = tally.get(one.issue_type, 0) + 1
    labels = _ISSUE_LABEL[language]
    types = text["waiting_gap"].join(
        labels[kind] if times == 1 else f"{labels[kind]} ×{times}"
        for kind, times in sorted(tally.items(), key=lambda pair: -pair[1])
    )
    return template.format(count=count, types=types)
