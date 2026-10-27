"""API 叫命令的那一條路：經命令執行器（plan §6〈命令執行器〉、M5 票 07）。

會登錄成 AI 工具、或能被確認卡執行的命令，它們的路由不直接叫 service，而是掛一個 `Command` 相依：

    run: Annotated[Run, Depends(Command("jobs.retry_job"))]
    job = await run(job_hash=job_hash)

按的人、喚醒、推播、角色都由執行器做，與 AI 叫同一個命令時一樣。拒絕是 `CommandRefusedError`，
`reason` 仍是那個模組的 enum，路由照舊翻成它的 HTTP 形狀。

`Command` 是相依物件，所以路由叫的是哪個命令讀得到：`tests/unit/test_executor_routes.py` 拿它比門禁
與命令的 `audience`。

這個模組**不用** `from __future__ import annotations`：FastAPI 從 `__call__` 的簽名讀相依，而物件
沒有 `__globals__` 可以解開字串型別。
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, Request, status

from berth.api.deps import ExecutorDep, SessionDep
from berth.api.gate import current_user
from berth.domain import Actor

#: 叫一次命令：關鍵字是命令的輸入（伺服器給的那幾格不用帶）。結果是 `Any`：型別隨命令，路由在
#: 接的那一行標上它知道的那一個。
Run = Callable[..., Awaitable[Any]]


class Command:
    """一條路由叫的那一個命令（`"<模組>.<函式>"`，登錄表的名字）。"""

    def __init__(self, name: str) -> None:
        self.name = name

    async def __call__(self, request: Request, session: SessionDep, executor: ExecutorDep) -> Run:
        user = current_user(request)
        if user is None:
            # 門禁保證走得到這裡的都登入了；萬一沒有，不可以變成不受角色限制的 `system`。
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="sign in to use this API")
        actor = Actor.person(user.id, user.role)

        async def run(**arguments: object) -> Any:
            return await executor.execute(session, self.name, arguments, actor)

        return run
