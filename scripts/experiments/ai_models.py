"""M5.5 票 02：AI 端點的模型清單帶 key 時實際回什麼（brief §20.26）。

量的是 `berth/adapters/ai/catalog.py` 照著寫的幾件事：

- Anthropic 接口 `GET {base}/v1/models`：`x-api-key` 與 `Authorization: Bearer` 各收不收、
  成功的形狀、分頁（`limit=1` 再帶 `after_id`）認不認；對照不帶 `/v1` 的 `{base}/models`。
- OpenAI 接口 `GET {base}/models`：成功的形狀。
- 兩支 key 錯時的 `401` 長什麼樣。

只用標準庫（`lib.py`），不 import berth。key 從一份 `.env` 讀（變數名同部署的
`AI_ANTHROPIC_API_KEY` / `AI_ANTHROPIC_BASE_URL`、`AI_OPENAI_API_KEY` / `AI_OPENAI_BASE_URL`），
**不印、不寫進任何檔案**：寫檔前檢查輸出裡沒有 key，有就一個檔都不寫。

    python3 scripts/experiments/ai_models.py record --env /path/to/.env

原始回應落在 .local/experiments/results/ai_models/（不進版控），只留內容型別的那一份寫進
tests/fixtures/http/ai_models/。只列模型，不花 token。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from lib import Response, request

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / ".local" / "experiments" / "results" / "ai_models"
FIXTURES = REPO / "tests" / "fixtures" / "http" / "ai_models"

ANTHROPIC_VERSION = "2023-06-01"
#: 錯的 key：看 401 的形狀。
WRONG_KEY = "sk-berth-experiment-not-a-real-key"
#: 寫進 fixture 的那幾份（其餘只留在 .local，是佐證）；`{a}` / `{o}` 是兩個接口的檔名前綴。
FIXTURE_NAMES = ("{a}.x-api-key", "{a}.bearer", "{a}.unauthorized", "{o}.ok", "{o}.unauthorized")
#: 只留內容型別：其餘是那一次的傳輸與 CDN 的東西，不是 API 的契約。
KEPT_HEADERS = {"content-type"}
UA = "Berth experiment (ai_models)"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


def need(values: dict[str, str], name: str) -> str:
    value = values.get(name, "")
    if not value:
        sys.exit(f"{name} is empty")
    return value


def anthropic_base(url: str) -> str:
    url = url.strip().rstrip("/")
    return url.removesuffix("/v1")


def label(base: str, interface: str) -> str:
    """fixture 檔名的前綴：認得的服務照名字，其餘照接口。"""
    host = urlsplit(base).hostname or ""
    vendor = "deepseek" if host.endswith("deepseek.com") else host.replace(".", "-")
    return f"{vendor}-anthropic" if interface == "anthropic" else vendor


def anthropic(
    base: str, key: str, params: dict[str, Any], *, bearer: bool = False, path: str = "/v1/models"
) -> Response:
    """`bearer` 為真時 key 走 `Authorization: Bearer`，否則走 `x-api-key`（SDK 與聊天用的）。"""
    auth = {"Authorization": f"Bearer {key}"} if bearer else {"x-api-key": key}
    headers = {**auth, "anthropic-version": ANTHROPIC_VERSION, "User-Agent": UA}
    return request(f"{base}{path}", headers=headers, params=params, timeout=30)


def openai(base: str, key: str) -> Response:
    headers = {"Authorization": f"Bearer {key}", "User-Agent": UA}
    return request(f"{base.rstrip('/')}/models", headers=headers, timeout=30)


def body_of(resp: Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text


def describe(name: str, resp: Response) -> None:
    answer = body_of(resp)
    types = [v for k, v in resp.headers.items() if k.lower() == "content-type"]
    print(f"{name}: {resp.status}  content-type={types[0] if types else '-'}")
    if isinstance(answer, dict):
        print(f"  top-level keys={sorted(answer)}")
        data = answer.get("data")
        if isinstance(data, list):
            ids = [item.get("id") for item in data if isinstance(item, dict)]
            print(f"  {len(data)} models: {ids}")
            if data and isinstance(data[0], dict):
                print(f"  item keys={sorted(data[0])}")
        for field in ("has_more", "first_id", "last_id", "error", "type"):
            if field in answer:
                print(f"  {field}={answer[field]!r}")
    else:
        print(f"  body={str(answer)[:200]!r}")


def record(env_path: Path) -> None:
    values = read_env(env_path)
    a_key, a_base = need(values, "AI_ANTHROPIC_API_KEY"), need(values, "AI_ANTHROPIC_BASE_URL")
    o_key, o_base = need(values, "AI_OPENAI_API_KEY"), need(values, "AI_OPENAI_BASE_URL")
    a_base = anthropic_base(a_base)
    a_label, o_label = label(a_base, "anthropic"), label(o_base, "openai")
    print(f"anthropic: {a_base}/v1/models; openai: {o_base.rstrip('/')}/models")

    responses: dict[str, Response] = {
        f"{a_label}.x-api-key": anthropic(a_base, a_key, {"limit": 1000}),
        f"{a_label}.bearer": anthropic(a_base, a_key, {"limit": 1000}, bearer=True),
        f"{a_label}.no-v1.x-api-key": anthropic(a_base, a_key, {}, path="/models"),
        f"{a_label}.no-v1.bearer": anthropic(a_base, a_key, {}, bearer=True, path="/models"),
        f"{a_label}.unauthorized": anthropic(a_base, WRONG_KEY, {"limit": 1000}),
        f"{o_label}.ok": openai(o_base, o_key),
        f"{o_label}.unauthorized": openai(o_base, WRONG_KEY),
    }
    first = anthropic(a_base, a_key, {"limit": 1}, bearer=True)
    responses[f"{a_label}.limit-1"] = first
    page = body_of(first)
    if isinstance(page, dict) and page.get("has_more") is True and page.get("last_id"):
        responses[f"{a_label}.limit-1.after"] = anthropic(
            a_base, a_key, {"limit": 1, "after_id": page["last_id"]}, bearer=True
        )
    else:
        print(f"{a_label}.limit-1: has_more is not true or no last_id, not asking for page 2")

    records = {
        name: {
            "body": body_of(resp),
            "headers": {k: v for k, v in resp.headers.items() if k.lower() in KEPT_HEADERS},
            "status": resp.status,
        }
        for name, resp in responses.items()
    }
    raw = {
        name: {"status": resp.status, "headers": resp.headers, "body": body_of(resp)}
        for name, resp in responses.items()
    }
    text = json.dumps([records, raw], ensure_ascii=False)
    if a_key in text or o_key in text:
        sys.exit("a key shows up in the responses: writing nothing")

    RESULTS.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    kept = {name.format(a=a_label, o=o_label) for name in FIXTURE_NAMES}
    for name, resp in responses.items():
        describe(name, resp)
        dump = json.dumps(raw[name], indent=2, ensure_ascii=False) + "\n"
        (RESULTS / f"{name}.json").write_text(dump, encoding="utf-8", newline="\n")
        if name in kept:
            fixture = json.dumps(records[name], indent=2, ensure_ascii=False) + "\n"
            (FIXTURES / f"{name}.json").write_text(fixture, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--env", type=Path, required=True, help=".env holding the AI_* variables")
    args = parser.parse_args()
    if args.command == "record":
        record(args.env)


if __name__ == "__main__":
    main()
