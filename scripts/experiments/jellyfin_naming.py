"""Jellyfin 命名實測（brief §20.6、§20.1、§7；plan §5、§9.4）。

對一台乾淨的 Jellyfin 跑完整流程：走初始精靈 → 建兩個媒體庫 → 掃描 →
查詢 Jellyfin 實際解析出來的 Series / Season / Episode / Movie / MediaSource /
MediaStream → 裝 MergeVersions → 跑合併任務 → 再查一次。

媒體庫用 Jellyfin 的預設 fetcher（TMDB），也就是實際部署的樣子。純檔名解析靠
媒體樹裡 TMDB 對不上的那組作品（make_media.py 的 PROBE），它的標題不會被遠端覆寫。

Jellyfin 的 DB 會保留舊掃描結果，重建媒體庫也清不掉，插件裝過也還在，所以要從乾淨的
/config 跑才量得到「未裝插件」的基準（砍 /config 的指令見根目錄 README 的〈實驗腳本〉）。

用法：
    python scripts/experiments/jellyfin_naming.py --base-url http://localhost:18096 --label 10.10.7
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from lib import Report, poll, request

ADMIN = "berth"
PASSWORD = "berth-experiment-2026"
MERGE_REPO = (
    "https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json"
)
MERGE_GUID = "f21bbed8-3a97-4d8b-88b2-48aaa65427cb"
MERGE_PACKAGE = "Merge Versions"

ITEM_FIELDS = "Path,ProviderIds,MediaSources,MediaStreams,ExtraType,ParentId"


class Jellyfin:
    """實驗用的極簡 Jellyfin 客戶端；正式的 adapter 在 M0 票 05 之後才寫。"""

    def __init__(self, base_url: str, label: str) -> None:
        self.base = base_url.rstrip("/")
        self.label = label
        self.token: str | None = None
        self.user_id: str | None = None
        self.server_id: str | None = None

    def auth_header(self) -> str:
        parts = [
            'Client="Berth-Experiment"',
            'Device="script"',
            f'DeviceId="berth-exp-{self.label}"',
            'Version="0.1.0"',
        ]
        if self.token:
            parts.append(f'Token="{self.token}"')
        return "MediaBrowser " + ", ".join(parts)

    def call(self, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = self.auth_header()
        resp = request(f"{self.base}{path}", headers=headers, **kwargs)
        if not resp.ok:
            method = kwargs.get("method", "GET")
            raise RuntimeError(f"{method} {path} -> {resp.status} {resp.text[:300]}")
        return resp.json()

    def public_info(self) -> Any:
        return request(f"{self.base}/System/Info/Public", timeout=5).json()

    # --- 初始精靈（plan §9.4 的步驟 1–7）---------------------------------

    def run_startup(self, report: Report) -> None:
        info = poll(self.public_info, what=f"Jellyfin {self.label} 起來", timeout=300)
        report.record("public_info_before", info)
        if info.get("StartupWizardCompleted"):
            report.note("初始精靈已完成，直接登入")
        else:
            self.call(
                "/Startup/Configuration",
                method="POST",
                json_body={
                    "UICulture": "zh-TW",
                    "MetadataCountryCode": "TW",
                    "PreferredMetadataLanguage": "zh-TW",
                },
            )
            # GET 不是多餘的：StartupController.GetFirstUser 會先跑 UserManager.InitializeAsync，
            # 也就是建立預設使用者。少了它，POST 的 Users.First() 會丟
            # 「Sequence contains no elements」而回 500（10.10.7 / 10.11.11 皆實測）。
            report.record("startup_user_get", self.call("/Startup/User"))
            self.call(
                "/Startup/User", method="POST", json_body={"Name": ADMIN, "Password": PASSWORD}
            )
            self.call(
                "/Startup/RemoteAccess", method="POST", json_body={"EnableRemoteAccess": True}
            )
            self.call("/Startup/Complete", method="POST")
            report.note("初始精靈四步全部匿名完成（brief §20.7 的 FirstTimeSetupOrElevated 成立）")
        auth = self.call(
            "/Users/AuthenticateByName",
            method="POST",
            json_body={"Username": ADMIN, "Pw": PASSWORD},
        )
        self.token = auth["AccessToken"]
        self.user_id = auth["User"]["Id"]
        self.server_id = auth["ServerId"]

    # --- 媒體庫 ----------------------------------------------------------

    def create_library(self, name: str, collection_type: str, path: str) -> None:
        options: dict[str, Any] = {
            "Enabled": True,
            "EnableInternetProviders": True,
            "EnableRealtimeMonitor": False,
            "EnableChapterImageExtraction": False,
            "ExtractChapterImagesDuringLibraryScan": False,
            "EnableTrickplayImageExtraction": False,
            "ExtractTrickplayImagesDuringLibraryScan": False,
            "SaveLocalMetadata": False,
            "EnableEmbeddedTitles": False,
            "EnableEmbeddedEpisodeInfos": False,
            "SeasonZeroDisplayName": "Specials",
            "AutomaticRefreshIntervalDays": 0,
            "PathInfos": [{"Path": path}],
            # TypeOptions 留空 = 用 Jellyfin 的預設 fetcher（劇集與電影都是 TMDB），
            # 也就是實際部署的樣子。要看純檔名解析，靠媒體樹裡 TMDB 對不上的那組。
            "TypeOptions": [],
        }
        # body 是 AddVirtualFolderDto，LibraryOptions 要包一層。直接送 LibraryOptions
        # 不會報錯，但整份選項會被丟掉（10.10.7 / 10.11.11 實測，見 plan §9.4）。
        self.call(
            "/Library/VirtualFolders",
            method="POST",
            params={
                "name": name,
                "collectionType": collection_type,
                "paths": path,
                "refreshLibrary": "false",
            },
            json_body={"LibraryOptions": options},
        )

    def delete_library(self, name: str) -> None:
        if name in {lib["Name"] for lib in self.call("/Library/VirtualFolders")}:
            self.call(
                "/Library/VirtualFolders",
                method="DELETE",
                params={"name": name, "refreshLibrary": "false"},
            )

    def library_id(self, name: str) -> str:
        for lib in self.call("/Library/VirtualFolders"):
            if lib["Name"] == name:
                return str(lib["ItemId"])
        raise KeyError(name)

    def item_count(self) -> int:
        total = 0
        for lib in self.call("/Library/VirtualFolders"):
            page = self.call(
                "/Items",
                params={"parentId": lib["ItemId"], "recursive": "true", "userId": self.user_id},
            )
            total += int(page.get("TotalRecordCount", 0))
        return total

    def wait_for_scan(self) -> int:
        """掃描任務回 Idle 不代表 item 都建好了，再等數量連續兩次相同。"""
        self.call("/Library/Refresh", method="POST")
        time.sleep(5)
        poll(
            lambda: (self.task("RefreshLibrary") or {}).get("State") == "Idle",
            what="媒體庫掃描結束",
            timeout=900,
        )

        def stable() -> int | None:
            first = self.item_count()
            time.sleep(5)
            return first if first and first == self.item_count() else None

        return int(poll(stable, what="item 數穩定", timeout=600, interval=5))

    def task(self, key: str) -> Any:
        for entry in self.call("/ScheduledTasks"):
            if entry.get("Key") == key:
                return entry
        return None

    def run_task_and_wait(self, key: str, *, timeout: float = 600) -> Any:
        entry = self.task(key)
        if entry is None:
            return None
        self.call(f"/ScheduledTasks/Running/{entry['Id']}", method="POST")
        time.sleep(3)
        poll(
            lambda: (self.task(key) or {}).get("State") == "Idle",
            what=f"排程任務 {key} 結束",
            timeout=timeout,
        )
        return entry

    def items(self, **params: Any) -> list[dict[str, Any]]:
        params.setdefault("userId", self.user_id)
        rows: list[dict[str, Any]] = self.call("/Items", params=params).get("Items", [])
        return rows


def summarise_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只留下判斷字幕選單顯示所需的欄位。"""
    return [
        {
            "DisplayTitle": s.get("DisplayTitle"),
            "Title": s.get("Title"),
            "Language": s.get("Language"),
            "IsDefault": s.get("IsDefault"),
            "IsExternal": s.get("IsExternal"),
            "Codec": s.get("Codec"),
            "Path": s.get("Path"),
        }
        for s in streams
        if s.get("Type") == "Subtitle"
    ]


