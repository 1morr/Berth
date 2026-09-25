"""`/rss` 端點（plan §6 rss 群組、M3 票 08）。

命令本身在 `test_rss.py`；這裡驗的是 HTTP 那一層：畫面上那條路（加 Feed → 立即輪詢 → 待綁定 →
綁定）走得通、拒絕的形狀與狀態碼。「誰進得來」在 `test_auth_api.py` 的整張表。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from berth.adapters.rss import acgrip
from berth.adapters.rss.mikan import bangumi_url, parse_feed, search_url
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import JobState, JobTrigger, PlanAction, Tags
from berth.main import create_app
from berth.models import Job, LedgerEntry, Media, Route
from tests.conftest import FIXTURES
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import (
    FEED,
    FEED_URL,
    KIMI,
    KIMI_ID,
    KIMI_KEY,
    anime_route,
    episode_pages,
    kimi,
    torrents,
)
from tests.integration.test_rss_preview import ACGRIP, ACGRIP_URL
from tests.integration.test_rss_screen import (
    KIMI_NAME,
    SINGLE,
    SINGLE_URL,
    Release,
    serve,
    serve_single,
)

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    made = factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]), admin=(ADMIN["username"], ADMIN["password"])
        ),
    )
    made.rss_.pages = {FEED_URL: FEED, **episode_pages()}
    made.torrent_ = torrents()
    return made


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        yield running


def seed(client: TestClient, roots: dict[str, Path]) -> int:
    """精靈的前幾步、《与你相恋》那一列、一條 anime Route。回 Route 的 id。"""

    async def run() -> int:
        # `app.state` 是 Starlette 的動態屬性，型別上看不到 lifespan 掛上去的 session factory。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await kimi(session)
            route: Route = await anime_route(session, roots)
            return route.id

    return asyncio.run(run())


def sign_in(client: TestClient) -> None:
    assert client.post("/api/auth/login", json=ADMIN, headers=BROWSER).status_code == 200


class TestThePageFlow:
    def test_add_poll_bind_and_see_the_jobs(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        route_id = seed(client, roots)
        sign_in(client)

        added = client.post("/api/rss/feeds", json={"url": FEED_URL}, headers=BROWSER)
        assert added.status_code == 201, added.text
        feed = added.json()
        assert (feed["kind"], feed["name"], feed["items"]) == ("mikan", "mikanani.me", 0)
        assert feed["route_id"] is None

        polled = client.post(f"/api/rss/feeds/{feed['id']}/poll", headers=BROWSER)
        assert polled.json() == {"items": 12, "series": 11, "bound": 0, "submitted": 0}

        series = client.get("/api/rss/series").json()
        pending = next(row for row in series if row["key"] == KIMI_KEY)
        assert (pending["media_id"], pending["waiting"]) == (None, 2)
        # 番組頁不在替身裡：自動綁定查不到，理由照封閉集合的形狀送出去（票 09）。
        assert [reason["code"] for reason in pending["reasons"]] == ["lookup_failed"]
        assert pending["candidates"] == []

        bound = client.put(
            f"/api/rss/series/{pending['id']}/binding",
            json={"media": KIMI_ID, "route": route_id},
            headers=BROWSER,
        )
        assert bound.status_code == 200, bound.text
        assert (bound.json()["media_id"], bound.json()["submitted"]) == (KIMI_ID, 2)

        jobs = client.get("/api/jobs").json()
        assert {row["hash"] for row in jobs} == {item.info_hash for item in KIMI}
        items = client.get("/api/rss/items").json()
        assert len(items) == 12
        assert {row["status"] for row in items if row["series_id"] == pending["id"]} == {
            "downloaded"
        }

    def test_deleting_a_feed_says_how_many_items_went(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed(client, roots)
        sign_in(client)
        feed = client.post("/api/rss/feeds", json={"url": FEED_URL}, headers=BROWSER).json()
        client.post(f"/api/rss/feeds/{feed['id']}/poll", headers=BROWSER)

        deleted = client.delete(f"/api/rss/feeds/{feed['id']}", headers=BROWSER)

        assert deleted.json() == {"items": 12}
        assert client.get("/api/rss/feeds").json() == []


class TestRefusals:
    def test_a_feed_from_elsewhere_is_422_with_the_reason(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed(client, roots)
        sign_in(client)

        refused = client.post(
            "/api/rss/feeds", json={"url": "https://example.com/feed"}, headers=BROWSER
        )

        assert refused.status_code == 422
        assert refused.json()["detail"] == {
            "reason": "feed_unsupported",
            "detail": "https://example.com/feed",
        }

    def test_a_feed_route_that_does_not_exist_is_422(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed(client, roots)
        sign_in(client)

        refused = client.post(
            "/api/rss/feeds", json={"url": FEED_URL, "route": 999}, headers=BROWSER
        )

        assert refused.status_code == 422
        assert refused.json()["detail"] == {"reason": "route_missing", "detail": "999"}
        assert client.get("/api/rss/feeds").json() == []

    def test_binding_a_missing_series_is_404(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        route_id = seed(client, roots)
        sign_in(client)

        refused = client.put(
            "/api/rss/series/999/binding",
            json={"media": KIMI_ID, "route": route_id},
            headers=BROWSER,
        )

        assert refused.status_code == 404
        assert refused.json()["detail"]["reason"] == "series_missing"

    def test_binding_without_backfill(self, client: TestClient, roots: dict[str, Path]) -> None:
        """`backfill: false`（票 12）：只送聚合 feed 帶到的兩集；替身上沒有單一 feed 也照樣綁。"""
        route_id = seed(client, roots)
        sign_in(client)
        feed = client.post("/api/rss/feeds", json={"url": FEED_URL}, headers=BROWSER).json()
        client.post(f"/api/rss/feeds/{feed['id']}/poll", headers=BROWSER)
        pending = next(
            row for row in client.get("/api/rss/series").json() if row["key"] == "mikan:4009:370"
        )

        bound = client.put(
            f"/api/rss/series/{pending['id']}/binding",
            json={"media": KIMI_ID, "route": route_id, "backfill": False},
            headers=BROWSER,
        )

        assert bound.status_code == 200, bound.text
        assert bound.json()["submitted"] == 2


class TestTheFirstRound:
    """新搜尋 feed 的第一輪預覽（票 11）：預覽 → 選「只追之後的」→ 再選一次是 409。"""

    def test_preview_then_follow_from_now(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        seed(client, roots)
        sign_in(client)
        factory.rss_.pages[ACGRIP_URL] = ACGRIP

        added = client.post("/api/rss/feeds", json={"url": ACGRIP_URL}, headers=BROWSER).json()
        assert (added["kind"], added["primed_at"]) == ("acgrip", None)
        feed = added["id"]
        assert client.post(f"/api/rss/feeds/{feed}/poll", headers=BROWSER).status_code == 200

        preview = client.get(f"/api/rss/feeds/{feed}/preview")
        assert preview.status_code == 200
        assert len(preview.json()) == 30
        assert {row["status"] for row in preview.json()} == {"unbound"}
        assert all(row["size"] for row in preview.json())

        primed = client.post(
            f"/api/rss/feeds/{feed}/prime", json={"mode": "later"}, headers=BROWSER
        )
        assert primed.status_code == 200, primed.text
        assert primed.json()["passed"] == 30
        assert primed.json()["feed"]["primed_at"] is not None

        again = client.post(f"/api/rss/feeds/{feed}/prime", json={"mode": "all"}, headers=BROWSER)
        assert again.status_code == 409
        assert again.json()["detail"]["reason"] == "feed_primed"

    def test_follow_from_now_on_a_feed_that_cannot_be_read_is_502(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed(client, roots)
        sign_in(client)
        feed = client.post("/api/rss/feeds", json={"url": ACGRIP_URL}, headers=BROWSER).json()

        refused = client.post(
            f"/api/rss/feeds/{feed['id']}/prime", json={"mode": "later"}, headers=BROWSER
        )

        assert refused.status_code == 502
        assert refused.json()["detail"]["reason"] == "feed_unreachable"
        assert client.get("/api/rss/feeds").json()[0]["primed_at"] is None


class TestExclusions:
    """排除條件的三層（票 10）：存得進去、清單說得出為什麼沒下載、寫壞的存不進去。"""

    def test_the_three_layers_round_trip_and_the_items_say_why(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed(client, roots)
        sign_in(client)
        assert client.get("/api/rss/exclusions").json() == {"not_single": True, "rules": []}
        saved = client.put(
            "/api/rss/exclusions", json={"not_single": True, "rules": ["Baha"]}, headers=BROWSER
        )
        assert saved.json() == {"not_single": True, "rules": ["Baha"]}
        feed = client.post("/api/rss/feeds", json={"url": FEED_URL}, headers=BROWSER).json()
        ruled = client.put(
            f"/api/rss/feeds/{feed['id']}/exclusions", json={"rules": [" 720p "]}, headers=BROWSER
        )
        assert ruled.json()["exclusions"] == ["720p"]

        client.post(f"/api/rss/feeds/{feed['id']}/poll", headers=BROWSER)

        series = next(row for row in client.get("/api/rss/series").json() if row["key"] == KIMI_KEY)
        on_series = client.put(
            f"/api/rss/series/{series['id']}/exclusions", json={"rules": ["/v2$/"]}, headers=BROWSER
        )
        assert on_series.json()["exclusions"] == ["/v2$/"]
        baha = [row for row in client.get("/api/rss/items").json() if "Baha" in row["title"]]
        assert baha
        assert {row["status"] for row in baha} == {"excluded"}
        assert {(row["skip"]["code"], row["skip"]["params"]["rule"]) for row in baha} == {
            ("global_rule", "Baha")
        }

    def test_a_broken_regex_is_422_and_says_why(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed(client, roots)
        sign_in(client)

        refused = client.put(
            "/api/rss/exclusions", json={"not_single": True, "rules": ["/[简繁/"]}, headers=BROWSER
        )

        assert refused.status_code == 422
        body = refused.json()["detail"]
        assert body["reason"] == "rule_invalid"
        assert body["detail"].startswith("/[简繁/: unterminated character set")
        assert client.get("/api/rss/exclusions").json()["rules"] == []


def picked_job(row: dict[str, Any], route_id: int) -> dict[str, Any]:
    """一次性清單的一列 → 一般送單的 body（畫面送的就是這一份）。"""
    return {
        "source": {
            "url": row["url"],
            "title": row["title"],
            "info_hash": row["info_hash"],
            "published_at": row["published_at"],
        },
        "media": KIMI_ID,
        "route": route_id,
    }


class TestOneshot:
    """一次性 RSS 連結（票 18、brief §15）：讀一條網址、挑幾筆走一般的送單，不建 Feed。"""

    def test_a_single_feed_lists_the_season_and_three_picks_are_three_jobs(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        route_id = seed(client, roots)
        sign_in(client)
        serve_single(factory)

        read = client.post("/api/rss/oneshot", json={"url": SINGLE_URL}, headers=BROWSER)

        assert read.status_code == 200, read.text
        body = read.json()
        assert body["kind"] == "mikan"
        rows = body["items"]
        # 沒選作品時季集是發佈名寫的那一個；新的在前，照 feed 的順序。
        assert [row["episode_start"] for row in rows] == list(range(12, 0, -1))
        assert {row["release_kind"] for row in rows} == {"single"}
        assert {row["tags"]["group"] for row in rows} == {"喵萌奶茶屋&LoliHouse"}
        assert all(row["known"] is None and row["job_hash"] == "" for row in rows)

        picked = [row for row in rows if row["episode_start"] in (1, 2, 3)]
        for row in picked:
            sent = client.post("/api/jobs", json=picked_job(row, route_id), headers=BROWSER)
            assert sent.status_code == 200, sent.text
            assert sent.json()["created"] is True

        jobs = client.get("/api/jobs").json()
        assert {row["hash"] for row in jobs} == {row["info_hash"] for row in picked}
        assert {(row["trigger"], row["media_id"]) for row in jobs} == {("manual", KIMI_ID)}
        # 不建 Feed、不長 RSS Series、不寫 Feed Item。
        assert client.get("/api/rss/feeds").json() == []
        assert client.get("/api/rss/series").json() == []
        assert client.get("/api/rss/items").json() == []

    def test_a_collection_is_marked_and_can_be_sent(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        """排除條件的合集預設只管自動下載：這裡標出來，照樣送得出去。"""
        route_id = seed(client, roots)
        sign_in(client)
        batch = Release(370, f"[LoliHouse] {KIMI_NAME} [01-12 合集][WebRip 1080p HEVC-10bit AAC]")
        url = "https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=1"
        serve(factory, url, [batch])

        read = client.post(
            "/api/rss/oneshot",
            json={"url": url, "media": KIMI_ID, "route": route_id},
            headers=BROWSER,
        )

        (row,) = read.json()["items"]
        assert row["release_kind"] == "collection"
        assert (row["season"], row["episode_start"], row["episode_end"]) == (1, 1, 12)
        assert row["whole_season"] is True
        sent = client.post("/api/jobs", json=picked_job(row, route_id), headers=BROWSER)
        assert sent.status_code == 200, sent.text
        assert sent.json()["job"]["hash"] == batch.hash

    def test_with_a_work_it_says_what_the_ledger_and_the_jobs_already_have(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        """選了作品與 Route：第 3 集已經有 Job、第 5 集帳本已有同一個版本（另一個 hash）。"""
        route_id = seed(client, roots)
        sign_in(client)
        serve_single(factory)
        season = tuple(reversed(parse_feed(SINGLE)))
        rows = client.post("/api/rss/oneshot", json={"url": SINGLE_URL}, headers=BROWSER).json()
        third = next(one for one in rows["items"] if one["episode_start"] == 3)
        sent = client.post("/api/jobs", json=picked_job(third, route_id), headers=BROWSER)
        assert sent.is_success
        name = "Kimishinu - S01E05 [LoliHouse][1080p].mkv"
        library(client, route_id, season[4].title, name)

        read = client.post(
            "/api/rss/oneshot",
            json={"url": SINGLE_URL, "media": KIMI_ID, "route": route_id},
            headers=BROWSER,
        )

        assert read.status_code == 200, read.text
        by_episode = {row["episode_start"]: row for row in read.json()["items"]}
        assert by_episode[3]["job_hash"] == season[2].info_hash
        assert by_episode[5]["known"] == name
        assert [number for number, row in by_episode.items() if row["known"]] == [5]
        assert {row["season"] for row in by_episode.values()} == {1}

    def test_each_failure_says_which_kind_it_is(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        route_id = seed(client, roots)
        sign_in(client)
        page = "https://nyaa.si/?q=Kamiina+Botan"
        factory.rss_.pages[page] = b"<!DOCTYPE html><html><body>Nyaa</body></html>"
        serve_single(factory)

        def refused(body: dict[str, Any]) -> tuple[int, str]:
            answer = client.post("/api/rss/oneshot", json=body, headers=BROWSER)
            return answer.status_code, answer.json()["detail"]["reason"]

        assert refused({"url": "https://example.com/feed"}) == (422, "feed_unsupported")
        assert refused({"url": "https://acg.rip/.xml?term=nothing"}) == (502, "feed_unreachable")
        assert refused({"url": page}) == (502, "feed_not_rss")
        assert refused({"url": SINGLE_URL, "media": "tv:1", "route": route_id}) == (
            422,
            "media_missing",
        )
        assert refused({"url": SINGLE_URL, "media": KIMI_ID, "route": 999}) == (
            422,
            "route_missing",
        )


def library(client: TestClient, route_id: int, title: str, name: str) -> None:
    """帳本有 `title` 那一集：已入庫的一筆 Job，hash 與 feed 上的不同（同一個版本換 hash 重傳）。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            route = await session.get(Route, route_id)
            media = await session.get(Media, KIMI_ID)
            assert route is not None and media is not None
            reupload = "e" * 40
            session.add(
                Job(
                    hash=reupload,
                    name=title,
                    source_url="",
                    media_id=media.id,
                    route_id=route.id,
                    state=JobState.IMPORTED,
                    trigger=JobTrigger.MANUAL,
                )
            )
            session.add(
                LedgerEntry(
                    job_hash=reupload,
                    source_rel_path=name,
                    source_abs_path=f"/data/torrent/complete/anime/{name}",
                    source_inode="1",
                    source_dev="1",
                    target_path=f"{route.target_path}/{media.folder_name}/Season 01/{name}",
                    target_inode="1",
                    media_id=media.id,
                    season=1,
                    episode_start=5,
                    tags_json=Tags(resolution="1080p", group="LoliHouse").model_dump(mode="json"),
                    action=PlanAction.IMPORT,
                )
            )
            await session.commit()

    asyncio.run(run())


