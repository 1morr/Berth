"""AI 的工具：一條登記一個（M5 票 05，plan §11.6〈命令登錄表〉）。機制在 `services/registry.py`。

加一個工具：寫它的輸入與結果型別、一個把輸入交給命令的 `run`，在 `REGISTRY` 的最後加一條 `Tool`
（加在最後：順序是 prompt 固定前綴的一部分）。結果型別要重跑 `pnpm -C web gen:api`，前端依它畫卡。
結果裡不放帳密、API key、token（`tests/unit/test_tool_results.py` 掃全部登記）。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from berth.domain import JellyfinPresence, MediaKind
from berth.services import weekly
from berth.services.registry import Registry, Tool, ToolContext

# --- 最近入庫 ---------------------------------------------------------------


class RecentImportsInput(BaseModel):
    days: int = Field(default=7, ge=1, le=31, description="How many days back to look.")


class RecentWork(BaseModel):
    """一部作品在這段時間入庫了什麼：結果卡上的一列（M5 票 09）。前四格與集數同週報的
    `ImportedWorkOut`，前端同一套說法。"""

    #: 作品的 id（`tv:209867`），作品被刪了是 `null`。結果卡連到作品頁
    #: （`deeplink.BerthPage.MEDIA`）。
    media: str | None
    kind: MediaKind | None
    title: str
    title_en: str
    year: int | None
    #: TMDB 海報的兩輪，畫面照 UI 語言挑；沒有是空字串。
    poster_url: str = Field(description="Poster image URL for the card; may be empty.")
    poster_url_en: str = Field(description="Poster image URL for the card; may be empty.")
    #: `[季, 起, 迄]`，接得上的已經併成一段。電影是空的。
    episodes: list[tuple[int, int, int]] = Field(
        description="[season, first episode, last episode] ranges; empty for a movie."
    )
    #: 這段時間入庫的那幾集 Jellyfin 收錄了沒（`inventory.imports_presence`）。
    presence: JellyfinPresence = Field(
        description=(
            "Whether Jellyfin shows these files yet: found, searching (still waiting), "
            "lost (Jellyfin could not find at least one)."
        )
    )

    @classmethod
    def of(cls, recent: weekly.RecentWork) -> RecentWork:
        work = recent.work
        return cls(
            media=work.media,
            kind=work.kind,
            title=work.title,
            title_en=work.title_en,
            year=recent.year,
            poster_url=recent.poster_url,
            poster_url_en=recent.poster_url_en,
            episodes=list(work.episodes),
            presence=recent.presence,
        )


class RecentImports(BaseModel):
    """「最近入庫」的結果卡：`[since, until)` 之間入庫的作品，依英文標題排。"""

    since: datetime
    until: datetime
    works: list[RecentWork]


async def _recent_imports(context: ToolContext, given: RecentImportsInput) -> RecentImports:
    since = context.now - timedelta(days=given.days)
    async with context.sessions() as session:
        works = await weekly.recent_imports(session, since=since, until=context.now)
    return RecentImports(
        since=since,
        until=context.now,
        works=[RecentWork.of(work) for work in works],
    )


REGISTRY = Registry(
    (
        Tool(
            name="recent_imports",
            description=(
                "List the works and episodes imported into the library in the last N days "
                "(default 7), grouped by work."
            ),
            input=RecentImportsInput,
            result=RecentImports,
            command=weekly.recent_imports,
            # 這段資料平常在週報頁：只有管理員（`ADMIN_PREFIXES` 的 `/weekly`）。
            route=("GET", "/weekly"),
            run=_recent_imports,
        ),
    )
)
