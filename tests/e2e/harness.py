"""e2e 兩個模組共用的位址、等待與「在容器裡問一句」。

fixture 在 `conftest.py`；這裡只有不需要 fixture 的那些。宿主上跑，可以用 Berth 的相依。
"""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from tests.conftest import FIXTURES
from tests.e2e.payload import Pack
from tests.e2e.stack import E2E_ENV

#: 宿主上的 port 是 e2e 自己的那一組（`e2e.env`，M4 票 34），與試跑環境的不撞。
BERTH = f"http://127.0.0.1:{E2E_ENV['BERTH_PORT']}"
QBITTORRENT = f"http://127.0.0.1:{E2E_ENV['QBITTORRENT_WEBUI_PORT']}"
JELLYFIN = f"http://127.0.0.1:{E2E_ENV['JELLYFIN_PORT']}"
#: compose 網路裡 `torrents` 那台的位址：抓 `.torrent` 的是 Berth 的容器，不是這個程序。
TORRENTS = "http://torrents:8000"
#: 容器名是 `compose.yml` 換過的那一組（`berth-e2e-*`，M4 票 34）：產品那一份的 `berth-*` 留給
#: 同一台機器上的試跑環境。
BERTH_CONTAINER = "berth-e2e"
JELLYFIN_CONTAINER = "berth-e2e-jellyfin"
QBITTORRENT_CONTAINER = "berth-e2e-qbittorrent"
TORRENTS_CONTAINER = "berth-e2e-torrents"

ADMIN = "skipper"
#: 擁有者的 Jellyfin 密碼（精靈第 1 步）。qBittorrent 的 WebUI 登入是另一組（`WEB_UI_LOGIN`）。
PASSWORD = "harbour-e2e"

JELLYFIN_CLIENT = 'MediaBrowser Client="Berth e2e", Device="ci", DeviceId="berth-e2e", Version="1"'

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


def imports_of(berth: httpx.Client, job: Submitted) -> list[Json]:
    """這一筆 Job 寫進帳本的正片（Media 詳情的「檔案與版本」）。"""
    media = ok(berth.get(f"/media/{job.media}"))
    return [
        row
        for row in media["files"]
        if row["job_hash"] == job.info_hash and row["action"] == "import"
    ]


def corpus(pack: Pack) -> dict[str, Json]:
    data: dict[str, Json] = json.loads(
        (FIXTURES / "parser" / pack.fixture).read_text(encoding="utf-8")
    )
    return data


def wait[T](what: str, seconds: float, probe: Callable[[], T | None], *, every: float = 5) -> T:
    deadline = time.monotonic() + seconds
    while True:
        value = probe()
        if value is not None:
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out after {seconds:.0f}s waiting for {what}")
        time.sleep(every)


def ok(response: httpx.Response) -> Json:
    assert response.is_success, (
        f"{response.request.method} {response.url}: {response.status_code} {response.text[:600]}"
    )
    return response.json() if response.content else None


def all_jobs(berth: httpx.Client) -> list[Json]:
    """下載列表上的每一筆，不分篩選、翻完每一頁（`GET /jobs` 一頁有上限，M4 票 04）。"""
    rows: list[Json] = []
    page = 1
    while True:
        answer = ok(berth.get("/jobs", params={"filter": "all", "page": page}))
        rows += answer["jobs"]
        if page * answer["page_size"] >= answer["total"]:
            return rows
        page += 1


