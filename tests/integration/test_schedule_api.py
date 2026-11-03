"""時間表端點（M5.5 票 09）：形狀與誰進得來。命令本身在 `test_schedule.py`。

一般使用者看得到時間表與狀態類別，看不到字幕組與 Feed（比照 `services/why_not.py` 的範圍）：
回應裡根本沒有那幾格，不是畫面藏起來。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.ttl import TtlCache
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.domain import MediaKind
from berth.main import create_app
from berth.models import Media, RssSeries, TmdbSettings
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
from tests.integration.test_schedule import APOTHECARY, DETAILS, FRIEREN, TODAY

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
}


@pytest.fixture(autouse=True)
def this_week(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schedule, "local_today", lambda: TODAY)
    monkeypatch.setattr(
        schedule, "_CACHE", TtlCache(ttl=schedule.CACHE_SECONDS, size=schedule.CACHE_WEEKS)
    )


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(bundled_libraries(roots["library"])),
        tmdb=FakeTmdbClient(airing=[APOTHECARY, FRIEREN], details=DETAILS),
    )


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
    """精靈跑完、憑證存好，《藥師少女》有一條綁好的 RSS Series。"""

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
            session.add(RssSeries(key="mikan:1:2", title_raw="[ANi] x", media_id="tv:220542"))
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
