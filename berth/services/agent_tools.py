"""側面板給模型的工具清單（M5 票 11、17、19）：哪幾個登錄表的命令是工具、誰看得到哪幾個。

從 `services.agent` 拆出來：skills（`services.skills`）也要照它判斷一份流程用得上的工具在不在，
而 agent 要讀 skills 的清單——放在 agent 裡就是互相 import。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from berth.domain import Role
from berth.services.registry import commands

#: 只有設了 Tavily key 才給模型的那一支。
TAVILY_TOOL = "web.tavily_search"

#: 推薦新番的資料來源（票 16；整部系列用的搜尋與系列走圖在票 23d 拿掉）：社群編的資料站，
#: 結果是外部內容。
ANIME_TOOLS: tuple[str, ...] = (
    "anilist.read_season",
    "bgm.read_calendar",
)

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
    # 票 26：重複訂閱要看得到、刪得掉（試用機上同一部作品兩份訂閱，助理只能說「留著」）。
    "rss.list_subscriptions",
    "rss.delete_feed",
    # 票 28：Jellyfin 裡已有、Berth 沒紀錄的作品（推薦、補缺集、整部系列前先看）。
    "inventory.find_in_library",
    # 票 16：推薦新番。
    *ANIME_TOOLS,
    "discover.read_trending",
)

#: 結果是**外部內容**的工具（別人寫的網頁、社群編的資料站）：`agent_origins.external_texts` 收它們的
#: 結果，它們的 id 也不算「出自工具結果」。伺服器端的 `web_search` 不經登錄表，另外認。
EXTERNAL_TOOLS: frozenset[str] = frozenset({TAVILY_TOOL, *ANIME_TOOLS})


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
    畫面列表的鍵、怎麼算出季集、空的證據與 tags 的空格）；列的順序不變，「符合」在最前面。
    **發佈時間留著**（票 26）：模型拿它算各字幕組多久出一集，在對話裡比較字幕組。

    **只給前 `MODEL_SEARCH_ROWS` 列與它們沒涵蓋到的集**（票 23d，`_rows_to_show`），其餘只說有幾列
    （`rows_not_shown`）：結果留在這一輪的上下文裡、之後每次呼叫都重送，Re:Zero 找種子時搜了 19 次，
    每次呼叫多約 7K input，撞到每輪 400K。
    各類的總數在 `counts`，要更準的用 `query` 再搜。"""
    if not isinstance(result, dict) or not isinstance(result.get("rows"), list):
        return result
    rows = result["rows"]
    shown = _rows_to_show(rows)
    given = {**result, "rows": [_compact_row(row) for row in shown]}
    if len(rows) > len(shown):
        given["rows_not_shown"] = len(rows) - len(shown)
    return given


#: 一次種子搜尋給模型看的列數；前面的列沒涵蓋到的集，後面「符合」的列照樣給（`_rows_to_show`）。
MODEL_SEARCH_ROWS = 10


def _rows_to_show(rows: list[object]) -> list[object]:
    """前 `MODEL_SEARCH_ROWS` 列，加上之後每一列「符合」而帶來新的集的（照原本的順序）。

    補缺集一季只搜一次（`missing-episodes`）：一季缺十幾集、每集各自一個發佈時，前 10 列常被幾集的
    好幾個版本佔滿（票 23d 的紅燈）。不靠模型再搜：每一集至少有一列進得來，多的才不給。"""
    shown: list[object] = []
    covered: set[tuple[int, int | None]] = set()
    for index, row in enumerate(rows):
        spans = _episodes(row)
        new = {span for span in spans if span not in covered and (span[0], None) not in covered}
        if index < MODEL_SEARCH_ROWS or new:
            shown.append(row)
            covered |= spans
    return shown


def _episodes(row: object) -> set[tuple[int, int | None]]:
    """一列「符合」的發佈蓋到的（季, 集）；整季包是（季, None）。
    不是「符合」或看不出季集的是空的。"""
    if not isinstance(row, dict) or row.get("verdict") != "fits":
        return set()
    season, start, end = row.get("season"), row.get("episode_start"), row.get("episode_end")
    if not isinstance(season, int):
        return set()
    if row.get("whole_season"):
        return {(season, None)}
    if not isinstance(start, int):
        return set()
    last = end if isinstance(end, int) and end >= start else start
    return {(season, episode) for episode in range(start, last + 1)}


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
    "published_at",
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


