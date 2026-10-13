"""M4 票 84：季的搜尋記號寫 `Season N` 還是 `SNN`，真的索引站回哪個比較多。

對每一對查詢呼叫 Prowlarr `GET /api/v1/search?type=search&limit=100`，
逐站（回應每筆的 `indexer`）數：
總筆數、發佈名真的含那部作品名字的筆數（The Pirate Bay 對查不到的字會回熱門清單，純筆數會騙人），
以及名字對得上的那些裡，發佈名自己寫 `SNN` / `Season N` / 兩者皆無各幾筆（索引站有沒有做模糊比對）。

只用標準庫，不 import berth。公開站會封 IP：每次查詢間隔 >= 3 秒，總查詢數上限 30。
用法：
    export PROWLARR_URL=http://127.0.0.1:19784 PROWLARR_API_KEY=...
    python scripts/experiments/season_token_compare.py
    python scripts/experiments/season_token_compare.py http://127.0.0.1:19784 <api key>
原始 JSON 寫到 .local/experiments/results/season_token_compare.json。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

MAX_QUERIES = 30
SLEEP = 3.5

# (作品顯示名, 用來比對發佈名的名字別名, 季號, 查詢模板)
CASES: list[tuple[str, list[str], int, str, str]] = [
    ("The Bear", ["the bear"], 3, "The Bear Season 3", "The Bear S03"),
    ("Severance", ["severance"], 2, "Severance Season 2", "Severance S02"),
    (
        "SPY x FAMILY",
        ["spy x family", "spy family", "spyxfamily"],
        2,
        "SPY x FAMILY Season 2",
        "SPY x FAMILY S02",
    ),
    ("Frieren", ["frieren"], 2, "Frieren Season 2", "Frieren S02"),
    ("Oshi no Ko", ["oshi no ko"], 2, "Oshi no Ko Season 2", "Oshi no Ko S02"),
    (
        "间谍过家家",
        ["间谍过家家", "間諜過家家", "spy x family", "spy family"],
        2,
        "间谍过家家 第2季",
        "间谍过家家 S02",
    ),
]


def norm(s: str) -> str:
    s = s.lower().replace(".", " ").replace("_", " ")
    s = re.sub(r"[^\w\u3400-\u9fff]+", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


def name_hit(title: str, aliases: list[str]) -> bool:
    t = norm(title)
    return any(norm(a) in t for a in aliases)


def marker(title: str, n: int) -> str:
    t = norm(title)
    s_form = re.search(rf" s0*{n}(?: |e\d)", t) or re.search(rf" s0*{n}e\d", t)
    word = re.search(rf" (?:season|series) 0*{n} ", t) or re.search(rf"第\s*0*{n}\s*[季期]", t)
    if s_form and word:
        return "both"
    return "snn" if s_form else "season" if word else "none"


def search(base: str, key: str, q: str) -> list[dict[str, Any]]:
    url = f"{base}/api/v1/search?" + urllib.parse.urlencode(
        {"query": q, "type": "search", "limit": 100}
    )
    req = urllib.request.Request(url, headers={"X-Api-Key": key})
    with urllib.request.urlopen(req, timeout=180) as r:
        rows: list[dict[str, Any]] = json.load(r)
        return rows


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PROWLARR_URL", "")).rstrip("/")
    key = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PROWLARR_API_KEY", "")
    if not base or not key:
        print(__doc__)
        return 2
    if len(CASES) * 2 > MAX_QUERIES:
        raise SystemExit("too many queries")
    out: list[dict[str, Any]] = []
    first = True
    for show, aliases, n, q_season, q_snn in CASES:
        for kind, q in (("season", q_season), ("snn", q_snn)):
            if not first:
                time.sleep(SLEEP)
            first = False
            try:
                rows = search(base, key, q)
                err = None
            except Exception as e:
                rows, err = [], repr(e)
            per: dict[str, dict[str, int]] = defaultdict(
                lambda: {"total": 0, "name": 0, "snn": 0, "season": 0, "both": 0, "none": 0}
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
    dest = Path(".local/experiments/results/season_token_compare.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {"date": time.strftime("%Y-%m-%d"), "results": out}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    print(
        f"{'query':32} {'indexer':16} {'total':>5} {'name':>5}"
        " | name hits with: snn season both none"
    )
    for o in out:
        if o["error"]:
            print(f"{o['query']:32} ERROR {o['error']}")
        for ix, p in sorted(o["per_indexer"].items()):
            print(
                f"{o['query']:32} {ix:16} {p['total']:5} {p['name']:5} | "
                f"{p['snn']:12} {p['season']:6} {p['both']:4} {p['none']:4}"
            )
        if not o["per_indexer"] and not o["error"]:
            print(f"{o['query']:32} (no results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
