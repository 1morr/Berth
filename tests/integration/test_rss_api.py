"""`/rss` 端點（plan §6 rss 群組、M3 票 08）。

命令本身在 `test_rss.py`；這裡驗的是 HTTP 那一層：畫面上那條路（加 Feed → 立即輪詢 → 待綁定 →
綁定）走得通、拒絕的形狀與狀態碼。「誰進得來」在 `test_auth_api.py` 的整張表。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import create_app
from berth.models import Route
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
