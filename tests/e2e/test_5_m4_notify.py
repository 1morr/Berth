"""M4 的通知（plan §11.5 的驗收、票 133）：Discord 換成 `discord.py` 那一台假的，其餘照舊是真的
qBittorrent、Jellyfin 與 TMDB。

plan §11.5 的驗收，各在哪一條測試：

1. RSS 命中 → 下載 → 入庫 → Jellyfin 可見，收件人收到「正在下載」與「可以看了」，說得出作品、季集
   與 Route——`test_an_rss_hit_tells_the_crew_it_is_downloading_then_ready_to_watch`；
2. 一件進審核的事推出「等你處理」並連到那一件——
   `test_a_new_review_item_pings_the_admin_with_a_link_to_it`；
3. 週報說得出這週入庫、修了什麼、還有什麼等人——
   `test_the_weekly_report_tells_what_came_in_was_fixed_and_waits`；
4. 管道掛掉時不阻塞任何管線、健康頁說得出來，回來之後補送——
   `test_a_dead_discord_blocks_nothing_and_catches_up`。

**收件人是兩個人**：管理員 `ADMIN`（中文，四種都訂）與一般使用者 `BOSUN`（英文，只訂「正在
下載」與「可以看了」，Jellyfin 只開 Anime 一個媒體庫）。每一輪由管理員按「立即輪詢」，所以他自己
收不到「正在下載」（`presser`，M4 票 126），這一則看的是 `BOSUN`。

排在 `test_4_` 之後、依賴它留下的狀態：《与你相恋》喵萌奶茶屋&LoliHouse 那一組已確認（新集直接
入庫、不進 audit），Re:ZERO 那一組綁好、改正過（offset 38）但還沒確認（新集入庫後進 audit）。

**週報由測試在 Berth 的容器裡呼叫 `compose_weekly`**（協調者 2026-10-22 選定）：排程一週一次、
新裝不補、重啟不立刻跑，而這一套 e2e 的入庫都發生在當天，最近一個已結束的週裡什麼都沒有。測試
產生的是到此刻為止的七天（`ends_at` 是現在），`week_of` 落在七天前那一天、不是週一，撞不到排程
那幾週；之後的路——待送表、送出迴圈、Discord、`GET /weekly/{id}`——都是真的。
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import httpx
import pytest

from berth.pipeline.notifying import TICK as NOTIFY_TICK
from tests.e2e.discord import BROKEN, HEALTHY
from tests.e2e.harness import (
    BERTH,
    BERTH_CONTAINER,
    DISCORD_CONTAINER,
    Json,
    all_jobs,
    berth_client,
    discord_messages,
    discord_mode,
    docker,
    in_container,
    ledger_of,
    ok,
    poll_feed,
    release_index,
    set_round,
    wait,
)
from tests.e2e.sites import AGGREGATE_URL, KIMI, RELEASES, REZERO, REZERO_URL

pytestmark = pytest.mark.e2e

#: Discord 的 user ID 是 17–20 位數字（`notify._SNOWFLAKE`）。
ADMIN_DISCORD = "100000000000000001"
#: 不叫 `deckhand`：那個 Jellyfin 帳號是 `test_2_` 建的，最後被停用，同名再建 Jellyfin 回 400。
BOSUN = "bosun"
BOSUN_PASSWORD = "harbour-bosun"
BOSUN_DISCORD = "100000000000000002"
#: 假 Discord 只看 `Bot ` 前綴，不比對 token。
BOT_TOKEN = "berth-e2e-bot-token"
#: 收件人只開這一個媒體庫：「可以看了」與「正在下載」在送出時問 Jellyfin 看不看得到（M4 票 125）。
BOSUN_LIBRARY = "anime"

#: 《与你相恋》喵萌奶茶屋&LoliHouse 第 6、7 集（`sites.RELEASES` 的第 3、4 輪）。
SIXTH = next(r.title for r in RELEASES if r.round == 3 and r.site == "mikan")
SEVENTH = next(r.title for r in RELEASES if r.round == 4)

#: 在 Berth 的容器裡產生到此刻為止的那一週，印出那一份的 id（同一週已經有了是 `null`）。
_COMPOSE_WEEKLY = """
import asyncio, json
from berth.config import load_config
from berth.db import create_engine, create_session_factory
from berth.pipeline.reconciling import local_now
from berth.services.weekly import compose_weekly

async def main():
    engine = create_engine(load_config())
    try:
        async with create_session_factory(engine)() as session:
            report = await compose_weekly(session, ends_at=local_now())
        print(json.dumps(report.id if report else None))
    finally:
        await engine.dispose()

