"""「正在下載」（M4 票 126，plan §11.5〈通知〉）。

一輪 RSS（一個 Feed 的一次輪詢、綁定後的補送）送出的 Job，依收件人與作品合成一則；人手按的下載送給
其他訂閱者、不送給按的人。斷言只看兩個公開的接縫：送單的那一個命令（`poll_feed`、`bind_series`）
之後，送出的一輪（`send_due`）交給 Discord 什麼。

替身是合成的 Mikan 聚合 feed：兩部作品各一個字幕組（番組 4009 與 5001），RSS Series 預先綁好，
所以那一輪讀到的就是 `matched`、在輪的最後送出。
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.notify import Message
from berth.adapters.qbittorrent import TorrentAdd
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.torrent import TorrentSource
from berth.adapters.torrent_fake import FakeTorrentFetcher
from berth.domain import (
    EpisodeSnapshot,
    JobState,
    Language,
    MediaKind,
    MediaSnapshot,
    NotificationKind,
    Role,
    SeasonSnapshot,
)
from berth.models import Job, Media, Route, RssFeed, RssSeries, User
from berth.naming import folder_name
from berth.services import downloading
from berth.services.notify import send_due
from berth.services.rss import bind_series, poll_feed, subscribe_mikan
from tests.integration.factories import FakeClientFactory
from tests.integration.test_notify import ADMIN_ID, CREW_ID, SECOND_ADMIN_ID, person, with_bot
from tests.integration.test_rss import NOW, harbour, routed_feed
from tests.integration.test_rss_screen import serve_single

pytestmark = pytest.mark.asyncio

FEED_URL = "https://mikanani.me/RSS/MyBangumi?token=REDACTED"
DOWNLOADING = (NotificationKind.DOWNLOADING,)

KIMI_BANGUMI, BOTAN_BANGUMI = 4009, 5001
KIMI_NAME = "与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai"
BOTAN_ID = "tv:300000"
BOTAN_NAME = "Kamiina Botan, Yoeru Sugata wa Yuri no Hana"


@dataclass(frozen=True)
class Release:
    bangumi: int
    title: str

    @property
    def hash(self) -> str:
        return hashlib.sha1(self.title.encode()).hexdigest()


def kimi(episode: int) -> Release:
    return Release(
        KIMI_BANGUMI, f"[LoliHouse] {KIMI_NAME} - {episode:02d} [WebRip 1080p HEVC-10bit AAC]"
    )


def botan(episode: int) -> Release:
    return Release(BOTAN_BANGUMI, f"[SubsPlease] {BOTAN_NAME} - {episode:02d} (1080p)")


def serve(factory: FakeClientFactory, releases: list[Release]) -> None:
    """合成的聚合 feed、每一筆的單集頁（指到它的番組 × 字幕組 1）與 `.torrent`。"""
    items = "".join(
        f'<item><guid isPermaLink="false">{escape(one.title)}</guid>'
        f"<link>https://mikanani.me/Home/Episode/{one.hash}</link>"
        f"<title>{escape(one.title)}</title>"
        '<torrent xmlns="https://mikanani.me/0.1/">'
        "<pubDate>2026-09-24T16:08:01</pubDate></torrent>"
        f'<enclosure type="application/x-bittorrent" length="1" '
        f'url="https://mikanani.me/Download/20260924/{one.hash}.torrent" /></item>'
        for one in releases
    )
    head = '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
    factory.rss_.pages[FEED_URL] = f"{head}{items}</channel></rss>".encode()
    for one in releases:
        factory.rss_.pages[f"https://mikanani.me/Home/Episode/{one.hash}"] = (
            f'<a href="/RSS/Bangumi?bangumiId={one.bangumi}&subgroupid=1" class="mikan-rss">'
        ).encode()
        factory.torrent_.sources[f"https://mikanani.me/Download/20260924/{one.hash}.torrent"] = (
            TorrentSource(info_hash=one.hash, content=f"torrent:{one.hash}".encode())
        )


def botan_snapshot() -> MediaSnapshot:
    first = date(2026, 7, 5)
    return MediaSnapshot(
        tmdb_id=300000,
        kind=MediaKind.TV,
        title="花語",
        title_en="Botan",
        title_original="かみいなボタン",
        year=2026,
        first_air_date=first,
        titles=(BOTAN_NAME, "Kamiina Botan"),
        seasons=(
            SeasonSnapshot(
                season_number=1,
                name="Season 1",
                names=("Season 1",),
                episode_count=12,
                air_date=first,
                episodes=tuple(
                    EpisodeSnapshot(
                        episode_number=number,
                        name=f"Episode {number}",
                        air_date=first + timedelta(days=7 * (number - 1)),
                    )
                    for number in range(1, 13)
                ),
            ),
        ),
    )


async def work(session: AsyncSession, media_id: str, shot: MediaSnapshot) -> Media:
    row = Media(
        id=media_id,
        tmdb_id=shot.tmdb_id,
        kind=MediaKind.TV,
        title_en=shot.title_en,
        title_original=shot.title_original,
        year=shot.year,
        folder_name=folder_name(shot),
        folder_frozen=True,
        tmdb_snapshot_json=shot.model_dump(mode="json"),
        tmdb_fetched_at=NOW,
    )
    session.add(row)
    return row


async def bound(session: AsyncSession, bangumi: int, media: Media, route: Route) -> RssSeries:
    """綁好、今天補過舊集的 RSS Series：輪詢讀到它的 Item 就是 `matched`。"""
    row = RssSeries(
        key=f"mikan:{bangumi}:1",
        title_raw="",
        mikan_bangumi_id=bangumi,
        mikan_subgroup_id=1,
        media_id=media.id,
        route_id=route.id,
        bound_by="1",
        backfilled_at=NOW,
    )
    session.add(row)
    return row


async def harbour_two(session: AsyncSession, roots: dict[str, Path]) -> FakeClientFactory:
    """`test_rss.harbour` 加第二部作品，兩個 RSS Series 都綁進 Route `Anime`、Feed 已加。"""
    kimi_media, route, factory = await harbour(session, roots)
    botan_media = await work(session, BOTAN_ID, botan_snapshot())
    await bound(session, KIMI_BANGUMI, kimi_media, route)
    await bound(session, BOTAN_BANGUMI, botan_media, route)
    await session.commit()
    await routed_feed(session, url=FEED_URL, name="Mikan")
    return factory


async def recipients(session: AsyncSession, factory: FakeClientFactory) -> None:
    """兩位訂閱了「正在下載」的人（一位英文）、一位只訂「可以看了」的人。三位都是替身 Jellyfin
    的帳號。"""
    await with_bot(session)
    await person(session, "skipper", discord=ADMIN_ID, kinds=DOWNLOADING)
    await person(session, "bosun", discord=SECOND_ADMIN_ID, kinds=DOWNLOADING, language=Language.EN)
    await person(session, "deckhand", role=Role.USER, discord=CREW_ID)
    await session.commit()
    for user in await session.scalars(select(User)):
        factory.jellyfin_.users[user.name] = "secret"


async def deliver(session: AsyncSession, factory: FakeClientFactory) -> None:
    await send_due(session, factory, now=NOW + timedelta(seconds=10))


def to(factory: FakeClientFactory, recipient: str) -> list[Message]:
    return [message for whom, message in factory.discord_.sent if whom == recipient]


async def feed_id(session: AsyncSession) -> int:
    found = await session.scalar(select(RssFeed.id).where(RssFeed.url == FEED_URL))
    assert found is not None
    return found


class TestOneRound:
    async def test_one_message_per_work_with_its_episodes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同一輪送出《与你相恋》3 集與《花語》2 集：每位收件人 2 則，季集範圍各自正確。"""
        factory = await harbour_two(session, roots)
        await recipients(session, factory)
        serve(factory, [kimi(3), kimi(4), kimi(5), botan(1), botan(2)])

        await poll_feed(session, factory, await feed_id(session), now=NOW)
        await deliver(session, factory)

        zh = to(factory, ADMIN_ID)
        assert len(zh) == 2
        by_title = {message.title: message for message in zh}
        assert by_title["正在下載：與妳相戀到生命盡頭"].description == "S01E03–E05"
        assert by_title["正在下載：花語"].description == "S01E01–E02"
        assert all(("Route", "Anime") in message.fields for message in zh)

        en = {message.title: message for message in to(factory, SECOND_ADMIN_ID)}
        assert set(en) == {"Downloading: Kimishinu", "Downloading: Botan"}
        assert to(factory, CREW_ID) == []
        jobs = list(await session.scalars(select(Job)))
        assert len(jobs) == 5
        assert {job.state for job in jobs} == {JobState.SUBMITTED}


