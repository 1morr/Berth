"""用真的 mediainfo 時長對真的 TMDB `runtime`（分鐘）量一次比值與秒數差，替片長驗證（M3 票 15、
`berth/parser/runtime.py` 的 `RUNTIME_SLACK` / `RUNTIME_RATIO`）定門檻。真的量到的是對得上的
正片與兩支外傳；兩集合併檔是拿相鄰兩集的真實片長相加模擬的，NCOP / SP 沒有量到。

`tests/fixtures/parser/*/*.json` 這份解析器 benchmark 只有檔案清單與期望結果，沒有時長；
`tests/fixtures/tmdb/<tmdb>.json`（`tmdb` 欄位值就是檔名）凍結了每集的 `runtime`（分鐘，
可能是 null）。時長的真實資料來自 AnimeTosho（索引 Nyaa 的種子，對它處理過的每個檔案存一份
mediainfo，`https://animetosho.org/file/<file_id>` 頁面裡的 `#file_addinfo` 區塊）。

**AnimeTosho 對多檔（批次）種子常常沒有 mediainfo**：這次實測確認，`show=torrent&nyaa_id=`
對批次種子（哪怕沒被標記重複、沒被刪除）經常直接回 `status: "skipped"`、完全沒有 `files[]`；
只有單檔種子穩定回得來（`my-hero-academia-139-subsplease`、`spy-x-family-05-subsplease` 兩個
fixture 本身的種子屬於這種）。因此本腳本對批次類的 fixture **改用同一部作品、同一段集數的
另一個發佈**（AT 上狀態是 `complete` 的）取代 fixture 字面上的那個種子——集數對得上、內容是
同一段正片，但不是 fixture JSON 裡記的那個確切檔案／字幕組／編碼；每一筆都在 `RESOLUTIONS`
裡用 `is_alt=True` 標起來並寫清楚原因。找不到任何堪用替代（`mizuiro-jidai-shincaps`：字面
種子回 HTTP 404，AT 在它發佈之後就停止索引了；真人劇/電影 fixture：AT 只收動漫）的直接跳過，
不硬湊。

**AnimeTosho 即將關站**（首頁公告 2026 年 10 月初到中旬停止服務）：這份腳本抓到的原始 JSON／
HTML 快取在 `.local/experiments/cache/runtime_gap/`，之後 AT 關站也還能重跑分析；但要擴大
樣本（目前時間盒內只解到 8 部作品／約 90 個檔案，還有若干 fixture 沒去查，見 `SKIPPED_SHOWS`）
要趁現在。

只用標準庫、不 import `berth`，可以搬到別台機器上跑；只讀本地 fixture、
只打 AnimeTosho 的公開端點（不需要任何憑證），不下載任何影片內容：

    python scripts/experiments/runtime_gap.py
"""

from __future__ import annotations

import hashlib
import html
import http.client
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "parser"
TMDB_FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "tmdb"
#: 抓過的東西留在磁碟上：AnimeTosho 的搜尋與種子頁一次要好幾秒，逐檔的 mediainfo 頁又是
#: 另一次請求，重跑分析不該再等一次；AT 關站後這份快取也還能重跑分析。
CACHE_DIR = REPO_ROOT / ".local" / "experiments" / "cache" / "runtime_gap"
UA = "berth-research/0.1 (+https://github.com/1morr/Berth)"

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".ts", ".wmv", ".mov", ".m2ts"}


# --------------------------------------------------------------------------------------
# 抓資料、快取
# --------------------------------------------------------------------------------------


def fetch(url: str, *, retries: int = 5) -> bytes:
    cached = CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".bin")
    if cached.exists():
        return cached.read_bytes()
    body = _fetch_uncached(url, retries=retries)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(body)
    return body


#: 逐檔打 mediainfo 頁面很容易連續觸發 AnimeTosho 的限速（429），每次真的發請求前都先
#: 停一下，比事後重試便宜也更禮貌。
_MIN_REQUEST_INTERVAL = 0.5
_last_request_at = 0.0


