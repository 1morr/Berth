"""通知：寫進待送表、送出一輪、通知設定（plan §11.5〈通知〉、M4 票 123）。

**寫入與觸發它的狀態變更同一筆交易**（`queue_ready` 不 commit），送出由獨立的迴圈做
（`pipeline/notifying.py`）：管道壞了不阻塞任何管線，觸發的那一筆 rollback 時也沒有通知。

**這是後端第一個自己組人話的地方**：其餘的句子都在前端（i18n key），可是 Discord 的收件人不在瀏覽器
上。所以待送表存事實（作品、季集、Route），送出那一刻照收件人自己的語言（`users.notify_language`，
存 Discord ID 那一刻的介面語言）組字。兩種語言的句子都在 `_TEXT`，與前端一樣 zh-Hant 與 en 並列。

這一張只送管理員；照媒體庫權限送給每個人、同一部作品 5 分鐘內合成一則是票 125，退避與放棄是
票 128。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.notify import Delivery, Link, Message
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
from berth.models import (
    BerthSettings,
    Job,
    LedgerEntry,
    Media,
    Notification,
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
    discord_user_id: str
    language: Language
    #: Berth 從外面看的網址（`BerthSettings`）；沒存過是空字串，通知不附連結。
    berth_url: str


@dataclass(frozen=True, slots=True)
class SendOutcome:
    sent: int
    failed: int


# --- 設定 -----------------------------------------------------------------


@command(Effect.READ)
async def read_notify(session: AsyncSession, user_id: int) -> NotifyView:
    settings = await read_settings(session, NotifySettings)
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
        discord_user_id=user.discord_user_id if user else "",
        language=user.notify_language if user else Language.ZH_HANT,
        berth_url=(await read_settings(session, BerthSettings)).public_url,
    )


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
    return delivery


# --- 寫入 -----------------------------------------------------------------


# 寫下的那幾則一旦送出就收不回來（送出迴圈不等人）。
@command(Effect.IRREVERSIBLE)
async def queue_ready(session: AsyncSession, job: Job, *, now: datetime) -> int:
    """「可以看了」：這一筆的正片在 Jellyfin 全部認出來了（`jellyfin_item_resolved`）。

    給每一位有 Discord ID 的管理員各排一則，回排了幾則。**不 commit**：與寫事件的那一筆交易同生死。
    """
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
    """送一輪：到時間、還沒送的每一則各送一次。沒送到的留著，下一輪再送（退避與放棄在票 128）。

    **網路不在寫交易裡**（plan §3.3）：先讀完收掉讀的交易，逐則送、逐則 commit 結果——一則幾毫秒的
    寫，不讓一輪的 Discord 往返握著寫鎖。
    """
    moment = now or utcnow()
    settings = await read_settings(session, NotifySettings)
    if not settings.discord_bot_token:
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
    bot = factory.discord(settings.discord_bot_token)
    sent = failed = 0
    for notification, user in rows:
        message = _render(notification, user.notify_language, berth_url)
        delivery = await bot.send(user.discord_user_id, message)
        if delivery.delivered:
            notification.status = NotificationStatus.SENT
            notification.sent_at = moment
            sent += 1
        else:
            notification.attempts += 1
            notification.error = f"{delivery.failure}: {delivery.detail}"
            failed += 1
            logger.warning(
                "notification not delivered",
                extra={
                    "notification": notification.id,
                    "failure": delivery.failure,
                    "detail": delivery.detail,
                },
            )
        await session.commit()
        if delivery.failure in _CHANNEL_DOWN:
            # 管道這一刻送不出任何一則：接著送只會把每一則的 `attempts` 灌高，限速時還多扣額度
            # （失敗的請求也算，brief §20.23）。剩下的留給下一輪。
            break
    return SendOutcome(sent=sent, failed=failed)


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
