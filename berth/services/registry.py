"""命令登錄表：AI 的工具從這裡來，而且只從這裡來（M5 票 05，plan §11.6〈命令登錄表〉）。

**工具逐條登記**（2026-10-24 拆票時使用者選定）：每一個命令都標了副作用（`services/commands.py`），
但只有在 `services/tools.py` 寫了一條 `Tool` 的才是工具。背景迴圈的入口、精靈的內部步驟標了也不會
變成工具；工具越少，被誘導的面越小。側面板、M6 的背景任務與 M7 的 MCP server 都只認這一份。

呼叫端只要知道兩件事：

- `Registry.tools_for(role)`：給這個角色的工具，**順序就是登記的順序**——工具定義在 prompt 的固定
  前綴裡，順序一變快取就吃不到。過濾照 API 的門禁（`services/access.py`）：每一條登記指著做同一件
  事的那一支端點，門禁不放那個角色進去，清單上就沒有它。
- `Registry.resolve(name, arguments, user)`：找工具、再檢查一次角色（模型叫了清單外的名字也一樣
  擋）、驗輸入，得到一次 `Call`。之後分兩條路（M5 票 10）：
  - **直接做**（`read`、`reversible`）：`Registry.run`。
  - **要人按**（`irreversible`，與被 `Tool.demote` 降級的那幾次）：`Registry.preview` 算出卡上
    「會發生什麼」，人按確認之後 `Registry.apply` 照他看到的那一份做。決定走哪一條、存卡片的是
    `services.proposals`，這裡只給機制。
  三支都把各模組的拒絕例外（`REJECTIONS`）變成同一種 `Refusal`，帶「重試 / 交給人 / 放棄」；
  其餘的例外是 bug，照樣往外丟。

副作用等級與反向命令**直接讀命令的標記**，不另寫一份；登記一支沒標的命令，造 `Tool` 那一刻就紅。
**不可逆的工具沒有 `run`**（造 `Tool` 時就擋）：AI 自己做不了它，在結構上就是這樣，不靠呼叫端記得。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.domain import ProposalCause, Role
from berth.services.access import Access, access_of, admits
from berth.services.ai import AiRefusedError
from berth.services.auth import AuthenticatedUser
from berth.services.claims import ClaimRejectedError, UnclaimedError
from berth.services.clients import ServiceClientFactory
from berth.services.commands import CommandMark, Effect, command, mark_of
from berth.services.conversations import AssistantRefusedError, ProposalRejectedError
from berth.services.deletion import DeletionRejectedError
from berth.services.indexer import SiteRejectedError
from berth.services.issues import IssueRejectedError
from berth.services.jellyfin import BundledLibraryRejectedError, InterfaceLoginRejectedError
from berth.services.jobs import JobRejectedError, actor_of, ai_actor
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
    AssistantRefusedError,
    BundledLibraryRejectedError,
    ChoiceLockedError,
    ClaimRejectedError,
    DeletionRejectedError,
    InterfaceLoginRejectedError,
    IssueRejectedError,
    JobRejectedError,
    NotifyRefusedError,
    OwnerRejectedError,
    PlanRejectedError,
    ProposalRejectedError,
    RematchRejectedError,
    ReviewRejectedError,
    RouteRejectedError,
    RssRejectedError,
    SiteRejectedError,
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
    #: 按確認卡的當下，這個人的角色已經拿不到這個工具（M5 票 10）。他看過那張卡，所以照實說。
    NOT_ALLOWED = "not_allowed"


class Refusal(BaseModel):
    """工具沒做成，而且什麼都沒改。AI 依 `next` 分得出重試、交給人還是放棄。"""

    model_config = ConfigDict(frozen=True)

    tool: str
    #: 理由碼：`ToolRefusal`，或那個模組的拒絕 enum 的值（`source_missing`、`feed_unreachable`…）。
    reason: str
    #: 原文或 id，說不出就是空字串。
    detail: str
    next: NextStep


class ProposalInput(BaseModel):
    """要人按的工具的輸入都帶著這一格：AI 為什麼要做，原文印在確認卡上（M5 票 10）。"""

    reason: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "One sentence, in the user's language, on why this should be done. It is shown on "
            "the confirmation card the user has to press."
        ),
    )


@dataclass(frozen=True, slots=True)
class ToolContext:
    """一次工具呼叫在誰的名下、拿什麼做事。依賴由呼叫端給，工具自己不建。"""

    sessions: async_sessionmaker[AsyncSession]
    clients: ServiceClientFactory
    user: AuthenticatedUser
    #: 這一次呼叫的時刻（「最近七天」從這裡往回算）。
    now: datetime
    #: 人按了確認卡，由他本人執行（M5 票 10）。否則是 AI 代他做的。
    confirmed: bool = False

    @property
    def actor(self) -> str:
        """寫進 `events.actor` 的那個人：AI 代這位使用者做的是 `ai:<user id>`（plan §2.3），
        他按了確認卡、由他本人執行的是他自己。"""
        return actor_of(self.user.id) if self.confirmed else ai_actor(self.user.id)


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
    #: **直接做**：把驗過的輸入交給 `command`，把它的回傳攤成 `result`。不可逆的工具沒有它。
    run: Callable[[ToolContext, Input], Awaitable[Result]] | None = None
    #: **要人按**的那一條（M5 票 10）：算出確認卡上「會發生什麼」（刪哪些檔、加哪個網址），
    #: 什麼都不改；做不成的（站已經在了、沒有東西可刪）在這裡就拒絕，不出卡片。
    preview: Callable[[ToolContext, Input], Awaitable[BaseModel]] | None = None
    #: `preview` 回的型別：前端依它畫卡上那一段（`main._document_components`）。
    preview_type: type[BaseModel] | None = None
    #: 人按了確認之後照**他看到的那一份**（存下的 preview）做。做之前 `preview` 會先重算一次，
    #: 不成立的就不走到這裡；這一支自己要擋的是那一份裡的東西已經不在了。
    apply: Callable[[ToolContext, Input, Any], Awaitable[Result]] | None = None
    #: **降級的入口**（M5 票 10）：可逆的工具在某些呼叫上要人按時，說出原因；`None` 是照常直接做。
    #: 之後的檢查（票 11 的網址來源）接在這裡，不各自造一套。降級的工具也要有 preview 與 apply。
    demote: Callable[[ToolContext, Input], ProposalCause | None] | None = None
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
        proposes = (self.preview, self.preview_type, self.apply)
        if any(part is not None for part in proposes) and None in proposes:
            raise ValueError(f"{self.name}: preview, preview_type and apply come together")
        if self.effect is Effect.IRREVERSIBLE:
            if self.run is not None:
                raise ValueError(f"{self.name}: an irreversible tool has no run; it is proposed")
            if self.preview is None:
                raise ValueError(f"{self.name}: an irreversible tool needs preview and apply")
            if not issubclass(self.input, ProposalInput):
                raise ValueError(f"{self.name}: an irreversible tool's input is a ProposalInput")
        elif self.run is None:
            raise ValueError(f"{self.name}: a {self.effect} tool needs run")
        if self.demote is not None and self.preview is None:
            raise ValueError(f"{self.name}: a tool that can be demoted needs preview and apply")

    @property
    def effect(self) -> Effect:
        return self._mark().effect

    @property
    def inverse(self) -> str | None:
        return self._mark().inverse

    @property
    def access(self) -> Access:
        return access_of(*self.route)

    def cause(self, context: ToolContext, given: Input) -> ProposalCause | None:
        """這一次呼叫為什麼要人按；`None` 是直接做。不可逆的永遠要人（brief §14）。"""
        if self.effect is Effect.IRREVERSIBLE:
            return ProposalCause.IRREVERSIBLE
        return self.demote(context, given) if self.demote is not None else None

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

    def get(self, name: str) -> Tool[Any, Any] | None:
        return self._tools.get(name)

    def frontend_models(self) -> tuple[type[BaseModel], ...]:
        """經對話送到前端的型別：每一個結果型別與 `Refusal`（`main._document_components`）。"""
        return (*(tool.result for tool in self._tools.values()), Refusal)

    def preview_models(self) -> tuple[type[BaseModel], ...]:
        """確認卡上「會發生什麼」的型別，一個要人按的工具一個（M5 票 10）。"""
        return tuple(
            tool.preview_type for tool in self._tools.values() if tool.preview_type is not None
        )

    def tools_for(self, role: Role) -> tuple[Tool[Any, Any], ...]:
        """這個角色拿得到的工具，照登記的順序。"""
        return tuple(tool for tool in self._tools.values() if admits(tool.access, role))

    def resolve(
        self, name: str, arguments: Mapping[str, object], user: AuthenticatedUser
    ) -> Call | Refusal:
        """找到工具、確認這個人拿得到、驗過輸入。清單外的名字與沒權限的說同一句。"""
        tool = self._tools.get(name)
        if tool is None or not admits(tool.access, user.role):
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
        return Call(tool=tool, given=given)

    # 派發到直接做的那幾條登記：只有讀取與可逆的有 `run`（不可逆的造 `Tool` 時就擋了）。
    @command(Effect.REVERSIBLE)
    async def run(self, call: Call, context: ToolContext) -> BaseModel | Refusal:
        """直接做。結果是那個工具的結果型別，或一份 `Refusal`。"""
        tool = call.tool
        assert tool.run is not None, f"{tool.name} is proposed, not run"
        return await _attempt(tool, tool.run(context, call.given), tool.result)

    @command(Effect.READ)
    async def preview(self, call: Call, context: ToolContext) -> BaseModel | Refusal:
        """確認卡上「會發生什麼」，什麼都不改。做不成的是一份 `Refusal`。"""
        tool = call.tool
        assert tool.preview is not None and tool.preview_type is not None
        return await _attempt(tool, tool.preview(context, call.given), tool.preview_type)

    # 派發到每一條要人按的登記，照最壞的那一條標（brief §14）：加索引站、刪 complete 從這裡做。
    # 只有 `services.proposals` 在人按了確認之後呼叫它。
    @command(Effect.IRREVERSIBLE)
    async def apply(
        self, call: Call, context: ToolContext, shown: BaseModel
    ) -> BaseModel | Refusal:
        """照人看到的那一份 preview 做。"""
        tool = call.tool
        assert tool.apply is not None
        return await _attempt(tool, tool.apply(context, call.given, shown), tool.result)


@dataclass(frozen=True, slots=True)
class Call:
    """驗過的一次呼叫：哪一個工具、什麼輸入。"""

    tool: Tool[Any, Any]
    given: BaseModel


async def _attempt(
    tool: Tool[Any, Any], pending: Awaitable[object], expected: type[BaseModel]
) -> BaseModel | Refusal:
    """等那一支做完；模組的拒絕換成 `Refusal`，回錯型別是 bug。"""
    try:
        result = await pending
    except REJECTIONS as exc:
        reason: StrEnum = exc.reason  # type: ignore[attr-defined]  # REJECTIONS 每一類都有，測試掃過
        return Refusal(
            tool=tool.name,
            reason=reason.value,
            detail=str(getattr(exc, "detail", "")),
            next=tool.next_step(reason),
        )
    if not isinstance(result, expected):
        raise TypeError(
            f"tool {tool.name} returned {type(result).__name__}, not {expected.__name__}"
        )
    return result


def _where(exc: ValidationError) -> str:
    """哪一格、為什麼，不含收到的值：模型送錯的那一格可能是它從別處抄來的密碼
    （同 `api/errors.py`）。"""
    return json.dumps(
        [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()],
        ensure_ascii=False,
    )
