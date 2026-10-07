"""頁 4 套件內的主鍵：測推薦站、把通過的加進去，一次做完（M4 票 44，審計 E-5）。

原本是測 → 勾 → 加三個動作；套件內的使用者沒有理由不要已經通過測試的推薦站。審計實測 Internet
Archive「測試通過、加入時卻失敗」：Prowlarr 加之前自己再連一次，那一次連不上。這種站要有自己的
結論，不算進已加入，也不和「測試就沒過」混在一起。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.adapters.prowlarr import ProwlarrIndexer
from berth.adapters.prowlarr.fake import DEFAULT_DEFINITIONS, FakeProwlarrClient
from berth.api.deps import get_bundled_services, get_client_factory
from berth.config import Config
from berth.main import create_app
from berth.services.indexer import DEFAULT_INDEXERS
from tests.integration.factories import FakeClientFactory
from tests.integration.test_setup_api import BROWSER, BUNDLED, _choose, _seen

#: 測試就不過的兩站（Cloudflare，brief §20.7 的原文）。
BLOCKED = {
    "1337x": "Unable to access 1337x.to, blocked by CloudFlare Protection.",
    "eztv": "Unable to access eztvx.to, blocked by CloudFlare Protection.",
}
#: 測得過、加入時被拒的一站。
FLAKY = {"acgrip": "Unable to connect to indexer, check the log above the ValidationFailure."}

PASSING = [name for name in DEFAULT_INDEXERS if name not in BLOCKED and name not in FLAKY]


def _present(definition_name: str, indexer_id: int) -> ProwlarrIndexer:
    """Prowlarr 裡已經有的一站（重裝保留了它的設定）。"""
    definition = next(row for row in DEFAULT_DEFINITIONS if row.definition_name == definition_name)
    return ProwlarrIndexer(
        id=indexer_id,
        name=definition.name,
        enabled=True,
        definition_name=definition_name,
        privacy=definition.privacy,
        language=definition.language,
        description=definition.description,
        protocol=definition.protocol,
    )


@contextmanager
def _signed_in(
    config: Config, tmp_path: Path, prowlarr: FakeProwlarrClient
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"))
    app.dependency_overrides[get_bundled_services] = lambda: BUNDLED
    app.dependency_overrides[get_client_factory] = lambda: FakeClientFactory(prowlarr=prowlarr)
    # 擁有者成立、qBittorrent 選好（同 `test_setup_api._claim`），Prowlarr 留給各組自己選。
    with TestClient(app, headers=BROWSER) as running:
        assert _choose(running, "jellyfin").status_code == 200
        owned = running.post(
            "/api/setup/owner",
            json={**_seen(running), "username": "skipper", "password": "harbour"},
        )
        assert owned.status_code == 200, owned.text
        assert _choose(running, "qbittorrent").status_code == 200
        yield running


class TestOneKey:
    @pytest.fixture
    def prowlarr(self) -> FakeProwlarrClient:
        return FakeProwlarrClient(rejects=BLOCKED, add_rejects=FLAKY)

    @pytest.fixture
    def client(
        self, config: Config, tmp_path: Path, prowlarr: FakeProwlarrClient
    ) -> Iterator[TestClient]:
        with _signed_in(config, tmp_path, prowlarr) as running:
            assert _choose(running, "prowlarr").status_code == 200
            yield running

    def test_one_request_tests_every_recommended_site_and_adds_only_the_ones_that_pass(
        self, client: TestClient, prowlarr: FakeProwlarrClient
    ) -> None:
        response = client.post("/api/setup/indexers/recommended")

        assert response.status_code == 200, response.text
        assert sorted(prowlarr.tested) == sorted(DEFAULT_INDEXERS)
        # 測試沒過的連送都不送；測過的才送去新增。
        assert prowlarr.add_attempts == [name for name in DEFAULT_INDEXERS if name not in BLOCKED]
        assert [row["definition_name"] for row in response.json()["sites"]] == PASSING

    def test_a_site_that_passed_the_test_but_failed_to_add_has_its_own_outcome(
        self, client: TestClient
    ) -> None:
        """三種結論分得開：加進去了、測過而加不進去、測試就沒過。重新讀這一頁也一樣。"""
        body = client.post("/api/setup/indexers/recommended").json()

        for answer in (body, client.get("/api/setup/indexers").json()):
            outcome = {
                row["definition_name"]: (row["passed"], row["stage"], row["reason"])
                for row in answer["checks"]
            }
            assert outcome["acgrip"] == (False, "add", "unreachable")
            assert outcome["1337x"] == (False, "test", "cloudflare")
            assert outcome["dmhy"] == (True, "add", None)
            assert "acgrip" not in [row["definition_name"] for row in answer["sites"]]

    def test_the_login_is_left_for_its_own_request(
        self, client: TestClient, prowlarr: FakeProwlarrClient
    ) -> None:
        """與「加入」同一個結論：還沒設過是待處理，主鍵不設登入、不讓 Prowlarr 重啟。"""
        body = client.post("/api/setup/indexers/recommended").json()

        assert [row["status"] for row in body["steps"] if row["step"] == "prowlarr_login"] == [
            "pending"
        ]
        assert prowlarr.restarts == 0

    def test_an_existing_prowlarr_is_refused(self, client: TestClient) -> None:
        """既有的那一台加站要按一次確認、看得到會加哪幾站（M4 票 20），沒有主鍵。"""
        _choose(client, "prowlarr", base_url="http://nas:9696", api_key="theirs")

        assert client.post("/api/setup/indexers/recommended").status_code == 422


class TestAlreadyThere:
    """重跑、重裝保留 Prowlarr 設定：已經在的站不重測、不重加。"""

    @pytest.fixture
    def prowlarr(self) -> FakeProwlarrClient:
        return FakeProwlarrClient(
            indexers=[_present("nyaasi", 1), _present("dmhy", 2)],
            rejects=BLOCKED,
            add_rejects=FLAKY,
        )

    @pytest.fixture
    def client(
        self, config: Config, tmp_path: Path, prowlarr: FakeProwlarrClient
    ) -> Iterator[TestClient]:
        with _signed_in(config, tmp_path, prowlarr) as running:
            assert _choose(running, "prowlarr").status_code == 200
            yield running

    def test_sites_already_in_prowlarr_are_left_alone(
        self, client: TestClient, prowlarr: FakeProwlarrClient
    ) -> None:
        body = client.post("/api/setup/indexers/recommended").json()

        assert {"nyaasi", "dmhy"}.isdisjoint(prowlarr.tested)
        assert {"nyaasi", "dmhy"}.isdisjoint(prowlarr.add_attempts)
        names = [row["definition_name"] for row in body["sites"]]
        assert sorted(names) == sorted(PASSING)

    def test_pressing_it_again_adds_nothing_twice(
        self, client: TestClient, prowlarr: FakeProwlarrClient
    ) -> None:
        client.post("/api/setup/indexers/recommended")
        before = len(prowlarr.add_attempts)

        body = client.post("/api/setup/indexers/recommended").json()

        # 第二次只再試上一次加不進去的那一站。
        assert prowlarr.add_attempts[before:] == list(FLAKY)
        names = [row["definition_name"] for row in body["sites"]]
        assert len(names) == len(set(names))
