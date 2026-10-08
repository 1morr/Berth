"""e2e 的共用 fixture：**一次 compose、一次精靈、一次入庫**，三個測試模組共享。

所以全部是 `scope="session"`：`test_1_m1_pipeline.py` 走完 M1 的整條路徑（約 13 分鐘），
`test_2_m15_library.py` 接著拿那三部作品當媒體庫裡的東西，驗 M1.5 的權限與瀏覽，
`test_3_m2_repair.py` 最後把它們弄壞再修好。**檔名的數字就是執行順序**（pytest 照檔名收集）：
M2 那一組會拆掉、換掉媒體庫裡的檔案，所以排在只讀它們的 M1.5 之後；M1.5 最後一條把 Jellyfin
停掉再起來，等它回來才結束。

前提是 `tests/e2e/compose.yml` 那一套已經起來（指令在 docs/development.md〈e2e〉）。
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import closing

import httpx
import pytest

from berth.models import DEFAULT_BUNDLED_LIBRARIES
from tests.e2e.harness import (
    ADMIN,
    BERTH_CONTAINER,
    GLOBAL_SAVE_PATH,
    PASSWORD,
    QBITTORRENT_CONTAINER,
    TORRENTS,
    TORRENTS_CONTAINER,
    WEB_UI_LOGIN,
    Json,
    Submitted,
    all_jobs,
    berth_client,
    corpus,
    docker,
    in_container,
    jellyfin_client,
    ok,
    qbittorrent_webui,
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
        # 每秒問一次：冷啟動閘門（`configured`）要在外部服務起來之前就開始精靈。
        wait("Berth", 180, lambda: _healthy(client), every=1)
        yield client


@pytest.fixture(scope="session")
def configured(berth: httpx.Client) -> None:
    """精靈六頁，順序照 `api/setup.py`。

    **三個服務頁都選套件內，是冷啟動閘門**（票 06h）：compose 不加 `--wait`，Berth 一回應就開始
    精靈，這時 Jellyfin 與 Prowlarr 還在啟動（Jellyfin 會回 503、會回不像它自己的東西，票 06g）。
    選了之後照常每 2 秒重測到連上，**不按「重新測試」**（`restart` 一律是 false）——使用者也不必按。
    第一輪就全部連上的話，代表這一輪沒有碰到啟動中的那幾秒，閘門等於沒守，所以那樣也算失敗。

    M4 票 15 起不偵測：來源由使用者選（`POST /setup/services/{kind}`），選了才測。頁 1 是擁有者：以
    `ADMIN` 建立套件內 Jellyfin 的管理員並拿到 Berth 的 session；之後的精靈都帶著那張 cookie。
    """
    tmdb_key = os.environ.get("TMDB_API_KEY", "").strip()
    assert tmdb_key, "set TMDB_API_KEY: the TMDB page of the wizard is a gate (ticket 02b)"

    started = time.monotonic()
    rounds: list[list[Json]] = []

    def connected(kind: str) -> Callable[[], bool | None]:
        def probe() -> bool | None:
            services: list[Json] = ok(
                berth.post(f"/setup/services/{kind}/test", json={"restart": False})
            )["services"]
            rounds.append(services)
            states = ", ".join(
                f"{row['kind']}={row['origin']}/{row['state']}/{row['reason']}" for row in services
            )
            print(f"test +{time.monotonic() - started:5.1f}s {states}")
            (row,) = [row for row in services if row["kind"] == kind]
            assert row["state"] in ("ok", "waiting"), row
            return True if row["state"] == "ok" else None

        return probe

    def choose_bundled(kind: str) -> None:
        ok(berth.post(f"/setup/services/{kind}", json={"origin": "bundled"}))
        wait(f"the bundled {kind} to answer", 300, connected(kind), every=2)

    choose_bundled("jellyfin")
    # 畫面上測過的那一台原樣帶回（M4 票 28）。
    (seen,) = [row for row in rounds[-1] if row["kind"] == "jellyfin"]
    target = {"base_url": seen["base_url"], "server_id": seen["server_id"]}
    owner = ok(berth.post("/setup/owner", json={**target, "username": ADMIN, "password": PASSWORD}))
    assert (owner["owner"], owner["current_step"]) == (ADMIN, 2), owner
    # 擁有者那一刻拿到的就是 Berth 的 session，而且是管理員（brief §11）。
    assert ok(berth.get("/auth/me")) == {"name": ADMIN, "role": "admin"}
    choose_bundled("qbittorrent")
    choose_bundled("prowlarr")
    assert len(rounds) > 3, ("services were already up: the cold start was not exercised", rounds)

    jellyfin = ok(berth.post("/setup/jellyfin/bootstrap", timeout=1200))
    failed = [row for row in jellyfin["steps"] if row["status"] == "failed"]
    assert not failed, failed

    _secure_qbittorrent(berth)
    _move_the_global_save_path()
    _prowlarr_as_existing(berth)
    choose_bundled("prowlarr")
    # 從既有換回套件內是換了一台：既有那一台的「之後再說」不跟過來（M4 票 39）。
    assert ok(berth.get("/setup/indexers"))["skipped"] is False
    ok(berth.post("/setup/indexers/skip", json={"skipped": True}))
    tmdb = ok(berth.post("/setup/tmdb/test", json={"api_key": tmdb_key}))
    assert tmdb["verified"], tmdb["steps"]

    routes = ok(berth.post("/setup/routes", json={}, timeout=300))
    assert routes["ready"], [(row["slug"], row["checks"]) for row in routes["routes"]]
    _complete_in_page_order(berth)
    # 同一組帳密就是之後登入 Berth 的那一組（Jellyfin 認的帳號），不是另一組 Berth 自己的。
    signed = ok(berth.post("/auth/login", json={"username": ADMIN, "password": PASSWORD}))
    assert signed == {"name": ADMIN, "role": "admin"}, signed


def _secure_qbittorrent(berth: httpx.Client) -> None:
    """頁 2：套件內那一台測試通過還不夠，介面登入設好才往下（M4 票 38）。

    先送一組 qBittorrent 5.2 起不收的密碼（M4 票 26）：被拒的那一組要停在頁 2、說得出是 qBittorrent
    拒絕的（`login_rejected`），帳號不算設好；合規的那一組之後就是 `qbittorrent_webui` 登入 WebUI
    用的。

    之後換成「既有」再換回套件內：Berth 忘了它設過的登入（換一台就重做那一頁），像重裝保留
    qBittorrent 的 config 那樣。兩次都只靠連線測試就做完——既有的那一台沒有確認鍵，套件內的那一台
    在測試時讀到它自己的登入，不必再按一次套用（審計 S5-06）。
    """
    assert ok(berth.get("/setup/status"))["current_step"] == 2
    short = {**WEB_UI_LOGIN, "password": WEB_UI_LOGIN["password"][:5]}
    refused = ok(berth.post("/setup/qbittorrent/apply", json={"login": short}))
    (row,) = [row for row in refused["steps"] if row["step"] == "web_ui_password"]
    assert (row["status"], row["failure"]) == ("failed", "login_rejected"), row
    assert ok(berth.get("/setup/status"))["current_step"] == 2

    applied = ok(berth.post("/setup/qbittorrent/apply", json={"login": WEB_UI_LOGIN}))
    assert applied["web_ui_username"] == ADMIN, applied["steps"]
    status = ok(berth.get("/setup/status"))
    assert status["current_step"] == 3, status
    (bundled,) = [row for row in status["services"] if row["kind"] == "qbittorrent"]

    existing = ok(
        berth.post(
            "/setup/services/qbittorrent",
            json={"origin": "existing", "base_url": bundled["base_url"], **WEB_UI_LOGIN},
        )
    )
    assert existing["current_step"] == 3, existing
    again = ok(berth.post("/setup/services/qbittorrent", json={"origin": "bundled"}))
    assert again["current_step"] == 3, again
    read = ok(berth.get("/setup/qbittorrent/diff"))
    assert [(row["step"], row["status"]) for row in read["steps"]] == [
        ("web_ui_password", "skipped")
    ], read["steps"]
    assert read["web_ui_username"] == ADMIN, read


def _prowlarr_as_existing(berth: httpx.Client) -> None:
    """頁 4 選「既有」：與頁 1、2 同一支 `POST /setup/services/prowlarr`（M4 票 39）。

    拿套件內那一台的位址當作使用者自己的：key 錯是 `auth_required`（不是連不上），而且測不過不存
    （M4 票 45：400 `connection_failed`，結論在 `attempt`）；帶對的 key 連上。對的 key 從 berth 唯讀
    掛載的 `config.xml` 讀——使用者是從 Prowlarr 的「設定 → 一般」抄。最後按「之後再說」，換回套件內
    時看它有沒有被清掉（呼叫端）。
    """
    status = ok(berth.get("/setup/status"))
    (bundled,) = [row for row in status["services"] if row["kind"] == "prowlarr"]

    def existing(api_key: str) -> httpx.Response:
        return berth.post(
            "/setup/services/prowlarr",
            json={"origin": "existing", "base_url": bundled["base_url"], "api_key": api_key},
        )

    rejected = existing("0" * 32)
    assert rejected.status_code == 400, rejected.text
    refusal = rejected.json()["detail"]
    attempt = refusal["attempt"]
    assert (refusal["reason"], attempt["origin"], attempt["state"], attempt["reason"]) == (
        "connection_failed",
        "existing",
        "failed",
        "auth_required",
    ), refusal
    config = in_container("cat", "/ext/prowlarr/config.xml", container=BERTH_CONTAINER)
    found = re.search(r"<ApiKey>(\w+)</ApiKey>", config)
    assert found, config
    (accepted,) = [
        row for row in ok(existing(found.group(1)))["services"] if row["kind"] == "prowlarr"
    ]
    assert (accepted["state"], accepted["reason"]) == ("ok", "connected"), accepted
    ok(berth.post("/setup/indexers/skip", json={"skipped": True}))


def _move_the_global_save_path() -> None:
    """使用者在 WebUI 把全域的預設儲存路徑改到別處（M4 票 32）。

    Berth 不再寫、也不再看 qBittorrent 的全域偏好：之後建 Route、送單、入庫都照常
    （`test_1_m1_pipeline.py` 驗它沒被改回來、下載也沒落在那裡）。
    """
    with closing(qbittorrent_webui()) as qbittorrent:
        moved = json.dumps({"save_path": GLOBAL_SAVE_PATH})
        ok(qbittorrent.post("/api/v2/app/setPreferences", data={"json": moved}))
        assert ok(qbittorrent.get("/api/v2/app/preferences"))["save_path"] == GLOBAL_SAVE_PATH


def _complete_in_page_order(berth: httpx.Client) -> None:
    """完成時照頁序把每一頁再問一次（M4 票 31）：停在完成頁的這時，頁 2 與頁 4 都被弄壞了。

    qBittorrent 停了、重新測試紅了（頁 2，M4 票 25）；另一個分頁收回了「之後再說」（頁 4）。
    完成先被送回頁 2，頁 2 好了再被送回頁 4，兩頁都好了才寫得下去。
    """

    def refused_at(page: int) -> None:
        refused = berth.post("/setup/complete")
        assert refused.status_code == 422, (refused.status_code, refused.text)
        assert f"page {page}" in refused.json()["detail"], refused.json()
        assert ok(berth.get("/health"))["setup_completed"] is False

    def qbittorrent_tests(*, green: bool) -> Callable[[], bool | None]:
        def probe() -> bool | None:
            services: list[Json] = ok(
                berth.post("/setup/services/qbittorrent/test", json={"restart": False})
            )["services"]
            (row,) = [row for row in services if row["kind"] == "qbittorrent"]
            return True if (row["state"] == "ok") == green else None

        return probe

    docker("stop", QBITTORRENT_CONTAINER)
    try:
        wait("the stopped qBittorrent to test red", 60, qbittorrent_tests(green=False), every=2)
        ok(berth.post("/setup/indexers/skip", json={"skipped": False}))
        refused_at(2)
    finally:
        docker("start", QBITTORRENT_CONTAINER)
    wait("qBittorrent to test green again", 180, qbittorrent_tests(green=True), every=2)
    refused_at(4)

    ok(berth.post("/setup/indexers/skip", json={"skipped": True}))
    ok(berth.post("/setup/complete"))


@pytest.fixture(scope="session")
def submitted(berth: httpx.Client, configured: None) -> tuple[Submitted, ...]:
    # 送單時 Berth 去 `torrents` 那台抓 `.torrent`。compose 不再等它（冷啟動閘門），這裡等。
    def payload_ready() -> bool | None:
        health = docker("inspect", "--format", "{{.State.Health.Status}}", TORRENTS_CONTAINER)
        return True if health.strip() == "healthy" else None

    wait("the torrents payload", 300, payload_ready)
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
    with closing(qbittorrent_webui()) as qbittorrent:
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
        rows = {row["hash"]: row for row in all_jobs(berth) if row["hash"] in wanted}
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

    `DEFAULT_BUNDLED_LIBRARIES` 是同一份對照的來源（資料夾就是 Route 的 slug），這裡只把名稱
    換成 Jellyfin 真的發出來的 id。
    """
    folders = ok(jellyfin.get("/Library/VirtualFolders"))
    by_name = {row["Name"]: row["ItemId"] for row in folders}
    found = {bundled.folder: by_name.get(bundled.name, "") for bundled in DEFAULT_BUNDLED_LIBRARIES}
    assert all(found.values()), (found, sorted(by_name))
    return found
