"""M5 票 17：Tavily `POST /search` 對真的服務實際回什麼。

量的是 `berth/adapters/websearch/tavily.py` 要照著寫的幾件事：成功的形狀（`results[]` 的欄位、
`request_id`、`response_time`）、`include_domains` 收不收子網域（`wikipedia.org` 要對得到
`en.wikipedia.org`）、key 錯的 `401` 與參數錯的 `400` 長什麼樣。

只用標準庫（`lib.py`），不 import berth。key 只從環境變數讀，不寫進任何檔案：

    TAVILY_API_KEY   app.tavily.com 的那一把（成功的那一次花 1 credit）

    uv run python scripts/experiments/tavily_search.py record     # 三種回應，原始的落在 .local
    uv run python scripts/experiments/tavily_search.py fixtures   # 拿掉傳輸標頭，寫進 fixture

原始回應落在 .local/experiments/results/tavily_search/，不進版控。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from lib import Response, request

API = "https://api.tavily.com"
REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / ".local" / "experiments" / "results" / "tavily_search"
FIXTURES = REPO / "tests" / "fixtures" / "http" / "tavily"

#: 錄製時用的網域（`berth/services/web.py` 的 `SEARCH_DOMAINS` 的一部分；不 import berth）。
DOMAINS = [
    "anilist.co",
    "myanimelist.net",
    "bgm.tv",
    "animenewsnetwork.com",
    "wikipedia.org",
    "themoviedb.org",
    "imdb.com",
    "reddit.com",
]
QUERY = "Frieren: Beyond Journey's End season 2 reception"

FIXTURE_NAMES = ("search.ok", "search.unauthorized", "search.bad-request")
#: 只留內容型別：其餘是那一次的傳輸與 Cloudflare 的東西，不是 API 的契約。
KEPT_HEADERS = {"content-type", "retry-after"}


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"缺環境變數 {name}（見檔頭說明）")
    return value


def search(key: str, body: dict[str, Any]) -> Response:
    headers = {"Authorization": f"Bearer {key}", "User-Agent": "Berth experiment (tavily_search)"}
    return request(f"{API}/search", method="POST", headers=headers, json_body=body, timeout=60)


def save(name: str, body: dict[str, Any], resp: Response) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    try:
        answer: Any = resp.json()
    except ValueError:
        answer = resp.text
    record = {"request": body, "status": resp.status, "headers": resp.headers, "body": answer}
    out = RESULTS / f"{name}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"{name}: {resp.status} → {out.relative_to(REPO)}")
    if isinstance(answer, dict) and "results" in answer:
        for hit in answer["results"]:
            print(f"  {hit.get('url')}  score={hit.get('score')}  keys={sorted(hit)}")
        print(f"  top-level keys={sorted(answer)}")
    else:
        print(f"  body={answer!r}")


def cmd_record(key: str) -> None:
    ok = {
        "query": QUERY,
        "search_depth": "basic",
        "max_results": 5,
        "include_domains": DOMAINS,
    }
    save("search.ok", ok, search(key, ok))
    save("search.unauthorized", ok, search("tvly-dev-not-a-real-key", ok))
    # 文件：`include_domains_mode` 不帶 `include_domains` 是 400。
    bad = {"query": QUERY, "include_domains_mode": "prefer"}
    save("search.bad-request", bad, search(key, bad))


def cmd_fixtures() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name in FIXTURE_NAMES:
        record = json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))
        fixture = {
            "status": record["status"],
            "headers": {k: v for k, v in record["headers"].items() if k.lower() in KEPT_HEADERS},
            "body": record["body"],
        }
        out = FIXTURES / f"{name}.json"
        text = json.dumps(fixture, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out.relative_to(REPO)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("record")
    sub.add_parser("fixtures")
    args = parser.parse_args()
    if args.step == "record":
        cmd_record(env("TAVILY_API_KEY"))
    else:
        cmd_fixtures()


if __name__ == "__main__":
    main()
