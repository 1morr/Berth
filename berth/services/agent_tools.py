"""側面板給模型的工具清單（M5 票 11、17、19）：哪幾個登錄表的命令是工具、誰看得到哪幾個。

從 `services.agent` 拆出來：skills（`services.skills`）也要照它判斷一份流程用得上的工具在不在，
而 agent 要讀 skills 的清單——放在 agent 裡就是互相 import。
"""

from __future__ import annotations

from berth.domain import Role
from berth.services.registry import commands

#: 只有設了 Tavily key 才給模型的那一支。
TAVILY_TOOL = "web.tavily_search"

#: 給模型的工具（登錄表的名字）。每一支都要有 `about`（`tests/unit/test_agent_tools.py`）。
TOOLS: tuple[str, ...] = (
    "discover.search_media",
    "why_not.explain",
    "jobs.list_jobs",
    "jobs.read_job_events",
    "skills.load_skill",
    TAVILY_TOOL,
)

#: 結果是**外部內容**的工具（別人寫的網頁）：`services.agent.external_texts` 收它們的結果。
#: 伺服器端的 `web_search` 不經登錄表，另外認。
EXTERNAL_TOOLS: frozenset[str] = frozenset({TAVILY_TOOL})


def tool_name(command_name: str) -> str:
    """給模型的工具名：兩家都只收 `[A-Za-z0-9_-]`，所以 `why_not.explain` → `why_not_explain`。"""
    return command_name.replace(".", "_")


def visible_tools(role: Role, *, tavily: bool) -> tuple[str, ...]:
    """這個角色的人在側面板看得到的工具（登錄表的名字），照命令的 `audience`；Tavily 那一支
    只在設了 key 時（`tavily`）。"""
    registry = commands()
    return tuple(
        name
        for name in TOOLS
        if (role is Role.ADMIN or registry[name].audience is Role.USER)
        and (tavily or name != TAVILY_TOOL)
    )
