"""M5.6 票 02：只有一季的作品，第 1 季整季缺時，索引站認哪一種查詢。

`services/search_queries.missing_batches` 整季缺時送「名字 × 季記號」。只有一季的番，發佈名
不寫「第1季」／`S01`／`Season 1`，所以要量：帶記號的查詢在動畫站回幾筆、不帶記號的名字回幾筆。
多季作品當對照：它們第 1 季的發佈多半也不寫記號，但記號仍問得到一些，所以修法只動只有一季的作品。

對每一個查詢呼叫 Prowlarr `GET /api/v1/search?type=search&limit=100`，
逐站（回應每筆的 `indexer`）數：
總筆數、發佈名真的含那部作品名字的筆數（The Pirate Bay 對查不到的字會回熱門清單，純筆數會騙人），
以及名字對得上的那些裡，發佈名自己寫了哪一種季記號（`第N季`、`SNN`、`Season N`、都沒有、別季）。

只用標準庫，不 import berth。公開站會封 IP：每次查詢間隔 >= 3 秒，總查詢數上限 20。
用法：
    export PROWLARR_URL=http://127.0.0.1:9696 PROWLARR_API_KEY=...
    python scripts/experiments/single_season_marks.py
    python scripts/experiments/single_season_marks.py http://127.0.0.1:9696 <api key>
原始 JSON 寫到 .local/experiments/results/single_season_marks.json。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from lib import name_hit, norm_title, prowlarr_search

MAX_QUERIES = 20
SLEEP = 3.5

# (作品, 比對發佈名用的名字, 季號, [(種類, 查詢)])
# 前兩部只有一季（譯名以 TMDB 為準）；後兩部是多季作品的對照組。
CASES: list[tuple[str, list[str], int, list[tuple[str, str]]]] = [
    (
        "私を喰べたい、ひとでなし（只有一季，CJK）",
        ["私を喰べたい", "ひとでなし", "想吃掉我的非人少女", "想吃掉我的", "非人少女"],
        1,
        [
            ("marked_cjk", "私を喰べたい、ひとでなし 第1季"),
            ("bare", "私を喰べたい、ひとでなし"),
            ("marked_cjk_zh", "想吃掉我的非人少女 第1季"),
            ("bare_zh", "想吃掉我的非人少女"),
        ],
    ),
    (
        "進撃の巨人（多季對照，CJK）",
        ["進撃の巨人", "进击的巨人", "attack on titan", "shingeki no kyojin"],
        1,
        [
            ("marked_cjk", "進撃の巨人 第1季"),
            ("bare", "進撃の巨人"),
        ],
    ),
    (
        "Death Note（只有一季，拉丁字）",
        ["death note"],
        1,
        [
            ("marked_snn", "Death Note S01"),
            ("marked_word", "Death Note Season 1"),
            ("bare", "Death Note"),
        ],
    ),
    (
        "SPY x FAMILY（多季對照，拉丁字）",
        ["spy x family", "spy family", "spyxfamily", "間諜家家酒", "间谍过家家"],
        1,
        [
            ("marked_snn", "SPY x FAMILY S01"),
            ("marked_word", "SPY x FAMILY Season 1"),
            ("bare", "SPY x FAMILY"),
        ],
    ),
]


def marker(title: str, n: int) -> str:
    """這一筆自己寫的季記號：`第N季`、`SNN`、`Season N`、都沒有、或是別季。"""
    t = norm_title(title)
    if re.search(rf"第\s*0*{n}\s*[季期]", t):
        return "cjk"
    s_form = re.search(rf" s0*{n}(?: |e\d)", t)
    word = re.search(rf" (?:season|series) 0*{n}(?: |$)", t)
    if s_form and word:
        return "both"
    if s_form:
        return "snn"
    if word:
        return "season"
    # 別季的記號：名字對得上卻寫著另一個季，不帶記號的名字才會撈到這種。
    if re.search(r"第\s*0*\d+\s*[季期]", t) or re.search(r" s0*\d+(?: |e\d)", t):
        return "other_season"
    return "none"


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PROWLARR_URL", "")).rstrip("/")
    key = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PROWLARR_API_KEY", "")
    if not base or not key:
        print(__doc__)
        return 2
    total = sum(len(queries) for _, _, _, queries in CASES)
    if total > MAX_QUERIES:
        raise SystemExit(f"too many queries: {total}")
    out: list[dict[str, Any]] = []
    first = True
    for show, aliases, n, queries in CASES:
        for kind, q in queries:
            if not first:
                time.sleep(SLEEP)
            first = False
            try:
                rows = prowlarr_search(base, key, q)
                err = None
            except Exception as e:
                rows, err = [], repr(e)
            per: dict[str, dict[str, int]] = defaultdict(
                lambda: {
                    "total": 0,
                    "name": 0,
                    "cjk": 0,
                    "snn": 0,
                    "season": 0,
                    "both": 0,
                    "other_season": 0,
                    "none": 0,
                }
            )
            for r in rows:
                p = per[r.get("indexer", "?")]
                p["total"] += 1
                if name_hit(r.get("title", ""), aliases):
                    p["name"] += 1
                    p[marker(r["title"], n)] += 1
            out.append(
                {
                    "show": show,
                    "kind": kind,
                    "query": q,
                    "error": err,
                    "per_indexer": per,
                    "titles": [(r.get("indexer"), r.get("title")) for r in rows],
                }
            )
    dest = Path(".local/experiments/results/single_season_marks.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {"date": time.strftime("%Y-%m-%d"), "results": out}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    print(
        f"{'query':40} {'indexer':16} {'total':>5} {'name':>5}"
        " | name hits with: cjk snn season none other"
    )
    for o in out:
        if o["error"]:
            print(f"{o['query']:40} ERROR {o['error']}")
        for ix, p in sorted(o["per_indexer"].items()):
            print(
                f"{o['query']:40} {ix:16} {p['total']:5} {p['name']:5} | "
                f"{p['cjk']:3} {p['snn']:3} {p['season']:6} {p['none']:4} {p['other_season']:5}"
            )
        if not o["per_indexer"] and not o["error"]:
            print(f"{o['query']:40} (no results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
