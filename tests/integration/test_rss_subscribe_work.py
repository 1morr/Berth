"""以作品訂閱 Mikan（M5.6 票 08）：伺服器自己找番組、用開播日挑。

模型只給作品與推薦的字幕組；「用哪些名字搜、挑哪一個番組」從 skill 搬進程式（brief §15
〈從 Media 頁訂閱〉）。這一層讀真的錄下來的搜尋頁（`home-search.frieren.html`），番組頁只留
`parse` 用得到的幾個選擇器（`page()`）：這裡測的是挑選與命令，不是 HTML 抓取。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss import acgrip, mikan, nyaa
from berth.domain import FeedKind, MediaKind, MediaSnapshot, RssRefusal, label_of
from berth.models import Job, Media, Route, RssSeries
from berth.parser.bangumi import names
from berth.services import rss as rss_service
from berth.services.bangumi import MAX_SEARCH_TERMS, match_bangumi
from berth.services.rss import RssRejectedError, Subscription
from tests.conftest import FIXTURES
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import KIMI_ID, NOW, harbour, kimi_snapshot
from tests.integration.test_rss_screen import SINGLE_URL, serve_single
from tests.integration.test_rss_subscribe import (
    ACGRIP_FEED,
    MOUSE,
    feeds,
    mouse_torrents,
    skipper,
)

pytestmark = pytest.mark.asyncio

MIKAN = FIXTURES / "http" / "mikan"


def search_results(*hits: tuple[int, str]) -> bytes:
    """搜尋頁的結果格子：連到 `/Home/Bangumi/<id>` 的 `<a>` 裡那一個 `div.an-text`。"""
    cells = "".join(
        f'<a href="/Home/Bangumi/{bangumi}"><div class="an-text" title="{title}"></div></a>'
        for bangumi, title in hits
    )
    return f'<ul class="an-ul">{cells}</ul>'.encode()


def page(
    title: str,
    premiere: str,
    groups: tuple[tuple[int, str], ...],
    *,
    releases: int = 12,
) -> bytes:
    """番組頁的三個選擇器：中文名、放送开始、左欄的字幕組與它的發佈表。"""
    links = "".join(
        f'<a class="subgroup-name subgroup-{group}">{name}</a>'
        f'<span class="date">09/24/2026 12:00</span>'
        for group, name in groups
    )
    tables = "".join(
        f'<div class="subgroup-text" id="{group}">'
        + "".join(
            f'<a class="magnet-link-wrap">[{name}] {title} - {episode:02d}</a>'
            for episode in range(1, releases + 1)
        )
        + "</div>"
        for group, name in groups
    )
    return f'<p class="bangumi-title">{title}</p>放送开始：{premiere}{links}{tables}'.encode()


def frieren() -> MediaSnapshot:
    first = date(2023, 9, 29)
    return MediaSnapshot(
        tmdb_id=209867,
        kind=MediaKind.TV,
        title="葬送的芙莉蓮",
        title_en="Frieren: Beyond Journey's End",
        title_original="葬送のフリーレン",
        titles=("葬送的芙莉莲", "Frieren"),
        year=first.year,
        first_air_date=first,
    )


async def with_snapshot(
    session: AsyncSession, roots: dict[str, Path], snapshot: MediaSnapshot
) -> tuple[Media, Route, FakeClientFactory]:
    """`harbour` 的媒體換成另一份快照（挑選看的是快照裡的名字與首播日）。"""
    media, route, factory = await harbour(session, roots)
    row = await session.get(Media, media.id)
    assert row is not None
    row.tmdb_snapshot_json = snapshot.model_dump(mode="json")
    await session.commit()
    return row, route, factory


async def kimi_setup(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Media, Route, FakeClientFactory]:
    """《与你相恋》：搜尋頁與番組頁都是真的錄下來的，單一 feed 也在。"""
    media, route, factory = await harbour(session, roots)
    serve_single(factory)
    for term in names(kimi_snapshot()):
        factory.rss_.pages[mikan.search_url(term)] = search_results((4009, "与你相恋到生命尽头"))
    factory.rss_.pages[mikan.bangumi_url(4009)] = (MIKAN / "home-bangumi.4009.html").read_bytes()
    return media, route, factory


class TestMatchingTheBangumi:
    async def test_the_search_tries_every_name_of_the_work(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """繁中名、日文名、簡體名、英文名都搜；只有簡體那一次找得到也夠了（brief §20.12）。"""
        media, _, factory = await kimi_setup(session, roots)
        for term in names(kimi_snapshot()):
            if term != "与你相恋到生命尽头":
                factory.rss_.pages.pop(mikan.search_url(term), None)

        found = await match_bangumi(session, factory, media.id)

        assert found.id == 4009
        assert found.title == "与你相恋到生命尽头"
        assert found.subgroups

    async def test_at_most_four_names_are_searched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """每個名字要真的打一次 Mikan 的搜尋頁（約 1.5 秒）：一次最多 `MAX_SEARCH_TERMS` 個。"""
        many = MediaSnapshot(
            tmdb_id=209867,
            kind=MediaKind.TV,
            title="名字一",
            title_en="Name One",
            title_original="名前一",
            titles=("名字二", "名字三", "名字四", "名字五", "Name Five"),
            first_air_date=date(2023, 9, 29),
        )
        _, _, factory = await with_snapshot(session, roots, many)

        with pytest.raises(RssRejectedError):
            await match_bangumi(session, factory, KIMI_ID)

        searched = [url for url in factory.rss_.requested if url.startswith(mikan.search_url(""))]
        assert len(searched) == MAX_SEARCH_TERMS
        assert searched == [mikan.search_url(term) for term in names(many)[:MAX_SEARCH_TERMS]]

    async def test_several_bangumi_are_picked_by_the_premiere_date(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """真的搜尋頁回兩個番組：本季與第二季，作品的首播日挑第一季那一個。"""
        _, _, factory = await with_snapshot(session, roots, frieren())
        factory.rss_.pages[mikan.search_url("葬送的芙莉莲")] = (
            MIKAN / "home-search.frieren.html"
        ).read_bytes()
        factory.rss_.pages[mikan.bangumi_url(3141)] = page(
            "葬送的芙莉莲", "9/29/2023", ((370, "LoliHouse"), (583, "ANi"))
        )
        factory.rss_.pages[mikan.bangumi_url(3821)] = page(
            "葬送的芙莉莲 第二季", "1/16/2026", ((370, "LoliHouse"),)
        )

        found = await match_bangumi(session, factory, KIMI_ID)

        assert found.id == 3141
        assert [group.name for group in found.subgroups] == ["LoliHouse", "ANi"]

    async def test_no_bangumi_is_a_refusal(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """找不到番組：這張票先拒絕，理由交給模型（退回關鍵字來源是票 09）。"""
        media, _, factory = await kimi_setup(session, roots)
        empty = (MIKAN / "home-search.none.html").read_bytes()
        for term in names(kimi_snapshot()):
            factory.rss_.pages[mikan.search_url(term)] = empty

        with pytest.raises(RssRejectedError) as refused:
            await match_bangumi(session, factory, media.id)

        assert refused.value.reason is RssRefusal.BANGUMI_NOT_FOUND

    async def test_a_bangumi_without_subgroups_is_a_refusal(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, factory = await kimi_setup(session, roots)
        factory.rss_.pages[mikan.bangumi_url(4009)] = page("与你相恋到生命尽头", "7/7/2026", ())

        with pytest.raises(RssRejectedError) as refused:
            await match_bangumi(session, factory, media.id)

        assert refused.value.reason is RssRefusal.BANGUMI_WITHOUT_SUBGROUPS

    async def test_every_search_failing_is_unreachable(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, factory = await kimi_setup(session, roots)
        for term in names(kimi_snapshot()):
            factory.rss_.pages.pop(mikan.search_url(term), None)

        with pytest.raises(RssRejectedError) as refused:
            await match_bangumi(session, factory, media.id)

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE

    async def test_a_bangumi_page_that_cannot_be_read_is_unreachable(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """搜到了、番組頁卻讀不到：說讀不到，不是「Mikan 上沒有」。"""
        media, _, factory = await kimi_setup(session, roots)
        factory.rss_.pages.pop(mikan.bangumi_url(4009))

        with pytest.raises(RssRejectedError) as refused:
            await match_bangumi(session, factory, media.id)

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE


class TestSubscribing:
    async def test_it_creates_the_same_feed_as_subscribing_by_bangumi_id(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """核准之後建的 Feed、Series 與補到的整季，和 `subscribe_mikan` 建的一樣。"""
        media, route, factory = await kimi_setup(session, roots)

        done = await rss_service.subscribe(
            session,
            factory,
            media_id=media.id,
            subgroup="LoliHouse",
            route_id=route.id,
            user_id=1,
            actor=label_of(1),
            now=NOW,
        )

        (feed,) = await feeds(session)
        assert (feed.url, feed.kind, feed.primed_at, feed.last_polled_at) == (
            SINGLE_URL,
            FeedKind.MIKAN,
            NOW,
            NOW,
        )
        series = await session.scalar(select(RssSeries))
        assert series is not None
        assert (series.key, series.media_id, series.mikan_subgroup_name) == (
            "mikan:4009:370",
            media.id,
            "LoliHouse",
        )
        assert isinstance(done, Subscription)
        assert done.series.submitted == 12
        assert len(list(await session.scalars(select(Job)))) == 12

    async def test_a_subgroup_the_bangumi_does_not_have_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await kimi_setup(session, roots)

        with pytest.raises(RssRejectedError) as refused:
            await rss_service.subscribe(
                session,
                factory,
                media_id=media.id,
                subgroup="Nobody",
                route_id=route.id,
                user_id=1,
                actor=label_of(1),
                now=NOW,
            )

        assert refused.value.reason is RssRefusal.SUBGROUP_NOT_FOUND
        assert await feeds(session) == []


# --- 退回關鍵字來源（M5.6 票 09） ---


def keyword_feed(titles: list[tuple[str, str]]) -> bytes:
    """一個關鍵字搜尋 feed 的最小形狀：標題與發佈日（新的在前由呼叫端排）。"""
    items = "".join(
        f"<item><title>{title}</title>"
        f"<link>https://example.invalid/{index}.torrent</link>"
        f"<guid>https://nyaa.si/view/{index}</guid>"
        f"<pubDate>{published} -0000</pubDate></item>"
        for index, (title, published) in enumerate(titles)
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        f"<title>search</title>{items}</channel></rss>"
    ).encode()


def no_bangumi(factory: FakeClientFactory) -> None:
    """Mikan 的每一次搜尋都回空頁：這部作品在 Mikan 上沒有番組。"""
    empty = (MIKAN / "home-search.none.html").read_bytes()
    for term in names(kimi_snapshot()):
        factory.rss_.pages[mikan.search_url(term)] = empty


def serve_keywords(
    factory: FakeClientFactory, *, nyaa_titles: list[tuple[str, str]] | None = None
) -> None:
    """兩個關鍵字站的第一個名字：nyaa 是英文名、acg.rip 是中文名（`rss.keyword_terms`）。"""
    factory.rss_.pages[nyaa.search_url("Kimishinu")] = keyword_feed(
        nyaa_titles
        if nyaa_titles is not None
        else [
            ("[ANi] Kimi ga Shinu made Koi wo Shitai - 12 [1080P]", "Fri, 18 Sep 2026 04:00:00"),
            ("[ANi] Kimi ga Shinu made Koi wo Shitai - 11 [1080P]", "Fri, 11 Sep 2026 04:00:00"),
        ]
    )
    factory.rss_.pages[acgrip.search_url("與妳相戀到生命盡頭")] = keyword_feed(
        [
            ("[ANi] 與妳相戀到生命盡頭 - 12 [1080P][CHT]", "Fri, 18 Sep 2026 04:00:00"),
            ("[喵萌奶茶屋] 與妳相戀到生命盡頭 - 12 [1080P][CHT] ", "Fri, 18 Sep 2026 05:00:00"),
        ]
    )


class TestFallingBackToKeywordSources:
    """M5.6 票 09：Mikan 找不到番組、或番組上沒有那個字幕組時，伺服器自己改問 nyaa 與 acg.rip。"""

    async def test_no_bangumi_offers_both_keyword_sites_with_their_terms(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, factory = await kimi_setup(session, roots)
        no_bangumi(factory)
        serve_keywords(factory)

        offers = await rss_service.subscription_offers(session, factory, media.id, "ANi")

        assert [
            (offer.kind, offer.term, offer.name, offer.releases) for offer in offers.offers
        ] == [
            (FeedKind.NYAA, "Kimishinu", "ANi", 2),
            (FeedKind.ACGRIP, "與妳相戀到生命盡頭", "ANi", 1),
            (FeedKind.ACGRIP, "與妳相戀到生命盡頭", "喵萌奶茶屋", 1),
        ]

    async def test_a_bangumi_without_the_named_subgroup_lists_its_groups_first(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """番組有、模型推薦的那一組不在上面：Mikan 的照樣列（人可以改訂別組），關鍵字站接在後面。"""
        media, _, factory = await kimi_setup(session, roots)
        serve_keywords(factory)

        offers = await rss_service.subscription_offers(session, factory, media.id, "黒ネズミたち")

        kinds = [offer.kind for offer in offers.offers]
        assert kinds[0] is FeedKind.MIKAN and kinds[-1] is FeedKind.ACGRIP
        assert FeedKind.NYAA in kinds
        assert any(offer.name == "ANi" and offer.kind is FeedKind.MIKAN for offer in offers.offers)
        assert any(offer.name == "ANi" and offer.kind is FeedKind.ACGRIP for offer in offers.offers)

    async def test_a_subgroup_the_bangumi_has_never_asks_the_keyword_sites(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, factory = await kimi_setup(session, roots)

        await rss_service.subscription_offers(session, factory, media.id, "ANi")

        assert not any(
            url.startswith((nyaa.search_url(""), acgrip.search_url("")))
            for url in factory.rss_.requested
        )

    async def test_an_unreachable_mikan_does_not_fall_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """讀不到 Mikan 不是「Mikan 上沒有」：分不出來就不要自己換來源。"""
        media, _, factory = await kimi_setup(session, roots)
        for term in names(kimi_snapshot()):
            factory.rss_.pages.pop(mikan.search_url(term), None)
        serve_keywords(factory)

        with pytest.raises(RssRejectedError) as refused:
            await rss_service.subscription_offers(session, factory, media.id, "ANi")

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE
        assert not any(url.startswith(nyaa.search_url("")) for url in factory.rss_.requested)

    async def test_keyword_sites_that_answer_with_nothing_are_a_refusal(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, factory = await kimi_setup(session, roots)
        no_bangumi(factory)
        for term in ("Kimishinu", "Kimi ga Shinu made Koi wo Shitai"):
            factory.rss_.pages[nyaa.search_url(term)] = keyword_feed([])
        for term in ("與妳相戀到生命盡頭", "君が死ぬまで恋をしたい"):
            factory.rss_.pages[acgrip.search_url(term)] = keyword_feed([])

        with pytest.raises(RssRejectedError) as refused:
            await rss_service.subscription_offers(session, factory, media.id, "ANi")

        assert refused.value.reason is RssRefusal.SUBGROUPS_NOT_FOUND

    async def test_keyword_sites_that_cannot_be_read_are_unreachable(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, factory = await kimi_setup(session, roots)
        no_bangumi(factory)

        with pytest.raises(RssRejectedError) as refused:
            await rss_service.subscription_offers(session, factory, media.id, "ANi")

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE

    async def test_a_work_mikan_does_not_carry_is_subscribed_by_keyword(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收 1：Mikan 沒有番組時走關鍵字來源，建的 Feed 與作品頁的關鍵字訂閱一樣。"""
        media, route, factory = await kimi_setup(session, roots)
        no_bangumi(factory)
        serve_keywords(factory)
        factory.rss_.pages[acgrip.search_url("與妳相戀到生命盡頭")] = ACGRIP_FEED
        mouse_torrents(factory)
        user_id = await skipper(session)

        await rss_service.subscribe(
            session,
            factory,
            media_id=media.id,
            subgroup=MOUSE,
            route_id=route.id,
            user_id=user_id,
            actor=label_of(1),
            now=NOW,
        )

        (feed,) = await feeds(session)
        assert (feed.url, feed.kind, feed.subgroup) == (
            acgrip.search_url("與妳相戀到生命盡頭"),
            FeedKind.ACGRIP,
            MOUSE,
        )
        assert len(list(await session.scalars(select(Job)))) == 5

    async def test_the_keyword_choice_on_the_card_is_the_one_subscribed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """卡片上的選項蓋掉來源與搜尋詞（`source`、`term`）：照人選的那一個訂。"""
        media, route, factory = await kimi_setup(session, roots)
        factory.rss_.pages[acgrip.search_url("與妳相戀到生命盡頭")] = ACGRIP_FEED
        mouse_torrents(factory)
        user_id = await skipper(session)

        await rss_service.subscribe(
            session,
            factory,
            media_id=media.id,
            subgroup=MOUSE,
            kind=FeedKind.ACGRIP,
            term="與妳相戀到生命盡頭",
            route_id=route.id,
            user_id=user_id,
            actor=label_of(1),
            now=NOW,
        )

        (feed,) = await feeds(session)
        assert (feed.kind, feed.subgroup) == (FeedKind.ACGRIP, MOUSE)
        # 選了關鍵字來源就不必再找番組：Mikan 的搜尋頁一次都沒讀。
        assert not any(url.startswith(mikan.search_url("")) for url in factory.rss_.requested)
