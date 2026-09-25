"""e2e 的公開 RSS 站替身（M3 票 21）：冒充 `mikanani.me` 與 `acg.rip`，照「第幾輪」送出 feed、
單集頁、番組頁與 `.torrent`。

公開站不能進 CI，所以 compose 把這兩個主機名（外加 `nyaa.si`）指到這一台（network aliases），
以 `tests/fixtures/e2e/tls/` 那張測試 CA 簽的憑證講 HTTPS——Berth 的番組頁與單一字幕組 feed
網址寫死 `https://mikanani.me/`。Berth 怎麼信這張 CA 見 `tests/e2e/compose.yml` 的 `ca-bundle`。

**發佈是票 07 錄下來的那幾份 fixture 裡的**（標題、發佈時間、字幕組、番組與字幕組 id），只換掉
下載連結與 info hash：位元組是這裡造的（`payload.py` 的種子影片，片長 24 分鐘），hash 從位元組
算。三部作品、兩輪：

- 《与你相恋到生命尽头》（Mikan 番組 4009，TMDB 285574）：聚合 feed 第一輪帶喵萌奶茶屋&LoliHouse
  的第 3、4 集，綁定時補舊集由單一字幕組 feed 補上第 1、2 集；第二輪同組第 5 集與它的 v2、另一組
  （北宇治字幕组）的第 5 集。
- 《上伊那牡丹，醉姿如百合》（TMDB 283905）：acg.rip 搜尋，第一輪綠茶字幕组第 11 集與千夏字幕组的
  整季合集，第二輪第 12 集。
- 《Re：从零开始的异世界生活》（TMDB 65942：**整部只有一季、85 集**，第二季後半從 E39、
  2021-01-06 起）：acg.rip 搜尋，LoliHouse 把那一個 cour 從 01 重數、四集。**這一部是合成的**：
  票 07 的 fixture 沒有 split-cour，標題照同一組的格式寫、發佈時間是每一集播出的隔天。TMDB 只有
  一季時純集號是 medium 的 S01E01，播出日比對才擋得到它；有好幾季的作品（例如 SPY×FAMILY）在那
  之前就因為信心低進審核了。

輪次住在 `ROUND` 這個檔案裡（沒有就是第 1 輪）：測試寫它，這一台每個請求讀一次。

**只用標準庫**（同 `payload.py`）：容器是 `python:3.13-alpine`。宿主上的測試 import 這一支只為了
常量與 `RELEASES`。
"""

from __future__ import annotations

import hashlib
import http.server
import json
import shutil
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape

try:
    from tests.e2e.payload import (
        ANNOUNCE,
        FIXTURES,
        PIECE_LENGTH,
        WORK,
        bencode,
        info_name,
        lasting,
        wait_for_berth,
    )
except ModuleNotFoundError:  # 容器裡：`python /e2e/sites.py`，/e2e 在 sys.path 上。
    from payload import (  # type: ignore[import-not-found, no-redef]  # 同一支檔案，另一種路徑
        ANNOUNCE,
        FIXTURES,
        PIECE_LENGTH,
        WORK,
        bencode,
        info_name,
        lasting,
        wait_for_berth,
    )

M3 = WORK / "m3"
STAGING = M3 / "staging"
#: 測試寫、這一台讀：現在是第幾輪。
ROUND = M3 / "round"
#: info hash → 那一包在 `STAGING` 底下的檔名與發佈名。測試照它把位元組放進 qBittorrent。
INDEX = M3 / "index.json"
#: 位元組與索引都寫好了才建：healthcheck 看它。
READY = M3 / "ready"
PORT = 443

#: 動畫一集。TMDB 上前兩部每一集是 24 或 25 分鐘，片長驗證（M3 票 15）的容忍是 216 秒；
#: Re:ZERO 那幾集是 28–30 分鐘（`Release.seconds`）。
EPISODE_SECONDS = 24 * 60
#: Mikan 的發佈時間不帶時區、是 UTC+8（brief §20.11）；acg.rip 寫 `-0700`。
MIKAN_TZ = timezone(timedelta(hours=8))
ACGRIP_TZ = timezone(timedelta(hours=-7))

