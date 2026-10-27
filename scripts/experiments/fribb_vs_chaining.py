"""有 Fribb 與沒 Fribb：AniList 條目對到 TMDB 哪一季、第幾集到第幾集，兩種算法各對幾季（2026-10-28，
不是票；票 16 之後使用者要看的比較）。

每部作品從 AniList 的一個條目沿 `SEQUEL` / `PREQUEL` / `SIDE_STORY` / `PARENT` / `SUMMARY` 走完系列
（同 `services/anilist.read_franchise` 的預設，不含衍生作），每個 `TV` 條目算兩種答案：

- **A（Fribb）**：`season.tmdb` 與 `episode_offset.tmdb`，起點 offset + 1、終點是起點 + AniList
  集數 − 1。
- **B（串接，`series-mapping` 第 3 步的退路）**：TV 條目照開播日排，從 TMDB S01E01 起依 AniList 集數
  一個接一個；一季的集數用完，下一個條目從下一季的 E01 起。

**正解不看 A、B**：AniList 條目的 `startDate` 對 TMDB 播出日相同的那一集（起點），`endDate`
對同一季裡播出日相同的最後一集（終點）。容忍 ±1 天：AniList 記的是日本首播日，深夜檔
（「25:30」）在別的時區或 TMDB 的編輯手上常記成前一天或後一天；週播的兩集相隔 7 天，±1 天不會
撞到隔壁那一集。同一天兩集（首播連播、串流一次放完）起點取最小、終點取最大。對不到的那一端寫
「無法判定」，那一列不算對錯。只比 TV 條目。

只打 AniList（每次間隔 2.5 秒，目前上限 30 次 / 分）、TMDB（`TMDB_API_KEY`，v3 key 或 v4
token）與 Fribb 的表；不經任何 AI 模型。回應快取在 `.local/experiments/cache/fribb_vs_chaining/`，
重跑不打網路。

    TMDB_API_KEY=... uv run python scripts/experiments/fribb_vs_chaining.py

輸出：`docs/research/fribb-vs-chaining-2026-10-28.json`（原始數據）與
`.local/experiments/results/fribb_vs_chaining/tables.md`（每部一張表，研究檔照它寫）。只用標準庫。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from lib import Response
from lib import request as _request

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / ".local" / "experiments" / "cache" / "fribb_vs_chaining"
RESULTS = REPO / ".local" / "experiments" / "results" / "fribb_vs_chaining"
OUT_JSON = REPO / "docs" / "research" / "fribb-vs-chaining-2026-10-28.json"

ANILIST = "https://graphql.anilist.co"
TMDB = "https://api.themoviedb.org/3"
FRIBB = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
UA = "1morr/berth-experiment (https://github.com/1morr/Berth)"

FOLLOWED = {"SEQUEL", "PREQUEL", "SIDE_STORY", "PARENT", "SUMMARY"}
#: 日期容忍幾天（理由見檔頭）。
TOLERANCE_DAYS = 1
MAX_ENTRIES = 40


@dataclass(frozen=True)
class Series:
    key: str
    #: 走系列圖的起點。
    anilist_id: int
    #: 正解與 B 用的 TMDB 劇集（手挑、不取自 Fribb）。
    tmdb_id: int
    #: 為什麼挑它。
    why: str
    #: 熱門，或冷門 / 容易撞名（重製版、同名不同作、只有劇場版接續）。
    group: str = "熱門"


SERIES = (
    Series(
        "rezero", 21355, 65942, "TMDB 把四季併成一季；Fribb 的 offset 已知差一集；有 OVA 與劇場版"
    ),
    Series("jujutsu", 113415, 95479, "TMDB 把三季併成一季；有劇場版 0"),
    Series("frieren", 154587, 209867, "TMDB 把兩季併成一季"),
    Series("dandadan", 171018, 240411, "第二季被 TMDB 併進第一季（brief §20.3）"),
    Series("aot", 16498, 1429, "分割 cour（第 3 季 Part 2、Final Season 三段）、OVA 多"),
    Series("mushoku", 108465, 94664, "第二季有第 0 集、季中有總集篇；OVA 多"),
    Series("kaguya", 101921, 83121, "三季加一部劇場版（First Kiss）"),
    Series("spyfamily", 140960, 120089, "第 1 季分兩個 cour、第 2 季、劇場版 CODE: White"),
    Series("bleach", 116674, 30984, "千年血戰篇分三段，TMDB 接在 366 集的原作之後"),
    Series("uchouten", 17909, 61338, "兩季相隔四年", "冷門"),
    Series("maou", 15809, 45997, "第 1 季與第 2 季相隔九年，第 2 季分兩個 cour", "冷門"),
    Series("fruitsbasket", 105334, 85991, "2019 重製版，TMDB 另有 2001 年的同名作", "撞名"),
    Series("hxh2011", 11061, 46298, "2011 重製版，TMDB 另有 1999 年的同名作", "撞名"),
    Series("urusei", 143277, 154524, "2022 重製版，TMDB 另有 1981 年的同名作", "撞名"),
    Series("kino", 98448, 74097, "2017 重製版，TMDB 另有 2003 年的奇諾之旅", "撞名"),
    Series("tamako", 16417, 48561, "只有劇場版接續（Tamako Love Story）", "冷門"),
    Series("abyss", 97986, 72636, "兩季之間夾一部劇場版接續（深き魂の黎明）", "冷門"),
)


# ---------------------------------------------------------------- 抓取與快取


def request(url: str, **kwargs: Any) -> Response:
    """`lib.request` 加上連線層的重試：跑的時候遇過 TLS 被中途掐斷（`UNEXPECTED_EOF`）。"""
    for attempt in range(4):
        try:
            return _request(url, **kwargs)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    raise AssertionError("unreachable")


def cached(name: str, fetch: Any) -> Any:
    path = CACHE / f"{hashlib.sha256(name.encode()).hexdigest()[:32]}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    value = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return value


ENTRIES_QUERY = (
    "query($ids:[Int]){Page(perPage:50){media(id_in:$ids,type:ANIME){id format episodes status "
    "startDate{year month day} endDate{year month day} title{romaji english} "
    "relations{edges{relationType(version:2) node{id type}}}}}}"
)


def anilist_entries(ids: list[int]) -> list[dict[str, Any]]:
    def fetch() -> Any:
        for _ in range(4):
            resp = request(
                ANILIST,
                method="POST",
                headers={"User-Agent": UA, "Accept": "application/json"},
                json_body={"query": ENTRIES_QUERY, "variables": {"ids": ids}},
            )
            time.sleep(2.5)
            if resp.status == 429:
                time.sleep(float(resp.headers.get("Retry-After", "60")))
                continue
            if resp.status != 200:
                raise SystemExit(f"AniList {resp.status}: {resp.text[:300]}")
            return resp.json()["data"]["Page"]["media"]
        raise SystemExit("AniList kept answering 429")

    found: list[dict[str, Any]] = cached(f"anilist:{sorted(ids)}", fetch)
    return found


def tmdb(path: str) -> Any:
    token = os.environ.get("TMDB_API_KEY", "").strip()

    def fetch() -> Any:
        if not token:
            raise SystemExit("set TMDB_API_KEY (v3 key or v4 token)")
        if token.count(".") == 2:
            resp = request(f"{TMDB}{path}", headers={"Authorization": f"Bearer {token}"})
        else:
            joiner = "&" if "?" in path else "?"
            resp = request(f"{TMDB}{path}{joiner}{urlencode({'api_key': token})}")
        if resp.status != 200:
            raise SystemExit(f"TMDB {path}: {resp.status} {resp.text[:200]}")
        return resp.json()

    return cached(f"tmdb:{path}", fetch)


def fribb_table() -> dict[int, dict[str, Any]]:
    path = CACHE / "anime-list-full.json"
    if not path.exists():
        resp = request(FRIBB, headers={"User-Agent": UA}, timeout=300)
        json.loads(resp.body)  # 下載斷掉的話這裡就停，不留半張表
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.body)
    table = json.loads(path.read_bytes())
    return {e["anilist_id"]: e for e in table if e.get("anilist_id")}


# ---------------------------------------------------------------- 系列與 TMDB


def walk(root: int) -> list[dict[str, Any]]:
    """同 `read_franchise`：一層問一次。"""
    found: dict[int, dict[str, Any]] = {}
    asked: set[int] = set()
    frontier = {root}
    while frontier and len(asked) < MAX_ENTRIES:
        wanted = sorted(frontier)[: MAX_ENTRIES - len(asked)]
        layer = anilist_entries(wanted)
        asked |= set(wanted)
        found |= {m["id"]: m for m in layer}
        frontier = set(sorted(frontier)[len(wanted) :]) | {
            e["node"]["id"]
            for m in layer
            for e in m["relations"]["edges"]
            if e["node"]["type"] == "ANIME"
            and e["relationType"] in FOLLOWED
            and e["node"]["id"] not in asked
        }
    return sorted(found.values(), key=lambda m: (iso(m["startDate"]) or "9999", m["id"]))


def iso(value: dict[str, Any] | None) -> str | None:
    """完整的年月日才算；只知道年或年月的對不了播出日。"""
    if not value or not all(isinstance(value.get(k), int) for k in ("year", "month", "day")):
        return None
    return f"{value['year']:04d}-{value['month']:02d}-{value['day']:02d}"


@dataclass(frozen=True)
class Episode:
    season: int
    number: int
    air_date: str | None


def tmdb_series(tmdb_id: int) -> tuple[dict[str, Any], list[Episode]]:
    detail = tmdb(f"/tv/{tmdb_id}")
    episodes: list[Episode] = []
    for season in detail["seasons"]:
        rows = tmdb(f"/tv/{tmdb_id}/season/{season['season_number']}")
        episodes += [
            Episode(season["season_number"], ep["episode_number"], ep.get("air_date") or None)
            for ep in rows.get("episodes", [])
        ]
    return detail, episodes


# ---------------------------------------------------------------- 三種答案


def days_apart(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def truth(entry: dict[str, Any], episodes: list[Episode]) -> dict[str, Any]:
    """播出日對播出日。起點先找正篇（第 1 季起），找不到才看 Specials。"""
    start, end = iso(entry["startDate"]), iso(entry["endDate"])
    out: dict[str, Any] = {"season": None, "start": None, "end": None, "note": ""}
    if start is None:
        out["note"] = "AniList 沒有完整的開播日"
        return out
    dated = [ep for ep in episodes if ep.air_date]
    for pool in ([ep for ep in dated if ep.season >= 1], [ep for ep in dated if ep.season == 0]):
        near = [ep for ep in pool if days_apart(ep.air_date or "", start) <= TOLERANCE_DAYS]
        if near:
            best = min(days_apart(ep.air_date or "", start) for ep in near)
            closest = [ep for ep in near if days_apart(ep.air_date or "", start) == best]
            if len({ep.season for ep in closest}) > 1:
                out["note"] = "開播日在兩季都有一集"
                return out
            first = min(closest, key=lambda ep: ep.number)
            out["season"], out["start"] = first.season, first.number
            break
    if out["season"] is None:
        out["note"] = "TMDB 沒有哪一集在開播日 ±1 天播出"
        return out
    if end is None:
        out["note"] = "AniList 沒有完整的完結日（還在播或沒填）"
        return out
    if out["season"] == 0:
        # 第一集（常是「第 0 集」）被 TMDB 放進 Specials、其餘在正篇：完結日對得到正篇的哪一季，
        # 正解就是那一季從開播日之後的第一集起，Specials 那一集另外註明。
        regular = [
            ep
            for ep in dated
            if ep.season >= 1 and days_apart(ep.air_date or "", end) <= TOLERANCE_DAYS
        ]
        if regular:
            special = out["start"]
            season = regular[0].season
            after = [
                ep.number for ep in dated if ep.season == season and (ep.air_date or "") > start
            ]
            out |= {
                "season": season,
                "start": min(after),
                "end": max(ep.number for ep in regular if ep.season == season),
                "note": f"第一集在 Specials（S00E{special:02d}）",
            }
            return out
    # 完結日在正篇的哪一季都找：TMDB 把一個條目拆成好幾季時（HxH 2011 的 148 集），終點在後面的季。
    later = [
        ep
        for ep in dated
        if ep.season >= 1
        and (ep.season, ep.number) >= (out["season"], out["start"])
        and days_apart(ep.air_date or "", end) <= TOLERANCE_DAYS
    ]
    if not later:
        out["note"] = "TMDB 正篇沒有哪一集在完結日 ±1 天播出"
        return out
    last = max(later, key=lambda ep: (ep.season, ep.number))
    out["end"] = last.number
    if last.season != out["season"]:
        out["end_season"] = last.season
        out["note"] = f"跨季：到 S{last.season:02d}E{last.number:02d}"
    return out


def by_fribb(
    entry: dict[str, Any], fribb: dict[int, dict[str, Any]], tmdb_id: int
) -> dict[str, Any]:
    row = fribb.get(entry["id"])
    tv = ((row or {}).get("themoviedb_id") or {}).get("tv")
    season = ((row or {}).get("season") or {}).get("tmdb")
    if row is None:
        return {"covered": False, "note": "表上沒有這個 AniList id"}
    movies = ((row.get("themoviedb_id") or {}).get("movie")) or []
    if tv is None and movies:
        return {
            "covered": True,
            "movies": movies,
            "season": None,
            "start": None,
            "end": None,
            "note": "TMDB 電影 " + "、".join(f"movie/{m}" for m in movies),
        }
    if tv is None:
        return {"covered": False, "note": "表上有，但沒有 TMDB 劇集"}
    if season is None:
        return {"covered": False, "tmdb_id": tv, "note": f"有 TMDB 劇集 tv/{tv}，沒有季"}
    if tv != tmdb_id:
        return {
            "covered": True,
            "tmdb_id": tv,
            "season": season,
            "start": None,
            "end": None,
            "note": f"對到別的 TMDB 劇集 {tv}",
        }
    offset = (row.get("episode_offset") or {}).get("tmdb") or 0
    start = offset + 1
    episodes = entry["episodes"]
    return {
        "covered": True,
        "tmdb_id": tv,
        "season": season,
        "offset": offset,
        "start": start,
        "end": start + episodes - 1 if isinstance(episodes, int) else None,
        "note": "",
    }


def by_chaining(
    tv_entries: list[dict[str, Any]], detail: dict[str, Any]
) -> dict[int, dict[str, Any]]:
    """`series-mapping` 第 3 步的退路：照開播日、從 S01E01 起依集數串，一季用完換下一季。"""
    seasons = sorted(
        (s["season_number"], s["episode_count"])
        for s in detail["seasons"]
        if s["season_number"] >= 1
    )
    out: dict[int, dict[str, Any]] = {}
    index, cursor = 0, 1
    for entry in tv_entries:
        count = entry["episodes"]
        if index >= len(seasons) or not isinstance(count, int):
            out[entry["id"]] = {
                "season": None,
                "start": None,
                "end": None,
                "note": "TMDB 的季用完了" if index >= len(seasons) else "AniList 沒有集數",
            }
            continue
        season, size = seasons[index]
        end = cursor + count - 1
        out[entry["id"]] = {
            "season": season,
            "start": cursor,
            "end": end,
            "note": f"超出那一季的 {size} 集" if end > size else "",
        }
        if end >= size:
            index, cursor = index + 1, 1
        else:
            cursor = end + 1
    return out


NATIVE_QUERY = "query($id:Int){Media(id:$id){id title{romaji english native}}}"


def anilist_titles(anilist_id: int) -> dict[str, Any]:
    """三種標題（系列圖的查詢沒取 `native`；另外問、另外快取，不讓已快取的系列圖失效）。"""

    def fetch() -> Any:
        resp = request(
            ANILIST,
            method="POST",
            headers={"User-Agent": UA, "Accept": "application/json"},
            json_body={"query": NATIVE_QUERY, "variables": {"id": anilist_id}},
        )
        time.sleep(2.5)
        if resp.status != 200:
            raise SystemExit(f"AniList {resp.status}: {resp.text[:300]}")
        return resp.json()["data"]["Media"]["title"]

    titles: dict[str, Any] = cached(f"anilist-title:{anilist_id}", fetch)
    return titles


def search_tmdb(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """退路真的會走的路：拿第一季的 AniList 標題（english、romaji、native 依序）搜 TMDB，取第一個
    有結果的標題裡、動畫類劇集中首播年最接近第一季的那一部（同年取搜尋排序在前的）。用
    `search/multi`，與 Berth 的 `discover.search_media` 同一支。"""
    tv = [e for e in entries if e["format"] == "TV" and iso(e["startDate"])]
    if not tv:
        return {"found": None, "note": "沒有有開播日的 TV 條目", "by_title": {}}
    first = tv[0]
    year = first["startDate"]["year"]
    titles = anilist_titles(first["id"])
    picks = {k: _pick(titles[k], year) for k in ("english", "romaji", "native") if titles.get(k)}
    for kind in ("english", "romaji", "native"):
        best = picks.get(kind)
        if best is None:
            continue
        return {
            "found": best["id"],
            "name": best.get("name"),
            "first_air_date": best.get("first_air_date"),
            "query": titles[kind],
            "query_kind": kind,
            "candidates": best["candidates"],
            # 敏感度：只用這一種標題搜的話會挑到哪一部（沒有動畫類結果是 None）。
            "by_title": {k: (p["id"] if p else None) for k, p in picks.items()},
            "titles": titles,
        }
    return {"found": None, "note": "三種標題都搜不到動畫類劇集", "by_title": {}}


def _pick(title: str, year: int) -> dict[str, Any] | None:
    results = tmdb(f"/search/multi?{urlencode({'query': title})}").get("results", [])
    animated: list[dict[str, Any]] = [
        r for r in results if r.get("media_type") == "tv" and 16 in (r.get("genre_ids") or [])
    ]
    if not animated:
        return None

    def distance(r: dict[str, Any]) -> int:
        aired = r.get("first_air_date") or ""
        return abs(int(aired[:4]) - year) if aired[:4].isdigit() else 9999

    chosen = min(animated, key=distance)
    best = dict(chosen)
    best["candidates"] = [(r["id"], r.get("name"), r.get("first_air_date")) for r in animated]
    return best


def verdict(answer: dict[str, Any], right: dict[str, Any]) -> str:
    """對 / 錯 / 無法判定 / 未覆蓋。終點無法判定時只比季與起點。"""
    if right["season"] is None:
        return "無法判定"
    if answer.get("covered") is False:
        return "未覆蓋"
    if answer.get("season") is None or answer.get("start") is None:
        return "錯"
    if right.get("end_season") is not None:
        return "錯"  # 正解跨季，A、B 只給得出一季裡的範圍
    keys = ("season", "start", "end") if right["end"] is not None else ("season", "start")
    return "對" if all(answer.get(k) == right[k] for k in keys) else "錯"


def how_wrong(answer: dict[str, Any], right: dict[str, Any]) -> str:
    if right.get("end_season") is not None:
        return f"正解跨季（{rng(right)}）"
    if answer.get("season") != right["season"]:
        return f"季不同（S{answer.get('season')} 對 S{right['season']}）"
    parts = []
    if answer.get("start") != right["start"] and answer.get("start") is not None:
        parts.append(f"起點差 {answer['start'] - right['start']:+d}")
    if right["end"] is not None and answer.get("end") is not None and answer["end"] != right["end"]:
        parts.append(f"終點差 {answer['end'] - right['end']:+d}")
    return "、".join(parts) or answer.get("note", "")


# ---------------------------------------------------------------- 主程式


def rng(answer: dict[str, Any]) -> str:
    if answer.get("covered") is False:
        return "—"
    if answer.get("season") is None:
        return answer.get("note") or "—"
    end = answer.get("end")
    if answer.get("end_season") is not None:
        first = f"S{answer['season']:02d}E{answer['start']:02d}"
        return f"{first}–S{answer['end_season']:02d}E{end:02d}"
    text = f"S{answer['season']:02d}E{answer['start'] or 0:02d}" + (f"–E{end:02d}" if end else "–?")
    return text + (f"（{answer['note']}）" if answer.get("note") else "")


def main() -> None:
    fribb = fribb_table()
    report: list[dict[str, Any]] = []
    lines: list[str] = []
    for series in SERIES:
        entries = walk(series.anilist_id)
        detail, episodes = tmdb_series(series.tmdb_id)
        tv_entries = [e for e in entries if e["format"] == "TV"]
        chained = by_chaining(tv_entries, detail)
        searched = search_tmdb(entries)
        found = searched["found"]
        chained2 = by_chaining(tv_entries, tmdb_series(found)[0]) if found else {}
        rows = []
        for entry in entries:
            # 只比 TV 條目：劇場版、OVA 用播出日對 Specials 或正篇常是巧合（CODE: White 上映那天
            # 正好播了 S02E12），列出 Fribb 怎麼對就好。
            right = (
                truth(entry, episodes)
                if entry["format"] == "TV"
                else {"season": None, "start": None, "end": None, "note": "不比（只比 TV 條目）"}
            )
            a = by_fribb(entry, fribb, series.tmdb_id)
            row: dict[str, Any] = {
                "anilist_id": entry["id"],
                "title": entry["title"]["romaji"],
                "format": entry["format"],
                "episodes": entry["episodes"],
                "start_date": iso(entry["startDate"]),
                "end_date": iso(entry["endDate"]),
                "fribb": a,
                "truth": right,
            }
            if entry["format"] == "TV":
                b = chained[entry["id"]]
                b2 = chained2.get(
                    entry["id"],
                    {"season": None, "start": None, "end": None, "note": searched.get("note", "")},
                )
                b2_verdict = verdict(b2, right)
                b2_how = how_wrong(b2, right) if b2_verdict == "錯" else ""
                if found != series.tmdb_id and right["season"] is not None:
                    b2_verdict = "錯"
                    b2_how = (
                        f"作品錯（找到 tv/{found} {searched.get('name')} "
                        f"{searched.get('first_air_date')}）"
                        if found
                        else f"作品沒找到（{searched.get('note')}）"
                    )
                row |= {
                    # Fribb 給的作品對不對：有劇集 id 才比；只對到電影的另記在 `fribb.movies`。
                    "fribb_tmdb_ok": a["tmdb_id"] == series.tmdb_id if "tmdb_id" in a else None,
                    "chained": b,
                    "searched": b2,
                    "a": verdict(a, right),
                    "b": verdict(b, right),
                    "b2": b2_verdict,
                    "a_how": how_wrong(a, right) if verdict(a, right) == "錯" else "",
                    "b_how": how_wrong(b, right) if verdict(b, right) == "錯" else "",
                    "b2_how": b2_how,
                }
            rows.append(row)
        seasons = [
            {
                "season_number": s["season_number"],
                "episode_count": s["episode_count"],
                "name": s["name"],
            }
            for s in detail["seasons"]
        ]
        report.append(
            {
                "series": series.key,
                "why": series.why,
                "group": series.group,
                "b2_search": searched,
                "b2_work_ok": found == series.tmdb_id,
                "anilist_root": series.anilist_id,
                "tmdb_id": series.tmdb_id,
                "tmdb_name": detail["name"],
                "tmdb_seasons": seasons,
                "entries": rows,
            }
        )
        lines += [
            f"### {detail['name']}（TMDB tv/{series.tmdb_id}）",
            "",
            f"{series.group}。{series.why}。B2 搜到的作品："
            + (
                f"tv/{found} {searched.get('name')}（{searched.get('first_air_date')}，"
                f"用「{searched.get('query')}」搜）"
                + ("，**對**" if found == series.tmdb_id else "，**錯**")
                if found
                else f"沒找到（{searched.get('note')}）"
            )
            + "。TMDB 的季："
            + "、".join(f"S{s['season_number']:02d} {s['episode_count']} 集" for s in seasons)
            + "。",
            "",
            "| AniList 條目 | 格式 | 集數 | A（Fribb） | B（串接，作品已知） "
            "| B2（串接，作品靠搜尋） | 正解 | A | B | B2 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            right = row["truth"]
            truth_text = (
                rng(right)
                if right["season"] is not None
                else "—"
                if row["format"] != "TV"
                else f"無法判定（{right['note']}）"
            )
            if right["season"] is not None and right["end"] is None:
                truth_text = f"{rng(right)}（{right['note']}）"
            a_cell = row.get("a", "")
            b_cell = row.get("b", "")
            if row.get("a_how"):
                a_cell += f"：{row['a_how']}"
            if row.get("b_how"):
                b_cell += f"：{row['b_how']}"
            b2_cell = row.get("b2", "")
            if row.get("b2_how"):
                b2_cell += f"：{row['b2_how']}"
            fribb_text = (
                rng(row["fribb"])
                if row["fribb"].get("covered")
                else f"未覆蓋（{row['fribb']['note']}）"
            )
            chained_text = rng(row["chained"]) if "chained" in row else "—"
            searched_text = rng(row["searched"]) if "searched" in row else "—"
            lines.append(
                f"| {row['anilist_id']} {row['title']} | {row['format']} | {row['episodes']} | "
                f"{fribb_text} | {chained_text} | {searched_text} | {truth_text} | "
                f"{a_cell or '—'} | {b_cell or '—'} | {b2_cell or '—'} |"
            )
        lines.append("")
        print(f"{series.key}: {len(entries)} entries, {len(tv_entries)} TV", file=sys.stderr)

    OUT_JSON.write_text(
        json.dumps(
            {"generated": "2026-10-28", "tolerance_days": TOLERANCE_DAYS, "series": report},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "tables.md").write_text("\n".join(lines), encoding="utf-8")
    tally: dict[str, dict[str, int]] = {}
    for item in report:
        for row in item["entries"]:
            for side in ("a", "b", "b2"):
                if side in row:
                    for key in (side, f"{side}:{item['group']}"):
                        bucket = tally.setdefault(key, {})
                        bucket[row[side]] = bucket.get(row[side], 0) + 1
    print(json.dumps(tally, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
