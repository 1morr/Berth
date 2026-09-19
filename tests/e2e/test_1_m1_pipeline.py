"""M1 的整條路徑（plan §10、§11.2 T1.8、brief §17）：只操作 Berth 的 API，外加下載這件事的替身。

精靈、送單、放位元組、等入庫與反查都在 `conftest.py`（兩個模組共享同一輪）：

1. 精靈八步——套件內的三個服務由 Berth 自己設定，TMDB 憑證讀環境變數 `TMDB_API_KEY`
2. 三筆送單：一部美劇一季、一部動漫一季、一部電影（`payload.PACKS`）；`.torrent` 由 Berth 自己去抓
3. **下載的替身**：問 qBittorrent 這一筆要下載到哪裡，把 staging 的檔案複製過去，再叫它 recheck
4. 等 Berth 自己走完 completed → planning → importing → imported，再等 Jellyfin 反查

斷言都拿外面的事實對 Berth 說的話：季集對語料、inode 在容器裡 `stat`、item id 在 Jellyfin 裡查。
套件內的媒體庫一開始是空的，所以反查要等 resolver 請 Jellyfin 掃描之後那一輪（`services/resolver.py`
的 `SCAN_AFTER_MISSES`）。

**Prowlarr 在跑但沒被測到**：精靈偵測得到它，第 5 步按「之後再說」，送單直接帶 `.torrent` 的網址。
索引站搜尋有自己的契約測試（`tests/integration/test_indexer_search.py`）。
"""

from __future__ import annotations

import json
from collections import Counter

import httpx
import pytest

from tests.e2e.harness import Json, Submitted, imports_of, in_container, ok
from tests.e2e.payload import PACKS

pytestmark = pytest.mark.e2e

#: 送單那兩筆記的是按下去的人；之後每一筆都該是 Berth 自己（`actor == "system"`）——
#: 重試、重新規劃都會以使用者的名義留在時間線上。
SUBMISSION_EVENTS = {"created", "submitted"}

#: 容器裡逐一 `stat` 參數裡的路徑，印出 `[[dev, ino, nlink], …]`。
STAT_EACH = (
    "import json, os, sys; "
    "print(json.dumps([(s.st_dev, s.st_ino, s.st_nlink) for s in map(os.stat, sys.argv[1:])]))"
)

#: 時間線上一定依序出現的站（中間可以夾別的，例如 `preplan`、`progress`）。狀態欄位只看得到終點，
#: 這一串才說得出它真的走過完成 → 規劃 → 入庫 → 通知 Jellyfin（票 15 的 code-review）。
PATH = (
    "created",
    "submitted",
    "metadata_received",
    "completed",
    "plan_generated",
    "linked",
    "jellyfin_scan_requested",
)

#: 帳本逐檔的 Jellyfin item id。API 只給 `presence`（找到了沒），id 本身只在資料庫裡，
#: 所以直接在 berth 容器裡讀——拿它對 Jellyfin 在那條路徑上的 item，才證明得了「反查得到 item id」。
LEDGER_ITEM_IDS = (
    "import json, sqlite3; "
    "rows = sqlite3.connect('/config/berth.db').execute("
    "\"select target_path, jellyfin_item_id from ledger where action = 'import'\").fetchall(); "
    "print(json.dumps(dict(rows)))"
)


def test_every_release_is_imported_without_a_human(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> None:
    for job in submitted:
        events = ok(berth.get(f"/jobs/{job.info_hash}/events"))
        types = [row["type"] for row in events]
        assert jobs[job.info_hash]["state"] == "imported", (job.pack.route_slug, types)
        remaining = iter(types)
        assert all(station in remaining for station in PATH), (job.pack.route_slug, types)
        by_hand = [
            (row["type"], row["actor"])
            for row in events
            if row["type"] not in SUBMISSION_EVENTS and row["actor"] != "system"
        ]
        assert not by_hand, by_hand
        assert "review_required" not in types, types


def test_the_ledger_holds_every_episode_the_corpus_imports(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> None:
    """季集對語料（benchmark 驗過的那一份正解），不對集名：集名來自活的 TMDB，會被編輯。"""
    for job in submitted:
        imports = imports_of(berth, job)
        got = Counter((row["season"], row["episode_start"]) for row in imports)
        assert got == job.episodes, job.pack.route_slug
        assert all(f"[tmdbid-{job.tmdb_id}]/" in row["target_path"] for row in imports)


def test_imports_are_hard_links_of_the_downloaded_files(
    berth: httpx.Client, submitted: tuple[Submitted, ...], jobs: dict[str, Json]
) -> None:
    """在容器裡 `stat` 兩端：同一個 device 與 inode，而且至少兩個鏈接。"""
    for job in submitted:
        root = jobs[job.info_hash]["content_path"]
        sources = [f"{root}/{path}" for path in job.imports]
        targets = [row["target_path"] for row in imports_of(berth, job)]
        stats = json.loads(
            in_container(
                "python",
                "-c",
                STAT_EACH,
                *sources,
                *targets,
            )
        )
        source_stats, target_stats = stats[: len(sources)], stats[len(sources) :]
        assert all(links >= 2 for _, _, links in stats), stats
        assert sorted((dev, ino) for dev, ino, _ in source_stats) == sorted(
            (dev, ino) for dev, ino, _ in target_stats
        ), job.pack.route_slug


def test_jellyfin_holds_every_import_where_berth_says(
    berth: httpx.Client,
    submitted: tuple[Submitted, ...],
    resolved: dict[str, Json],
    jellyfin: httpx.Client,
    libraries: dict[str, str],
) -> None:
    """帳本逐檔記下的 item id 就是 Jellyfin 自己在那條路徑上的 item，季集也是它認的；
    媒體庫卡片深連結的 Series / Movie 也是 Jellyfin 以 TMDB id 認出來的那一個。"""
    items = ok(
        jellyfin.get(
            "/Items",
            params={
                "recursive": "true",
                "includeItemTypes": "Series,Episode,Movie",
                "fields": "Path,ProviderIds,MediaSources",
            },
        )
    )["Items"]
    by_path = {source["Path"]: item for item in items for source in item.get("MediaSources") or []}
    ledger: dict[str, str] = json.loads(
        in_container("python", "-c", LEDGER_ITEM_IDS, container="berth")
    )
    for job in submitted:
        for row in resolved[job.media]["files"]:
            if row["action"] != "import":
                continue
            item = by_path.get(row["target_path"])
            assert item is not None, row["target_path"]
            assert ledger[row["target_path"]] == item["Id"], row["target_path"]
            if item["Type"] == "Episode":
                assert (item["ParentIndexNumber"], item["IndexNumber"]) == (
                    row["season"],
                    row["episode_start"],
                ), row["target_path"]

    # 牆是一個 Jellyfin 媒體庫一頁（M1.5 票 03），所以卡片要從那條 Route 入庫的那一個媒體庫上找。
    cards = {
        card["media_id"]: card
        for pack in PACKS
        for card in ok(berth.get(f"/inventory/{libraries[pack.route_slug]}"))["titles"]
    }
    for job in submitted:
        kind = "Movie" if job.media.startswith("movie:") else "Series"
        owners = [
            item["Id"]
            for item in items
            if item["Type"] == kind and (item.get("ProviderIds") or {}).get("Tmdb") == job.tmdb_id
        ]
        assert cards[job.media]["jellyfin_item_id"] in owners, (job.media, owners)
        print(f"{job.media}: Jellyfin {kind} {cards[job.media]['jellyfin_item_id']}")
