#!/usr/bin/env python3
"""M1 票 01：量化字幕組編號換算到三種季集來源的失敗率（brief §10、§20.6）。

三種來源：
  A. TMDB 季集（Berth 現況）
  B. TVDB default(aired) season
  C. TVDB absolute

只用標準庫，不 import `berth`，跟 `scripts/experiments/` 其他腳本一樣可以搬到別台機器跑。
TMDB 憑證讀環境變數 `TMDB_API_KEY`（v3 API key 或 v4 read access token 都可以，與 Berth 收的
兩種形狀一致）——Berth 不內建任何 provider 的 key，腳本也一樣（票 02b）。
TVDB 資料走 Sonarr 的 Skyhook 代理（免 key，見 research 文件的「資料來源」一節）。
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import http.client
import itertools
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TMDB_BASE = "https://api.themoviedb.org/3"
SKYHOOK_BASE = "https://skyhook.sonarr.tv/v1/tvdb/shows/en"
UA = "berth-research/0.1 (+https://github.com/1morr/Berth)"

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / ".local" / "experiments" / "results"


def tmdb_token() -> str:
    """使用者自備的憑證，從環境變數讀（票 02b）。"""
    token = os.environ.get("TMDB_API_KEY", "").strip()
    if not token:
        raise SystemExit(
            "請先設好 TMDB_API_KEY（themoviedb.org → 設定 → API 申請，v3 key 或 v4 token 都可以）"
        )
    return token


#: 抓過的東西留在磁碟上。Mikan 的搜尋頁一次要一分半，重跑分析不該再等一次。
CACHE_DIR = REPO_ROOT / ".local" / "experiments" / "cache" / "anime_episode_source"


def fetch(url: str, headers: dict[str, str] | None = None, *, retries: int = 5) -> bytes:
    cached = CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".bin")
    if cached.exists():
        return cached.read_bytes()
    body = _fetch_uncached(url, headers, retries=retries)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(body)
    return body


def _fetch_uncached(url: str, headers: dict[str, str] | None, *, retries: int = 5) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return bytes(resp.read())
        except (OSError, http.client.HTTPException) as exc:
            # Mikan 的頁面動輒 500 KB 以上，連線被中途掐掉是常態（IncompleteRead、
            # WinError 10053）。這些都是 OSError 或 HTTPException 的子類，一律重試。
            last = exc
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"抓不到 {url}: {last}")


def tmdb_get(token: str, path: str, **params: str) -> Any:
    url = f"{TMDB_BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return json.loads(fetch(url, {"Authorization": f"Bearer {token}"}))


# --------------------------------------------------------------------------------------
# 樣本
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Series:
    """一部作品。`shapes` 是這部作品被選進樣本的理由（票要求涵蓋的四種形態）。"""

    key: str
    tmdb_id: int
    tvdb_id: int
    shapes: tuple[str, ...]
    mikan_query: str
    #: Mikan 的「番組」等於一輪播出（一個 cour），由 `--discover` 找出來後固定在這裡。
    bangumi_ids: tuple[int, ...]


# --------------------------------------------------------------------------------------
# Provider 結構
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Episode:
    """一集在某個編號體系裡的座標。`absolute` 只有 TVDB 直接給。"""

    season: int
    number: int
    air_date: str | None
    absolute: int | None = None


@dataclass
class Scheme:
    """一個候選的季集來源。`episodes` 只含正篇（season >= 1）。"""

    key: str
    episodes: list[Episode] = field(default_factory=list)

    def seasons(self) -> dict[int, list[Episode]]:
        out: dict[int, list[Episode]] = {}
        for ep in self.episodes:
            out.setdefault(ep.season, []).append(ep)
        for eps in out.values():
            eps.sort(key=lambda e: e.number)
        return out

    def aired_order(self) -> list[Episode]:
        """播出順序。air_date 缺的排在同季同集號的位置，不讓它們亂序。"""
        return sorted(self.episodes, key=lambda e: (e.air_date or "9999-99-99", e.season, e.number))


def tmdb_scheme(token: str, tmdb_id: int) -> Scheme:
    detail = tmdb_get(token, f"tv/{tmdb_id}")
    scheme = Scheme("tmdb")
    for season in detail["seasons"]:
        n = int(season["season_number"])
        if n < 1:
            continue
        data = tmdb_get(token, f"tv/{tmdb_id}/season/{n}")
        for ep in data["episodes"]:
            scheme.episodes.append(
                Episode(
                    season=n, number=int(ep["episode_number"]), air_date=ep.get("air_date") or None
                )
            )
    return scheme


def skyhook_show(tvdb_id: int) -> dict[str, Any]:
    return dict(json.loads(fetch(f"{SKYHOOK_BASE}/{tvdb_id}")))


def tvdb_schemes(show: dict[str, Any]) -> tuple[Scheme, Scheme]:
    """同一份 TVDB 資料的兩種讀法：default(aired) season，與 absolute。"""
    aired = Scheme("tvdb_aired")
    absolute = Scheme("tvdb_absolute")
    for ep in show["episodes"]:
        season = int(ep["seasonNumber"])
        if season < 1:
            continue
        air = ep.get("airDate") or None
        aired.episodes.append(
            Episode(
                season=season,
                number=int(ep["episodeNumber"]),
                air_date=air,
                absolute=ep.get("absoluteEpisodeNumber"),
            )
        )
        abs_no = ep.get("absoluteEpisodeNumber")
        if abs_no is not None:
            absolute.episodes.append(
                Episode(season=1, number=int(abs_no), air_date=air, absolute=int(abs_no))
            )
    return aired, absolute


# --------------------------------------------------------------------------------------
# 標題解析（只求「有把握才出手」，解不出來的丟掉並計入 coverage）
# --------------------------------------------------------------------------------------

MAX_EPISODE = 1500

#: 一筆合集最多展開幾集。真實的合集不會超過這個數，超過的是解析錯誤。
MAX_BATCH = 200
YEAR_LO, YEAR_HI = 1900, 2100

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
ROMAN = {"II": 2, "III": 3, "IV": 4, "V": 5}

#: 拆掉之後才找得到集號的技術標籤。順序有意義：先拆長的。
TECH = re.compile(
    r"\b(?:\d{3,4}[pP]|[xXhH]\.?26[45]|AV1|HEVC|AVC|10 ?-?bit|8 ?-?bit|FLAC|"
    r"AAC(?:x\d)?|OPUS|DDP?\d|"
    r"MP4|MKV|WEB-?DL|WEBRip|BDRip|BD-?BOX|Blu-?Ray|HDTV|Baha|Bilibili|B-?Global|CR|Sentai|MUSE|"
    r"\d+(?:\.\d+)?[Gg][Bb]|\d{3,4}x\d{3,4}|v\d)\b",
    re.I,
)
SEASON_PATTERNS = (
    re.compile(r"第\s*([一二三四五六七八九十\d]+)\s*[季期]"),
    re.compile(r"(?:^|[\s/\[])[Ss](?:eason)?\s*(\d{1,2})(?![\dPpEe])"),
    re.compile(r"\bSeason\s+(\d{1,2})\b", re.I),
)
EPISODE_PATTERNS = (
    # 第 12 话 / 第 12 集
    (re.compile(r"第\s*(\d{1,4})\s*[话話集]"), False),
    # [12] [12-24] [12v2] [01-12 END]
    (
        re.compile(
            r"[\[\【]\s*(\d{1,4})(?:\s*-\s*(\d{1,4}))?\s*(?:v\d)?\s*"
            r"(?:END|Fin|FIN|完|合集|精校合集|TV全集|全集)?\s*[\]\】]"
        ),
        True,
    ),
    # " - 12 " / " - 12 END"
    (
        re.compile(
            r"\s[-–]\s*(\d{1,4})(?:\s*-\s*(\d{1,4}))?\s*(?:v\d)?\s*(?:END|Fin|完)?\s*(?:[\[\(【]|$)"
        ),
        True,
    ),
    # "| 01-24"
    (re.compile(r"[|｜]\s*(\d{1,4})\s*-\s*(\d{1,4})"), True),
)


@dataclass(frozen=True)
class ParsedTitle:
    group: str | None
    season_hint: int | None
    first: int
    last: int


def batch_numbers(parsed: ParsedTitle) -> range:
    """一筆釋出涵蓋的集號。合集就是那麼多個檔案，所以逐集展開。"""
    return range(parsed.first, min(parsed.last, parsed.first + MAX_BATCH) + 1)


@dataclass(frozen=True)
class Release:
    """一筆釋出：解析出來的標題，加上「發佈時間對到正篇第幾集」（對不到就是 None）。

    `title` 是 Mikan 的原始標題。這一支自己用不到，M1 票 14d 的 `absolute_rule_cost.py`
    要拿它餵 Berth 的解析器，再對這裡校準出來的正解。
    """

    parsed: ParsedTitle
    published: str | None
    ordinal: int | None
    title: str


def _group_of(title: str) -> str | None:
    m = re.match(r"\s*[\[\【]([^\]\】]{1,40})[\]\】]", title)
    return m.group(1).strip() if m else None


def _season_hint(text: str) -> int | None:
    for pat in SEASON_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group(1)
            if raw.isdigit():
                return int(raw)
            if raw in CN_NUM:
                return CN_NUM[raw]
    for word, value in ROMAN.items():
        if re.search(rf"(?:^|\s)(?:{word})(?:\s|$)", text):
            return value
    return None


def parse_title(title: str) -> ParsedTitle | None:
    """解不出集號就回 None——寧可少算樣本，也不要拿解析器的錯當成編號體系的錯。

    不先切掉開頭的方括號：中文釋出常見的形狀是整串方括號
    `[字幕組][作品名][1162][ViuTV][1080p]`，切掉「開頭的方括號」等於把集號也切掉。
    集號那一格必須整格只有數字（加上 v2 / END 這類標記），所以 `[1080p]`、`[简繁]` 都不會誤中。
    """
    cleaned = TECH.sub(" ", title)
    cleaned = re.sub(
        r"[\[\【][^\]\】]*(?:字幕|双语|简|繁|内嵌|内封|外挂|招募|CHS|CHT|GB|BIG5|JP)"
        r"[^\]\】]*[\]\】]",
        " ",
        cleaned,
    )
    for pat, allow_range in EPISODE_PATTERNS:
        m = pat.search(cleaned)
        if not m:
            continue
        first = int(m.group(1))
        last = int(m.group(2)) if allow_range and m.lastindex and m.group(2) else first
        if last < first or first < 1 or last > MAX_EPISODE:
            continue
        if any(YEAR_LO <= n <= YEAR_HI for n in (first, last)):
            continue  # `[2024]` 是年份不是集號；本樣本最長的柯南也才 1212 集
        return ParsedTitle(_group_of(title), _season_hint(title), first, last)
    return None


# --------------------------------------------------------------------------------------
# 播出輪次（cour）與 provider 之間的對位
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Part:
    """一輪播出（cour）。

    錨點是**正篇序位**（TV ordinal）——「這部作品播出的第 N 集」，不是 TVDB 的 absolute
    number。兩者不一樣：TVDB 會把 OVA 與劇場版也編進 absolute（SPY×FAMILY 的劇場版
    CODE: White 就是 absolute 38），而字幕組數的是 TV 正篇。用 absolute 當錨點會憑空
    多出偏移，量到的是模型的錯不是來源的錯。
    """

    index: int
    bangumi_id: int
    start_ordinal: int
    end_ordinal: int
    start_date: str
    end_date: str
    tvdb_seasons: tuple[int, ...]
    tvdb_absolute: tuple[int, int]


def _days_between(a: str, b: str) -> int:
    from datetime import date

    ay, am, ad = (int(x) for x in a.split("-")[:3])
    by, bm, bd = (int(x) for x in b.split("-")[:3])
    return (date(by, bm, bd) - date(ay, am, ad)).days


def parts_from_bangumi(aired: Scheme, starts: list[tuple[int, str]]) -> list[Part]:
    """用 Mikan 的番組邊界切出播出輪次，不用播出日期間隔猜。

    番組就是華語圈認定的一輪播出，也正是字幕組決定「要不要把集號歸零」的那條線；
    連續兩 cour（Re:Zero 第四季的喪失篇與奪還篇之間只隔兩週）用間隔門檻切不開，
    用番組邊界就精確。門檻切法留給 `virtual_seasons`——那是 Berth 真的算得出來的東西。
    """
    ordered = sorted(starts, key=lambda row: row[1])
    buckets: dict[int, list[tuple[int, Episode]]] = {bangumi_id: [] for bangumi_id, _ in ordered}
    for ordinal, ep in enumerate(aired.aired_order(), start=1):
        if not ep.air_date:
            continue
        owner: int | None = None
        for bangumi_id, start in ordered:
            # 番組頁的放送开始偶爾比第一集早一兩天（時區、先行放送），留三天餘裕。
            if _days_between(start, ep.air_date) >= -3:
                owner = bangumi_id
            else:
                break
        if owner is not None:
            buckets[owner].append((ordinal, ep))

    parts: list[Part] = []
    for bangumi_id, _ in ordered:
        chunk = buckets[bangumi_id]
        if not chunk:
            continue
        parts.append(_mk_part(len(parts) + 1, chunk, bangumi_id))
    return parts


def _mk_part(index: int, chunk: list[tuple[int, Episode]], bangumi_id: int) -> Part:
    dates = sorted(ep.air_date for _, ep in chunk if ep.air_date)
    absolutes = [ep.absolute for _, ep in chunk if ep.absolute is not None]
    return Part(
        index=index,
        bangumi_id=bangumi_id,
        start_ordinal=min(ordinal for ordinal, _ in chunk),
        end_ordinal=max(ordinal for ordinal, _ in chunk),
        start_date=dates[0],
        end_date=dates[-1],
        tvdb_seasons=tuple(sorted({ep.season for _, ep in chunk})),
        tvdb_absolute=(min(absolutes), max(absolutes)) if absolutes else (0, 0),
    )


def coord_for_ordinal(
    scheme: Scheme, aired: Scheme, ordinal: int
) -> tuple[tuple[int, int] | None, str]:
    """正篇第 `ordinal` 集在該來源裡的**正確**座標，以及這個座標是怎麼對出來的。

    對位方法要一起回傳：TMDB 那一欄整個建立在「TVDB 的第 N 集 == TMDB 的哪一集」上，
    若是靠序位硬湊出來的，那一筆就不該當成可信的正確答案，要單獨列出來。
    """
    order = aired.aired_order()
    if not 1 <= ordinal <= len(order):
        return None, "no_source"
    source = order[ordinal - 1]
    if scheme.key == "tvdb_aired":
        return (source.season, source.number), "direct"
    if scheme.key == "tvdb_absolute":
        return (
            ((1, source.absolute), "direct") if source.absolute is not None else (None, "no_source")
        )
    if source.air_date:
        same_day = [e for e in scheme.episodes if e.air_date == source.air_date]
        if len(same_day) == 1:
            return (same_day[0].season, same_day[0].number), "air_date"
    # 播出日期對不上（provider 之間收錄的集數本來就不一定一致）→ 退回序位，並標記。
    target = scheme.aired_order()
    if ordinal <= len(target):
        return (target[ordinal - 1].season, target[ordinal - 1].number), "position"
    return None, "no_source"


# --------------------------------------------------------------------------------------
# 換算器：三種來源共用同一套規則，差別只在餵給它的結構
# --------------------------------------------------------------------------------------


#: plan §4.4 的虛擬季門檻。180 天是量出來的，不是借來的常數：改成 60 天會把一季切成兩個
#: 虛擬季、季號提示就對不上，整體失敗率從 8.0% 惡化到 9.7%（research 文件 §6.4）。
DEFAULT_GAP_DAYS = 180


def virtual_seasons(scheme: Scheme, gap_days: int) -> list[list[Episode]]:
    """plan §4.4 的虛擬季：把每個真實季按播出日期斷點再切開，依序攤平成一份清單。"""
    out: list[list[Episode]] = []
    seasons = scheme.seasons()
    for season in sorted(seasons):
        eps = [e for e in seasons[season] if e.air_date]
        if not eps:
            out.append(seasons[season])
            continue
        chunk: list[Episode] = [eps[0]]
        for prev, cur in itertools.pairwise(eps):
            assert prev.air_date and cur.air_date
            if _days_between(prev.air_date, cur.air_date) > gap_days:
                out.append(chunk)
                chunk = []
            chunk.append(cur)
        out.append(chunk)
    return out


def map_episode(
    scheme: Scheme, aired: Scheme, season_hint: int | None, number: int, gap_days: int
) -> tuple[int, int] | None:
    """檔名的（季號提示, 集號）→ 該來源的座標。換不出來回 None（Berth 會標 review）。

    `tvdb_absolute` 借同一份 TVDB 紀錄的 aired season 解季號再輸出絕對編號——Sonarr 就是
    這樣做的，也是這個來源最強的形態；不給它這個能力等於故意打敗它。
    """
    if scheme.key == "tvdb_absolute":
        # 這個來源的重點就是「字幕組寫的數字本來就是絕對編號」。沒有季號、而且那個號碼
        # 在絕對編號裡存在，就直接用；繞去 aired season 再換回來只會多一次換算的機會出錯。
        known = {e.number for e in scheme.episodes}
        first_season = aired.seasons().get(1) or []
        if season_hint is None and number in known and number > len(first_season):
            return (1, number)
        coord = map_episode(aired, aired, season_hint, number, gap_days)
        if coord is None:
            return (1, number) if number in known else None
        match = next(
            (e for e in aired.episodes if e.season == coord[0] and e.number == coord[1]), None
        )
        return (1, match.absolute) if match and match.absolute is not None else None

    seasons = scheme.seasons()
    order = scheme.aired_order()
    if season_hint is not None:
        # 三條，順序有意義：季內編號 → 虛擬季內編號 → 帶著季號的絕對編號。
        # 反過來先試絕對編號的話，「第二季 01」會被當成整部的第 1 集。
        eps = seasons.get(season_hint)
        if eps and number <= len(eps):
            return (season_hint, number)
        virtual = virtual_seasons(scheme, gap_days)
        if 1 <= season_hint <= len(virtual):
            chunk = virtual[season_hint - 1]
            if number <= len(chunk):
                target = chunk[number - 1]
                return (target.season, target.number)
        # 「第二季 / S2 - 20」這種寫法真的存在（黒ネズミたち、Skymoon-Raws 都這樣發），
        # 季號是給人看的，數字是絕對編號。集號超出那一季的長度就只可能是這種。
        return _as_absolute(scheme, order, number)

    first = seasons.get(1) or []
    if number <= len(first):
        return (1, number)
    return _as_absolute(scheme, order, number)


def _as_absolute(scheme: Scheme, order: list[Episode], number: int) -> tuple[int, int] | None:
    """集號溢位了 → 當成絕對編號。

    來源自己帶絕對編號（TVDB）就直接查表；TMDB 沒有這個欄位，只能數播出序位，
    而序位會被「provider 有沒有把某支特輯 / 劇場版算成一集」影響。這正是兩者的差別所在。
    """
    match = next((e for e in scheme.episodes if e.absolute == number), None)
    if match is not None:
        return (match.season, match.number)
    # 查不到（TMDB 沒有這個欄位；或字幕組數的是正篇序位而不是官方編號）→ 只能數序位。
    if number <= len(order):
        target = order[number - 1]
        return (target.season, target.number)
    return None


# --------------------------------------------------------------------------------------
# Mikan：番組 = 一輪播出，所以「這個檔案屬於哪一 cour」不必用猜的
# --------------------------------------------------------------------------------------

#: id 與標題在同一個 <a> 標籤裡，樣子是
#: `<a href="/Home/Bangumi/3361" target="_blank" class="an-text" title="多数欠">`。
#: 跨標籤比對會把 id 配到下一個項目的標題上，所以整條 regex 必須留在同一個標籤內。
BANGUMI_LINK = re.compile(r'href="/Home/Bangumi/(\d+)"[^>]*class="an-text"[^>]*title="([^"]*)"')
AIR_START = re.compile(r"放送开始：\s*([\d/]+)")
SEASONS = ("春", "夏", "秋", "冬")


def mikan_season_index(years: range) -> dict[int, str]:
    """逐季的番組清單 → {bangumi id: 標題}。

    搜尋頁一頁 1.5 MB 且常常 chunked 斷線，一次查要一分半；逐季的清單只有 70 KB、十秒
    就回來，而且一次把整季的番組都給了。番組 == 一輪播出，這正是這個實驗要的粒度。
    """
    index: dict[int, str] = {}
    for year in years:
        for season in SEASONS:
            url = (
                "https://mikanani.me/Home/BangumiCoverFlowByDayOfWeek"
                f"?year={year}&seasonStr={urllib.parse.quote(season)}"
            )
            page = fetch(url).decode("utf-8", "replace")
            for bangumi_id, title in BANGUMI_LINK.findall(page):
                index.setdefault(int(bangumi_id), html_mod.unescape(title).strip())
    return index


def mikan_bangumi_start(bangumi_id: int) -> str | None:
    """番組頁的「放送开始」，格式是 M/D/YYYY。"""
    page = fetch(f"https://mikanani.me/Home/Bangumi/{bangumi_id}").decode("utf-8", "replace")
    m = AIR_START.search(html_mod.unescape(re.sub(r"<[^>]+>", "|", page)))
    if not m:
        return None
    month, day, year = (int(x) for x in m.group(1).split("/"))
    return f"{year:04d}-{month:02d}-{day:02d}"


#: Mikan RSS 的擴充命名空間，`<ns:torrent><ns:pubDate>` 才是實際發佈時間。
MIKAN_NS = "{https://mikanani.me/0.1/}"


def mikan_bangumi_items(bangumi_id: int) -> list[tuple[str, str | None]]:
    """(標題, 發佈日期)。發佈日期是把檔名的數字釘到某一集上的依據。"""
    xml = fetch(f"https://mikanani.me/RSS/Bangumi?bangumiId={bangumi_id}").decode(
        "utf-8", "replace"
    )
    rows: list[tuple[str, str | None]] = []
    for item in ET.fromstring(xml).iter("item"):
        title = item.findtext("title")
        if not title:
            continue
        published = item.findtext(f"{MIKAN_NS}torrent/{MIKAN_NS}pubDate")
        rows.append((title, published[:10] if published else None))
    return rows


# --------------------------------------------------------------------------------------
# 評分
# --------------------------------------------------------------------------------------

HIT, WRONG, REFUSED = "hit", "wrong", "refused"


@dataclass
class Trial:
    """一次換算：某字幕組在某一輪播出釋出的某一集。"""

    series: str
    part: int
    group: str
    convention: str
    season_hint: int | None
    number: int
    truth_ordinal: int
    #: 這一集來自哪一筆釋出的原始標題（見 `Release.title`）。合集展開的每一集共用同一個。
    title: str
    outcomes: dict[str, str] = field(default_factory=dict)
    #: 每個來源的「正確座標」是怎麼對出來的：direct / air_date / position / no_source
    joins: dict[str, str] = field(default_factory=dict)


#: 釋出的發佈時間與播出日期的容許區間。WEB 版通常在播出當天到兩天內出現；
#: 一週一集的節奏下，這個窗口最多只會對到一集。
PUBLISH_WINDOW = (-1, 3)

#: 一個（輪次, 字幕組）要有幾筆對得上時間的釋出、幾個不同集號、眾數佔多少，才敢用它的 offset。
#: 集號要夠分散：全部落在同一集上的話，眾數只是同一筆證據被數了很多次。
MIN_ANCHORS, MIN_DISTINCT, MIN_SHARE = 4, 3, 0.7

#: 校準出來的偏移量必須把這個字幕組的集號放回它自己那一輪播出裡，否則就是校準失敗
#: （補檔、重發、BD 合集的發佈時間離播出很遠，會把眾數帶歪）。不留餘裕：偏移量差一集時，
#: 這個字幕組的最後一集就會落到這一輪之外，那正是要抓的東西。
PART_SLACK = 0


def calibrate_offset(
    anchors: list[tuple[int, int]], numbers: list[int], part: Part
) -> tuple[int, int, int] | None:
    """從「檔名寫的集號 → 實際播出的第幾集」推出這個字幕組在這一輪用的偏移量。

    不去猜字幕組「應該」怎麼編號，直接用發佈時間把檔名的數字釘到某一集上，再取眾數。
    補檔、重發、BD 合集的發佈時間離播出很遠，會落在眾數之外，所以要求眾數佔六成以上。
    """
    if len(anchors) < MIN_ANCHORS or len({number for number, _ in anchors}) < MIN_DISTINCT:
        return None
    counts: dict[int, int] = {}
    for number, ordinal in anchors:
        counts[ordinal - number] = counts.get(ordinal - number, 0) + 1
    offset, hits = max(counts.items(), key=lambda kv: (kv[1], -abs(kv[0])))
    if hits / len(anchors) < MIN_SHARE:
        return None
    # 範圍檢查要看這個字幕組在這一輪的**全部**釋出，不是只看對得上時間的那些。
    # 固定晚十天發佈的字幕組，每一筆都會被釘到下一集去，偏移量因此整體差一集——
    # 但它最後一集的號碼會因此掉到這一輪之外，這條就是這樣抓到的。
    lo, hi = min(numbers) + offset, max(numbers) + offset
    if lo < part.start_ordinal - PART_SLACK or hi > part.end_ordinal + PART_SLACK:
        return None
    return offset, hits, len(anchors)


CONVENTIONS = ("restart", "absolute", "absolute_official", "season_relative")


def describe_offset(offset: int, part: Part, first_in_season: int) -> str:
    """把偏移量翻成人看得懂的編號習慣。"""
    if offset == part.start_ordinal - 1:
        return "restart"  # 每 cour 從 01 起算
    if offset == 0:
        return "absolute"  # 正篇序位，接著往下算
    if offset == part.end_ordinal - part.tvdb_absolute[1]:
        # 官方編號：特輯 / 劇場版也佔號，與 TVDB absolute 同步。比對用這一輪的**結尾**，
        # 因為佔號的那一支可能落在這一輪中間（航海王的跨作品特別篇就是）。
        return "absolute_official"
    if offset == part.start_ordinal - first_in_season:
        # 季內連號：分割成兩 cour 的季，第二 cour 從 13 接下去而不是回到 01。
        return "season_relative"
    return f"offset{offset:+d}"


def evaluate(
    series_key: str,
    schemes: dict[str, Scheme],
    aired: Scheme,
    parts: list[Part],
    releases: dict[tuple[int, str], list[Release]],
    gap_days: int,
) -> tuple[list[Trial], dict[str, int], list[dict[str, Any]]]:
    total_episodes = len(aired.aired_order())
    order = aired.aired_order()
    trials: list[Trial] = []
    calibrations: list[dict[str, Any]] = []
    skipped: dict[str, int] = {"no_offset": 0, "out_of_range": 0, "odd_offset": 0}
    for (part_index, group), items in sorted(releases.items()):
        part = parts[part_index - 1]
        anchors = [
            (item.parsed.first, item.ordinal)
            for item in items
            if item.ordinal is not None and item.parsed.first == item.parsed.last
        ]
        numbers = [n for item in items for n in (item.parsed.first, item.parsed.last)]
        calibrated = calibrate_offset(anchors, numbers, part)
        if calibrated is None:
            skipped["no_offset"] += sum(len(batch_numbers(i.parsed)) for i in items)
            continue
        offset, hits, seen = calibrated
        opener = order[part.start_ordinal - 1]
        convention = describe_offset(offset, part, opener.number)
        if convention not in CONVENTIONS:
            # 沒有字幕組會用一個沒來由的偏移量替一輪播出編號，所以校準到這種值就是校準失敗。
            # 這種筆數在三個來源都是 100% 錯，留著只會替三欄同時灌水。
            skipped["odd_offset"] += sum(len(batch_numbers(i.parsed)) for i in items)
            continue
        calibrations.append(
            {
                "part": part_index,
                "group": group,
                "offset": offset,
                "convention": convention,
                "anchors": seen,
                "agree": hits,
            }
        )
        for item in items:
            parsed = item.parsed
            for number in batch_numbers(parsed):
                truth = number + offset
                if not 1 <= truth <= total_episodes:
                    skipped["out_of_range"] += 1
                    continue
                if order[truth - 1].air_date is None:
                    skipped["out_of_range"] += 1
                    continue
                trial = Trial(
                    series_key,
                    part_index,
                    group,
                    convention,
                    parsed.season_hint,
                    number,
                    truth,
                    item.title,
                )
                for key, scheme in schemes.items():
                    expected, how = coord_for_ordinal(scheme, aired, truth)
                    trial.joins[key] = how
                    got = map_episode(scheme, aired, parsed.season_hint, number, gap_days)
                    if expected is None:
                        trial.outcomes[key] = REFUSED if got is None else WRONG
                    elif got is None:
                        trial.outcomes[key] = REFUSED
                    else:
                        trial.outcomes[key] = HIT if got == expected else WRONG
                trials.append(trial)
    return trials, skipped, calibrations


# --------------------------------------------------------------------------------------
# 收集：把一部作品的三種來源、播出輪次、字幕組釋出全部湊齊
# --------------------------------------------------------------------------------------


@dataclass
class SeriesResult:
    series: Series
    parts: list[Part]
    schemes: dict[str, Scheme]
    trials: list[Trial]
    bangumi: list[dict[str, Any]]
    parsed_ratio: tuple[int, int]
    #: 有多少筆釋出的發佈時間唯一對到某一集——offset 校準就是靠這些。
    anchored: int
    skipped: dict[str, int]
    #: 每個（輪次, 字幕組）校準出來的偏移量與支持它的證據筆數，供人逐條核對。
    calibrations: list[dict[str, Any]]


def match_ordinal(aired: Scheme, published: str | None) -> int | None:
    """發佈日期 → 正篇第幾集。窗口內剛好一集才算數，模稜兩可就回 None。"""
    if published is None:
        return None
    lo, hi = PUBLISH_WINDOW
    hits = [
        ordinal
        for ordinal, ep in enumerate(aired.aired_order(), start=1)
        if ep.air_date and lo <= _days_between(ep.air_date, published) <= hi
    ]
    return hits[0] if len(hits) == 1 else None


def collect(series: Series, token: str, gap_days: int) -> SeriesResult:
    show = skyhook_show(series.tvdb_id)
    aired, absolute = tvdb_schemes(show)
    schemes = {
        "tmdb": tmdb_scheme(token, series.tmdb_id),
        "tvdb_aired": aired,
        "tvdb_absolute": absolute,
    }
    starts = [
        (bangumi_id, start)
        for bangumi_id in series.bangumi_ids
        if (start := mikan_bangumi_start(bangumi_id)) is not None
    ]
    parts = parts_from_bangumi(aired, starts)
    part_of = {part.bangumi_id: part.index for part in parts}

    releases: dict[tuple[int, str], list[Release]] = {}
    bangumi_rows: list[dict[str, Any]] = []
    total = parsed_ok = anchored = 0
    for bangumi_id, start in starts:
        part_index = part_of.get(bangumi_id)
        rows = 0
        for title, published in mikan_bangumi_items(bangumi_id):
            total += 1
            parsed = parse_title(title)
            if parsed is None or part_index is None:
                continue
            parsed_ok += 1
            rows += 1
            ordinal = match_ordinal(aired, published)
            anchored += ordinal is not None
            releases.setdefault((part_index, parsed.group or "?"), []).append(
                Release(parsed, published, ordinal, title)
            )
        bangumi_rows.append(
            {
                "bangumi_id": bangumi_id,
                "air_start": start,
                "part": part_index,
                "titles": rows,
            }
        )
    trials, skipped, calibrations = evaluate(series.key, schemes, aired, parts, releases, gap_days)
    return SeriesResult(
        series,
        parts,
        schemes,
        trials,
        bangumi_rows,
        (parsed_ok, total),
        anchored,
        skipped,
        calibrations,
    )


# --------------------------------------------------------------------------------------
# 報告
# --------------------------------------------------------------------------------------

SCHEME_ORDER = ("tmdb", "tvdb_aired", "tvdb_absolute")
CONVENTION_LABEL = {
    "restart": "每 cour 從 01 重新起算",
    "absolute": "接著往下算（正篇序位）",
    "absolute_official": "接著往下算（官方編號，特輯 / 劇場版也佔號）",
    "season_relative": "季內連號（分割兩 cour 的第二 cour 從 13 接下去）",
}
SCHEME_LABEL = {
    "tmdb": "TMDB 季集",
    "tvdb_aired": "TVDB default(aired)",
    "tvdb_absolute": "TVDB absolute",
}


def tally(trials: list[Trial]) -> dict[str, dict[str, int]]:
    out = {k: {HIT: 0, WRONG: 0, REFUSED: 0} for k in SCHEME_ORDER}
    for trial in trials:
        for key, outcome in trial.outcomes.items():
            out[key][outcome] += 1
    return out


def pct(part: int, whole: int) -> str:
    return f"{100.0 * part / whole:5.1f}%" if whole else "    -"


def print_report(results: list[SeriesResult]) -> None:
    every = [t for r in results for t in r.trials]

    print("\n## 每部作品的結構")
    for r in results:
        s = r.series
        tm = r.schemes["tmdb"].seasons()
        tv = r.schemes["tvdb_aired"].seasons()
        print(f"\n### {s.key}（tmdb={s.tmdb_id} tvdb={s.tvdb_id}）形態：{'、'.join(s.shapes)}")
        print(
            f"    TMDB       {len(tm)} 季 {sum(len(v) for v in tm.values())} 集："
            f"{[len(tm[k]) for k in sorted(tm)]}"
        )
        print(
            f"    TVDB aired {len(tv)} 季 {sum(len(v) for v in tv.values())} 集："
            f"{[len(tv[k]) for k in sorted(tv)]}"
        )
        print(
            f"    播出輪次 {len(r.parts)}："
            + ", ".join(
                f"#{p.index} 第{p.start_ordinal}-{p.end_ordinal}集 {p.start_date}" for p in r.parts
            )
        )
        print(f"    Mikan 標題 {r.parsed_ratio[1]} 筆，解析出集號並對到輪次 {r.parsed_ratio[0]} 筆")

    print("\n## 逐部作品的換算失敗率（分母是解析出來的釋出集數）")
    header = f"{'作品':20s} {'樣本':>5s}  " + "  ".join(
        f"{SCHEME_LABEL[k]:>20s}" for k in SCHEME_ORDER
    )
    print(header)
    for r in results:
        counts = tally(r.trials)
        n = len(r.trials)
        cells = []
        for k in SCHEME_ORDER:
            bad = counts[k][WRONG] + counts[k][REFUSED]
            cells.append(f"{pct(bad, n)} ({counts[k][WRONG]}錯/{counts[k][REFUSED]}退)".rjust(20))
        print(f"{r.series.key:20s} {n:5d}  " + "  ".join(cells))

    counts = tally(every)
    n = len(every)
    print(
        f"\n{'合計':20s} {n:5d}  "
        + "  ".join(
            f"{pct(counts[k][WRONG] + counts[k][REFUSED], n)} "
            f"({counts[k][WRONG]}錯/{counts[k][REFUSED]}退)".rjust(20)
            for k in SCHEME_ORDER
        )
    )

    print("\n## 依字幕組編號習慣拆開（習慣是從發佈時間校準出來的，不是猜的）")
    for convention in sorted({t.convention for t in every}):
        subset = [t for t in every if t.convention == convention]
        counts = tally(subset)
        label = CONVENTION_LABEL.get(convention, convention)
        print(f"\n{label}：{len(subset)} 集")
        for k in SCHEME_ORDER:
            bad = counts[k][WRONG] + counts[k][REFUSED]
            print(
                f"    {SCHEME_LABEL[k]:22s} 失敗 {pct(bad, len(subset))} "
                f"（錯置 {counts[k][WRONG]}、退回 review {counts[k][REFUSED]}）"
            )

    overlap = overlap_counts(every)
    print("\n## 失敗是誰的問題（三個來源的交集）")
    overlap_labels = {
        "all_three": "三個來源一起錯——與編號來源無關",
        "tmdb_only": "只有 TMDB 錯",
        "tvdb_only": "只有 TVDB 兩欄錯",
        "mixed": "其餘組合",
    }
    for key, count in overlap.items():
        print(f"    {overlap_labels[key]:34s} {count:5d}")

    print("\n## TMDB 那一欄的對位品質（TVDB 絕對編號 → TMDB 座標）")
    joins: dict[str, int] = {}
    for trial in every:
        how = trial.joins.get("tmdb", "?")
        joins[how] = joins.get(how, 0) + 1
    notes = {
        "air_date": "播出日期唯一命中，可信",
        "position": "日期對不上，退回播出序位——這幾筆的『正確答案』本身存疑",
        "no_source": "對不出來",
    }
    for how, count in sorted(joins.items(), key=lambda kv: -kv[1]):
        print(f"    {how:10s} {count:5d}  {pct(count, n)}  {notes.get(how, how)}")

    print("\n## 有沒有季號提示")
    for has_hint in (True, False):
        subset = [t for t in every if (t.season_hint is not None) == has_hint]
        counts = tally(subset)
        print(f"\n{'標題寫了第 N 季' if has_hint else '標題沒有季號'}：{len(subset)} 集")
        for k in SCHEME_ORDER:
            bad = counts[k][WRONG] + counts[k][REFUSED]
            print(
                f"    {SCHEME_LABEL[k]:22s} 失敗 {pct(bad, len(subset))} "
                f"（錯置 {counts[k][WRONG]}、退回 review {counts[k][REFUSED]}）"
            )


def overlap_counts(trials: list[Trial]) -> dict[str, int]:
    """哪些失敗是三個來源共有的、哪些是某一個來源獨有的。

    研究文件拿這組數字說「主因與編號來源無關」，所以它必須從產出本身重現得出來，
    不能只存在於某一次分析的腦袋裡。
    """
    counts: dict[str, int] = {"all_three": 0, "tmdb_only": 0, "tvdb_only": 0, "mixed": 0}
    for trial in trials:
        bad = {key for key in SCHEME_ORDER if trial.outcomes[key] != HIT}
        if not bad:
            continue
        if len(bad) == len(SCHEME_ORDER):
            counts["all_three"] += 1
        elif bad == {"tmdb"}:
            counts["tmdb_only"] += 1
        elif bad == {"tvdb_aired", "tvdb_absolute"}:
            counts["tvdb_only"] += 1
        else:
            counts["mixed"] += 1
    return counts


def failure_cases(results: list[SeriesResult]) -> list[dict[str, Any]]:
    """逐條列出失敗，並標上是哪一種形態造成的。"""
    rows: list[dict[str, Any]] = []
    for r in results:
        seen: set[tuple[str, ...]] = set()
        for t in r.trials:
            for key in SCHEME_ORDER:
                if t.outcomes[key] == HIT:
                    continue
                sig = (key, str(t.part), t.group, t.convention, str(t.season_hint))
                if sig in seen:
                    continue
                seen.add(sig)
                rows.append(
                    {
                        "series": r.series.key,
                        "shapes": list(r.series.shapes),
                        "scheme": key,
                        "part": t.part,
                        "group": t.group,
                        "convention": t.convention,
                        "season_hint": t.season_hint,
                        "example_number": t.number,
                        "truth_ordinal": t.truth_ordinal,
                        "outcome": t.outcomes[key],
                    }
                )
    return rows


# --------------------------------------------------------------------------------------
# 自我檢查：整份數字都壓在 map_episode 上，所以它要有手算過的樣例守著
# --------------------------------------------------------------------------------------


def _weekly(season: int, count: int, start: str, first_abs: int) -> list[Episode]:
    from datetime import date, timedelta

    y, m, d = (int(x) for x in start.split("-"))
    day = date(y, m, d)
    return [
        Episode(
            season=season,
            number=i + 1,
            air_date=(day + timedelta(days=7 * i)).isoformat(),
            absolute=first_abs + i,
        )
        for i in range(count)
    ]


def self_test() -> None:
    """三個手算過的形態，外加虛擬季門檻本身。

    形態：TMDB 併季（Dandadan 實況）、行銷季號不等於播出輪次（SPY×FAMILY）、劇場版佔掉一個
    absolute（CODE: White）。門檻：同一份資料在 180 天與 60 天下會給出不同答案，兩邊都釘住。
    """
    # --- Dandadan：TVDB 切成 S1/S2 各 12 集，TMDB 併成 S1 共 24 集 ---
    aired = Scheme("tvdb_aired")
    aired.episodes = _weekly(1, 12, "2024-10-04", 1) + _weekly(2, 12, "2025-07-04", 13)
    absolute = Scheme("tvdb_absolute")
    absolute.episodes = [
        Episode(1, e.absolute or 0, e.air_date, e.absolute) for e in aired.episodes
    ]
    tmdb = Scheme("tmdb")
    tmdb.episodes = [Episode(1, i + 1, e.air_date) for i, e in enumerate(aired.episodes)]
    schemes = {"tmdb": tmdb, "tvdb_aired": aired, "tvdb_absolute": absolute}

    # 「第二季 01」（每 cour 重新起算）＝ 絕對編號 13
    for key, want in (("tmdb", (1, 13)), ("tvdb_aired", (2, 1)), ("tvdb_absolute", (1, 13))):
        got = map_episode(schemes[key], aired, 2, 1, DEFAULT_GAP_DAYS)
        assert got == want, f"dandadan 第二季01 {key}: {got} != {want}"
        assert coord_for_ordinal(schemes[key], aired, 13)[0] == want, f"dandadan 對位 {key}"
    # 「13」（接著往下算、沒有季號）＝ 同一集
    for key, want in (("tmdb", (1, 13)), ("tvdb_aired", (2, 1)), ("tvdb_absolute", (1, 13))):
        got = map_episode(schemes[key], aired, None, 13, DEFAULT_GAP_DAYS)
        assert got == want, f"dandadan 無季號13 {key}: {got} != {want}"
    # 「第二季 / S2 - 20」＝ 帶季號的絕對編號 20，三種來源都要換算得出來
    for key, want in (("tmdb", (1, 20)), ("tvdb_aired", (2, 8)), ("tvdb_absolute", (1, 20))):
        got = map_episode(schemes[key], aired, 2, 20, DEFAULT_GAP_DAYS)
        assert got == want, f"dandadan 第二季20 {key}: {got} != {want}"
        assert coord_for_ordinal(schemes[key], aired, 20)[0] == want, f"dandadan 對位20 {key}"
    # 「01」without 季號，實際是第二輪 → 三種來源都會錯置成第一集
    for key in schemes:
        assert (
            map_episode(schemes[key], aired, None, 1, DEFAULT_GAP_DAYS)
            != coord_for_ordinal(schemes[key], aired, 13)[0]
        ), f"dandadan 無季號01 {key} 應該錯置"

    # --- SPY×FAMILY 形態：行銷「第二季」是第三輪播出，前兩輪被併成 S1 ---
    aired2 = Scheme("tvdb_aired")
    aired2.episodes = (
        _weekly(1, 12, "2022-04-09", 1)
        + [
            Episode(1, 12 + i + 1, d, 12 + i + 1)
            for i, d in enumerate(e.air_date or "" for e in _weekly(9, 13, "2022-10-01", 13))
        ]
        + _weekly(2, 12, "2023-10-07", 26)
    )
    absolute2 = Scheme("tvdb_absolute")
    absolute2.episodes = [
        Episode(1, e.absolute or 0, e.air_date, e.absolute) for e in aired2.episodes
    ]
    # 「第二季 01」＝ 絕對編號 26，靠 aired season 直接命中
    assert map_episode(aired2, aired2, 2, 1, DEFAULT_GAP_DAYS) == (2, 1)
    assert map_episode(absolute2, aired2, 2, 1, DEFAULT_GAP_DAYS) == (1, 26)
    # 若整部被併成一季（TMDB 對 Dandadan / 咒術 / Re:Zero 就是這樣），只剩虛擬季可用。
    # 這裡就是 180 天門檻的價值所在，兩個門檻都釘住：
    #   180 天 → 只在真正的長休（287 天）切一刀，虛擬季 = [前兩 cour], [第三 cour]，
    #            「第二季」落在行銷上的第二季，對。
    #    60 天 → 連 cour 之間的 98 天也切，虛擬季變三段，「第二季」落到第二個 cour，錯。
    merged = Scheme("tmdb")
    merged.episodes = [Episode(1, i + 1, e.air_date) for i, e in enumerate(aired2.episodes)]
    assert coord_for_ordinal(merged, aired2, 26)[0] == (1, 26)
    assert len(virtual_seasons(merged, DEFAULT_GAP_DAYS)) == 2
    assert map_episode(merged, aired2, 2, 1, DEFAULT_GAP_DAYS) == (1, 26)
    assert len(virtual_seasons(merged, 60)) == 3
    assert map_episode(merged, aired2, 2, 1, 60) == (1, 13)

    # --- 劇場版占掉一個 absolute：正篇序位 != TVDB absolute ---
    # SPY×FAMILY 的 CODE: White 就是 absolute 38，正篇第 38 集的 absolute 是 39。
    gapped = Scheme("tvdb_aired")
    gapped.episodes = _weekly(1, 37, "2022-04-09", 1) + [
        Episode(season=2, number=i + 1, air_date=e.air_date, absolute=39 + i)
        for i, e in enumerate(_weekly(2, 13, "2025-10-04", 39))
    ]
    gapped_abs = Scheme("tvdb_absolute")
    gapped_abs.episodes = [
        Episode(1, e.absolute or 0, e.air_date, e.absolute) for e in gapped.episodes
    ]
    assert coord_for_ordinal(gapped, gapped, 38)[0] == (2, 1)
    assert coord_for_ordinal(gapped_abs, gapped, 38)[0] == (1, 39)
    # 字幕組接著往下算寫「38」，指的是正篇第 38 集 → absolute 要換算成 39
    assert map_episode(gapped_abs, gapped, None, 38, DEFAULT_GAP_DAYS) == (1, 39)
    print("self-test ok")


# --------------------------------------------------------------------------------------
# 進入點
# --------------------------------------------------------------------------------------


def load_sample() -> tuple[Series, ...]:
    raw = json.loads((Path(__file__).with_name("anime_sample.json")).read_text(encoding="utf-8"))
    return tuple(
        Series(
            key=s["key"],
            tmdb_id=s["tmdb_id"],
            tvdb_id=s["tvdb_id"],
            shapes=tuple(s["shapes"]),
            mikan_query=s["mikan_query"],
            bangumi_ids=tuple(s["bangumi_ids"]),
        )
        for s in raw
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--discover",
        action="store_true",
        help="只列出每部作品在 Mikan 的番組候選，用來維護 anime_sample.json",
    )
    parser.add_argument(
        "--gap-days",
        type=int,
        default=DEFAULT_GAP_DAYS,
        help=f"虛擬季的播出日期間隔門檻，天（預設 {DEFAULT_GAP_DAYS}，與 plan §4.4 一致）",
    )
    parser.add_argument("--since", type=int, default=2013, help="discover 掃描的起始年份")
    parser.add_argument("--self-test", action="store_true", help="只跑 map_episode 的手算樣例")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "anime_episode_source.json")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    sample = load_sample()
    if args.discover:
        index = mikan_season_index(range(args.since, 2027))
        print(f"Mikan {args.since}-2026 共 {len(index)} 個番組")
        for series in sample:
            print(f"\n## {series.key}  比對：{series.mikan_query}")
            for bangumi_id, title in sorted(index.items()):
                if series.mikan_query in title:
                    print(f"   {bangumi_id:6d}  {title}")
        return 0

    token = tmdb_token()
    results = [collect(s, token, args.gap_days) for s in sample]
    print_report(results)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "gap_days": args.gap_days,
        "series": [
            {
                "key": r.series.key,
                "tmdb_id": r.series.tmdb_id,
                "tvdb_id": r.series.tvdb_id,
                "shapes": list(r.series.shapes),
                "bangumi": r.bangumi,
                "parts": [vars(p) for p in r.parts],
                "structure": {
                    key: {str(s): len(eps) for s, eps in scheme.seasons().items()}
                    for key, scheme in r.schemes.items()
                    if key != "tvdb_absolute"
                },
                "tally": tally(r.trials),
                "trials": len(r.trials),
                "parsed": r.parsed_ratio[0],
                "titles": r.parsed_ratio[1],
                "anchored": r.anchored,
                "skipped": r.skipped,
                "conventions": sorted({t.convention for t in r.trials}),
                "calibrations": r.calibrations,
            }
            for r in results
        ],
        "total": tally([t for r in results for t in r.trials]),
        "by_convention": {
            c: tally([t for r in results for t in r.trials if t.convention == c])
            for c in sorted({t.convention for r in results for t in r.trials})
        },
        "by_season_hint": {
            ("with_hint" if h else "no_hint"): tally(
                [t for r in results for t in r.trials if (t.season_hint is not None) == h]
            )
            for h in (True, False)
        },
        "failures": failure_cases(results),
        "overlap": overlap_counts([t for r in results for t in r.trials]),
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n原始結果：{args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
