"""命令登錄表（brief §14〈API-first〉、plan §11.6〈分段〉第 2 段，M5 票 06）。

AI 的工具、確認卡（M5）、MCP server（M7）都從這一份知道一個命令叫什麼、收什麼、回什麼、會被什麼
理由拒絕、要不要人。來源是命令自己的標記（`services/commands.py`）與簽名，這裡不另外抄一份。

**收哪些**：`berth.services` 底下每一個模組自己定義、有標記、**不帶 `INTERNAL`** 的公開函式。

**輸入模型由簽名推出**：伺服器給的參數不進輸入（`INJECTED_TYPES` 依型別認，`INJECTED_NAMES` 依名字
認），其餘每一格照型別與預設值成為 pydantic 欄位。推不出的（收 ORM 列、收函式、`*args`）是
`collect` 的失敗，`tests/unit/test_command_registry.py` 的閘門讓它紅：改成 `INTERNAL` 或改簽名。

**乾跑**：`dry_run` 跑命令註冊的 `validate`，回 `Verdict`，不改任何狀態。沒註冊的，預覽只顯示參數
（`Verdict.checked` 為假）。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import typing
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from types import ModuleType, NoneType, UnionType
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import Role
from berth.services.clients import BundledServices, HostResolver, ServiceClientFactory
from berth.services.commands import (
    CommandMark,
    Effect,
    Flag,
    Validator,
    command,
    details_of,
    mark_of,
    needs_person,
)
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.jellyfin_access import JellyfinAccess
from berth.services.sources import SourceCache

_PACKAGE = "berth.services"

#: 依型別認的注入：連線、事件、喚醒訊號、快取這些伺服器手上的東西（`X | None` 也算）。
INJECTED_TYPES: frozenset[object] = frozenset(
    {
        AsyncSession,
        ServiceClientFactory,
        EventHub,
        JobHints,
        SourceCache,
        JellyfinAccess,
        BundledServices,
        HostResolver,
    }
)

#: 依名字認的注入：按的人是誰（`actor`、`user_id`、`role`，由門禁給）、時鐘（`now`）、測試掛鉤
#: （`sleep`、`timeout`）與部署設定（`published_port`）。命令裡這幾個名字只當這個意思用。
INJECTED_NAMES = frozenset(
    {"actor", "user_id", "role", "now", "sleep", "timeout", "published_port"}
)


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """登錄表的一列。"""

    #: `"<模組>.<函式>"`，相對 `berth.services`（同 inverse 的寫法）。
    name: str
    function: Callable[..., Any]
    #: 呼叫端（模型、卡片、MCP）要給的那幾格。
    input: type[BaseModel]
    #: 由伺服器給的參數名（`INJECTED_TYPES`、`INJECTED_NAMES`），照簽名的順序。
    injected: tuple[str, ...]
    #: 回傳型別的註記：卡片照它決定長相（研究 C2〈卡片的原則〉）。
    result: object
    mark: CommandMark
    #: 給模型看的說明；空字串是還沒寫。
    about: str
    #: 拒絕理由的集合（`domain` 的 `*Refusal`）；空的是沒宣告。
    refusals: tuple[type[StrEnum], ...]
    validate: Validator | None
    #: 誰做得了（`commands.CommandDetails.audience`）：命令執行器照它擋。
    audience: Role

    @property
    def effect(self) -> Effect:
        return self.mark.effect

    @property
    def inverse(self) -> str | None:
        return self.mark.inverse

    @property
    def flags(self) -> frozenset[Flag]:
        return self.mark.flags

    @property
    def needs_person(self) -> bool:
        return needs_person(self.mark)


@dataclass(frozen=True, slots=True)
class Verdict:
    """乾跑的答案。`refusal` 是 `None` 而 `checked` 為真：可以做；`checked` 為假：沒有驗證函式，
    只看得到參數。"""

    checked: bool
    refusal: StrEnum | None = None
    #: 拒絕例外的 `detail`：原文或那一個 id，不翻譯。
    detail: str = ""


class _UnregistrableError(Exception):
    pass


def commands() -> Mapping[str, CommandSpec]:
    """全部可用的命令，依名字。推不出輸入模型的命令讓這裡丟 `RuntimeError`（閘門先紅）。"""
    return _commands()


@cache
def _commands() -> Mapping[str, CommandSpec]:
    found, failures = collect(_modules())
    if failures:
        raise RuntimeError("commands that cannot be registered: " + "; ".join(failures))
    return found


def collect(modules: Iterable[ModuleType]) -> tuple[dict[str, CommandSpec], list[str]]:
    """這幾個模組的命令，與註冊不了的每一個（一行一個，`"<名字>: <原因>"`）。"""
    found: dict[str, CommandSpec] = {}
    failures: list[str] = []
    for module in modules:
        short = module.__name__.removeprefix(_PACKAGE + ".")
        for attribute, function in vars(module).items():
            mark = mark_of(function)
            if (
                attribute.startswith("_")
                or mark is None
                or Flag.INTERNAL in mark.flags
                or getattr(function, "__module__", None) != module.__name__
            ):
                continue
            name = f"{short}.{attribute}"
            try:
                found[name] = _spec(name, function, mark)
            except _UnregistrableError as exc:
                failures.append(f"{name}: {exc}")
    return found, failures


# 讀登錄表、跑只讀的驗證函式：預覽的入口，不是一個命令。
@command(Effect.READ, flags={Flag.INTERNAL})
async def dry_run(
    spec: CommandSpec, session: AsyncSession, arguments: Mapping[str, object]
) -> Verdict:
    """照 `arguments` 跑 `spec` 的驗證函式，不改任何狀態。

    參數先過輸入模型：格式不對是 pydantic 的 `ValidationError`（呼叫端給錯了），不是拒絕。
    驗證函式丟出的例外 `reason` 在宣告的拒絕理由裡才轉成 `Verdict`，其餘原樣丟回去。
    """
    parsed = spec.input.model_validate(arguments)
    if spec.validate is None:
        return Verdict(checked=False)
    wanted = inspect.signature(spec.validate).parameters
    given = {name: getattr(parsed, name) for name in wanted if name in spec.input.model_fields}
    try:
        await spec.validate(session, **given)
    except Exception as exc:
        reason = getattr(exc, "reason", None)
        if not any(isinstance(reason, kind) for kind in spec.refusals):
            raise
        assert isinstance(reason, StrEnum)
        return Verdict(checked=True, refusal=reason, detail=str(getattr(exc, "detail", "")))
    return Verdict(checked=True)


def _modules() -> list[ModuleType]:
    package = importlib.import_module(_PACKAGE)
    return [
        importlib.import_module(f"{_PACKAGE}.{found.name}")
        for found in pkgutil.iter_modules(package.__path__)
    ]


def _spec(name: str, function: Callable[..., Any], mark: CommandMark) -> CommandSpec:
    target = inspect.unwrap(function)
    try:
        hints = typing.get_type_hints(target)
    except (NameError, TypeError) as exc:
        raise _UnregistrableError(f"annotations do not resolve ({exc})") from exc
    fields: dict[str, Any] = {}
    injected: list[str] = []
    for parameter in inspect.signature(target).parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            raise _UnregistrableError(f"takes *{parameter.name}")
        if parameter.name not in hints:
            raise _UnregistrableError(f"{parameter.name} has no annotation")
        hint = hints[parameter.name]
        if parameter.name in INJECTED_NAMES or bare_type(hint) in INJECTED_TYPES:
            injected.append(parameter.name)
            continue
        default = ... if parameter.default is parameter.empty else parameter.default
        fields[parameter.name] = (hint, default)
    details = details_of(function)
    try:
        model = create_model(
            _model_name(name),
            __config__=ConfigDict(extra="forbid", frozen=True),
            **fields,
        )
        model.model_json_schema()
    except Exception as exc:  # pydantic 的幾種 schema 錯誤沒有共同的基底
        raise _UnregistrableError(f"no input model ({type(exc).__name__}: {exc})") from exc
    if details.validate is not None:
        extra = set(inspect.signature(details.validate).parameters) - {"session", *fields}
        if extra:
            raise _UnregistrableError(f"validate takes what the input lacks: {sorted(extra)}")
    return CommandSpec(
        name=name,
        function=function,
        input=model,
        injected=tuple(injected),
        result=hints.get("return"),
        mark=mark,
        about=details.about,
        refusals=details.refusals,
        validate=details.validate,
        audience=details.audience,
    )


def bare_type(hint: object) -> object:
    """`X | None` → `X`；其餘原樣。"""
    if isinstance(hint, UnionType) or typing.get_origin(hint) is typing.Union:
        rest = [arg for arg in typing.get_args(hint) if arg is not NoneType]
        if len(rest) == 1:
            return rest[0]
    return hint


def _model_name(name: str) -> str:
    return "".join(part.title() for part in name.replace(".", "_").split("_")) + "Input"
