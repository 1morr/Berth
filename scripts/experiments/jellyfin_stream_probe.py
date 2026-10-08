"""M4 票 55：入庫的那一部片，Jellyfin 認不認得、播不播得到（Unraid 上 mover 前後各問一次）。

在 `berth` 容器裡跑，用 Berth 自己存的 Jellyfin API key（`settings` 表的 `services.jellyfin`），
key 不印出。只讀：問一次 `/Items` 與一次帶 `Range` 的 `/Videos/{id}/stream`。

    ssh root@tower 'docker exec -i berth python - <jellyfin item id>' \\
        < scripts/experiments/jellyfin_stream_probe.py

只用標準庫：berth image 裡就跑得起來，不必另外裝東西。
"""

from __future__ import annotations

import json
import sqlite3
import sys
import urllib.request
from typing import Any

BASE = "http://jellyfin:8096"
DATABASE = "file:/config/berth.db?mode=ro"
#: 只要前 1 MiB：證明讀得到檔案，不必整部傳完。
FIRST_MIB = "bytes=0-1048575"


def _api_key(value: Any) -> str | None:
    """`services.jellyfin` 的 JSON 裡第一個非空的 `api_key`。"""
    if isinstance(value, dict):
        for name, inner in value.items():
            if name == "api_key" and isinstance(inner, str) and inner:
                return inner
            found = _api_key(inner)
            if found:
                return found
    return None


def _request(key: str, path: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    token = {"Authorization": f'MediaBrowser Token="{key}"'}
    request = urllib.request.Request(BASE + path, headers={**token, **(headers or {})})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.read()


def main(item: str) -> None:
    connection = sqlite3.connect(DATABASE, uri=True)
    (stored,) = connection.execute(
        "select value_json from settings where key = 'services.jellyfin'"
    ).fetchone()
    key = _api_key(json.loads(stored))
    if key is None:
        raise SystemExit("Berth 沒有存 Jellyfin 的 API key")

    _, body = _request(
        key, f"/Items?Ids={item}&Fields=Path,MediaSources,ProviderIds&Recursive=true"
    )
    found = json.loads(body)["Items"][0]
    source = found["MediaSources"][0]
    minutes = round(source.get("RunTimeTicks", 0) / 6e8, 1)
    print("name:", found["Name"], found.get("ProductionYear"))
    print("tmdb:", found.get("ProviderIds", {}).get("Tmdb"))
    print("path:", found.get("Path"))
    print("container:", source.get("Container"), "size:", source.get("Size"), "minutes:", minutes)

    status, chunk = _request(key, f"/Videos/{item}/stream?static=true", {"Range": FIRST_MIB})
    print("stream:", status, len(chunk), "bytes")


if __name__ == "__main__":
    main(sys.argv[1])
