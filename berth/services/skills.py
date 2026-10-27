"""Skills：側面板的工作流程說明，漸進揭露（M5 票 19、plan §11.6〈分段〉第 7 段）。

情境的流程（系列整理、新番推薦、為什麼沒入庫、補缺集）寫進 system prompt 太長，而且每一輪都要付費。
所以 instructions 只列名稱與一句描述（`menu`），模型需要時叫 `load_skill` 拿全文。

**檔案**：`berth/skills/<name>/SKILL.md`，照 Agent Skills 規格（agentskills.io/specification）：
YAML frontmatter 的 `name`（小寫英數與連字號、≤ 64、等於資料夾名）與 `description`（不空、
≤ 1024），內文是 Markdown。Berth 多一格 `tools`：流程要用的登錄表命令。

**只能是指令**：規格允許的其他鍵（`allowed-tools`、`license`…）與資料夾裡的附檔（`scripts/`）一律
拒絕。skill 給的只有字，工具照舊是登錄表那幾支、經執行器、受同一道門禁。

**誰看得到**：`tools` 全都在這個人的側面板工具裡（`agent_tools.visible_tools`）才列、才給載。工具還
沒做好（票 13 / 14 / 16）或這個人的角色用不到的，就像不存在。Tavily 那一支看 key，skill 不能要它。
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from berth.domain import Role
from berth.services.agent_tools import tool_name, visible_tools
from berth.services.commands import Effect, command

#: repo 裡的 skills（隨套件出貨：wheel 收整個 `berth/`）。
SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"

FILE_NAME = "SKILL.md"

#: Agent Skills 規格：小寫英數與連字號，不以連字號開頭或結尾。
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME_LIMIT = 64
DESCRIPTION_LIMIT = 1024

#: 登錄表的命令名（`why_not.explain`）。
_COMMAND = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")

_FIELDS = ("name", "description", "tools")

_FRONTMATTER = re.compile(r"---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)(.*)", re.DOTALL)


class SkillFormatError(ValueError):
    """skill 檔的格式不對。說的是哪一份、哪一格。"""


class SkillRefusal(StrEnum):
    """不放 `domain/enums.py`：到不了 HTTP，只有側面板的工具叫得到（同 `web.WebRefusal`）。"""

    #: 沒有這個 skill，或它要的工具這個人用不到。
    SKILL_MISSING = "skill_missing"


class SkillRefusedError(Exception):
    def __init__(self, reason: SkillRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else str(reason))
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    #: 流程要用的命令（登錄表的名字）；全部在才給。
    tools: tuple[str, ...]
    #: frontmatter 之後的 Markdown，頭尾空白去掉。
    body: str


class SkillEntry(BaseModel):
    name: str
    description: str


class SkillText(BaseModel):
    name: str
    instructions: str


def parse_skill(folder: str, text: str) -> Skill:
    """一份 `SKILL.md` 的內容。`folder` 是它所在資料夾的名字，`name` 要等於它。"""
    found = _FRONTMATTER.fullmatch(text.removeprefix("\ufeff").replace("\r\n", "\n"))
    if found is None:
        raise SkillFormatError(f"{folder}: no frontmatter between two '---' lines at the top")
    header, body = found.groups()
    try:
        fields = yaml.safe_load(header)
    except yaml.YAMLError as exc:
        raise SkillFormatError(f"{folder}: the frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(fields, dict):
        raise SkillFormatError(f"{folder}: the frontmatter is not a YAML mapping")
    extra = sorted(str(key) for key in fields if key not in _FIELDS)
    if extra:
        raise SkillFormatError(
            f"{folder}: unknown frontmatter keys {extra}; a skill has only {list(_FIELDS)}"
        )
    name = fields.get("name")
    if not isinstance(name, str) or len(name) > NAME_LIMIT or not _NAME.fullmatch(name):
        raise SkillFormatError(
            f"{folder}: name must be lowercase letters, digits and inner hyphens, "
            f"at most {NAME_LIMIT} characters"
        )
    if name != folder:
        raise SkillFormatError(f"{folder}: name {name!r} differs from its folder")
    description = fields.get("description")
    if not isinstance(description, str) or not (description := description.strip()):
        raise SkillFormatError(f"{folder}: description is missing or blank")
    if len(description) > DESCRIPTION_LIMIT:
        raise SkillFormatError(f"{folder}: description is over {DESCRIPTION_LIMIT} characters")
    tools = fields.get("tools")
    if not isinstance(tools, list) or not tools:
        raise SkillFormatError(f"{folder}: tools must be a non-empty list of command names")
    if not all(isinstance(tool, str) and _COMMAND.fullmatch(tool) for tool in tools):
        raise SkillFormatError(f"{folder}: tools must be command names like why_not.explain")
    body = body.strip()
    if not body:
        raise SkillFormatError(f"{folder}: the body is empty")
    unmentioned = [tool_name(tool) for tool in tools if f"`{tool_name(tool)}`" not in body]
    if unmentioned:
        raise SkillFormatError(f"{folder}: the body never names {unmentioned}")
    return Skill(name=name, description=description, tools=tuple(tools), body=body)


def read_skills(root: Path) -> tuple[Skill, ...]:
    """`root` 底下的每一份 skill，照名字排。格式不對、放錯位置的都是 `SkillFormatError`。

    名字唯一靠 `name` 要等於資料夾名。點開頭的檔案（Finder 的 `.DS_Store`）不看。
    """
    skills: list[Skill] = []
    for entry in _visible(root):
        if not entry.is_dir():
            raise SkillFormatError(f"{entry.name}: a skill is a folder holding {FILE_NAME}")
        others = [path.name for path in _visible(entry) if path.name != FILE_NAME]
        if others:
            raise SkillFormatError(f"{entry.name}: only {FILE_NAME} may be in it, found {others}")
        path = entry / FILE_NAME
        if not path.is_file():
            raise SkillFormatError(f"{entry.name}: no {FILE_NAME}")
        skills.append(parse_skill(entry.name, path.read_text(encoding="utf-8")))
    return tuple(skills)


def _visible(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir() if not path.name.startswith("."))


@cache
def catalog() -> tuple[Skill, ...]:
    """repo 裡的 skills。格式壞了第一次叫就丟（`tests/unit/test_skills.py` 先紅）。"""
    return read_skills(SKILLS_ROOT)


def available(skills: Iterable[Skill], visible: Collection[str]) -> tuple[Skill, ...]:
    """`visible`（登錄表的名字）蓋得到它全部工具的那幾份。"""
    return tuple(skill for skill in skills if set(skill.tools) <= set(visible))


def skills_for(role: Role) -> tuple[Skill, ...]:
    """這個人在側面板用得上的。Tavily 那一支不算：skill 不能要它（`tests/unit/test_skills.py`）。"""
    return available(catalog(), visible_tools(role, tavily=False))


def menu(skills: Iterable[Skill]) -> str:
    """instructions 裡的清單：一份一行，名稱與描述。"""
    return "\n".join(f"- {skill.name}: {skill.description}" for skill in skills)


# 只讀 repo 裡的檔案。一般使用者也行：列的只有他用得上的（`/skills`，票 18 的斜線指令叫它）。
@command(
    Effect.READ,
    audience=Role.USER,
    about="List the workflow skills you can load with load_skill: name and description.",
)
async def list_skills(*, role: Role) -> list[SkillEntry]:
    return [
        SkillEntry(name=skill.name, description=skill.description) for skill in skills_for(role)
    ]


# 同上：只回字，不叫任何東西。
@command(
    Effect.READ,
    refusals=(SkillRefusal,),
    audience=Role.USER,
    about="Load the full steps of one workflow skill listed in your instructions, by its name. "
    "Load it before starting that kind of task and follow it.",
)
async def load_skill(name: str, *, role: Role) -> SkillText:
    """拒絕：`skill_missing`（沒有，或它要的工具這個人用不到）。"""
    for skill in skills_for(role):
        if skill.name == name:
            return SkillText(name=skill.name, instructions=skill.body)
    raise SkillRefusedError(SkillRefusal.SKILL_MISSING, name)
