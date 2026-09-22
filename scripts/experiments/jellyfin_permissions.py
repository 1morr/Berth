"""以受限使用者實測 Jellyfin 的媒體庫權限（M1.5 票 01；研究 library-browsing.md §2、§3、§5）。

伺服器 API key 代讀某位使用者時，Jellyfin 哪些端點會套用他的媒體庫權限、哪些不會——研究第 2 節
那張表原本全是讀原始碼得來的。這支腳本起一台**一次性**的 Jellyfin（image 取自
`deploy/docker-compose.yml` 釘的那一個），在全新的 `/config` 與 dummy 媒體樹上建三個媒體庫、
一個管理員、一個只開放其中兩個媒體庫的一般使用者，然後量：

1. 研究第 2 節的表，逐列用 API key 與使用者自己的 token 各打一次
2. `/Items` 的過濾、排序、分頁參數是不是真的有作用（`/Items` 靜默忽略不存在的參數）
3. 從 TMDB id 找到這位使用者看得到的作品
4. 對 Series / Season 標已看，會不會遞迴到底下的集
5. 帳號被 Jellyfin 停用之後，API key 代讀是否照樣回資料
6. 研究當時在 12.0.0 上量過的行為，這一版是否相同

媒體庫關掉網路 metadata：類型、年份、評分、分級與 TMDB id 都寫在 NFO 裡，排序與篩選的
預期才算得出來，結果也不隨 TMDB 變動。跑完刪掉容器與工作目錄（`--keep` 保留，除錯用）。

用法（報告寫到 .local/experiments/results/）：
    python scripts/experiments/jellyfin_permissions.py
    python scripts/experiments/jellyfin_permissions.py --record   # 另外重錄 fixture
    python scripts/experiments/jellyfin_permissions.py --record --only items.tv.series.page.json
    python scripts/experiments/jellyfin_permissions.py --record --only shows-nextup.watching.json,…
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from jellyfin_naming import Jellyfin
from lib import Report, Response, poll, request

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy" / "docker-compose.yml"
FIXTURES = ROOT / "tests" / "fixtures" / "http" / "jellyfin"
CONTAINER = "berth-exp-jellyfin-permissions"
FFMPEG = "/usr/lib/jellyfin-ffmpeg/ffmpeg"
LIMITED = "limited"
PASSWORD = "berth-experiment-2026"
API_KEY_APP = "Berth-Permissions"
TICKS_PER_MINUTE = 60 * 10_000_000
#: fixture 是對這一版錄的。fixture README 的規則是「新版本開新檔案、不覆寫既有的」，所以
#: `deploy/` 換了版本之後 `--record` 會停下來，由人決定新檔名，而不是悄悄蓋掉這一組證據。
RECORDED_VERSION = "12.1.0"

#: 媒體庫名 → collection type。受限使用者只開放 ALLOWED，FORBIDDEN 是「沒權限的那一個」。
LIBRARIES = {"TV": "tvshows", "Movies": "movies", "Anime": "tvshows"}
ALLOWED = ("TV", "Movies")
FORBIDDEN = "Anime"


@dataclass(frozen=True)
class Title:
    """媒體樹裡的一部作品。`episodes` 空的是電影。

    名稱、年份、評分、分級、加入日期刻意排成彼此不同的順序：某個排序鍵被忽略時，
    結果會退回名稱順序，看得出來。
    """

    library: str
    name: str
    year: int
    premiered: str
    rating: float | None
    mpaa: str
    genres: tuple[str, ...]
    tmdb: int | None
    episodes: tuple[tuple[int, int], ...] = ()
    critic: int | None = None
    minutes: int = 10
    #: 檔案 mtime 往回推幾天。電影與集的 DateCreated 在這個 bind mount 上實測就是 mtime
    #: （劇的 DateCreated 是掃描時間，不受它影響），「加入日期」「新集加入」排序才有不同的值可比。
    age_days: int = 0
    #: 資料夾裡 `poster.jpg` 以外的本機圖：`landscape`（Jellyfin 讀成 Thumb）、`fanart`
    #: （Backdrop）。繼續觀看與下一集的橫卡照 Thumb → 劇的 Thumb → Backdrop → 劇的 Backdrop
    #: 取圖（M1.5 票 07，研究 §7），幾部作品各缺不同的圖，DTO 上的每一格才都錄得到。
    art: tuple[str, ...] = ()

    @property
    def folder(self) -> str:
        tag = f" [tmdbid-{self.tmdb}]" if self.tmdb else ""
        return f"{self.name} ({self.year}){tag}"

    @property
    def is_movie(self) -> bool:
        return not self.episodes

    @property
    def label(self) -> str:
        return f"{self.library}/{self.name}"


FRIEREN = ("Frieren", 2023, "2023-09-29", 8.0, "TV-PG", ("Animation", "Adventure"), 209867)
S1 = ((1, 1), (1, 2))

TITLES: tuple[Title, ...] = (
    Title("TV", "Alpha Show", 2022, "2022-04-01", 7.0, "TV-14", ("Drama", "Fantasy"), 1399,
          ((1, 1), (1, 2), (1, 3), (2, 1), (2, 2)), age_days=30, art=("landscape", "fanart")),
    Title("TV", "Bravo Show", 2020, "2020-01-20", 9.0, "TV-MA", ("Comedy",), 1396, S1,
          age_days=10, art=("fanart",)),
    Title("TV", *FRIEREN, S1, age_days=40),
    # 沒有 TMDB id 的作品：`hasTmdbId` 有沒有真的過濾，要靠它看。
    Title("TV", "Hotel Show", 2021, "2021-06-01", None, "TV-G", ("Documentary",), None,
          ((1, 1),), age_days=20),
    # 同一個 TMDB id 也在沒權限的媒體庫裡：由 TMDB id 找作品時不可以找到這一份。
    Title("Anime", *FRIEREN, ((1, 1), (1, 2), (1, 3)), age_days=40),
    # 只在沒權限的媒體庫裡的類型、年份、分級：出現在回應裡就是洩漏。
    Title("Anime", "Delta Mecha", 2019, "2019-10-05", 6.0, "TV-Y7", ("Mecha",), 37854, S1,
          age_days=5),
    Title("Movies", "Echo Movie", 2021, "2021-10-22", 8.4, "PG-13", ("Science Fiction",), 27205,
          critic=87, minutes=20, age_days=20),
    Title("Movies", "Foxtrot Movie", 2018, "2018-03-09", 7.1, "R", ("Drama",), 157336,
          critic=72, minutes=10, age_days=30, art=("landscape", "fanart")),
    Title("Movies", "Golf Movie", 2024, "2024-03-01", 7.8, "PG", ("Science Fiction", "Adventure"),
          693134, critic=94, minutes=15, age_days=10),
)  # fmt: skip

FORBIDDEN_GENRES = {"Mecha"}
FORBIDDEN_YEARS = {2019}
FORBIDDEN_RATINGS = {"TV-Y7"}

#: 受限使用者的觀看紀錄（媒體庫, 作品, 季, 集, 看完的日期）。沒權限的那一部要在縮權**之前**寫，
#: 縮權之後 API key 也寫不進去（這正是要量的一列），所以建置時先給全部權限。
PLAYED = (
    ("TV", "Alpha Show", 1, 1, "2026-01-01"),
    ("TV", "Bravo Show", 1, 1, "2026-03-01"),
    ("Anime", "Delta Mecha", 1, 1, "2026-02-01"),
)
#: 看到一半的集（媒體庫, 作品, 季, 集, 分鐘）。
IN_PROGRESS = (("TV", "Frieren", 1, 1, 3), ("Anime", "Frieren", 1, 1, 4))
#: `shows-nextup.watching.cutoff.json` 的 `nextUpDateCutoff`：落在 `PLAYED` 的 Alpha 與 Bravo 之間。
NEXT_UP_CUTOFF = "2026-02-15T00:00:00.000Z"

#: 研究 §1.3、§4.1 記下的 12.0.0 參數表；拿來比這一版的 OpenAPI。
RESEARCH_12_0_PARAMS: dict[str, set[str]] = {
    "/UserItems/Resume": {
        "userId", "startIndex", "limit", "searchTerm", "parentId", "fields", "mediaTypes",
        "enableUserData", "imageTypeLimit", "enableImageTypes", "excludeItemTypes",
        "includeItemTypes", "enableTotalRecordCount", "enableImages", "excludeActiveSessions",
    },
    "/Shows/NextUp": {
        "userId", "startIndex", "limit", "fields", "seriesId", "parentId", "enableImages",
        "imageTypeLimit", "enableImageTypes", "enableUserData", "nextUpDateCutoff",
        "enableTotalRecordCount", "enableResumable", "enableRewatching",
    },
    "/Shows/{seriesId}/Episodes": {
        "seriesId", "userId", "fields", "season", "seasonId", "isMissing", "adjacentTo",
        "startItemId", "startIndex", "limit", "enableImages", "imageTypeLimit",
        "enableImageTypes", "enableUserData", "sortBy",
    },
    "/Shows/{seriesId}/Seasons": {
        "seriesId", "userId", "fields", "isSpecialSeason", "isMissing", "adjacentTo",
        "enableImages", "imageTypeLimit", "enableImageTypes", "enableUserData",
    },
}  # fmt: skip


# --- 一次性環境 ----------------------------------------------------------------


def compose_image() -> str:
    """套件內 Jellyfin 釘的 image。從 compose 讀，不另外寫死一份。"""
    text = COMPOSE.read_text("utf-8")
    match = re.search(r"image:\s*(lscr\.io/linuxserver/jellyfin:\S+)", text)
    if not match:
        raise SystemExit(f"{COMPOSE} 裡找不到 linuxserver/jellyfin 的 image")
    return match.group(1)


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True)


def nfo(title: Title) -> str:
    root = "movie" if title.is_movie else "tvshow"
    lines = [
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
        f"<{root}>",
        f"  <title>{title.name}</title>",
        f"  <year>{title.year}</year>",
        f"  <premiered>{title.premiered}</premiered>",
        f"  <mpaa>{title.mpaa}</mpaa>",
    ]
    if title.rating is not None:
        lines.append(f"  <rating>{title.rating}</rating>")
    if title.critic is not None:
        lines.append(f"  <criticrating>{title.critic}</criticrating>")
    lines += [f"  <genre>{g}</genre>" for g in title.genres]
    if title.tmdb:
        lines.append(f'  <uniqueid type="tmdb" default="true">{title.tmdb}</uniqueid>')
    lines.append(f"</{root}>")
    return "\n".join(lines) + "\n"


def make_media(workdir: Path, image: str) -> None:
    """種子影片與海報用 Jellyfin image 自己的 ffmpeg 產生，宿主不必裝 ffmpeg。

    影片是 64×64、每秒一格的黑畫面，幾十 KB；長度照 `Title.minutes`，「片長」排序才有值可比。
    """
    seeds = workdir / "seeds"
    seeds.mkdir(parents=True)
    mount = f"type=bind,source={seeds},target=/out"
    ffmpeg = ["run", "--rm", "--mount", mount, "--entrypoint", FFMPEG, image]
    quiet = ["-hide_banner", "-loglevel", "error", "-f", "lavfi"]
    for minutes in sorted({t.minutes for t in TITLES}):
        black = ["-i", "color=c=black:s=64x64:r=1", "-t", str(minutes * 60)]
        encode = ["-c:v", "libx264", "-pix_fmt", "yuv420p", f"/out/seed-{minutes}.mkv"]
        docker(*ffmpeg, *quiet, *black, *encode)
    for name, color, size in (
        ("poster", "0x1d4e89", "200x300"),
        ("landscape", "0x89511d", "320x180"),
        ("fanart", "0x1d8951", "320x180"),
    ):
        still = ["-i", f"color=c={color}:s={size}", "-frames:v", "1", f"/out/{name}.jpg"]
        docker(*ffmpeg, *quiet, *still)

    media = workdir / "media"
    now = datetime.now(UTC).timestamp()
    for title in TITLES:
        folder = media / title.library.lower() / title.folder
        folder.mkdir(parents=True)
        seed = seeds / f"seed-{title.minutes}.mkv"
        for art in ("poster", *title.art):
            shutil.copyfile(seeds / f"{art}.jpg", folder / f"{art}.jpg")
        if title.is_movie:
            shutil.copyfile(seed, folder / f"{title.folder}.mkv")
            (folder / "movie.nfo").write_text(nfo(title), "utf-8")
        else:
            (folder / "tvshow.nfo").write_text(nfo(title), "utf-8")
            for season, episode in title.episodes:
                season_dir = folder / f"Season {season:02d}"
                season_dir.mkdir(exist_ok=True)
                name = f"{title.name} ({title.year}) - S{season:02d}E{episode:02d}.mkv"
                shutil.copyfile(seed, season_dir / name)
        stamp = now - title.age_days * 86400
        # 由深到淺：寫子項會更新父資料夾的 mtime，資料夾要最後改。
        for path in [*sorted(folder.rglob("*"), reverse=True), folder]:
            os.utime(path, (stamp, stamp))


@contextmanager
def disposable_jellyfin(
    workdir: Path, image: str, port: int, keep: bool, report: Report
) -> Iterator[str]:
    """起一台全新的 Jellyfin；離開時連同匿名 volume 與工作目錄一起刪掉。

    `/config` 與 `/media` 都是 bind mount，但 image 宣告了 `VOLUME /config`，
    ffmpeg 那幾個 `--rm` 容器會各帶一個匿名 volume——`--rm` 與 `rm -v` 會一起清掉它們。
    """
    docker("rm", "-f", "-v", CONTAINER, check=False)
    workdir.mkdir(parents=True, exist_ok=True)
    if any(workdir.iterdir()):
        raise SystemExit(f"{workdir} 不是空目錄；這支腳本跑完會整個刪掉它")
    try:
        make_media(workdir, image)
        (workdir / "config").mkdir()
        config = f"type=bind,source={workdir / 'config'},target=/config"
        media = f"type=bind,source={workdir / 'media'},target=/media,readonly"
        env = ["-e", "PUID=1000", "-e", "PGID=1000", "-e", "TZ=Etc/UTC"]
        publish = ["-p", f"127.0.0.1:{port}:8096"]
        mounts = ["--mount", config, "--mount", media]
        docker("run", "-d", "--name", CONTAINER, *publish, *env, *mounts, image)
        report.note(f"一次性容器 {CONTAINER}（{image}），工作目錄 {workdir}")
        yield f"http://127.0.0.1:{port}"
    finally:
        if keep:
            report.note(f"--keep：保留容器 {CONTAINER} 與 {workdir}")
        else:
            docker("rm", "-f", "-v", CONTAINER, check=False)
            shutil.rmtree(workdir, ignore_errors=True)
            report.note(f"已刪除容器 {CONTAINER} 與 {workdir}")


# --- 連線 ----------------------------------------------------------------------


@dataclass(frozen=True)
class Credential:
    """一種身分。`token` 是 None 就不帶 `Authorization`（匿名）。

    每種身分用自己的 DeviceId：Jellyfin 以裝置管理 session，分開是預防同一個裝置重新登入時
    作廢別的身分的 token（沒有實測過會不會）。
    """

    name: str
    token: str | None
    device: str = "berth-exp-permissions"

    def header(self) -> dict[str, str]:
        parts = f'Client="Berth-Experiment", Device="script", DeviceId="{self.device}"'
        token = f', Token="{self.token}"' if self.token else ""
        return {"Authorization": f'MediaBrowser {parts}, Version="0.1.0"{token}'}


ANONYMOUS = Credential("anonymous", None)


class Server:
    def __init__(self, base: str) -> None:
        self.base = base

    def send(
        self,
        cred: Credential,
        path: str,
        *,
        method: str = "GET",
        params: Mapping[str, str] | None = None,
        json_body: Any = None,
    ) -> Response:
        headers = cred.header() if cred.token is not None else {}
        url = f"{self.base}{path}"
        return request(url, method=method, headers=headers, params=params, json_body=json_body)

    def login(self, device: str) -> Response:
        """以受限使用者登入。`device` 由呼叫端給，理由見 `Credential`。"""
        body = {"Username": LIMITED, "Pw": PASSWORD}
        cred = Credential("login", None, device)
        url = f"{self.base}/Users/AuthenticateByName"
        return request(url, method="POST", headers=cred.header(), json_body=body)

    def json(self, cred: Credential, path: str, **kwargs: Any) -> Any:
        """設定步驟用：不是 2xx 就停，後面量到的東西都建立在它上面。"""
        resp = self.send(cred, path, **kwargs)
        if not resp.ok:
            method = kwargs.get("method", "GET")
            raise RuntimeError(f"{method} {path} -> {resp.status} {resp.text[:300]}")
        return resp.json()


# --- 媒體樹在 Jellyfin 裡的樣子 --------------------------------------------------


@dataclass
class Catalog:
    libraries: dict[str, str]
    titles: dict[Title, str] = field(default_factory=dict)
    seasons: dict[tuple[Title, int], str] = field(default_factory=dict)
    episodes: dict[tuple[Title, int, int], str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    image_tags: dict[str, str] = field(default_factory=dict)

    def title(self, library: str, name: str) -> Title:
        return next(t for t in self.titles if t.library == library and t.name == name)

    def title_id(self, library: str, name: str) -> str:
        return self.titles[self.title(library, name)]

    def season(self, library: str, name: str, season: int) -> str:
        return self.seasons[(self.title(library, name), season)]

    def episode(self, library: str, name: str, season: int, episode: int) -> str:
        return self.episodes[(self.title(library, name), season, episode)]

    def ids_in(self, library: str) -> set[str]:
        out = {self.libraries[library]}
        out |= {i for t, i in self.titles.items() if t.library == library}
        out |= {i for (t, _), i in self.seasons.items() if t.library == library}
        out |= {i for (t, _, _), i in self.episodes.items() if t.library == library}
        return out

    def label(self, item_id: str) -> str:
        return self.labels.get(item_id, item_id)

    def describe(self, item: Mapping[str, Any]) -> str:
        return self.labels.get(str(item.get("Id")), f"?{item.get('Type')}:{item.get('Name')}")


def discover(srv: Server, api: Credential) -> Catalog | None:
    """把 TITLES 對上 Jellyfin 的 item id。缺任何一個（還沒掃完）就回 None 讓 poll 再等。"""
    folders = srv.json(api, "/Library/VirtualFolders")
    catalog = Catalog({str(f["Name"]): str(f["ItemId"]) for f in folders})
    catalog.labels = {lib_id: f"lib:{name}" for name, lib_id in catalog.libraries.items()}
    for library, lib_id in catalog.libraries.items():
        params = {"parentId": lib_id, "recursive": "true", "fields": "Path"}
        items: list[dict[str, Any]] = srv.json(api, "/Items", params=params)["Items"]
        for title in (t for t in TITLES if t.library == library):
            root = f"/media/{library.lower()}/{title.folder}"
            if title.is_movie:
                heads = [i for i in items if i["Type"] == "Movie" and root in str(i.get("Path"))]
            else:
                heads = [i for i in items if i["Type"] == "Series" and i.get("Path") == root]
            if len(heads) != 1:
                return None
            head = heads[0]
            catalog.titles[title] = head["Id"]
            catalog.labels[head["Id"]] = title.label
            catalog.image_tags[head["Id"]] = str((head.get("ImageTags") or {}).get("Primary", ""))
            children = [i for i in items if i.get("SeriesId") == head["Id"]]
            for season, episode in title.episodes:
                seasons = [
                    i for i in children if i["Type"] == "Season" and i.get("IndexNumber") == season
                ]
                episodes = [
                    i
                    for i in children
                    if i["Type"] == "Episode"
                    and (i.get("ParentIndexNumber"), i.get("IndexNumber")) == (season, episode)
                ]
                if len(seasons) != 1 or len(episodes) != 1:
                    return None
                catalog.seasons[(title, season)] = seasons[0]["Id"]
                catalog.labels[seasons[0]["Id"]] = f"{title.label} S{season:02d}"
                catalog.episodes[(title, season, episode)] = episodes[0]["Id"]
                catalog.labels[episodes[0]["Id"]] = f"{title.label} S{season:02d}E{episode:02d}"
    return catalog


def check_metadata(srv: Server, api: Credential, catalog: Catalog, admin_id: str) -> list[str]:
    """NFO 沒被讀到的話，後面所有排序與篩選的預期都不成立，所以先驗。

    `/Items/{id}` 用 API key 而不帶 `userId` 回 400，所以帶管理員自己的 id。
    """
    problems = []
    for title, item_id in catalog.titles.items():
        item = srv.json(api, f"/Items/{item_id}", params={"userId": admin_id})
        got = (
            sorted(item.get("Genres") or []),
            item.get("ProductionYear"),
            (item.get("ProviderIds") or {}).get("Tmdb"),
            item.get("OfficialRating"),
        )
        want = (
            sorted(title.genres),
            title.year,
            str(title.tmdb) if title.tmdb else None,
            title.mpaa,
        )
        if got != want:
            problems.append(f"{title.label}: 預期 {want}，Jellyfin 是 {got}")
    return problems


# --- 量測工具 ------------------------------------------------------------------


def rows_of(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("Items"), list):
            return list(payload["Items"])
        if "Id" in payload:
            return [payload]
    return None


def ids_of(resp: Response) -> set[str]:
    return {str(r["Id"]) for r in rows_of(resp.json()) or []}


@dataclass
class Outcome:
    status: int
    verdict: str
    count: int | None = None
    shown: list[str] = field(default_factory=list)
    body: str = ""

    def line(self) -> str:
        count = "" if self.count is None else f"，{self.count} 筆"
        return f"HTTP {self.status} → {self.verdict}{count} {self.shown[:8]} {self.body}"


def judge(resp: Response, catalog: Catalog, forbidden: set[str], write: bool = False) -> Outcome:
    """把一個回應判成 filtered / leaks / 狀態碼。

    - 非 2xx：判定就是狀態碼（404 = Jellyfin 擋下來了）
    - 寫入類 2xx：leaks（寫進去了）
    - 清單：出現任何屬於沒權限媒體庫的 item（本身、所屬的劇、季、上層）就是 leaks
    - 類型 / 年份 / 分級清單：出現只存在於沒權限媒體庫的值就是 leaks；三份都空是 empty
    """
    if not resp.ok:
        return Outcome(resp.status, str(resp.status), body=resp.text[:160])
    if write:
        return Outcome(resp.status, "leaks", body=resp.text[:160])
    payload = resp.json() if resp.body else None
    # `/Items/Filters(2)` 的形狀。單一 item 的 DTO 也有 `Genres`，靠 `Id` 分開。
    if isinstance(payload, dict) and "Genres" in payload and "Id" not in payload:
        genres = {g["Name"] if isinstance(g, dict) else g for g in payload["Genres"] or []}
        years = set(payload.get("Years") or [])
        ratings = set(payload.get("OfficialRatings") or [])
        leaked_values = (
            (genres & FORBIDDEN_GENRES) | (years & FORBIDDEN_YEARS) | (ratings & FORBIDDEN_RATINGS)
        )
        shown = [f"Genres={sorted(genres)}", f"Years={sorted(years)}", f"Ratings={sorted(ratings)}"]
        if not (genres or years or ratings):
            return Outcome(resp.status, "empty", None, shown)
        return Outcome(resp.status, "leaks" if leaked_values else "filtered", None, shown)
    rows = rows_of(payload)
    if rows is None:
        return Outcome(resp.status, "?", body=resp.text[:160])
    if rows and all(r.get("Type") in {"Genre", "Year"} for r in rows):
        names = {str(r.get("Name")) for r in rows}
        leaked_names = names & (FORBIDDEN_GENRES | {str(y) for y in FORBIDDEN_YEARS})
        verdict = "leaks" if leaked_names else "filtered"
        return Outcome(resp.status, verdict, len(rows), sorted(names))
    keys = ("Id", "SeriesId", "SeasonId", "ParentId")
    leaked = any({str(r[k]) for k in keys if r.get(k)} & forbidden for r in rows)
    shown = [catalog.describe(r) for r in rows]
    return Outcome(resp.status, "leaks" if leaked else "filtered", len(rows), shown)


class Fixtures:
    """`--record` 時把回應原文寫進 tests/fixtures/http/jellyfin/。

    body 重新縮排成與其他 fixture 相同的格式（`sort_keys`、`ensure_ascii=False`）。
    404 的 body 也是 JSON（problem details，或 `"Series not found"` 這種 JSON 字串）；
    狀態碼不在檔案裡，寫在 fixture README。圖片只存狀態碼與標頭。
    """

    def __init__(self, enabled: bool, only: frozenset[str] = frozenset()) -> None:
        self.enabled = enabled
        #: 空的就是整組。非空時只寫這幾個檔名：一次加錄新的 fixture，不必讓既有的那一組跟著換掉
        #: 使用者 id、`ServerId` 與日期（item id 由路徑決定，兩輪相同）。
        self.only = only

    def write(self, name: str, resp: Response) -> None:
        if not self.enabled or (self.only and name not in self.only):
            return
        path = FIXTURES / name
        if name.endswith(".headers.json"):
            payload = {"status": resp.status, "headers": dict(sorted(resp.headers.items()))}
            path.write_text(json.dumps(payload, indent=2) + "\n", "utf-8", newline="\n")
        else:
            text = json.dumps(resp.json(), indent=2, ensure_ascii=False, sort_keys=True)
            path.write_text(text + "\n", "utf-8", newline="\n")
        print(f"  寫入 {path.relative_to(ROOT)}（HTTP {resp.status}，{len(resp.body)} bytes）")


# --- 建置 ----------------------------------------------------------------------


def create_library(srv: Server, admin: Credential, name: str, collection_type: str) -> None:
    """關掉所有網路 fetcher：metadata 只來自 NFO，圖只來自資料夾裡的 jpg（`Title.art`）。

    `TypeOptions` 列出型別而 fetcher 清單留空 = 那個型別一個 fetcher 都不開；
    整個 `TypeOptions` 留空才是「用預設」（TMDB）。
    """
    no_fetchers: list[dict[str, Any]] = [
        {"Type": kind, "MetadataFetchers": [], "ImageFetchers": []}
        for kind in ("Series", "Season", "Episode", "Movie")
    ]
    path = f"/media/{name.lower()}"
    options = {
        "Enabled": True,
        "EnableRealtimeMonitor": False,
        "EnableChapterImageExtraction": False,
        "ExtractChapterImagesDuringLibraryScan": False,
        "EnableTrickplayImageExtraction": False,
        "ExtractTrickplayImagesDuringLibraryScan": False,
        "SaveLocalMetadata": False,
        "MetadataSavers": [],
        "AutomaticRefreshIntervalDays": 0,
        "PathInfos": [{"Path": path}],
        "TypeOptions": no_fetchers,
    }
    params = {"name": name, "collectionType": collection_type, "paths": path}
    body = {"LibraryOptions": options}
    srv.json(
        admin,
        "/Library/VirtualFolders",
        method="POST",
        params={**params, "refreshLibrary": "false"},
        json_body=body,
    )


def iso(day: str) -> str:
    return f"{day}T12:00:00.0000000Z"


def seed_user_data(srv: Server, api: Credential, catalog: Catalog, user_id: str) -> None:
    user = {"userId": user_id}
    for library, name, season, episode, day in PLAYED:
        item = catalog.episode(library, name, season, episode)
        params = {**user, "datePlayed": iso(day)}
        srv.json(api, f"/UserPlayedItems/{item}", method="POST", params=params)
    for library, name, season, episode, minutes in IN_PROGRESS:
        item = catalog.episode(library, name, season, episode)
        body = {"PlaybackPositionTicks": minutes * TICKS_PER_MINUTE}
        srv.json(api, f"/UserItems/{item}/UserData", method="POST", params=user, json_body=body)
    # 電影：一部看到一半（繼續觀看）、兩部看過不同次數（PlayCount 排序）。
    movie_data: list[tuple[str, dict[str, Any]]] = [
        ("Foxtrot Movie", {"PlaybackPositionTicks": 5 * TICKS_PER_MINUTE}),
        ("Echo Movie", {"Played": True, "PlayCount": 3, "LastPlayedDate": iso("2026-04-01")}),
        ("Golf Movie", {"Played": True, "PlayCount": 1, "LastPlayedDate": iso("2026-05-01")}),
    ]
    for name, body in movie_data:
        item = catalog.title_id("Movies", name)
        srv.json(api, f"/UserItems/{item}/UserData", method="POST", params=user, json_body=body)


def set_policy(srv: Server, admin: Credential, user_id: str, **changes: Any) -> None:
    policy: dict[str, Any] = srv.json(admin, f"/Users/{user_id}")["Policy"]
    srv.json(admin, f"/Users/{user_id}/Policy", method="POST", json_body={**policy, **changes})


# --- 1. 研究第 2 節的表 ----------------------------------------------------------


@dataclass(frozen=True)
class Row:
    label: str
    path: str
    params: dict[str, str]
    #: 研究第 2 節的推論：filtered（✔）、leaks（✘）、404、anonymous、unknown（未查或未列）
    expected: str
    method: str = "GET"
    fixture: str | None = None
    #: 寫入類的列：每打完一次就讀回這個 item 的 UserData，才分得出「404 而且真的沒寫進去」。
    readback: str | None = None


def matrix_rows(c: Catalog) -> list[Row]:
    lib = c.libraries[FORBIDDEN]
    delta = c.title_id(FORBIDDEN, "Delta Mecha")
    season = c.season(FORBIDDEN, "Delta Mecha", 1)
    ep = c.episode(FORBIDDEN, "Delta Mecha", 1, 2)
    rec = {"recursive": "true"}
    return [
        Row("GET /UserViews?userId=U", "/UserViews", {}, "filtered",
            fixture="userviews.restricted.json"),
        Row("GET /Items?userId=U&recursive=true（不帶 parentId / ids）", "/Items",
            {**rec, "includeItemTypes": "Series,Movie"}, "filtered"),
        Row("GET /Items?userId=U&parentId=<無權的媒體庫>", "/Items", {**rec, "parentId": lib},
            "leaks", fixture="items.parent-forbidden.json"),
        Row("GET /Items?userId=U&parentId=<無權的劇>（研究未列）", "/Items",
            {**rec, "parentId": delta}, "unknown"),
        Row("GET /Items?userId=U&parentId=<無權的季>（研究未列）", "/Items",
            {**rec, "parentId": season}, "unknown"),
        Row("GET /Items?userId=U&ids=<無權的項目>", "/Items", {"ids": delta}, "leaks"),
        Row("GET /Items/{無權的項目}?userId=U", f"/Items/{delta}", {}, "404",
            fixture="items-id.forbidden.json"),
        Row("GET /UserItems/Resume?userId=U（不帶 parentId）", "/UserItems/Resume",
            {"mediaTypes": "Video"}, "filtered"),
        Row("GET /UserItems/Resume?userId=U&parentId=<無權的媒體庫>", "/UserItems/Resume",
            {"mediaTypes": "Video", "parentId": lib}, "leaks"),
        Row("GET /Shows/NextUp?userId=U（不帶 parentId / seriesId）", "/Shows/NextUp", {},
            "filtered"),
        Row("GET /Shows/NextUp?userId=U&parentId=<無權的媒體庫>", "/Shows/NextUp",
            {"parentId": lib}, "leaks"),
        Row("GET /Shows/NextUp?userId=U&seriesId=<無權的劇>", "/Shows/NextUp",
            {"seriesId": delta}, "leaks"),
        Row("GET /Shows/{無權的劇}/Seasons?userId=U", f"/Shows/{delta}/Seasons", {}, "404",
            fixture="shows-seasons.forbidden.json"),
        Row("GET /Shows/{無權的劇}/Episodes?userId=U", f"/Shows/{delta}/Episodes", {}, "404",
            fixture="shows-episodes.forbidden.json"),
        Row("GET /Shows/{無權的劇}/Episodes?userId=U&seasonId=<無權的季>",
            f"/Shows/{delta}/Episodes", {"seasonId": season}, "404"),
        Row("POST /UserPlayedItems/{無權的集}?userId=U", f"/UserPlayedItems/{ep}", {}, "404",
            method="POST", fixture="userplayeditems.forbidden.json", readback=ep),
        Row("DELETE /UserPlayedItems/{無權的集}?userId=U", f"/UserPlayedItems/{ep}", {}, "404",
            method="DELETE"),
        Row("GET /UserItems/{無權的集}/UserData?userId=U（研究未列）",
            f"/UserItems/{ep}/UserData", {}, "unknown"),
        Row("GET /Genres?userId=U&parentId=<無權的媒體庫>", "/Genres", {"parentId": lib}, "leaks"),
        Row("GET /Years?userId=U&parentId=<無權的媒體庫>", "/Years", {**rec, "parentId": lib},
            "leaks"),
        Row("GET /Items/Filters?userId=U&parentId=<無權的媒體庫>", "/Items/Filters",
            {"parentId": lib}, "leaks"),
        Row("GET /Items/Filters2?userId=U&parentId=<無權的媒體庫>", "/Items/Filters2",
            {"parentId": lib}, "leaks"),
        Row("GET /Items/Filters?userId=U（不帶 parentId，研究未列）", "/Items/Filters", {},
            "unknown"),
        Row("GET /Genres?userId=U（不帶 parentId，研究未列）", "/Genres", {}, "unknown"),
        Row("GET /Items/Latest?userId=U", "/Items/Latest", {}, "unknown"),
        Row("GET /Items/Latest?userId=U&parentId=<無權的媒體庫>", "/Items/Latest",
            {"parentId": lib}, "unknown"),
    ]  # fmt: skip


def run_matrix(
    srv: Server,
    creds: tuple[Credential, Credential],
    c: Catalog,
    user_id: str,
    report: Report,
    fixtures: Fixtures,
) -> None:
    report.heading("1. 研究第 2 節的表（API key 與使用者 token，userId=受限使用者）")
    api = creds[0]
    forbidden = c.ids_in(FORBIDDEN)
    results: list[dict[str, Any]] = []
    for row in matrix_rows(c):
        outcomes = {}
        for cred in creds:
            params = {"userId": user_id, **row.params}
            resp = srv.send(cred, row.path, method=row.method, params=params)
            outcome = judge(resp, c, forbidden, write=row.method != "GET")
            if row.readback:
                # `ids=` 不檢查權限，正好拿來讀沒權限的那一集。
                read = {"userId": user_id, "ids": row.readback}
                data = srv.json(api, "/Items", params=read)["Items"][0].get("UserData") or {}
                played = {k: data.get(k) for k in ("Played", "PlayCount", "LastPlayedDate")}
                outcome.body = f"讀回 {played} {outcome.body}"
            outcomes[cred.name] = outcome
            if cred is api and row.fixture:
                fixtures.write(row.fixture, resp)
        verdict = outcomes[api.name].verdict
        if row.expected == "unknown":
            mark = "（研究未查或未列）"
        else:
            mark = "" if verdict == row.expected else "  ← 推論錯"
        report.note(f"{row.label}  研究推論 {row.expected}{mark}")
        for name, outcome in outcomes.items():
            report.note(f"    {name:8} {outcome.line()}")
        results.append(
            {
                "row": row.label,
                "expected": row.expected,
                "outcomes": {n: vars(o) for n, o in outcomes.items()},
            }
        )

    delta = c.title_id(FORBIDDEN, "Delta Mecha")
    image = srv.send(ANONYMOUS, f"/Items/{delta}/Images/Primary")
    report.note(f"GET /Items/{{無權的項目}}/Images/Primary（匿名）→ HTTP {image.status}")
    results.append({"row": "匿名取無權項目的圖", "expected": "anonymous", "status": image.status})
    report.record("matrix", results)


# --- 2. 過濾、排序、分頁 -----------------------------------------------------------


def run_filters(srv: Server, api: Credential, c: Catalog, user_id: str, report: Report) -> None:
    report.heading("2. /Items 的過濾與分頁參數（API key + userId=受限使用者）")
    allowed = [t for t in c.titles if t.library in ALLOWED]

    def titles(pred: Callable[[Title], bool]) -> set[str]:
        return {c.titles[t] for t in allowed if pred(t)}

    def episodes_of(name: str, season: int | None = None) -> set[str]:
        return {
            i
            for (t, s, _), i in c.episodes.items()
            if t.library == "TV" and t.name == name and season in (None, s)
        }

    user = {"userId": user_id, "recursive": "true"}
    base = {**user, "includeItemTypes": "Series,Movie"}
    eps = {**user, "includeItemTypes": "Episode"}
    alpha = c.title_id("TV", "Alpha Show")
    alpha_s1 = c.season("TV", "Alpha Show", 1)
    sci_fi_2024 = {**base, "genres": "Science Fiction", "years": "2024"}
    # (標籤, 查詢, 拿掉被測參數之後的對照查詢, 預期的 item id；None = 預期被忽略)
    checks: list[tuple[str, dict[str, str], dict[str, str], set[str] | None]] = [
        ("parentId=<TV 媒體庫>", {**base, "parentId": c.libraries["TV"]}, base,
         titles(lambda t: t.library == "TV")),
        ("parentId=<劇>&includeItemTypes=Episode", {**eps, "parentId": alpha}, eps,
         episodes_of("Alpha Show")),
        ("parentId=<季>&includeItemTypes=Episode", {**eps, "parentId": alpha_s1}, eps,
         episodes_of("Alpha Show", 1)),
        ("includeItemTypes=Series", {**user, "includeItemTypes": "Series"}, user,
         titles(lambda t: not t.is_movie)),
        ("includeItemTypes=Movie", {**user, "includeItemTypes": "Movie"}, user,
         titles(lambda t: t.is_movie)),
        ("genres=Drama", {**base, "genres": "Drama"}, base,
         titles(lambda t: "Drama" in t.genres)),
        ("genres=Drama|Comedy", {**base, "genres": "Drama|Comedy"}, base,
         titles(lambda t: bool({"Drama", "Comedy"} & set(t.genres)))),
        ("genres=Mecha（只在無權的媒體庫）", {**base, "genres": "Mecha"}, base, set()),
        ("years=2022", {**base, "years": "2022"}, base, titles(lambda t: t.year == 2022)),
        ("years=2018,2020", {**base, "years": "2018,2020"}, base,
         titles(lambda t: t.year in {2018, 2020})),
        ("years=2019（只在無權的媒體庫）", {**base, "years": "2019"}, base, set()),
        ("genres=Science Fiction&years=2024", sci_fi_2024, base,
         titles(lambda t: "Science Fiction" in t.genres and t.year == 2024)),
        ("對照：genre=Drama（少一個 s）", {**base, "genre": "Drama"}, base, None),
        ("對照：year=2022（少一個 s）", {**base, "year": "2022"}, base, None),
    ]  # fmt: skip
    results = []
    for label, params, baseline_params, expected in checks:
        got = ids_of(srv.send(api, "/Items", params=params))
        baseline = ids_of(srv.send(api, "/Items", params=baseline_params))
        if expected is None:
            verdict = "被忽略（與對照相同）" if got == baseline else "有作用"
        elif got == expected:
            verdict = "伺服器有過濾" if got != baseline else "結果對，但與對照相同（證明不了）"
        else:
            verdict = "結果不符預期"
        shown = sorted(c.label(i) for i in got)
        report.note(f"{label}: {verdict}；{len(got)} 筆（對照 {len(baseline)} 筆）{shown[:8]}")
        results.append(
            {"check": label, "verdict": verdict, "got": shown, "baseline": len(baseline)}
        )

    ordered = {**base, "sortBy": "SortName", "sortOrder": "Ascending"}
    full = srv.json(api, "/Items", params=ordered)
    page = srv.json(api, "/Items", params={**ordered, "startIndex": "2", "limit": "3"})
    full_ids = [i["Id"] for i in full["Items"]]
    page_ids = [i["Id"] for i in page["Items"]]
    paging = {
        "full": [c.label(i) for i in full_ids],
        "page": [c.label(i) for i in page_ids],
        "page_is_slice_2_5": page_ids == full_ids[2:5],
        "TotalRecordCount": page.get("TotalRecordCount"),
        "StartIndex": page.get("StartIndex"),
    }
    report.note(f"startIndex=2&limit=3：{paging}")
    report.record("filters", {"checks": results, "paging": paging})


SortKey = Callable[[dict[str, Any]], Any]


def run_sorts(srv: Server, api: Credential, c: Catalog, user_id: str, report: Report) -> None:
    report.heading("2b. sortBy / sortOrder（每個鍵後面接 SortName，jellyfin-web 的寫法）")
    series_played = {
        c.title_id(lib, name): day for lib, name, _, _, day in PLAYED if lib in ALLOWED
    }
    # 從 DTO 讀得到排序鍵的，驗「照這個值排」；讀不到的（分級、隨機）只驗升降冪互為反序。
    keys: dict[str, SortKey | None] = {
        "SortName": lambda i: i.get("SortName"),
        "CommunityRating": lambda i: i.get("CommunityRating"),
        "CriticRating": lambda i: i.get("CriticRating"),
        "PremiereDate": lambda i: i.get("PremiereDate"),
        "ProductionYear": lambda i: i.get("ProductionYear"),
        "DateCreated": lambda i: i.get("DateCreated"),
        "DateLastContentAdded": lambda i: i.get("DateLastMediaAdded"),
        "SeriesDatePlayed": lambda i: series_played.get(i["Id"]),
        "DatePlayed": lambda i: (i.get("UserData") or {}).get("LastPlayedDate"),
        "PlayCount": lambda i: (i.get("UserData") or {}).get("PlayCount"),
        "Runtime": lambda i: i.get("RunTimeTicks"),
        "OfficialRating": None,
        "Random": None,
    }
    plans = {
        "TV": ("Series", ["SortName", "CommunityRating", "PremiereDate", "ProductionYear",
                          "OfficialRating", "DateCreated", "DateLastContentAdded",
                          "SeriesDatePlayed", "Random"]),
        "Movies": ("Movie", ["SortName", "CommunityRating", "CriticRating", "PremiereDate",
                             "ProductionYear", "OfficialRating", "DateCreated", "DatePlayed",
                             "PlayCount", "Runtime", "Random"]),
    }  # fmt: skip
    fields = "SortName,DateCreated,DateLastMediaAdded"
    results = []
    for library, (kind, sort_keys) in plans.items():
        parent = c.libraries[library]
        base = {"userId": user_id, "parentId": parent, "recursive": "true"}
        base |= {"includeItemTypes": kind, "fields": fields}
        by_name = [r["Id"] for r in srv.json(api, "/Items", params=base)["Items"]]
        for key in sort_keys:
            sort_by = key if key == "SortName" else f"{key},SortName"
            asc = srv.json(api, "/Items", params={**base, "sortBy": sort_by})["Items"]
            desc_params = {**base, "sortBy": sort_by, "sortOrder": "Descending"}
            desc = srv.json(api, "/Items", params=desc_params)["Items"]
            extract = keys[key]

            def value(row: dict[str, Any], extract: SortKey | None = extract) -> Any:
                return extract(row) if extract else row.get("OfficialRating")

            values = [value(r) for r in asc]
            desc_values = [value(r) for r in desc]
            is_reverse = [r["Id"] for r in desc] == [r["Id"] for r in reversed(asc)]
            flipped = [r["Id"] for r in desc] != [r["Id"] for r in asc]
            present = [v for v in values if v is not None]
            desc_present = [v for v in desc_values if v is not None]
            # 並列（含沒有值的）之間靠 SortName 排，不一定剛好反過來，所以各自驗單調。
            monotonic = present == sorted(present) and desc_present == sorted(
                desc_present, reverse=True
            )
            if key == "Random":
                verdict = "不判定（隨機）"
            elif extract is None:
                verdict = "升降冪互為反序" if is_reverse else "升降冪不是反序"
            elif len(set(present)) < 2:
                verdict = "證明不了（值都一樣或沒有值）"
            elif monotonic and flipped:
                verdict = "伺服器有排序"
            else:
                verdict = "沒有照這個鍵排序"
            order = [c.label(r["Id"]) for r in asc]
            desc_order = [c.label(r["Id"]) for r in desc]
            same_as_name = [r["Id"] for r in asc] == by_name and key != "SortName"
            tail = "（與名稱順序相同，證明不了用的是這個鍵）" if same_as_name else ""
            report.note(f"{library} sortBy={sort_by}: {verdict}{tail}")
            report.note(f"    升冪 {order} 值 {values}")
            report.note(f"    降冪 {desc_order} 值 {desc_values}")
            results.append(
                {
                    "library": library,
                    "sortBy": sort_by,
                    "verdict": verdict,
                    "ascending": order,
                    "values": values,
                    "descending": desc_order,
                    "descending_values": desc_values,
                    "same_as_name_order": same_as_name,
                }
            )
    report.record("sorts", results)


# --- 3. 由 TMDB id 找作品 ----------------------------------------------------------


def run_tmdb_lookup(srv: Server, api: Credential, c: Catalog, user_id: str, report: Report) -> None:
    report.heading("3. 由 TMDB id 找到這位使用者看得到的作品")
    base = {"userId": user_id, "recursive": "true", "includeItemTypes": "Series,Movie"}
    baseline = ids_of(srv.send(api, "/Items", params=base))
    out: dict[str, Any] = {}

    guesses = {}
    for param in ("anyProviderIdEquals", "providerIds", "tmdbId", "hasProviderId"):
        got = ids_of(srv.send(api, "/Items", params={**base, param: "Tmdb.209867"}))
        guesses[param] = "被忽略" if got == baseline else f"有作用：{len(got)} 筆"
    out["guessed_params"] = guesses
    report.note(f"看起來像 provider id 過濾的參數名：{guesses}")

    has_tmdb = ids_of(srv.send(api, "/Items", params={**base, "hasTmdbId": "true"}))
    expected = {i for t, i in c.titles.items() if t.library in ALLOWED and t.tmdb}
    out["hasTmdbId"] = {
        "server_filters": has_tmdb == expected and has_tmdb != baseline,
        "got": sorted(c.label(i) for i in has_tmdb),
    }
    report.note(f"hasTmdbId=true：{out['hasTmdbId']}")

    lean = {"hasTmdbId": "true", "fields": "ProviderIds", "enableImages": "false"}
    listing = srv.json(api, "/Items", params={**base, **lean, "enableUserData": "false"})

    def matching(rows: list[dict[str, Any]], tmdb: int) -> list[str]:
        return [r["Id"] for r in rows if (r.get("ProviderIds") or {}).get("Tmdb") == str(tmdb)]

    one_step = {
        str(tmdb): [c.label(i) for i in matching(listing["Items"], tmdb)]
        for tmdb in (209867, 37854, 27205)
    }
    out["one_step"] = {"found": one_step, "rows_fetched": len(listing["Items"])}
    report.note(
        f"一段法（帶 userId、不帶 parentId、hasTmdbId、fields=ProviderIds，Berth 端比對）："
        f"{one_step}；一次拉回 {len(listing['Items'])} 筆"
    )

    server_wide = {k: v for k, v in base.items() if k != "userId"}
    everyone = srv.json(api, "/Items", params={**server_wide, **lean})
    two_step = {}
    for tmdb in (209867, 37854):
        two_step[str(tmdb)] = {
            c.label(i): srv.send(api, f"/Items/{i}", params={"userId": user_id}).status
            for i in matching(everyone["Items"], tmdb)
        }
    out["two_step"] = two_step
    report.note(f"兩段法（不帶 userId 找候選 → /Items/{{id}}?userId= 驗可見性）：{two_step}")
    report.record("tmdb_lookup", out)


# --- 4. Series / Season 標已看 ---------------------------------------------------


def watch_state(srv: Server, api: Credential, c: Catalog, series: str, user_id: str) -> Any:
    user = {"userId": user_id}
    rows = srv.json(api, f"/Shows/{series}/Episodes", params=user)["Items"]
    fields = ("Played", "PlayCount", "PlaybackPositionTicks", "LastPlayedDate")
    state = {c.label(r["Id"]): {k: (r.get("UserData") or {}).get(k) for k in fields} for r in rows}
    seasons = [i for (t, _), i in c.seasons.items() if c.titles[t] == series]
    for item in [series, *seasons]:
        data = srv.json(api, f"/Items/{item}", params=user).get("UserData") or {}
        folder_fields = ("Played", "PlayCount", "UnplayedItemCount", "PlayedPercentage")
        state[f"({c.label(item)})"] = {k: data.get(k) for k in folder_fields}
    return state


def run_played_recursion(
    srv: Server, api: Credential, c: Catalog, user_id: str, report: Report, fixtures: Fixtures
) -> None:
    report.heading("4. 對 Series / Season 標已看、未看會不會遞迴到集")
    user = {"userId": user_id}
    frieren = c.title_id("TV", "Frieren")
    alpha = c.title_id("TV", "Alpha Show")
    season_two = c.season("TV", "Alpha Show", 2)
    # Frieren 開始時第一集看到一半；Alpha 開始時第一集是早就看完的（PLAYED）。最後對整部
    # Alpha 標未看，看它會不會連那筆舊紀錄一起清掉。
    plans = {
        "series": (frieren, [("POST", frieren), ("DELETE", frieren)]),
        "season": (alpha, [("POST", season_two), ("DELETE", season_two), ("DELETE", alpha)]),
    }
    out: dict[str, Any] = {}
    for kind, (series, steps) in plans.items():
        log = [{"step": "before", "state": watch_state(srv, api, c, series, user_id)}]
        report.note(f"{c.label(series)} 開始：{log[0]['state']}")
        for method, target in steps:
            resp = srv.send(api, f"/UserPlayedItems/{target}", method=method, params=user)
            state = watch_state(srv, api, c, series, user_id)
            step = f"{method} {c.label(target)}"
            log.append({"step": step, "status": resp.status, "body": resp.json(), "state": state})
            report.note(f"{step} → HTTP {resp.status} {resp.text}")
            report.note(f"    之後：{state}")
        out[kind] = log

    # 單集的一來一回錄成 fixture（票 05 的契約測試）。
    ep = c.episode("TV", "Bravo Show", 1, 2)
    posted = srv.send(api, f"/UserPlayedItems/{ep}", method="POST", params=user)
    fixtures.write("userplayeditems.post.json", posted)
    deleted = srv.send(api, f"/UserPlayedItems/{ep}", method="DELETE", params=user)
    fixtures.write("userplayeditems.delete.json", deleted)
    out["episode"] = {"post": posted.json(), "delete": deleted.json()}
    report.note(f"單集 POST → {posted.status} {posted.text}")
    report.note(f"單集 DELETE → {deleted.status} {deleted.text}")
    report.record("played_recursion", out)


# --- 5. 停用的帳號 -------------------------------------------------------------------


def run_disabled(
    srv: Server,
    admin: Credential,
    creds: tuple[Credential, Credential],
    c: Catalog,
    user_id: str,
    report: Report,
    fixtures: Fixtures,
) -> None:
    report.heading("5. 帳號被 Jellyfin 停用之後")
    api, user = creds
    fixtures.write("users.restricted.json", srv.send(api, f"/Users/{user_id}"))
    views = srv.json(api, "/UserViews", params={"userId": user_id})
    set_policy(srv, admin, user_id, IsDisabled=True)
    after = srv.send(api, f"/Users/{user_id}")
    fixtures.write("users.restricted.disabled.json", after)
    policy = after.json()["Policy"]
    kept = {k: policy.get(k) for k in ("IsDisabled", "EnableAllFolders", "EnabledFolders")}
    report.note(f"GET /Users/{{id}}（API key）→ HTTP {after.status}：{kept}")
    view_ids = [v["Id"] for v in views["Items"]]
    library_ids = {n: c.libraries[n] for n in ALLOWED}
    report.note(f"UserViews 的 Id {view_ids}；媒體庫 ItemId {library_ids}")

    forbidden = c.ids_in(FORBIDDEN)
    alpha = c.title_id("TV", "Alpha Show")
    ep = c.episode("TV", "Bravo Show", 1, 2)
    titles = {"recursive": "true", "includeItemTypes": "Series,Movie"}
    tv = {"parentId": c.libraries["TV"], "recursive": "true"}
    probes: list[tuple[str, Credential, str, str, dict[str, str]]] = [
        ("UserViews", api, "GET", "/UserViews", {}),
        ("Items（不帶 parentId）", api, "GET", "/Items", titles),
        ("Items?parentId=TV", api, "GET", "/Items", tv),
        ("Resume", api, "GET", "/UserItems/Resume", {"mediaTypes": "Video"}),
        ("NextUp", api, "GET", "/Shows/NextUp", {}),
        ("Items/{id}", api, "GET", f"/Items/{alpha}", {}),
        ("Seasons", api, "GET", f"/Shows/{alpha}/Seasons", {}),
        ("POST UserPlayedItems", api, "POST", f"/UserPlayedItems/{ep}", {}),
        ("DELETE UserPlayedItems", api, "DELETE", f"/UserPlayedItems/{ep}", {}),
        ("停用前發的使用者 token：UserViews", user, "GET", "/UserViews", {}),
        ("停用前發的使用者 token：Items", user, "GET", "/Items", titles),
    ]  # fmt: skip
    results: dict[str, Any] = {}
    for label, cred, method, path, params in probes:
        resp = srv.send(cred, path, method=method, params={"userId": user_id, **params})
        outcome = judge(resp, c, forbidden, write=method != "GET")
        results[label] = vars(outcome)
        report.note(f"{label}（{cred.name}）→ {outcome.line()}")
    login = srv.login("berth-exp-permissions-relogin")
    results["停用後重新登入"] = {"status": login.status, "body": login.text[:160]}
    report.note(f"停用後重新登入 → HTTP {login.status} {login.text[:160]}")
    report.record("disabled", {"policy": kept, "userviews_ids": view_ids, "probes": results})


# --- 6. 與 12.0.0 的差異、其餘 fixture ------------------------------------------------


def run_regression(
    srv: Server, api: Credential, c: Catalog, user_id: str, report: Report, fixtures: Fixtures
) -> None:
    report.heading("6. 研究在 12.0.0 上量過的行為")
    user = {"userId": user_id}
    out: dict[str, Any] = {"version": srv.json(api, "/System/Info").get("Version")}
    report.note(f"伺服器版本 {out['version']}")

    for label, extra in (("不帶 mediaTypes", {}), ("mediaTypes=Video", {"mediaTypes": "Video"})):
        rows = srv.json(api, "/UserItems/Resume", params={**user, **extra})["Items"]
        out[f"resume {label}"] = [f"{r['Type']}:{c.describe(r)}" for r in rows]
        report.note(f"Resume {label}：{out[f'resume {label}']}")

    ep = c.episode("TV", "Bravo Show", 1, 2)
    delta = c.title_id(FORBIDDEN, "Delta Mecha")
    forbidden = c.ids_in(FORBIDDEN)
    no_user: dict[str, Any] = {
        "Resume": srv.send(api, "/UserItems/Resume").status,
        "NextUp": srv.send(api, "/Shows/NextUp").status,
        "GET /Items/{id}": srv.send(api, f"/Items/{ep}").status,
        # 沒有 user 就沒有權限可套：無權的劇照樣回，判定是 leaks。
        "GET /Shows/{無權的劇}/Seasons": judge(
            srv.send(api, f"/Shows/{delta}/Seasons"), c, forbidden
        ).line(),
        "GET /Shows/{無權的劇}/Episodes": judge(
            srv.send(api, f"/Shows/{delta}/Episodes"), c, forbidden
        ).line(),
        "POST UserPlayedItems": srv.send(api, f"/UserPlayedItems/{ep}", method="POST").status,
    }
    no_user["讀回 Played"] = srv.json(api, f"/UserItems/{ep}/UserData", params=user).get("Played")
    out["without_userId"] = no_user
    report.note(f"不帶 userId：{no_user}")

    alpha = c.title_id("TV", "Alpha Show")
    legacy_resume = srv.send(api, f"/Users/{user_id}/Items/Resume", params={"mediaTypes": "Video"})
    legacy_item = srv.send(api, f"/Users/{user_id}/Items/{alpha}")
    out["legacy_paths"] = {
        "/Users/U/Items/Resume": legacy_resume.status,
        "/Users/U/Items/{id}": legacy_item.status,
    }
    report.note(f"舊路徑：{out['legacy_paths']}")

    paths = srv.json(ANONYMOUS, "/api-docs/openapi.json")["paths"]

    def params_of(path: str) -> set[str]:
        return {p["name"] for p in paths[path]["get"].get("parameters", [])}

    items_params = params_of("/Items")
    out["openapi"] = {
        "param_diff_vs_12_0": {
            path: {"added": sorted(params_of(path) - old), "removed": sorted(old - params_of(path))}
            for path, old in RESEARCH_12_0_PARAMS.items()
        },
        "legacy_resume_listed": "/Users/{userId}/Items/Resume" in paths,
        "items_provider_params": sorted(p for p in items_params if "rovider" in p),
        "items_language_params": sorted(p for p in items_params if "anguage" in p),
    }
    report.note(f"OpenAPI：{out['openapi']}")

    episodes = {**user, "recursive": "true", "includeItemTypes": "Episode"}
    total = len(ids_of(srv.send(api, "/Items", params=episodes)))
    ignored = {}
    for param in ("seriesId", "ancestorIds"):
        got = ids_of(srv.send(api, "/Items", params={**episodes, param: alpha}))
        ignored[param] = f"{len(got)} 筆（全部 {total} 筆）"
    out["items_ignores"] = ignored
    report.note(f"/Items 沒有的參數：{ignored}")

    flat = srv.json(api, "/Items", params={**user, "includeItemTypes": "Series"})
    out["includeItemTypes_without_recursive"] = flat.get("TotalRecordCount")
    report.note(f"includeItemTypes=Series 不帶 recursive：{flat.get('TotalRecordCount')} 筆")

    tv = {**user, "parentId": c.libraries["TV"]}
    filters = srv.send(api, "/Items/Filters", params={**tv, "includeItemTypes": "Series"})
    fixtures.write("items-filters.tv.json", filters)
    filters2 = srv.json(api, "/Items/Filters2", params={**tv, "includeItemTypes": "Series"})
    out["filters"] = filters.json()
    out["filters2_keys"] = sorted(filters2)
    report.note(f"Filters：{filters.json()}；Filters2 的鍵：{sorted(filters2)}")
    years = {}
    for label, extra in (("不帶 includeItemTypes", {}), ("Series", {"includeItemTypes": "Series"})):
        rows = srv.json(api, "/Years", params={**tv, "recursive": "true", **extra})["Items"]
        years[label] = [r["Name"] for r in rows]
    out["years"] = years
    report.note(f"/Years：{years}")

    latest = srv.json(api, "/Items/Latest", params=tv)
    out["latest_default"] = [f"{r['Type']}:{c.describe(r)}" for r in latest]
    report.note(f"/Items/Latest?parentId=TV 預設：{out['latest_default']}")

    tag = c.image_tags[alpha]
    resized = {"fillWidth": "100", "quality": "90", "format": "Webp", "tag": tag}
    origin = {"Origin": "http://berth.invalid"}
    # (標籤, 查詢, 額外標頭, 錄成哪個 fixture)。CORS 標頭只在帶 Origin 的請求上才會出現。
    variants: list[tuple[str, dict[str, str], dict[str, str], str | None]] = [
        ("no tag", {}, {}, "images-primary.no-tag.headers.json"),
        ("tag", {"tag": tag}, {}, "images-primary.tag.headers.json"),
        ("wrong tag", {"tag": "0" * 32}, {}, None),
        ("fillWidth=100&quality=90&format=Webp", resized, {},
         "images-primary.resized.headers.json"),
        ("tag + Origin", {"tag": tag}, origin, None),
    ]  # fmt: skip
    wanted = ("Content-Type", "Content-Length", "Cache-Control", "ETag", "Last-Modified")
    images: dict[str, Any] = {}
    for label, params, extra_headers, fixture in variants:
        url = f"{srv.base}/Items/{alpha}/Images/Primary"
        resp = request(url, params=params, headers=extra_headers)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        shown = {k: headers.get(k.lower()) for k in (*wanted, "Access-Control-Allow-Origin")}
        images[label] = {"status": resp.status, "bytes": len(resp.body), **shown}
        if fixture:
            fixtures.write(fixture, resp)
    banner = srv.send(ANONYMOUS, f"/Items/{alpha}/Images/Banner")
    images["Banner（沒有這種圖）"] = {"status": banner.status}
    out["images"] = images
    report.note(f"圖片（匿名）：{images}")

    token = api.token or ""
    legacy_auth = {
        "X-Emby-Token": request(f"{srv.base}/Items", params=user, headers={"X-Emby-Token": token}),
        "api_key=": request(f"{srv.base}/Items", params={**user, "api_key": token}),
    }
    out["legacy_auth"] = {k: v.status for k, v in legacy_auth.items()}
    report.note(f"舊式驗證：{out['legacy_auth']}")
    report.record("regression", out)


def record_browsing(
    srv: Server, api: Credential, c: Catalog, user_id: str, fixtures: Fixtures
) -> None:
    """瀏覽要用、但上面沒順手錄到的回應。參數照 jellyfin-web（研究 §7）。"""
    wall = {
        "userId": user_id,
        "recursive": "true",
        "sortBy": "SortName",
        "sortOrder": "Ascending",
        "fields": "PrimaryImageAspectRatio,ProviderIds,Path",
        "imageTypeLimit": "1",
        "enableImageTypes": "Primary,Backdrop,Thumb",
        "startIndex": "0",
        "limit": "100",
    }
    for name, library, kind in (
        ("items.tv.series.userdata.json", "TV", "Series"),
        ("items.movies.movie.userdata.json", "Movies", "Movie"),
    ):
        params = {**wall, "parentId": c.libraries[library], "includeItemTypes": kind}
        fixtures.write(name, srv.send(api, "/Items", params=params))
    tv_series = {"parentId": c.libraries["TV"], "includeItemTypes": "Series"}
    # 牆的第二頁（M1.5 票 03）：整份 4 部，`startIndex=1&limit=2` 要恰好是第 2、3 部。
    page = {**wall, **tv_series, "startIndex": "1", "limit": "2"}
    fixtures.write("items.tv.series.page.json", srv.send(api, "/Items", params=page))
    # Berth 端比對用的整份索引（票 03）：只要 id、名稱、年份與 TMDB id，觀看紀錄不要；
    # 圖只要 Primary 的 tag（票 04：篩選後的牆從這一份畫海報）。
    index = {
        "userId": user_id,
        "recursive": "true",
        **tv_series,
        "fields": "ProviderIds",
        "imageTypeLimit": "1",
        "enableImageTypes": "Primary",
        "enableUserData": "false",
        "enableTotalRecordCount": "false",
    }
    fixtures.write("items.tv.series.index.json", srv.send(api, "/Items", params=index))
    # 排序與篩選（M1.5 票 06）：牆的查詢加上一個參數。每一份都要與名稱順序的那一份不同，
    # 才證明得了伺服器真的照它排或篩（`/Items` 靜默忽略打錯的參數）。
    rating = {**wall, **tv_series, "sortBy": "CommunityRating,SortName"}
    for name, params in (
        ("items.tv.series.sort-rating.ascending.json", rating),
        ("items.tv.series.sort-rating.descending.json", {**rating, "sortOrder": "Descending"}),
        ("items.tv.series.genres.json", {**wall, **tv_series, "genres": "Drama|Comedy"}),
        ("items.tv.series.years.json", {**wall, **tv_series, "years": "2020,2023"}),
    ):
        fixtures.write(name, srv.send(api, "/Items", params=params))
    # 電影庫的排序鍵後面接 `SortName,ProductionYear`（jellyfin-web `movies.js`）；`DatePlayed`
    # 只在電影庫的選單上，研究 §3.1 原本沒驗。
    played = {
        **wall,
        "parentId": c.libraries["Movies"],
        "includeItemTypes": "Movie",
        "sortBy": "DatePlayed,SortName,ProductionYear",
        "sortOrder": "Descending",
    }
    resp = srv.send(api, "/Items", params=played)
    fixtures.write("items.movies.movie.sort-dateplayed.descending.json", resp)
    alpha = c.title_id("TV", "Alpha Show")
    user = {"userId": user_id}
    seasons = {**user, "fields": "ItemCounts,PrimaryImageAspectRatio"}
    fixtures.write("shows-seasons.json", srv.send(api, f"/Shows/{alpha}/Seasons", params=seasons))
    season_one = c.season("TV", "Alpha Show", 1)
    episodes = {**user, "seasonId": season_one, "fields": "Overview,PrimaryImageAspectRatio"}
    resp = srv.send(api, f"/Shows/{alpha}/Episodes", params=episodes)
    fixtures.write("shows-episodes.json", resp)
    record_watching(srv, api, c, user_id, fixtures)
    record_title_watch(srv, api, c, user_id, fixtures)


def record_watching(
    srv: Server, api: Credential, c: Catalog, user_id: str, fixtures: Fixtures
) -> None:
    """繼續觀看與下一集（M1.5 票 07）：參數照 jellyfin-web 首頁（`resume.ts`、`nextUp.ts`，
    研究 §7），每個過濾參數另錄一份拿掉或換值的，證明伺服器真的照它過濾。

    - Resume 不帶 `mediaTypes=Video` 會混進 Season 與 Series（研究 §1.2）。
    - `parentId` 只放允許清單上的媒體庫：Resume 帶 TV 就沒有 Movies 的那部片，NextUp 帶 Movies
      是空的。
    - `nextUpDateCutoff`：jellyfin-web 送「今天減使用者設定的天數」（預設 365）。Alpha 最後看的日期
      （2026-01-01）早於 2026-02-15、Bravo（2026-03-01）晚於它。
    """
    images = {"imageTypeLimit": "1", "enableImageTypes": "Primary,Backdrop,Thumb"}
    resume = {
        "userId": user_id,
        "limit": "12",
        **images,
        "enableTotalRecordCount": "false",
        "mediaTypes": "Video",
    }
    mixed = {key: value for key, value in resume.items() if key != "mediaTypes"}
    tv = {**resume, "parentId": c.libraries["TV"]}
    for name, params in (
        ("useritems-resume.watching.json", resume),
        ("useritems-resume.watching.mixed.json", mixed),
        ("useritems-resume.watching.tv.json", tv),
    ):
        fixtures.write(name, srv.send(api, "/UserItems/Resume", params=params))
    year_ago = datetime.now(UTC) - timedelta(days=365)
    next_up = {
        "userId": user_id,
        "limit": "24",
        **images,
        "enableTotalRecordCount": "false",
        "enableResumable": "false",
        "nextUpDateCutoff": year_ago.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
    for name, params in (
        ("shows-nextup.watching.json", next_up),
        ("shows-nextup.watching.cutoff.json", {**next_up, "nextUpDateCutoff": NEXT_UP_CUTOFF}),
        ("shows-nextup.watching.movies.json", {**next_up, "parentId": c.libraries["Movies"]}),
    ):
        fixtures.write(name, srv.send(api, "/Shows/NextUp", params=params))


def record_title_watch(
    srv: Server, api: Credential, c: Catalog, user_id: str, fixtures: Fixtures
) -> None:
    """Media 詳情的觀看區（M1.5 票 08）：由 TMDB id 找作品、確認看得到、這部劇的下一集。

    - 找作品不帶 `parentId`（研究 §10）：TV 的 Frieren 在、Anime 的那一份不在，沒有 TMDB id 的
      Hotel Show 不在（`hasTmdbId` 真的有過濾）。
    - `/Items/{id}` 不必 `fields` 就帶 `ProviderIds` 與 `UserData`（v12.0 `new DtoOptions()`）。
    - 帶 `seriesId` 的 NextUp 用伺服器預設（jellyfin-web 劇集頁同樣不送 `enableResumable`）：
      Alpha 看過 E01 → E02；Frieren E01 看到一半 → 回 E01 與它的位置；Hotel 沒看過 → S01E01。
    """
    user = {"userId": user_id}
    lookup = {
        **user,
        "recursive": "true",
        "includeItemTypes": "Series",
        "hasTmdbId": "true",
        "fields": "ProviderIds",
        "enableImages": "false",
        "enableUserData": "false",
    }
    fixtures.write("items.tmdb-lookup.series.json", srv.send(api, "/Items", params=lookup))
    for name, library, title in (
        ("items-id.series.json", "TV", "Alpha Show"),
        ("items-id.movie.json", "Movies", "Foxtrot Movie"),
    ):
        path = f"/Items/{c.title_id(library, title)}"
        fixtures.write(name, srv.send(api, path, params=user))
    for name, title in (
        ("shows-nextup.series.json", "Alpha Show"),
        ("shows-nextup.series.resumable.json", "Frieren"),
        ("shows-nextup.series.unwatched.json", "Hotel Show"),
    ):
        params = {**user, "seriesId": c.title_id("TV", title)}
        fixtures.write(name, srv.send(api, "/Shows/NextUp", params=params))


# --- main ------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18396)
    parser.add_argument("--workdir", type=Path, default=None, help="預設是系統暫存目錄下的新目錄")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--record", action="store_true", help="重錄 tests/fixtures/http/jellyfin/")
    parser.add_argument(
        "--only",
        default="",
        help="搭配 --record：只寫這幾個 fixture（逗號分隔的檔名），其餘不動",
    )
    parser.add_argument("--keep", action="store_true", help="跑完不刪容器與工作目錄")
    args = parser.parse_args()

    image = compose_image()
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="berth-jellyfin-permissions-"))
    report = Report(name="jellyfin-permissions", out_dir=args.out)
    fixtures = Fixtures(args.record, frozenset(filter(None, args.only.split(","))))
    report.heading(f"Jellyfin 受限使用者權限實測（{image}）")

    with disposable_jellyfin(workdir, image, args.port, args.keep, report) as base:
        # `/System/Info/Public` 在伺服器還在載入時就回 200，精靈的端點這時是 503。
        startup = f"{base}/Startup/Configuration"
        poll(lambda: request(startup, timeout=5).ok, what="Jellyfin 載入完成", timeout=300)
        setup = Jellyfin(base, "permissions")
        setup.run_startup(report)
        srv = Server(base)
        admin = Credential("admin", setup.token)
        srv.json(admin, "/Auth/Keys", method="POST", params={"app": API_KEY_APP})
        keys = srv.json(admin, "/Auth/Keys")["Items"]
        key = next(k["AccessToken"] for k in keys if k.get("AppName") == API_KEY_APP)
        api = Credential("api key", key, "berth-exp-permissions-api")
        version = srv.json(api, "/System/Info")["Version"]
        if args.record and version != RECORDED_VERSION:
            report.note(f"伺服器是 {version}，fixture 是 {RECORDED_VERSION} 錄的：換版本要開新檔名")
            return 1

        for name, collection_type in LIBRARIES.items():
            create_library(srv, admin, name, collection_type)
        report.note(f"掃描完成，共 {setup.wait_for_scan()} 個 item")
        catalog: Catalog = poll(lambda: discover(srv, api), what="媒體樹全部出現", timeout=300)
        problems = check_metadata(srv, api, catalog, str(setup.user_id))
        for line in problems:
            report.note(f"NFO 沒有照預期讀進來：{line}")
        if problems:
            report.write()
            return 1
        report.record("catalog", {label: item for item, label in catalog.labels.items()})

        body = {"Name": LIMITED, "Password": PASSWORD}
        user_id = str(srv.json(admin, "/Users/New", method="POST", json_body=body)["Id"])
        seed_user_data(srv, api, catalog, user_id)
        allowed = [catalog.libraries[n] for n in ALLOWED]
        set_policy(srv, admin, user_id, EnableAllFolders=False, EnabledFolders=allowed)
        device = "berth-exp-permissions-limited"
        user = Credential("user", srv.login(device).json()["AccessToken"], device)
        report.note(f"受限使用者 {LIMITED}（{user_id}）只開放 {ALLOWED}，{FORBIDDEN} 沒有權限")

        creds = (api, user)
        run_matrix(srv, creds, catalog, user_id, report, fixtures)
        run_filters(srv, api, catalog, user_id, report)
        run_sorts(srv, api, catalog, user_id, report)
        run_tmdb_lookup(srv, api, catalog, user_id, report)
        record_browsing(srv, api, catalog, user_id, fixtures)
        run_regression(srv, api, catalog, user_id, report, fixtures)
        run_played_recursion(srv, api, catalog, user_id, report, fixtures)
        run_disabled(srv, admin, creds, catalog, user_id, report, fixtures)
    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