class TestSubscribeFromTheDetailPage:
    """詳情頁的「RSS 訂閱」（票 19）：搜番組 → 列字幕組 → 訂閱；以標題建搜尋 feed → 第一輪預覽。"""

    def test_search_pick_a_subgroup_subscribe_and_list_the_series_of_the_work(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        route_id = seed(client, roots)
        sign_in(client)
        mikan = FIXTURES / "http" / "mikan"
        factory.rss_.pages[search_url("Frieren")] = (
            mikan / "home-search.frieren.html"
        ).read_bytes()
        factory.rss_.pages[bangumi_url(4009)] = (mikan / "home-bangumi.4009.html").read_bytes()
        serve_single(factory)

        hits = client.get("/api/rss/mikan/search", params={"q": "Frieren"})
        assert hits.status_code == 200, hits.text
        assert hits.json()[0] == {"id": 3141, "title": "葬送的芙莉莲"}
        bangumi = client.get("/api/rss/mikan/bangumi/4009").json()
        loli = next(group for group in bangumi["subgroups"] if group["id"] == 370)
        assert (loli["name"], loli["updated"], loli["bound_to"]) == (
            "LoliHouse",
            "2026-09-24",
            None,
        )

        done = client.post(
            "/api/rss/subscriptions/mikan",
            json={
                "media": KIMI_ID,
                "route": route_id,
                "bangumi": 4009,
                "subgroup": 370,
                "name": "与你相恋到生命尽头 · LoliHouse",
            },
            headers=BROWSER,
        )

        assert done.status_code == 201, done.text
        assert done.json()["feed"]["url"] == SINGLE_URL
        assert done.json()["series"]["submitted"] == len(parse_feed(SINGLE))
        (listed,) = client.get("/api/rss/series", params={"media": KIMI_ID}).json()
        assert (listed["source"], listed["group"], listed["confirmed"]) == (
            "mikan",
            "喵萌奶茶屋&LoliHouse",
            False,
        )
        assert listed["latest_title"] and listed["latest_at"]
        assert client.get("/api/rss/series", params={"media": "tv:1"}).json() == []

    def test_subscribing_twice_is_409(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        route_id = seed(client, roots)
        sign_in(client)
        serve_single(factory)
        body = {"media": KIMI_ID, "route": route_id, "bangumi": 4009, "subgroup": 370}
        client.post("/api/rss/subscriptions/mikan", json=body, headers=BROWSER)

        again = client.post("/api/rss/subscriptions/mikan", json=body, headers=BROWSER)

        assert again.status_code == 409
        assert again.json()["detail"]["reason"] == "series_bound"

    def test_a_title_search_feed_opens_its_first_round(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        route_id = seed(client, roots)
        sign_in(client)
        factory.rss_.pages[acgrip.search_url("Kimi ga Shinu made")] = ACGRIP

        made = client.post(
            "/api/rss/subscriptions/search",
            json={
                "media": KIMI_ID,
                "route": route_id,
                "kind": "acgrip",
                "term": "Kimi ga Shinu made",
            },
            headers=BROWSER,
        )

        assert made.status_code == 201, made.text
        feed = made.json()
        assert (feed["url"], feed["primed_at"]) == (ACGRIP_URL, None)
        preview = client.get(f"/api/rss/feeds/{feed['id']}/preview").json()
        assert "matched" in {row["status"] for row in preview}
        assert "unbound" not in {row["status"] for row in preview}
