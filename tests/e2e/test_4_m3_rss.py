"""M3 的 RSS（plan §11.4、brief §15、票 21）：公開站換成 `sites.py` 那一台，下載與入庫走真的
qBittorrent 與 Jellyfin，TMDB 是真的。

plan §11.4 的八條驗收，各在哪一條測試：

1. Mikan 聚合 feed 全自動追完——`test_a_mikan_feed_binds_itself_and_fills_in_the_old_episodes`；
   acg.rip 搜尋 feed（「全自動」是從 Media 頁訂閱的那一種：一般的搜尋 feed 沒有番組頁，長出來的
   一律留給人綁，brief §15——Re:ZERO 那一個就是這樣綁的）——
   `test_a_search_subscription_takes_its_first_round_but_not_the_batch` 與
   `test_new_episodes_arrive_by_themselves_and_versions_live_side_by_side`；
2. 中途訂閱的一部補齊舊集、之後的新集自動入庫——同上第一條與最後那一條；
3. 同一集兩個字幕組、同組 v1 與 v2 都並存——`…versions_live_side_by_side`；
4. 合集被排除——`…but_not_the_batch`；
5. split-cour 在審核裡改正一次、其餘集數跟著對——`test_one_correction_carries_the_rest_…`；
6. 發佈時間與換算出的那一集播出日對不上的不自動入庫——`test_a_split_cour_…_is_held`；
7. Jellyfin 認到的季集與帳本不同時開出 Issue——`test_jellyfin_reading_an_episode_differently_…`；
8. 已確認的 RSS Series 的新集數不出現在 audit 清單——`test_a_confirmed_series_…_audit_list`
   （M4 票 11 起《与你相恋》兩組的第一批證據夠強、由系統確認，`second_round` 斷言這件事）。

排在 `test_3_` 之後：那一組把 Anime 媒體庫刪光再重建，這一組只往裡面加。**Feed 不等背景輪詢**：
每一輪由測試按「立即輪詢」（`POST /rss/feeds/{id}/poll`，畫面上那一顆），輪次由測試寫進替身。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx
import pytest

from tests.e2e.harness import Json, ledger_of, ok, poll_feed, set_round, wait
from tests.e2e.sites import (
    AGGREGATE_URL,
    KAMIINA,
    KIMI,
    KITAUJI,
    LOLIHOUSE,
    REZERO,
    REZERO_URL,
)

pytestmark = pytest.mark.e2e

#: Re:ZERO 那一個 cour 的第一集在 TMDB 上是 S01E39（整部只有一季）。
REZERO_FIRST = 39


@dataclass(frozen=True, slots=True)
class FirstRound:
    route: int
    aggregate: int
    kamiina: int
    rezero: int
    #: 喵萌奶茶屋&LoliHouse 的《与你相恋》：自動綁定的那一個 RSS Series。
    kimi_series: int
    rezero_series: int


def _series(berth: httpx.Client, key: str) -> Json:
    rows: list[Json] = ok(berth.get("/rss/series"))
    found = [row for row in rows if row["key"] == key]
    assert len(found) == 1, (key, [row["key"] for row in rows])
    return found[0]


def _episodes(berth: httpx.Client, media: str) -> list[tuple[int, int, str]]:
    """帳本上這部作品的正片：`(季, 集, 目標路徑)`。"""
    files = ok(berth.get(f"/media/{media}"))["files"]
    return sorted(
        (row["season"], row["episode_start"], row["target_path"])
        for row in files
        if row["action"] == "import"
    )


@pytest.fixture(scope="module")
def first_round(
    berth: httpx.Client, resolved: dict[str, Json], settle: Callable[[], dict[str, Json]]
) -> FirstRound:
    """三個 Feed 各讀第一輪，送出去的全部停下來。

    相依 `resolved`：M1 那三包反查完了，這一組才開始往媒體庫裡加東西（前面的模組都在它之後跑）。
    """
    for media in (KIMI, KAMIINA, REZERO):
        # 詳情頁打開過，那一部才有 Media 那一列（綁定與訂閱要它）。
        ok(berth.get(f"/media/{media}"))
    route = next(
        row["id"] for row in ok(berth.get(f"/media/{KIMI}"))["routes"] if row["slug"] == "anime"
    )

    # 加 Feed 時兩格都要給（M4 票 105）：劇集送進 Anime（預設安裝有 TV 與 Anime 兩條收劇集的
    # Route），電影送進唯一的 Movies。
    movies = next(
        row["route"]["id"]
        for row in ok(berth.get("/routes"))
        if row["route"]["collection_type"] == "movies" and row["route"]["enabled"]
    )
    routes = {"tv_route": route, "movie_route": movies}
    aggregate = ok(berth.post("/rss/feeds", json={"url": AGGREGATE_URL, **routes}))["id"]
    polled = poll_feed(berth, aggregate)
    assert (polled["bound"], polled["submitted"]) == (1, 4), polled

    # 從 Media 頁訂閱 acg.rip 搜尋（M5 票 26）：先搜、列出字幕組，選绿茶字幕组；只綁那一組，
    # 建好就讀一輪、當場送出第一批（第 11 集），不再到 RSS 頁選第一輪。
    groups = ok(berth.get("/rss/search/subgroups", params={"kind": "acgrip", "q": "Kamiina Botan"}))
    assert {row["name"] for row in groups} == {"绿茶字幕组", "千夏字幕组"}, groups
    kamiina = ok(
        berth.post(
            "/rss/subscriptions/search",
            json={
                "media": KAMIINA,
                "route": route,
                "kind": "acgrip",
                "term": "Kamiina Botan",
                "subgroup": "绿茶字幕组",
            },
        )
    )
    assert kamiina["poll_error"] == "", kamiina
    assert kamiina["primed_at"] is not None, kamiina

    # 一般的 acg.rip 搜尋 feed：沒有番組頁，長出來的留在待綁定，由人綁。
    rezero = ok(berth.post("/rss/feeds", json={"url": REZERO_URL, **routes}))["id"]
    poll_feed(berth, rezero)
    ok(berth.post(f"/rss/feeds/{rezero}/prime", json={"mode": "all"}))
    pending = [
        row
        for row in ok(berth.get("/rss/series"))
        if row["media_id"] is None and "Re Zero" in row["title_raw"]
    ]
    assert len(pending) == 1, pending
    bound = ok(
        berth.put(
            f"/rss/series/{pending[0]['id']}/binding",
            json={"media": REZERO, "route": route},
        )
    )
    assert bound["submitted"] == 4, bound

    jobs = settle()
    assert len(jobs) == 9, sorted(row["name"] for row in jobs.values())
    return FirstRound(
        route=route,
        aggregate=aggregate,
        kamiina=kamiina["id"],
        rezero=rezero,
        kimi_series=_series(berth, f"mikan:4009:{LOLIHOUSE}")["id"],
        rezero_series=pending[0]["id"],
    )


def test_a_mikan_feed_binds_itself_and_fills_in_the_old_episodes(
    berth: httpx.Client, first_round: FirstRound
) -> None:
    """聚合 feed 只帶到第 3、4 集；自動綁定（送進 Feed 說的 Route）照預設補舊集，補上 1、2。"""
    series = _series(berth, f"mikan:4009:{LOLIHOUSE}")
    assert (series["media_id"], series["route_id"]) == (KIMI, first_round.route)
    assert series["bound_by"] == "system"
    assert [reason["code"] for reason in series["reasons"]][-1] == "feed_route"

    assert [(season, episode) for season, episode, _ in _episodes(berth, KIMI)] == [
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    ]


def test_a_search_subscription_takes_only_its_subgroup(
    berth: httpx.Client, first_round: FirstRound
) -> None:
    """M5 票 26：選了绿茶字幕组的那一條只收那一組；千夏字幕组的合集不寫成 Item、不長 Series。"""
    items = [row for row in ok(berth.get("/rss/items")) if row["feed_id"] == first_round.kamiina]
    assert items, items
    assert all(row["title"].startswith("[绿茶字幕组]") for row in items), items
    assert all(row["job_hash"] for row in items), items

    assert [(season, episode) for season, episode, _ in _episodes(berth, KAMIINA)] == [(1, 11)]


def _held(berth: httpx.Client, media: str) -> list[Json]:
    rows: list[Json] = ok(berth.get("/review"))["rows"]
    return [row for row in rows if row["kind"] == "plan" and row["media_id"] == media]


def test_a_split_cour_published_after_the_episode_it_maps_to_is_held(
    berth: httpx.Client, first_round: FirstRound
) -> None:
    """LoliHouse 把第二季後半從 01 重數，TMDB 只有一季：照字面是 S01E01–E04，而發佈當時這部作品
    在播的是 E39 之後——播出日比對把四份計劃都擋在審核，一集都沒入庫。"""
    held = _held(berth, REZERO)
    assert len(held) == 4, held
    assert {row["reason"]["code"] for row in held} == {"air_date_conflict"}, held
    assert _episodes(berth, REZERO) == []


def test_one_correction_carries_the_rest_of_the_series(
    berth: httpx.Client, first_round: FirstRound, settle: Callable[[], dict[str, Json]]
) -> None:
    """其中一份的那一列改成 S01E39 並「套用到這個 RSS Series」：Series 記下 offset 38，其餘三份
    重新規劃、通過比對、自動入庫；改的那一份等人核准。"""
    held = _held(berth, REZERO)
    plans = [ok(berth.get(f"/plans/{row['ref']}")) for row in held]
    first = next(plan for plan in plans if " - 01 " in plan["items"][0]["rel_path"])
    row = first["items"][0]

    edited = ok(
        berth.put(
            f"/plans/{first['id']}/items",
            json={
                "items": [
                    {
                        "id": row["id"],
                        "action": "import",
                        "season": 1,
                        "episode_start": REZERO_FIRST,
                    }
                ],
                "apply_to_series": True,
            },
        )
    )
    assert (edited["corrected"]["season"], edited["corrected"]["episode_offset"]) == (1, 38)

    ok(berth.post(f"/plans/{first['id']}/approve"))
    settle()
    wanted = [(1, episode) for episode in range(REZERO_FIRST, REZERO_FIRST + 4)]

    def imported() -> bool | None:
        found = [(season, episode) for season, episode, _ in _episodes(berth, REZERO)]
        return True if found == wanted else None

    wait("the corrected cour to be imported", 300, imported)
    assert _held(berth, REZERO) == []


@pytest.fixture(scope="module")
def second_round(
    berth: httpx.Client, first_round: FirstRound, settle: Callable[[], dict[str, Json]]
) -> dict[str, Json]:
    """《与你相恋》的第一批由系統確認過了，替身換到第二輪，兩個 Feed 各讀一次，送出去的全部停下來。

    第一批的四集都只寫集號、單季、發佈時剛播、播出日對得上（M4 票 11 的「證據夠強」）：最後一集
    落地時整批擔保，Series 確認、四集都不在 audit 清單上，每一筆的時間線記下 `series_confirmed`。
    """
    series = _series(berth, f"mikan:4009:{LOLIHOUSE}")
    assert (series["confirmed"], series["ask"]) == (True, None), series
    audit = [
        row
        for row in ok(berth.get("/review"))["rows"]
        if row["kind"] == "audit"
        and row["series"] is not None
        and row["series"]["id"] == first_round.kimi_series
    ]
    assert audit == [], audit
    for job in _sent_by(berth, LOLIHOUSE):
        events = ok(berth.get(f"/jobs/{job}/events"))
        said = [row["payload"] for row in events if row["type"] == "series_confirmed"]
        assert [payload["episodes"] for payload in said] == [
            ["S01E01", "S01E02", "S01E03", "S01E04"]
        ], (job, said)

    set_round(2)
    polled = poll_feed(berth, first_round.aggregate)
    # 同組的第 5 集與它的 v2，加上另一個字幕組長出來、自動綁上的那一個 Series 的第 5 集。
    assert (polled["bound"], polled["submitted"]) == (1, 3), polled
    assert poll_feed(berth, first_round.kamiina)["submitted"] == 1
    return settle()


def test_new_episodes_arrive_by_themselves_and_versions_live_side_by_side(
    berth: httpx.Client, second_round: dict[str, Json]
) -> None:
    # 第一輪的 Re:ZERO 改正之後也入庫了：到這裡替身送出去的每一筆都入庫，沒有一筆要人。
    assert {row["state"] for row in second_round.values()} == {"imported"}, second_round
    fifth = [row for row in _files(berth, KIMI) if (row["season"], row["episode_start"]) == (1, 5)]
    # 喵萌奶茶屋&LoliHouse 的 v1 與 v2、北宇治字幕组：三份各自一個檔案，都在同一集上。
    assert len({row["target_path"] for row in fifth}) == 3, fifth
    loli = sorted(
        (row["target_path"] for row in fifth if row["job_hash"] in _sent_by(berth, LOLIHOUSE)),
        key=lambda path: "v2" in path,
    )
    assert len(loli) == 2 and "v2" not in loli[0] and "v2" in loli[1], loli
    kitauji = _series(berth, f"mikan:4009:{KITAUJI}")
    assert (kitauji["media_id"], kitauji["bound_by"]) == (KIMI, "system")

    assert [(season, episode) for season, episode, _ in _episodes(berth, KAMIINA)] == [
        (1, 11),
        (1, 12),
    ]


def test_a_confirmed_series_new_episodes_stay_out_of_the_audit_list(
    berth: httpx.Client, first_round: FirstRound, second_round: dict[str, Json]
) -> None:
    """確認過的那一組第二輪的兩份不進 audit；還沒確認的 Series 照樣進。

    北宇治字幕组那一個是第二輪才長出來的，它唯一的一份證據夠強，系統當場確認（M4 票 11），也不進。
    還沒確認的那一邊是 Re:ZERO：改正並套用到 Series 之後季號與 offset 是人說的，跟著重算的三集仍是
    第一批，照樣在 audit 清單上等人。

    先斷言那兩份真的入庫了：停在審核的也不在 audit 清單上，那樣這一條會空泛地成立。
    """
    loli = _sent_by(berth, LOLIHOUSE)
    fifth = [
        row
        for row in _files(berth, KIMI)
        if (row["season"], row["episode_start"]) == (1, 5) and row["job_hash"] in loli
    ]
    assert len(fifth) == 2, fifth
    audit = [
        row
        for row in ok(berth.get("/review"))["rows"]
        if row["kind"] == "audit" and row["media_id"] in (KIMI, REZERO)
    ]
    groups = {row["series"]["id"] for row in audit}
    assert _series(berth, f"mikan:4009:{KITAUJI}")["confirmed"] is True
    assert groups == {first_round.rezero_series}, audit


def test_jellyfin_reading_an_episode_differently_opens_an_issue(
    berth: httpx.Client, jellyfin: httpx.Client, first_round: FirstRound
) -> None:
    """帳本說 S01E01，Jellyfin 那一集被改成第 7 集（有人在 Jellyfin 裡改了中繼資料並鎖住）：
    對帳的回驗開出 `jellyfin_item_mismatch`。"""
    job = next(
        row["job_hash"]
        for row in _files(berth, KIMI)
        if (row["season"], row["episode_start"]) == (1, 1)
    )

    def found() -> Json | None:
        rows = ledger_of(job)
        return rows[0] if rows and rows[0]["jellyfin_item_id"] else None

    entry = wait("Jellyfin to resolve the first episode", 1200, found, every=15)
    item_id = entry["jellyfin_item_id"]
    item = ok(jellyfin.get(f"/Items/{item_id}"))
    item.update(IndexNumber=7, LockData=True)
    updated = jellyfin.post(f"/Items/{item_id}", json=item)
    assert updated.status_code == 204, updated.text

    started = berth.post("/reconcile")
    assert started.status_code == 202, started.text
    run_id = started.json()["id"]

    def finished() -> Json | None:
        state = ok(berth.get("/reconcile"))
        last = state["last"]
        return last if state["current"] is None and last and last["id"] == run_id else None

    wait("the reconcile run to finish", 300, finished, every=2)
    issues = [
        row
        for row in ok(berth.get("/issues"))
        if row["type"] == "jellyfin_item_mismatch" and row["path"] == entry["target_path"]
    ]
    assert len(issues) == 1, ok(berth.get("/issues"))


def _sent_by(berth: httpx.Client, subgroup: int) -> set[str]:
    """《与你相恋》那一個字幕組的 RSS Series 送出的 Job。"""
    series = _series(berth, f"mikan:4009:{subgroup}")["id"]
    return {
        row["job_hash"]
        for row in ok(berth.get("/rss/items"))
        if row["series_id"] == series and row["job_hash"]
    }


def _files(berth: httpx.Client, media: str) -> list[Json]:
    rows: list[Json] = ok(berth.get(f"/media/{media}"))["files"]
    return [row for row in rows if row["action"] == "import"]
