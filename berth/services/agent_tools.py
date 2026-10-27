"""側面板給模型的工具清單（M5 票 11、17、19）：哪幾個登錄表的命令是工具、誰看得到哪幾個。

從 `services.agent` 拆出來：skills（`services.skills`）也要照它判斷一份流程用得上的工具在不在，
而 agent 要讀 skills 的清單——放在 agent 裡就是互相 import。
"""

from __future__ import annotations

from collections.abc import Callable

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
    # 票 13：送單那一條路要的讀取與第一個寫入。
    "search.search_torrents",
    "media.route_choices",
    "downloading.add_manual_download",
    TAVILY_TOOL,
    # 票 14：訂閱、加 Feed 與它們要的讀取。`routes.check_route(s)` 不給：探測會讓 qBittorrent 校驗到
    # 100%、觸發使用者設的「完成時執行外部程式」，AI 按一次那邊就跑一次，而沒有情境要它。
    "media.read_media",
    "routes.list_routes",
    "bangumi.search_bangumi",
    "bangumi.read_bangumi",
    "rss.subscribe_mikan",
    "rss.subscribe_search",
    "rss.add_feed",
)

#: 結果是**外部內容**的工具（別人寫的網頁）：`agent_origins.external_texts` 收它們的結果。
#: 伺服器端的 `web_search` 不經登錄表，另外認。
EXTERNAL_TOOLS: frozenset[str] = frozenset({TAVILY_TOOL})


def tool_name(command_name: str) -> str:
    """給模型的工具名：兩家都只收 `[A-Za-z0-9_-]`，所以 `why_not.explain` → `why_not_explain`。"""
    return command_name.replace(".", "_")


#: 工具名 → 登錄表的名字（歷史裡的工具呼叫與結果記的是工具名）。
COMMAND_OF: dict[str, str] = {tool_name(name): name for name in TOOLS}


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


def _compact_search(result: object) -> object:
    """`search.search_torrents` 給模型的那一份：一次搜尋最多 350 列、每列十幾格（約 220 KB），照原樣
    交的話截斷（`agent_guards.clip`）只留得下前十幾列。挑發佈用不到的格子拿掉（站上的頁面、
    畫面列表的鍵、怎麼算出季集、發佈時間、空的證據與 tags 的空格），留得下的列多兩三倍；列的順序
    不變，「符合」在最前面。"""
    if not isinstance(result, dict) or not isinstance(result.get("rows"), list):
        return result
    return {**result, "rows": [_compact_row(row) for row in result["rows"]]}


#: 給模型的一列留下的格子（`search.SearchResult`）。
_SEARCH_ROW_KEYS = (
    "source_id",
    "title",
    "indexer",
    "size",
    "seeders",
    "season",
    "episode_start",
    "episode_end",
    "whole_season",
    "verdict",
    "evidence",
    "tags",
)


def _compact_row(row: object) -> object:
    if not isinstance(row, dict):
        return row
    kept = {key: row[key] for key in _SEARCH_ROW_KEYS if key in row}
    if not kept.get("evidence"):
        kept.pop("evidence", None)
    if isinstance(kept.get("tags"), dict):
        kept["tags"] = {key: value for key, value in kept["tags"].items() if value}
    return kept


#: 結果交給模型之前換成的樣子（JSON 形狀進、JSON 形狀出）。沒列的原樣交。
MODEL_VIEWS: dict[str, Callable[[object], object]] = {
    "search.search_torrents": _compact_search,
}
