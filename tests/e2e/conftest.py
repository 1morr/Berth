"""e2e 的共用 fixture：**一次 compose、一次精靈、一次入庫**，兩個測試模組共享。

所以全部是 `scope="session"`：`test_1_m1_pipeline.py` 走完 M1 的整條路徑（約 13 分鐘），
`test_2_m15_library.py` 接著拿那三部作品當媒體庫裡的東西，驗 M1.5 的權限與瀏覽。**檔名的數字就是
執行順序**（pytest 照檔名收集）：M1.5 最後一條會把 Jellyfin 停掉再起來，它要是全場最後一條。

前提是 `tests/e2e/compose.yml` 那一套已經起來（指令在 README〈e2e〉）。
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator
from contextlib import closing

import httpx
import pytest

from berth.services.jellyfin import BUNDLED_LIBRARIES
from tests.e2e.harness import (
    ADMIN,
    PASSWORD,
    QBITTORRENT,
    TORRENTS,
    Json,
    Submitted,
    berth_client,
    corpus,
    in_container,
    jellyfin_client,
    ok,
    wait,
)
from tests.e2e.payload import PACKS, STAGING, info_name

#: Job 停下來、不會再自己動的狀態。`imported` 以外的都是失敗。
SETTLED = {
    "imported",
    "import_failed",
    "review",
    "submit_failed",
    "missing_files",
    "client_error",
    "client_removed",
}


def _healthy(client: httpx.Client) -> bool | None:
    try:
        return True if client.get("/health").is_success else None
    except httpx.TransportError:
        return None


@pytest.fixture(scope="session")
def berth() -> Iterator[httpx.Client]:
    with berth_client() as client:
        wait("Berth", 180, lambda: _healthy(client))
        yield client


@pytest.fixture(scope="session")
def configured(berth: httpx.Client) -> None:
    """精靈八步，順序照 `api/setup.py`。"""
    tmdb_key = os.environ.get("TMDB_API_KEY", "").strip()
    assert tmdb_key, "set TMDB_API_KEY: step 6 of the wizard is a gate (ticket 02b)"

    ok(berth.post("/setup/admin", json={"username": ADMIN, "password": PASSWORD}))

    def detected() -> bool | None:
        status = ok(berth.post("/setup/detect", json={"restart": False}))
        services = status["services"]
        if any(row["origin"] == "timeout" for row in services):
            ok(berth.post("/setup/detect", json={"restart": True}))
        return True if services and all(row["resolved"] for row in services) else None

    wait("the three bundled services to be detected", 300, detected)

    jellyfin = ok(berth.post("/setup/jellyfin/bootstrap", timeout=1200))
    failed = [row for row in jellyfin["steps"] if row["status"] == "failed"]
    assert not failed, failed

    ok(berth.post("/setup/qbittorrent/apply"))
    ok(berth.post("/setup/indexers/skip", json={"skipped": True}))
    tmdb = ok(berth.post("/setup/tmdb/test", json={"api_key": tmdb_key}))
    assert tmdb["verified"], tmdb["steps"]

    routes = ok(berth.post("/setup/routes", json={}, timeout=300))
    assert routes["ready"], [(row["slug"], row["checks"]) for row in routes["routes"]]
    ok(berth.post("/setup/complete"))
    ok(berth.post("/auth/login", json={"username": ADMIN, "password": PASSWORD}))


@pytest.fixture(scope="session")
def submitted(berth: httpx.Client, configured: None) -> tuple[Submitted, ...]:
    out = []
    for pack in PACKS:
        spec = corpus(pack)
        media_id = spec["context"]["media"]
        media = ok(berth.get(f"/media/{media_id}"))
        route = next(row for row in media["routes"] if row["slug"] == pack.route_slug)
        created = ok(
            berth.post(
                "/jobs",
                json={
                    "source": {
                        "url": f"{TORRENTS}/{pack.route_slug}.torrent",
                        "title": spec["torrent_name"],
                        "info_hash": "",
                    },
                    "media": media_id,
                    "route": route["id"],
                },
            )
        )
        assert created["job"]["state"] == "submitted", created["job"]
        imports = [row for row in spec["expected"] if row["action"] == "import"]
        out.append(
            Submitted(
                pack=pack,
                media=media_id,
                info_hash=created["job"]["hash"],
                episodes=Counter((row["season"], row["episode"]) for row in imports),
                imports=tuple(row["path"] for row in imports),
            )
        )
    return tuple(out)


@pytest.fixture(scope="session")
def planted(submitted: tuple[Submitted, ...]) -> None:
    """位元組到了：複製進 qBittorrent 的下載路徑，再叫它 recheck。"""
    with httpx.Client(base_url=QBITTORRENT, headers={"Referer": QBITTORRENT}) as qbittorrent:
        login = qbittorrent.post(
            "/api/v2/auth/login", data={"username": ADMIN, "password": PASSWORD}
        )
        # 成功的形狀隨版本不同（4.4 是 `200 Ok.`、5.x 是 `204`，brief §20.7），失敗是 `Fails.`。
        assert login.is_success and login.text != "Fails.", (login.status_code, login.text)
        for job in submitted:
            info = f"/api/v2/torrents/info?hashes={job.info_hash}"

            def listed(info: str = info) -> Json | None:
                rows: list[Json] = ok(qbittorrent.get(info))
                return rows[0] if rows else None

            row = wait(f"qBittorrent to list {job.pack.route_slug}", 120, listed)
            where = row.get("download_path") or row["save_path"]
            source = STAGING / job.pack.route_slug / info_name(corpus(job.pack)["torrent_name"])
            in_container("sh", "-c", 'mkdir -p "$1" && cp -r "$2" "$1/"', "sh", where, str(source))
            ok(qbittorrent.post("/api/v2/torrents/recheck", data={"hashes": job.info_hash}))


@pytest.fixture(scope="session")
def jobs(berth: httpx.Client, submitted: tuple[Submitted, ...], planted: None) -> dict[str, Json]:
    wanted = {job.info_hash for job in submitted}

    def settled() -> dict[str, Json] | None:
        rows = {row["hash"]: row for row in ok(berth.get("/jobs")) if row["hash"] in wanted}
        done = len(rows) == len(wanted) and all(row["state"] in SETTLED for row in rows.values())
        return rows if done else None

    return wait("the three jobs to settle", 900, settled)


@pytest.fixture(scope="session")
def resolved(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> dict[str, Json]:
    """每一個正片都被 Jellyfin 反查到（`presence == found`）之後的 Media 詳情。"""

    def found() -> dict[str, Json] | None:
        details = {job.media: ok(berth.get(f"/media/{job.media}")) for job in submitted}
        imports = [
            row for media in details.values() for row in media["files"] if row["action"] == "import"
        ]
        pending = [row for row in imports if row["presence"] != "found"]
        assert not [row for row in pending if row["presence"] == "lost"], pending
        return details if imports and not pending else None

    return wait("Jellyfin to resolve every import", 1500, found, every=15)


@pytest.fixture(scope="session")
def jellyfin(configured: None) -> Iterator[httpx.Client]:
    """管理員自己的 token。建帳號、改權限、叫掃描都走它。

    相依 `configured`：這個帳號是精靈第 1 步建的，在那之前登入是 401。
    """
    with closing(jellyfin_client(ADMIN, PASSWORD)) as client:
        yield client


@pytest.fixture(scope="session")
def libraries(jellyfin: httpx.Client, configured: None) -> dict[str, str]:
    """精靈建的三個媒體庫：Route 的 slug → Jellyfin 的媒體庫 id。

    `BUNDLED_LIBRARIES` 是同一份對照的來源，這裡只把名稱換成 Jellyfin 真的發出來的 id。
    """
    folders = ok(jellyfin.get("/Library/VirtualFolders"))
    by_name = {row["Name"]: row["ItemId"] for row in folders}
    found = {bundled.slug: by_name.get(bundled.name, "") for bundled in BUNDLED_LIBRARIES}
    assert all(found.values()), (found, sorted(by_name))
    return found
