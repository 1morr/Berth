"""套件內三個主機名解不解得到（M4 票 30，brief §19 2026-10-01 的決定）。

只有 Berth 時「套件內」照常列出；進頁只做主機名解析，解不到的卡片說「這套 compose 沒有起 X」。
**只查 DNS，不對服務發請求**：brief §19「選之前不發請求」不變。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.adapters import dns
from berth.adapters.dns import SystemHostResolver
from berth.api.deps import get_bundled_services, get_client_factory, get_host_resolver
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import create_app
from berth.services.clients import BundledServices
from tests.integration.factories import COMPOSE


class AnsweringResolver:
    """認得 `known` 裡的主機名，其餘解不到。記下被問過哪些。"""

    def __init__(self, known: set[str]) -> None:
        self.known = known
        self.asked: list[str] = []

    async def resolves(self, host: str) -> bool:
        self.asked.append(host)
        return host in self.known


class NoClients:
    """造任何一個服務 client 都是錯：這一支只查 DNS。"""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"GET /setup/compose built a {name} client")


@pytest.fixture
def resolver() -> AnsweringResolver:
    # 只有 Berth 與 qBittorrent：`COMPOSE_PROFILES=qbittorrent`。
    return AnsweringResolver({"qbittorrent"})


@pytest.fixture
def client(config: Config, tmp_path: Path, resolver: AnsweringResolver) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"))
    app.dependency_overrides[get_bundled_services] = lambda: BundledServices(
        targets=COMPOSE, prowlarr_api_key=""
    )
    app.dependency_overrides[get_client_factory] = NoClients
    app.dependency_overrides[get_host_resolver] = lambda: resolver
    with TestClient(app, headers={CSRF_HEADER: "XMLHttpRequest"}) as running:
        yield running


class TestComposeHosts:
    def test_unresolvable_hosts_are_marked_and_resolvable_ones_are_not(
        self, client: TestClient, resolver: AnsweringResolver
    ) -> None:
        # 擁有者成立之前就問得到：頁 1 的 Jellyfin 卡片要用。
        response = client.get("/api/setup/compose")

        assert response.status_code == 200
        assert response.json() == {
            "resolvable": {"jellyfin": False, "qbittorrent": True, "prowlarr": False}
        }
        # 問的是主機名，不是整條位址；三個都問，每個一次。
        assert sorted(resolver.asked) == ["jellyfin", "prowlarr", "qbittorrent"]

    def test_every_host_resolving_marks_none(
        self, client: TestClient, resolver: AnsweringResolver
    ) -> None:
        resolver.known = {"jellyfin", "qbittorrent", "prowlarr"}

        assert client.get("/api/setup/compose").json()["resolvable"] == {
            "jellyfin": True,
            "qbittorrent": True,
            "prowlarr": True,
        }


class TestSystemHostResolver:
    """真的問一次系統的解析器。

    解不到的那一個用含空白的名字：`getaddrinfo` 當場拒絕，與網路無關。`.invalid` 不行——有 fake-IP 的
    DNS（代理工具的 TUN 模式）連它也答一個 198.18.x（2026-10-03 在開發機實測）。
    """

    @pytest.mark.asyncio
    async def test_a_known_host_resolves(self) -> None:
        assert await SystemHostResolver().resolves("localhost") is True

    @pytest.mark.asyncio
    async def test_a_reserved_invalid_name_does_not(self) -> None:
        assert await SystemHostResolver().resolves("berth not a host") is False

    @pytest.mark.asyncio
    async def test_no_answer_in_time_is_not_taken_as_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """上游 DNS 一直不回：說不出結論就不說「沒有起」（畫面上什麼都不加）。"""

        async def never_answers(*_: object, **__: object) -> object:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        monkeypatch.setattr(dns, "RESOLVE_TIMEOUT_SECONDS", 0.01)
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", never_answers)

        assert await SystemHostResolver().resolves("jellyfin") is True