def _pace() -> None:
    global _last_request_at
    wait = _last_request_at + _MIN_REQUEST_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _fetch_uncached(url: str, *, retries: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last: Exception | None = None
    for attempt in range(retries):
        _pace()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return bytes(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                # 太快打站被限速，退避重試；不能當成最終答案快取起來，不然這個 429 頁面會
                # 被誤當成「這個 URL 就長這樣」永久記住（第一版腳本踩過這個坑）。
                retry_after = exc.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 5 * (attempt + 1)
                )
                last = exc
                time.sleep(wait)
                continue
            # 其他 4xx/5xx（例如 404）是 AT 本身就沒有這筆資料（例如 mizuiro-jidai-shincaps：
            # 種子是 AT 停止索引之後才發的），不是暫時性錯誤，重試沒有意義。把錯誤內容原樣
            # 快取起來，呼叫端自己判斷（json 解不出來、或 status 不是 complete 就跳過）。
            return exc.read()
        except (OSError, http.client.HTTPException) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"抓不到 {url}: {last}")


def at_torrent(nyaa_id: int) -> dict[str, Any]:
    url = f"https://feed.animetosho.org/json?show=torrent&nyaa_id={nyaa_id}"
    found: dict[str, Any] = json.loads(fetch(url))
    return found


# --------------------------------------------------------------------------------------
# mediainfo 頁面解析
# --------------------------------------------------------------------------------------

_ADDINFO_RE = re.compile(r'id="file_addinfo"[^>]*>(.*?)</div>', re.S)


def parse_mediainfo(page_html: str) -> dict[str, dict[str, str]]:
    """`https://animetosho.org/file/<id>` 頁面裡 `#file_addinfo` 那個 div，逐行按第一個冒號
    切成 key/value，section 用沒有冒號的那幾行（General / Video / Audio / Text）分界。回傳
    `{section: {key: value}}`。"""
    match = _ADDINFO_RE.search(page_html)
    if not match:
        return {}
    sections: dict[str, dict[str, str]] = {}
    current = "General"
    for raw_line in match.group(1).split("<br />"):
        line = html.unescape(raw_line).strip()
        if not line:
            continue
        if ":" not in line:
            current = line
            sections.setdefault(current, {})
            continue
        key, _, value = line.partition(":")
        sections.setdefault(current, {})[key.strip()] = value.strip()
    return sections


def file_mediainfo(file_id: int) -> dict[str, dict[str, str]]:
    page = fetch(f"https://animetosho.org/file/{file_id}").decode("utf-8", "replace")
    return parse_mediainfo(page)


_HMS_RE = re.compile(r"^(\d+):(\d{2}):(\d{2})(?:\.(\d+))?$")
_HUMAN_RE = re.compile(r"(?:(?P<h>\d+)\s*h)?\s*(?:(?P<min>\d+)\s*min)?\s*(?:(?P<s>\d+)\s*s)?")


def _hms_to_seconds(text: str) -> float | None:
    """`FromStats_Duration` 的形狀：`HH:MM:SS.ffffffff`（逐幀統計出來的，比 General 區塊
    人類可讀的『23 min 50 s』精確到毫秒）。"""
    match = _HMS_RE.match(text.strip())
    if not match:
        return None
    h, mi, s, frac = match.groups()
    total = int(h) * 3600 + int(mi) * 60 + int(s)
    if frac:
        total += int(frac) / (10 ** len(frac))
    return float(total)


def _human_to_seconds(text: str) -> float | None:
    """General 區塊的 `Duration`：`1 h 2 min 3 s` 這種，任一段都可能缺（例如 `23 min 50 s`
    沒有小時）。"""
    match = _HUMAN_RE.match(text.strip())
    if not match or not any(match.groups()):
        return None
    h = int(match.group("h") or 0)
    mi = int(match.group("min") or 0)
    s = int(match.group("s") or 0)
    if h == 0 and mi == 0 and s == 0:
        return None
    return float(h * 3600 + mi * 60 + s)


