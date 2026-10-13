"""頁 1 成為擁有者之後就問既有 Jellyfin 看不看得到 `/data`（M4 票 63，審計 C7、P1-7）。

qBittorrent 沒掛 `/data` 在頁 2 就知道（M4 票 46），Jellyfin 原本要到頁 3「建立並檢查」才知道，多繞
一輪。問法沿用頁 3（`jellyfin._add_berth_path`）：在共用根目錄寫一個探測檔，以
`Environment/ValidatePath` 問它——那一支要管理員的憑證，所以要等擁有者成立、Berth 拿到自己的 key。
套件內那一台不問：compose 掛著 `/data`。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.domain import ConnectionReason, ConnectionState, ServiceKind, ServiceOrigin
from berth.services.setup import (
    STEP_QBITTORRENT,
    ConnectionFailedError,
    ServiceConnection,
    ServiceView,
    SetupStatus,
    choose_service,
    claim_owner,
    read_status,
    retest_service,
)
from tests.integration.factories import FakeClientFactory
from tests.integration.test_setup_api import BUNDLED
from tests.integration.test_setup_owner import JELLYFIN_URL, NOW, PASSWORD, SEEN, existing, found
from tests.integration.test_setup_qbittorrent_data import leftovers, share


def jellyfin_of(status: SetupStatus) -> ServiceView:
    return next(row for row in status.services if row.kind is ServiceKind.JELLYFIN)


async def owned_without_data(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[FakeClientFactory, Path, SetupStatus]:
    """既有 Jellyfin 只掛了 `/movies`、`/tv`：登入成為擁有者那一刻的狀態。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    data = await share(session, roots)
    factory = existing()
    factory.jellyfin_.visible_roots = ("/movies", "/tv")
    claimed = await claim_owner(
        session, factory, target=SEEN, username="captain", password=PASSWORD
    )
    return factory, data, claimed.status


@pytest.mark.asyncio
async def test_an_existing_jellyfin_without_data_is_red_on_page_1_right_after_the_owner(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """擁有者照樣成立（帳密與 key 都對了），但頁 1 那一條轉紅、說它看不到 `/data`；探測檔收掉。"""
    factory, data, status = await owned_without_data(session, roots)

    row = jellyfin_of(status)
    assert (row.state, row.reason, row.detail) == (
        ConnectionState.FAILED,
        ConnectionReason.DATA_UNSEEN,
        str(data),
    )
    assert "Jellyfin cannot see" in row.error
    assert status.owner == "captain"
    # 不擋頁 2：擁有者是頁 1 的事；頁 3 照舊擋（加不上 Berth 路徑）。
    assert status.current_step == STEP_QBITTORRENT
    assert [Path(path).parent for path in factory.jellyfin_.paths_validated] == [data]
    assert leftovers(data) == []


@pytest.mark.asyncio
async def test_once_mounted_the_same_retest_turns_page_1_green(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    factory, data, _ = await owned_without_data(session, roots)
    factory.jellyfin_.visible_roots = None

    mounted = await retest_service(session, factory, BUNDLED, ServiceKind.JELLYFIN, now=NOW)

    row = jellyfin_of(mounted)
    assert (row.state, row.reason) == (ConnectionState.OK, ConnectionReason.SETUP_COMPLETED)
    assert len(factory.jellyfin_.paths_validated) == 2
    assert leftovers(data) == []


@pytest.mark.asyncio
async def test_saving_the_address_again_is_refused_while_it_cannot_see_data(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """既有表單測過才存（M4 票 45）：看不到 `/data` 也是測不過，表單上帶著同一個結論與補法。"""
    factory, _, _ = await owned_without_data(session, roots)

    with pytest.raises(ConnectionFailedError) as refused:
        await choose_service(
            session,
            factory,
            BUNDLED,
            ServiceKind.JELLYFIN,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url=JELLYFIN_URL),
            now=NOW,
        )

    assert refused.value.attempt.reason is ConnectionReason.DATA_UNSEEN


@pytest.mark.asyncio
async def test_a_jellyfin_that_sees_data_stays_green(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    data = await share(session, roots)
    factory = existing()

    claimed = await claim_owner(
        session, factory, target=SEEN, username="captain", password=PASSWORD
    )

    assert jellyfin_of(claimed.status).state is ConnectionState.OK
    assert [Path(path).parent for path in factory.jellyfin_.paths_validated] == [data]
    assert leftovers(data) == []


@pytest.mark.asyncio
async def test_nothing_is_asked_before_the_owner_or_of_the_bundled_jellyfin(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """還沒有擁有者時 Berth 沒有 key，`ValidatePath` 問不了；套件內那一台由 compose 掛 `/data`。"""
    await share(session, roots)
    blind = FakeJellyfinClient(
        base_url=JELLYFIN_URL,
        startup_wizard_completed=True,
        admin=("captain", PASSWORD),
        visible_roots=("/movies",),
    )
    factory = FakeClientFactory(jellyfin=blind)

    chosen = await choose_service(
        session,
        factory,
        BUNDLED,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url=JELLYFIN_URL),
        now=NOW,
    )
    assert jellyfin_of(chosen).state is ConnectionState.OK

    await found(session, origin=ServiceOrigin.BUNDLED)
    bundled = FakeJellyfinClient(startup_wizard_completed=False, visible_roots=("/movies",))
    factory = FakeClientFactory(jellyfin=bundled)
    claimed = await claim_owner(session, factory, target=SEEN, username="skipper", password="x1")

    assert jellyfin_of(claimed.status).state is ConnectionState.OK
    assert blind.paths_validated == bundled.paths_validated == []
    assert (await read_status(session)).owner == "skipper"


@pytest.mark.asyncio
async def test_a_probe_berth_cannot_write_does_not_break_the_claim(
    session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """擁有者成立、session 發了之後才問：探測檔寫到一半失敗（磁碟滿、權限在途中變了）不讓頁 1 的回應
    壞掉。那是 Berth 自己這一邊的事，頁 3 Berth 那一條會說（code-review）。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    await share(session, roots)
    factory = existing()
    factory.jellyfin_.visible_roots = ("/movies",)

    def full_disk(*args: object, **kwargs: object) -> object:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("berth.services.setup.probe_file", full_disk)

    claimed = await claim_owner(
        session, factory, target=SEEN, username="captain", password=PASSWORD
    )

    assert claimed.signed_in.user.name == "captain"
    assert jellyfin_of(claimed.status).state is ConnectionState.OK
    assert factory.jellyfin_.paths_validated == []
