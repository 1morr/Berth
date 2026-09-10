"""探索與搜尋（plan §6 discover 群組、§8.3、brief §13、票 03、04b）。

三個 feed 都是同一條路：**英文那一輪是清單本身**（順序、成員、檔名用的標題都以它為準），
`zh-TW` 那一輪只是一張「這一部的顯示用標題與海報」的查表。方向不能反過來——`language`
會換掉 TMDB 回的**成員與順序**而不只是文字（2026-09-09 實測 `trending/tv/week`，20 筆
差 3 筆），照 `zh-TW` 那一輪當清單會讓作品憑空消失。

快取一小時（plan §8.3）。快取存的就是卡片本身——**卡片上還沒有任何本地狀態**（票 04b）：
「已追蹤 / 部分 / 完整 / 下載中」要等 Job 與帳本才推導得出來（票 09 起）。那些狀態回來時
不能塞進這份快取，它們是本地事實、會當場改掉，不該等一小時。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import zip_longest
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.tmdb import (
    BASE_LANGUAGE,
    DISPLAY_LANGUAGE,
    TmdbClient,
    TmdbEntry,
)
from berth.domain import MediaKind, TmdbProblem
from berth.models import MediaCard, TmdbCache, TmdbSettings, dump_cards, load_cards
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings, write_settings
from berth.services.steps import message
from berth.services.tmdb import MISSING_CREDENTIAL, credential
from berth.services.tracking import tracked_media

#: 探索與搜尋的快取壽命（plan §8.3）。Media 快照另有 24 小時的規則，不走這裡。
CACHE_TTL = timedelta(hours=1)

#: 卡片牆用的海報尺寸，取自 `configuration` 的 `poster_sizes`。整頁是一面卡牆，
#: 拿 `original` 會讓首頁下載好幾十 MB。
POSTER_SIZE = "w342"

TRENDING_KEY = "discover:trending"
POPULAR_KEY = "discover:popular"


@dataclass(frozen=True, slots=True)
class DiscoverItem:
    """牆上的一格：一張 `MediaCard` 加上「我追了沒」。

    欄位與 `MediaCard` 一致（`from_card()` 直接展開它），不是各寫一份——`api` 不可以 import
    `models`（plan §1.3），所以命令回的東西必須是 services 自己的型別。
    """

    id: str
    tmdb_id: int
    kind: MediaKind
    title: str
    title_en: str
    year: int | None
    poster_url: str
    #: Berth 已經為這部作品做過事（`CONTEXT.md` 的 Tracked Media）。**不進 `tmdb_cache`**：
    #: 它是本地事實而且會當場改掉，而那份快取一小時才換一次（plan §8.3）。
    tracked: bool = False

    @classmethod
    def from_card(cls, card: MediaCard, *, tracked: bool = False) -> DiscoverItem:
        return cls(id=card.id, tracked=tracked, **card.model_dump())


@dataclass(frozen=True, slots=True)
class DiscoverResult:
    """一個 feed 的結果。

    失敗**不是例外而是回傳值**：探索頁一次要畫三個 feed，其中一個垮掉時另外兩個照樣
    畫得出來，而畫面要說得出「下一步是什麼」而不是留一片空白（票 03 驗收）。
    """

    items: tuple[DiscoverItem, ...]
    problem: TmdbProblem | None = None
    #: 失敗時服務回的原文（英文）。與精靈的纜繩同一個規矩：原文不翻譯。
    detail: str = ""


class _KindFeed(Protocol):
    """`trending` 與 `popular` 的共同簽章：同一種合併方式，兩支端點。"""

    async def __call__(self, kind: MediaKind, *, language: str) -> tuple[TmdbEntry, ...]: ...


async def read_trending(session: AsyncSession, factory: ServiceClientFactory) -> DiscoverResult:
    """本週趨勢，劇集與電影交錯。"""

    async def fetch(client: TmdbClient, base: str) -> tuple[MediaCard, ...]:
        return await _both_kinds(client.trending, base)

    return await _feed(session, factory, TRENDING_KEY, fetch)


async def read_popular(session: AsyncSession, factory: ServiceClientFactory) -> DiscoverResult:
    """熱門，同樣兩種作品交錯。"""

    async def fetch(client: TmdbClient, base: str) -> tuple[MediaCard, ...]:
        return await _both_kinds(client.popular, base)

    return await _feed(session, factory, POPULAR_KEY, fetch)


async def search_media(
    session: AsyncSession, factory: ServiceClientFactory, query: str
) -> DiscoverResult:
    """`search/multi`：一次查兩種作品，順序照 TMDB 的相關性。"""
    normalised = normalise_query(query)
    if not normalised:
        # 空的查詢不必問 TMDB 才知道沒有結果。
        return DiscoverResult(())

    async def fetch(client: TmdbClient, base: str) -> tuple[MediaCard, ...]:
        listing = await client.search(normalised, language=BASE_LANGUAGE)
        display = _by_key(await client.search(normalised, language=DISPLAY_LANGUAGE))
        return tuple(_card(entry, display, base) for entry in listing)

    return await _feed(session, factory, search_key(normalised), fetch)


def normalise_query(query: str) -> str:
    """`  SPY  X  Family ` 與 `spy x family` 是同一個查詢，不該各佔一格快取。"""
    return " ".join(query.split()).lower()


def search_key(normalised: str) -> str:
    return f"search:{normalised}"


class _Fetch(Protocol):
    async def __call__(self, client: TmdbClient, base: str) -> tuple[MediaCard, ...]: ...


async def _feed(
    session: AsyncSession, factory: ServiceClientFactory, key: str, fetch: _Fetch
) -> DiscoverResult:
    cached = await _read_cache(session, key)
    if cached is not None:
        return await _wall(session, cached)

    settings = await read_settings(session, TmdbSettings)
    key_in_hand = credential(settings)
    if not key_in_hand:
        # 憑證是精靈第 6 步的必填閘門（票 02b），所以「沒有 key」有一句自己的話。
        return DiscoverResult((), TmdbProblem.CREDENTIAL_MISSING, MISSING_CREDENTIAL)

    client = factory.tmdb(key_in_hand)
    try:
        cards = await fetch(client, await image_base(session, client))
    except AuthFailedError as exc:
        return DiscoverResult((), TmdbProblem.CREDENTIAL_REJECTED, message(exc))
    except ServiceError as exc:
        return DiscoverResult((), TmdbProblem.UNREACHABLE, message(exc))
    finally:
        await client.aclose()

    await _write_cache(session, key, cards)
    return await _wall(session, cards)


async def _both_kinds(feed: _KindFeed, base: str) -> tuple[MediaCard, ...]:
    """兩種作品各取一份，交錯成一面牆。

    交錯而不是重排：TMDB 給的順序就是那個 feed 的排名，而 `popularity` 欄位**不是**它
    （2026-09-09 實測，回應裡的 `popularity` 是亂序的），拿來排只會得到一份第三種順序。
    """
    listing = {kind: await feed(kind, language=BASE_LANGUAGE) for kind in MediaKind}
    display: dict[tuple[MediaKind, int], TmdbEntry] = {}
    for kind in MediaKind:
        display |= _by_key(await feed(kind, language=DISPLAY_LANGUAGE))
    return _interleave(
        *(tuple(_card(entry, display, base) for entry in listing[kind]) for kind in MediaKind)
    )


def _by_key(entries: Iterable[TmdbEntry]) -> dict[tuple[MediaKind, int], TmdbEntry]:
    """顯示用那一輪的查表。鍵要帶 `kind`——同一個 TMDB id 在劇集與電影各是一部作品。"""
    return {(entry.kind, entry.tmdb_id): entry for entry in entries}


def _card(
    entry: TmdbEntry, display: dict[tuple[MediaKind, int], TmdbEntry], base: str
) -> MediaCard:
    """一筆英文結果 + 顯示用那一輪的同一部作品（可能沒有）→ 一張卡。

    標題與海報**同時**取自顯示用那一輪：TMDB 的海報也是分語言的，中文標題配英文海報是
    兩個來源拼出來的東西。年份與英文標題永遠來自英文那一輪。
    """
    shown = display.get((entry.kind, entry.tmdb_id), entry)
    return MediaCard(
        tmdb_id=entry.tmdb_id,
        kind=entry.kind,
        title=shown.title or entry.title,
        title_en=entry.title,
        year=entry.year,
        poster_url=_poster(shown.poster_path or entry.poster_path, base),
    )


def _poster(path: str, base: str) -> str:
    """沒有海報路徑或沒有圖片基底時是空字串——半條網址只會變成一個破圖。"""
    return f"{base}{POSTER_SIZE}{path}" if path and base else ""


def _interleave(*lists: tuple[MediaCard, ...]) -> tuple[MediaCard, ...]:
    return tuple(card for row in zip_longest(*lists) for card in row if card is not None)


async def image_base(session: AsyncSession, client: TmdbClient) -> str:
    """圖片基底對同一把憑證是常數，所以存起來，只在還沒有的時候問。

    精靈第 6 步驗憑證時就會寫下它；這裡的 fallback 是給**在這個欄位存在之前就跑完精靈**
    的資料庫用的——那些人不會再跑一次精靈。

    探索牆與 Media 詳情（票 04）共用這一支：兩邊組的是同一種海報網址，
    而「還沒有就問一次並寫回去」那半條規則各寫一份的話會問兩次。
    """
    settings = await read_settings(session, TmdbSettings)
    if settings.image_base_url:
        return settings.image_base_url
    settings.image_base_url = (await client.configuration()).image_base_url
    await write_settings(session, settings)
    return settings.image_base_url


async def _read_cache(session: AsyncSession, key: str) -> tuple[MediaCard, ...] | None:
    row = await session.get(TmdbCache, key)
    if row is None or datetime.now(UTC) - row.fetched_at >= CACHE_TTL:
        return None
    return load_cards(row.value_json)


async def _write_cache(session: AsyncSession, key: str, cards: tuple[MediaCard, ...]) -> None:
    await session.merge(
        TmdbCache(key=key, value_json=dump_cards(cards), fetched_at=datetime.now(UTC))
    )


async def _wall(session: AsyncSession, cards: tuple[MediaCard, ...]) -> DiscoverResult:
    """卡片變成牆上的那幾格，順手問一次「哪幾部 Berth 已經做過事」。

    **一次問一整面牆**（`services/tracking`），不是逐格一句 `EXISTS`——一面牆 40 格。
    「部分 / 完整 / 下載中」還沒有：那要等帳本（票 12）才推導得出來，而現在每一格都會是
    同一個字（brief §13）。
    """
    tracked = await tracked_media(session, [card.id for card in cards])
    return DiscoverResult(
        tuple(DiscoverItem.from_card(card, tracked=card.id in tracked) for card in cards)
    )
