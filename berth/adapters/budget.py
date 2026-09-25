"""一個站一份請求預算（M3 票 20、plan §3.2、§8.4）。

`rss_poller`、每日補漏與索引站搜尋打的是同一批公開站（Prowlarr 預設的 Mikan、Nyaa、ACG.RIP
就是 RSS 那三站，brief §20.7），所以它們共用一份：一個站在一段**滾動**視窗裡最多幾個請求。
形狀照 Prowlarr 索引站的 Query Limit（`docs/research/request-budget.md`）：用完的那一個**被拒絕**，
不是排隊等——拒絕說得出何時放得下，呼叫的一方照它自己的規矩延後（輪詢下一輪再試、搜尋把時間給畫面）。

**記在程序的記憶體裡**，重啟歸零：Prowlarr 從它的歷史表數，而 Berth 沒有逐請求的歷史表；
為了數請求開一張表，就要在背景迴圈與 API 之間多搶一把 SQLite 的寫鎖（輪詢在寫交易裡抓單集頁，
M3 票 14b 的教訓）。重啟最多多送一個視窗的量。
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from berth.adapters.http import ServiceError
from berth.adapters.rss import FeedFetcher
from berth.domain import BudgetUse

#: 一個站一小時最多幾個請求。理由見 plan §3.2 的 `rss_poller` 那一段。
LIMIT = 60
WINDOW = timedelta(hours=1)

Clock = Callable[[], datetime]


class BudgetExhaustedError(ServiceError):
    """這個站的預算放不下這一次。是 `ServiceError`：抓不到 Feed、單集頁、單一 feed 的每一條
    既有退路（記在 `last_error`、下一輪再試）照樣接得住它。"""

    def __init__(self, site: str, until: datetime | None) -> None:
        when = until.isoformat() if until is not None else "never (more than the whole budget)"
        super().__init__(f"request budget for {site} is used up; it fits again at {when}")
        self.site = site
        #: 放得下的時刻。`None` 是永遠放不下（一次要的比整份預算還多）。
        self.until = until


@dataclass(frozen=True, slots=True)
class Deferral:
    """被預算擋下、還沒過得去的一種工作。"""

    use: BudgetUse
    #: 擋下了幾個請求。
    refused: int
    #: 第一次被擋的時刻。
    since: datetime
    #: 最近一次被擋時算出的「放得下」的時刻。
    until: datetime | None


@dataclass(frozen=True, slots=True)
class SiteUsage:
    site: str
    limit: int
    window: timedelta
    #: 視窗裡的請求數。
    used: int
    #: 照誰用掉的拆開（`BudgetUse` 的順序，零的不列）。
    by_use: tuple[tuple[BudgetUse, int], ...]
    #: 最早那一個請求滑出視窗的時刻；視窗是空的時是 `None`。
    frees_at: datetime | None
    deferred: tuple[Deferral, ...]


class RequestBudget:
    """一個程序一份（`ServiceClientFactory.budget`）。

    `take` 在同一個事件迴圈裡不 `await`，所以「數得下」與「記下來」之間不會被插隊。
    """

    def __init__(
        self,
        *,
        limit: int = LIMIT,
        window: timedelta = WINDOW,
        now: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self.limit = limit
        self.window = window
        self._now = now
        self._log: dict[str, deque[tuple[datetime, BudgetUse]]] = {}
        self._deferred: dict[tuple[str, BudgetUse], Deferral] = {}

    def take(self, sites: Iterable[str], count: int, use: BudgetUse) -> None:
        """在每一個站各佔 `count` 格；有一站放不下就一格都不佔，丟 `BudgetExhaustedError`。"""
        moment = self._now()
        targets = tuple(dict.fromkeys(sites))
        for site in targets:
            until = self._fits_at(site, count, moment)
            if until != moment:
                self._defer(site, use, count, moment, until)
                raise BudgetExhaustedError(site, until)
        for site in targets:
            self._log.setdefault(site, deque()).extend((moment, use) for _ in range(count))
            self._deferred.pop((site, use), None)

    def ready_at(self, sites: Iterable[str], count: int) -> datetime | None:
        """每一個站都放得下 `count` 個的最早時刻（現在放得下就是現在）；永遠放不下是 `None`。"""
        moment = self._now()
        latest = moment
        for site in sites:
            until = self._fits_at(site, count, moment)
            if until is None:
                return None
            latest = max(latest, until)
        return latest

    def usage(self) -> tuple[SiteUsage, ...]:
        """健康頁那一張卡：視窗裡問過、或有工作被擋著的站，照站名排。"""
        moment = self._now()
        rows: list[SiteUsage] = []
        for site in sorted(self._log.keys() | {site for site, _ in self._deferred}):
            log = self._window(site, moment)
            deferred = tuple(
                one
                for use in BudgetUse
                if (one := self._deferred.get((site, use))) is not None
                and self._still_waiting(one, moment)
            )
            if not log and not deferred:
                continue
            counts = Counter(use for _, use in log)
            rows.append(
                SiteUsage(
                    site=site,
                    limit=self.limit,
                    window=self.window,
                    used=len(log),
                    by_use=tuple((use, counts[use]) for use in BudgetUse if counts[use]),
                    frees_at=log[0][0] + self.window if log else None,
                    deferred=deferred,
                )
            )
        return tuple(rows)

    def _still_waiting(self, deferral: Deferral, moment: datetime) -> bool:
        """放得下的時刻一過就不算延後：搜尋與人按的讀取被擋之後沒有東西自己重試，一直列著的話
        健康頁會說它永遠在等。永遠放不下的那一種列一個窗長。"""
        until = deferral.until if deferral.until is not None else deferral.since + self.window
        return moment < until

    def _window(self, site: str, moment: datetime) -> deque[tuple[datetime, BudgetUse]]:
        """這個站還在視窗裡的請求（舊的先丟掉）。"""
        log = self._log.setdefault(site, deque())
        while log and log[0][0] <= moment - self.window:
            log.popleft()
        return log

    def _fits_at(self, site: str, count: int, moment: datetime) -> datetime | None:
        if count > self.limit:
            return None
        log = self._window(site, moment)
        overflow = len(log) + count - self.limit
        if overflow <= 0:
            return moment
        # 要等到前 `overflow` 個滑出視窗：第 overflow 個的時間加上視窗。
        return log[overflow - 1][0] + self.window

    def _defer(
        self, site: str, use: BudgetUse, count: int, moment: datetime, until: datetime | None
    ) -> None:
        before = self._deferred.get((site, use))
        self._deferred[(site, use)] = Deferral(
            use=use,
            refused=count + (before.refused if before is not None else 0),
            since=before.since if before is not None else moment,
            until=until,
        )


def site_of(url: str) -> str:
    """網址 → 預算的鍵：小寫主機名，`www.` 去掉（`nyaa.si` 與 `www.nyaa.si` 是同一站）。"""
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


class BudgetedFetcher:
    """每抓一條網址先在那一站的預算裡佔一格（`FeedFetcher` 的包裝）。"""

    def __init__(self, inner: FeedFetcher, budget: RequestBudget, use: BudgetUse) -> None:
        self._inner = inner
        self._budget = budget
        self._use = use

    async def fetch(self, url: str) -> bytes:
        self._budget.take((site_of(url),), 1, self._use)
        return await self._inner.fetch(url)

    async def aclose(self) -> None:
        await self._inner.aclose()