AGGREGATE = "/RSS/MyBangumi"
#: 聚合 feed 的網址。token 是假的：替身不看它。
AGGREGATE_URL = f"https://mikanani.me{AGGREGATE}?token=berth-e2e"
#: acg.rip 搜尋 feed 的網址（`adapters/rss/acgrip.search_url` 的形狀）。
REZERO_URL = "https://acg.rip/.xml?term=Re+Zero"

KIMI = "tv:285574"
KAMIINA = "tv:283905"
REZERO = "tv:65942"
KIMI_BANGUMI = 4009
#: 票 07 的 fixture 裡喵萌奶茶屋&LoliHouse 的字幕組 id。
LOLIHOUSE = 370
#: 北宇治字幕组：fixture 沒錄到它在這一部的 id，這是替身自己的。
KITAUJI = 1230


@dataclass(frozen=True, slots=True)
class Release:
    title: str
    #: aware 的發佈時間。
    published: datetime
    #: 從第幾輪起出現在 feed 上。
    round: int
    #: `mikan` 或 `acgrip`。
    site: str
    #: Mikan：（番組, 字幕組）。聚合 feed 與那一組的單一 feed 都列它，`aggregate` 為假時只在後者。
    mikan: tuple[int, int] | None = None
    aggregate: bool = True
    #: acg.rip：那一筆的頁面 id，與列在哪一個搜尋 feed（`rezero` 或 `kamiina`）。
    page: int = 0
    search: str = ""
    seconds: int = EPISODE_SECONDS

    @property
    def file_name(self) -> str:
        return info_name(self.title) + ".mkv"


def _mikan(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=MIKAN_TZ)


def _acgrip(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=ACGRIP_TZ)


def _kimi(group: str, episode: str) -> str:
    if group == "kitauji":
        return (
            "[北宇治字幕组] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai "
            f"[{episode}][WebRip][HEVC_AAC][简繁日内封]"
        )
    return (
        "[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - "
        f"{episode} [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]"
    )


def _rezero(episode: int) -> str:
    return (
        "[LoliHouse] Re：从零开始的异世界生活 / Re Zero kara Hajimeru Isekai Seikatsu - "
        f"{episode:02d} [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]"
    )


_LOLI = (KIMI_BANGUMI, LOLIHOUSE)
RELEASES: tuple[Release, ...] = (
    # 聚合 feed 沒帶到、補舊集才補得到的兩集（`aggregate=False`）。
    Release(_kimi("", "01"), _mikan("2026-07-08T12:23:11.098"), 1, "mikan", _LOLI, False),
    Release(_kimi("", "02"), _mikan("2026-07-18T01:37:28.264"), 1, "mikan", _LOLI, False),
    Release(_kimi("", "03"), _mikan("2026-07-23T17:13:01.782"), 1, "mikan", _LOLI),
    Release(_kimi("", "04"), _mikan("2026-07-30T20:28:39.227"), 1, "mikan", _LOLI),
    Release(_kimi("", "05"), _mikan("2026-08-06T00:36:22.835"), 2, "mikan", _LOLI),
    Release(_kimi("", "05v2"), _mikan("2026-08-07T19:02:40.118"), 2, "mikan", _LOLI),
    Release(_kimi("kitauji", "05"), _mikan("2026-08-05T22:11:09.502"), 2, "mikan", (4009, KITAUJI)),
    Release(
        "[绿茶字幕组] 上伊那牡丹，酒醉身姿似百合花般 / Kamiina Botan, Yoeru Sugata wa Yuri no Hana "
        "[11][WebRip][1080p][简繁日内封]",
        _acgrip("2026-06-28T00:43:12"),
        1,
        "acgrip",
        page=358731,
        search="kamiina",
    ),
    Release(
        "[千夏字幕组][上伊那牡丹，醉姿如百合_Kamiina Botan, Yoeru Sugata wa Yuri no Hana]"
        "[第01-12话][1080p_HEVC][简繁内封][合集]",
        _acgrip("2026-07-06T00:23:40"),
        1,
        "acgrip",
        page=359402,
        search="kamiina",
    ),
    Release(
        "[绿茶字幕组] 上伊那牡丹，酒醉身姿似百合花般 / Kamiina Botan, Yoeru Sugata wa Yuri no Hana "
        "[12][WebRip][1080p][简繁日内封]",
        _acgrip("2026-06-28T01:50:31"),
        2,
        "acgrip",
        page=358736,
        search="kamiina",
    ),
    *(
        Release(
            _rezero(episode),
            _acgrip("2021-01-07T09:30:00") + timedelta(weeks=episode - 1),
            1,
            "acgrip",
            page=150700 + episode,
            search="rezero",
            seconds=29 * 60,
        )
        for episode in range(1, 5)
    ),
)


