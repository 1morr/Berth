"""通知：寫進待送表、送出一輪、通知設定（plan §11.5〈通知〉、M4 票 123）。

**寫入與觸發它的狀態變更同一筆交易**（`queue_ready` 不 commit），送出由獨立的迴圈做
（`pipeline/notifying.py`）：管道壞了不阻塞任何管線，觸發的那一筆 rollback 時也沒有通知。

**這是後端第一個自己組人話的地方**：其餘的句子都在前端（i18n key），可是 Discord 的收件人不在瀏覽器
上。所以待送表存事實（作品、季集、Route），送出那一刻照收件人自己的語言（`users.notify_language`，
存 Discord ID 那一刻的介面語言）組字。兩種語言的句子都在 `_TEXT`，與前端一樣 zh-Hant 與 en 並列。

這一張只送管理員；照媒體庫權限送給每個人、同一部作品 5 分鐘內合成一則是票 125。

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
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.notify import Delivery, Link, Message, NotifyChannel
from berth.adapters.notify.discord import invite_url
from berth.domain import (
    DeliveryFailure,
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
    Job,
    LedgerEntry,
    Media,
    Notification,
    NotifySenderSettings,
    NotifySettings,
    Route,
    User,
)
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.deeplink import (
    MEDIA_PAGE,
    PublicUrlRejectedError,
    berth_link,
    normalized_public_url,
)
from berth.services.settings import read_settings, update_settings

logger = logging.getLogger(__name__)

#: Discord 的 user ID 是 snowflake：64 位元整數的十進位，現在是 17–20 位。
_SNOWFLAKE = re.compile(r"\d{17,20}")

_TEXT: dict[Language, dict[str, str]] = {
    Language.ZH_HANT: {
        "ready": "可以看了：{title}",
        "open": "在 Berth 打開",
        "test_title": "Berth 測試訊息",
        "test_body": "收到這一則，Berth 的通知就接通了。",
    },
    Language.EN: {
        "ready": "Ready to watch: {title}",
        "open": "Open in Berth",
        "test_title": "Berth test message",
        "test_body": "If you can read this, Berth notifications are working.",
    },
}

#: 這幾種是管道本身送不出去，不是這一位收件人的事：這一輪不再送下一則。
_CHANNEL_DOWN = frozenset(
    {DeliveryFailure.UNAUTHORIZED, DeliveryFailure.RATE_LIMITED, DeliveryFailure.UNAVAILABLE}
)

#: 再送也一樣的：那一則當場放棄。
_FINAL = frozenset({DeliveryFailure.RECIPIENT_UNREACHABLE, DeliveryFailure.REJECTED})

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
class NotifyView:
    """通知設定頁讀的那一份。**沒有 token**：只說設定了沒。"""

    bot_configured: bool
    bot_name: str
    invite_url: str | None
    #: Discord 不再接受存著的那一把 token（M4 票 128）：通知暫停到換一把。
    token_rejected: bool
    discord_user_id: str
    language: Language
    #: Berth 從外面看的網址（`BerthSettings`）；沒存過是空字串，通知不附連結。
    berth_url: str
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
async def read_notify(session: AsyncSession, user_id: int) -> NotifyView:
    settings = await read_settings(session, NotifySettings)
    sender = await read_settings(session, NotifySenderSettings)
    user = await session.get(User, user_id)
    configured = bool(settings.discord_bot_token)
    return NotifyView(
        bot_configured=configured,
        bot_name=settings.discord_bot_name if configured else "",
        invite_url=(
            invite_url(settings.discord_application_id)
            if configured and settings.discord_application_id
            else None
        ),
        token_rejected=_rejected(settings, sender),
        discord_user_id=user.discord_user_id if user else "",
        language=user.notify_language if user else Language.ZH_HANT,
        berth_url=(await read_settings(session, BerthSettings)).public_url,
        unreachable_at=user.notify_unreachable_at if user else None,
        unreachable_detail=user.notify_unreachable_detail if user else "",
    )


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


# 同一個命令就是自己的反向：換回原本的 token，或傳空字串清掉。
@command(Effect.REVERSIBLE)
async def set_bot_token(
    session: AsyncSession, factory: ServiceClientFactory, token: str, *, user_id: int
) -> NotifyView:
    """存 bot token。**先問 Discord 它是哪一個 bot**，問得到才存（順手記下 application id 與名字，
    邀請連結照它組）；空字串是清掉。網路在寫交易之前（plan §3.3）。"""
    token = token.strip()
    if not token:
        await update_settings(session, NotifySettings, _clear_bot)
        logger.info("discord bot token cleared")
        return await read_notify(session, user_id)
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
    return await read_notify(session, user_id)


def _clear_bot(settings: NotifySettings) -> None:
    settings.discord_bot_token = ""
    settings.discord_application_id = ""
    settings.discord_bot_name = ""


# 同上：再存一次原本的 ID，或空字串清掉。
@command(Effect.REVERSIBLE)
async def set_discord_id(
    session: AsyncSession, user_id: int, discord_id: str, language: Language
) -> NotifyView:
    """存這個人的 Discord user ID 與通知語言（存的那一刻的介面語言）。空字串是不收。"""
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
    await session.commit()
    return await read_notify(session, user_id)


# 同上：再存一次原本的網址，或空字串清掉。
@command(Effect.REVERSIBLE)
async def set_berth_url(session: AsyncSession, value: str, *, user_id: int) -> NotifyView:
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
    return await read_notify(session, user_id)


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

    給每一位有 Discord ID 的管理員各排一則，回排了幾則。**不 commit**：與寫事件的那一筆交易同生死。

    **寫不成也不讓那一筆交易失敗**（M4 票 128）：讀不出內容時記 log、不排，回 0。這裡的查詢不
    autoflush：呼叫端還沒 flush 的改動要是有錯，在它自己 commit 時爆，不在這裡被吞掉。
    """
    try:
        with session.no_autoflush:
            admins = list(
                await session.scalars(
                    select(User)
                    .where(User.role == Role.ADMIN, User.discord_user_id != "")
                    .order_by(User.id)
                )
            )
            if not admins:
                return 0
            content = await _ready_content(session, job)
    except Exception:
        # job id 由上下文蓋上去（`berth.logs`）；`extra={"job": …}` 會撞到它。
        with job_context(job.hash):
            logger.exception("ready notification not queued")
        return 0
    for admin in admins:
        session.add(
            Notification(
                user_id=admin.id,
                kind=NotificationKind.READY,
                content_json=content,
                merge_key=job.media_id or job.hash,
                not_before=now,
                created_at=now,
            )
        )
    return len(admins)


