"""整個 API 共用的錯誤形狀（票 07）。"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, cast

from fastapi import status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

#: pydantic 每一條錯誤裡會夾帶的原值。`input` 在「缺欄位」時是**整份 body**，
#: `ctx` 在部分錯誤型別裡帶著原始例外——兩者都可能是使用者剛打的密碼。
_VALUE_KEYS = frozenset({"input", "ctx"})


async def validation_error(request: Request, exc: Exception) -> Response:
    """422 的回應只留「哪個欄位、為什麼」，不留收到的值。

    少打一個欄位送 `POST /auth/login`，預設的處理器會把整份 body（含密碼）原樣回進
    回應裡，也就進了任何側錄它的地方。掛在 app 上而不是逐個端點：下一個收密碼或 API key
    的端點不必記得這件事。
    """
    errors: list[dict[str, Any]] = [
        {key: value for key, value in error.items() if key not in _VALUE_KEYS}
        for error in cast(RequestValidationError, exc).errors()
    ]
    return JSONResponse({"detail": errors}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


def refusal_responses[R: StrEnum](
    model: type[BaseModel], statuses: Mapping[R, int]
) -> dict[int | str, dict[str, Any]]:
    """把「理由 → 狀態碼」那一張表翻成 OpenAPI 的 `responses`（M2 票 02）。

    兩件事一起解決：拒絕的形狀（`{reason, detail}`）進得了文件，所以前端從 OpenAPI 取得到
    那個封閉集合而不是自己抄一份；而每個狀態碼底下列的是**哪幾種理由會走到它**，那一行由
    同一張表導出，所以文件與實際回的狀態碼不會各說各話。

    `statuses` 收的是端點真的會回的那幾種——不是整個 enum。過度宣告的文件跟漏掉的一樣沒用。
    """
    reasons_by_code: dict[int, list[str]] = {}
    for reason, code in statuses.items():
        reasons_by_code.setdefault(code, []).append(f"`{reason.value}`")
    return {
        code: {"model": model, "description": " · ".join(reasons)}
        for code, reasons in sorted(reasons_by_code.items())
    }
