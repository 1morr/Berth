"""qBittorrent 那一側的探針（`adapters.qbittorrent.probe_sight`，M4 票 19，brief §20.2）。

這裡用一台**照劇本答話**的 qBittorrent：`torrents/info` 每被問一次就往下讀一行。整合測試的替身
一加進去就列得出來、一 recheck 就是結論，量不到真的那一台在時間上的樣子——2026-09-30 對 5.2.3
實跑時，`torrents/add` 回來之後那一個 torrent 還不在 `torrents/info` 裡，探針當場說它「不見了」，
而且 recheck 送在它出現之前會被靜默吃掉。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from berth.adapters import qbittorrent
from berth.adapters.qbittorrent import ProbeSight, TorrentStatus, probe_sight


def row(state: str, progress: float = 0.0) -> TorrentStatus:
    return TorrentStatus(
        hash="probe",
        name=".berth-probe-1",
        state=state,
        category="",
        tags=(),
        progress=progress,
        completion_on=0,
        last_activity=0,
        added_on=0,
        save_path="/data/torrent/complete/tv",
        content_path="",
        total_size=5,
    )


@dataclass
class Scripted:
    """`torrents/info` 照 `before` 答到 recheck 為止，之後照 `after`；讀完最後一行就一直是它。"""

    before: list[TorrentStatus | None]
    after: list[TorrentStatus | None]
    calls: list[str] = field(default_factory=list)
    rechecked: bool = False

    async def add_probe(self, name: str, payload: bytes, *, save_path: str) -> str:
        self.calls.append("add")
        return "probe"

    async def recheck(self, info_hash: str) -> None:
        self.calls.append("recheck")
        self.rechecked = True

    async def torrent(self, info_hash: str) -> TorrentStatus | None:
        self.calls.append("info")
        script = self.after if self.rechecked else self.before
        return script.pop(0) if len(script) > 1 else script[0]

    async def delete_torrent(self, info_hash: str, *, delete_files: bool) -> None:
        self.calls.append(f"delete(files={delete_files})")


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qbittorrent, "PROBE_POLL_SECONDS", 0.0)
    monkeypatch.setattr(qbittorrent, "PROBE_SETTLE_SECONDS", 0.05)
    monkeypatch.setattr(qbittorrent, "PROBE_TIMEOUT_SECONDS", 1.0)


async def sight(client: Scripted) -> ProbeSight:
    return await probe_sight(
        client,  # type: ignore[arg-type]  # 劇本只實作探針用得到的那幾支
        name=".berth-probe-1",
        payload=b"berth",
        save_path="/data/torrent/complete/tv",
    )


@pytest.mark.asyncio
async def test_a_probe_that_is_not_listed_yet_is_waited_for_and_rechecked_only_once_it_is() -> None:
    client = Scripted(
        before=[None, None, row("checkingResumeData"), row("stoppedDL")],
        after=[row("checkingUP"), row("stoppedUP", 1.0)],
    )

    assert await sight(client) is ProbeSight.SEEN
    first_listed = client.calls.index("recheck")
    assert client.calls[:first_listed] == ["add", "info", "info", "info", "info"]
    assert client.calls[-1] == "delete(files=False)"


@pytest.mark.asyncio
async def test_a_file_qbittorrent_cannot_see_stays_at_zero_and_is_unseen() -> None:
    client = Scripted(before=[row("stoppedDL")], after=[row("stoppedDL")])

    assert await sight(client) is ProbeSight.UNSEEN
    assert client.calls[-1] == "delete(files=False)"


@pytest.mark.asyncio
async def test_an_unreadable_file_is_its_own_answer() -> None:
    client = Scripted(before=[row("pausedDL")], after=[row("checkingDL"), row("error")])

    assert await sight(client) is ProbeSight.UNREADABLE


@pytest.mark.asyncio
async def test_a_probe_that_never_shows_up_is_unsettled_and_still_removed() -> None:
    client = Scripted(before=[None], after=[None])

    assert await sight(client) is ProbeSight.UNSETTLED
    assert "recheck" not in client.calls
    assert client.calls[-1] == "delete(files=False)"


@pytest.mark.asyncio
async def test_a_queue_of_other_checks_is_waited_out_not_read_as_unseen() -> None:
    """qBittorrent 一次只校驗一個 torrent：排隊的那一段不是答案。"""
    queued = [row("queuedForChecking")] * 5
    client = Scripted(before=[row("stoppedDL")], after=[*queued, row("stoppedUP", 1.0)])

    assert await sight(client) is ProbeSight.SEEN
