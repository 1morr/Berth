"""時間表：這一週 TMDB 上播的動畫，一集一張卡（M5.5 票 09；spec〈範圍〉「時間表」、brief §20.3、
`.scratch/m5.5/schedule-shape.md`）。

**主幹是 TMDB**（票 08 量過，這週有集的日本作品列得出九成以上）：`discover/tv` 列出這一週有一集播出
的動畫，但每一筆沒有集與播出日，所以每一部再讀一次 `tv/{id}` 的上一集與下一集，落在這一週的就放進
它播出那一天。週界前後各放寬一天（深夜檔兩邊常差一天），放哪一天照 TMDB 的 `air_date`。

**快取的是卡片的骨架，不是狀態**：有人打開才抓，結果記在程序內（`TtlCache`）；不為卡片寫
`media` 列。狀態（已入庫、已訂閱）是本地事實、會當場改掉，每次照資料庫算——訂閱完下一次打開就要變。

**全部列，不篩**（使用者 2026-11-04 定，票的 Comments）：discover 約一半是長壽 / 兒童節目與
國產動畫，篩不篩等用過再定。

**第二層：時刻與評分**（票 14）。AniList `AiringSchedule` 給未來的放送時刻，Bangumi `/calendar` 給
評分；兩邊都沒有 TMDB id，Berth 也沒有對照表（brief §20.3），所以**原文名壓平後完全相同**才算
同一部；時刻另外要那一筆的日本日期與 TMDB 的播出日差一天以內。對不上、同名不只一部就不顯示，不猜。
兩個來源與 TMDB 同時抓，各自失敗或太慢就只少那一格，卡片照常（快取在各自的 adapter 裡）。
"""

from __future__ import annotations

import asyncio
import logging
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.anilist import Airing
from berth.adapters.bgm import CalendarItem
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
from berth.services.keeping_up import late_by_work
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

#: 第二層（時刻、評分）最多等幾秒。AniList 被限流時會停下來等一分鐘（`anilist.client`），
#: 時間表不陪它等；一週三頁、兩秒一頁，冷快取約六秒。
SECOND_LAYER_TIMEOUT = 10.0
#: Bangumi 條目的開播日與 TMDB 那一季的開播日差幾天以內算同一季（評分）。2026-11-04 那一週原文名
#: 對到的 48 部全在一天以內（深夜檔差一天），放寬到 60 天也沒有多對到（票 14 Comments）。
SEASON_START_SLACK = timedelta(days=1)
#: 第二層的來源失敗或逾時之後幾秒內不再問它。
LEFT_OUT_SECONDS = 5 * 60
#: TMDB 的播出日是日本的日期：AniList 的時刻換成日本時間再比。
AIRING_ZONE = ZoneInfo("Asia/Tokyo")
#: 放送與 TMDB 播出日差幾天以內算同一集（深夜檔的「25:00」兩邊常差一天）。
AIRING_SLACK = timedelta(days=1)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    """快取的那一份：一部作品這一週的一集，還沒有狀態。"""

    media_id: str
    tmdb_id: int
    #: Display Round：`zh-TW` 那一輪的標題與海報；`_en` 是 `en-US` 那一輪（`CONTEXT.md`）。
    title: str
    title_en: str
    #: TMDB 的 `original_name`：第二層照它對 AniList 與 Bangumi。
    original_title: str
    #: 卡片那一季的開播日（`tv/{id}` 的 `seasons[]`）：評分照它認 Bangumi 的哪一季。
    #: TMDB 沒寫是 `None`。
    season_air_date: date | None
    poster_url: str
    poster_url_en: str
    air_date: date
    season: int
    episode: int


@dataclass(frozen=True, slots=True)
class SecondLayer:
    """這一週 AniList 的放送與 Bangumi 的放送表；來源失敗的那一份是空的。"""

    airings: tuple[Airing, ...] = ()
    ratings: tuple[CalendarItem, ...] = ()


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
    #: 狀態是 `late` 時，那一集從播出日到今天（容器時區）的天數；否則 `None`（M5.5 票 12）。
    late_days: int | None
    #: AniList 的放送時刻（UTC），只給還沒播的；對不上是 `None`。
    airs_at: datetime | None
    #: Bangumi 的評分（1–10）與打分人數；對不上或沒人打分是 `None`。
    score: float | None
    votes: int | None


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
#: 第二層這一陣子問不到的來源（`"AniList"`、`"Bangumi"`）。
_LEFT_OUT: TtlCache[bool] = TtlCache(ttl=LEFT_OUT_SECONDS, size=2)


