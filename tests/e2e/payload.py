"""e2e 的「索引站」與「下載」替身：語料的檔案清單 → 真的小影片 + 從那些位元組算出來的 `.torrent`。

在 compose 的 `torrents` 容器裡跑（`tests/e2e/compose.yml`）：

1. 在 `/data/e2e/staging/<slug>/<info_name>/` 建出三包發佈的整棵檔案樹。檔案清單取自 benchmark
   語料（`tests/fixtures/parser/`），影片是 `tests/fixtures/e2e/` 的種子加上檔名當尾巴——逐檔
   內容不同，硬鏈接對到誰一眼看得出來。
2. 由那些位元組算出 `.torrent`，寫進 `/data/e2e/torrents/<slug>.torrent`。
3. 用 http.server 送那個目錄。Berth 送單時自己來抓（票 09），這台就是索引站的下載連結。

沒有 peer 可以真的下載，所以位元組是測試在送單之後從 staging 複製到 qBittorrent 說的下載路徑、
再叫它 recheck（`test_1_m1_pipeline.py`）。plan §10 原本寫的 `seedMode` 是 qBittorrent Web API
2.16 起才有、而且要由送單的一方帶——那是 Berth，不是測試。

**只用標準庫**：容器是 `python:3.13-alpine`，沒有 Berth 也沒有測試相依。宿主上的測試 import
這一支只為了 `PACKS` 與 `info_name()`，兩邊才不會各算一份。
"""

from __future__ import annotations

import hashlib
import http.server
import json
import re
import shutil
from dataclasses import dataclass
from functools import partial
from pathlib import Path, PurePosixPath

#: 容器內的掛載點（`tests/e2e/compose.yml`）。POSIX 路徑：宿主上的測試拿 `STAGING` 組
#: `docker exec` 的參數，在 Windows 上 `Path` 會把它寫成反斜線。
FIXTURES = PurePosixPath("/fixtures")
WORK = PurePosixPath("/data/e2e")
STAGING = WORK / "staging"
TORRENTS = WORK / "torrents"
PORT = 8000

PIECE_LENGTH = 1 << 18
VIDEO_SUFFIXES = (".mkv", ".mp4")
#: 不是影片的檔案（`.txt`、`.jpg`）只要存在：分類器看副檔名，它們一律略過。
FILLER = b"berth e2e\n"
#: 沒有 tracker 會回應；qBittorrent 收 torrent 時只要這一欄的形狀對。
ANNOUNCE = "http://127.0.0.1:1/announce"
#: torrent 的根目錄名會真的變成資料夾，而發佈名裡可能有 `/`（芙莉蓮那一包）。
_UNSAFE = re.compile(r'[<>:"/\\|?*]')


@dataclass(frozen=True, slots=True)
class Pack:
    """一包發佈：語料裡的哪一筆、送進哪一條 Route。"""

    #: `tests/fixtures/parser/` 底下的相對路徑。
    fixture: str
    #: 套件內 Jellyfin 的三條 Route 之一（plan §9.3 第 7 步）。也是 `.torrent` 的檔名。
    route_slug: str


#: brief §17 的 M1 驗收：一部美劇一季、一部動漫一季、一部電影。
PACKS = (
    Pack("tv/the-bear-s03-successfulcrab.json", "tv"),
    Pack("anime/frieren-7acg-bd-batch.json", "anime"),
    Pack("movie/oppenheimer-yts.json", "movies"),
)


def info_name(release: str) -> str:
    """torrent 的 `name`：發佈名換掉檔案系統不收的字元。"""
    return _UNSAFE.sub("-", release)


def bencode(value: object) -> bytes:
    if isinstance(value, int):
        return f"i{value}e".encode()
    if isinstance(value, bytes):
        return f"{len(value)}:".encode() + value
    if isinstance(value, str):
        return bencode(value.encode())
    if isinstance(value, list):
        return b"l" + b"".join(bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        items = sorted((str(key).encode(), item) for key, item in value.items())
        return b"d" + b"".join(bencode(key) + bencode(item) for key, item in items) + b"e"
    raise TypeError(f"cannot bencode {type(value).__name__}")


def build(fixtures: Path, staging: Path, torrents: Path) -> None:
    shutil.rmtree(staging, ignore_errors=True)
    torrents.mkdir(parents=True, exist_ok=True)
    seeds = {suffix: (fixtures / "e2e" / f"seed{suffix}").read_bytes() for suffix in VIDEO_SUFFIXES}
    for pack in PACKS:
        spec = json.loads((fixtures / "parser" / pack.fixture).read_text(encoding="utf-8"))
        name = info_name(spec["torrent_name"])
        files: list[tuple[str, bytes]] = []
        for row in spec["files"]:
            path: str = row["path"]
            head = seeds.get(Path(path).suffix.lower(), FILLER)
            content = head + path.encode()
            target = staging / pack.route_slug / name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            files.append((path, content))

        joined = b"".join(content for _, content in files)
        pieces = b"".join(
            hashlib.sha1(joined[offset : offset + PIECE_LENGTH]).digest()
            for offset in range(0, len(joined), PIECE_LENGTH)
        )
        info = {
            "name": name,
            "piece length": PIECE_LENGTH,
            "pieces": pieces,
            "files": [{"length": len(content), "path": path.split("/")} for path, content in files],
        }
        (torrents / f"{pack.route_slug}.torrent").write_bytes(
            bencode({"announce": ANNOUNCE, "info": info})
        )
        digest = hashlib.sha1(bencode(info)).hexdigest()
        print(f"{pack.route_slug}: {len(files)} files, {len(joined)} bytes, {digest}", flush=True)


def serve(directory: Path) -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    http.server.ThreadingHTTPServer(("", PORT), handler).serve_forever()


if __name__ == "__main__":
    build(Path(FIXTURES), Path(STAGING), Path(TORRENTS))
    serve(Path(TORRENTS))