asyncio.run(main())
"""


@dataclass(frozen=True, slots=True)
class Kimi:
    title: str
    title_en: str
    #: Anime 那一條 Route 的名字（訊息的 Route 欄）。
    route: str


@dataclass(frozen=True, slots=True)
class ThirdRound:
    #: 第 6 集那一筆 Job。
    sixth: str
    #: 這一輪之前審核佇列上的每一列：`(kind, ref)`。
    review_before: frozenset[tuple[str, int]]


def _review_keys(berth: httpx.Client) -> frozenset[tuple[str, int]]:
    rows: list[Json] = ok(berth.get("/review"))["rows"]
    return frozenset((row["kind"], row["ref"]) for row in rows)


def _feed(berth: httpx.Client, url: str) -> int:
    (found,) = [row["id"] for row in ok(berth.get("/rss/feeds")) if row["url"] == url]
    return int(found)


def _info_hash(title: str) -> str:
    (found,) = [digest for digest, row in release_index().items() if row["title"] == title]
    return str(found)


def _to(recipient: str) -> list[Json]:
    """送給這個人的每一則 embed，先到的在前。"""
    return [row["body"]["embeds"][0] for row in discord_messages() if row["recipient"] == recipient]


def _arrives(what: str, recipient: str, matches: Callable[[Json], bool], seconds: float) -> Json:
    """等到送給這個人、而且對得上的那一則。"""

    def found() -> Json | None:
        hits = [embed for embed in _to(recipient) if matches(embed)]
        return hits[-1] if hits else None

    return wait(what, seconds, found, every=5)


def _link(embed: Json) -> str:
    """內文最後一行的 Markdown 連結（`adapters/notify/discord._description`）。"""
    found = re.findall(r"\]\((\S+?)\)", embed.get("description", ""))
    assert found, embed
    return str(found[-1])


def _fields(embed: Json) -> dict[str, str]:
    return {field["name"]: field["value"] for field in embed.get("fields", [])}


@pytest.fixture(scope="module")
def kimi(berth: httpx.Client) -> Kimi:
    media = ok(berth.get(f"/media/{KIMI}"))
    (route,) = [row["name"] for row in media["routes"] if row["slug"] == BOSUN_LIBRARY]
    return Kimi(title=media["title"], title_en=media["title_en"], route=route)


@pytest.fixture(scope="module")
def bosun(jellyfin: httpx.Client, libraries: dict[str, str]) -> Iterator[httpx.Client]:
    """一般使用者，Jellyfin 只開 Anime；登入 Berth 那一刻就有自己的那一列。"""
    created = ok(jellyfin.post("/Users/New", json={"Name": BOSUN, "Password": BOSUN_PASSWORD}))
    policy = ok(jellyfin.get(f"/Users/{created['Id']}"))["Policy"]
    only = {**policy, "EnableAllFolders": False, "EnabledFolders": [libraries[BOSUN_LIBRARY]]}
    updated = jellyfin.post(f"/Users/{created['Id']}/Policy", json=only)
    assert updated.status_code == 204, updated.text
    with berth_client() as client:
        signed = ok(
            client.post("/auth/login", json={"username": BOSUN, "password": BOSUN_PASSWORD})
        )
        assert signed == {"name": BOSUN, "role": "user"}, signed
        yield client


@pytest.fixture(scope="module")
def wired(berth: httpx.Client, bosun: httpx.Client) -> None:
    """管理員設 bot token 與 Berth 的網址；兩個人各填自己的 Discord ID、語言與要收的種類。

    Berth 的網址填宿主上看得到的那一個：測試要照通知裡的連結真的開一次。
    """
    bot = ok(berth.put("/settings/notifications/bot", json={"token": BOT_TOKEN}))
    assert (bot["bot_configured"], bot["bot_name"]) == (True, "Berth e2e"), bot
    ok(berth.put("/settings/notifications/berth-url", json={"berth_url": BERTH}))
    # 「等你處理」最後才訂：`test_4_` 最後一條剛開了一個 Issue，看守還沒看過它。先訂的話它算
    # 「新的一件」，第 3 輪的審核項會在 10 分鐘的合併窗裡併進同一則，連結就不是那一件
    # （第一次實跑撞到）。沒人訂的那幾輪，看守只記下現在等著的、不排。
    admin = {"discord_user_id": ADMIN_DISCORD, "language": "zh-Hant"}
    quiet = {**admin, "kinds": ["ready", "downloading", "weekly"]}
    assert ok(berth.put("/me/notifications", json=quiet))["kinds"] == quiet["kinds"]
    time.sleep(3 * NOTIFY_TICK.total_seconds())
    full = {**admin, "kinds": ["ready", "downloading", "waiting", "weekly"]}
    assert ok(berth.put("/me/notifications", json=full))["kinds"] == full["kinds"]
    crew = {
        "discord_user_id": BOSUN_DISCORD,
        "language": "en",
        "kinds": ["ready", "downloading"],
    }
    assert ok(bosun.put("/me/notifications", json=crew))["kinds"] == crew["kinds"]

    # 「測試」真的送一則：假 Discord 接得到，而且是送給按的那一個人。
    tested = ok(bosun.post("/me/notifications/test"))
    assert tested["delivered"] is True, tested
    assert _to(BOSUN_DISCORD)[-1]["title"] == "Berth test message"


@pytest.fixture(scope="module")
def third_round(
    berth: httpx.Client, wired: None, settle: Callable[[], dict[str, Json]]
) -> ThirdRound:
    """第 3 輪：《与你相恋》第 6 集（確認過的那一組，直接入庫）與 Re:ZERO 第 5 集（還沒確認，入庫後
    進 audit）。兩個 Feed 各由管理員按一次立即輪詢，送出去的全部停下來。"""
    before = _review_keys(berth)
    set_round(3)
    assert poll_feed(berth, _feed(berth, AGGREGATE_URL))["submitted"] == 1
    assert poll_feed(berth, _feed(berth, REZERO_URL))["submitted"] == 1
    jobs = settle()
    sixth = _info_hash(SIXTH)
    assert jobs[sixth]["state"] == "imported", jobs[sixth]
    return ThirdRound(sixth=sixth, review_before=before)


def test_an_rss_hit_tells_the_crew_it_is_downloading_then_ready_to_watch(
    third_round: ThirdRound, kimi: Kimi
) -> None:
    """`BOSUN` 沒按任何東西：先收到「正在下載」（輪結束那一刻排、立刻送），Jellyfin 認出那一集
    之後收到「可以看了」（合併 5 分鐘）。兩則都說得出作品、季集與 Route，連到作品頁。"""

    def about_the_sixth(kind: str) -> Callable[[Json], bool]:
        def matches(embed: Json) -> bool:
            return embed["title"] == f"{kind}: {kimi.title_en}" and "S01E06" in embed.get(
                "description", ""
            )

        return matches

    downloading = _arrives(
        "the downloading notice", BOSUN_DISCORD, about_the_sixth("Downloading"), 120
    )
    assert _fields(downloading) == {"Route": kimi.route}, downloading
    assert _link(downloading) == f"{BERTH}/media/{KIMI}"

    # Jellyfin 可見：帳本那一筆有 Jellyfin 的 item id，才有「可以看了」。
    def resolved() -> bool | None:
        rows = ledger_of(third_round.sixth)
        return True if rows and all(row["jellyfin_item_id"] for row in rows) else None

    wait("Jellyfin to resolve the sixth episode", 1500, resolved, every=15)
    ready = _arrives(
        "the ready-to-watch notice", BOSUN_DISCORD, about_the_sixth("Ready to watch"), 600
    )
    assert _fields(ready) == {"Route": kimi.route}, ready
    assert _link(ready) == f"{BERTH}/media/{KIMI}"
    # 送出時照每個人存下的語言組字：管理員收到的同一件事是中文。
    _arrives(
        "the admin's ready-to-watch notice in Chinese",
        ADMIN_DISCORD,
        lambda embed: (
            embed["title"] == f"可以看了：{kimi.title}" and "S01E06" in embed.get("description", "")
        ),
        120,
    )


def test_a_new_review_item_pings_the_admin_with_a_link_to_it(
    berth: httpx.Client, third_round: ThirdRound
) -> None:
    """Re:ZERO 第 5 集入庫進了 audit：看守在下一輪看見它，10 分鐘收齊之後推「等你處理」，這一波
    只有它一件，所以連到那一列；照連結開得到審核頁，而那一列就在佇列上。"""
    fresh = _review_keys(berth) - third_round.review_before
    assert len(fresh) == 1, fresh
    ((kind, ref),) = fresh
    anchor = f"/review#{kind}-{ref}"

    pinged = _arrives(
        "the waiting-for-you notice",
        ADMIN_DISCORD,
        lambda embed: (
            embed.get("description", "").startswith("新增 1 件：1 件待審核")
            and _link(embed).endswith(anchor)
        ),
        900,
    )
    assert re.fullmatch(r"有 \d+ 件等你處理", pinged["title"]), pinged
    assert _link(pinged) == f"{BERTH}{anchor}"

    page, _, fragment = _link(pinged).partition("#")
    with httpx.Client() as client:
        opened = client.get(page)
    assert opened.status_code == 200, opened.status_code
    assert opened.headers["content-type"].startswith("text/html"), opened.headers
    assert (kind, ref) in _review_keys(berth), fragment


def test_the_weekly_report_tells_what_came_in_was_fixed_and_waits(
    berth: httpx.Client, third_round: ThirdRound
) -> None:
    """觸發一次產生（見模組說明）：入庫說得出《与你相恋》第 1–6 集；修了什麼說得出 M3 核准的那一份
    Re:ZERO 與 M2 人修好的三種 Issue；還有什麼等人說得出審核佇列上的件數。摘要推給管理員、連到
    那一份。"""
    printed = in_container("python", "-c", _COMPOSE_WEEKLY, container=BERTH_CONTAINER)
    report_id = json.loads(printed.strip().splitlines()[-1])
    assert isinstance(report_id, int), printed

    report = ok(berth.get(f"/weekly/{report_id}"))
    works = {row["media"]: row for row in report["imported"]}
    assert [1, 1, 6] in works[KIMI]["episodes"], works[KIMI]
    assert REZERO in works, sorted(works)
    fixed = report["fixed"]
    assert fixed["approved"] >= 1, fixed
    assert {"library_link_missing", "inode_mismatch", "source_missing"} <= set(fixed["resolved"])
    waiting = report["waiting"]
    assert waiting["review"] == len(_review_keys(berth)), waiting

    (line,) = [row for row in ok(berth.get("/weekly")) if row["id"] == report_id]
    summary = _arrives(
        "the weekly summary",
        ADMIN_DISCORD,
        lambda embed: (
            embed["title"].startswith("週報：") and _link(embed).endswith(f"/weekly/{report_id}")
        ),
        120,
    )
    assert summary["description"].startswith(
        f"入庫 {line['works']} 部（{line['episodes']} 集）· 修了 {line['fixed']} 件"
        f" · 等你處理 {line['waiting']} 件"
    ), (summary, line)
    assert _link(summary) == f"{BERTH}/weekly/{report_id}"
    # 週報只送管理員（`ADMIN_ONLY_KINDS`）。
    assert not [e for e in _to(BOSUN_DISCORD) if "Weekly" in e["title"]]


def _channel(berth: httpx.Client) -> Json:
    return ok(berth.get("/health/detail"))["notify"]


def test_a_dead_discord_blocks_nothing_and_catches_up(
    berth: httpx.Client,
    bosun: httpx.Client,
    third_round: ThirdRound,
    settle: Callable[[], dict[str, Json]],
    kimi: Kimi,
) -> None:
    """先是 5xx：「測試」照實說連不上、什麼都沒送到。再整個關掉：第 4 輪照樣送單、下載、入庫，
    健康頁的通知資料（`/health/detail` 的 `notify`，通知卡讀的就是它）說連不上、有幾則等著；
    打開之後退避到期就補送那一則「正在下載」。"""
    discord_mode(BROKEN)
    try:
        before = len(discord_messages())
        tested = ok(bosun.post("/me/notifications/test"))
        assert (tested["delivered"], tested["failure"]) == (False, "unavailable"), tested
        assert len(discord_messages()) == before
    finally:
        discord_mode(HEALTHY)

    docker("stop", DISCORD_CONTAINER)
    try:
        set_round(4)
        assert poll_feed(berth, _feed(berth, AGGREGATE_URL))["submitted"] == 1
        seventh = _info_hash(SEVENTH)
        assert settle()[seventh]["state"] == "imported"

        def down() -> Json | None:
            channel = _channel(berth)
            return channel if channel["failures"] >= 1 and channel["pending"] >= 1 else None

        channel = wait("the health page to say Discord is unreachable", 300, down)
        assert channel["configured"] is True and channel["token_rejected"] is False, channel
        assert channel["error"], channel
        # 管線沒有在等它：下載列表上這一筆入庫了。
        states = {row["hash"]: row["state"] for row in all_jobs(berth)}
        assert states[seventh] == "imported"
    finally:
        docker("start", DISCORD_CONTAINER)

    # 退避從 30 秒起加倍、最多 1 小時（`notify.backoff`）；關掉的那幾分鐘撐不到很長。
    _arrives(
        "the downloading notice sent late",
        BOSUN_DISCORD,
        lambda embed: (
            embed["title"] == f"Downloading: {kimi.title_en}"
            and "S01E07" in embed.get("description", "")
        ),
        900,
    )

    def recovered() -> Json | None:
        channel = _channel(berth)
        return channel if channel["failures"] == 0 and channel["last_sent_at"] else None

    wait("the health page to say Discord is back", 120, recovered)
