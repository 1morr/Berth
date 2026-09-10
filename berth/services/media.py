"""Media 詳情與快照刷新（plan §2.2、§5、§8.3、brief §7.5、§13、票 04、04b）。

這一支管的是**一部作品的本地事實**：它的 TMDB 快照、資料夾名、可以入庫到哪幾條 Route。
探索頁那邊的 `services/discover.py` 管的是「牆上有哪些作品」，兩者的快取規則刻意不同——
牆是一小時就整批丟掉的短期快取，這裡的一列要活得跟檔案系統上的資料夾一樣久。

三條規則值得先讀：

- **英文那一輪是結構本身**，`zh-TW` 只補顯示用標題與簡介（plan §8.3、票 03 的同一個理由）。
  季名、集名都留英文——它們會進檔名（plan §5），而且季名是 §4.4 篇章名比對的來源。
- **快照 24 小時**（plan §8.3）。過期就重抓，使用者不必按任何東西。
- **`folder_name` 跟著標題走**（plan §5、brief §4.5）。它在畫面上是「將會是」的預覽，
  凍結發生在第一次真的通向磁碟那一刻——手動送單成功時（`services/jobs`，票 09）。
  這一支沒有凍結的權力，只有**遵守**它的義務：`folder_frozen` 之後刷新不再動那串字。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, NotFoundError, ServiceError
from berth.adapters.tmdb import (
    BASE_LANGUAGE,
    DISPLAY_LANGUAGE,
    SIMPLIFIED_LANGUAGE,
    TmdbClient,
    TmdbDetail,
    unique_titles,
)
from berth.domain import (
    CollectionType,
    EpisodeSnapshot,
    MediaKind,
    MediaSnapshot,
    SeasonSnapshot,
    TmdbProblem,
    collection_type_for,
)
from berth.models import Media, Route, TmdbSettings, parse_media_id
from berth.models import media_id as build_media_id
from berth.naming import folder_name
from berth.services.clients import ServiceClientFactory
from berth.services.discover import POSTER_SIZE, image_base
from berth.services.settings import read_settings
from berth.services.steps import message
from berth.services.tmdb import MISSING_CREDENTIAL, credential
from berth.services.tracking import is_tracked

#: Media 快照的壽命（plan §8.3）。探索牆另有一小時的規則，不走這裡。
SNAPSHOT_TTL = timedelta(hours=24)

#: planning 之前收緊成 6 小時（plan §8.3、票 11）。**不是「每次都重抓」**：一部正在播的
#: 作品每週多一集，而一份六小時前的季集表算得出同一份 Plan；每次都抓只會讓每一筆完成的
#: 下載都排隊等 TMDB。也**不是** 24 小時——新播的那一集正是使用者現在在下載的那一集。
PLANNING_TTL = timedelta(hours=6)


@dataclass(frozen=True, slots=True)
class RouteChoice:
    """詳情頁下拉裡的一條 Route。只列 `collection_type` 與這部作品相符的（票 04 驗收）。"""

    id: int
    name: str
    slug: str
    collection_type: CollectionType


@dataclass(frozen=True, slots=True)
class MediaView:
    """詳情頁的一整份。

    失敗**不是例外而是回傳值**，與探索頁同一個道理：快照過期而 TMDB 連不上時，
    存下來的季集加一句「這是舊的」，比一片空白有用得多（shape brief §5）。
    """

    id: str
    tmdb_id: int
    kind: MediaKind
    title: str
    title_en: str
    title_original: str
    year: int | None
    #: 首播 / 上映日。識別欄位那一行的標籤說的就是它，所以年份之外整個日期也要送出去。
    first_air_date: date | None
    overview: str
    poster_url: str
    #: 電影片長（分鐘）。劇集是 `None`。
    runtime: int | None
    #: 畫面上的「將會是」。凍結在第一次送單成功那一刻（票 09），在那之前跟著標題走。
    folder_name: str
    #: 那串字已經定死了。畫面照它換掉整句說明——「將會是」與「就是」是兩件事。
    folder_frozen: bool
    #: Berth 已經為這部作品做過事（`CONTEXT.md` 的 Tracked Media，票 09 起是 `EXISTS(jobs)`）。
    tracked: bool
    #: 上次送單用的 Route，下拉的預選值（plan §2.2）。還沒送過單時是 `None`。
    default_route_id: int | None
    seasons: tuple[SeasonSnapshot, ...]
    #: 這份快照什麼時候抓的。畫面用它說「這是 N 前的快照」。
    fetched_at: datetime | None
    routes: tuple[RouteChoice, ...]
    problem: TmdbProblem | None = None
    #: 失敗時服務回的原文（英文），與精靈的纜繩同一個規矩。
    detail: str = ""


async def read_media(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str
) -> MediaView:
    """詳情頁要的一整份。快照過期（或還沒有）時順手重抓一次。"""
    return await _load(session, factory, media_id, force=False)


async def read_snapshot(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str
) -> MediaSnapshot | None:
    """搜尋要的是快照**本身**——標題集合與季集，不是詳情頁那一份視圖（票 08）。

    先走一次 `read_media` 是為了同一條 24 小時規則：搜尋常常是使用者在詳情頁待了一會兒
    之後才按的，那時快照可能剛好過期，而用過期的標題去搜等於搜錯名字。拿不到 TMDB 時
    存下來的那一份仍然回得出來——舊的標題仍然是真的標題。
    """
    await read_media(session, factory, media_id)
    parsed = parse_media_id(media_id)
    if parsed is None:
        return None
    row = await session.get(Media, build_media_id(*parsed))
    if row is None or row.tmdb_snapshot_json is None:
        return None
    return MediaSnapshot.model_validate(row.tmdb_snapshot_json)


async def snapshot_for_planning(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str
) -> MediaSnapshot | None:
    """planning 要的那一份：超過 6 小時就先刷新（plan §8.3、票 11）。

    **失敗不擋**（與送單前那一步同一個規矩，票 09）：TMDB 連不上時存下來的季集仍然是真的
    季集，而 Plan 少一個訊號也還是算得出來。`_load` 本來就把服務錯誤變成回傳值而不是例外，
    所以這裡不必接——它回來之後那一列上有什麼，這一支就回什麼。
    """
    parsed = parse_media_id(media_id)
    if parsed is None:
        return None
    row = await session.get(Media, build_media_id(*parsed))
    if row is None or not _fresh(row, PLANNING_TTL):
        await _load(session, factory, media_id, force=True)
        row = await session.get(Media, build_media_id(*parsed))
    if row is None or row.tmdb_snapshot_json is None:
        return None
    return MediaSnapshot.model_validate(row.tmdb_snapshot_json)


async def refresh_media(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str
) -> MediaView:
    """不管幾歲都重抓一次。TMDB 改了標題，`folder_name` 就跟著改（票 04b 驗收）。"""
    return await _load(session, factory, media_id, force=True)


async def _load(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str, *, force: bool
) -> MediaView:
    parsed = parse_media_id(media_id)
    if parsed is None:
        # `/media/nonsense` 是網址打錯。它與「TMDB 上沒有這部作品」的下一步一樣。
        return _missing(media_id)
    kind, tmdb_id = parsed
    row = await session.get(Media, build_media_id(kind, tmdb_id))

    if row is not None and not force and _fresh(row):
        return await _view(session, row)

    settings = await read_settings(session, TmdbSettings)
    key_in_hand = credential(settings)
    if not key_in_hand:
        return await _problem(
            session, row, TmdbProblem.CREDENTIAL_MISSING, MISSING_CREDENTIAL, kind, tmdb_id
        )

    client = factory.tmdb(key_in_hand)
    try:
        snapshot = await _fetch(session, client, kind, tmdb_id)
    except NotFoundError as exc:
        return await _problem(session, row, TmdbProblem.NOT_FOUND, message(exc), kind, tmdb_id)
    except AuthFailedError as exc:
        return await _problem(
            session, row, TmdbProblem.CREDENTIAL_REJECTED, message(exc), kind, tmdb_id
        )
    except ServiceError as exc:
        return await _problem(session, row, TmdbProblem.UNREACHABLE, message(exc), kind, tmdb_id)
    finally:
        await client.aclose()

    return await _view(session, await _store(session, row, snapshot))


async def _fetch(
    session: AsyncSession, client: TmdbClient, kind: MediaKind, tmdb_id: int
) -> MediaSnapshot:
    """三輪詳情 + 每季一次 + Absolute group（有的話），收斂成一份快照。

    英文那一輪決定結構與所有會進檔名的字串；`zh-TW` 那一輪只回答「這一部叫什麼、簡介怎麼寫」。
    季集只取英文那一輪：集名會進檔名（plan §5 的 `{episode_title}`），中文集名放進去
    等於讓磁碟上的檔名跟著 UI 的語言跑。

    第三輪（`zh-CN`）只為了**季名**（plan §4.4）：真實發佈裡的篇章名是「柱训练篇」，
    TMDB 的 `zh-TW` 給「柱訓練篇」、`en-US` 給「Hashira Training Arc」——三套字，
    少一套就有一整類發佈比對不到。劇集才多這一次請求，電影沒有季。
    """
    base = await client.detail(kind, tmdb_id, language=BASE_LANGUAGE)
    display = await client.detail(kind, tmdb_id, language=DISPLAY_LANGUAGE)
    # 第三輪只為了季名，所以只有劇集打得到它。
    localised = [display]
    if kind is MediaKind.TV:
        localised.append(await client.detail(kind, tmdb_id, language=SIMPLIFIED_LANGUAGE))

    ordering: dict[tuple[int, int], int] = {}
    if base.absolute_group_id:
        ordering = dict(await client.absolute_ordering(base.absolute_group_id))

    season_names = _season_names(*localised)
    seasons = []
    for entry in base.seasons:
        season = await client.season(tmdb_id, entry.season_number, language=BASE_LANGUAGE)
        seasons.append(
            SeasonSnapshot(
                season_number=entry.season_number,
                # 季名取詳情那一份：`tv/{id}/season/{n}` 也回一個，但清單那一份才是
                # 使用者在 TMDB 網站上看到的那個（篇章名就掛在那裡）。
                name=entry.name,
                names=unique_titles([entry.name, *season_names.get(entry.season_number, ())]),
                episode_count=entry.episode_count,
                air_date=entry.air_date,
                episodes=tuple(
                    EpisodeSnapshot(
                        episode_number=row.episode_number,
                        name=row.name,
                        air_date=row.air_date,
                        runtime=row.runtime,
                        absolute_number=ordering.get((row.season_number, row.episode_number)),
                    )
                    for row in season.episodes
                ),
            )
        )

    return MediaSnapshot(
        tmdb_id=tmdb_id,
        kind=kind,
        title=display.title or base.title,
        title_en=base.title,
        title_original=base.original_title,
        year=base.year,
        overview=display.overview or base.overview,
        poster_url=await _poster(session, client, display.poster_path or base.poster_path),
        first_air_date=base.first_air_date,
        runtime=base.runtime,
        titles=_titles(base, display),
        seasons=tuple(seasons),
    )


def _season_names(*rounds: TmdbDetail) -> dict[int, tuple[str, ...]]:
    """各季在其他語言下的名字：`{季號: (名字, …)}`（plan §4.4 的篇章名比對）。

    比對是逐字比的，所以這裡收的是**原樣**的季名。`第 1 季` 這種只是季號的翻譯也收——
    它比對不到任何東西，但也不會錯，而挑掉它需要一張「哪些字算季號」的表。
    """
    names: dict[int, list[str]] = {}
    for detail in rounds:
        for entry in detail.seasons:
            names.setdefault(entry.season_number, []).append(entry.name)
    return {number: tuple(values) for number, values in names.items()}


def _titles(base: TmdbDetail, display: TmdbDetail) -> tuple[str, ...]:
    """比對用的標題集合。顯示用那一輪的標題也算——`間諜家家酒` 也會出現在檔名裡。"""
    return unique_titles([*base.titles, display.title, *display.titles])


async def _poster(session: AsyncSession, client: TmdbClient, path: str) -> str:
    """沒有海報路徑或沒有圖片基底時是空字串——半條網址只會變成一個破圖。"""
    if not path:
        return ""
    base = await image_base(session, client)
    return f"{base}{POSTER_SIZE}{path}" if base else ""


def _fresh(row: Media, ttl: timedelta = SNAPSHOT_TTL) -> bool:
    """這份快照還夠新嗎。`ttl` 是參數而不是常數：同一列在兩個問題下有兩個答案——
    畫面上 24 小時的舊季集只是舊，planning 拿它算出來的卻是磁碟上的檔名（plan §8.3）。"""
    return (
        row.tmdb_snapshot_json is not None
        and row.tmdb_fetched_at is not None
        and datetime.now(UTC) - row.tmdb_fetched_at < ttl
    )


async def _store(session: AsyncSession, row: Media | None, snapshot: MediaSnapshot) -> Media:
    """寫下快照。

    `folder_name` 跟著標題走：這一列上還沒有任何檔案依賴它，而畫面要說的是「**現在**送單
    的話會是這串字」。**送單成功之後就不動了**（`folder_frozen`，票 09）——那一刻起磁碟上
    真的有一個那樣的資料夾，而 TMDB 改標題不該讓 Berth 的檔案跟著改名（brief §4.5）。
    """
    if row is None:
        row = Media(
            id=build_media_id(snapshot.kind, snapshot.tmdb_id),
            tmdb_id=snapshot.tmdb_id,
            kind=snapshot.kind,
            title_en=snapshot.title_en,
            title_original=snapshot.title_original,
            year=snapshot.year,
            folder_name=folder_name(snapshot),
        )
        session.add(row)
    else:
        row.title_en = snapshot.title_en
        row.title_original = snapshot.title_original
        row.year = snapshot.year
        if not row.folder_frozen:
            row.folder_name = folder_name(snapshot)
    row.tmdb_snapshot_json = snapshot.model_dump(mode="json")
    row.tmdb_fetched_at = datetime.now(UTC)
    await session.commit()
    return row


async def _problem(
    session: AsyncSession,
    row: Media | None,
    problem: TmdbProblem,
    detail: str,
    kind: MediaKind,
    tmdb_id: int,
) -> MediaView:
    """拿不到 TMDB 時還剩下什麼。

    有存過的快照就照樣畫，只是掛一條理由——過期的季集仍然是**真的**季集。
    一列都沒有時只剩下 id 與那句話。
    """
    if row is not None:
        return await _view(session, row, problem=problem, detail=detail)
    return MediaView(
        id=build_media_id(kind, tmdb_id),
        tmdb_id=tmdb_id,
        kind=kind,
        title="",
        title_en="",
        title_original="",
        year=None,
        first_air_date=None,
        overview="",
        poster_url="",
        runtime=None,
        folder_name="",
        folder_frozen=False,
        tracked=False,
        default_route_id=None,
        seasons=(),
        fetched_at=None,
        routes=await _routes(session, kind),
        problem=problem,
        detail=detail,
    )


def _missing(media_id: str) -> MediaView:
    """`media.id` 認不得的樣子。認不得就沒有 kind，所以連 Route 都列不出來。"""
    return MediaView(
        id=media_id,
        tmdb_id=0,
        kind=MediaKind.TV,
        title="",
        title_en="",
        title_original="",
        year=None,
        first_air_date=None,
        overview="",
        poster_url="",
        runtime=None,
        folder_name="",
        folder_frozen=False,
        tracked=False,
        default_route_id=None,
        seasons=(),
        fetched_at=None,
        routes=(),
        problem=TmdbProblem.NOT_FOUND,
        detail=f"{media_id}: not a media id",
    )


async def _view(
    session: AsyncSession,
    row: Media,
    *,
    problem: TmdbProblem | None = None,
    detail: str = "",
) -> MediaView:
    # 快照可能不在：TMDB 從第一次開啟這一頁起就連不上時，這一列上只有 `_store` 之外的
    # 途徑寫下的那幾欄。那時仍然畫得出識別欄位與資料夾名，季集是空的。
    snapshot = (
        MediaSnapshot.model_validate(row.tmdb_snapshot_json)
        if row.tmdb_snapshot_json
        else _bare(row)
    )
    return MediaView(
        id=row.id,
        tmdb_id=row.tmdb_id,
        kind=row.kind,
        title=snapshot.title,
        title_en=row.title_en,
        title_original=row.title_original,
        year=row.year,
        first_air_date=snapshot.first_air_date,
        overview=snapshot.overview,
        poster_url=snapshot.poster_url,
        runtime=snapshot.runtime,
        folder_name=row.folder_name,
        folder_frozen=row.folder_frozen,
        tracked=await is_tracked(session, row.id),
        default_route_id=row.default_route_id,
        seasons=snapshot.seasons,
        fetched_at=row.tmdb_fetched_at,
        routes=await _routes(session, row.kind),
        problem=problem,
        detail=detail,
    )


def _bare(row: Media) -> MediaSnapshot:
    """沒有快照時，這一列自己知道的那幾格。"""
    return MediaSnapshot(
        tmdb_id=row.tmdb_id,
        kind=row.kind,
        title=row.title_en,
        title_en=row.title_en,
        title_original=row.title_original,
        year=row.year,
    )


async def _routes(session: AsyncSession, kind: MediaKind) -> tuple[RouteChoice, ...]:
    rows = await session.scalars(
        select(Route)
        .where(
            Route.collection_type == collection_type_for(kind),
            Route.enabled.is_(True),
        )
        .order_by(Route.id)
    )
    return tuple(
        RouteChoice(id=row.id, name=row.name, slug=row.slug, collection_type=row.collection_type)
        for row in rows
    )