def is_batch(release: Release) -> bool:
    """整季合集：Berth 預設排除它（`parser.release` 的 `batch`），所以這一台不必造位元組以外的東西，
    測試也不會等它下載。"""
    return "合集" in release.title


def current_round(path: Path = Path(ROUND)) -> int:
    try:
        return int(path.read_text().strip() or 1)
    except FileNotFoundError:
        return 1


# --- 位元組與 torrent --------------------------------------------------------


def build(fixtures: Path, staging: Path) -> dict[str, tuple[Release, bytes]]:
    """每一筆發佈一支影片、一個單檔 torrent。回 info hash → （發佈, `.torrent`）。"""
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    seed = (fixtures / "e2e" / "seed.mkv").read_bytes()
    out: dict[str, tuple[Release, bytes]] = {}
    for release in RELEASES:
        content = lasting(seed, release.seconds) + release.title.encode()
        (staging / release.file_name).write_bytes(content)
        info = {
            "name": release.file_name,
            "length": len(content),
            "piece length": PIECE_LENGTH,
            "pieces": b"".join(
                hashlib.sha1(content[offset : offset + PIECE_LENGTH]).digest()
                for offset in range(0, len(content), PIECE_LENGTH)
            ),
        }
        digest = hashlib.sha1(bencode(info)).hexdigest()
        out[digest] = (release, bencode({"announce": ANNOUNCE, "info": info}))
    return out


# --- 各站的頁面 -------------------------------------------------------------


def mikan_feed(title: str, releases: list[tuple[str, Release, int]]) -> bytes:
    """Mikan RSS 的形狀（`tests/fixtures/http/mikan/rss-bangumi.4009-370.xml`）。"""
    items = []
    for digest, release, size in releases:
        name = escape(release.title)
        page = f"https://mikanani.me/Home/Episode/{digest}"
        local = release.published.astimezone(MIKAN_TZ)
        stamp = local.strftime("%Y-%m-%dT%H:%M:%S.") + f"{local.microsecond // 1000:03d}"
        items.append(
            f'<item><guid isPermaLink="false">{name}</guid><link>{page}</link>'
            f"<title>{name}</title><description>{name}[{size / 1e6:.2f} MB]</description>"
            f'<torrent xmlns="https://mikanani.me/0.1/"><link>{page}</link>'
            f"<contentLength>{size}</contentLength><pubDate>{stamp}</pubDate></torrent>"
            f'<enclosure type="application/x-bittorrent" length="{size}" '
            f'url="https://mikanani.me/Download/{local:%Y%m%d}/{digest}.torrent" /></item>'
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        f"<title>{escape(title)}</title><link>https://mikanani.me/</link>"
        f"<description>{escape(title)}</description>{''.join(items)}</channel></rss>"
    ).encode()


def acgrip_feed(term: str, releases: list[tuple[str, Release, int]]) -> bytes:
    """acg.rip RSS 的形狀（`tests/fixtures/http/acgrip/rss-search.kamiina-botan.xml`）。"""
    items = []
    for _, release, size in releases:
        page = f"https://acg.rip/t/{release.page}"
        items.append(
            f"<item><title>{escape(release.title)}</title><description></description>"
            f"<pubDate>{format_datetime(release.published)}</pubDate>"
            f"<link>{page}</link><guid>{page}</guid>"
            f'<enclosure url="{page}.torrent" type="application/x-bittorrent"/>'
            f"<torrent:contentLength>{size}</torrent:contentLength></item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" '
        'xmlns:torrent="http://xmlns.ezrss.it/0.1/" xmlns:media="http://search.yahoo.com/mrss/">'
        f"<channel><title>ACG.RIP</title><link>https://acg.rip/.xml?term={escape(term)}</link>"
        f"{''.join(items)}</channel></rss>"
    ).encode()


