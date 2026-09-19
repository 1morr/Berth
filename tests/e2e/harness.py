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

BERTH = "http://127.0.0.1:8383"
QBITTORRENT = "http://127.0.0.1:8080"
JELLYFIN = "http://127.0.0.1:8096"
#: compose 網路裡 `torrents` 那台的位址：抓 `.torrent` 的是 Berth 的容器，不是這個程序。
TORRENTS = "http://torrents:8000"
TORRENTS_CONTAINER = "berth-e2e-torrents"
#: `jellyfin` / `qbittorrent` / `berth` 的 `container_name` 兩份 compose 相同：e2e 那一份只換
#: 專案名，另外加了 `torrents` 這台與自己的 volume。
JELLYFIN_CONTAINER = "jellyfin"

ADMIN = "skipper"
#: 精靈第 1 步勾了「同一組帳密」，所以 Jellyfin 與 qBittorrent 也是這一組。
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


def docker(*command: str) -> str:
    """對 compose 起的容器下一句 docker（`stop` / `start`）。"""
    result = subprocess.run(
        ["docker", *command], capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert result.returncode == 0, f"{command}: {result.stderr}"
    return result.stdout


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