class _RefusesBotan(FakeQbittorrentClient):
    """《花語》的 torrent 收不下（連不上），其餘照收。"""

    async def add_torrent(self, request: TorrentAdd) -> None:
        if request.content.decode() in {
            f"torrent:{botan(episode).hash}" for episode in range(1, 13)
        }:
            raise ServiceUnavailableError("POST /api/v2/torrents/add: connection refused")
        await super().add_torrent(request)


class TestNotSent:
    async def test_a_submission_qbittorrent_refused_is_not_downloading(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`submit_failed` 的那幾筆不算：這一輪只有《与你相恋》那一則。"""
        factory = await harbour_two(session, roots)
        factory.qbittorrent_ = _RefusesBotan()
        await recipients(session, factory)
        serve(factory, [kimi(3), kimi(4), botan(1), botan(2)])

        await poll_feed(session, factory, await feed_id(session), now=NOW)
        await deliver(session, factory)

        states = {job.name: job.state for job in await session.scalars(select(Job))}
        assert sorted(states.values()) == sorted(
            [JobState.SUBMITTED] * 2 + [JobState.SUBMIT_FAILED] * 2
        )
        (only,) = to(factory, ADMIN_ID)
        assert only.title == "正在下載：與妳相戀到生命盡頭"
        assert only.description == "S01E03–E04"


class _BreaksOn(FakeTorrentFetcher):
    """要到某一份 `.torrent` 時丟出沒人接的例外：一輪做到一半壞掉。"""

    def __init__(self, broken: Release, sources: dict[str, TorrentSource]) -> None:
        super().__init__(sources=sources)
        self.broken = f"https://mikanani.me/Download/20260924/{broken.hash}.torrent"

    async def fetch(self, url: str) -> TorrentSource:
        if url == self.broken:
            raise RuntimeError("the round breaks here")
        return await super().fetch(url)


class TestBrokenRound:
    async def test_what_was_sent_before_the_round_broke_is_still_told(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送出去的已經在 qBittorrent 裡了：輪中途壞掉也照說。"""
        factory = await harbour_two(session, roots)
        await recipients(session, factory)
        # 真的 feed 新的在前；送單舊的先，所以第 5 集是最後一筆。
        serve(factory, [kimi(5), kimi(4), kimi(3)])
        factory.torrent_ = _BreaksOn(kimi(5), factory.torrent_.sources)

        with pytest.raises(RuntimeError):
            await poll_feed(session, factory, await feed_id(session), now=NOW)
        await deliver(session, factory)

        (only,) = to(factory, ADMIN_ID)
        assert only.description == "S01E03–E04"


class _CancelledOn(FakeTorrentFetcher):
    """要到某一份 `.torrent` 時那一輪被 cancel：關機時正在跑的請求（M5 票 02）。"""

    def __init__(self, cancelled: Release, sources: dict[str, TorrentSource]) -> None:
        super().__init__(sources=sources)
        self.cancelled = f"https://mikanani.me/Download/20260924/{cancelled.hash}.torrent"

    async def fetch(self, url: str) -> TorrentSource:
        if url == self.cancelled:
            raise asyncio.CancelledError
        return await super().fetch(url)


class TestCancelledRound:
    async def test_what_was_sent_before_the_cancel_is_still_told(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """與壞掉的那一輪同理：cancel 之前送出的兩筆已經在 qBittorrent 裡了。"""
        factory = await harbour_two(session, roots)
        await recipients(session, factory)
        serve(factory, [kimi(5), kimi(4), kimi(3)])
        factory.torrent_ = _CancelledOn(kimi(5), factory.torrent_.sources)

        with pytest.raises(asyncio.CancelledError):
            await poll_feed(session, factory, await feed_id(session), now=NOW)
        await deliver(session, factory)

        (only,) = to(factory, ADMIN_ID)
        assert only.description == "S01E03–E04"

    async def test_a_write_that_fails_only_logs_and_the_cancel_goes_on(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """排不進去不蓋掉 cancel：關機照走，只留一行 log。"""
        factory = await harbour_two(session, roots)
        await recipients(session, factory)
        serve(factory, [kimi(5), kimi(4), kimi(3)])
        factory.torrent_ = _CancelledOn(kimi(5), factory.torrent_.sources)

        async def broken(*_args: object) -> None:
            raise RuntimeError("database is locked")

        monkeypatch.setattr(downloading, "_close", broken)

        with pytest.raises(asyncio.CancelledError):
            await poll_feed(session, factory, await feed_id(session), now=NOW)

        assert "downloading notifications of a broken round not queued" in caplog.messages


class _HoldsOn(FakeTorrentFetcher):
    """要到某一份 `.torrent` 時停住，等測試來 cancel（真的 `task.cancel()`）。"""

    def __init__(self, held: Release, sources: dict[str, TorrentSource]) -> None:
        super().__init__(sources=sources)
        self.held = f"https://mikanani.me/Download/20260924/{held.hash}.torrent"
        self.reached = asyncio.Event()

    async def fetch(self, url: str) -> TorrentSource:
        if url == self.held:
            self.reached.set()
            await asyncio.Event().wait()
        return await super().fetch(url)


class TestCancelledTwice:
    async def test_a_second_cancel_while_writing_waits_for_the_write(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """寫的時候再來一次 cancel（lifespan 自己被 cancel 時轉過來的那一次）：寫完才往上走，
        不留一段在背景用著呼叫端要關掉的 session。"""
        factory = await harbour_two(session, roots)
        await recipients(session, factory)
        serve(factory, [kimi(5), kimi(4), kimi(3)])
        fetcher = _HoldsOn(kimi(5), factory.torrent_.sources)
        factory.torrent_ = fetcher
        writing, release = asyncio.Event(), asyncio.Event()
        close = downloading._close

        async def held_close(*args: Any) -> None:
            writing.set()
            await release.wait()
            await close(*args)

        monkeypatch.setattr(downloading, "_close", held_close)
        running = asyncio.create_task(poll_feed(session, factory, await feed_id(session), now=NOW))
        await fetcher.reached.wait()
        running.cancel()
        await writing.wait()
        running.cancel()
        for _ in range(5):
            await asyncio.sleep(0)
        assert not running.done()
        release.set()

        with pytest.raises(asyncio.CancelledError):
            await running
        await deliver(session, factory)

        (only,) = to(factory, ADMIN_ID)
        assert only.description == "S01E03–E04"


class TestBinding:
    async def test_a_hundred_torrents_from_one_binding_are_one_message(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """試跑那一次的形狀（plan §11.5）：一次綁定送出上百個 torrent，每位收件人這部作品一則；
        按綁定的人在場，不告訴他。"""
        media, route, factory = await harbour(session, roots)
        await recipients(session, factory)
        feed = await routed_feed(session, url=FEED_URL, name="Mikan")
        serve(factory, [kimi(episode) for episode in range(1, 121)])
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await session.scalar(select(RssSeries).where(RssSeries.key == "mikan:4009:1"))
        assert series is not None and series.media_id is None
        skipper = await session.scalar(select(User).where(User.name == "skipper"))
        assert skipper is not None

        await bind_series(
            session,
            factory,
            series.id,
            media_id=media.id,
            route_id=route.id,
            user_id=skipper.id,
            now=NOW,
        )
        await deliver(session, factory)

        assert len(list(await session.scalars(select(Job)))) == 120
        assert to(factory, ADMIN_ID) == []
        (only,) = to(factory, SECOND_ADMIN_ID)
        assert only.title == "Downloading: Kimishinu"
        # 快照只有 12 集：之後的集數放不進任何一季，猜不到的不寫進範圍（`downloading._content`）。
        assert only.description == "S01E01–E12"


async def skipper_id(session: AsyncSession) -> int:
    found = await session.scalar(select(User.id).where(User.name == "skipper"))
    assert found is not None
    return found


class TestWhoPressed:
    """人在場按出來的一輪不告訴按的人；其他訂閱者照收（M4 票 126）。"""

    async def test_subscribing_from_the_media_page(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        await recipients(session, factory)
        serve_single(factory)

        await subscribe_mikan(
            session,
            factory,
            bangumi_id=4009,
            subgroup_id=370,
            media_id=media.id,
            route_id=route.id,
            user_id=await skipper_id(session),
            now=NOW,
        )
        await deliver(session, factory)

        assert to(factory, ADMIN_ID) == []
        (only,) = to(factory, SECOND_ADMIN_ID)
        assert only.title == "Downloading: Kimishinu"

    async def test_polling_now(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        """「立即輪詢」：按的人不收；同一個 Feed 的背景輪詢沒有人按，每一位都收（上面那幾條）。"""
        factory = await harbour_two(session, roots)
        await recipients(session, factory)
        serve(factory, [kimi(3)])

        await poll_feed(
            session, factory, await feed_id(session), user_id=await skipper_id(session), now=NOW
        )
        await deliver(session, factory)

        assert to(factory, ADMIN_ID) == []
        assert len(to(factory, SECOND_ADMIN_ID)) == 1