async def _ready_content(session: AsyncSession, job: Job) -> dict[str, Any]:
    """事實，不是句子：作品的兩種標題、季集範圍、Route 名。組字在送出時（`_render`）。"""
    media = await session.get(Media, job.media_id) if job.media_id else None
    route = await session.get(Route, job.route_id) if job.route_id else None
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
        "route": route.name if route else "",
        "episodes": [] if movie else [list(span) for span in episode_spans(features)],
    }


def episode_spans(entries: Iterable[LedgerEntry]) -> list[tuple[int, int, int]]:
    """帳本的季集收成連續的範圍：E01、E02、E03 是一段，E05 另一段。沒有季集的（電影）不算。"""
    points = sorted(
        (entry.season, entry.episode_start, entry.episode_end or entry.episode_start)
        for entry in entries
        if entry.season is not None and entry.episode_start is not None
    )
    spans: list[tuple[int, int, int]] = []
    for season, start, end in points:
        if spans and spans[-1][0] == season and start <= spans[-1][2] + 1:
            spans[-1] = (season, spans[-1][1], max(spans[-1][2], end))
        else:
            spans.append((season, start, end))
    return spans


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
    await session.commit()
    if not rows:
        return SendOutcome(sent=0, failed=0)
    bot = factory.discord(token)
    sent = failed = 0
    for notification, user in rows:
        delivery = await _deliver(bot, notification, user, berth_url)
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


async def _deliver(
    bot: NotifyChannel, notification: Notification, user: User, berth_url: str
) -> Delivery | None:
    """組字、送出。出了例外記在那一則上、回 `None`：組不成句子的再組也一樣，當場放棄；管道丟出來的
    （說好不丟）不知道送到了沒，留著下一輪再送，滿 `GIVE_UP_AFTER` 才放棄。"""
    try:
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
    """`berth_url` 是 `BerthSettings.public_url`：連結在送出時照當下存的那一個組。"""
    content = notification.content_json
    text = _TEXT[language]
    title = content["title_en"] if language is Language.EN else content["title"]
    route = content.get("route") or ""
    media = content.get("media")
    url = berth_link(berth_url, MEDIA_PAGE.format(media_id=media)) if media else None
    return Message(
        title=text["ready"].format(title=title),
        description=describe_spans(content.get("episodes") or []),
        fields=((_ROUTE, route),) if route else (),
        link=Link(text["open"], url) if url else None,
    )