def summarise_item(item: dict[str, Any]) -> dict[str, Any]:
    sources = item.get("MediaSources") or []
    return {
        "Id": item.get("Id"),
        "Name": item.get("Name"),
        "Type": item.get("Type"),
        "ParentIndexNumber": item.get("ParentIndexNumber"),
        "IndexNumber": item.get("IndexNumber"),
        "IndexNumberEnd": item.get("IndexNumberEnd"),
        "ExtraType": item.get("ExtraType"),
        "Path": item.get("Path"),
        "ProviderIds": item.get("ProviderIds"),
        "MediaSourceCount": len(sources),
        "MediaSourceNames": [s.get("Name") for s in sources],
        "MediaSourcePaths": [s.get("Path") for s in sources],
        "SubtitleStreams": summarise_streams(
            [s for src in sources for s in (src.get("MediaStreams") or [])]
        ),
    }


def survey(jf: Jellyfin, report: Report, phase: str) -> dict[str, Any]:
    """把 Jellyfin 對整個媒體樹的解讀抓成一份快照。

    只用「媒體庫根 + recursive」抓一次，再照 Path 前綴分群。不逐個 Series 用
    parentId 查，因為那條路徑在剛掃完時可能回 0（見 series_child_query 的實測）。

    每個 Series 是一個 dict，季、集、extras 都掛在它底下 —— 讀的人只要跟著一條路走。
    """
    folders = jf.call("/Library/VirtualFolders")
    by_name = {f["Name"]: f for f in folders}
    result: dict[str, Any] = {
        "virtual_folders": [
            {
                "Name": f["Name"],
                "ItemId": f.get("ItemId"),
                "CollectionType": f.get("CollectionType"),
                "Locations": f.get("Locations"),
            }
            for f in folders
        ]
    }

    everything = jf.items(
        parentId=by_name["TV"]["ItemId"], recursive="true", fields=ITEM_FIELDS
    ) + jf.items(parentId=by_name["Movies"]["ItemId"], recursive="true", fields=ITEM_FIELDS)
    of_type = {
        t: [i for i in everything if i.get("Type") == t]
        for t in ("Series", "Season", "Episode", "Movie")
    }

    def under(parent_path: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prefix = parent_path.rstrip("/") + "/"
        return [i for i in items if (i.get("Path") or "").startswith(prefix)]

    def with_extras(item: dict[str, Any]) -> dict[str, Any]:
        return {
            **summarise_item(item),
            "Extras": [summarise_item(x) for x in jf.call(f"/Items/{item['Id']}/SpecialFeatures")],
        }

    result["series"] = [
        {
            **with_extras(entry),
            "Seasons": [with_extras(s) for s in under(entry["Path"], of_type["Season"])],
            "Episodes": sorted(
                (summarise_item(e) for e in under(entry["Path"], of_type["Episode"])),
                key=lambda e: (
                    e["ParentIndexNumber"] or 0,
                    e["IndexNumber"] or 0,
                    e["Name"] or "",
                ),
            ),
        }
        for entry in of_type["Series"]
    ]
    result["movies"] = sorted(
        (with_extras(m) for m in of_type["Movie"]), key=lambda m: m["Name"] or ""
    )
    report.record(f"survey_{phase}", result)
    return result


def series_child_query(jf: Jellyfin, tv_library_id: str) -> dict[str, Any]:
    """plan §8.2 的 find_episodes 走的是「以 series 為 parent」查詢，量它回幾筆。

    對照組是「以媒體庫為 parent + recursive」，同一批 Episode 一定查得到。
    """
    series = jf.items(
        parentId=tv_library_id, recursive="true", includeItemTypes="Series", fields="Path"
    )
    all_eps = jf.items(
        parentId=tv_library_id, recursive="true", includeItemTypes="Episode", fields="Path"
    )
    out = {}
    for s in series:
        prefix = (s.get("Path") or "").rstrip("/") + "/"
        out[s.get("Name") or s["Id"]] = {
            "by_library_recursive": len(
                [e for e in all_eps if (e.get("Path") or "").startswith(prefix)]
            ),
            "by_parent_id": len(
                jf.items(parentId=s["Id"], recursive="true", includeItemTypes="Episode")
            ),
            "by_shows_endpoint": int(
                jf.call(f"/Shows/{s['Id']}/Episodes").get("TotalRecordCount", 0)
            ),
        }
    return out


def print_survey(report: Report, snapshot: dict[str, Any], phase: str) -> None:
    report.heading(f"媒體樹快照（{phase}）")
    for s in snapshot.get("series", []):
        folder = (s["Path"] or "").rsplit("/", 1)[-1]
        report.note(f"Series: {s['Name']!r} 資料夾={folder!r} providers={s['ProviderIds']}")
        for season in s["Seasons"]:
            report.note(f"    Season: {season['Name']!r} index={season['IndexNumber']}")
            report.note(f"        季層 extras: {[x['Name'] for x in season['Extras']]}")
        for e in s["Episodes"]:
            span = f"-E{e['IndexNumberEnd']:02d}" if e["IndexNumberEnd"] else ""
            files = [(p or "").rsplit("/", 1)[-1] for p in e["MediaSourcePaths"]]
            report.note(
                f"    Episode S{e['ParentIndexNumber'] or 0:02d}E{e['IndexNumber'] or 0:02d}{span}"
                f" name={e['Name']!r} sources={e['MediaSourceCount']} {e['MediaSourceNames']}"
            )
            report.note(f"        檔案 {files}")
            for sub in e["SubtitleStreams"]:
                report.note(
                    f"        字幕 DisplayTitle={sub['DisplayTitle']!r} Title={sub['Title']!r} "
                    f"Language={sub['Language']!r} default={sub['IsDefault']}"
                )
        report.note(f"    劇集層 extras: {[x['Name'] for x in s['Extras']]}")
    for m in snapshot.get("movies", []):
        files = [(p or "").rsplit("/", 1)[-1] for p in m["MediaSourcePaths"]]
        report.note(f"Movie: {m['Name']!r} sources={m['MediaSourceCount']} {m['MediaSourceNames']}")
        report.note(f"    檔案 {files}")
        if m["Extras"]:
            report.note(f"    電影層 extras: {[x['Name'] for x in m['Extras']]}")


def install_merge_versions(jf: Jellyfin, report: Report) -> None:
    report.heading("MergeVersions 插件")
    repos = jf.call("/Repositories")
    if not any(r.get("Url") == MERGE_REPO for r in repos):
        repos.append({"Name": "danieladov", "Url": MERGE_REPO, "Enabled": True})
        jf.call("/Repositories", method="POST", json_body=repos)
    packages = poll(
        lambda: [p for p in jf.call("/Packages") if p.get("name") == MERGE_PACKAGE],
        what="插件庫出現 Merge Versions",
        timeout=120,
    )
    versions = [v.get("version") for v in packages[0].get("versions", [])]
    report.record("merge_versions_package", {"name": packages[0].get("name"), "versions": versions})
    report.note(f"插件庫可見版本：{versions[:5]}")
    wanted = MERGE_GUID.replace("-", "")

    def kick_install() -> bool:
        # 下載是 Jellyfin 自己連 GitHub，偶爾會 TLS 中斷回 500；重試而不是放棄。
        if any(p.get("Id", "").replace("-", "") == wanted for p in jf.call("/Plugins")):
            return True
        resp = request(
            f"{jf.base}/Packages/Installed/{MERGE_PACKAGE.replace(' ', '%20')}"
            f"?assemblyGuid={MERGE_GUID}",
            method="POST",
            headers={"Authorization": jf.auth_header()},
        )
        report.note(f"POST /Packages/Installed -> {resp.status}")
        time.sleep(10)
        return any(p.get("Id", "").replace("-", "") == wanted for p in jf.call("/Plugins"))

    poll(kick_install, what="MergeVersions 下載安裝完成", timeout=300, interval=10)
    installed = [
        {"Name": p.get("Name"), "Version": p.get("Version"), "Status": p.get("Status")}
        for p in jf.call("/Plugins")
        if p.get("Id", "").replace("-", "") == wanted
    ]
    report.record("merge_versions_installed", installed)
    report.note(f"插件安裝完成 {installed}，重啟 Jellyfin")
    request(f"{jf.base}/System/Restart", method="POST", headers={"Authorization": jf.auth_header()})
    time.sleep(5)
    poll(jf.public_info, what="Jellyfin 重啟完成", timeout=300)
    # /System/Info/Public 在伺服器還在載入時就回 200 了，這時 /ScheduledTasks 是
    # 503「Jellyfin 伺服器載入中」。要等真正吃得下管理員 API 才算重啟完成。
    poll(
        lambda: (
            request(f"{jf.base}/ScheduledTasks", headers={"Authorization": jf.auth_header()}).ok
        ),
        what="Jellyfin 載入完成（/ScheduledTasks 回 200）",
        timeout=300,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--label", required=True, help="報告用的版本標籤，例如 10.10.7")
    parser.add_argument("--out", type=Path, default=Path(".local/experiments/results"))
    parser.add_argument("--tv-path", default="/data/library/tv")
    parser.add_argument("--movie-path", default="/data/library/movies")
    args = parser.parse_args()

    report = Report(name=f"jellyfin-{args.label}", out_dir=args.out)
    jf = Jellyfin(args.base_url, args.label)

    report.heading(f"Jellyfin {args.label}（{args.base_url}）")
    jf.run_startup(report)
    info = jf.call("/System/Info")
    report.record("system_info", {k: info.get(k) for k in ("Version", "Id", "OperatingSystem")})
    report.note(f"版本 {info.get('Version')}，ServerId {jf.server_id}")

    jf.delete_library("TV")
    jf.delete_library("Movies")
    time.sleep(3)
    jf.create_library("TV", "tvshows", args.tv_path)
    jf.create_library("Movies", "movies", args.movie_path)
    report.note(f"第一次掃描完成，共 {jf.wait_for_scan()} 個 item")
    # 剛建完馬上讀，10.10.7 的 LibraryOptions 還是空的；掃完再讀才是真正存下來的值。
    report.record(
        "library_options_stored",
        {
            lib["Name"]: {
                k: lib.get("LibraryOptions", {}).get(k)
                for k in (
                    "EnableInternetProviders",
                    "EnableRealtimeMonitor",
                    "SeasonZeroDisplayName",
                )
            }
            for lib in jf.call("/Library/VirtualFolders")
        },
    )
    tv_id = jf.library_id("TV")
    parity = {"after_first_scan": series_child_query(jf, tv_id)}
    report.note(f"第一次掃描後的 series 子項查詢：{parity['after_first_scan']}")

    # 再掃一次：第一次掃完之後，以 series 為 parent 的查詢有機會回 0（見上一行的數字）。
    report.note(f"第二次掃描完成，共 {jf.wait_for_scan()} 個 item")
    parity["after_second_scan"] = series_child_query(jf, tv_id)
    report.note(f"第二次掃描後的 series 子項查詢：{parity['after_second_scan']}")
    report.record("series_child_query", parity)

    before = survey(jf, report, "before-plugin")
    print_survey(report, before, "未裝 MergeVersions")

    install_merge_versions(jf, report)
    merge_tasks = [
        {
            "Key": t.get("Key"),
            "Id": t.get("Id"),
            "Name": t.get("Name"),
            "Category": t.get("Category"),
        }
        for t in jf.call("/ScheduledTasks")
        if "merge" in (t.get("Key") or "").lower() or "merge" in (t.get("Name") or "").lower()
    ]
    report.record("merge_tasks", merge_tasks)
    for t in merge_tasks:
        report.note(f"排程任務 Key={t['Key']!r} Name={t['Name']!r} Id={t['Id']}")

    for key in ("MergeEpisodesTask", "MergeMoviesTask"):
        if jf.run_task_and_wait(key) is None:
            report.note(f"找不到排程任務 {key}")
    time.sleep(10)
    after = survey(jf, report, "after-merge")
    print_survey(report, after, "MergeVersions 合併後")

    report.record(
        "deep_link_candidates",
        {
            "hashbang": f"{jf.base}/web/index.html#!/details?id={{itemId}}&serverId={jf.server_id}",
            "hash": f"{jf.base}/web/index.html#/details?id={{itemId}}&serverId={jf.server_id}",
            "serverId": jf.server_id,
            "sample_series_id": (after.get("series") or [{}])[0].get("Id"),
            "sample_movie_id": (after.get("movies") or [{}])[0].get("Id"),
        },
    )
    report.note("深連結候選網址已記錄，實際可用性由 playwright 手動驗證")
    report.write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