def episode_page(bangumi: int, subgroup: int) -> bytes:
    """單集頁上 Berth 只讀那一顆 `a.mikan-rss`（`adapters/rss/mikan.series_key`）。"""
    return (
        f'<html><body><a href="/RSS/Bangumi?bangumiId={bangumi}&amp;subgroupid={subgroup}" '
        'class="mikan-rss" target="_blank">RSS</a></body></html>'
    ).encode()


class Sites:
    def __init__(self, fixtures: Path, torrents: dict[str, tuple[Release, bytes]]) -> None:
        self.fixtures = fixtures
        self.torrents = torrents
        self.sizes = {digest: len(data) for digest, (_, data) in torrents.items()}

    def listed(self, keep: Callable[[Release], bool]) -> list[tuple[str, Release, int]]:
        """這一輪列得出來的，新的在前。"""
        now = current_round()
        rows = [
            (digest, release, self.sizes[digest])
            for digest, (release, _) in self.torrents.items()
            if release.round <= now and keep(release)
        ]
        return sorted(rows, key=lambda row: row[1].published, reverse=True)

    def answer(self, host: str, target: str) -> tuple[int, str, bytes]:
        split = urlsplit(target)
        path, query = split.path, parse_qs(split.query)
        if host == "mikanani.me":
            return self._mikan(path, query)
        if host == "acg.rip":
            return self._acgrip(path, query)
        return 404, "text/plain", b"not here"

    def _mikan(self, path: str, query: dict[str, list[str]]) -> tuple[int, str, bytes]:
        if path == AGGREGATE:
            rows = self.listed(lambda r: r.site == "mikan" and r.aggregate)
            return 200, "application/xml", mikan_feed("Mikan Project - 我的番组", rows)
        if path == "/RSS/Bangumi":
            key = (int(query["bangumiId"][0]), int(query["subgroupid"][0]))
            rows = self.listed(lambda r: r.mikan == key)
            return 200, "application/xml", mikan_feed("Mikan Project - 与你相恋到生命尽头", rows)
        if path.startswith("/Home/Episode/"):
            digest = path.rsplit("/", 1)[-1]
            release = self.torrents[digest][0]
            assert release.mikan is not None
            return 200, "text/html", episode_page(*release.mikan)
        if path == f"/Home/Bangumi/{KIMI_BANGUMI}":
            page = self.fixtures / "http" / "mikan" / "home-bangumi.4009.html"
            return 200, "text/html", page.read_bytes()
        if path.startswith("/Download/") and path.endswith(".torrent"):
            return self._torrent(path.rsplit("/", 1)[-1].removesuffix(".torrent"))
        return 404, "text/plain", b"not here"

    def _acgrip(self, path: str, query: dict[str, list[str]]) -> tuple[int, str, bytes]:
        if path == "/.xml":
            term = query.get("term", [""])[0]
            search = "rezero" if "zero" in term.lower() else "kamiina"
            rows = self.listed(lambda r: r.site == "acgrip" and r.search == search)
            return 200, "application/xml", acgrip_feed(term, rows)
        if path.startswith("/t/") and path.endswith(".torrent"):
            page = int(path.removeprefix("/t/").removesuffix(".torrent"))
            digest = next(d for d, (r, _) in self.torrents.items() if r.page == page)
            return self._torrent(digest)
        return 404, "text/plain", b"not here"

    def _torrent(self, digest: str) -> tuple[int, str, bytes]:
        found = self.torrents.get(digest.lower())
        if found is None:
            return 404, "text/plain", b"no such torrent"
        return 200, "application/x-bittorrent", found[1]


def serve(sites: Sites, certificate: Path, key: Path) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            host = (self.headers.get("Host") or "").split(":")[0].removeprefix("www.")
            status, kind, body = sites.answer(host, self.path)
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(("", PORT), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    fixtures = Path(FIXTURES)
    tls = fixtures / "e2e" / "tls"
    wait_for_berth()
    built = build(fixtures, Path(STAGING))
    Path(INDEX).write_text(
        json.dumps(
            {digest: {"file": r.file_name, "title": r.title} for digest, (r, _) in built.items()},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    Path(READY).write_text("ok")
    print(f"sites: {len(built)} releases", flush=True)
    serve(Sites(fixtures, built), tls / "site.pem", tls / "site.key")
