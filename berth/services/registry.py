"""命令登錄表：AI 的工具從這裡來，而且只從這裡來（M5 票 05，plan §11.6〈命令登錄表〉）。

**工具逐條登記**（2026-10-24 拆票時使用者選定）：每一個命令都標了副作用（`services/commands.py`），
但只有在 `services/tools.py` 寫了一條 `Tool` 的才是工具。背景迴圈的入口、精靈的內部步驟標了也不會
變成工具；工具越少，被誘導的面越小。側面板、M6 的背景任務與 M7 的 MCP server 都只認這一份。

呼叫端只要知道兩件事：

- `Registry.tools_for(role)`：給這個角色的工具，**順序就是登記的順序**——工具定義在 prompt 的固定
  前綴裡，順序一變快取就吃不到。過濾照 API 的門禁（`services/access.py`）：每一條登記指著做同一件
  事的那一支端點，門禁不放那個角色進去，清單上就沒有它。
- `Registry.invoke(name, arguments, context)`：驗輸入、再檢查一次角色（模型叫了清單外的名字
  也一樣擋）、呼叫命令、回結果型別的一份；各模組的拒絕例外（`REJECTIONS`）在這裡變成同一種
  `Refusal`，帶「重試 / 交給人 / 放棄」。其餘的例外是 bug，照樣往外丟。

副作用等級與反向命令**直接讀命令的標記**，不另寫一份；登記一支沒標的命令，造 `Tool` 那一刻就紅。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.domain import Role
from berth.services.access import Access, access_of, admits
from berth.services.ai import AiRefusedError
from berth.services.auth import AuthenticatedUser
from berth.services.claims import ClaimRejectedError, UnclaimedError
from berth.services.commands import CommandMark, Effect, command, mark_of
from berth.services.issues import IssueRejectedError
from berth.services.jellyfin import BundledLibraryRejectedError, InterfaceLoginRejectedError
from berth.services.jobs import JobRejectedError, ai_actor
from berth.services.notify import NotifyRefusedError
from berth.services.plan_review import PlanRejectedError
from berth.services.rematch import RematchRejectedError
from berth.services.review import ReviewRejectedError
from berth.services.routes import RouteRejectedError
from berth.services.rss import RssRejectedError
from berth.services.setup import ChoiceLockedError, OwnerRejectedError

#: 各模組自己的拒絕：建構時收 `reason`（封閉集合），多半還有 `detail`（原文）。命令丟出它時**還沒動
#: 任何東西**，所以換成 `Refusal` 是安全的。`tests/unit/test_registry.py` 掃 `berth/services` 確認
#: 一種都沒漏。
REJECTIONS: tuple[type[Exception], ...] = (
    AiRefusedError,
    BundledLibraryRejectedError,
    ChoiceLockedError,
    ClaimRejectedError,
    InterfaceLoginRejectedError,
    IssueRejectedError,
    JobRejectedError,
    NotifyRefusedError,
    OwnerRejectedError,
    PlanRejectedError,
    RematchRejectedError,
    ReviewRejectedError,
    RouteRejectedError,
    RssRejectedError,
    UnclaimedError,
)

#: Anthropic 與 OpenAI 相容兩種格式都收的工具名（`^[a-zA-Z0-9_-]{1,64}$`），再收窄成小寫蛇形。
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


class NextStep(StrEnum):
    """拒絕之後 AI 該怎麼辦（plan §11.6）。"""

    #: 再試一次可能就成：輸入改一改，或那一邊暫時不通。
    RETRY = "retry"
    #: 要人來：說明原因、請使用者處理。沒在登記裡說的拒絕都是這一種。
    HAND_OVER = "hand_over"
    #: 不必再試：沒有這個工具、這件事已經不成立。
    GIVE_UP = "give_up"


class ToolRefusal(StrEnum):
    """登錄表自己的拒絕理由（各模組的理由照原樣傳出去）。不在 `domain/enums.py`：那裡的 `*Refusal`
    是端點的拒絕、每一種都有狀態碼（`TestStatusTables`），這兩種沒有端點。照樣進 OpenAPI
    （`main._document_components`），前端拿得到這個封閉集合。"""

    #: 沒有這個工具，或這個人的角色拿不到它——兩種說同一句，不說出「有，但你不行」。
    UNKNOWN_TOOL = "unknown_tool"
    #: 輸入不合 schema。`detail` 只說哪一格、為什麼，不回填收到的值。
    INVALID_INPUT = "invalid_input"


class Refusal(BaseModel):
    """工具沒做成，而且什麼都沒改。AI 依 `next` 分得出重試、交給人還是放棄。"""

    model_config = ConfigDict(frozen=True)

    tool: str
    #: 理由碼：`ToolRefusal`，或那個模組的拒絕 enum 的值（`source_missing`、`feed_unreachable`…）。
    reason: str
    #: 原文或 id，說不出就是空字串。
    detail: str
    next: NextStep


@dataclass(frozen=True, slots=True)
class ToolContext:
    """一次工具呼叫在誰的名下、拿什麼做事。依賴由呼叫端給，工具自己不建。"""

    sessions: async_sessionmaker[AsyncSession]
    user: AuthenticatedUser
    #: 這一次呼叫的時刻（「最近七天」從這裡往回算）。
    now: datetime

    @property
    def actor(self) -> str:
        """寫進 `events.actor` 的那個人：`ai:<user id>`，AI 代這位使用者做的（plan §2.3）。"""
        return ai_actor(self.user.id)


@dataclass(frozen=True, slots=True)
class Tool[Input: BaseModel, Result: BaseModel]:
    """一條登記。"""

    name: str
    #: 給模型看的說明，英文。進 prompt 的固定前綴，改一個字快取就重寫一次。
    description: str
    input: type[Input]
    #: 結果型別：前端依它畫結果卡（`main._document_components` 匯進 OpenAPI），結果裡沒有帳密
    #: （`tests/unit/test_tool_results.py`）。
    result: type[Result]
    #: 底下的那一支 service 命令。等級與反向命令讀它的標記。
    command: Callable[..., Any]
    #: 做同一件事的那一支端點，`(方法, 路徑)`，路徑相對 `/api`、寫 FastAPI 的模板。誰拿得到這個工具
    #: 照它的門禁（`services/access.py`）。
    route: tuple[str, str]
    #: 怎麼呼叫命令：把驗過的輸入交給 `command`，把它的回傳攤成 `result`。
    run: Callable[[ToolContext, Input], Awaitable[Result]]
    #: 哪幾種模組的拒絕值得重試或該放棄；沒列的都是交給人。
    next_steps: Mapping[StrEnum, NextStep] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if mark_of(self.command) is None:
            raise UnmarkedCommandError(self.name, self.command)
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"tool name {self.name!r} is not lower snake case of 1–64 characters")
        method, path = self.route
        if method not in _METHODS or not path.startswith("/"):
            raise ValueError(f"{self.name}: route {self.route!r} is not (method, /api path)")

    @property
    def effect(self) -> Effect:
        return self._mark().effect

    @property
    def inverse(self) -> str | None:
        return self._mark().inverse

    @property
    def access(self) -> Access:
        return access_of(*self.route)

    def next_step(self, reason: StrEnum) -> NextStep:
        """登記說的下一步，沒說的是交給人。**連 enum 一起比**：`JobRefusal.MEDIA_MISSING` 與
        `RssRefusal.MEDIA_MISSING` 的值一樣，StrEnum 用值比的話一條會配到另一條。"""
        for known, step in self.next_steps.items():
            if type(known) is type(reason) and known == reason:
                return step
        return NextStep.HAND_OVER

    def _mark(self) -> CommandMark:
        mark = mark_of(self.command)
        assert mark is not None  # __post_init__ 擋掉了沒標的
        return mark


class UnmarkedCommandError(TypeError):
    """登記了一支沒標副作用的命令：不知道它可不可逆，就不知道 AI 能不能自己做。"""

    def __init__(self, name: str, function: Callable[..., Any]) -> None:
        qualified = f"{function.__module__}.{function.__qualname__}"
        super().__init__(f"tool {name}: {qualified} is unmarked; give it @command(Effect...)")


class Registry:
    """全部的登記。"""

    def __init__(self, tools: Iterable[Tool[Any, Any]]) -> None:
        self._tools: dict[str, Tool[Any, Any]] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"two tools are named {tool.name}")
            self._tools[tool.name] = tool

    def __iter__(self) -> Iterator[Tool[Any, Any]]:
        return iter(self._tools.values())

    def frontend_models(self) -> tuple[type[BaseModel], ...]:
        """經對話送到前端的型別：每一個結果型別與 `Refusal`（`main._document_components`）。"""
        return (*(tool.result for tool in self._tools.values()), Refusal)

    def tools_for(self, role: Role) -> tuple[Tool[Any, Any], ...]:
        """這個角色拿得到的工具，照登記的順序。"""
        return tuple(tool for tool in self._tools.values() if admits(tool.access, role))

    # 派發到任何一條登記，照最壞的那一條標（brief §14）：不可逆的工具（加索引站、刪 complete）
    # 也從這裡呼叫。要人確認的那一道在對話核心（票 10 的確認卡），不在這裡。
    @command(Effect.IRREVERSIBLE)
    async def invoke(
        self, name: str, arguments: Mapping[str, object], context: ToolContext
    ) -> BaseModel | Refusal:
        """呼叫一個工具。結果是那個工具的結果型別，或一份 `Refusal`。"""
        tool = self._tools.get(name)
        if tool is None or not admits(tool.access, context.user.role):
            return Refusal(
                tool=name, reason=ToolRefusal.UNKNOWN_TOOL, detail="", next=NextStep.GIVE_UP
            )
        try:
            given = tool.input.model_validate(arguments)
        except ValidationError as exc:
            return Refusal(
                tool=name,
                reason=ToolRefusal.INVALID_INPUT,
                detail=_where(exc),
                next=NextStep.RETRY,
            )
        try:
            result = await tool.run(context, given)
        except REJECTIONS as exc:
            reason: StrEnum = exc.reason  # type: ignore[attr-defined]  # REJECTIONS 每一類都有，測試掃過
            return Refusal(
                tool=name,
                reason=reason.value,
                detail=str(getattr(exc, "detail", "")),
                next=tool.next_step(reason),
            )
        if not isinstance(result, tool.result):
            raise TypeError(
                f"tool {name} returned {type(result).__name__}, not {tool.result.__name__}"
            )
        done: BaseModel = result
        return done


def _where(exc: ValidationError) -> str:
    """哪一格、為什麼，不含收到的值：模型送錯的那一格可能是它從別處抄來的密碼
    （同 `api/errors.py`）。"""
    return json.dumps(
        [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()],
        ensure_ascii=False,
    )
