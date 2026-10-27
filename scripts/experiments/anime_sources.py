"""M5 票 16：AniList、Bangumi `/calendar` 與 Fribb 的表對真的服務實際回什麼，錄成契約測試的
fixture。

量的是 `berth/adapters/{anilist,bgm,fribb}` 要照著寫的幾件事：GraphQL 三種問法的形狀（標題搜尋、
依 id 取條目與關係、季表的分數分佈）、限流標頭、錯誤的 `errors`；放送表缺哪些格子；Fribb 的
`themoviedb_id`、`season`、`episode_offset` 長什麼樣。

**與其他實驗不同，這一支 import berth 的查詢字串**（`berth.adapters.anilist`）：fixture 要是
adapter 真的會送的那幾句的回應，抄一份會漂移。其餘只用標準庫（`lib.py`）。

    uv run python scripts/experiments/anime_sources.py record     # 原始回應落在 .local
    uv run python scripts/experiments/anime_sources.py fixtures   # 裁標頭與 Fribb，寫進 fixture

AniList 目前限 30 次 / 分：`record` 每次之間等 2.5 秒，Re:Zero 的系列圖一層一次。**不錄 429**：
要刻意撞上限才拿得到，而那正是條款不要的事；契約測試用文件上的範例（brief §20.3）。

原始回應落在 .local/experiments/results/anime_sources/，不進版控。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from lib import Response, request

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


from berth.adapters.anilist import ENTRIES_QUERY, SEARCH_QUERY, SEASON_QUERY  # noqa: E402
from berth.services.anilist import FOLLOWED  # noqa: E402

RESULTS = REPO / ".local" / "experiments" / "results" / "anime_sources"
FIXTURES = REPO / "tests" / "fixtures" / "http"

ANILIST = "https://graphql.anilist.co"
BGM = "https://api.bgm.tv/calendar"
FRIBB = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
USER_AGENT = "1morr/berth-experiment (https://github.com/1morr/Berth)"

#: `services/anilist.read_franchise` 預設沿的那幾種（不含 `SPIN_OFF`）。
FOLLOW = FOLLOWED
REZERO = 21355

#: Fribb 的表裁到這幾筆：Re:Zero 的每一輪與 OVA、季表前幾部、一部有電影 id 的（魔法公主）。
FRIBB_KEPT_EXTRA = {164}

KEPT_HEADERS = {
    "content-type",
    "retry-after",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "cache-control",
}


def anilist(name: str, query: str, variables: dict[str, Any]) -> Any:
    body = {"query": query, "variables": variables}
    resp = request(
        ANILIST,
        method="POST",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        json_body=body,
        timeout=60,
    )
    answer = save(name, body, resp)
    time.sleep(2.5)
    return answer


def save(name: str, sent: Any, resp: Response) -> Any:
    RESULTS.mkdir(parents=True, exist_ok=True)
    try:
        answer: Any = resp.json()
    except ValueError:
        answer = resp.text
    record = {"request": sent, "status": resp.status, "headers": resp.headers, "body": answer}
    out = RESULTS / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    limit = {k: v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")}
    print(f"{name}: {resp.status} {limit} → {out.relative_to(REPO)}")
    return answer


def cmd_record() -> None:
    anilist(
        "anilist/search.rezero",
        SEARCH_QUERY,
        {"q": "Re:Zero kara Hajimeru Isekai Seikatsu", "n": 8},
    )
    # 系列圖：一層一次（`id_in`），同 `services/anilist.read_franchise`。
    seen: set[int] = set()
    frontier = [REZERO]
    level = 0
    while frontier:
        ids = sorted(set(frontier) - seen)
        if not ids:
            break
        answer = anilist(f"anilist/entries.rezero.{level}", ENTRIES_QUERY, {"ids": ids, "n": 50})
        seen |= set(ids)
        frontier = []
        for media in answer["data"]["Page"]["media"]:
            for edge in media["relations"]["edges"]:
                node = edge["node"]
                if node["type"] == "ANIME" and edge["relationType"] in FOLLOW:
                    frontier.append(node["id"])
        level += 1
    anilist("anilist/season.fall-2026", SEASON_QUERY, {"s": "FALL", "y": 2026, "n": 25})
    anilist("anilist/entries.missing", ENTRIES_QUERY, {"ids": [999999999], "n": 50})
    anilist("anilist/bad-query", "query{Page{media(nope:1){id}}}", {})

    resp = request(BGM, headers={"User-Agent": USER_AGENT}, timeout=60)
    save("bgm/calendar", None, resp)

    resp = request(FRIBB, headers={"User-Agent": USER_AGENT}, timeout=300)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "fribb-anime-list-full.json").write_text(resp.text, encoding="utf-8")
    print(f"fribb: {resp.status} {len(resp.text)} chars")


def raw(name: str) -> dict[str, Any]:
    record: dict[str, Any] = json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))
    return record


def write(name: str, record: Any) -> None:
    out = FIXTURES / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"→ {out.relative_to(REPO)}")


def cmd_fixtures() -> None:
    names = [p.stem for p in (RESULTS / "anilist").glob("*.json")]
    for stem in sorted(names):
        rec = raw(f"anilist/{stem}")
        headers = {k.lower(): v for k, v in rec["headers"].items() if k.lower() in KEPT_HEADERS}
        write(
            f"anilist/{stem}",
            {
                "request": rec["request"],
                "status": rec["status"],
                "headers": headers,
                "body": rec["body"],
            },
        )
    rec = raw("bgm/calendar")
    headers = {k.lower(): v for k, v in rec["headers"].items() if k.lower() in KEPT_HEADERS}
    write("bgm/calendar", {"status": rec["status"], "headers": headers, "body": rec["body"]})

    # Fribb：整張 7.5 MB 不進 repo（也不該再散布，brief §20.3），只留測試要的幾筆、原樣。
    table = json.loads((RESULTS / "fribb-anime-list-full.json").read_text(encoding="utf-8"))
    kept = set(FRIBB_KEPT_EXTRA)
    for stem in names:
        if stem.startswith("entries.rezero"):
            kept |= {m["id"] for m in raw(f"anilist/{stem}")["body"]["data"]["Page"]["media"]}
    season = raw("anilist/season.fall-2026")["body"]["data"]["Page"]["media"]
    kept |= {m["id"] for m in season[:10]}
    excerpt = [e for e in table if e.get("anilist_id") in kept]
    write("fribb/anime-list-full.excerpt", excerpt)
    print(f"fribb excerpt: {len(excerpt)} of {len(table)} entries")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("record", "fixtures"))
    args = parser.parse_args()
    {"record": cmd_record, "fixtures": cmd_fixtures}[args.command]()


if __name__ == "__main__":
    main()
