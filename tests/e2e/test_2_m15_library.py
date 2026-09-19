"""M1.5 的權限與瀏覽（plan §11.2b、brief §17 的 M1.5 那一列、票 11）：一個**只看得到一個媒體庫**
的一般使用者登入 Berth，對真的 Jellyfin 12.1 驗六件事。

疊在 `test_1_m1_pipeline.py` 那一輪之上（fixture 都在 `conftest.py`，session scope）：三部作品已經
由 Berth 入庫、Jellyfin 也反查到了，所以牆上同時有 Berth 經手的與不經 Berth 的。

1. 看不到沒權限的媒體庫，直接請求那個媒體庫的網址也被拒；
2. 不是 Berth 入庫的作品照樣瀏覽得到（這一支自己把一部放進 TV 的資料夾，不經 Berth）；
3. 某一集的播放連結指向 Jellyfin 的那一集（Berth 給的 item id 就是 Jellyfin 在那條路徑上的 item）；
4. 標為已看之後 Jellyfin 那一端**這個帳號自己的** `UserData` 真的變了，標回未看也是；
5. 帳號在 Jellyfin 被停用之後，Berth 的 session 結束；
6. Jellyfin 整台停掉時牆說得出「問不到 Jellyfin」（票 07 留給這一輪的）。

**最後兩條的順序是寫死的**：第 5 條把這個帳號停用（之後 `viewer` 的每一個請求都是 401），第 6 條把
Jellyfin 整台停掉再起回來。pytest 照檔名與檔案內的順序跑，所以這個模組叫 `test_2_`，
而這兩條寫在最下面。
權限那一端一律拿**使用者自己的 token** 問 Jellyfin：伺服器 API key 代讀只套一部分媒體庫權限
（brief §20.8），拿 API key 問就證明不了「他看得到」。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing

import httpx
import pytest

from tests.e2e.harness import (
    JELLYFIN_CONTAINER,
    Json,
    Submitted,
    berth_client,
    docker,
    in_container,
    jellyfin_client,
    ok,
    wait,
)

pytestmark = pytest.mark.e2e

VIEWER = "deckhand"
VIEWER_PASSWORD = "harbour-deckhand"
#: 這位一般使用者唯一看得到的媒體庫（Route 的 slug）。M1 的美劇入庫在這裡。
ALLOWED = "tv"
#: 他沒有權限的那一個。M1 的電影入庫在這裡，所以「看不到」不是因為媒體庫是空的。
FORBIDDEN = "movies"

#: 不經 Berth 放進 Jellyfin 的那一部。認不出 provider 時 Jellyfin 就拿資料夾名當名稱，而且把
#: 括號裡的年份**拆進 `ProductionYear`**——牆上顯示的是不帶年份的那一個。
OUTSIDER = "Harbour Test Footage"
OUTSIDER_YEAR = 2019
OUTSIDER_FOLDER = f"{OUTSIDER} ({OUTSIDER_YEAR})"
OUTSIDER_EPISODE = f"{OUTSIDER_FOLDER} - S01E01.mkv"


@pytest.fixture(scope="session")
def viewer_id(jellyfin: httpx.Client, libraries: dict[str, str]) -> str:
    """一個只看得到 `ALLOWED` 的一般使用者。`IsAdministrator` 是預設的 false，
    所以他在 Berth 是 `user` 角色（brief §11）。"""
    created = ok(jellyfin.post("/Users/New", json={"Name": VIEWER, "Password": VIEWER_PASSWORD}))
    user_id: str = created["Id"]
    policy = ok(jellyfin.get(f"/Users/{user_id}"))["Policy"]
    assert not policy["IsAdministrator"], policy
    ok(
        jellyfin.post(
            f"/Users/{user_id}/Policy",
            json={**policy, "EnableAllFolders": False, "EnabledFolders": [libraries[ALLOWED]]},
        )
    )
    return user_id


@pytest.fixture(scope="session")
def viewer(
    berth: httpx.Client, viewer_id: str, resolved: dict[str, Json]
) -> Iterator[httpx.Client]:
    """這位一般使用者的 Berth session。`berth` 是管理員那一份，兩份 cookie 各自獨立。"""
    with berth_client() as client:
        me = ok(client.post("/auth/login", json={"username": VIEWER, "password": VIEWER_PASSWORD}))
        assert me["role"] == "user", me
        yield client


@pytest.fixture(scope="session")
def viewer_jellyfin(viewer_id: str) -> Iterator[httpx.Client]:
    with closing(jellyfin_client(VIEWER, VIEWER_PASSWORD)) as client:
        yield client


@pytest.fixture(scope="session")
def outsider(jellyfin: httpx.Client, libraries: dict[str, str], resolved: dict[str, Json]) -> Json:
    """一部 Berth 從來沒碰過的作品：檔案直接放進 TV 媒體庫的目錄，再請 Jellyfin 掃描。

    `resolved` 先跑完，Berth 的三部才都已經在 Jellyfin 裡——這一部是**多出來的**那一部。
    """
    folders = ok(jellyfin.get("/Library/VirtualFolders"))
    location = next(row["Locations"][0] for row in folders if row["ItemId"] == libraries[ALLOWED])
    season = f"{location}/{OUTSIDER_FOLDER}/Season 01"
    in_container(
        "sh",
        "-c",
        'mkdir -p "$1" && cp /fixtures/e2e/seed.mkv "$1/$2"',
        "sh",
        season,
        OUTSIDER_EPISODE,
    )
    ok(jellyfin.post("/Library/Refresh"))

    def indexed() -> Json | None:
        found = ok(
            jellyfin.get(
                "/Items",
                params={
                    "recursive": "true",
                    "includeItemTypes": "Series",
                    "parentId": libraries[ALLOWED],
                    "searchTerm": OUTSIDER,
                },
            )
        )["Items"]
        return found[0] if found else None

    return wait(f"Jellyfin to index {OUTSIDER}", 600, indexed, every=10)


def _played(
    jellyfin: httpx.Client, user_id: str, series_id: str, season_id: str
) -> dict[int, bool]:
    """這個帳號自己看到的那一季：集號 → 看過了沒。

    **走清單端點**：`GET /Items/{集}?userId=` 的 `UserData` 用的是 provider 導出的 `Key`，
    整部劇遞迴標記那一次寫的不是它（票 11 實測，研究 §5）。Berth 讀的也是這一支。
    """
    items = ok(
        jellyfin.get(
            f"/Shows/{series_id}/Episodes", params={"userId": user_id, "seasonId": season_id}
        )
    )["Items"]
    return {row["IndexNumber"]: row["UserData"]["Played"] for row in items}


def _bear(submitted: tuple[Submitted, ...]) -> Submitted:
    return next(job for job in submitted if job.pack.route_slug == ALLOWED)


def test_the_wall_only_offers_the_libraries_jellyfin_lets_them_see(
    viewer: httpx.Client, libraries: dict[str, str]
) -> None:
    """切換列只有 TV；直接打 Movies 的網址也被拒——牆上沒有它不等於後端不給。"""
    listed = ok(viewer.get("/inventory"))
    assert [row["id"] for row in listed] == [libraries[ALLOWED]], listed

    refused = viewer.get(f"/inventory/{libraries[FORBIDDEN]}")
    assert refused.status_code == 404, refused.text
    assert refused.json()["detail"]["reason"] == "library_not_visible", refused.text


def test_titles_berth_never_imported_are_on_the_wall(
    viewer: httpx.Client, libraries: dict[str, str], outsider: Json
) -> None:
    """既有媒體庫裡不是 Berth 入庫的作品照樣瀏覽得到，而且說得出「Berth 沒經手」。"""
    wall = ok(viewer.get(f"/inventory/{libraries[ALLOWED]}"))
    cards = {row["title"]: row for row in wall["titles"]}
    assert OUTSIDER in cards, sorted(cards)

    card = cards[OUTSIDER]
    assert card["tracking"] is None, card
    assert card["jellyfin_item_id"] == outsider["Id"], card
    assert card["media_id"] == "", card
    assert card["year"] == OUTSIDER_YEAR, card
    # 同一面牆上也有 Berth 經手的那一部，兩種才算「疊在一起」。
    assert [row["title"] for row in wall["titles"] if row["tracking"]], wall["titles"]


def test_an_episode_link_points_at_that_jellyfin_episode(
    viewer: httpx.Client,
    viewer_jellyfin: httpx.Client,
    viewer_id: str,
    submitted: tuple[Submitted, ...],
    resolved: dict[str, Json],
) -> None:
    """觀看區每一集的 `item_id`（深連結 `…/web/#/details?id=` 帶的就是它）就是 Jellyfin
    在 Berth 入庫那條路徑上的 item，季集也是 Jellyfin 認的。"""
    bear = _bear(submitted)
    area = ok(viewer.get(f"/media/{bear.media}/watch"))
    assert area is not None and area["kind"] == "tv", area
    assert area["jellyfin"]["url"] or area["jellyfin"]["port"], area["jellyfin"]

    season = area["seasons"][0]
    episodes = ok(
        viewer.get(
            f"/jellyfin/shows/{area['item_id']}/episodes", params={"season_id": season["id"]}
        )
    )
    assert episodes, area

    #: 帳本那一端：Berth 入庫的每一集在 Jellyfin 是哪一條路徑。
    by_number = {
        (row["season"], row["episode_start"]): row["target_path"]
        for row in resolved[bear.media]["files"]
        if row["action"] == "import"
    }
    for shown in episodes:
        item = ok(viewer_jellyfin.get(f"/Items/{shown['item_id']}", params={"userId": viewer_id}))
        assert item["Type"] == "Episode", item
        assert item["SeriesId"] == area["item_id"], item
        number = (item["ParentIndexNumber"], item["IndexNumber"])
        assert number == (shown["season"], shown["episode_start"]), (shown, number)
        assert item["Path"] == by_number[number], (number, item["Path"])


def test_marking_watched_writes_through_to_that_users_jellyfin_record(
    viewer: httpx.Client,
    viewer_jellyfin: httpx.Client,
    viewer_id: str,
    submitted: tuple[Submitted, ...],
) -> None:
    """標為已看 / 未看之後，Jellyfin 那一端**這個帳號**的觀看紀錄真的跟著改：一集自己的一次，
    整部劇遞迴的一次（票 01 實測的遞迴，這裡對真的服務再驗一遍）。"""
    bear = _bear(submitted)
    area = ok(viewer.get(f"/media/{bear.media}/watch"))
    series, season = area["item_id"], area["seasons"][0]["id"]
    episodes = ok(viewer.get(f"/jellyfin/shows/{series}/episodes", params={"season_id": season}))
    first = episodes[0]["item_id"]

    def played_now() -> dict[int, bool]:
        return _played(viewer_jellyfin, viewer_id, series, season)

    assert set(played_now().values()) == {False}, played_now()

    # 一集自己：兩個方向。
    assert ok(viewer.post(f"/jellyfin/items/{first}/played"))["played"] is True
    assert played_now()[episodes[0]["episode_start"]] is True, played_now()
    assert ok(viewer.delete(f"/jellyfin/items/{first}/played"))["played"] is False
    assert played_now()[episodes[0]["episode_start"]] is False, played_now()

    # 整部劇：Jellyfin 自己遞迴到每一集。
    assert ok(viewer.post(f"/jellyfin/items/{series}/played"))["played"] is True
    assert set(played_now().values()) == {True}, played_now()
    assert ok(viewer.delete(f"/jellyfin/items/{series}/played"))["played"] is False
    assert set(played_now().values()) == {False}, played_now()


def test_disabling_the_account_ends_the_berth_session(
    viewer: httpx.Client, jellyfin: httpx.Client, viewer_id: str, libraries: dict[str, str]
) -> None:
    """**這一支跑完之後 `viewer` 就不能用了**（見模組 docstring）。允許清單記 60 秒
    （`ACCESS_TTL_SECONDS`），所以停用之後最多等那麼久才會被擋。"""
    policy = ok(jellyfin.get(f"/Users/{viewer_id}"))["Policy"]
    ok(jellyfin.post(f"/Users/{viewer_id}/Policy", json={**policy, "IsDisabled": True}))

    def ended() -> httpx.Response | None:
        response = viewer.get(f"/inventory/{libraries[ALLOWED]}")
        return response if response.status_code == 401 else None

    refused = wait("the Berth session to end", 180, ended, every=5)
    assert refused.json()["detail"]["reason"] == "account_disabled", refused.text
    # session 是真的沒了，不只是那一支端點擋下來。
    assert viewer.get("/auth/me").status_code == 401


def test_browsing_says_so_when_jellyfin_is_not_there(
    berth: httpx.Client, libraries: dict[str, str]
) -> None:
    """Jellyfin 停掉時牆說得出「問不到 Jellyfin」（票 07 留給這一輪的：那條路徑之前只有 vitest
    與後端單元測試，沒有對真的服務跑過）。

    用管理員那一份 session：上一支已經把 `viewer` 的帳號停用了。停掉的容器一定會再起來
    （`finally`），而這一支是模組最後一條，後面沒有東西被它影響。
    """
    docker("stop", JELLYFIN_CONTAINER)
    try:
        refused = berth.get(f"/inventory/{libraries[ALLOWED]}")
        assert refused.status_code == 503, refused.text
        assert refused.json()["detail"]["reason"] == "jellyfin_unreachable", refused.text
    finally:
        docker("start", JELLYFIN_CONTAINER)

    def back() -> bool | None:
        return True if berth.get(f"/inventory/{libraries[ALLOWED]}").is_success else None

    assert wait("Jellyfin to come back", 300, back, every=5)
