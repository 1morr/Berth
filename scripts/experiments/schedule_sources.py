"""M5.5 票 08：TMDB discover 列得出幾成 Bangumi 放送表上的當季新番（時間表的主幹選誰）。

做法：

1. 抓 Bangumi `/calendar`（當季放送表），每部再讀 `/v0/subjects/{id}` 的 `meta_tags` 分出產地
   （日本 / 中國 / 其他）與平台（TV / WEB）。
2. 對每一週的窗口（預設這一週與上一週，週一到週日）跑幾組 discover 條件，全部頁數都抓。
   `air_date.gte/lte` 官方沒寫篩什麼；實測是「這段期間有一集播出」（柯南、小丸子都在）。
3. 每部 Bangumi 作品先找它的 TMDB id：標題對 discover 的結果（原名對 `original_name`、中文名對
   `zh-CN` 的 `name`，拿掉「第 N 期」這類季號後比）；對不到再打 `search/tv`（原名、中文名、
   拿掉季號的原名、第一個詞依序試）。**列得出**＝這個 id 在那一組 discover 的結果裡。
4. 漏掉的作品（`REFERENCE` 那一組）讀 `tv/{id}` 說出原因：TMDB 查不到、沒標動畫（genre 16）、
   原文語言不符、這一週沒有播出日的集（TMDB 還沒建那一集，或日期不同）。

分母：Bangumi 開播日在窗口結束之後的不算（還沒開播）。覆蓋率照 `SCOPES` 的五種分母印，
判定用的是最後一種（日本、Bangumi 這週有集；2026-11-04 使用者定）。

`tv/on_the_air` 不比：它不分類型（2026-11-04 實測 1703 筆、86 頁），官方說它只是 discover 的包裝。

只用標準庫，不 import berth。TMDB 憑證讀 `TMDB_API_KEY`（v3 key 或 v4 token）；Bangumi 送
User-Agent（brief §20.3）。回應快取在 `.local/experiments/cache/schedule_sources/`，快取鍵帶日期
（隔天重跑會重抓；只有 Bangumi 條目的 `meta_tags` 不帶），結果 JSON 落在
`.local/experiments/results/`。

    uv run --env-file .env python scripts/experiments/schedule_sources.py
    uv run --env-file .env python scripts/experiments/schedule_sources.py --week 2026-11-02 \\
        --param with_status=0 --param with_type=4     # 自訂一組條件，與內建幾組並列
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from lib import request

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / ".local" / "experiments" / "cache" / "schedule_sources"
RESULTS = REPO / ".local" / "experiments" / "results" / "schedule_sources"

TMDB = "https://api.themoviedb.org/3"
BGM = "https://api.bgm.tv"
UA = "1morr/berth-experiment (https://github.com/1morr/Berth)"
#: 時間表要的是中文名；discover 與搜尋都用這個語言，`original_name` 不受影響。
LANGUAGE = "zh-CN"
#: TMDB 的 Animation。
ANIMATION = 16

#: 漏掉的作品照這一組列原因（2026-11-04 量完選定給票 09 的條件）。
REFERENCE = "animation+ja|zh±1"
#: 不送出的條件：窗口前後各放寬幾天。
PAD = "_pad_days"
#: 內建的 discover 條件（窗口另外加）。名字就是報告裡那一欄。
VARIANTS: dict[str, dict[str, str]] = {
    "animation": {"with_genres": str(ANIMATION)},
    "animation+ja": {"with_genres": str(ANIMATION), "with_original_language": "ja"},
    "animation+ja|zh": {"with_genres": str(ANIMATION), "with_original_language": "ja|zh"},
    "animation+JP": {"with_genres": str(ANIMATION), "with_origin_country": "JP"},
    # 窗口前後各放寬一天：深夜檔（「25:00」）兩邊常差一天，週一凌晨的集會掉到隔壁那一週。
    "animation+ja±1": {
        "with_genres": str(ANIMATION),
        "with_original_language": "ja",
        PAD: "1",
    },
    "animation+ja|zh±1": {
        "with_genres": str(ANIMATION),
        "with_original_language": "ja|zh",
        PAD: "1",
    },
}

TODAY = date.today()


# ---------------------------------------------------------------- HTTP 與快取


def cached(key: str, fetch: Callable[[], Any], *, daily: bool = True) -> Any:
    """`daily`：快取鍵帶今天的日期（清單、集與搜尋結果都會變；換季重跑不能讀到舊的）。"""
    if daily:
        key = f"{TODAY.isoformat()}:{key}"
    path = CACHE / f"{hashlib.sha256(key.encode()).hexdigest()[:24]}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    value = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return value


def tmdb(path: str, params: dict[str, str]) -> Any:
    token = os.environ.get("TMDB_API_KEY", "").strip()
    query = urlencode(sorted(params.items()))

    def fetch() -> Any:
        if not token:
            raise SystemExit("set TMDB_API_KEY (v3 key or v4 token)")
        if token.count(".") == 2:
            resp = request(f"{TMDB}{path}?{query}", headers={"Authorization": f"Bearer {token}"})
        else:
            resp = request(f"{TMDB}{path}?{query}&{urlencode({'api_key': token})}")
        if resp.status == 404:
            return None
        if resp.status != 200:
            raise SystemExit(f"TMDB {path}: {resp.status} {resp.text[:200]}")
        return resp.json()

    return cached(f"tmdb:{path}?{query}", fetch)


def bgm(path: str, *, daily: bool = True) -> Any:
    def fetch() -> Any:
        resp = request(f"{BGM}{path}", headers={"User-Agent": UA})
        time.sleep(0.3)
        if resp.status != 200:
            raise SystemExit(f"Bangumi {path}: {resp.status} {resp.text[:200]}")
        return resp.json()

    return cached(f"bgm:{path}", fetch, daily=daily)


def discover(params: dict[str, str]) -> list[dict[str, Any]]:
    """全部頁數（TMDB 最多 500 頁，這裡遠不到）。"""
    first = tmdb("/discover/tv", {**params, "language": LANGUAGE, "page": "1"})
    found: list[dict[str, Any]] = list(first["results"])
    for page in range(2, int(first["total_pages"]) + 1):
        more = tmdb("/discover/tv", {**params, "language": LANGUAGE, "page": str(page)})
        found += more["results"]
    return found


# ---------------------------------------------------------------- 標題


SEASON_MARKS = re.compile(
    r"(第\s*[0-9一二三四五六七八九十]+\s*(期|季|部|クール|シーズン|シリーズ)"
    r"|season\s*[0-9]+|[0-9]+(st|nd|rd|th)\s*season|part\s*[0-9]+|第?[0-9]+期"
    r"|\s[壹贰叁肆伍陆柒捌玖拾]+$"
    r"|\b(ii|iii|iv)\b)",
    re.IGNORECASE,
)


def squash(title: str) -> str:
    """NFKC、小寫、只留字母數字與 CJK / 假名。"""
    text = unicodedata.normalize("NFKC", title).lower()
    # 「与」是中文名裡的「&」（Welsh & Shedar 在 TMDB 是「威尔什与榭达」）。
    return "".join(ch for ch in text if ch.isalnum() and ch != "与")


def base_title(title: str) -> str:
    """拿掉季號再壓平：Bangumi 一季一條，TMDB 多季一條。"""
    text = unicodedata.normalize("NFKC", title)
    return squash(SEASON_MARKS.sub(" ", text))


#: 衍生作的記號：一邊有、另一邊沒有就不是同一部（迷你動畫對到本篇是第一輪的誤配）。
SPINOFF = re.compile(r"ミニアニメ|ミニ劇場|ミニ$|迷你|特別篇|特别篇|劇場版|剧场版|2DMV|MV$")


def same_title(a: str, b: str) -> bool:
    """壓平後相同，或較短的一邊（至少 4 個字）是另一邊的開頭；衍生作記號要兩邊一致。"""
    if bool(SPINOFF.search(a.strip())) != bool(SPINOFF.search(b.strip())):
        return False
    x, y = base_title(a), base_title(b)
    if not x or not y:
        return False
    if x == y:
        return True
    short, long_ = sorted((x, y), key=len)
    return len(short) >= 4 and long_.startswith(short)


# ---------------------------------------------------------------- Bangumi


@dataclass
class Show:
    bgm_id: int
    name: str
    name_cn: str
    air_date: str
    weekday: int
    region: str
    platform: str
    #: Bangumi 正篇各集的播出日（沒填的不列）。
    airdates: list[str] = field(default_factory=list)
    tmdb_id: int | None = None
    tmdb_title: str = ""
    found_by: str = ""
    #: 每個窗口每組條件：列得出（True）或沒列。
    listed: dict[str, dict[str, bool]] = field(default_factory=dict)
    #: 每個窗口：Bangumi 說這一週有沒有一集（沒有任何播出日是 None）。
    bgm_airs: dict[str, bool | None] = field(default_factory=dict)
    #: 每個窗口：`REFERENCE` 那一組沒列時的原因（列到的窗口沒有這個鍵）。
    why_missed: dict[str, str] = field(default_factory=dict)

    @property
    def titles(self) -> list[str]:
        return [t for t in (self.name, self.name_cn) if t]


def calendar() -> list[Show]:
    shows: list[Show] = []
    for day in bgm("/calendar"):
        for item in day["items"]:
            detail = bgm(f"/v0/subjects/{item['id']}", daily=False)
            tags = set(detail.get("meta_tags") or [])
            region = next((r for r in ("日本", "中国") if r in tags), "其他")
            platform = detail.get("platform") or ""
            shows.append(
                Show(
                    bgm_id=item["id"],
                    name=html.unescape(item["name"]),
                    name_cn=html.unescape(item.get("name_cn") or ""),
                    air_date=item.get("air_date") or "",
                    weekday=day["weekday"]["id"],
                    region=region,
                    platform=platform,
                    airdates=read_airdates(item["id"]),
                )
            )
    return shows


def read_airdates(subject: int) -> list[str]:
    """`/v0/episodes` 的正篇（`type=0`），一頁 100 筆翻到底（柯南一千多集）。"""
    found: list[str] = []
    offset = 0
    while True:
        page = bgm(f"/v0/episodes?subject_id={subject}&type=0&limit=100&offset={offset}")
        found += [e["airdate"] for e in page["data"] if e.get("airdate")]
        offset += len(page["data"])
        if not page["data"] or offset >= page["total"]:
            return found


# ---------------------------------------------------------------- 對應


def titles_of(row: dict[str, Any]) -> list[str]:
    return [t for t in (row.get("original_name"), row.get("name")) if t]


def matches(show: Show, row: dict[str, Any]) -> bool:
    return any(same_title(a, b) for a in show.titles for b in titles_of(row))


def match_listed(show: Show, rows: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    hits = [r for r in rows.values() if matches(show, r)]
    if not hits:
        return None
    # 同名多部時取原名完全相同的，再取開播最晚的（新作或重製版）。
    hits.sort(
        key=lambda r: (
            squash(r.get("original_name", "")) == squash(show.name),
            r.get("first_air_date") or "",
        ),
        reverse=True,
    )
    return hits[0]


def search(show: Show) -> dict[str, Any] | None:
    # 最後退到第一個詞：「ぷにるんず ぷに４」在 TMDB 只有「ぷにるんず」一部。
    heads = [t.split()[0] for t in (show.name, show.name_cn) if t.split()]
    queries = [
        show.name,
        show.name_cn,
        SEASON_MARKS.sub(" ", show.name).strip(),
        *(h for h in heads if len(h) >= 4),
    ]
    for query in dict.fromkeys(q for q in queries if q):
        answer = tmdb("/search/tv", {"query": query, "language": LANGUAGE})
        hits = [r for r in answer["results"] if matches(show, r)]
        if hits:
            hits.sort(key=lambda r: ANIMATION in r.get("genre_ids", []), reverse=True)
            return dict(hits[0])
    return None


def resolve(shows: list[Show], listed: dict[int, dict[str, Any]]) -> None:
    for show in shows:
        row = match_listed(show, listed)
        how = "listed-title"
        if row is None:
            row = search(show)
            how = "search"
        if row is not None:
            show.tmdb_id = int(row["id"])
            show.tmdb_title = f"{row.get('original_name', '')} / {row.get('name', '')}"
            show.found_by = how


def explain_miss(show: Show, variant: dict[str, str]) -> str:
    if show.tmdb_id is None:
        if any(SPINOFF.search(t.strip()) for t in show.titles):
            return "TMDB 查不到這部衍生作（本篇不算同一部）"
        return "TMDB 查不到"
    detail = tmdb(f"/tv/{show.tmdb_id}", {"language": LANGUAGE})
    if detail is None:
        return "TMDB 查不到"
    genres = {g["id"] for g in detail.get("genres", [])}
    if ANIMATION not in genres:
        return f"沒標動畫（{', '.join(g['name'] for g in detail.get('genres', [])) or '無類型'}）"
    lang = variant.get("with_original_language")
    if lang and detail.get("original_language") not in lang.split("|"):
        return f"原文語言是 {detail.get('original_language')}"
    country = variant.get("with_origin_country")
    if country and country not in detail.get("origin_country", []):
        return f"產地是 {','.join(detail.get('origin_country', [])) or '無'}"
    seen = [
        (e or {}).get("air_date")
        for e in (detail.get("last_episode_to_air"), detail.get("next_episode_to_air"))
    ]
    dates = ", ".join(d for d in seen if d) or "無"
    return f"這一週沒有播出日的集（最近一集與下一集：{dates}）"


# ---------------------------------------------------------------- 報告


#: 分母。最後一個是判定用的：Berth 的作品來自日本字幕組的 feed，時間表列的是「這一週有播的」。
SCOPES: dict[str, Callable[[Show, str], bool]] = {
    "全部": lambda s, w: True,
    "日本": lambda s, w: s.region == "日本",
    "日本/TV": lambda s, w: s.region == "日本" and s.platform == "TV",
    "Bangumi 這週有集": lambda s, w: s.bgm_airs.get(w) is True,
    "日本且 Bangumi 這週有集": lambda s, w: s.region == "日本" and s.bgm_airs.get(w) is True,
}


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def run(week: date, custom: dict[str, str]) -> dict[str, Any]:
    variants = dict(VARIANTS)
    if custom:
        variants["custom"] = {"with_genres": str(ANIMATION), **custom}
    windows = {"this": (week, week + timedelta(days=6))}
    windows["last"] = (week - timedelta(days=7), week - timedelta(days=1))

    listed: dict[str, dict[str, set[int]]] = {}
    listed_rows: dict[int, dict[str, Any]] = {}
    reference: dict[str, list[dict[str, Any]]] = {}
    sizes: dict[str, dict[str, int]] = {}
    for wname, (start, end) in windows.items():
        listed[wname] = {}
        sizes[wname] = {}
        for vname, params in variants.items():
            sent = {k: v for k, v in params.items() if k != PAD}
            pad = timedelta(days=int(params.get(PAD, "0")))
            sent |= {"air_date.gte": str(start - pad), "air_date.lte": str(end + pad)}
            rows = discover(sent)
            listed[wname][vname] = {int(r["id"]) for r in rows}
            if vname == REFERENCE:
                reference[wname] = rows
            sizes[wname][vname] = len(rows)
            listed_rows |= {int(r["id"]): r for r in rows}

    shows = calendar()
    resolve(shows, listed_rows)

    for show in shows:
        for wname, (start, end) in windows.items():
            if show.air_date and show.air_date > str(end):
                continue
            show.bgm_airs[wname] = (
                any(str(start) <= d <= str(end) for d in show.airdates) if show.airdates else None
            )
            show.listed[wname] = {
                v: show.tmdb_id is not None and show.tmdb_id in ids
                for v, ids in listed[wname].items()
            }
            if not show.listed[wname][REFERENCE]:
                show.why_missed[wname] = explain_miss(show, variants[REFERENCE])

    coverage: dict[str, dict[str, dict[str, Any]]] = {}
    for wname in windows:
        coverage[wname] = {}
        for scope, keep in SCOPES.items():
            pool = [s for s in shows if wname in s.listed and keep(s, wname)]
            coverage[wname][scope] = {
                v: {
                    "listed": sum(s.listed[wname][v] for s in pool),
                    "total": len(pool),
                }
                for v in variants
            }
    mapped = {s.tmdb_id for s in shows}
    return {
        "measured_at": TODAY.isoformat(),
        "week": week.isoformat(),
        "windows": {k: [str(a), str(b)] for k, (a, b) in windows.items()},
        "variants": variants,
        "discover_sizes": sizes,
        "coverage": coverage,
        "shows": [asdict(s) for s in shows],
        # 反方向：那一組 discover 列了、Bangumi 放送表沒有的作品。
        "extras": {
            w: [
                {
                    k: r.get(k)
                    for k in ("id", "original_language", "first_air_date", "original_name", "name")
                }
                for r in rows
                if int(r["id"]) not in mapped
            ]
            for w, rows in reference.items()
        },
    }


AIRS = {True: "Bangumi 這週有集", False: "Bangumi 這週沒集", None: "Bangumi 無播出日"}


def report(result: dict[str, Any]) -> None:
    print(f"量測日 {result['measured_at']}；Bangumi 放送表 {len(result['shows'])} 部")
    regions = Counter(f"{s['region']}/{s['platform']}" for s in result["shows"])
    print("產地/平台：" + "、".join(f"{k} {v}" for k, v in sorted(regions.items())))
    for wname, (start, end) in result["windows"].items():
        print(f"\n## 窗口 {wname}：{start} – {end}")
        print(
            "discover 筆數："
            + "、".join(f"{k} {v}" for k, v in result["discover_sizes"][wname].items())
        )
        for scope, row in result["coverage"][wname].items():
            cells = [
                f"{v} {c['listed']}/{c['total']} = {c['listed'] / c['total']:.1%}"
                for v, c in row.items()
                if c["total"]
            ]
            print(f"覆蓋率（{scope}）：" + "；".join(cells))
        print(f"漏掉（{REFERENCE}）：")
        for s in result["shows"]:
            reason = s["why_missed"].get(wname)
            if reason:
                tmdb_id = s["tmdb_id"] or "—"
                print(
                    f"  - [{s['region']}/{s['platform']}；{AIRS[s['bgm_airs'][wname]]}] "
                    f"{s['name']}（{s['name_cn'] or '—'}，"
                    f"bgm {s['bgm_id']}，開播 {s['air_date']}）→ tmdb {tmdb_id}：{reason}"
                )
    for wname, extras in result["extras"].items():
        langs = dict(Counter(x["original_language"] for x in extras))
        print(f"\n## {REFERENCE} 列了、Bangumi 放送表沒有（{wname}）：{len(extras)} 部，{langs}")
        for x in extras:
            if x["original_language"] == "ja":
                print(
                    f"  - tmdb {x['id']} {x['original_name']}"
                    f"（{x['name']}，首播 {x['first_air_date']}）"
                )
    print("\n對應（人工核對用）：")
    for s in result["shows"]:
        print(f"  {s['bgm_id']} {s['name']} ⇒ {s['tmdb_id']} {s['tmdb_title']} [{s['found_by']}]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--week", type=date.fromisoformat, default=monday(TODAY), help="週一")
    parser.add_argument(
        "--param", action="append", default=[], help="自訂 discover 條件 key=value（可重複）"
    )
    args = parser.parse_args()
    custom = dict(p.split("=", 1) for p in args.param)
    result = run(monday(args.week), custom)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{result['measured_at']}_week-{result['week']}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report(result)
    print(f"\n→ {out.relative_to(REPO)}", file=sys.stderr)


if __name__ == "__main__":
    main()