def _compact_media(result: object) -> object:
    """`media.read_media` 給模型的那一份（票 16）：一季一集一筆的集表在長的一季就超過截斷上限——
    Re:Zero 的 TMDB 第 1 季 85 集，`agent_guards.clip` 砍掉 `seasons` 之後模型看不到那一季的總集數，
    `series-mapping` 對範圍要的正是它。逐集換成「狀態 → 集數範圍」（`imported: "1-25, 27"`），
    檔案只留季集、tags 與狀態；海報網址與英文簡介模型用不到。"""
    if not isinstance(result, dict):
        return result
    kept = {k: v for k, v in result.items() if k not in _MEDIA_DROPPED}
    if isinstance(kept.get("seasons"), list):
        kept["seasons"] = [_compact_season(season) for season in kept["seasons"]]
    if isinstance(kept.get("files"), list):
        kept["files"] = [
            {key: row[key] for key in _FILE_KEYS if key in row} if isinstance(row, dict) else row
            for row in kept["files"]
        ]
    return kept


_MEDIA_DROPPED = frozenset({"poster_url", "poster_url_en", "overview_en"})
_FILE_KEYS = ("season", "episode_start", "episode_end", "tags", "status", "presence")


def _compact_season(season: object) -> object:
    if not isinstance(season, dict) or not isinstance(season.get("episodes"), list):
        return season
    by_status: dict[str, list[int]] = {}
    jobs: dict[str, str] = {}
    for episode in season["episodes"]:
        if not isinstance(episode, dict) or not isinstance(episode.get("episode_number"), int):
            continue
        status = str(episode.get("status"))
        by_status.setdefault(status, []).append(episode["episode_number"])
        if episode.get("job"):
            jobs[str(episode["episode_number"])] = str(episode["job"])
    compact = {k: v for k, v in season.items() if k != "episodes"}
    compact["episodes"] = {status: _ranges(numbers) for status, numbers in by_status.items()}
    if jobs:
        compact["jobs"] = jobs
    if blocks := _aired_blocks(season["episodes"]):
        compact["aired_blocks"] = blocks
    return compact


#: 相鄰兩集的播出日隔超過這麼多天就算另一段（cour 之間通常隔一季；一季裡停播一兩週不算）。
AIRING_GAP_DAYS = 28


def _aired_blocks(episodes: list[object]) -> list[dict[str, str]]:
    """播出日連得起來的幾段（票 23d）：沒有網路搜尋時 `series-mapping` 拿它切出各季、各 cour。
    逐集的日期換成「哪幾集、從哪天到哪天」，還沒定播出日的那幾集不進任何一段。"""
    dated = sorted(
        (episode["episode_number"], date.fromisoformat(episode["air_date"]))
        for episode in episodes
        if isinstance(episode, dict)
        and isinstance(episode.get("episode_number"), int)
        and isinstance(episode.get("air_date"), str)
    )
    blocks: list[list[tuple[int, date]]] = []
    for number, aired in dated:
        if blocks and (aired - blocks[-1][-1][1]).days <= AIRING_GAP_DAYS:
            blocks[-1].append((number, aired))
        else:
            blocks.append([(number, aired)])
    return [
        {
            "episodes": _ranges([number for number, _ in block]),
            "from": block[0][1].isoformat(),
            "to": block[-1][1].isoformat(),
        }
        for block in blocks
    ]


def _ranges(numbers: list[int]) -> str:
    """`[1, 2, 3, 5]` → `"1-3, 5"`。"""
    spans: list[str] = []
    ordered = sorted(set(numbers))
    start = previous = ordered[0]
    for number in [*ordered[1:], None]:
        if number is not None and number == previous + 1:
            previous = number
            continue
        spans.append(str(start) if start == previous else f"{start}-{previous}")
        if number is not None:
            start = previous = number
    return ", ".join(spans)


#: 結果交給模型之前換成的樣子（JSON 形狀進、JSON 形狀出）。沒列的原樣交。
MODEL_VIEWS: dict[str, Callable[[object], object]] = {
    "search.search_torrents": _compact_search,
    "media.read_media": _compact_media,
}
