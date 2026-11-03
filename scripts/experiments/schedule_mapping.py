"""M5.5 票 14：時間表的卡片（TMDB）對得到幾成 AniList 與 Bangumi 的作品。

時刻（AniList `AiringSchedule`）與評分（Bangumi）只在「對得到」的卡片上顯示，對不上就不顯示、不猜。
Berth 沒有 TMDB 對 AniList / Bangumi 的 id 對照表（Fribb 在 M5 票 23d 拿掉，brief §20.3），
所以比兩種對應：

1. **Wikidata**：`tv/{id}` 帶 `append_to_response=external_ids` 拿 `wikidata_id`（同一個請求），
   再讀 Wikidata 的 P8729（AniList anime ID）與 P5732（Bangumi subject ID）。純 id，不比標題。
2. **原文標題相同**：TMDB `original_name` 與 AniList `title.native` / Bangumi `name` 壓平後完全相同
   （NFKC、小寫、只留字母數字），而且那一邊這一週也有一集。

卡片的範圍與票 09 的時間表一樣：discover（`with_genres=16`、`ja|zh`、週界前後放寬一天），每部的
上一集與下一集落在這一週的才算一張。AniList 這一週的 `airingSchedules` 全部頁數，
Bangumi `/calendar`。

只用標準庫，不 import berth。TMDB 憑證讀 `TMDB_API_KEY`；AniList、Bangumi、Wikidata 免 key。
回應快取在 `.local/experiments/cache/schedule_mapping/`（快取鍵帶日期），結果 JSON 落在
`.local/experiments/results/schedule_mapping/`。

    uv run --env-file .env python scripts/experiments/schedule_mapping.py
    uv run --env-file .env python scripts/experiments/schedule_mapping.py --week 2026-11-02
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import unicodedata
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from lib import request

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / ".local" / "experiments" / "cache" / "schedule_mapping"
RESULTS = REPO / ".local" / "experiments" / "results" / "schedule_mapping"

TMDB = "https://api.themoviedb.org/3"
BGM = "https://api.bgm.tv"
ANILIST = "https://graphql.anilist.co"
WIKIDATA = "https://www.wikidata.org/w/api.php"
UA = "1morr/berth-experiment (https://github.com/1morr/Berth)"
JST = ZoneInfo("Asia/Tokyo")

ANILIST_PROP = "P8729"
BANGUMI_PROP = "P5732"

AIRING_QUERY = (
    "query($p:Int,$a:Int,$b:Int){Page(page:$p,perPage:50){pageInfo{hasNextPage}"
    "airingSchedules(airingAt_greater:$a,airingAt_lesser:$b,sort:TIME){"
    "airingAt episode media{id idMal format countryOfOrigin title{romaji native} synonyms}}}}"
)

TODAY = date.today()


def cached(key: str, fetch: Callable[[], Any]) -> Any:
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
            raise SystemExit(f"TMDB {path}: {resp.status}")
        return resp.json()

    return cached(f"tmdb:{path}?{query}", fetch)


def anilist(variables: dict[str, int]) -> Any:
    def fetch() -> Any:
        time.sleep(2.1)  # 30 次 / 分（brief §20.3）
        resp = request(
            ANILIST,
            method="POST",
            json_body={"query": AIRING_QUERY, "variables": variables},
            headers={"User-Agent": UA},
        )
        if resp.status != 200:
            raise SystemExit(f"AniList: {resp.status} {resp.text[:200]}")
        return resp.json()["data"]

    return cached(f"anilist:{json.dumps(variables, sort_keys=True)}", fetch)


def wikidata(ids: list[str]) -> dict[str, Any]:
    def fetch() -> Any:
        resp = request(
            WIKIDATA,
            params={
                "action": "wbgetentities",
                "ids": "|".join(ids),
                "props": "claims",
                "format": "json",
            },
            headers={"User-Agent": UA},
        )
        if resp.status != 200:
            raise SystemExit(f"Wikidata: {resp.status}")
        return resp.json()["entities"]

    entities: dict[str, Any] = cached(f"wikidata:{'|'.join(ids)}", fetch)
    return entities


def bgm_calendar() -> list[dict[str, Any]]:
    def fetch() -> Any:
        resp = request(f"{BGM}/calendar", headers={"User-Agent": UA})
        if resp.status != 200:
            raise SystemExit(f"Bangumi: {resp.status}")
        return resp.json()

    return [item for day in cached("bgm:/calendar", fetch) for item in day["items"]]


def squash(title: str) -> str:
    text = unicodedata.normalize("NFKC", title or "").lower()
    return "".join(ch for ch in text if ch.isalnum())


def claim(entity: dict[str, Any], prop: str) -> list[str]:
    values = []
    for c in entity.get("claims", {}).get(prop, []):
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str):
            values.append(value)
    return values


def cards(start: date, end: date) -> list[dict[str, Any]]:
    params = {
        "with_genres": "16",
        "with_original_language": "ja|zh",
        "air_date.gte": (start - timedelta(days=1)).isoformat(),
        "air_date.lte": (end + timedelta(days=1)).isoformat(),
        "language": "en-US",
    }
    first = tmdb("/discover/tv", {**params, "page": "1"})
    rows = list(first["results"])
    for page in range(2, int(first["total_pages"]) + 1):
        rows += tmdb("/discover/tv", {**params, "page": str(page)})["results"]
    found: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()
    for row in rows:
        detail = tmdb(
            f"/tv/{row['id']}", {"language": "zh-TW", "append_to_response": "external_ids"}
        )
        if detail is None:
            continue
        for ep in (detail.get("last_episode_to_air"), detail.get("next_episode_to_air")):
            if not ep or not ep.get("air_date"):
                continue
            aired = date.fromisoformat(ep["air_date"])
            key = (row["id"], ep["season_number"], ep["episode_number"])
            if not start <= aired <= end or key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "tmdb_id": row["id"],
                    "original_name": row.get("original_name") or "",
                    "language": row.get("original_language"),
                    "air_date": aired.isoformat(),
                    "season": ep["season_number"],
                    "episode": ep["episode_number"],
                    "wikidata_id": (detail.get("external_ids") or {}).get("wikidata_id"),
                    # 卡片那一季的開播日：評分的季別守衛拿它對 Bangumi 條目的開播日。
                    "season_air_date": next(
                        (
                            s.get("air_date") or ""
                            for s in detail.get("seasons") or []
                            if s.get("season_number") == ep["season_number"]
                        ),
                        "",
                    ),
                }
            )
    return found


def airing(start: date, end: date) -> list[dict[str, Any]]:
    lo = datetime.combine(start - timedelta(days=1), datetime.min.time(), JST)
    hi = datetime.combine(end + timedelta(days=2), datetime.min.time(), JST)
    found: list[dict[str, Any]] = []
    page = 1
    while True:
        data = anilist({"p": page, "a": int(lo.timestamp()), "b": int(hi.timestamp())})["Page"]
        found += data["airingSchedules"]
        if not data["pageInfo"]["hasNextPage"]:
            return found
        page += 1


def run(start: date) -> dict[str, Any]:
    end = start + timedelta(days=6)
    week = cards(start, end)
    schedules = airing(start, end)
    calendar = bgm_calendar()

    qids = sorted({c["wikidata_id"] for c in week if c["wikidata_id"]})
    entities: dict[str, Any] = {}
    for i in range(0, len(qids), 50):
        entities |= wikidata(qids[i : i + 50])

    anilist_by_id: dict[int, list[dict[str, Any]]] = {}
    anilist_by_title: dict[str, set[int]] = {}
    for s in schedules:
        media = s["media"]
        anilist_by_id.setdefault(media["id"], []).append(s)
        anilist_by_title.setdefault(squash(media["title"]["native"]), set()).add(media["id"])
    bgm_by_id = {item["id"]: item for item in calendar}
    bgm_by_title: dict[str, set[int]] = {}
    for item in calendar:
        bgm_by_title.setdefault(squash(item.get("name") or ""), set()).add(item["id"])

    for card in week:
        entity = entities.get(card["wikidata_id"] or "", {})
        card["wd_anilist"] = [int(v) for v in claim(entity, ANILIST_PROP) if v.isdigit()]
        card["wd_bangumi"] = [int(v) for v in claim(entity, BANGUMI_PROP) if v.isdigit()]
        card["wd_anilist_airing"] = [a for a in card["wd_anilist"] if a in anilist_by_id]
        card["wd_bangumi_calendar"] = [b for b in card["wd_bangumi"] if b in bgm_by_id]
        key = squash(card["original_name"])
        card["title_anilist"] = sorted(anilist_by_title.get(key, ())) if key else []
        card["title_bangumi"] = sorted(bgm_by_title.get(key, ())) if key else []
        card["future"] = card["air_date"] >= TODAY.isoformat()
        card["bgm_air_dates"] = [bgm_by_id[b].get("air_date") or "" for b in card["title_bangumi"]]
        rating = (
            (bgm_by_id[card["title_bangumi"][0]].get("rating") or {})
            if card["title_bangumi"]
            else {}
        )
        card["bgm_rated"] = bool(rating.get("score")) and bool(rating.get("total"))

    return {"week": start.isoformat(), "cards": week, "anilist_media": len(anilist_by_id)}


#: 評分的季別守衛（M5.5 票 14）：Bangumi 開播日與 TMDB 那一季開播日相差幾天以內算同一季。
SEASON_TOLERANCES = (0, 1, 3, 7, 14, 30, 60)
#: 產品用的容差（`services/schedule.SEASON_START_SLACK`）。
SEASON_SLACK = 1


def season_gap(card: dict[str, Any]) -> int | None:
    """原文名對到唯一一筆 Bangumi 時，它的開播日與 TMDB 那一季開播日差幾天；缺日期是 None。"""
    if len(card["title_bangumi"]) != 1 or not card["season_air_date"]:
        return None
    bgm_date = card["bgm_air_dates"][0]
    if not bgm_date:
        return None
    return (date.fromisoformat(bgm_date) - date.fromisoformat(card["season_air_date"])).days


def report_season_guard(week: list[dict[str, Any]]) -> None:
    sub = [c for c in week if c["language"] == "ja"]
    matched = [c for c in sub if len(c["title_bangumi"]) == 1]
    print(
        f"\n評分的季別守衛（日本 {len(sub)} 張，原文名對到唯一一筆 Bangumi 的 {len(matched)} 張）"
    )
    for tolerance in SEASON_TOLERANCES:
        kept = [c for c in matched if (g := season_gap(c)) is not None and abs(g) <= tolerance]
        print(
            f"  容差 ±{tolerance:>2} 天：{len(kept)}/{len(sub)} = {100 * len(kept) / len(sub):.1f}%"
        )
    rated = [c for c in matched if c["bgm_rated"]]
    guarded = [c for c in rated if (g := season_gap(c)) is not None and abs(g) <= SEASON_SLACK]
    n = len(sub)
    print(
        f"  會顯示評分（有分數也有人數）：守衛前 {len(rated)}/{n} = {100 * len(rated) / n:.1f}%，"
    )
    print(f"    守衛後（±{SEASON_SLACK} 天）{len(guarded)}/{n} = {100 * len(guarded) / n:.1f}%")
    print("  差距（Bangumi − TMDB 那一季，天）：")
    for c in sorted(matched, key=lambda c: abs(season_gap(c) or 10**6)):
        print(
            f"    {season_gap(c)!s:>6}  tmdb {c['tmdb_id']} S{c['season']:02d} "
            f"{c['season_air_date'] or '-'} / bgm {c['title_bangumi'][0]} "
            f"{c['bgm_air_dates'][0] or '-'}  {c['original_name'][:28]}"
        )


def report(result: dict[str, Any]) -> None:
    week = result["cards"]
    print(
        f"週 {result['week']}：卡片 {len(week)} 張，"
        f"AniList 這週有放送的作品 {result['anilist_media']} 部"
    )
    for lang in ("ja", "zh"):
        sub = [c for c in week if c["language"] == lang]
        n = len(sub)
        if not n:
            continue

        def pct(k: int, n: int = n) -> str:
            return f"{k}/{n} = {100 * k / n:.1f}%"

        print(f"\n[{lang}] 卡片 {n}（未來的 {sum(c['future'] for c in sub)}）")
        print("  有 wikidata_id       ", pct(sum(bool(c["wikidata_id"]) for c in sub)))
        print("  Wikidata→AniList     ", pct(sum(bool(c["wd_anilist"]) for c in sub)))
        print("   …且這週在 AniList 放送", pct(sum(bool(c["wd_anilist_airing"]) for c in sub)))
        print("  Wikidata→Bangumi     ", pct(sum(bool(c["wd_bangumi"]) for c in sub)))
        print("   …且在 Bangumi 放送表 ", pct(sum(bool(c["wd_bangumi_calendar"]) for c in sub)))
        print("  原文標題→AniList     ", pct(sum(bool(c["title_anilist"]) for c in sub)))
        print("  原文標題→Bangumi     ", pct(sum(bool(c["title_bangumi"]) for c in sub)))
        either_a = sum(bool(c["wd_anilist_airing"] or c["title_anilist"]) for c in sub)
        either_b = sum(bool(c["wd_bangumi_calendar"] or c["title_bangumi"]) for c in sub)
        print("  AniList 任一         ", pct(either_a))
        print("  Bangumi 任一         ", pct(either_b))
        # 兩種都對到時是否一致（不一致的是誤配的候選）。
        for name, wd, ti in (
            ("AniList", "wd_anilist_airing", "title_anilist"),
            ("Bangumi", "wd_bangumi_calendar", "title_bangumi"),
        ):
            both = [c for c in sub if c[wd] and c[ti]]
            differ = [c for c in both if set(c[wd]) != set(c[ti])]
            print(f"  {name} 兩種都對到 {len(both)}，不一致 {len(differ)}")
            for c in differ:
                print(
                    f"    tmdb {c['tmdb_id']} {c['original_name']}: wikidata {c[wd]} 標題 {c[ti]}"
                )

    print("\n只有標題對到、Wikidata 沒對到（日本）：")
    for c in week:
        if c["language"] != "ja":
            continue
        a = c["title_anilist"] and not c["wd_anilist_airing"]
        b = c["title_bangumi"] and not c["wd_bangumi_calendar"]
        if a or b:
            print(
                f"  tmdb {c['tmdb_id']} {c['original_name']} wd={c['wikidata_id']} "
                f"AL={c['title_anilist'] if a else ''} BGM={c['title_bangumi'] if b else ''}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week", type=date.fromisoformat, help="週一（預設這一週）")
    args = parser.parse_args()
    start = args.week or TODAY - timedelta(days=TODAY.weekday())
    result = run(start)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{start.isoformat()}-{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    report(result)
    report_season_guard(result["cards"])
    print(f"\n結果：{out.relative_to(REPO)}", file=sys.stderr)


if __name__ == "__main__":
    main()