def measured_seconds(sections: dict[str, dict[str, str]]) -> float | None:
    """量測用的時長（秒）。優先 Video 軌的 `FromStats_Duration`：它是逐幀統計出來的，代表
    影片串流本身，最接近 mediainfo 驗證實際會拿來比對的那個數字；Video 軌沒有這個欄位時退
    而求其次用 General 區塊人類可讀的 `Duration` 文字。"""
    video = sections.get("Video", {})
    if "FromStats_Duration" in video:
        seconds = _hms_to_seconds(video["FromStats_Duration"])
        if seconds is not None:
            return seconds
    general = sections.get("General", {})
    if "Duration" in general:
        return _human_to_seconds(general["Duration"])
    return None


# --------------------------------------------------------------------------------------
# fixture / TMDB 讀取（本地，唯讀）
# --------------------------------------------------------------------------------------


def load_tmdb(tmdb_key: str) -> dict[str, Any]:
    path = TMDB_FIXTURES_DIR / f"{tmdb_key}.json"
    found: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return found


def episode_runtime_minutes(tmdb: dict[str, Any], season: int, episode: int) -> int | None:
    for s in tmdb["seasons"]:
        if s["season_number"] == season:
            for e in s["episodes"]:
                if e["episode_number"] == episode:
                    runtime = e.get("runtime")
                    return runtime if isinstance(runtime, int) else None
    return None


def season_first_episode(tmdb: dict[str, Any], season: int) -> int | None:
    """這一季 TMDB 記的最小集號。多數作品是 1，但像 One Piece 這種長壽番，TMDB 把每一季切
    成連續播出的一段，集號直接沿用全劇累計的絕對集數（例如 season 22 是 1089-1155），不是
    從 1 開始——『被誤判成這季第一集』的基準要用這個，不能寫死 1。"""
    for s in tmdb["seasons"]:
        if s["season_number"] == season:
            numbers = [e["episode_number"] for e in s["episodes"]]
            return min(numbers) if numbers else None
    return None


# --------------------------------------------------------------------------------------
# 每部作品怎麼從 AnimeTosho 對回 TMDB 集數
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ShowResolution:
    label: str
    #: 對應的 fixture id（可能不只一個共用同一個替代發佈，用 " / " 接起來只是註記用途）。
    fixtures: str
    tmdb: str
    nyaa_id: int
    is_alt: bool
    note: str
    season: int
    #: 有兩種取集數的方式：只有一個檔案時用 `single_episode`；批次用 `episode_regex`
    #: 對檔名取出數字（group 1），加上 `offset` 換成 TMDB 集號。
    single_episode: int | None = None
    episode_regex: re.Pattern[str] | None = None
    offset: int = 0


