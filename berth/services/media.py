"""Media 詳情、追蹤與快照刷新（plan §2.2、§5、§8.3、brief §7.5、§13、票 04）。

這一支管的是**一部作品的本地事實**：它的 TMDB 快照、追不追蹤、資料夾名、預設 Route。
探索頁那邊的 `services/discover.py` 管的是「牆上有哪些作品」，兩者的快取規則刻意不同——
牆是一小時就整批丟掉的短期快取，這裡的一列要活得跟檔案系統上的資料夾一樣久。

三條規則值得先讀：

- **英文那一輪是結構本身**，`zh-TW` 只補顯示用標題與簡介（plan §8.3、票 03 的同一個理由）。
  季名、集名都留英文——它們會進檔名（plan §5），而且季名是 §4.4 篇章名比對的來源。
- **快照 24 小時**（plan §8.3）。過期就重抓，使用者不必按任何東西。
- **`folder_name` 在追蹤那一刻凍結**（plan §5、brief §4.5）。還沒追蹤的那一列上它是預覽，
  跟著 TMDB 的標題走；`tracked` 一旦是 true 就再也不動它。
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

#: Media 快照的壽命（plan §8.3）。探索牆另有一小時的規則，不走這裡。
SNAPSHOT_TTL = timedelta(hours=24)


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
    #: 追蹤後凍結；還沒追蹤時是「將會是」的預覽。
    folder_name: str
    tracked: bool
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


async def refresh_media(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str
) -> MediaView:
    """不管幾歲都重抓一次。**不動已經凍結的 `folder_name`**（票 04 驗收）。"""
    return await _load(session, factory, media_id, force=True)


async def track_media(
    session: AsyncSession,
    factory: ServiceClientFactory,
    media_id: str,
    *,
    route_id: int | None,
) -> MediaView:
    """把這部作品交給 Berth 管，並指定它的預設 Route。

    **這一刻凍結 `folder_name`**：它從此是檔案系統上的事實，TMDB 之後改標題也不動它
    （plan §5、brief §4.5）。Route 不在凍結之列——媒體庫會搬，資料夾名不會，
    所以重按這一支只是改 Route。

    追蹤前要先有快照：沒有標題就算不出資料夾名。TMDB 那時拿不到的話這一支就失敗，
    而不是凍結一個猜出來的名字。
    """
    view = await _load(session, factory, media_id, force=False)
    if view.problem is not None and view.fetched_at is None:
        return view

    row = await session.get(Media, view.id)
    if row is None:  # pragma: no cover - `_load` 成功時一定寫得出這一列
        raise ValueError(f"{media_id}: no snapshot to track")
    route = await _route_for(session, row.kind, route_id)

    row.tracked = True
    row.default_route_id = route.id if route is not None else None
    await session.commit()
    return await _view(session, row)


async def _route_for(session: AsyncSession, kind: MediaKind, route_id: int | None) -> Route | None:
    """選的 Route 必須存在、啟用中，而且收得下這種作品。

    型別不符要擋在這裡而不是送單時：劇集進了 movies 媒體庫，命名模板與 Jellyfin 的掃描
    兩邊都會錯（plan §5、brief §4.3）。
    """
    if route_id is None:
        return None
    route = await session.get(Route, route_id)
    if route is None or not route.enabled:
        raise ValueError(f"route {route_id}: no such route")
    wanted = collection_type_for(kind)
    if route.collection_type is not wanted:
        raise ValueError(
            f"route {route_id}: collection type is {route.collection_type.value}, "
            f"and {kind.value} needs {wanted.value}"
        )
    return route


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
    """兩輪詳情 + 每季一次 + Absolute group（有的話），收斂成一份快照。

    英文那一輪決定結構與所有會進檔名的字串；`zh-TW` 那一輪只回答「這一部叫什麼、簡介怎麼寫」。
    季集只取英文那一輪：集名會進檔名（plan §5 的 `{episode_title}`），中文集名放進去
    等於讓磁碟上的檔名跟著 UI 的語言跑。
    """
    base = await client.detail(kind, tmdb_id, language=BASE_LANGUAGE)
    display = await client.detail(kind, tmdb_id, language=DISPLAY_LANGUAGE)

    ordering: dict[tuple[int, int], int] = {}
    if base.absolute_group_id:
        ordering = dict(await client.absolute_ordering(base.absolute_group_id))

    seasons = []
    for entry in base.seasons:
        season = await client.season(tmdb_id, entry.season_number, language=BASE_LANGUAGE)
        seasons.append(
            SeasonSnapshot(
                season_number=entry.season_number,
                # 季名取詳情那一份：`tv/{id}/season/{n}` 也回一個，但清單那一份才是
                # 使用者在 TMDB 網站上看到的那個（篇章名就掛在那裡）。
                name=entry.name,
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


def _titles(base: TmdbDetail, display: TmdbDetail) -> tuple[str, ...]:
    """比對用的標題集合。顯示用那一輪的標題也算——`間諜家家酒` 也會出現在檔名裡。"""
    return unique_titles([*base.titles, display.title, *display.titles])


async def _poster(session: AsyncSession, client: TmdbClient, path: str) -> str:
    """沒有海報路徑或沒有圖片基底時是空字串——半條網址只會變成一個破圖。"""
    if not path:
        return ""
    base = await image_base(session, client)
    return f"{base}{POSTER_SIZE}{path}" if base else ""


def _fresh(row: Media) -> bool:
    return (
        row.tmdb_snapshot_json is not None
        and row.tmdb_fetched_at is not None
        and datetime.now(UTC) - row.tmdb_fetched_at < SNAPSHOT_TTL
    )


async def _store(session: AsyncSession, row: Media | None, snapshot: MediaSnapshot) -> Media:
    """寫下快照。

    `folder_name` 只在**還沒追蹤**時跟著標題走：那時候它是畫面上的預覽。追蹤之後它是
    檔案系統上的事實，TMDB 改標題也不動它（plan §5、brief §4.5）。
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
        if not row.tracked:
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
    snapshot = MediaSnapshot.model_validate(row.tmdb_snapshot_json or {})
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
        tracked=row.tracked,
        default_route_id=row.default_route_id,
        seasons=snapshot.seasons,
        fetched_at=row.tmdb_fetched_at,
        routes=await _routes(session, row.kind),
        problem=problem,
        detail=detail,
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