def local_today() -> date:
    """容器時區的今天（`TZ`）。週一到週日、哪一欄是今天都照它。"""
    return datetime.now().astimezone().date()


def utc_now() -> datetime:
    """「未來的放送」照它（測試換掉它）。"""
    return datetime.now(UTC)


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
        "says whether that episode is imported, the work is subscribed, or neither. airs_at "
        "(AniList, future episodes only) and score (Bangumi, 1-10 with votes) are present only "
        "when the original title matches exactly."
    ),
)
async def read_schedule(session: AsyncSession, factory: ServiceClientFactory) -> ScheduleWeek:
    """這一週的時間表。同一週第二次打開不打 TMDB（快取 `CACHE_SECONDS`）。"""
    today = local_today()
    start, end = week_of(today)

    # 憑證每次都看：拿掉之後快取裡的這一週也不再給，與探索頁、作品頁說同一句。
    key_in_hand = credential(await read_settings(session, TmdbSettings))
    if not key_in_hand:
        return ScheduleWeek(start, end, today, (), *tmdb_problem(None))

    # 第二層與 TMDB 同時抓：冷快取時兩邊都要好幾秒。它自己吞掉錯誤，TMDB 失敗時收掉。
    second = asyncio.create_task(_second_layer(factory, start, end))
    try:
        slots = await _slots(session, factory, key_in_hand, start, end)
        layer = await second
    except ServiceError as exc:
        return ScheduleWeek(start, end, today, (), *tmdb_problem(exc))
    finally:
        second.cancel()

    # 「晚了沒」與卡片的天數照同一支時鐘（`local_today`）：牆上這一刻換成時間表的今天。
    moment = datetime.combine(today, datetime.now().astimezone().timetz())
    return ScheduleWeek(start, end, today, await _cards(session, slots, layer, utc_now(), moment))


async def _slots(
    session: AsyncSession,
    factory: ServiceClientFactory,
    credential_value: str,
    start: date,
    end: date,
) -> tuple[ScheduleSlot, ...]:
    cache_key = start.isoformat()
    slots = _CACHE.get(cache_key)
    if slots is None:
        client = factory.tmdb(credential_value)
        try:
            slots = await _fetch(client, start, end, await image_base(session, client))
        finally:
            await client.aclose()
        _CACHE.put(cache_key, slots)
    return slots


async def _second_layer(factory: ServiceClientFactory, start: date, end: date) -> SecondLayer:
    """這一週（日本時間，前後各寬一天）的放送與 Bangumi 放送表。時段整週固定，快取才接得住。"""
    since = datetime.combine(start - WINDOW_SLACK, time(), AIRING_ZONE)
    until = datetime.combine(end + WINDOW_SLACK + timedelta(days=1), time(), AIRING_ZONE)
    airings, ratings = await asyncio.gather(
        _quietly("AniList", lambda: factory.anilist().airing(since, until)),
        _quietly("Bangumi", factory.bgm().calendar),
    )
    return SecondLayer(tuple(airings), tuple(ratings))


