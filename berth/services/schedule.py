"""時間表：這一週 TMDB 上播的動畫，一集一張卡（M5.5 票 09；spec〈範圍〉「時間表」、brief §20.3、
`.scratch/m5.5/schedule-shape.md`）。

**主幹是 TMDB**（票 08 量過，這週有集的日本作品列得出九成以上）：`discover/tv` 列出這一週有一集播出
的動畫，但每一筆沒有集與播出日，所以每一部再讀一次 `tv/{id}` 的上一集與下一集，落在這一週的就放進
它播出那一天。週界前後各放寬一天（深夜檔兩邊常差一天），放哪一天照 TMDB 的 `air_date`。

**快取的是卡片的骨架，不是狀態**：有人打開才抓，結果記在程序內（`TtlCache`）；不為卡片寫
`media` 列。狀態（已入庫、已訂閱）是本地事實、會當場改掉，每次照資料庫算——訂閱完下一次打開就要變。

**全部列，不篩**（使用者 2026-11-04 定，票的 Comments）：discover 約一半是長壽 / 兒童節目與
國產動畫，篩不篩等用過再定。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import NotFoundError, ServiceError
from berth.adapters.tmdb import (
    ANIMATION_GENRE,
    BASE_LANGUAGE,
    DISPLAY_LANGUAGE,
    TmdbClient,
    TmdbDetail,
    TmdbEntry,
)
from berth.adapters.ttl import TtlCache
from berth.domain import MediaKind, PlanAction, Role, ScheduleStatus, TmdbProblem
from berth.models import LedgerEntry, TmdbSettings
from berth.models import media_id as build_media_id
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.discover import image_base, poster_url
from berth.services.inventory import episodes_of
from berth.services.rss import subscribed_media
from berth.services.settings import read_settings
from berth.services.tmdb import credential, tmdb_problem

#: 記多久（spec 說 6–24 小時）。取下限：季初 TMDB 一天裡會補建好幾集，記一整天就一整天看不到。
CACHE_SECONDS = 6 * 60 * 60
#: 記幾週。現在只有「這一週」，跨週那一刻上一週的那一筆還在。
CACHE_WEEKS = 2

#: 原文是日文或中文（票 08：`ja|zh` 對日本作品與只用 `ja` 一樣，另外列得出國產動畫）。
LANGUAGES = ("ja", "zh")
#: 週界前後各放寬幾天（票 08：不放寬的話上一週只有 89.5%）。
WINDOW_SLACK = timedelta(days=1)
#: discover 最多讀幾頁。實測一週 9 頁（164 部）；上限只防 TMDB 回了離譜的頁數。
MAX_PAGES = 20
#: 同時讀幾部的詳情。TMDB 每個 IP 約 20 併發（brief §20.3），速率另有全域的桶。
CONCURRENCY = 8
#: 小海報（`w-12` 的縮圖，2× 也夠）。
THUMB_SIZE = "w154"


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    """快取的那一份：一部作品這一週的一集，還沒有狀態。"""

    media_id: str
    tmdb_id: int
    #: Display Round：`zh-TW` 那一輪的標題與海報；`_en` 是 `en-US` 那一輪（`CONTEXT.md`）。
    title: str
    title_en: str
    poster_url: str
    poster_url_en: str
    air_date: date
    season: int
    episode: int


@dataclass(frozen=True, slots=True)
class ScheduleCard:
    """時間表上的一張卡。

    只有狀態類別：字幕組與 Feed 是管理員的頁面（比照 `services/why_not.py`）。
    """

    media_id: str
    tmdb_id: int
    title: str
    title_en: str
    poster_url: str
    poster_url_en: str
    air_date: date
    season: int
    episode: int
    status: ScheduleStatus


@dataclass(frozen=True, slots=True)
class ScheduleWeek:
    """這一週（週一到週日）。卡片照播出日排，同一天裡已入庫與已訂閱的在前。

    失敗**不是例外而是回傳值**，同探索頁：畫面要說得出是沒填憑證還是 TMDB 連不上。
    """

    start: date
    end: date
    today: date
    cards: tuple[ScheduleCard, ...]
    problem: TmdbProblem | None = None
    #: 失敗時服務回的原文（英文），不翻譯。
    detail: str = ""


_CACHE: TtlCache[tuple[ScheduleSlot, ...]] = TtlCache(ttl=CACHE_SECONDS, size=CACHE_WEEKS)


def local_today() -> date:
    """容器時區的今天（`TZ`）。週一到週日、哪一欄是今天都照它。"""
    return datetime.now().astimezone().date()


def week_of(day: date) -> tuple[date, date]:
    """`day` 所在那一週的週一與週日。"""
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


# 讀 TMDB 記在程序內、不落地，不算改東西。每個登入的人都能看（spec：時間表給每個人）。
@command(
    Effect.READ,
    audience=Role.USER,
    about=(
        "This week's airing anime on TMDB (Japanese or Chinese originals), one card per episode "
        "on the day TMDB says it airs. Each card's media_id is the id other tools take; status "
        "says whether that episode is imported, the work is subscribed, or neither."
    ),
)
async def read_schedule(session: AsyncSession, factory: ServiceClientFactory) -> ScheduleWeek:
    """這一週的時間表。同一週第二次打開不打 TMDB（快取 `CACHE_SECONDS`）。"""
    today = local_today()
    start, end = week_of(today)
    key = start.isoformat()

    # 憑證每次都看：拿掉之後快取裡的這一週也不再給，與探索頁、作品頁說同一句。
    key_in_hand = credential(await read_settings(session, TmdbSettings))
    if not key_in_hand:
        return ScheduleWeek(start, end, today, (), *tmdb_problem(None))

    slots = _CACHE.get(key)
    if slots is None:
        client = factory.tmdb(key_in_hand)
        try:
            slots = await _fetch(client, start, end, await image_base(session, client))
        except ServiceError as exc:
            return ScheduleWeek(start, end, today, (), *tmdb_problem(exc))
        finally:
            await client.aclose()
        _CACHE.put(key, slots)

    return ScheduleWeek(start, end, today, await _cards(session, slots))


async def _fetch(client: TmdbClient, start: date, end: date, base: str) -> tuple[ScheduleSlot, ...]:
    listing = await _airing(client, start - WINDOW_SLACK, end + WINDOW_SLACK)
    details = await _details(client, listing)

    slots: list[ScheduleSlot] = []
    seen: set[tuple[int, int, int]] = set()
    for entry, found in zip(listing, details, strict=True):
        if found is None:
            continue
        for aired in (found.last_episode, found.next_episode):
            if aired is None or aired.air_date is None or not start <= aired.air_date <= end:
                continue
            key = (entry.tmdb_id, aired.season_number, aired.episode_number)
            if key in seen:
                continue
            seen.add(key)
            slots.append(
                ScheduleSlot(
                    media_id=build_media_id(MediaKind.TV, entry.tmdb_id),
                    tmdb_id=entry.tmdb_id,
                    title=found.title or entry.title,
                    title_en=entry.title,
                    poster_url=poster_url(found.poster_path or entry.poster_path, base, THUMB_SIZE),
                    poster_url_en=poster_url(entry.poster_path, base, THUMB_SIZE),
                    air_date=aired.air_date,
                    season=aired.season_number,
                    episode=aired.episode_number,
                )
            )
    return tuple(slots)


async def _airing(client: TmdbClient, aired_from: date, aired_to: date) -> list[TmdbEntry]:
    """discover 的全部頁數，英文那一輪（清單本身，同探索頁）。

    翻頁之間名次會挪，同一部只留第一次。
    """
    entries: list[TmdbEntry] = []
    seen: set[int] = set()
    page, pages = 1, 1
    while page <= min(pages, MAX_PAGES):
        found = await client.discover_tv(
            genre=ANIMATION_GENRE,
            original_languages=LANGUAGES,
            aired_from=aired_from,
            aired_to=aired_to,
            page=page,
            language=BASE_LANGUAGE,
        )
        for entry in found.entries:
            if entry.tmdb_id not in seen:
                seen.add(entry.tmdb_id)
                entries.append(entry)
        pages = found.total_pages
        page += 1
    return entries


async def _details(client: TmdbClient, entries: list[TmdbEntry]) -> list[TmdbDetail | None]:
    """每一部的 `zh-TW` 詳情：上一集、下一集與顯示用標題、海報一次拿到。

    TMDB 說沒有這一部（404）的那一格是 `None`、不列；其他錯誤整份不要（不記半份進快取）。
    """
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(entry: TmdbEntry) -> TmdbDetail | None:
        async with gate:
            try:
                return await client.detail(MediaKind.TV, entry.tmdb_id, language=DISPLAY_LANGUAGE)
            except NotFoundError:
                return None

    # 等每一部都回來才看錯誤：先丟出去的話其他的還在用一個馬上要關掉的 client。
    results = await asyncio.gather(*(one(entry) for entry in entries), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return [result for result in results if not isinstance(result, BaseException)]


async def _cards(
    session: AsyncSession, slots: tuple[ScheduleSlot, ...]
) -> tuple[ScheduleCard, ...]:
    """骨架加上這一刻的狀態，一次問一整週（不是逐張一句查詢）。

    已訂閱是 `CONTEXT.md` 的訂閱（`rss.subscribed_media`，與作品頁的訂閱清單同一個來源）。
    """
    wanted = list({slot.media_id for slot in slots})
    subscribed = await subscribed_media(session, wanted)
    imported: set[tuple[str, int, int]] = set()
    if wanted:
        for row in await session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.media_id.in_(wanted), LedgerEntry.action == PlanAction.IMPORT
            )
        ):
            assert row.media_id is not None  # where 擋掉了 NULL，型別上看不出來
            imported |= {(row.media_id, *pair) for pair in episodes_of(row)}

    def status(slot: ScheduleSlot) -> ScheduleStatus:
        if (slot.media_id, slot.season, slot.episode) in imported:
            return ScheduleStatus.IMPORTED
        if slot.media_id in subscribed:
            return ScheduleStatus.SUBSCRIBED
        return ScheduleStatus.UNSUBSCRIBED

    cards = [
        ScheduleCard(
            media_id=slot.media_id,
            tmdb_id=slot.tmdb_id,
            title=slot.title,
            title_en=slot.title_en,
            poster_url=slot.poster_url,
            poster_url_en=slot.poster_url_en,
            air_date=slot.air_date,
            season=slot.season,
            episode=slot.episode,
            status=status(slot),
        )
        for slot in slots
    ]
    # 一天之內：有事的（已入庫、已訂閱）在前，其餘照 TMDB 的順序（`sorted` 是穩定的）。
    return tuple(
        sorted(cards, key=lambda card: (card.air_date, card.status is ScheduleStatus.UNSUBSCRIBED))
    )
