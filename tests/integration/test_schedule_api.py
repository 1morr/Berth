"""時間表端點（M5.5 票 09）：形狀與誰進得來。命令本身在 `test_schedule.py`。

一般使用者看得到時間表與狀態類別，看不到字幕組與 Feed（比照 `services/why_not.py` 的範圍）：
回應裡根本沒有那幾格，不是畫面藏起來。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.adapters.anilist.fake import FakeAniList
from berth.adapters.bgm.fake import FakeBgm
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.ttl import TtlCache
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.domain import FeedKind, MediaKind
from berth.main import create_app
from berth.models import Media, RssFeed, TmdbSettings
from berth.services import schedule
from berth.services.routes import build_routes
from berth.services.settings import write_settings
from berth.services.setup import complete_setup
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import (
    arrange,
    bundled_libraries,
    factory_for,
    fake_jellyfin,
    sign_in_crew,
    sign_in_owner,
)
from tests.integration.factories import FakeClientFactory
from tests.integration.test_schedule import (
    APOTHECARY,
    DETAILS,
    FRIEREN,
    NOW,
    SATURDAY_NIGHT,
    TODAY,
    airs,
    rated,
)

#: 卡片的每一格。多一格（例如字幕組）就要有人看一眼：一般使用者也拿得到這一份。
CARD_FIELDS = {
    "media_id",
    "tmdb_id",
    "title",
    "title_en",
    "poster_url",
    "poster_url_en",
    "air_date",
    "season",
    "episode",
    "status",
    "airs_at",
    "score",
    "votes",
}


@pytest.fixture(autouse=True)
def this_week(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schedule, "local_today", lambda: TODAY)
    monkeypatch.setattr(schedule, "utc_now", lambda: NOW)
    monkeypatch.setattr(schedule, "_LEFT_OUT", TtlCache(ttl=schedule.LEFT_OUT_SECONDS, size=2))
    monkeypatch.setattr(
        schedule, "_CACHE", TtlCache(ttl=schedule.CACHE_SECONDS, size=schedule.CACHE_WEEKS)
    )


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    factory = factory_for(
        roots,
        jellyfin=fake_jellyfin(bundled_libraries(roots["library"])),
        tmdb=FakeTmdbClient(airing=[APOTHECARY, FRIEREN], details=DETAILS),
    )
    # 測試的 TMDB 原文名就是英文名（`test_schedule.show`）
    factory.anilist_ = FakeAniList(airings=[airs(10, FRIEREN.original_title, SATURDAY_NIGHT)])
    factory.bgm_ = FakeBgm(items=[rated(500, FRIEREN.original_title)])
    return factory


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _seed(running, roots, factory)
        yield running


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    """精靈跑完、憑證存好，《藥師少女》有一條訂閱（預先綁定它的關鍵字 Feed，字幕組 ANi）。"""

    async def run() -> None:
        # `TestClient.app` 是 Starlette 的 `ASGIApp`，型別上沒有 `state`（實際是 FastAPI）。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await write_settings(
                session,
                TmdbSettings(api_key=TMDB_API_KEY, image_base_url="https://image.tmdb.org/t/p/"),
            )
            await session.commit()
            await build_routes(session, factory, ())
            await complete_setup(session)
            session.add(
                Media(
                    id="tv:220542",
                    tmdb_id=220542,
                    kind=MediaKind.TV,
                    title_en=APOTHECARY.title,
                    title_original=APOTHECARY.title,
                    folder_name=APOTHECARY.title,
                )
            )
            await session.flush()
            session.add(
                RssFeed(
                    name="acg.rip",
                    url="https://acg.rip/.xml?term=x",
                    kind=FeedKind.ACGRIP,
                    media_id="tv:220542",
                    subgroup="ANi",
                )
            )
            await session.commit()

    asyncio.run(run())


def test_it_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/schedule").status_code == 401


def test_an_ordinary_user_sees_the_week_and_the_status_but_no_subgroup(client: TestClient) -> None:
    sign_in_owner(client)
    sign_in_crew(client)

    response = client.get("/api/schedule")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["start"], body["end"], body["today"]) == ("2026-11-02", "2026-11-08", "2026-11-04")
    assert body["problem"] is None
    assert [set(card) for card in body["cards"]] == [CARD_FIELDS, CARD_FIELDS]
    assert [(card["media_id"], card["status"]) for card in body["cards"]] == [
        ("tv:220542", "subscribed"),
        ("tv:209867", "unsubscribed"),
    ]
    assert date.fromisoformat(body["cards"][0]["air_date"]) == date(2026, 11, 3)


def test_the_airing_time_is_an_instant_and_the_rating_carries_its_votes(
    client: TestClient,
) -> None:
    """時刻帶時區送（畫面照瀏覽器的時區寫），對不上的那一張三格都是 null。"""
    sign_in_owner(client)

    cards = {card["media_id"]: card for card in client.get("/api/schedule").json()["cards"]}

    frieren = cards["tv:209867"]
    assert datetime.fromisoformat(frieren["airs_at"]) == SATURDAY_NIGHT
    assert (frieren["score"], frieren["votes"]) == (8.1, 900)
    apothecary = cards["tv:220542"]
    assert (apothecary["airs_at"], apothecary["score"], apothecary["votes"]) == (None, None, None)
