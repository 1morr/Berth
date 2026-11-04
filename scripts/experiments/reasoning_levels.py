"""M5.5 票 17：推理程度送到真的 DeepSeek 時服務收不收、回不回推理文字（brief §20.26）。

照 Berth 自己的 `adapters.ai.build_model` 與 `chat_settings` 組請求（所以量的就是產品送的那一份），
兩種接口各送 `off` / `low` / `medium` / `high` 一次，記下：

- 送出的推理參數（請求本體裡的 `thinking`、`output_config`、`reasoning_effort`；**不記標頭**）；
- 服務的狀態碼（出錯時連同 body）；
- 回應裡有沒有推理文字、多長，與 output token。

key 從一份 `.env` 讀（變數名同部署的 `AI_ANTHROPIC_*` / `AI_OPENAI_*`），**不印、不寫進任何檔案**：
寫檔前檢查輸出裡沒有 key，有就不寫。原始結果落在 `.local/experiments/results/reasoning_levels/`
（不進版控）。一共 8 次很短的呼叫，花得到幾分錢。

    uv run python scripts/experiments/reasoning_levels.py --env /path/to/.env
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx2
from pydantic_ai import ModelRequest, ThinkingPart
from pydantic_ai.direct import model_request
from pydantic_ai.exceptions import ModelHTTPError

from berth.adapters.ai import AiEndpoint, build_model, chat_settings
from berth.domain import AiProvider, AiReasoning

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / ".local" / "experiments" / "results" / "reasoning_levels"
PROMPT = "What is 17 * 23? Reply with the number only."
MAX_TOKENS = 2048
#: 請求本體裡與推理有關的幾格。
REASONING_KEYS = ("thinking", "output_config", "reasoning_effort")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


def endpoints(values: dict[str, str]) -> list[AiEndpoint]:
    found = []
    for provider, prefix in (
        (AiProvider.ANTHROPIC, "AI_ANTHROPIC"),
        (AiProvider.OPENAI, "AI_OPENAI"),
    ):
        key = values.get(f"{prefix}_API_KEY", "")
        model = values.get(f"{prefix}_MODEL", "")
        if key and model:
            found.append(AiEndpoint(provider, values.get(f"{prefix}_BASE_URL", ""), key, model))
    if not found:
        sys.exit("no AI_ANTHROPIC_* or AI_OPENAI_* key and model in the .env")
    return found


async def one(endpoint: AiEndpoint) -> dict[str, Any]:
    sent: list[dict[str, Any]] = []

    async def record(request: httpx2.Request) -> None:
        body = json.loads(request.content or b"{}")
        sent.append({key: body[key] for key in REASONING_KEYS if key in body})

    client = httpx2.AsyncClient(event_hooks={"request": [record]}, timeout=120)
    model = build_model(endpoint, http_client=client)
    row: dict[str, Any] = {
        "provider": endpoint.provider.value,
        "base_host": httpx2.URL(endpoint.base_url or "https://official").host,
        "model": endpoint.model,
        "reasoning": endpoint.reasoning.value,
    }
    settings = chat_settings(endpoint, model, MAX_TOKENS)
    settings["max_retries"] = 0  # 量的是第一個回應怎麼說
    try:
        response = await model_request(
            model, [ModelRequest.user_text_prompt(PROMPT)], model_settings=settings
        )
    except ModelHTTPError as exc:
        row |= {"status": exc.status_code, "error": exc.body}
    else:
        thoughts = [p.content for p in response.parts if isinstance(p, ThinkingPart)]
        row |= {
            "status": 200,
            "reasoning_chars": sum(len(text) for text in thoughts),
            "output_tokens": response.usage.output_tokens,
            "answer": response.text,
        }
    finally:
        await client.aclose()
    row["sent"] = sent[0] if sent else None
    return row


async def main(env: Path) -> int:
    values = read_env(env)
    rows = []
    for base in endpoints(values):
        for level in AiReasoning:
            rows.append(await one(replace(base, reasoning=level)))
    text = json.dumps(rows, ensure_ascii=False, indent=2)
    keys = [value for name, value in values.items() if name.endswith("_API_KEY") and value]
    if any(key in text for key in keys):
        sys.exit("a key showed up in the output; nothing written")
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "levels.json").write_text(text + "\n", encoding="utf-8")
    for row in rows:
        print(
            row["provider"],
            row["model"],
            row["reasoning"],
            row["status"],
            json.dumps(row["sent"]),
            row.get("reasoning_chars", "-"),
            row.get("output_tokens", "-"),
            str(row.get("error", ""))[:160],
        )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, required=True)
    sys.exit(asyncio.run(main(parser.parse_args().env)))
