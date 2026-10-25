# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "anthropic==2.3.0",
#     "openai==3.37.0",
#     "httpx==0.28.1",
#     "respx==0.23.1",
# ]
# ///
"""M5 票 07：官方 SDK 能不能用專案現有的 respx 測（docs/research/ai-providers.md 結論 1）。

第一次嘗試的票 06 寫的，2026-10-25 重量。

`anthropic` 1.0 與 `openai` 3.0 起底層改用 `httpx2`，respx 只 patch `httpx`。這支量三件事：

1. `respx-plain`：照專案的寫法用 respx 攔，兩個 SDK 的請求有沒有被攔到。
2. `respx-alias`：在 import respx 之前呼叫 `httpx2.alias_httpx()`（官方 MIGRATION 給的解法），
   攔不攔得到。另開子程序跑，因為 alias 會改掉整個程序的 `import httpx`。
3. `stream-error`：Anthropic 的串流在 200 之後送 `event: error`（overloaded），SDK 拋的是哪個型別。

不打網路、不用憑證，SDK 在臨時環境裡（PEP 723），不進 Berth 的依賴：

    uv run --script scripts/experiments/ai_sdk_mocking.py

2026-10-24 與 2026-10-25 兩次的結果相同，寫在 brief §20.24
（全文在 docs/research/ai-providers.md 結論 1）。
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from typing import Any

BASE = "https://provider.test"
ANTHROPIC_BODY = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "m",
    "content": [{"type": "text", "text": "hi"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 1, "output_tokens": 1},
}
OPENAI_BODY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 0,
    "model": "m",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


async def _call_both() -> dict[str, str]:
    """各打一次最小請求，回報每個 SDK 是被攔到（`intercepted`）還是真的去連線（例外名稱）。"""
    import anthropic  # type: ignore[import-not-found]  # 只在 PEP 723 的臨時環境裡有
    import openai  # type: ignore[import-not-found]  # 同上

    out: dict[str, str] = {}
    try:
        anthropic_client = anthropic.AsyncAnthropic(base_url=BASE, api_key="k", max_retries=0)
        await anthropic_client.messages.create(
            model="m", max_tokens=5, messages=[{"role": "user", "content": "a"}]
        )
        out["anthropic"] = "intercepted"
    except Exception as exc:  # 量的就是它拋什麼
        out["anthropic"] = type(exc).__name__
    try:
        openai_client = openai.AsyncOpenAI(base_url=f"{BASE}/v1", api_key="k", max_retries=0)
        await openai_client.chat.completions.create(
            model="m", messages=[{"role": "user", "content": "a"}]
        )
        out["openai"] = "intercepted"
    except Exception as exc:  # 同上
        out["openai"] = type(exc).__name__
    return out


def respx_plain() -> dict[str, str]:
    import httpx
    import respx

    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{BASE}/v1/messages").mock(return_value=httpx.Response(200, json=ANTHROPIC_BODY))
        mock.post(f"{BASE}/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=OPENAI_BODY)
        )
        return asyncio.run(_call_both())


def respx_alias_child() -> dict[str, str]:
    import httpx2  # type: ignore[import-not-found]  # 只在 PEP 723 的臨時環境裡有

    httpx2.alias_httpx()  # 必須在任何 `import httpx`（含 respx 的）之前
    return respx_plain()


def stream_error() -> str:
    import anthropic
    import httpx2

    def sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    body = sse(
        "message_start",
        {
            "type": "message_start",
            "message": {**ANTHROPIC_BODY, "content": [], "stop_reason": None},
        },
    ) + sse(
        "error", {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
    )

    def handler(request: Any) -> Any:
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=body.encode()
        )

    async def stream_once() -> str:
        client = anthropic.AsyncAnthropic(
            base_url=BASE,
            api_key="k",
            max_retries=0,
            http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
        )
        try:
            async with client.messages.stream(
                model="m", max_tokens=5, messages=[{"role": "user", "content": "a"}]
            ) as stream:
                await stream.get_final_message()
        except Exception as exc:  # 量的就是它拋什麼
            return f"{type(exc).__name__} status={getattr(exc, 'status_code', None)}"
        return "no error"

    return asyncio.run(stream_once())


def main() -> None:
    if sys.argv[1:] == ["--alias-child"]:
        print(json.dumps(respx_alias_child()))
        return
    print("respx-plain :", respx_plain())
    child = subprocess.run(
        [sys.executable, __file__, "--alias-child"], capture_output=True, text=True, check=False
    )
    print("respx-alias :", child.stdout.strip() or child.stderr.strip().splitlines()[-1])
    print("stream-error:", stream_error())


if __name__ == "__main__":
    main()
