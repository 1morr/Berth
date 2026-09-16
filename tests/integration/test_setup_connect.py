"""既有服務的連線表單：存下連線資訊並真的測一次（plan §9.3 第 2 步、票 05 驗收）。"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import (
    AuthFailedError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.indexer import IndexerSearch
from berth.adapters.jellyfin import JellyfinClient
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.tmdb import TmdbClient
from berth.adapters.torrent import TorrentFetcher
from berth.adapters.torznab import TorznabClient
from berth.domain import DetectionReason, IndexerKind, ServiceKind, ServiceOrigin
from berth.models import IndexerSettings, JellyfinSettings, QbittorrentSettings
from berth.services.settings import read_settings
from berth.services.setup import ServiceConnection, connect_service, read_status


class FakeClientFactory:
    """記下被要求的位址，並回固定的替身。"""

    def __init__(
        self,
        *,
        jellyfin: FakeJellyfinClient | None = None,
        qbittorrent: FakeQbittorrentClient | None = None,
        prowlarr: FakeProwlarrClient | None = None,
    ) -> None:
        self._jellyfin = jellyfin or FakeJellyfinClient()
        self._qbittorrent = qbittorrent or FakeQbittorrentClient()
        self._prowlarr = prowlarr or FakeProwlarrClient()
        self.asked: list[tuple[str, str]] = []

    def jellyfin(self, base_url: str, token: str = "") -> JellyfinClient:
        self.asked.append(("jellyfin", base_url))
        return self._jellyfin

    def qbittorrent(self, base_url: str) -> QbittorrentClient:
        self.asked.append(("qbittorrent", base_url))
        return self._qbittorrent

    def prowlarr(self, base_url: str, api_key: str) -> ProwlarrClient:
        self.asked.append(("prowlarr", base_url))
        return self._prowlarr

    def tmdb(self, credential: str) -> TmdbClient:
        raise AssertionError("the connection form never talks to TMDB")

    def torrent(self) -> TorrentFetcher:
        raise AssertionError("the connection form never fetches a torrent")

    def torznab(self, base_url: str, api_key: str) -> TorznabClient:
        raise AssertionError("the connection form never talks to a Torznab endpoint")

    def indexer_search(self, kind: IndexerKind, base_url: str, api_key: str) -> IndexerSearch:
        raise AssertionError("the connection form never searches for releases")


def verdict(status: object, kind: ServiceKind) -> tuple[ServiceOrigin, DetectionReason]:
    row = next(r for r in status.services if r.kind is kind)  # type: ignore[attr-defined]
    return row.origin, row.reason


@pytest.mark.asyncio
async def test_an_existing_jellyfin_reports_its_version(session: AsyncSession) -> None:
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(
            base_url="http://nas:8096",
            server_name="nas",
            version="12.0.0",
            startup_wizard_completed=True,
        )
    )

    status = await connect_service(
        session,
        ServiceKind.JELLYFIN,
        ServiceConnection(base_url="http://nas:8096"),
        factory,
    )

    # 判定用的是服務自己報的事實（跑過初始精靈），不是「他填了表單所以算既有」。
    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.EXISTING,
        DetectionReason.SETUP_COMPLETED,
    )
    assert factory.asked == [("jellyfin", "http://nas:8096")]
    assert (await read_settings(session, JellyfinSettings)).base_url == "http://nas:8096"


@pytest.mark.asyncio
async def test_qbittorrent_credentials_are_verified_and_stored(session: AsyncSession) -> None:
    qbittorrent = FakeQbittorrentClient(base_url="http://nas:8080")
    factory = FakeClientFactory(qbittorrent=qbittorrent)

    status = await connect_service(
        session,
        ServiceKind.QBITTORRENT,
        ServiceConnection(base_url="http://nas:8080", username="admin", password="secret"),
        factory,
    )

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.EXISTING,
        DetectionReason.CONNECTED,
    )
    assert qbittorrent.logins == [("admin", "secret")]
    stored = await read_settings(session, QbittorrentSettings)
    assert (stored.base_url, stored.username, stored.password) == (
        "http://nas:8080",
        "admin",
        "secret",
    )


@pytest.mark.asyncio
async def test_a_password_free_qbittorrent_is_not_asked_to_log_in(session: AsyncSession) -> None:
    qbittorrent = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=qbittorrent)

    await connect_service(
        session,
        ServiceKind.QBITTORRENT,
        ServiceConnection(base_url="http://nas:8080"),
        factory,
    )

    assert qbittorrent.logins == []


@pytest.mark.asyncio
async def test_wrong_qbittorrent_credentials_report_auth_required(session: AsyncSession) -> None:
    factory = FakeClientFactory(
        qbittorrent=FakeQbittorrentClient(login_error=AuthFailedError("rejected"))
    )

    status = await connect_service(
        session,
        ServiceKind.QBITTORRENT,
        ServiceConnection(base_url="http://nas:8080", username="admin", password="wrong"),
        factory,
    )

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.EXISTING,
        DetectionReason.AUTH_REQUIRED,
    )


@pytest.mark.asyncio
async def test_a_hand_pasted_prowlarr_key_is_stored_and_used(session: AsyncSession) -> None:
    """讀不到掛載時的退路：貼上的 key 要真的存下來並生效（票 05 驗收）。"""
    factory = FakeClientFactory(
        prowlarr=FakeProwlarrClient(indexers=[ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True)])
    )

    status = await connect_service(
        session,
        ServiceKind.PROWLARR,
        ServiceConnection(base_url="http://prowlarr:9696", api_key="pasted"),
        factory,
    )

    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.EXISTING,
        DetectionReason.HAS_INDEXERS,
    )
    stored = await read_settings(session, IndexerSettings)
    assert (stored.kind, stored.base_url, stored.api_key) == (
        "prowlarr",
        "http://prowlarr:9696",
        "pasted",
    )


@pytest.mark.asyncio
async def test_a_bundled_prowlarr_stays_bundled_after_pasting_its_key(
    session: AsyncSession,
) -> None:
    """讀不到掛載的**套件內** Prowlarr，貼上 key 之後仍然是套件內。

    判定看的是服務自己的狀態（有沒有索引站），不是位址是誰填的。判成既有的話，
    票 08 的十個預設索引站對它就不會跑了。
    """
    status = await connect_service(
        session,
        ServiceKind.PROWLARR,
        ServiceConnection(base_url="http://prowlarr:9696", api_key="pasted"),
        FakeClientFactory(),
    )

    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.NO_INDEXERS,
    )


@pytest.mark.asyncio
async def test_prowlarr_without_a_pasted_key_still_asks_for_one(session: AsyncSession) -> None:
    status = await connect_service(
        session,
        ServiceKind.PROWLARR,
        ServiceConnection(base_url="http://prowlarr:9696"),
        FakeClientFactory(),
    )

    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.EXISTING,
        DetectionReason.API_KEY_MISSING,
    )


@pytest.mark.asyncio
async def test_a_failed_test_still_keeps_what_the_user_typed(session: AsyncSession) -> None:
    """測不過也要存：使用者改一個欄位再按一次，不該重打整份表單。"""
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(error=ServiceUnavailableError("refused"))
    )

    status = await connect_service(
        session,
        ServiceKind.JELLYFIN,
        ServiceConnection(base_url="http://typo:8096"),
        factory,
    )

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.EXISTING,
        DetectionReason.UNREACHABLE,
    )
    assert (await read_settings(session, JellyfinSettings)).base_url == "http://typo:8096"


@pytest.mark.asyncio
async def test_a_connected_service_is_not_reprobed_by_the_polling_loop(
    session: AsyncSession,
) -> None:
    """前端每 3 秒自動重探。重探不可以把使用者剛填好的連線判回「探不到」。"""
    from berth.services.clients import SetupProbes
    from berth.services.setup import detect_services

    absent = SetupProbes(
        jellyfin=FakeJellyfinClient(error=ServiceNotDeployedError("no such host")),
        qbittorrent=FakeQbittorrentClient(error=ServiceUnavailableError("still starting")),
        prowlarr=FakeProwlarrClient(),
        prowlarr_api_key="key",
    )
    nas = FakeClientFactory(
        jellyfin=FakeJellyfinClient(
            base_url="http://nas:8096",
            server_name="nas",
            version="12.0.0",
            startup_wizard_completed=True,
        )
    )
    await detect_services(session, absent)
    await connect_service(
        session,
        ServiceKind.JELLYFIN,
        ServiceConnection(base_url="http://nas:8096"),
        nas,
    )

    # qBittorrent 還在啟動，所以輪詢會再打一次 detect。
    status = await detect_services(session, absent)

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.EXISTING,
        DetectionReason.SETUP_COMPLETED,
    )
    jellyfin = next(r for r in status.services if r.kind is ServiceKind.JELLYFIN)
    assert jellyfin.base_url == "http://nas:8096"


@pytest.mark.asyncio
async def test_connecting_one_service_leaves_the_others_alone(session: AsyncSession) -> None:
    from berth.adapters.jellyfin.fake import FakeJellyfinClient as _Jellyfin
    from berth.services.clients import SetupProbes
    from berth.services.setup import detect_services

    await detect_services(
        session,
        SetupProbes(
            jellyfin=_Jellyfin(),
            qbittorrent=FakeQbittorrentClient(),
            prowlarr=FakeProwlarrClient(),
            prowlarr_api_key="key",
        ),
    )
    await connect_service(
        session,
        ServiceKind.JELLYFIN,
        ServiceConnection(base_url="http://nas:8096"),
        FakeClientFactory(),
    )

    status = await read_status(session)
    assert len(status.services) == 3
    assert verdict(status, ServiceKind.QBITTORRENT)[0] is ServiceOrigin.BUNDLED
