"""M2 的修正與對帳（plan §11.3、brief §9、票 16）：三種人為破壞各造一次，對帳偵測到，按 Issue 上的
動作修好；以及刪掉媒體庫之後一鍵重新入庫。

疊在前兩個模組那一輪之上：三部作品已經由 Berth 入庫、Jellyfin 也反查到了。**每一條只碰一筆 Job
的檔案**，彼此不踩：

- 美劇第一集：在 **Jellyfin 裡**刪掉（`DELETE /Items/{id}` 真的刪磁碟上的檔案，brief §20.1）→
  `library_link_missing` → 重新鏈接；
- 美劇第二集：媒體庫那一份被一個**複製品**取代 → `inode_mismatch` → 以硬鏈接取代；
- 電影：complete 裡的來源被**手動刪掉** → `source_missing` → 標記為已無來源；complete 裡多了
  一個**沒人認領的目錄** → `orphan_complete` → 刪除；
- 動漫：整個 Anime 媒體庫裡的東西刪光 → `POST /jobs/{hash}/reimport` → 回到同樣的路徑、
  同一個 inode、同樣的帳本列。

每一條修完都再對帳一次，斷言那一件沒有再開——修好的意思是下一輪不再問。

排在 `test_2_` 之後：它最後一條把 Jellyfin 停掉再起來，並等它回來才結束。
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable

import httpx
import pytest

from tests.e2e.harness import (
    Json,
    Submitted,
    exists,
    imports_of,
    in_container,
    ledger_of,
    ok,
    same_file,
    stat_each,
    wait,
)

pytestmark = pytest.mark.e2e

#: complete 裡憑空多出來的目錄。名字不像任何一包發佈，Berth 不會把它認成誰的。
ORPHAN = "Berth e2e stray folder"


@pytest.fixture(scope="module")
def reconcile(berth: httpx.Client, resolved: dict[str, Json]) -> Callable[[], list[Json]]:
    """開一輪對帳並等它跑完，回傳跑完之後開著的 Issue。

    `resolved` 先跑完：還在等 Jellyfin 反查的那幾列不是這個模組要比的東西。
    """

    def run() -> list[Json]:
        started = berth.post("/reconcile")
        assert started.status_code == 202, started.text
        run_id = started.json()["id"]

        def finished() -> Json | None:
            state = ok(berth.get("/reconcile"))
            last = state["last"]
            return last if state["current"] is None and last and last["id"] == run_id else None

        report = wait("the reconcile run to finish", 300, finished, every=2)
        skipped = [side for side in report["sides"] if side["unavailable"] or side["skipped"]]
        assert not skipped, skipped
        issues: list[Json] = ok(berth.get("/issues"))
        return issues

    return run


def _one(issues: list[Json], kind: str, path: str) -> Json:
    found = [row for row in issues if row["type"] == kind and row["path"] == path]
    assert len(found) == 1, (kind, path, [(row["type"], row["path"]) for row in issues])
    return found[0]


def _none(issues: list[Json], kind: str, path: str) -> None:
    left = [row for row in issues if row["type"] == kind and row["path"] == path]
    assert not left, left


def _resolve(berth: httpx.Client, issue: Json, action: str) -> Json:
    assert action in issue["actions"], issue
    resolved: Json = ok(berth.post(f"/issues/{issue['id']}/resolve", json={"action": action}))
    assert resolved["status"] == "resolved", resolved
    return resolved


def _job(submitted: tuple[Submitted, ...], slug: str) -> Submitted:
    return next(job for job in submitted if job.pack.route_slug == slug)


def test_a_file_deleted_in_jellyfin_is_relinked(
    berth: httpx.Client,
    jellyfin: httpx.Client,
    submitted: tuple[Submitted, ...],
    reconcile: Callable[[], list[Json]],
) -> None:
    """「Jellyfin 內刪除」：以管理員在 Jellyfin 裡刪掉一集，磁碟上的檔案就沒了。"""
    entry = ledger_of(_job(submitted, "tv").info_hash)[0]
    target, source = entry["target_path"], entry["source_abs_path"]
    assert entry["jellyfin_item_id"], entry

    deleted = jellyfin.delete(f"/Items/{entry['jellyfin_item_id']}")
    assert deleted.status_code == 204, deleted.text
    assert not exists(target)

    issue = _one(reconcile(), "library_link_missing", target)
    _resolve(berth, issue, "relink")

    assert same_file(source, target)
    _none(reconcile(), "library_link_missing", target)


def test_a_copy_in_place_of_the_hard_link_is_replaced_by_one(
    berth: httpx.Client, submitted: tuple[Submitted, ...], reconcile: Callable[[], list[Json]]
) -> None:
    """「用複製取代硬鏈接」：內容一樣、inode 不同。大小一致，所以給「以硬鏈接取代」。"""
    entry = ledger_of(_job(submitted, "tv").info_hash)[1]
    target, source = entry["target_path"], entry["source_abs_path"]
    in_container("sh", "-c", 'cp "$1" "$1.copy" && mv -f "$1.copy" "$1"', "sh", target)
    assert not same_file(source, target)

    issue = _one(reconcile(), "inode_mismatch", target)
    assert issue["detail"]["same_size"] is True, issue
    _resolve(berth, issue, "replace_with_link")

    assert same_file(source, target)
    _none(reconcile(), "inode_mismatch", target)


def test_a_source_deleted_from_complete_by_hand_is_marked_sourceless(
    berth: httpx.Client, submitted: tuple[Submitted, ...], reconcile: Callable[[], list[Json]]
) -> None:
    """「complete 目錄手動刪檔」：媒體庫那一份還在（硬鏈接的另一端），保留它、帳本記下沒有來源。"""
    movie = _job(submitted, "movies")
    (entry,) = ledger_of(movie.info_hash)
    target, source = entry["target_path"], entry["source_abs_path"]
    in_container("rm", source)

    issue = _one(reconcile(), "source_missing", target)
    _resolve(berth, issue, "mark_sourceless")

    assert exists(target)
    (row,) = imports_of(berth, movie)
    assert row["status"] == "source_missing", row
    _none(reconcile(), "source_missing", target)


def test_a_folder_nobody_owns_in_complete_is_deleted(
    berth: httpx.Client,
    jobs: dict[str, Json],
    submitted: tuple[Submitted, ...],
    reconcile: Callable[[], list[Json]],
) -> None:
    """complete 裡多了一個不屬於任何 torrent、也不在帳本上的目錄。"""
    complete = posixpath.dirname(jobs[_job(submitted, "movies").info_hash]["content_path"])
    stray = f"{complete}/{ORPHAN}"
    in_container("sh", "-c", 'mkdir -p "$1" && echo stray > "$1/notes.txt"', "sh", stray)

    issue = _one(reconcile(), "orphan_complete", stray)
    _resolve(berth, issue, "delete_orphan")

    assert not exists(stray)
    _none(reconcile(), "orphan_complete", stray)


def test_deleting_the_library_is_undone_with_one_reimport(
    berth: httpx.Client, submitted: tuple[Submitted, ...], reconcile: Callable[[], list[Json]]
) -> None:
    """刪掉整個 Anime 媒體庫裡的東西（票 10 驗收的「刪掉整個 library 目錄」），按一次重新入庫：
    同樣的路徑、同一個 inode、同樣的帳本列。媒體庫那個目錄本身留著——它是 Jellyfin 的媒體庫資料夾
    與 Route 的寫入目標，拿掉它是另一種壞法（Route 檢查會紅），不是「刪了 library」。

    中間先對帳一次：`/issues` 上那一整排「鏈接遺失」要在重新入庫之後自己收掉（importer 接回鏈接時
    關掉它們，`services/importer.HEALED_BY_LINKING`）——不然使用者修好了，那一頁還掛著一排按什麼都
    沒有結果的按鈕。
    """
    anime = _job(submitted, "anime")
    before = ledger_of(anime.info_hash)
    # `<媒體庫>/<作品> [tmdbid-N]/Season 01/<檔案>`：媒體庫底下的每一樣都拿掉。
    library = posixpath.dirname(posixpath.dirname(posixpath.dirname(before[0]["target_path"])))
    assert all(row["target_path"].startswith(library + "/") for row in before), before
    in_container("find", library, "-mindepth", "1", "-delete")
    assert in_container("find", library, "-mindepth", "1") == ""
    detected = reconcile()
    for row in before:
        _one(detected, "library_link_missing", row["target_path"])

    events_before = len(ok(berth.get(f"/jobs/{anime.info_hash}/events")))
    job = ok(berth.post(f"/jobs/{anime.info_hash}/reimport"))
    assert job["state"] == "completed", job

    def reimported() -> list[str] | None:
        state = ok(berth.get(f"/jobs/{anime.info_hash}"))["state"]
        events = ok(berth.get(f"/jobs/{anime.info_hash}/events"))
        types = [row["type"] for row in events[events_before:]]
        assert state not in {"review", "import_failed"}, (state, types)
        return types if state == "imported" and "linked" in types else None

    types = wait("the reimported job to be linked again", 600, reimported)
    assert types[0] == "retried", types

    after = ledger_of(anime.info_hash)
    assert [(row["id"], row["target_path"]) for row in after] == [
        (row["id"], row["target_path"]) for row in before
    ]
    stats = stat_each(
        *(row["source_abs_path"] for row in after), *(row["target_path"] for row in after)
    )
    sources, targets = stats[: len(after)], stats[len(after) :]
    assert [(dev, ino) for dev, ino, _ in sources] == [(dev, ino) for dev, ino, _ in targets]
    for issues in (ok(berth.get("/issues")), reconcile()):
        for row in after:
            _none(issues, "library_link_missing", row["target_path"])