RESOLUTIONS: tuple[ShowResolution, ...] = (
    ShowResolution(
        label="My Hero Academia 139",
        fixtures="my-hero-academia-139-subsplease",
        tmdb="tv-65930",
        nyaa_id=1814011,
        is_alt=False,
        note="fixture 本身的種子，單檔，AT 直接有 mediainfo",
        season=7,
        single_episode=1,
    ),
    ShowResolution(
        label="Spy x Family 05",
        fixtures="spy-x-family-05-subsplease",
        tmdb="tv-120089",
        nyaa_id=1525282,
        is_alt=False,
        note="fixture 本身的種子，單檔，AT 直接有 mediainfo",
        season=1,
        single_episode=5,
    ),
    ShowResolution(
        label="Overlord S2 (01-13)",
        fixtures="overlord-s2-dbd-raws",
        tmdb="tv-64196",
        nyaa_id=1138165,
        is_alt=True,
        note=(
            "fixture 本身的 DBD-Raws 批次種子在 AT 上被標記為 skipped（AT 對批次種子常見的"
            "限制，見模組說明）；改用同一部作品另一個 BDRip 批次（[Anime Land]），同樣 13 集"
            "正片，但缺原批次裡的 NCOP/NCED/PV/SP/menu 額外檔案，這些拿不到真實時長"
        ),
        season=2,
        episode_regex=re.compile(r"^(\d{2}) -"),
    ),
    ShowResolution(
        label="Frieren S1 (01-28)",
        fixtures="frieren-7acg-bd-batch",
        tmdb="tv-209867",
        nyaa_id=1859137,
        is_alt=True,
        note=(
            "fixture 本身種子未被 AT 索引；改用另一個 BDRip 批次（[EMBER]），同樣 28 集正片，"
            "但缺原批次裡的 S00（特典，11 個檔案）——而且 TMDB 這部作品的 season 0『Specials』"
            "其實是另一組 1-2 分鐘的短篇，跟字幕組批次裡的 S00E01-11 特典完全不是同一批內容，"
            "就算拿得到特典的真實時長也不能拿 TMDB season 0 直接對，這裡就不硬湊"
        ),
        season=1,
        episode_regex=re.compile(r"S01E(\d+)-"),
    ),
    ShowResolution(
        label="One Piece 1089-1104",
        fixtures="one-piece-1089-1104-erai",
        tmdb="tv-37854",
        nyaa_id=1818405,
        is_alt=True,
        note=(
            "fixture 本身種子（nyaa_id=1818402）被標記為 skipped；改用同一個 Erai-raws 批次"
            "的 1080p/HEVC 版本（AT 上是 complete），16 集正片，另外 2 個特別篇跟 fixture"
            "expected[] 裡的 unmatched 額外檔案同名（Innen no Log / Dai Tannou Kikaku），"
            "當成真的『誤判候選』資料點"
        ),
        season=22,
        episode_regex=re.compile(r"One Piece - (\d{4})\b"),
    ),
    ShowResolution(
        label="Bleach TYBW Soukoku-tan (27-40)",
        fixtures="bleach-tybw-soukoku-tan-erai",
        tmdb="tv-30984",
        nyaa_id=2001967,
        is_alt=True,
        note=(
            "fixture 本身種子（nyaa_id=1950688）被標記為 skipped；改用另一個批次發佈"
            "（[ADC]），14 集正片，track 01-14 對應 TMDB season 2 episode 27-40"
            "（fixture expected[] 逐筆核對過的對應關係）"
        ),
        season=2,
        episode_regex=re.compile(r"Soukoku Tan (\d+) -"),
        offset=26,
    ),
    ShowResolution(
        label="Pokemon Horizons 135",
        fixtures="pokemon-horizons-fysub",
        tmdb="tv-220150",
        nyaa_id=2102880,
        is_alt=True,
        note="fixture 本身種子（dmhy 來源）AT 無索引；改用同一集的另一個單集發佈",
        season=1,
        single_episode=135,
    ),
    ShowResolution(
        label="Spy x Family S3 (01-13)",
        fixtures="spy-x-family-s3-ani (13) / spy-x-family-s3-dynamis (10)",
        tmdb="tv-120089",
        nyaa_id=2073926,
        is_alt=True,
        note=(
            "兩個 fixture（各自只要 S03E13、S03E10）本身種子都是 acg.rip 來源，AT 無索引；"
            "改用同一季的 [Judas] 批次（complete），13 集正片一次量到，含這兩張票各自需要"
            "的那一集"
        ),
        season=3,
        episode_regex=re.compile(r"S03E(\d+)v?\d*\.mkv$"),
    ),
)

