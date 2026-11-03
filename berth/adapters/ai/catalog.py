"""向 AI 端點問它有哪些模型（M5.5 票 02；形狀與來源在 brief §20.26，回應錄在
`tests/fixtures/http/ai_models/`）。

- **Anthropic Messages**：`GET {base}/v1/models`，`x-api-key` 加 `anthropic-version`；有分頁，
  `has_more` 為真時帶 `after_id={last_id}` 再問。base URL 不含 `/v1`（`normalize_base_url`）。
- **OpenAI 相容**：`GET {base}/models`，`Authorization: Bearer`；一次給完。

**不跟轉址**：`x-api-key` 是自訂標頭，httpx 轉到別的主機時照樣帶著（它只拿掉 `Authorization`），
而 key 只送到填的那個端點（M5.5 票 01）。轉址當成「回的不是 API」。

問不到不丟例外：回 `ModelListing` 帶 `AiProbeFailure`，分類同「測試連線」（`adapters.ai.probe`），
只是 `NOT_FOUND` 在這裡是「這個端點不提供模型清單」（404、405、501）。

**DeepSeek 的 Anthropic 相容端點不提供模型清單**（2026-11-04 實測）：`x-api-key` 與 `Bearer`
帶對的 key 都是 404，所以標頭維持 `x-api-key`（同 SDK 與聊天）；這時建議退回本機價目表，
它認得 DeepSeek。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from berth.adapters.ai import effective_base_url
from berth.adapters.http import HttpSession, ProtocolMismatchError, ServiceError, json_body
from berth.domain import AiProbeFailure, AiProvider

#: Anthropic 的版本標頭（API 必填，SDK 送的也是這一個）。
ANTHROPIC_VERSION = "2023-06-01"

#: Anthropic 一頁最多 1,000 個（預設 20）：一般一頁就完。
_PAGE_SIZE = 1000
#: 服務不理 `after_id`、`has_more` 一直是真時不要無限問下去。
_MAX_PAGES = 10
#: 同「測試連線」：30 秒沒回就算連不上。
_TIMEOUT_SECONDS = 30.0
#: 這個端點沒有列模型的路由。DeepSeek 的 Anthropic 相容端點帶對的 key 是 404（brief §20.26）；
#: key 錯時它先回 401，所以 401 / 403 仍然只說 key 被拒。
_NO_MODEL_LIST = (404, 405, 501)
#: 不翻成例外、原樣拿回來分類的狀態碼：4xx、5xx，加上不跟的 3xx 轉址。
_CLASSIFIED_STATUSES = tuple(range(300, 600))


@dataclass(frozen=True, slots=True)
class ModelListing:
    """一次「取得模型」的結果。"""

    #: 服務列的模型 id，照它給的順序、去掉重複；失敗是空的。
    models: tuple[str, ...]
    #: 成功是 `None`。
    failure: AiProbeFailure | None
    #: 服務回的 HTTP 狀態碼；成功或沒有回應是 `None`。
    status: int | None
    #: 服務回的原文或連線錯誤的訊息；成功是空字串。
    detail: str


class ModelCatalog(Protocol):
    async def list_models(self) -> ModelListing: ...


class HttpModelCatalog:
    def __init__(self, provider: AiProvider, base_url: str, api_key: str) -> None:
        self._provider = provider
        self._base_url = effective_base_url(provider, base_url)
        self._api_key = api_key

    async def list_models(self) -> ModelListing:
        try:
            async with HttpSession(
                self._base_url,
                headers=self._headers(),
                timeout=_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as http:
                if self._provider is AiProvider.ANTHROPIC:
                    models = await _anthropic_pages(http)
                else:
                    models = _ids(await _answer(http, "/models", {}))
        except _RefusedError as refused:
            return refused.listing
        except ProtocolMismatchError as exc:
            return ModelListing((), AiProbeFailure.BAD_RESPONSE, None, str(exc))
        except ServiceError as exc:
            return ModelListing((), AiProbeFailure.UNREACHABLE, None, str(exc))
        return ModelListing(tuple(dict.fromkeys(models)), None, None, "")

    def _headers(self) -> dict[str, str]:
        if self._provider is AiProvider.ANTHROPIC:
            return {"x-api-key": self._api_key, "anthropic-version": ANTHROPIC_VERSION}
        return {"Authorization": f"Bearer {self._api_key}"}


class _RefusedError(Exception):
    def __init__(self, listing: ModelListing) -> None:
        super().__init__(listing.detail)
        self.listing = listing


async def _anthropic_pages(http: HttpSession) -> list[str]:
    models: list[str] = []
    params: dict[str, str | int] = {"limit": _PAGE_SIZE}
    for _ in range(_MAX_PAGES):
        page = await _answer(http, "/v1/models", params)
        models.extend(_ids(page))
        last_id = page.get("last_id")
        if page.get("has_more") is not True or not isinstance(last_id, str) or not last_id:
            break
        params = {"limit": _PAGE_SIZE, "after_id": last_id}
    return models


async def _answer(http: HttpSession, path: str, params: dict[str, str | int]) -> dict[str, Any]:
    response = await http.request("GET", path, params=params, tolerate=_CLASSIFIED_STATUSES)
    if response.status_code != 200:
        raise _RefusedError(_refusal(response))
    body = json_body(response)
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ProtocolMismatchError(f"GET {path}: no data list in the answer")
    return body


def _ids(page: dict[str, Any]) -> list[str]:
    return [
        item["id"]
        for item in page["data"]
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    ]


def _refusal(response: httpx.Response) -> ModelListing:
    status = response.status_code
    if status in (401, 403):
        failure = AiProbeFailure.KEY_REJECTED
    elif status in _NO_MODEL_LIST:
        failure = AiProbeFailure.NOT_FOUND
    elif status < 400:
        failure = AiProbeFailure.BAD_RESPONSE
    else:
        failure = AiProbeFailure.SERVICE_ERROR
    return ModelListing((), failure, status, response.text)