async def _quietly[T](source: str, ask: Callable[[], Awaitable[list[T]]]) -> list[T]:
    """失敗或太慢就是空的：卡片照常，只少這一格（票 14）。

    失敗的來源記 `LEFT_OUT_SECONDS`，這段時間不再問：否則它掛著時每一次打開都要等到逾時。
    """
    if _LEFT_OUT.get(source):
        return []
    try:
        return await asyncio.wait_for(ask(), SECOND_LAYER_TIMEOUT)
    except (ServiceError, TimeoutError) as exc:
        logger.warning("schedule: %s left out: %s", source, str(exc) or type(exc).__name__)
        _LEFT_OUT.put(source, True)
        return []


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
                    original_title=entry.original_title,
                    season_air_date=next(
                        (
                            s.air_date
                            for s in found.seasons
                            if s.season_number == aired.season_number
                        ),
                        None,
                    ),
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
    session: AsyncSession,
    slots: tuple[ScheduleSlot, ...],
    layer: SecondLayer,
    now: datetime,
    moment: datetime,
) -> tuple[ScheduleCard, ...]:
    """骨架加上這一刻的狀態，一次問一整週（不是逐張一句查詢）。

    已訂閱是 `CONTEXT.md` 的訂閱（`rss.subscribed_media`，與作品頁的訂閱清單同一個來源）；晚了是
    追更頁的同一套判定（`keeping_up.late_by_work`，只問訂閱著的那幾部）。
    """
    wanted = list({slot.media_id for slot in slots})
    subscribed = await subscribed_media(session, wanted)
    late = await late_by_work(session, subscribed, now=moment)
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
        if (slot.season, slot.episode) in late.get(slot.media_id, {}):
            return ScheduleStatus.LATE
        if slot.media_id in subscribed:
            return ScheduleStatus.SUBSCRIBED
        return ScheduleStatus.UNSUBSCRIBED

    airings = _by_match_key(layer.airings, lambda airing: airing.native_title)
    ratings = _by_match_key(layer.ratings, lambda item: item.name)

    def card(slot: ScheduleSlot) -> ScheduleCard:
        key = match_key(slot.original_title)
        found = _rating(slot, ratings.get(key, []))
        return ScheduleCard(
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
            late_days=_late_days(late, slot, moment.date()),
            airs_at=_airs_at(slot, airings.get(key, []), now),
            score=found.score if found else None,
            votes=found.votes if found else None,
        )

    cards = [card(slot) for slot in slots]
    # 一天之內：有事的（已入庫、已訂閱）在前，其餘照 TMDB 的順序（`sorted` 是穩定的）。
    return tuple(
        sorted(cards, key=lambda card: (card.air_date, card.status is ScheduleStatus.UNSUBSCRIBED))
    )


def _late_days(
    late: dict[str, dict[tuple[int, int], date]], slot: ScheduleSlot, today: date
) -> int | None:
    """卡片那一集晚了幾天：從遲到判定看到的播出日（作品的快照）算到今天，與追更頁同一個數。"""
    aired = late.get(slot.media_id, {}).get((slot.season, slot.episode))
    return None if aired is None else (today - aired).days


def match_key(title: str) -> str:
    """比對用的原文名：NFKC、不分大小寫、只留字母與數字（全形、空白、標點不算差別）。"""
    text = unicodedata.normalize("NFKC", title).casefold()
    return "".join(ch for ch in text if ch.isalnum())


def _by_match_key[T](items: tuple[T, ...], title: Callable[[T], str]) -> dict[str, list[T]]:
    grouped: dict[str, list[T]] = {}
    for item in items:
        if key := match_key(title(item)):
            grouped.setdefault(key, []).append(item)
    return grouped


def _rating(slot: ScheduleSlot, same_title: list[CalendarItem]) -> CalendarItem | None:
    """原文名相同的只有一部、開播日對得上卡片那一季、有分數也有人數才給。

    季別：TMDB 多季併成一部、原文名是系列名，Bangumi 一季一條、第一季常用系列名；不比開播日的話，
    第二季的卡會掛上第一季的分數。任一邊沒有日期就不給。少了 `total` 不寫「0 人打分」。
    """
    if len({item.id for item in same_title}) != 1:
        return None
    item = same_title[0]
    if not _same_season(slot.season_air_date, item.air_date):
        return None
    return item if item.score is not None and item.votes > 0 else None


def _same_season(tmdb_start: date | None, bgm_start: str) -> bool:
    try:
        started = date.fromisoformat(bgm_start)
    except ValueError:
        return False
    return tmdb_start is not None and abs(started - tmdb_start) <= SEASON_START_SLACK


def _airs_at(slot: ScheduleSlot, same_title: list[Airing], now: datetime) -> datetime | None:
    """原文名相同、日本日期與 TMDB 差一天以內的那一筆；不只一部、或兩筆一樣近就不給。

    只給未來的：AniList 只保證未來的放送準確（brief §20.3）。一律換成 UTC，API 送出的形狀才一致。
    """

    def distance(airing: Airing) -> int:
        return abs((airing.airs_at.astimezone(AIRING_ZONE).date() - slot.air_date).days)

    near = sorted((a for a in same_title if distance(a) <= AIRING_SLACK.days), key=distance)
    if not near or len({a.media_id for a in near}) != 1:
        return None
    if len(near) > 1 and distance(near[0]) == distance(near[1]):
        return None
    return near[0].airs_at.astimezone(UTC) if near[0].airs_at > now else None
