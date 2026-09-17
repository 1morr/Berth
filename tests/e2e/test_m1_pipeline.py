"""M1 的整條路徑（plan §10、§11.2 T1.8、brief §17）：只操作 Berth 的 API，外加下載這件事的替身。

前提是 `tests/e2e/compose.yml` 那一套已經起來（指令在 README〈e2e〉）。一次跑完整個模組：

1. 精靈八步——套件內的三個服務由 Berth 自己設定，TMDB 憑證讀環境變數 `TMDB_API_KEY`
2. 三筆送單：一部美劇一季、一部動漫一季、一部電影（`payload.PACKS`）；`.torrent` 由 Berth 自己去抓
3. **下載的替身**：問 qBittorrent 這一筆要下載到哪裡，把 staging 的檔案複製過去，再叫它 recheck
4. 等 Berth 自己走完 completed → planning → importing → imported，再等 Jellyfin 反查

斷言都拿外面的事實對 Berth 說的話：季集對語料、inode 在容器裡 `stat`、item id 在 Jellyfin 裡查。
套件內的媒體庫一開始是空的，所以反查要等 resolver 請 Jellyfin 掃描之後那一輪（`services/resolver.py`
的 `SCAN_AFTER_MISSES`），整個模組約 13 分鐘。

**Prowlarr 在跑但沒被測到**：精靈偵測得到它，第 5 步按「之後再說」，送單直接帶 `.torrent` 的網址。
索引站搜尋有自己的契約測試（`tests/integration/test_indexer_search.py`）。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from tests.conftest import FIXTURES
from tests.e2e.payload import PACKS, STAGING, Pack, info_name

pytestmark = pytest.mark.e2e

BERTH = "http://127.0.0.1:8383"
QBITTORRENT = "http://127.0.0.1:8080"
JELLYFIN = "http://127.0.0.1:8096"
#: compose 網路裡 `torrents` 那台的位址：抓 `.torrent` 的是 Berth 的容器，不是這個程序。
TORRENTS = "http://torrents:8000"
TORRENTS_CONTAINER = "berth-e2e-torrents"

ADMIN = "skipper"
#: 精靈第 1 步勾了「同一組帳密」，所以 Jellyfin 與 qBittorrent 也是這一組。
PASSWORD = "harbour-e2e"

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
#: 送單那兩筆記的是按下去的人；之後每一筆都該是 Berth 自己（`actor == "system"`）——
#: 重試、重新規劃都會以使用者的名義留在時間線上。
SUBMISSION_EVENTS = {"created", "submitted"}

#: 容器裡逐一 `stat` 參數裡的路徑，印出 `[[dev, ino, nlink], …]`。
STAT_EACH = (
    "import json, os, sys; "
    "print(json.dumps([(s.st_dev, s.st_ino, s.st_nlink) for s in map(os.stat, sys.argv[1:])]))"
)

JELLYFIN_CLIENT = 'MediaBrowser Client="Berth e2e", Device="ci", DeviceId="berth-e2e", Version="1"'

#: 時間線上一定依序出現的站（中間可以夾別的，例如 `preplan`、`progress`）。狀態欄位只看得到終點，
#: 這一串才說得出它真的走過完成 → 規劃 → 入庫 → 通知 Jellyfin（票 15 的 code-review）。
PATH = (
    "created",
    "submitted",
    "metadata_received",
    "completed",
    "plan_generated",
    "linked",
    "jellyfin_scan_requested",
)

#: 帳本逐檔的 Jellyfin item id。API 只給 `presence`（找到了沒），id 本身只在資料庫裡，
#: 所以直接在 berth 容器裡讀——拿它對 Jellyfin 在那條路徑上的 item，才證明得了「反查得到 item id」。
LEDGER_ITEM_IDS = (
    "import json, sqlite3; "
    "rows = sqlite3.connect('/config/berth.db').execute("
    "\"select target_path, jellyfin_item_id from ledger where action = 'import'\").fetchall(); "
    "print(json.dumps(dict(rows)))"
)

#: 外部服務回的 JSON。形狀由每一條斷言自己檢查，型別層寫死它只會是第二份不會被驗的 schema。
type Json = Any


@dataclass(frozen=True, slots=True)
class Submitted:
    pack: Pack
    media: str
    info_hash: str
    #: `(season, episode)`；電影是 `(None, None)`。語料寫下的每一個正片。
    episodes: Counter[tuple[int | None, int | None]]
    #: 語料裡要入庫的正片，相對 torrent 的根。
    imports: tuple[str, ...]

    @property
    def tmdb_id(self) -> str:
        return self.media.split(":")[1]


def _corpus(pack: Pack) -> dict[str, Json]:
    data: dict[str, Json] = json.loads(
        (FIXTURES / "parser" / pack.fixture).read_text(encoding="utf-8")
    )
    return data


def _wait[T](what: str, seconds: float, probe: Callable[[], T | None], *, every: float = 5) -> T:
    deadline = time.monotonic() + seconds
    while True:
        value = probe()
        if value is not None:
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out after {seconds:.0f}s waiting for {what}")
        time.sleep(every)


def _ok(response: httpx.Response) -> Json:
    assert response.is_success, (
        f"{response.request.method} {response.url}: {response.status_code} {response.text[:600]}"
    )
    return response.json() if response.content else None


def _in_container(*command: str, container: str = TORRENTS_CONTAINER) -> str:
    """預設在 `torrents` 容器裡跑：它掛著同一個 /data，而且是 uid 1000。"""
    result = subprocess.run(
        ["docker", "exec", container, *command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, f"{command}: {result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def berth() -> Iterator[httpx.Client]:
    # 門禁要求非 GET 帶這個標頭（`api/gate.py` 的 CSRF 那一條）。
    with httpx.Client(
        base_url=f"{BERTH}/api", headers={"X-Requested-With": "berth-e2e"}, timeout=120
    ) as client:
        _wait("Berth", 180, lambda: _healthy(client))
        yield client


def _imports(berth: httpx.Client, job: Submitted) -> list[Json]:
    """這一筆 Job 寫進帳本的正片（Media 詳情的「檔案與版本」）。"""
    media = _ok(berth.get(f"/media/{job.media}"))
    return [
        row
        for row in media["files"]
        if row["job_hash"] == job.info_hash and row["action"] == "import"
    ]


def _healthy(client: httpx.Client) -> bool | None:
    try:
        return True if client.get("/health").is_success else None
    except httpx.TransportError:
        return None


@pytest.fixture(scope="module")
def configured(berth: httpx.Client) -> None:
    """精靈八步，順序照 `api/setup.py`。"""
    tmdb_key = os.environ.get("TMDB_API_KEY", "").strip()
    assert tmdb_key, "set TMDB_API_KEY: step 6 of the wizard is a gate (ticket 02b)"

    _ok(berth.post("/setup/admin", json={"username": ADMIN, "password": PASSWORD}))

    def detected() -> bool | None:
        status = _ok(berth.post("/setup/detect", json={"restart": False}))
        services = status["services"]
        if any(row["origin"] == "timeout" for row in services):
            _ok(berth.post("/setup/detect", json={"restart": True}))
        return True if services and all(row["resolved"] for row in services) else None

    _wait("the three bundled services to be detected", 300, detected)

    jellyfin = _ok(berth.post("/setup/jellyfin/bootstrap", timeout=1200))
    failed = [row for row in jellyfin["steps"] if row["status"] == "failed"]
    assert not failed, failed

    _ok(berth.post("/setup/qbittorrent/apply"))
    _ok(berth.post("/setup/indexers/skip", json={"skipped": True}))
    tmdb = _ok(berth.post("/setup/tmdb/test", json={"api_key": tmdb_key}))
    assert tmdb["verified"], tmdb["steps"]

    routes = _ok(berth.post("/setup/routes", json={}, timeout=300))
    assert routes["ready"], [(row["slug"], row["checks"]) for row in routes["routes"]]
    _ok(berth.post("/setup/complete"))
    _ok(berth.post("/auth/login", json={"username": ADMIN, "password": PASSWORD}))


@pytest.fixture(scope="module")
def submitted(berth: httpx.Client, configured: None) -> tuple[Submitted, ...]:
    out = []
    for pack in PACKS:
        corpus = _corpus(pack)
        media_id = corpus["context"]["media"]
        media = _ok(berth.get(f"/media/{media_id}"))
        route = next(row for row in media["routes"] if row["slug"] == pack.route_slug)
        created = _ok(
            berth.post(
                "/jobs",
                json={
                    "source": {
                        "url": f"{TORRENTS}/{pack.route_slug}.torrent",
                        "title": corpus["torrent_name"],
                        "info_hash": "",
                    },
                    "media": media_id,
                    "route": route["id"],
                },
            )
        )
        assert created["job"]["state"] == "submitted", created["job"]
        imports = [row for row in corpus["expected"] if row["action"] == "import"]
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


@pytest.fixture(scope="module")
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
                rows: list[Json] = _ok(qbittorrent.get(info))
                return rows[0] if rows else None

            row = _wait(f"qBittorrent to list {job.pack.route_slug}", 120, listed)
            where = row.get("download_path") or row["save_path"]
            source = STAGING / job.pack.route_slug / info_name(_corpus(job.pack)["torrent_name"])
            _in_container("sh", "-c", 'mkdir -p "$1" && cp -r "$2" "$1/"', "sh", where, str(source))
            _ok(qbittorrent.post("/api/v2/torrents/recheck", data={"hashes": job.info_hash}))


@pytest.fixture(scope="module")
def jobs(berth: httpx.Client, submitted: tuple[Submitted, ...], planted: None) -> dict[str, Json]:
    wanted = {job.info_hash for job in submitted}

    def settled() -> dict[str, Json] | None:
        rows = {row["hash"]: row for row in _ok(berth.get("/jobs")) if row["hash"] in wanted}
        done = len(rows) == len(wanted) and all(row["state"] in SETTLED for row in rows.values())
        return rows if done else None

    return _wait("the three jobs to settle", 900, settled)


@pytest.fixture(scope="module")
def resolved(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> dict[str, Json]:
    """每一個正片都被 Jellyfin 反查到（`presence == found`）之後的 Media 詳情。"""

    def found() -> dict[str, Json] | None:
        details = {job.media: _ok(berth.get(f"/media/{job.media}")) for job in submitted}
        imports = [
            row for media in details.values() for row in media["files"] if row["action"] == "import"
        ]
        pending = [row for row in imports if row["presence"] != "found"]
        assert not [row for row in pending if row["presence"] == "lost"], pending
        return details if imports and not pending else None

    return _wait("Jellyfin to resolve every import", 1500, found, every=15)


@pytest.fixture(scope="module")
def jellyfin() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=JELLYFIN, timeout=60) as client:
        auth = _ok(
            client.post(
                "/Users/AuthenticateByName",
                json={"Username": ADMIN, "Pw": PASSWORD},
                headers={"Authorization": JELLYFIN_CLIENT},
            )
        )
        client.headers["Authorization"] = f'{JELLYFIN_CLIENT}, Token="{auth["AccessToken"]}"'
        yield client


def test_every_release_is_imported_without_a_human(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> None:
    for job in submitted:
        events = _ok(berth.get(f"/jobs/{job.info_hash}/events"))
        types = [row["type"] for row in events]
        assert jobs[job.info_hash]["state"] == "imported", (job.pack.route_slug, types)
        remaining = iter(types)
        assert all(station in remaining for station in PATH), (job.pack.route_slug, types)
        by_hand = [
            (row["type"], row["actor"])
            for row in events
            if row["type"] not in SUBMISSION_EVENTS and row["actor"] != "system"
        ]
        assert not by_hand, by_hand
        assert "review_required" not in types, types


def test_the_ledger_holds_every_episode_the_corpus_imports(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> None:
    """季集對語料（benchmark 驗過的那一份正解），不對集名：集名來自活的 TMDB，會被編輯。"""
    for job in submitted:
        imports = _imports(berth, job)
        got = Counter((row["season"], row["episode_start"]) for row in imports)
        assert got == job.episodes, job.pack.route_slug
        assert all(f"[tmdbid-{job.tmdb_id}]/" in row["target_path"] for row in imports)


def test_imports_are_hard_links_of_the_downloaded_files(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> None:
    """在容器裡 `stat` 兩端：同一個 device 與 inode，而且至少兩個鏈接。"""
    for job in submitted:
        root = jobs[job.info_hash]["content_path"]
        sources = [f"{root}/{path}" for path in job.imports]
        targets = [row["target_path"] for row in _imports(berth, job)]
        stats = json.loads(
            _in_container(
                "python",
                "-c",
                STAT_EACH,
                *sources,
                *targets,
            )
        )
        source_stats, target_stats = stats[: len(sources)], stats[len(sources) :]
        assert all(links >= 2 for _, _, links in stats), stats
        assert sorted((dev, ino) for dev, ino, _ in source_stats) == sorted(
            (dev, ino) for dev, ino, _ in target_stats
        ), job.pack.route_slug


def test_jellyfin_holds_every_import_where_berth_says(
    berth: httpx.Client,
    submitted: tuple[Submitted, ...],
    resolved: dict[str, Json],
    jellyfin: httpx.Client,
) -> None:
    """帳本逐檔記下的 item id 就是 Jellyfin 自己在那條路徑上的 item，季集也是它認的；
    媒體庫卡片深連結的 Series / Movie 也是 Jellyfin 以 TMDB id 認出來的那一個。"""
    items = _ok(
        jellyfin.get(
            "/Items",
            params={
                "recursive": "true",
                "includeItemTypes": "Series,Episode,Movie",
                "fields": "Path,ProviderIds,MediaSources",
            },
        )
    )["Items"]
    by_path = {source["Path"]: item for item in items for source in item.get("MediaSources") or []}
    ledger: dict[str, str] = json.loads(
        _in_container("python", "-c", LEDGER_ITEM_IDS, container="berth")
    )
    for job in submitted:
        for row in resolved[job.media]["files"]:
            if row["action"] != "import":
                continue
            item = by_path.get(row["target_path"])
            assert item is not None, row["target_path"]
            assert ledger[row["target_path"]] == item["Id"], row["target_path"]
            if item["Type"] == "Episode":
                assert (item["ParentIndexNumber"], item["IndexNumber"]) == (
                    row["season"],
                    row["episode_start"],
                ), row["target_path"]

    cards = {
        card["media_id"]: card
        for pack in PACKS
        for card in _ok(berth.get(f"/inventory/{pack.route_slug}"))["items"]
    }
    for job in submitted:
        kind = "Movie" if job.media.startswith("movie:") else "Series"
        owners = [
            item["Id"]
            for item in items
            if item["Type"] == kind and (item.get("ProviderIds") or {}).get("Tmdb") == job.tmdb_id
        ]
        assert cards[job.media]["jellyfin_item_id"] in owners, (job.media, owners)
        print(f"{job.media}: Jellyfin {kind} {cards[job.media]['jellyfin_item_id']}")
