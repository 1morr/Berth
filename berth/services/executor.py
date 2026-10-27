"""命令執行器（plan §6〈命令執行器〉、§11.6〈分段〉第 2 段，M5 票 07）。

API、AI 的工具、確認卡（Proposal），以及 M7 的 Discord 與 MCP 叫命令都走這一條路。原本散在 API 層的
語意收在這裡（研究 R9）：

1. **查登錄表**（`registry.commands()`）：沒有、或是 `internal` 的，拒絕 `unknown_command`。
2. **角色**：命令的 `audience` 是 `Role.ADMIN` 而按的人（或 AI 替的那個人）不是，拒絕 `admin_only`。
   「自己的送單」由命令自己看注入的 `user_id` 與 `role`。
3. **驗輸入**：照登錄表推出的輸入模型；格式不對是 pydantic 的 `ValidationError`（呼叫端給錯了），
   不是拒絕。
4. **注入**伺服器手上的東西：session、client、hub、喚醒訊號、來源快取，以及按的人——`actor`
   （`events.actor` 的寫法，`domain/actor.py`）、`user_id`、`role`。
5. **事後**（只讀的命令沒有）：命令回來的每一筆 Job（結果本身，或結果的欄位）推一則 SSE 提示，
   停在規劃器或 importer 要接手的狀態就叫醒它——API 原本逐支寫的 `nudge()` 正是這一條
   （`reject` / `reimport` 退回 `completed` 叫規劃器，入庫重試與核准進 `importing` 叫 importer）。
6. **拒絕的形狀**：命令丟出它宣告的拒絕（`refusals`）時，換成同一個 `CommandRefusedError`
   （`reason` 仍是那個模組的 enum，`detail` 原文）；其餘例外原樣丟回去。

**不 commit**：工作單元是呼叫端的（API 的請求、AI 的一次工具呼叫），命令自己 commit 的照舊。
"""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import Actor, JobState, Role
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect
from berth.services.events import EventHub, JobSignal
from berth.services.hints import JobHints
from berth.services.jobs import JobView
from berth.services.plan import PLANNABLE
from berth.services.registry import CommandSpec, bare_type, commands
from berth.services.sources import SourceCache


class CommandRefusal(StrEnum):
    """執行器自己的拒絕；命令本身的拒絕用它模組的 enum。

    不放 `domain/enums.py`：那裡的 `*Refusal` 都是 API 回得出來的封閉集合
    （`test_openapi_contract`），而這兩種到不了 HTTP——經執行器的路由，門禁與 `audience` 一致
    （`test_executor_routes`）。
    """

    #: 登錄表上沒有這個命令（`internal` 的也不在上面）。
    UNKNOWN_COMMAND = "unknown_command"
    #: 只有管理員做得了（`audience`），而按的人（或 AI 替的那個人）不是。
    ADMIN_ONLY = "admin_only"


class CommandRefusedError(Exception):
    """經執行器的拒絕都是這一個形狀：哪個命令、哪一種理由（各模組的 enum）、原文。"""

    def __init__(self, command: str, reason: StrEnum, detail: str = "") -> None:
        super().__init__(f"{command}: {reason}: {detail}" if detail else f"{command}: {reason}")
        self.command = command
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Executor:
    """一個程序一份的東西；`execute` 每次呼叫帶自己的 session 與按的人。"""

    factory: ServiceClientFactory
    hub: EventHub
    sources: SourceCache
    #: 規劃器的喚醒訊號。
    plans: JobHints
    #: importer 的喚醒訊號。
    imports: JobHints

    # 回 `Any`：結果型別隨命令（`CommandSpec.result`），呼叫端照它知道的那一個命令標型別。
    async def execute(
        self, session: AsyncSession, name: str, arguments: Mapping[str, object], actor: Actor
    ) -> Any:
        spec = commands().get(name)
        if spec is None:
            raise CommandRefusedError(name, CommandRefusal.UNKNOWN_COMMAND)
        if spec.audience is Role.ADMIN and actor.role is not Role.ADMIN:
            raise CommandRefusedError(name, CommandRefusal.ADMIN_ONLY)
        parsed = spec.input.model_validate(arguments)
        given = {field: getattr(parsed, field) for field in spec.input.model_fields}
        try:
            result = await spec.function(**given, **self._injected(spec, session, actor))
        except Exception as exc:
            reason = getattr(exc, "reason", None)
            if not isinstance(reason, StrEnum) or not isinstance(reason, spec.refusals):
                raise
            raise CommandRefusedError(name, reason, str(getattr(exc, "detail", ""))) from exc
        if spec.effect is not Effect.READ:
            self._after(result)
        return result

    # `Any`：每一格的型別是那個命令的參數，這裡只照名字與型別配對。
    def _injected(self, spec: CommandSpec, session: AsyncSession, actor: Actor) -> dict[str, Any]:
        """登錄表標成注入的那幾格。給不出、而命令也沒有預設值的，是執行器還不支援的命令。"""
        by_name: dict[str, object] = {
            "actor": actor.label,
            "user_id": actor.user_id,
            "role": actor.role,
        }
        by_type: dict[object, object] = {
            AsyncSession: session,
            ServiceClientFactory: self.factory,
            EventHub: self.hub,
            SourceCache: self.sources,
        }
        hints = {"plans": self.plans, "imports": self.imports}
        target = inspect.unwrap(spec.function)
        parameters = inspect.signature(target).parameters
        annotations = typing.get_type_hints(target)
        supplied: dict[str, Any] = {}
        for name in spec.injected:
            kind = bare_type(annotations[name])
            if name in by_name:
                supplied[name] = by_name[name]
            elif kind is JobHints and name in hints:
                supplied[name] = hints[name]
            elif kind in by_type:
                supplied[name] = by_type[kind]
            elif parameters[name].default is inspect.Parameter.empty:
                raise RuntimeError(f"the executor cannot supply {name} to {spec.name}")
        return supplied

    def _after(self, result: object) -> None:
        for job in _jobs_in(result):
            self.hub.publish(JobSignal(hash=job.hash, state=job.state, progress=job.progress))
            if job.state in PLANNABLE:
                self.plans.nudge()
            if job.state is JobState.IMPORTING:
                self.imports.nudge()


def _jobs_in(result: object) -> tuple[JobView, ...]:
    """命令動到的 Job：結果本身是 `JobView`，或結果是帶 `JobView` 欄位的 dataclass。"""
    if isinstance(result, JobView):
        return (result,)
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        values = [getattr(result, field.name) for field in dataclasses.fields(result)]
        return tuple(value for value in values if isinstance(value, JobView))
    return ()
