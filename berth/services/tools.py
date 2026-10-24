"""AI 的工具：一條登記一個（M5 票 05，plan §11.6〈命令登錄表〉）。機制在 `services/registry.py`。

加一個工具：寫它的輸入與結果型別、一個把輸入交給命令的 `run`，在 `REGISTRY` 的最後加一條 `Tool`
（加在最後：順序是 prompt 固定前綴的一部分）。結果型別要重跑 `pnpm -C web gen:api`，前端依它畫卡。
結果裡不放帳密、API key、token（`tests/unit/test_tool_results.py` 掃全部登記）。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from berth.domain import JellyfinPresence, JobState, MediaKind, ServiceOrigin
from berth.models import Media
from berth.services import deletion, indexer, weekly
from berth.services.registry import NextStep, ProposalInput, Registry, Tool, ToolContext

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


# --- 加索引站（要人按，M5 票 10）---------------------------------------------------


class AddIndexerInput(ProposalInput):
    site: str = Field(
        min_length=1,
        max_length=200,
        description="The site's Prowlarr definition name or display name, e.g. nyaasi or Nyaa.si.",
    )


class IndexerAddition(BaseModel):
    """確認卡上「會發生什麼」：哪一站、它在哪個網址、加到哪一台 Prowlarr。"""

    site: str
    name: str
    #: 這一站的網址（Prowlarr 定義的第一個）；定義沒寫是空字串。
    url: str
    description: str
    language: str
    #: 加到哪一台 Prowlarr（它的位址）、那一台是不是 Berth 套件內的。
    prowlarr: str
    origin: ServiceOrigin

    @classmethod
    def of(cls, plan: indexer.SiteAddition) -> IndexerAddition:
        return cls(
            site=plan.definition_name,
            name=plan.name,
            url=plan.url,
            description=plan.description,
            language=plan.language,
            prowlarr=plan.prowlarr,
            origin=plan.origin,
        )


class IndexerAdded(BaseModel):
    site: str
    name: str


async def _plan_indexer(context: ToolContext, given: AddIndexerInput) -> IndexerAddition:
    async with context.sessions() as session:
        plan = await indexer.plan_site_addition(session, context.clients, given.site)
    return IndexerAddition.of(plan)


async def _add_indexer(
    context: ToolContext, given: AddIndexerInput, shown: IndexerAddition
) -> IndexerAdded:
    async with context.sessions() as session:
        added = await indexer.add_site(session, context.clients, shown.site)
    return IndexerAdded(site=added.definition_name, name=added.name)


# --- 刪 complete（要人按，M5 票 10）-------------------------------------------------


class DeleteDownloadsInput(ProposalInput):
    media: str = Field(
        pattern=r"^(tv|movie):[0-9]+$",
        description="The work's id as Berth gives it, e.g. tv:209867 or movie:550.",
    )


class JobDownloadsPreview(BaseModel):
    hash: str
    name: str
    state: JobState
    #: 會被刪的檔案，絕對路徑。
    files: list[str]
    #: 紀錄上有、磁碟上已經不在的幾個。
    missing: int
    bytes: int
    #: 刪了真的空得出來的；媒體庫還握著同一份時是 0。
    reclaimable: int

    @classmethod
    def of(cls, job: deletion.JobDownloads) -> JobDownloadsPreview:
        return cls(
            hash=job.hash,
            name=job.name,
            state=job.state,
            files=list(job.files),
            missing=job.missing,
            bytes=job.bytes,
            reclaimable=job.reclaimable,
        )


class DownloadsDeletion(BaseModel):
    """確認卡上「會發生什麼」：這部作品每一筆 Job 會移除 torrent、刪掉下載目錄裡的這幾個檔案；
    媒體庫的鏈接與紀錄留著（brief §9.2）。"""

    media: str
    title: str
    title_en: str
    jobs: list[JobDownloadsPreview]


class JobDownloadsDeleted(BaseModel):
    hash: str
    name: str
    sources: int
    freed: int
    #: 這一筆沒做成的理由碼（`JobRefusal`）；做成了是空字串。
    refused: str

    @classmethod
    def of(cls, row: deletion.JobDownloadsOutcome) -> JobDownloadsDeleted:
        return cls(
            hash=row.hash, name=row.name, sources=row.sources, freed=row.freed, refused=row.refused
        )


class DownloadsDeleted(BaseModel):
    media: str
    jobs: list[JobDownloadsDeleted]


async def _plan_downloads(context: ToolContext, given: DeleteDownloadsInput) -> DownloadsDeletion:
    async with context.sessions() as session:
        jobs = await deletion.plan_downloads_deletion(session, given.media)
        media = await session.get(Media, given.media)
    snapshot = media.snapshot() if media is not None else None
    return DownloadsDeletion(
        media=given.media,
        title=snapshot.title if snapshot is not None else "",
        title_en=snapshot.title_en if snapshot is not None else "",
        jobs=[JobDownloadsPreview.of(job) for job in jobs],
    )


async def _delete_downloads(
    context: ToolContext, given: DeleteDownloadsInput, shown: DownloadsDeletion
) -> DownloadsDeleted:
    async with context.sessions() as session:
        done = await deletion.delete_downloads(
            session,
            context.clients,
            [job.hash for job in shown.jobs],
            actor=context.actor,
        )
    return DownloadsDeleted(
        media=given.media,
        jobs=[JobDownloadsDeleted.of(row) for row in done],
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
        Tool(
            name="add_indexer",
            description=(
                "Propose adding a public torrent site to Prowlarr so Berth can search it. Nothing "
                "is added until the user presses confirm on the card; tell them so."
            ),
            input=AddIndexerInput,
            result=IndexerAdded,
            command=indexer.add_site,
            route=("POST", "/setup/indexers/apply"),
            preview=_plan_indexer,
            preview_type=IndexerAddition,
            apply=_add_indexer,
            next_steps={
                indexer.SiteRefusal.SITE_UNKNOWN: NextStep.RETRY,
                indexer.SiteRefusal.PROWLARR_UNREACHABLE: NextStep.RETRY,
                indexer.SiteRefusal.SITE_PRESENT: NextStep.GIVE_UP,
                indexer.SiteRefusal.SITE_NOT_OFFERED: NextStep.GIVE_UP,
            },
        ),
        Tool(
            name="delete_downloads",
            description=(
                "Propose deleting a work's downloads: remove its torrents from qBittorrent and "
                "delete their files in the download folder. Library links stay, so Jellyfin "
                "still plays it. Nothing is deleted until the user presses confirm on the card; "
                "tell them so."
            ),
            input=DeleteDownloadsInput,
            result=DownloadsDeleted,
            command=deletion.delete_downloads,
            route=("DELETE", "/jobs/{job_hash}"),
            preview=_plan_downloads,
            preview_type=DownloadsDeletion,
            apply=_delete_downloads,
            next_steps={deletion.DeletionRefusal.NOTHING_TO_DELETE: NextStep.GIVE_UP},
        ),
    )
)
