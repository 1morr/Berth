"""頁 2 測連線時就問 qBittorrent 看不看得到 `/data`（M4 票 46，審計 S3、P2-4）。

掛 `/downloads`、沒掛 `/data` 的 qBittorrent 原本在頁 2 是綠的，要到頁 3 的探針才紅。Berth 在共用
根目錄寫一個探測檔、請它停住校驗一次：探針**校驗不完**（`probe_torrent(unfinished=True)`），看得到的
那一台停在一半，不觸發「torrent 完成時執行外部程式」（brief §20.2）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import qbittorrent
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import ConnectionReason, ConnectionState, ServiceKind, ServiceOrigin
from berth.models import PathSettings
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_QBITTORRENT,
    STEP_ROUTES,
    ConnectionFailedError,
    ServiceConnection,
    ServiceView,
    SetupStatus,
    choose_service,
    retest_service,
)
from tests.integration.factories import FakeClientFactory
from tests.integration.test_setup_qbittorrent import BUNDLED, NOW, arrange


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    """看不到的那一面要等 state 穩定一段時間；替身一 recheck 就是結論，不必等滿 3 秒。"""
    monkeypatch.setattr(qbittorrent, "PROBE_SETTLE_SECONDS", 0.1)
    monkeypatch.setattr(qbittorrent, "PROBE_POLL_SECONDS", 0.01)


async def share(session: AsyncSession, roots: dict[str, Path]) -> Path:
    """Berth 的三層路徑指到 `roots`；回共用根目錄（compose 裡的 `/data`）。"""
    paths = await read_settings(session, PathSettings)
    paths.complete_root = str(roots["complete"])
    paths.incomplete_root = str(roots["incomplete"])
    paths.library_root = str(roots["library"])
    await write_settings(session, paths)
    await session.commit()
    return roots["library"].parent


def spy(client: FakeQbittorrentClient) -> list[dict[str, Any]]:
    """`add_probe` 每一次收到的參數。"""
    calls: list[dict[str, Any]] = []
    add_probe = client.add_probe

    async def recorded(name: str, payload: bytes, **kwargs: Any) -> str:
        calls.append({"name": name, "size": len(payload), **kwargs})
        return await add_probe(name, payload, **kwargs)

    client.add_probe = recorded  # type: ignore[method-assign]  # 只包一層記參數，行為照舊
    return calls


def qbittorrent_of(status: SetupStatus) -> ServiceView:
    return next(row for row in status.services if row.kind is ServiceKind.QBITTORRENT)


def leftovers(data: Path) -> list[Path]:
    return list(data.rglob(".berth-probe-*"))


@pytest.mark.asyncio
async def test_an_existing_qbittorrent_without_data_is_red_on_page_2_and_green_once_mounted(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """只掛 `/downloads` 的那一台：連得上、版本夠，但讀不到 Berth 寫進 `/data` 的檔——停在頁 2，理由
    是它看不到 `/data`。多掛一條之後同一顆「重新測試」就過。兩次都不留探針。"""
    await arrange(session, origin=ServiceOrigin.EXISTING, username="owner", password="s3cret")
    data = await share(session, roots)
    client = FakeQbittorrentClient(base_url="http://nas:8080", visible_roots=("/downloads",))
    calls = spy(client)
    factory = FakeClientFactory(qbittorrent=client)

    blind = await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)

    row = qbittorrent_of(blind)
    assert (row.state, row.reason, row.detail) == (
        ConnectionState.FAILED,
        ConnectionReason.DATA_UNSEEN,
        str(data),
    )
    assert "qBittorrent cannot see" in row.error
    assert blind.current_step == STEP_QBITTORRENT
    assert client.open_probes == {}
    assert leftovers(data) == []

    client.visible_roots = None
    mounted = await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)

    assert qbittorrent_of(mounted).state is ConnectionState.OK
    assert mounted.current_step == STEP_ROUTES
    assert client.open_probes == {}
    assert leftovers(data) == []
    # 校驗不完的那一種，放在共用根目錄：兩次都是。
    assert [(call["save_path"], call["unfinished"]) for call in calls] == [(str(data), True)] * 2
    assert client.writes == []


@pytest.mark.asyncio
async def test_an_existing_form_without_data_is_refused_and_nothing_is_saved(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """既有表單測過才存（M4 票 45）：看不到 `/data` 也是測不過，拒絕帶回那一次的結論。"""
    await arrange(session)
    data = await share(session, roots)
    client = FakeQbittorrentClient(base_url="http://nas:8080", visible_roots=("/downloads",))
    factory = FakeClientFactory(qbittorrent=client)

    with pytest.raises(ConnectionFailedError) as refused:
        await choose_service(
            session,
            factory,
            BUNDLED,
            ServiceKind.QBITTORRENT,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://nas:8080", username="owner", password="s3cret"),
            now=NOW,
        )

    assert refused.value.attempt.reason is ConnectionReason.DATA_UNSEEN
    assert client.open_probes == {}
    assert leftovers(data) == []


@pytest.mark.asyncio
async def test_a_bundled_qbittorrent_without_data_is_red_too(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """套件內那一台的 compose 一定掛 `/data`；被改掉時同一條，而且不是「還在啟動」那種等。"""
    await arrange(session)
    await share(session, roots)
    client = FakeQbittorrentClient(visible_roots=("/downloads",))
    factory = FakeClientFactory(qbittorrent=client)

    status = await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)

    row = qbittorrent_of(status)
    assert (row.state, row.reason) == (ConnectionState.FAILED, ConnectionReason.DATA_UNSEEN)


@pytest.mark.asyncio
async def test_without_its_own_data_berth_does_not_ask(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Berth 自己沒有共用根目錄（沒掛 `/data`）時不問：問了也分不出是誰少了掛載。頁 3 Berth 自己那一
    條會說（`directory_missing` / `berth_cannot_write`）。"""
    await arrange(session, origin=ServiceOrigin.EXISTING, username="owner", password="s3cret")
    gone = tmp_path / "gone"
    await share(
        session,
        {
            "complete": gone / "torrent" / "complete",
            "incomplete": gone / "i",
            "library": gone / "library",
        },
    )
    client = FakeQbittorrentClient(base_url="http://nas:8080", visible_roots=("/downloads",))
    factory = FakeClientFactory(qbittorrent=client)

    status = await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)

    assert qbittorrent_of(status).state is ConnectionState.OK
    assert client.probed == []


@pytest.mark.asyncio
async def test_without_a_shared_root_berth_does_not_ask(session: AsyncSession) -> None:
    """下載與媒體庫沒有共同父目錄（共同的是 `/`）時不問：探測檔會寫進 Berth 自己的 `/`，再問
    qBittorrent 它自己的 `/`，答案什麼都說明不了（同 `routes._under_shared_root`）。"""
    await arrange(session, origin=ServiceOrigin.EXISTING, username="owner", password="s3cret")
    paths = await read_settings(session, PathSettings)
    paths.complete_root = "/downloads/torrent/complete"
    paths.incomplete_root = "/downloads/torrent/incomplete"
    paths.library_root = "/media/library"
    await write_settings(session, paths)
    await session.commit()
    client = FakeQbittorrentClient(base_url="http://nas:8080")
    factory = FakeClientFactory(qbittorrent=client)

    status = await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)

    assert qbittorrent_of(status).state is ConnectionState.OK
    assert client.probed == []