def docker(*command: str) -> str:
    """對 compose 起的容器下一句 docker（`stop` / `start`）。"""
    result = subprocess.run(
        ["docker", *command], capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert result.returncode == 0, f"{command}: {result.stderr}"
    return result.stdout


#: 精靈頁 2 之後，測試在 qBittorrent 的 WebUI 把全域的預設儲存路徑改到這裡（M4 票 32）。它在 /data
#: 底下、寫得進去，只是沒有任何一條 Route 用它：Berth 送的每一筆都走分類自己的路徑。
GLOBAL_SAVE_PATH = "/data/not-berth"

#: 精靈頁 2 替套件內 qBittorrent 設的 WebUI 登入（M4 票 07：泊位上必填，帳號預填擁有者）。
WEB_UI_LOGIN = {"username": ADMIN, "password": "harbour-webui"}


def qbittorrent_webui() -> httpx.Client:
    """以 WebUI 登入套件內的 qBittorrent，測試才看得到、改得到它的 torrent 與偏好。

    用的是精靈頁 2 在泊位上設的那一組（M4 票 07）——這也順便驗了「泊位上設的帳密之後能登入
    qBittorrent WebUI」。同 `jellyfin_client`，收尾要 `closing()`。
    """
    client = httpx.Client(base_url=QBITTORRENT, headers={"Referer": QBITTORRENT})
    login = client.post("/api/v2/auth/login", data=WEB_UI_LOGIN)
    # 成功的形狀隨版本不同（4.4 是 `200 Ok.`、5.x 是 `204`，brief §20.7），失敗是 `Fails.`。
    assert login.is_success and login.text != "Fails.", (login.status_code, login.text)
    return client


def in_container(*command: str, container: str = TORRENTS_CONTAINER) -> str:
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


#: 容器裡逐一 `stat` 參數裡的路徑，印出 `[[dev, ino, nlink], …]`。
_STAT_EACH = (
    "import json, os, sys; "
    "print(json.dumps([(s.st_dev, s.st_ino, s.st_nlink) for s in map(os.stat, sys.argv[1:])]))"
)

#: 帳本裡一筆 Job 的正片。API 不給來源路徑與 item id（畫面用不到），所以直接在 berth 容器裡讀。
_LEDGER_OF = (
    "import json, sqlite3, sys; "
    "db = sqlite3.connect('/config/berth.db'); db.row_factory = sqlite3.Row; "
    'rows = db.execute("select id, target_path, source_abs_path, jellyfin_item_id from ledger '
    "where action = 'import' and job_hash = ? order by target_path\", sys.argv[1:]).fetchall(); "
    "print(json.dumps([dict(row) for row in rows]))"
)


def stat_each(*paths: str) -> list[tuple[int, int, int]]:
    """在 `torrents` 容器裡 `stat`：`(device, inode, 鏈接數)`，順序同參數。"""
    rows: list[list[int]] = json.loads(in_container("python", "-c", _STAT_EACH, *paths))
    return [(dev, ino, links) for dev, ino, links in rows]


def same_file(first: str, second: str) -> bool:
    """同一個 device 上的同一個 inode：硬鏈接，不是複製。"""
    (dev_a, ino_a, _), (dev_b, ino_b, _) = stat_each(first, second)
    return (dev_a, ino_a) == (dev_b, ino_b)


def exists(path: str) -> bool:
    """在 `torrents` 容器裡看那條路徑在不在（檔案或目錄都算）。"""
    return (
        in_container("sh", "-c", 'test -e "$1" && echo yes || echo no', "sh", path).strip() == "yes"
    )


def ledger_of(job_hash: str) -> list[Json]:
    """這一筆 Job 在帳本上的正片：`id`、`target_path`、`source_abs_path`、`jellyfin_item_id`。"""
    rows: list[Json] = json.loads(
        in_container("python", "-c", _LEDGER_OF, job_hash, container=BERTH_CONTAINER)
    )
    return rows


def jellyfin_client(username: str, password: str) -> httpx.Client:
    """以這個帳號自己的 token 問 Jellyfin。API key 代讀只套一部分權限（brief §20.8），所以
    「這個人看不看得到」一律拿他自己的 token 問。

    登入那一下已經把 client 開起來了，所以收尾要 `closing()`——`with` 會被 httpx 當成
    「同一個 client 開第二次」擋下來。
    """
    client = httpx.Client(base_url=JELLYFIN, timeout=60)
    auth = ok(
        client.post(
            "/Users/AuthenticateByName",
            json={"Username": username, "Pw": password},
            headers={"Authorization": JELLYFIN_CLIENT},
        )
    )
    client.headers["Authorization"] = f'{JELLYFIN_CLIENT}, Token="{auth["AccessToken"]}"'
    return client


def berth_client() -> httpx.Client:
    # 門禁要求非 GET 帶這個標頭（`api/gate.py` 的 CSRF 那一條）。
    return httpx.Client(
        base_url=f"{BERTH}/api", headers={"X-Requested-With": "berth-e2e"}, timeout=120
    )
