"""時間表的命令（M5.5 票 09；spec〈範圍〉「時間表」、brief §20.3、
`.scratch/m5.5/schedule-shape.md`）。

驗四件事：**放進哪一天、第幾集**（TMDB 每部的上一集與下一集，discover 本身沒有）、
**快取**（同一週再打開不打 TMDB）、**狀態每次照資料庫算**（訂閱完下一次就變，不等快取過期），
以及拿不到 TMDB 時說得出下一步。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.anilist import Airing
from berth.adapters.anilist.fake import FakeAniList
from berth.adapters.bgm import CalendarItem
from berth.adapters.bgm.fake import FakeBgm
from berth.adapters.http import (
    NotFoundError,
    ProtocolMismatchError,
    ServiceError,
    ServiceUnavailableError,
)
from berth.adapters.tmdb import TmdbDetail, TmdbEntry, TmdbEpisode, TmdbSeasonEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.ttl import TtlCache
from berth.domain import (
    EpisodeSnapshot,
    FeedItemStatus,
    FeedKind,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    ScheduleStatus,
    SeasonSnapshot,
    TmdbProblem,
)
from berth.models import (
    LedgerEntry,
    Media,
    RssFeed,
    RssItem,
    RssSeries,
    RssSettings,
    TmdbSettings,
)
from berth.services import schedule
from berth.services.schedule import read_schedule
from berth.services.settings import read_settings, write_settings
from tests.conftest import TMDB_API_KEY
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio

JST = ZoneInfo("Asia/Tokyo")

#: 這一週是 2026-11-02（一）到 11-08（日），今天是週三。
TODAY = date(2026, 11, 4)
#: 「現在」：週三中午（日本時間）。比它晚的放送才是未來的。
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=JST)


def show(tmdb_id: int, title: str) -> TmdbEntry:
    return TmdbEntry(
        tmdb_id=tmdb_id,
        kind=MediaKind.TV,
        title=title,
        original_title=title,
        year=2026,
        poster_path=f"/{tmdb_id}.jpg",
        animation=True,
    )


def episode(season: int, number: int, aired: date) -> TmdbEpisode:
    return TmdbEpisode(
        season_number=season, episode_number=number, name="", air_date=aired, runtime=None
    )


#: 測試作品每一季的開播日（評分的季別守衛拿它對 Bangumi 的開播日）。
SEASON_START = date(2026, 10, 4)


def detail(
    entry: TmdbEntry, last: TmdbEpisode | None, upcoming: TmdbEpisode | None = None
) -> TmdbDetail:
    numbers = sorted({e.season_number for e in (last, upcoming) if e is not None})
    return TmdbDetail(
        tmdb_id=entry.tmdb_id,
        kind=MediaKind.TV,
        title=entry.title,
        original_title=entry.original_title,
        year=entry.year,
        first_air_date=None,
        overview="",
        poster_path=entry.poster_path,
        last_episode=last,
        next_episode=upcoming,
        seasons=tuple(
            TmdbSeasonEntry(season_number=n, name="", episode_count=12, air_date=SEASON_START)
            for n in numbers
        ),
    )


#: 週二播了第 5 集。
APOTHECARY = show(220542, "The Apothecary Diaries")
#: 上週日播了第 4 集，這週六播第 5 集：放在下一集那一天。
FRIEREN = show(209867, "Frieren")
#: 上一集是上週、下一集是下週：discover 放寬了一天才列得出它（深夜檔），這週沒有它的集。
EDGE = show(300001, "Edge of the Week")
#: TMDB 說沒有這一部（discover 列了、詳情 404）。
GONE = show(300002, "Gone")

DETAILS = (
    detail(APOTHECARY, episode(2, 5, date(2026, 11, 3)), episode(2, 6, date(2026, 11, 10))),
    detail(FRIEREN, episode(2, 4, date(2026, 11, 1)), episode(2, 5, date(2026, 11, 7))),
    detail(EDGE, episode(1, 9, date(2026, 11, 1)), episode(1, 10, date(2026, 11, 9))),
)


def tmdb(**overrides: object) -> FakeTmdbClient:
    defaults: dict[str, object] = {
        "airing": [APOTHECARY, FRIEREN, EDGE, GONE],
        "details": DETAILS,
        "translations": {220542: "藥師少女的獨語"},
        "page_size": 2,
    }
    # 每個測試只覆寫它在乎的那一格；FakeTmdbClient 的參數各有型別
    # （`test_discover.tmdb` 同一個寫法）。
    return FakeTmdbClient(**{**defaults, **overrides})  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def this_week(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """今天固定在 11/04，快取每個測試一份（它是程序內的，測試之間不能共用）。"""
    monkeypatch.setattr(schedule, "local_today", lambda: TODAY)
    monkeypatch.setattr(schedule, "utc_now", lambda: NOW)
    monkeypatch.setattr(
        schedule, "_CACHE", TtlCache(ttl=schedule.CACHE_SECONDS, size=schedule.CACHE_WEEKS)
    )
    monkeypatch.setattr(schedule, "_LEFT_OUT", TtlCache(ttl=schedule.LEFT_OUT_SECONDS, size=2))
    yield


async def credentialled(
    session: AsyncSession,
    client: FakeTmdbClient,
    *,
    anilist: FakeAniList | None = None,
    bgm: FakeBgm | None = None,
) -> FakeClientFactory:
    await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
    await session.commit()
    return FakeClientFactory(tmdb=client, anilist=anilist, bgm=bgm)


async def add_media(session: AsyncSession, entry: TmdbEntry) -> str:
    media_id = f"tv:{entry.tmdb_id}"
    session.add(
        Media(
            id=media_id,
            tmdb_id=entry.tmdb_id,
            kind=MediaKind.TV,
            title_en=entry.title,
            title_original=entry.title,
            folder_name=entry.title,
        )
    )
    await session.flush()
    return media_id


async def subscribe(session: AsyncSession, media_id: str, key: str = "mikan:1:2") -> RssFeed:
    """一條 Feed 帶著一筆 Item，Item 長出一個綁到這部作品的 RSS Series
    （Mikan 單一 feed 的形狀）。"""
    feed = RssFeed(name=key, url=f"https://mikanani.me/RSS/{key}", kind=FeedKind.MIKAN)
    series = RssSeries(key=key, title_raw="[ANi] x", media_id=media_id)
    session.add_all([feed, series])
    await session.flush()
    session.add(
        RssItem(
            feed_id=feed.id,
            guid=key,
            title="[ANi] x - 01",
            series_id=series.id,
            status=FeedItemStatus.PASSED,
        )
    )
    await session.flush()
    return feed


class TestTheWeek:
    async def test_each_episode_sits_on_the_day_tmdb_says_it_airs(
        self, session: AsyncSession
    ) -> None:
        """上一集或下一集落在這一週的，放在那一天；兩集都不在這一週的不列（spec、brief §20.3）。"""
        client = tmdb()
        week = await read_schedule(session, await credentialled(session, client))

        assert (week.start, week.end, week.today) == (date(2026, 11, 2), date(2026, 11, 8), TODAY)
        assert [
            (card.media_id, card.air_date, card.season, card.episode) for card in week.cards
        ] == [
            ("tv:220542", date(2026, 11, 3), 2, 5),
            ("tv:209867", date(2026, 11, 7), 2, 5),
        ]
        assert week.problem is None

    async def test_it_asks_for_animation_in_japanese_or_chinese_a_day_wider_on_each_side(
        self, session: AsyncSession
    ) -> None:
        """深夜檔兩邊常差一天（票 08）：週一前一天到週日後一天，全部頁數。"""
        client = tmdb()
        await read_schedule(session, await credentialled(session, client))

        assert client.discover_queries == [
            (date(2026, 11, 1), date(2026, 11, 9), ("ja", "zh")),
            (date(2026, 11, 1), date(2026, 11, 9), ("ja", "zh")),
        ]
        assert [path for path, _ in client.requests if path.startswith("discover")] == [
            "discover/tv/1",
            "discover/tv/2",
        ]

    async def test_both_display_rounds_travel(self, session: AsyncSession) -> None:
        """英文那一輪是 discover 的清單，`zh-TW` 那一輪是每部的詳情（Display Round）。"""
        client = tmdb(poster_translations={220542: "/zh.jpg"})
        week = await read_schedule(session, await credentialled(session, client))

        apothecary = week.cards[0]
        assert (apothecary.title, apothecary.title_en) == (
            "藥師少女的獨語",
            "The Apothecary Diaries",
        )
        assert apothecary.poster_url.endswith("/zh.jpg")
        assert apothecary.poster_url_en.endswith("/220542.jpg")

    async def test_a_week_with_nothing_on_tmdb_is_empty_not_a_problem(
        self, session: AsyncSession
    ) -> None:
        week = await read_schedule(session, await credentialled(session, tmdb(airing=[])))

        assert week.cards == ()
        assert week.problem is None


class TestTheCache:
    async def test_opening_it_again_does_not_ask_tmdb(self, session: AsyncSession) -> None:
        """同一個快取期間內再打開不再打外部來源（票 09 驗收）。"""
        client = tmdb()
        factory = await credentialled(session, client)
        first = await read_schedule(session, factory)
        asked = len(client.requests)

        again = await read_schedule(session, factory)

        assert len(client.requests) == asked
        assert again.cards == first.cards

    async def test_subscribing_shows_on_the_next_opening_without_refetching(
        self, session: AsyncSession
    ) -> None:
        """狀態不進快取：綁上一條 RSS Series，下一次打開那張卡就是已訂閱。"""
        client = tmdb()
        factory = await credentialled(session, client)
        before = await read_schedule(session, factory)
        assert {card.status for card in before.cards} == {ScheduleStatus.UNSUBSCRIBED}

        await subscribe(session, await add_media(session, APOTHECARY))
        await session.commit()
        asked = len(client.requests)

        after = await read_schedule(session, factory)

        assert len(client.requests) == asked
        assert [card.status for card in after.cards] == [
            ScheduleStatus.SUBSCRIBED,
            ScheduleStatus.UNSUBSCRIBED,
        ]

    async def test_a_failed_round_is_not_kept(self, session: AsyncSession) -> None:
        """TMDB 連不上時說得出下一步，而且不記下那一次：下一次打開再問。"""
        client = tmdb(error=ServiceUnavailableError("TMDB is down"))
        factory = await credentialled(session, client)

        week = await read_schedule(session, factory)
        assert (week.cards, week.problem) == ((), TmdbProblem.UNREACHABLE)
        assert week.detail == "TMDB is down"

        client.error = None
        again = await read_schedule(session, factory)
        assert len(again.cards) == 2


class TestStatus:
    async def test_an_imported_episode_outranks_the_subscription(
        self, session: AsyncSession
    ) -> None:
        """帳本蓋到卡片上那一集才是已入庫；同一部作品的別集入庫不算（卡片說的是這一集）。"""
        client = tmdb()
        factory = await credentialled(session, client)
        apothecary = await add_media(session, APOTHECARY)
        frieren = await add_media(session, FRIEREN)
        await subscribe(session, apothecary)
        session.add_all(
            [
                ledger(apothecary, season=2, start=4, end=5, path="a"),
                ledger(frieren, season=2, start=4, end=4, path="b"),
            ]
        )
        await session.commit()

        week = await read_schedule(session, factory)

        assert [(card.media_id, card.status) for card in week.cards] == [
            ("tv:220542", ScheduleStatus.IMPORTED),
            ("tv:209867", ScheduleStatus.UNSUBSCRIBED),
        ]

    async def test_a_series_waiting_to_be_bound_subscribes_nothing(
        self, session: AsyncSession
    ) -> None:
        """待綁定的 RSS Series（`media_id` 是 NULL）不屬於任何作品。"""
        client = tmdb()
        factory = await credentialled(session, client)
        session.add(RssSeries(key="title:x:y", title_raw="x"))
        await session.commit()

        week = await read_schedule(session, factory)

        assert {card.status for card in week.cards} == {ScheduleStatus.UNSUBSCRIBED}

    async def test_subscribed_and_imported_cards_lead_their_day(
        self, session: AsyncSession
    ) -> None:
        """一天之內已入庫與已訂閱的在前，其餘照 TMDB 的順序（shape〈排序〉）。"""
        second = show(300003, "Second on Tuesday")
        client = tmdb(
            airing=[APOTHECARY, second],
            details=(
                DETAILS[0],
                detail(second, episode(1, 2, date(2026, 11, 3))),
            ),
        )
        factory = await credentialled(session, client)
        await subscribe(session, await add_media(session, second), "mikan:3:4")
        await session.commit()

        week = await read_schedule(session, factory)

        assert [card.media_id for card in week.cards] == ["tv:300003", "tv:220542"]

    async def test_a_keyword_feed_bound_to_the_work_is_a_subscription(
        self, session: AsyncSession
    ) -> None:
        """訂閱是 `CONTEXT.md` 那一個：預先綁定作品的關鍵字 Feed 還沒長出 RSS Series 也算
        （acg.rip 的「只追之後的」就是這樣）。"""
        client = tmdb()
        factory = await credentialled(session, client)
        media_id = await add_media(session, APOTHECARY)
        session.add(
            RssFeed(
                name="acg.rip",
                url="https://acg.rip/.xml?term=x",
                kind=FeedKind.ACGRIP,
                media_id=media_id,
            )
        )
        await session.commit()

        week = await read_schedule(session, factory)

        assert week.cards[0].status is ScheduleStatus.SUBSCRIBED

    async def test_deleting_the_feed_unsubscribes_even_though_the_series_stays(
        self, session: AsyncSession
    ) -> None:
        """刪掉一條訂閱就是刪那條 Feed（`CONTEXT.md`）；RSS Series 與它的綁定留著
        （`rss.delete_feed`），但卡片要說未訂閱，與作品頁的訂閱清單一致。"""
        client = tmdb()
        factory = await credentialled(session, client)
        feed = await subscribe(session, await add_media(session, APOTHECARY))
        await session.commit()
        await session.delete(feed)
        await session.commit()

        week = await read_schedule(session, factory)

        assert week.cards[0].status is ScheduleStatus.UNSUBSCRIBED

    async def test_without_a_credential_a_cached_week_is_not_served(
        self, session: AsyncSession
    ) -> None:
        """憑證拿掉了：快取裡還有這一週也照實說沒有憑證，與探索頁、作品頁同一句。"""
        client = tmdb()
        factory = await credentialled(session, client)
        await read_schedule(session, factory)
        await write_settings(session, TmdbSettings())
        await session.commit()

        week = await read_schedule(session, factory)

        assert (week.cards, week.problem) == ((), TmdbProblem.CREDENTIAL_MISSING)


class TestNoTmdb:
    async def test_without_a_credential_it_says_so(self, session: AsyncSession) -> None:
        client = tmdb()
        week = await read_schedule(session, FakeClientFactory(tmdb=client))

        assert (week.cards, week.problem) == ((), TmdbProblem.CREDENTIAL_MISSING)
        assert client.requests == []

    async def test_a_show_tmdb_no_longer_has_is_left_out(self, session: AsyncSession) -> None:
        """discover 列了、詳情 404：那一部不列，其餘照畫（不是整頁的錯）。"""
        client = tmdb()
        client.detail_errors[(MediaKind.TV, APOTHECARY.tmdb_id)] = NotFoundError("gone")
        week = await read_schedule(session, await credentialled(session, client))

        assert [card.media_id for card in week.cards] == ["tv:209867"]
        assert week.problem is None


def ledger(media_id: str, *, season: int, start: int, end: int, path: str) -> LedgerEntry:
    return LedgerEntry(
        source_rel_path=f"{path}.mkv",
        source_abs_path=f"/data/complete/{path}.mkv",
        source_dev="1",
        target_path=f"/data/media/{path}.mkv",
        target_inode=path,
        media_id=media_id,
        action=PlanAction.IMPORT,
        season=season,
        episode_start=start,
        episode_end=end,
    )


class TestLate:
    """卡片那一集是遲到判定裡晚的集時是「晚 N 天」（M5.5 票 12），N 從播出日算；已入庫仍優先。"""

    async def test_a_late_episode_says_how_many_days_since_it_aired(
        self, session: AsyncSession
    ) -> None:
        factory = await credentialled(session, tmdb())
        apothecary = await add_media(session, APOTHECARY)
        media = await session.get(Media, apothecary)
        assert media is not None
        # 每週一集，第 5 集週二（11/03）播；第 1–4 集入庫了，門檻 0 天：週三就晚了。
        media.tmdb_snapshot_json = MediaSnapshot(
            tmdb_id=APOTHECARY.tmdb_id,
            kind=MediaKind.TV,
            title=APOTHECARY.title,
            title_en=APOTHECARY.title,
            title_original=APOTHECARY.title,
            seasons=(
                SeasonSnapshot(
                    season_number=2,
                    episode_count=6,
                    episodes=tuple(
                        EpisodeSnapshot(
                            episode_number=n, air_date=date(2026, 11, 3) - timedelta(weeks=5 - n)
                        )
                        for n in range(1, 7)
                    ),
                ),
            ),
        ).model_dump(mode="json")
        await subscribe(session, apothecary)
        session.add(ledger(apothecary, season=2, start=1, end=4, path="a"))
        settings = await read_settings(session, RssSettings)
        settings.overdue_days = 0
        await write_settings(session, settings)
        await session.commit()

        cards = by_media(await read_schedule(session, factory))

        assert cards[apothecary].status is ScheduleStatus.LATE
        assert cards[apothecary].late_days == 1
        assert cards["tv:209867"].late_days is None


# --- 第二層：時刻與評分（M5.5 票 14） ----------------------------------------------------------

#: 原文名是日文的兩部：週二播過一集（過去的）、週六要播一集（未來的）。
PAST = replace(APOTHECARY, original_title="薬屋のひとりごと")
FUTURE = replace(FRIEREN, original_title="葬送のフリーレン")


def japanese_tmdb() -> FakeTmdbClient:
    return tmdb(
        airing=[PAST, FUTURE],
        details=(
            detail(PAST, episode(2, 5, date(2026, 11, 3)), episode(2, 6, date(2026, 11, 10))),
            detail(FUTURE, episode(2, 4, date(2026, 11, 1)), episode(2, 5, date(2026, 11, 7))),
        ),
    )


def airs(media: int, native: str, at: datetime, episode: int = 5) -> Airing:
    return Airing(media_id=media, episode=episode, airs_at=at, native_title=native)


def rated(bgm_id: int, name: str, score: float | None = 8.1, votes: int = 900) -> CalendarItem:
    return CalendarItem(
        id=bgm_id,
        name=name,
        name_cn="",
        air_date="2026-10-04",
        weekday=6,
        score=score,
        votes=votes,
        rank=None,
    )


#: 週六 23:00（日本時間）：TMDB 說 11/07 那一集。
SATURDAY_NIGHT = datetime(2026, 11, 7, 23, 0, tzinfo=JST)


def by_media(week: schedule.ScheduleWeek) -> dict[str, schedule.ScheduleCard]:
    return {card.media_id: card for card in week.cards}


class TestAiringTimeAndRating:
    async def test_a_future_episode_shows_its_time_and_the_work_its_rating(
        self, session: AsyncSession
    ) -> None:
        """原文名與 AniList / Bangumi 的原文名相同才算同一部（brief §20.3）。"""
        anilist = FakeAniList(
            airings=[
                airs(10, "葬送のフリーレン", SATURDAY_NIGHT),
                airs(11, "薬屋のひとりごと", datetime(2026, 11, 3, 23, 0, tzinfo=JST)),
            ]
        )
        bgm = FakeBgm(
            items=[rated(500, "葬送のフリーレン"), rated(501, "薬屋のひとりごと", 7.5, 40)]
        )
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist, bgm=bgm)

        cards = by_media(await read_schedule(session, factory))

        future, past = cards["tv:209867"], cards["tv:220542"]
        assert (future.airs_at, future.score, future.votes) == (SATURDAY_NIGHT, 8.1, 900)
        assert future.airs_at is not None and future.airs_at.tzinfo is UTC  # API 一律送 UTC
        # 過去的集不給時刻（AniList 只保證未來的準確），評分是作品的，照樣給
        assert (past.airs_at, past.score, past.votes) == (None, 7.5, 40)

    async def test_the_fake_window_excludes_both_ends_like_anilist(self) -> None:
        """`airingAt_greater` / `_lesser` 兩端都不含：替身要一樣，時段剛好在午夜的才對得上。"""
        midnight = datetime(2026, 11, 1, tzinfo=JST)
        anilist = FakeAniList(airings=[airs(10, "x", midnight)])

        assert await anilist.airing(midnight, datetime(2026, 11, 2, tzinfo=JST)) == []

    async def test_it_asks_anilist_for_the_week_a_day_wider_on_each_side_in_japan(
        self, session: AsyncSession
    ) -> None:
        """深夜檔兩邊常差一天，同 discover；查詢的時段整週固定，快取才接得住。"""
        anilist = FakeAniList()
        await read_schedule(session, await credentialled(session, japanese_tmdb(), anilist=anilist))

        assert anilist.asked == [
            (
                "airing",
                (datetime(2026, 11, 1, tzinfo=JST), datetime(2026, 11, 10, tzinfo=JST)),
            )
        ]

    async def test_a_late_night_slot_a_day_after_tmdbs_date_still_matches(
        self, session: AsyncSession
    ) -> None:
        """「25:00」：TMDB 寫 11/07，AniList 是 11/08 01:00。差一天以內算那一集。"""
        late = datetime(2026, 11, 8, 1, 0, tzinfo=JST)
        anilist = FakeAniList(airings=[airs(10, "葬送のフリーレン", late)])
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist)

        assert by_media(await read_schedule(session, factory))["tv:209867"].airs_at == late

    async def test_an_airing_two_days_off_is_another_episode_and_is_not_shown(
        self, session: AsyncSession
    ) -> None:
        anilist = FakeAniList(
            airings=[airs(10, "葬送のフリーレン", datetime(2026, 11, 9, 23, 0, tzinfo=JST))]
        )
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist)

        assert by_media(await read_schedule(session, factory))["tv:209867"].airs_at is None

    async def test_a_title_that_differs_is_not_guessed(self, session: AsyncSession) -> None:
        """續作的「第2期」、迷你動畫的「ミニ」：原文名不同就不顯示，不猜。"""
        anilist = FakeAniList(airings=[airs(10, "葬送のフリーレン 第2期", SATURDAY_NIGHT)])
        bgm = FakeBgm(items=[rated(500, "葬送のフリーレン 第2期")])
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist, bgm=bgm)

        future = by_media(await read_schedule(session, factory))["tv:209867"]

        assert (future.airs_at, future.score, future.votes) == (None, None, None)

    @pytest.mark.parametrize("bgm_start", ["2023-09-29", ""])
    async def test_a_bangumi_entry_of_another_season_or_without_a_date_has_no_rating(
        self, session: AsyncSession, bgm_start: str
    ) -> None:
        """TMDB 多季併成一部、原文名是系列名；Bangumi 一季一條，第一季常用系列名。開播日要對得上
        卡片那一季（差一天以內），否則第二季的卡會掛上第一季的分數。"""
        bgm = FakeBgm(items=[replace(rated(500, "葬送のフリーレン"), air_date=bgm_start)])
        factory = await credentialled(session, japanese_tmdb(), bgm=bgm)

        future = by_media(await read_schedule(session, factory))["tv:209867"]

        assert (future.score, future.votes) == (None, None)

    async def test_a_late_night_premiere_a_day_off_still_rates(self, session: AsyncSession) -> None:
        """深夜檔：Bangumi 記 10/03（日本的「24:30」前一天），TMDB 記 10/04。"""
        bgm = FakeBgm(items=[replace(rated(500, "葬送のフリーレン"), air_date="2026-10-03")])
        factory = await credentialled(session, japanese_tmdb(), bgm=bgm)

        assert by_media(await read_schedule(session, factory))["tv:209867"].score == 8.1

    async def test_titles_match_regardless_of_width_case_and_punctuation(
        self, session: AsyncSession
    ) -> None:
        anilist = FakeAniList(airings=[airs(10, "葬送の フリーレン！", SATURDAY_NIGHT)])
        bgm = FakeBgm(items=[rated(500, "葬送のフリーレン!")])
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist, bgm=bgm)

        future = by_media(await read_schedule(session, factory))["tv:209867"]

        assert (future.airs_at, future.score) == (SATURDAY_NIGHT, 8.1)

    async def test_two_works_with_the_same_title_are_not_told_apart(
        self, session: AsyncSession
    ) -> None:
        anilist = FakeAniList(
            airings=[
                airs(10, "葬送のフリーレン", SATURDAY_NIGHT),
                airs(12, "葬送のフリーレン", SATURDAY_NIGHT),
            ]
        )
        bgm = FakeBgm(items=[rated(500, "葬送のフリーレン"), rated(502, "葬送のフリーレン")])
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist, bgm=bgm)

        future = by_media(await read_schedule(session, factory))["tv:209867"]

        assert (future.airs_at, future.score) == (None, None)

    async def test_two_airings_of_the_same_work_take_the_nearest_day(
        self, session: AsyncSession
    ) -> None:
        """一週播兩集的：TMDB 那一天的那一筆，不是隔天的那一筆。"""
        anilist = FakeAniList(
            airings=[
                airs(10, "葬送のフリーレン", datetime(2026, 11, 6, 23, 0, tzinfo=JST), 4),
                airs(10, "葬送のフリーレン", SATURDAY_NIGHT, 5),
            ]
        )
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist)

        assert by_media(await read_schedule(session, factory))["tv:209867"].airs_at == (
            SATURDAY_NIGHT
        )

    @pytest.mark.parametrize(("score", "votes"), [(None, 0), (7.2, 0)])
    async def test_a_rating_without_a_score_or_its_votes_is_not_shown(
        self, session: AsyncSession, score: float | None, votes: int
    ) -> None:
        """有分數沒人數是 Bangumi 少了 `total`：不寫「0 人打分」。"""
        bgm = FakeBgm(items=[rated(500, "葬送のフリーレン", score=score, votes=votes)])
        factory = await credentialled(session, japanese_tmdb(), bgm=bgm)

        future = by_media(await read_schedule(session, factory))["tv:209867"]

        assert (future.score, future.votes) == (None, None)


class Stuck(FakeAniList):
    """一直不回答的 AniList（被限流時 `Throttle` 會停下來等）。"""

    calls: int = 0

    async def airing(self, start: datetime, end: datetime) -> list[Airing]:
        self.calls += 1
        await asyncio.sleep(60)
        return []


class TestSecondLayerFailures:
    """外部來源失敗時卡片照常顯示，只少這兩格（票 14 驗收）。"""

    async def test_a_failed_source_is_not_asked_again_for_a_while(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """掛掉的來源記一陣子（`LEFT_OUT_SECONDS`）：不讓每一次打開都等它到逾時。"""
        monkeypatch.setattr(schedule, "SECOND_LAYER_TIMEOUT", 0.01)
        anilist = Stuck()
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist)

        await read_schedule(session, factory)
        await read_schedule(session, factory)

        assert anilist.calls == 1

    @pytest.mark.parametrize(
        "error", [ServiceUnavailableError("AniList is down"), ProtocolMismatchError("odd")]
    )
    async def test_anilist_failing_leaves_the_times_out_and_keeps_the_ratings(
        self, session: AsyncSession, error: ServiceError
    ) -> None:
        anilist = FakeAniList(airings=[airs(10, "葬送のフリーレン", SATURDAY_NIGHT)], error=error)
        bgm = FakeBgm(items=[rated(500, "葬送のフリーレン")])
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist, bgm=bgm)

        week = await read_schedule(session, factory)

        assert (week.problem, len(week.cards)) == (None, 2)
        future = by_media(week)["tv:209867"]
        assert (future.airs_at, future.score) == (None, 8.1)

    async def test_bangumi_failing_leaves_the_ratings_out_and_keeps_the_times(
        self, session: AsyncSession
    ) -> None:
        anilist = FakeAniList(airings=[airs(10, "葬送のフリーレン", SATURDAY_NIGHT)])
        bgm = FakeBgm(error=ServiceUnavailableError("bgm.tv is down"))
        factory = await credentialled(session, japanese_tmdb(), anilist=anilist, bgm=bgm)

        week = await read_schedule(session, factory)

        assert (week.problem, len(week.cards)) == (None, 2)
        future = by_media(week)["tv:209867"]
        assert (future.airs_at, future.score) == (SATURDAY_NIGHT, None)

    async def test_a_source_that_does_not_answer_in_time_is_left_out(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AniList 被限流時會停下來等一分鐘（`anilist.client.Throttle`）：時間表不陪它等。"""
        monkeypatch.setattr(schedule, "SECOND_LAYER_TIMEOUT", 0.01)
        bgm = FakeBgm(items=[rated(500, "葬送のフリーレン")])
        factory = await credentialled(session, japanese_tmdb(), anilist=Stuck(), bgm=bgm)

        week = await asyncio.wait_for(read_schedule(session, factory), timeout=5)

        future = by_media(week)["tv:209867"]
        assert (future.airs_at, future.score) == (None, 8.1)

    async def test_tmdb_failing_does_not_wait_for_the_second_layer(
        self, session: AsyncSession
    ) -> None:
        """第二層與 TMDB 同時抓；TMDB 失敗就整頁說問題，不等還沒回來的 AniList。"""
        client = tmdb(error=ServiceUnavailableError("TMDB is down"))
        factory = await credentialled(session, client, anilist=Stuck())

        week = await asyncio.wait_for(read_schedule(session, factory), timeout=5)

        assert week.problem is TmdbProblem.UNREACHABLE