#: 查過但這次時間盒內沒能解到具體檔案／確認拿不到的 fixture，附原因，供下次擴充。
SKIPPED_SHOWS: tuple[tuple[str, str], ...] = (
    (
        "mizuiro-jidai-shincaps",
        "字面種子（nyaa_id=2157786）直接對 AT 回 HTTP 404 Not Found——AT 公告 2026-05-09 之後"
        "停止更新索引，這個種子的發佈時間晚於那個時間點，確認是真的拿不到，不是暫時性錯誤",
    ),
    (
        "your-name-bdmv",
        "BDMV 光碟結構（M2TS + 選單），fixture 沒有季集資訊可對，AT 也不收這種發佈形式",
    ),
    (
        "12 個真人劇/電影 fixture（thepiratebay.org、部分 dmhy 來源）",
        "AnimeTosho 只收動漫，這些從一開始就不在它的索引範圍內",
    ),
    (
        "mushoku-tensei-s2-02-sakurato / mushoku-tensei-s3-comicat / mushoku-tensei-s3-kitauji",
        "無職轉生字幕組的『第幾季』編號與 TMDB 的季數切法對不齊（TMDB 把兩輪播出算進同一季，"
        "不同字幕組對『第二部』『Part 2』算不算獨立一季又不一致），AT 搜尋到的候選標的季數"
        "無法在不逐一人工核對播出集數的情況下安全對應，這次時間盒內選擇不硬猜，跳過",
    ),
    (
        "demon-slayer-hashira-uha / dragon-ball-daima-ktxp / kamiina-botan-chiyanabi / "
        "rezero-lolihouse-v2",
        "AT 搜尋有找到疑似候選（見 .local/experiments/cache/runtime_gap/ 裡的搜尋結果），"
        "但這次時間盒內沒有逐一drill down 到確切的 nyaa_id／檔案層級，留給下次擴充",
    ),
)


# --------------------------------------------------------------------------------------
# 量測
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EpisodeMeasurement:
    show: str
    filename: str
    tmdb: str
    season: int
    episode: int
    seconds: float
    is_alt: bool


@dataclass(frozen=True)
class ExtraMeasurement:
    show: str
    filename: str
    tmdb: str
    #: 如果被誤判成這一季第一集正片，要拿哪一集的 TMDB runtime 當基準。
    baseline_season: int
    seconds: float
    is_alt: bool


def resolve(res: ShowResolution) -> tuple[list[EpisodeMeasurement], list[ExtraMeasurement]]:
    data = at_torrent(res.nyaa_id)
    status = data.get("status")
    if status != "complete":
        print(
            f"  [WARN] {res.label}: AT status={status!r}（非 complete），整個略過", file=sys.stderr
        )
        return [], []

    regulars: list[EpisodeMeasurement] = []
    extras: list[ExtraMeasurement] = []
    for f in data.get("files", []):
        filename = f["filename"]
        if Path(filename).suffix.lower() not in VIDEO_EXTS:
            continue

        episode: int | None = None
        if res.single_episode is not None:
            episode = res.single_episode
        elif res.episode_regex is not None:
            m = res.episode_regex.search(filename)
            if m:
                episode = int(m.group(1)) + res.offset

        sections = file_mediainfo(f["id"])
        seconds = measured_seconds(sections)
        if seconds is None:
            print(f"  [WARN] {res.label}: {filename!r} 取不到時長，略過", file=sys.stderr)
            continue

        if episode is not None:
            regulars.append(
                EpisodeMeasurement(
                    res.label, filename, res.tmdb, res.season, episode, seconds, res.is_alt
                )
            )
        else:
            extras.append(
                ExtraMeasurement(res.label, filename, res.tmdb, res.season, seconds, res.is_alt)
            )
    return regulars, extras


# --------------------------------------------------------------------------------------
# 統計
# --------------------------------------------------------------------------------------


