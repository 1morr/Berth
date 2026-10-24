"""兩種格式的 adapter 共用的 HTTP 細節：逾時、狀態碼的分類、`retry-after`、主機名、模型清單。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from urllib.parse import urlsplit

import httpx

from berth.adapters.ai import AiProviderError
from berth.adapters.http import HttpSession, ProtocolMismatchError, ServiceError, json_body
from berth.domain import AiFailure

#: 一輪對話可以想很久；連線本身不該等。
STREAM_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
#: 列模型只是一次 GET。
LIST_TIMEOUT = 15.0


def failure_of_status(status: int) -> AiFailure:
    """body 說不出原因時，只看狀態碼的分法（brief §20.24「錯誤」）。"""
    if status == 429:
        return AiFailure.RATE_LIMITED
    if status == 402:
        return AiFailure.QUOTA_EXHAUSTED
    if status in (401, 403):
        return AiFailure.AUTH_FAILED
    if status == 404:
        return AiFailure.MODEL_NOT_FOUND
    if status >= 500:
        return AiFailure.PROVIDER_DOWN
    return AiFailure.REJECTED


def retry_after(response: httpx.Response) -> float | None:
    """限流時 provider 說的秒數；沒說或不是秒數（HTTP 日期）是 `None`。"""
    raw = response.headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def host_of(base_url: str) -> str:
    """`ai_calls.host`：`host[:port]`，不含帳密。"""
    return urlsplit(base_url).netloc.rpartition("@")[2]


async def list_model_ids(
    session: HttpSession,
    path: str,
    *,
    read_error: Callable[[httpx.Response], Awaitable[AiProviderError]],
    params: Mapping[str, str | int] | None = None,
) -> list[str] | None:
    """`GET {path}` 讀 `data[].id`（兩種格式同形）。端點沒有這一支、或回的不是這個形狀是 `None`
    （設定頁退回手填）；憑證不對、連不上這類有下一步的失敗照樣是 `AiProviderError`。"""
    try:
        response = await session.request(
            "GET", path, params=params, tolerate=tuple(range(400, 600))
        )
        if response.status_code != 200:
            error = await read_error(response)
            if error.failure in (AiFailure.MODEL_NOT_FOUND, AiFailure.REJECTED):
                # 端點沒有這一支（第三方常見）：退回手填，不是錯。
                return None
            raise error
        body = json_body(response)
    except AiProviderError:
        raise
    except ProtocolMismatchError:
        return None
    except ServiceError as exc:
        raise AiProviderError(AiFailure.UNREACHABLE, str(exc)) from exc
    data = body.get("data") if isinstance(body, Mapping) else None
    if not isinstance(data, list):
        return None
    return [str(item["id"]) for item in data if isinstance(item, Mapping) and "id" in item]
