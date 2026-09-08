"""整個 API 共用的錯誤形狀（票 07）。"""

from __future__ import annotations

from typing import Any, cast

from fastapi import status
from fastapi.exceptions import RequestValidationError
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