def _percentile(values: Sequence[float], pct: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[int(position)])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _print_distribution(label: str, values: Sequence[float], fmt: str = ".4f") -> None:
    if not values:
        print(f"{label}: (no data)")
        return
    print(
        f"{label}: n={len(values)} "
        f"min={min(values):{fmt}} p10={_percentile(values, 10):{fmt}} "
        f"p50={_percentile(values, 50):{fmt}} p90={_percentile(values, 90):{fmt}} "
        f"p99={_percentile(values, 99):{fmt}} max={max(values):{fmt}}"
    )


def trunc(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def tmdb_runtime_null_rate() -> None:
    """跟量測無關，是額外查證：per-episode TMDB runtime 到底多常是 null（決定驗證功能要不要
    留一條『查不到 runtime 就不比對』的路徑）。掃過本地所有凍結的 TMDB fixture，只讀檔案。"""
    total = 0
    null = 0
    for path in sorted(TMDB_FIXTURES_DIR.glob("*.json")):
        tmdb = json.loads(path.read_text(encoding="utf-8"))
        for season in tmdb.get("seasons", []):
            for ep in season.get("episodes", []):
                total += 1
                if ep.get("runtime") is None:
                    null += 1
    pct = (null / total * 100) if total else 0.0
    print(
        f"TMDB runtime 是 null 的比例：{null}/{total} = {pct:.1f}%"
        "（掃 tests/fixtures/tmdb/*.json 全部集數）"
    )


def main() -> int:
    print("=== 逐部作品解析 ===")
    all_regulars: list[EpisodeMeasurement] = []
    all_extras: list[ExtraMeasurement] = []
    for res in RESOLUTIONS:
        alt_tag = "ALT" if res.is_alt else "direct"
        print(f"\n[{alt_tag}] {res.label}  (nyaa_id={res.nyaa_id}, fixtures={res.fixtures})")
        print(f"  {res.note}")
        regulars, extras = resolve(res)
        print(f"  -> {len(regulars)} 集正片、{len(extras)} 個額外檔案 取得時長")
        all_regulars.extend(regulars)
        all_extras.extend(extras)

    print(f"\n跳過的 fixture（{len(SKIPPED_SHOWS)} 組，原因見下）：")
    for names, reason in SKIPPED_SHOWS:
        print(f"  - {names}: {reason}")

    # ---- 正片：ratio 與 diff ----
    print(f"\n\n=== 正片正確對應（regular episode，n={len(all_regulars)} 個檔案）===")
    ratios: list[float] = []
    diffs: list[float] = []
    tmdb_cache: dict[str, dict[str, Any]] = {}
    per_episode: list[tuple[EpisodeMeasurement, int, float, float]] = []
    for m in all_regulars:
        tmdb = tmdb_cache.setdefault(m.tmdb, load_tmdb(m.tmdb))
        runtime_min = episode_runtime_minutes(tmdb, m.season, m.episode)
        if runtime_min is None:
            print(
                f"  [WARN] {m.show} S{m.season:02d}E{m.episode:03d} 在 {m.tmdb} 找不到 runtime，"
                "跳過這筆"
            )
            continue
        expected = runtime_min * 60
        ratio = m.seconds / expected
        diff = m.seconds - expected
        ratios.append(ratio)
        diffs.append(diff)
        per_episode.append((m, runtime_min, ratio, diff))

    _print_distribution("ratio (measured / tmdb_runtime*60)", ratios)
    _print_distribution("diff seconds (measured - tmdb_runtime*60)", diffs, fmt=".1f")

    print("\n每筆明細：")
    for m, runtime_min, ratio, diff in per_episode:
        print(
            f"  {trunc(m.show, 26):<26} S{m.season:02d}E{m.episode:03d} "
            f"measured={m.seconds:8.1f}s  tmdb={runtime_min:3d}min={runtime_min * 60:5d}s  "
            f"ratio={ratio:.4f}  diff={diff:+7.1f}s  {'[ALT]' if m.is_alt else ''}"
        )

    # ---- 額外檔案：真的量到的 unmatched/extra，與『被誤判成第一集正片』的假設 ----
    print(f"\n\n=== 額外檔案（真的量到時長，n={len(all_extras)}）===")
    hypo_ratios: list[float] = []
    hypo_diffs: list[float] = []
    for x in all_extras:
        tmdb = tmdb_cache.setdefault(x.tmdb, load_tmdb(x.tmdb))
        baseline_ep = season_first_episode(tmdb, x.baseline_season)
        print(f"  {trunc(x.show, 26):<26} {trunc(x.filename, 70)}")
        print(f"      真實時長 = {x.seconds:.1f}s", end="")
        if baseline_ep is None:
            print(f"  (baseline S{x.baseline_season:02d} 查無任何集數資料)")
            continue
        baseline_min = episode_runtime_minutes(tmdb, x.baseline_season, baseline_ep)
        if baseline_min is None:
            print(f"  (baseline S{x.baseline_season:02d}E{baseline_ep:03d} runtime 查無資料)")
            continue
        expected = baseline_min * 60
        ratio = x.seconds / expected
        diff = x.seconds - expected
        hypo_ratios.append(ratio)
        hypo_diffs.append(diff)
        print(
            f"  | 若被誤判成 S{x.baseline_season:02d}E{baseline_ep:03d} 正片"
            f"（tmdb={baseline_min}min={expected:.0f}s）: ratio={ratio:.4f} diff={diff:+.1f}s"
        )
    if hypo_ratios:
        print()
        _print_distribution("hypothetical ratio（額外檔案 vs 被誤判的那一集）", hypo_ratios)
        _print_distribution("hypothetical diff seconds", hypo_diffs, fmt=".1f")

    # ---- 合併多集：拿兩個真實相鄰正片的時長加總，模擬「兩集被誤判成一個檔案只對到第一集」 ----
    print("\n\n=== 假設合併集（相鄰兩集正片時長相加，模擬合併檔誤判成單集）===")
    merged_ratios: list[float] = []
    merged_diffs: list[float] = []
    by_show_season: dict[tuple[str, int], dict[int, tuple[float, str]]] = {}
    for m in all_regulars:
        by_show_season.setdefault((m.show, m.season), {})[m.episode] = (m.seconds, m.tmdb)
    merged_examples: list[str] = []
    for (show, season), eps in by_show_season.items():
        for ep in sorted(eps):
            if ep + 1 not in eps:
                continue
            sec_a, tmdb_key = eps[ep]
            sec_b, _ = eps[ep + 1]
            tmdb = tmdb_cache.setdefault(tmdb_key, load_tmdb(tmdb_key))
            runtime_min = episode_runtime_minutes(tmdb, season, ep)
            if runtime_min is None:
                continue
            expected = runtime_min * 60
            merged_seconds = sec_a + sec_b
            ratio = merged_seconds / expected
            diff = merged_seconds - expected
            merged_ratios.append(ratio)
            merged_diffs.append(diff)
            merged_examples.append(
                f"  {trunc(show, 26):<26} S{season:02d}E{ep:03d}+E{ep + 1:03d} "
                f"merged={merged_seconds:.1f}s  vs single-ep tmdb={expected:.0f}s  "
                f"ratio={ratio:.4f} diff={diff:+.1f}s"
            )
    _print_distribution("merged-pair ratio", merged_ratios)
    _print_distribution("merged-pair diff seconds", merged_diffs, fmt=".1f")
    print(f"（共 {len(merged_examples)} 組相鄰集數，只列前 5 組與後 5 組）")
    for line in merged_examples[:5]:
        print(line)
    if len(merged_examples) > 10:
        print("  ...")
    for line in merged_examples[-5:]:
        print(line)

    # ---- TMDB runtime null 比例 ----
    print("\n\n=== TMDB runtime null 比例（額外查證，跟量測無關）===")
    tmdb_runtime_null_rate()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
