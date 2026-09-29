"""套件內 qBittorrent / Prowlarr 的介面登入（M4 票 07、15）。

- **沿用 Jellyfin 帳密**（brief §16.3）：帳號是擁有者，密碼先向 Jellyfin 驗過才寫；
  驗不過兩台都不寫。
- **已經設過就不強迫再設**：重裝保留 config 的那一台，帳號認得出來就算有結論（brief §20.14）。
- **只存雜湊**（brief §19 2026-09-29 ⑤）：資料庫裡沒有介面密碼的明文。
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    InterfaceLoginRefusal,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import Setting, SetupSettings
from berth.services.indexer import apply_default_indexers, read_indexer_status
from berth.services.indexer import set_interface_login as set_prowlarr_login
from berth.services.jellyfin import InterfaceLoginRejectedError
from berth.services.qbittorrent import apply_qbittorrent, read_qbittorrent_diff
from berth.services.qbittorrent import set_interface_login as set_qbittorrent_login
from berth.services.settings import read_settings, write_settings
from berth.services.steps import InterfaceLogin, password_matches
from tests.integration.arrange import chosen, own
from tests.integration.factories import FakeClientFactory

OWNER_PASSWORD = "Harbour-owner-1"
REUSED = InterfaceLogin(username="", password=OWNER_PASSWORD, reuse_owner=True)
MISTYPED = InterfaceLogin(username="", password="not-it", reuse_owner=True)


async def bundled_pair(session: AsyncSession) -> None:
    """擁有者 skipper 成立，qBittorrent 與 Prowlarr 都選了套件內。"""
    await own(session)
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        ServiceKind.JELLYFIN: chosen(ServiceOrigin.BUNDLED, "http://jellyfin:8096"),
        ServiceKind.QBITTORRENT: chosen(ServiceOrigin.BUNDLED, "http://qbittorrent:8080"),
        ServiceKind.PROWLARR: chosen(ServiceOrigin.BUNDLED, "http://prowlarr:9696"),
    }
    await write_settings(session, setup)
    await session.commit()


def factory(
    *,
    qbittorrent: FakeQbittorrentClient | None = None,
    prowlarr: FakeProwlarrClient | None = None,
    jellyfin: FakeJellyfinClient | None = None,
) -> FakeClientFactory:
    return FakeClientFactory(
        jellyfin=jellyfin or FakeJellyfinClient(admin=("skipper", OWNER_PASSWORD)),
        qbittorrent=qbittorrent or FakeQbittorrentClient(),
        prowlarr=prowlarr or FakeProwlarrClient(),
    )


async def _no_sleep(_: float) -> None:
    return None


async def stored_settings(session: AsyncSession) -> str:
    rows = await session.scalars(select(Setting))
    return json.dumps([row.value_json for row in rows], ensure_ascii=False)


# --- 沿用 Jellyfin 帳密 ---


@pytest.mark.asyncio
async def test_reusing_the_jellyfin_login_sets_the_owners_pair_on_both(
    session: AsyncSession,
) -> None:
    await bundled_pair(session)
    qbittorrent, prowlarr = FakeQbittorrentClient(), FakeProwlarrClient()
    clients = factory(qbittorrent=qbittorrent, prowlarr=prowlarr)

    await apply_qbittorrent(session, clients, login=REUSED)
    await apply_default_indexers(session, clients, ["nyaasi"], login=REUSED, sleep=_no_sleep)

    await qbittorrent.login("skipper", OWNER_PASSWORD)
    assert prowlarr.signs_in("skipper", OWNER_PASSWORD)
    setup = await read_settings(session, SetupSettings)
    assert (setup.qbittorrent.web_ui_username, setup.indexer.web_ui_username) == (
        "skipper",
        "skipper",
    )


@pytest.mark.asyncio
async def test_a_mistyped_jellyfin_password_writes_neither(session: AsyncSession) -> None:
    await bundled_pair(session)
    qbittorrent, prowlarr = FakeQbittorrentClient(), FakeProwlarrClient()
    clients = factory(qbittorrent=qbittorrent, prowlarr=prowlarr)

    for attempt in (
        apply_qbittorrent(session, clients, login=MISTYPED),
        set_qbittorrent_login(session, clients, MISTYPED),
        apply_default_indexers(session, clients, ["nyaasi"], login=MISTYPED, sleep=_no_sleep),
        set_prowlarr_login(session, clients, MISTYPED, sleep=_no_sleep),
    ):
        with pytest.raises(InterfaceLoginRejectedError) as refused:
            await attempt
        assert refused.value.reason is InterfaceLoginRefusal.OWNER_PASSWORD

    assert qbittorrent.writes == []
    assert prowlarr.restarts == 0
    assert await prowlarr.indexers() == []
    setup = await read_settings(session, SetupSettings)
    assert (setup.qbittorrent.steps, setup.indexer.steps) == ([], [])


@pytest.mark.asyncio
async def test_an_unreachable_jellyfin_cannot_vouch_for_the_password(
    session: AsyncSession,
) -> None:
    await bundled_pair(session)
    qbittorrent = FakeQbittorrentClient()
    clients = factory(
        qbittorrent=qbittorrent,
        jellyfin=FakeJellyfinClient(error=ServiceUnavailableError("connection refused")),
    )

    with pytest.raises(InterfaceLoginRejectedError) as refused:
        await apply_qbittorrent(session, clients, login=REUSED)

    assert refused.value.reason is InterfaceLoginRefusal.JELLYFIN_UNREACHABLE
    assert "connection refused" in refused.value.detail
    assert qbittorrent.writes == []


# --- 只存雜湊 ---


@pytest.mark.asyncio
async def test_no_interface_password_is_stored_in_plain_text(session: AsyncSession) -> None:
    await bundled_pair(session)
    clients = factory()
    own_pair = InterfaceLogin(username="deck", password="Deck-pass-9")

    await apply_qbittorrent(session, clients, login=REUSED)
    await apply_default_indexers(session, clients, ["nyaasi"], login=own_pair, sleep=_no_sleep)

    stored = await stored_settings(session)
    assert OWNER_PASSWORD not in stored
    assert "Deck-pass-9" not in stored
    setup = await read_settings(session, SetupSettings)
    assert password_matches(OWNER_PASSWORD, setup.qbittorrent.web_ui_password_hash)
    assert password_matches("Deck-pass-9", setup.indexer.web_ui_password_hash)


@pytest.mark.asyncio
async def test_the_same_pair_again_is_already_in_place(session: AsyncSession) -> None:
    """雜湊夠比出「已經是這一組」：同一組再按一次不重寫（票 06c 的道理）。"""
    await bundled_pair(session)
    qbittorrent = FakeQbittorrentClient()
    clients = factory(qbittorrent=qbittorrent)
    pair = InterfaceLogin(username="deck", password="Deck-pass-9")
    await apply_qbittorrent(session, clients, login=pair)
    written = len(qbittorrent.writes)

    status = await apply_qbittorrent(session, clients, login=pair)

    assert len(qbittorrent.writes) == written
    step = next(row for row in status.steps if row.step == QbittorrentStep.PASSWORD.value)
    assert (step.status, step.detail) == (StepStatus.SKIPPED, "deck")


# --- 已經設過（重裝保留 config）---


@pytest.mark.asyncio
async def test_a_bundled_qbittorrent_that_already_has_a_login_is_not_forced(
    session: AsyncSession,
) -> None:
    await bundled_pair(session)
    qbittorrent = FakeQbittorrentClient(preferences={"web_ui_username": "keeper"})
    clients = factory(qbittorrent=qbittorrent)

    diff = await read_qbittorrent_diff(session, clients)
    status = await apply_qbittorrent(session, clients)

    assert diff.web_ui_username == "keeper"
    step = next(row for row in status.steps if row.step == QbittorrentStep.PASSWORD.value)
    assert (step.status, step.detail) == (StepStatus.SKIPPED, "keeper")
    assert all("web_ui_password" not in write for write in qbittorrent.writes)


@pytest.mark.asyncio
async def test_a_fresh_bundled_qbittorrent_still_asks_for_a_login(session: AsyncSession) -> None:
    """全新的那一台帳號是 `admin`、密碼沒設：必填，照舊停在頁 2（M4 票 07）。"""
    await bundled_pair(session)
    clients = factory()

    status = await apply_qbittorrent(session, clients)

    step = next(row for row in status.steps if row.step == QbittorrentStep.PASSWORD.value)
    assert step.status is StepStatus.PENDING
    assert status.web_ui_username == ""


@pytest.mark.asyncio
async def test_a_bundled_prowlarr_that_already_has_a_login_is_not_forced(
    session: AsyncSession,
) -> None:
    await bundled_pair(session)
    prowlarr = FakeProwlarrClient(
        host_config={"authenticationMethod": "forms", "username": "keeper", "password": "x"}
    )
    clients = factory(prowlarr=prowlarr)

    before = await read_indexer_status(session, clients)
    status = await apply_default_indexers(session, clients, ["nyaasi"], sleep=_no_sleep)

    assert before.web_ui_username == "keeper"
    step = next(row for row in status.steps if row.step == PROWLARR_LOGIN_STEP)
    assert (step.status, step.detail) == (StepStatus.SKIPPED, "keeper")
    assert prowlarr.restarts == 0


@pytest.mark.asyncio
async def test_a_fresh_bundled_prowlarr_still_asks_for_a_login(session: AsyncSession) -> None:
    await bundled_pair(session)
    clients = factory()

    status = await apply_default_indexers(session, clients, ["nyaasi"], sleep=_no_sleep)

    step = next(row for row in status.steps if row.step == PROWLARR_LOGIN_STEP)
    assert step.status is StepStatus.PENDING
