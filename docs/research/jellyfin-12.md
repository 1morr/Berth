# Jellyfin 12 查證：版本差異、劇集原生多版本、MergeVersions 的去留

2026-09-15。回答三件事：12.0 與 10.10 / 10.11 差在哪（只看與 Berth 有關的）、劇集原生多版本之後
MergeVersions 還要不要裝、Berth 要改哪裡。結論摘要在第 5 節。

## 0. 環境、方法與寫入紀錄

- **標記**：【實測 12.0.0】【實測 12.1.0】= 對一次性容器打過；【實測 真環境】= 對票 12 / 13 驗收那台 Jellyfin
  唯讀打過；【原始碼】= 讀過 tag 的程式碼（附行號）；【文件】= 官方 release notes、官方部落格、官方文件；
  【未查】= 查不到或沒做。**10.10 / 10.11 這一輪沒有重測**，對照一律引 [`m0-experiments.md`](m0-experiments.md)
  （2026-09-07 對 `jellyfin/jellyfin:10.10.7` / `:10.11.11` 的實測）。
- **原始碼**：`github.com/jellyfin/jellyfin` tag **`v10.11.11`**（`1fbd8739`）、**`v12.0`**（`6c073e19`，沒有
  `v12.0.0` 這個 tag）、**`v12.1`**（`ee91c75e`），shallow clone 到 session scratchpad 比對。
  `danieladov/jellyfin-plugin-mergeversions` tag **`12.0.0`**（`e6f58d63`）。
- **文件**：[v12.0 release notes](https://github.com/jellyfin/jellyfin/releases/tag/v12.0)（2026-09-08 發佈）、
  [v12.1 release notes](https://github.com/jellyfin/jellyfin/releases/tag/v12.1)（2026-09-15 發佈）、
  [官方部落格 Jellyfin 12.0](https://jellyfin.org/posts/jellyfin-release-12.0)（原檔
  `jellyfin.org/blog/2026/09-07-jellyfin-release-12.0/index.mdx`）、官方文件
  [`_video-multiversion.md`](https://github.com/jellyfin/jellyfin.org/blob/187351cd69c532a833c9ed57de036297012f5e9e/docs/general/server/media/_video-multiversion.md)
  （2026-09-09 由 jellyfin.org#1867「Episode multiversion support」改寫；Shows / Movies 兩頁都 import 它）。
  沒有引用論壇或第三方文章當結論。
- **一次性容器**（全部已刪，見本節最後）：

  | 名稱 | Image | Port | 回報版本 |
  | --- | --- | --- | --- |
  | `berth-research-jf120` | `lscr.io/linuxserver/jellyfin@sha256:0f42497a…`（= `12.0ubu2604-ls48`，本機 `latest` 那一份） | 18396 | `12.0.0` |
  | `berth-research-jf121` | `lscr.io/linuxserver/jellyfin:12.1ubu2604-ls49`（為了這次 pull） | 18397 | `12.1.0` |

  `/config` 與媒體樹各放一個 named volume（`<名稱>-config`、`<名稱>-data`）——Berth 的檔名接在 scratchpad
  的長路徑後面會超過 Windows 的 260 字元上限，bind mount 建不出來。腳本 `jf12_versions.py`（scratchpad，
  未進版控）**用 Berth 自己的 `berth.naming` 產生檔名、用 Berth 自己的 `HttpJellyfinClient` 跑 plan §9.4 的精靈
  與插件安裝**，dummy 影片是 image 內建 jellyfin-ffmpeg 產生的 2 秒 64×36 黑畫面 MKV（做法同
  `scripts/experiments/make_media.py`）。量測用 `GET /Items?parentId=<媒體庫>&recursive=true&fields=Path,MediaSources,MediaSourceCount`
  與 `GET /Shows/{id}/Episodes`。兩個版本各跑一輪。
- **真環境（唯讀）**：`localhost:8096`，`/System/Info/Public` 回 `Version: 12.0.0`。API key 以
  `docker exec berth /app/.venv/bin/python` 開 `file:/config/berth.db?mode=ro` 讀 `settings` 表
  `key='services.jellyfin'` 的 `value_json`（這張表的欄位是 `value_json`，不是 `value`）。對 Jellyfin 只發過 GET：
  `/System/Info/Public`、`/Plugins`、`/ScheduledTasks`、`/Repositories`、
  `/Items?recursive=true&includeItemTypes=Episode,Movie&fields=MediaSourceCount,Path,MediaSources`，
  以及驗證標頭探測（四種寫法各一次 `GET /ScheduledTasks`）。**沒有任何寫入、掃描、重啟或重建**，Berth 資料庫只以唯讀模式開過。
- **對一次性容器的寫入**：初始精靈、建 TV / Movies 媒體庫、建 API key、`Paths` 加一條路徑、三次 `RefreshLibrary`、兩次 `notify_paths`、
  加 `danieladov` 插件庫、安裝 MergeVersions、重啟、跑兩個合併任務；收尾前另對兩台送過 `POST /Startup/User`（401 / 403，沒有寫入）。
- **清理**（2026-09-15，實驗結束後）：

  ```
  docker rm -f berth-research-jf120 berth-research-jf121
  docker volume rm berth-research-jf120-config berth-research-jf120-data berth-research-jf121-config berth-research-jf121-data
  docker image rm lscr.io/linuxserver/jellyfin:12.1ubu2604-ls49
  ```

  之後 `docker ps -a --filter name=berth-research` 與 `docker volume ls --filter name=berth-research` 都是 0 筆；
  原本的 `berth`、`jellyfin`（仍是 `0f42497a69fa`）、`qbittorrent`、`prowlarr`、`berth-torrents` 照舊在跑。
  腳本、log 與原始碼 clone 只留在 session scratchpad，不進 repo。

## 1. 12.0 與 10.10 / 10.11 的差別（只列與 Berth 有關的）

### 1.1 版號為什麼從 10.11 跳到 12.0【文件】

- 部落格「Why 12.0?」：拿掉版號前面永遠不變的 `10`。**本來會叫 10.12.0 的版本就是 12.0**，伺服器回報 `12.0.0`；
  10.11.x 是最後一個舊版號系列。理由是 10.11.0 重寫了媒體庫資料庫，實質上是大版本，版號卻看起來像小更新，
  使用者照小更新的心態升級。部落格特別點名：**解析版號字串或釘 container tag 的工具要在升級前檢查**。
  實作是 [PR #16758 Switch to new version scheme](https://github.com/jellyfin/jellyfin/pull/16758)
  （`SharedVersion.cs` 的 `AssemblyVersion("12.0.0")`）。
- 12.1 已經在 2026-09-15 發佈（47 個修正，其中三個與多版本有關，見 §2.3）。

### 1.2 升級、資料庫遷移、能不能降回去【文件 + 原始碼】

- **可以從 10.10.7 或任何 10.11.x 直接升 12.0**，不需要中繼版本；更舊的要先升到 10.10.7（release notes「Notes on Updating」、部落格 TL;DR 第 2 點）。
- **降不回去**：「database changes that prevent rolling back without a full restore」，部落格寫「a backup is the only way back」。
  原始碼裡沒有找到主動擋降級的檢查（grep `downgrade` 無結果）；實際降級會怎樣【未查】。
- **升級前要先移除第三方插件**：「Plugins built for 10.11 will not load on 12.0」（部落格第 7 點）。
- **升級後必須完整掃描一次媒體庫**：自動分組的版本（不是手動合併的）在遷移時會被清掉，掃描之前那些版本看起來像不見了；
  第一次掃描會比平常久很多（release notes「Performance PR implications」、部落格第 4、5 點）。對應原始碼是
  [`20260113120000_MigrateLinkedChildren.cs` L289-320](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Server/Migrations/Routines/20260113120000_MigrateLinkedChildren.cs#L289-L320)
  （刪掉型別錯的 `LocalAlternateVersion` 關係，「recreated with the correct type on next library scan」）。
- 12.1 再加一個遷移 `RepairAlternateVersionLinks`（[PR #17842](https://github.com/jellyfin/jellyfin/pull/17842)），
  12.1.0 容器首次啟動的 log 有 `Seed migration null-RepairAlternateVersionLinks.`【實測 12.1.0】。

### 1.3 掃描與命名規則的變動

| 變動 | 來源 | 對 Berth |
| --- | --- | --- |
| **劇集支援多版本** | [PR #16828](https://github.com/jellyfin/jellyfin/pull/16828)（2026-05-15 併入 master，在 v12.0 裡） | 見第 2 節——這是最大的一條 |
| 電影版本標籤的分隔符除了 `-` 也接受 `_`、`.`，或以 `[` 開頭 | [PR #16465](https://github.com/jellyfin/jellyfin/pull/16465)；[VideoListResolver v12.1 L180-205](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Naming/Video/VideoListResolver.cs#L180-L205) | Berth 用 ` - `，不受影響；**「檔名開頭必須與資料夾名一致」這條沒變**（同一段 `StartsWith(folderName)`） |
| 版本選單的名字改成「去掉所有版本共同前綴」 | [BaseItem v12.0 L1289-1340、L1418-1470](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/BaseItem.cs#L1289-L1340) | 劇集的版本標籤不再是整個檔名主幹（§2.4） |
| 從季資料夾與集檔名解析 provider id（`tmdbid-` 等） | [PR #16472](https://github.com/jellyfin/jellyfin/pull/16472)；`EpisodeResolver` / `SeasonResolver` 的 `SetProviderIdFromPath` | Berth 的集檔名與季資料夾不帶 id，無影響 |
| `tmdb` / `tvdb` / `imdb` 可當 `tmdbid` 等的別名 | [PR #16433](https://github.com/jellyfin/jellyfin/pull/16433) | 無影響 |
| 沒有任何影片的季資料夾不再建 Season | [PR #16611](https://github.com/jellyfin/jellyfin/pull/16611)；[SeasonResolver v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/Resolvers/TV/SeasonResolver.cs)（`EnumerateFiles(..., AllDirectories)`） | Berth 不建空季資料夾；只有 `extras/` 的季資料夾仍算有影片 |
| 方括號 tag 出現在檔名中間時不再截斷標題 | [PR #16222](https://github.com/jellyfin/jellyfin/pull/16222) | 只影響「從檔名猜標題」；Berth 的資料夾帶 `[tmdbid-]` |
| `WEB-DL` 被當成 release tag 清掉 | [PR #17636](https://github.com/jellyfin/jellyfin/pull/17636) | 同上 |
| 集標題裡的帶連字號數字不再被當成多集檔；支援三位數以上集號 | [PR #17442](https://github.com/jellyfin/jellyfin/pull/17442)、[#16475](https://github.com/jellyfin/jellyfin/pull/16475) | 無影響 |
| symlink 只在播放時解析；`.ogg` 不再算影片 | release notes「Breaking and behavior changes」 | Berth 用硬鏈接、不產 `.ogg` |
| 名稱排序改用 `SortName` / `CleanName` | 同上 | 瀏覽頁的排序結果可能與 10.11 不同（M1.5） |

`POST /Library/Media/Updated` 背後的 [`FileRefresher.cs`](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/IO/FileRefresher.cs)
在 10.11.11 與 12.0 之間**一行都沒改**；`LibraryMonitor.cs` 只多了 `.ignore` 規則快取與 `DirectoryService.Invalidate`。
所以 brief §20.1「路徑通知對從沒掃到過內容的媒體庫無效」在 12.x 依然成立【原始碼】。

### 1.4 Berth 用到的端點【原始碼 + 實測 12.0.0 / 12.1.0】

方法：(1) `diff` 兩個 tag 的 controller；(2) 兩台一次性容器的 `/api-docs/openapi.json` 與
`api.jellyfin.org` 的 stable 版（已是 12.1.0）逐一查 path、`deprecated` 與 security policy；
(3) **用 Berth 的 `HttpJellyfinClient` 把 plan §9.4 整段序列加上 §8.2 / §9.5 的其他呼叫，對 12.0.0 與 12.1.0 各跑一遍**。

| 端點 | 10.11.11 → 12.0 原始碼 | 12.0 / 12.1 OpenAPI | 實測（兩版相同） |
| --- | --- | --- | --- |
| `GET /System/Info/Public` | 無變動 | 匿名 | 200 |
| `POST /Startup/Configuration` | `[Obsolete("Use configuration endpoints")]` | **deprecated**，`FirstTimeSetupOrElevated` | 匿名 204 |
| `GET /Startup/User` | `[Obsolete("Use authentication endpoints")]` | **deprecated** | 匿名 200（仍會建立預設使用者） |
| `POST /Startup/User` | **新增：第一個使用者已有密碼就回 403**（[L143-146](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/StartupController.cs#L143-L146)，[PR #17369](https://github.com/jellyfin/jellyfin/pull/17369)） | 未 deprecated | 精靈中匿名 204；**精靈完成後帶 API key 再送一次回 403、匿名回 401，原密碼仍可登入** |
| `POST /Startup/RemoteAccess` | `[Obsolete("Use configuration endpoints")]` | **deprecated** | 匿名 204 |
| `POST /Startup/Complete` | 無變動 | — | 204 |
| `POST /Users/AuthenticateByName` | 只加 `[Tags]` | 匿名 | 200，`AccessToken`、`User.Policy.IsAdministrator=true` |
| `GET` / `POST /Auth/Keys` | 只加 `[Tags]` | `RequiresElevation` | POST 204 不回 key，GET 列得回 `AppName=Berth` |
| `GET` / `POST /Library/VirtualFolders` | `name` 加驗證：不可空、不可前後空白 | `FirstTimeSetupOrElevated` | 精靈中匿名建 TV / Movies 成功，`LibraryOptions` 包一層照樣存下 |
| `POST /Library/VirtualFolders/Paths` | 無實質變動 | 同上 | 204，TV 的 `Locations` 變成 `[/data/library/tv, /data/library/tv-extra]` |
| `GET /Libraries/AvailableOptions` | — | `FirstTimeSetupOrDefault` | 精靈中匿名 200 |
| `POST /Library/Media/Updated` | **逐字相同** | `DefaultAuthorization` | 204；已有內容的媒體庫 100 秒內看到新加的版本（§2.3 第二階段） |
| `POST /Environment/ValidatePath` | 只刪了不相干的 `NetworkShares` | `FirstTimeSetupOrElevated` | 存在 → `True`、不存在 → `False` |
| `GET /Items` | 改成 async；**有 `includeItemTypes` 且沒指定 `recursive` 時預設遞迴**（[L335-339](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/ItemsController.cs#L335-L339)，release notes 說同一個查詢可能回不同結果） | `DefaultAuthorization` | Berth 明確帶 `recursive=true`，結果符合預期 |
| `GET /ScheduledTasks`、`POST /ScheduledTasks/Running/{id}` | 只加 `[Tags]` | `RequiresElevation` | 200 / 204 |
| `GET /Packages`、`POST /Packages/Installed/{name}` | 內建插件（`CanUninstall=false`）查詢與安裝一律 404（[L183-191](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/PackageController.cs#L183-L191)）；安裝器拒絕含路徑字元的套件名（[PR #17013](https://github.com/jellyfin/jellyfin/pull/17013)） | `RequiresElevation` | `Merge Versions`（含空白）裝得起來 |
| `GET` / `POST /Repositories` | 無變動 | `RequiresElevation` | 新裝的伺服器預設有 `Jellyfin Stable`（`https://repo.jellyfin.org/files/plugin/manifest.json`） |
| `GET /Plugins` | 插件圖片路徑加固 | `RequiresElevation` | 200 |
| `POST /System/Restart` | `SystemController` 無變動 | `LocalAccessOrRequiresElevation` | 回應正常；之後輪詢 `/ScheduledTasks` 到 200，插件載入完成。這一輪沒有看到 brief §20.7 記的「連線被切」，那是時序問題，不代表行為變了 |

另外兩條相關的：

- 12.0 移除了 `/emby/*` 與 `/mediabrowser/*` 路由前綴（[PR #15669](https://github.com/jellyfin/jellyfin/pull/15669)），Berth 不用。
- release notes 的 API 政策：「沒列在 OpenAPI 的端點不該用」「標 obsolete 的端點與參數不該用」「deprecation 至少標滿一個大版本週期才移除」。
  所以 `/Startup/Configuration`、`GET /Startup/User`、`/Startup/RemoteAccess` **12.x 還能用，下一個大版本可以拿掉**。

### 1.5 驗證標頭【原始碼 + 實測】

- 「舊式驗證」在 12.0 **預設關閉，而且有一個遷移會把既有安裝也關掉**（[PR #15559](https://github.com/jellyfin/jellyfin/pull/15559)、
  [#16754](https://github.com/jellyfin/jellyfin/pull/16754) 暫時恢復、[#16992](https://github.com/jellyfin/jellyfin/pull/16992) 再關；
  [`20260531160000_DisableLegacyAuthorization.cs` L27](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Server/Migrations/Routines/20260531160000_DisableLegacyAuthorization.cs#L27)）。
- 被這個開關擋住的是（[AuthorizationContext v12.0 L93-111、L233-235、L258-259](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Server.Implementations/Security/AuthorizationContext.cs#L93-L111)）：
  `X-Emby-Token`、`X-MediaBrowser-Token`、`?api_key=`、`X-Emby-Authorization` 標頭、`Emby` 這個 scheme 名。
  **不受影響**：`Authorization: MediaBrowser …, Token="…"` 與 `?ApiKey=`。
- 實測（同一把 API key 打 `GET /ScheduledTasks`）：

  | 寫法 | 真環境 12.0.0 | 一次性 12.0.0 | 一次性 12.1.0 |
  | --- | --- | --- | --- |
  | `Authorization: MediaBrowser Client=…, Token="…"`（Berth 的寫法） | 200 | 200 | 200 |
  | `X-Emby-Token` | 401 | 401 | 401 |
  | `X-Emby-Authorization` | 401 | 401 | 401 |
  | `?api_key=` | 401 | 401 | 401 |
  | `?ApiKey=` | 沒測 | 200 | 200 |

  **Berth 的 `berth/adapters/jellyfin/client.py` `_authorization()` 已經是不受影響的那一種，不用改。**

### 1.6 插件 ABI 與 `targetAbi`【文件 + 原始碼 + 實測】

- 12.0 目標框架是 **.NET 10**，插件必須重新 target、重新建置；多個插件介面改了。**處理多版本或播放清單內容的插件要改用新的
  `ILibraryManager` 方法**（`ResolveAlternateVersion`、`GetLocalAlternateVersionIds`、`GetLinkedAlternateVersions`、`UpsertLinkedChild`），
  因為這些關係不再序列化在父 item 裡（release notes「Platform」「Plugin changes」、部落格「Plugins」）。
- **安裝時挑版本**：`InstallationManager.GetCompatibleVersions` 只留 `targetAbi <= 伺服器版本` 的版本，再照版本號降冪取第一個
  （[L269-281](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Updates/InstallationManager.cs#L269-L281)）。
  所以 Berth **不指定版本**的 `POST /Packages/Installed/Merge%20Versions?assemblyGuid=…` 在 12.x 裝到 `12.0.0`（`targetAbi 12.0`），
  在 10.11 仍裝到 `10.11.0.1`【實測 12.0.0 / 12.1.0；10.11 引 m0 §1.6】。
- **載入時沒有下限**：本機插件的相容判斷只有 `伺服器版本 >= targetAbi`
  （[PluginManager L745-755](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Plugins/PluginManager.cs#L745-L755)），
  所以為 10.11 建的插件**過得了 ABI 檢查**，壞在載入型別（`TypeLoadException` → `NotSupported`，
  [L172-183](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Plugins/PluginManager.cs#L172-L183)）
  或執行時。MergeVersions 的舊版在 12.0 RC 上正是後者：`MissingMethodException: Method not found: 'System.String MediaBrowser.Controller.Entities.Video.get_PrimaryVersionId()'`
  （[mergeversions#103](https://github.com/danieladov/jellyfin-plugin-mergeversions/issues/103)、[#108](https://github.com/danieladov/jellyfin-plugin-mergeversions/issues/108) 的 log）。

### 1.7 linuxserver image【原始碼 + 實測】

- tag 格式從 `10.11.11ubu2604-ls47` 變成 **`12.0ubu2604-ls48`**、**`12.1ubu2604-ls49`**（少了修訂號那一位）。
  兩者的 base 都是 `ghcr.io/linuxserver/baseimage-ubuntu:resolute`（Ubuntu 26.04）；
  [`10.11.11ubu2604-ls47...12.0ubu2604-ls48`](https://github.com/linuxserver/docker-jellyfin/compare/10.11.11ubu2604-ls47...12.0ubu2604-ls48)
  只改了 CI 檔與 `package_versions.txt`，**Dockerfile 沒動**，`/config`、8096、`PUID` / `PGID` 都照舊。
- **`latest` 已經是 12.1**：Docker Hub 上 `latest`、`12.1ubu2604-ls49`、`version-12.1ubu2604` 同一個 digest（2026-09-15 05:55Z 推出）。
  本機的 `lscr.io/linuxserver/jellyfin:latest` 還是 `12.0ubu2604-ls48`（`0f42497a69fa`），真環境跑的就是它；
  下一次 `docker compose pull` 就會升到 12.1。
- **舊版 tag 會保留**：Docker Hub 仍列出 `12.0ubu2604-ls48`、`version-12.0ubu2604`，另有 `version-<版號>` 這種跟著同一版號重建的 tag。
  `m0-experiments.md` §0 寫的「linuxserver 只保留最新 tag，釘不了版本」**不成立**。
  官方 image `jellyfin/jellyfin` 另有 `12`、`12.1`、`12.0` tag（沒有 `PUID` / `PGID`，plan §9.1 選 linuxserver 的理由不變）。

## 2. 劇集原生多版本

### 2.1 官方文件的規則【文件】

`_video-multiversion.md`（Shows 與 Movies 兩頁共用）：

- **Shows**：「multiple versions are recognized when they are in the **same season folder** and are identified as the **same episode** per the standard naming scheme」。範例是
  `Season 01/Series Name S01E01 - 1080p.mkv`、`… - 720p.mkv`、`… - Extended.mkv`。**沒有要求 ` - ` 後綴、括號或子資料夾**。
- **Movies**（沒變）：檔名必須一字不差地以資料夾名開頭（含年份與 provider id），版本標籤以 `-`、`.`、`_` 分隔或放在方括號裡。
- 排序：字母序；結尾是 `p` / `i` 的解析度標籤依解析度降冪；第一個是預設版本。

### 2.2 原始碼：怎麼分組、在哪裡【原始碼】

1. `MovieResolver` 解析季資料夾裡的集數時，`ResolveVideos<Episode>` 的 `supportMultiEditions` 從 `false` 改成 `true`，
   並把 `collectionType` 傳進 `VideoListResolver`（10.11.11 L231、L277 → [v12.0 L234、L280](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/Resolvers/Movies/MovieResolver.cs#L234-L280)）。
2. `VideoListResolver.Resolve` 遇到 `CollectionType.tvshows` 走 `GetEpisodesGroupedByVersion`，其他走電影的
   `GetVideosGroupedByVersion`（[v12.1 L103-108](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Naming/Video/VideoListResolver.cs#L103-L108)）。
3. **分組的鍵只有季號與集號**：`EpisodePathParser` 解析每個檔案路徑，鍵是 `S{季}E{集}`（或日期型的 `DYYYYMMDD`），
   同一個資料夾清單裡同鍵的檔案併成一組（[v12.1 L207-272](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Naming/Video/VideoListResolver.cs#L207-L272)）。
   - **集標題不在鍵裡**：官方測試 `TestMultiVersionEpisodeSameNumberDifferentTitle` 明寫同集號不同標題「are grouped as alternate versions」，註解稱之為 trade-off。
   - **`IndexNumberEnd` 不在鍵裡**：多集檔 `S01E03-E04` 的鍵也是 `S1E3`（§2.3 實測）。
   - 版本先後由 `OrganizeAlternateVersions` 決定：檔名含解析度（`[0-9]{2}[0-9]+[ip]`）的依解析度降冪、同解析度依檔名排序，其餘依檔名排序（L274-319）。**是決定性的**，不像 10.10 / 10.11 + MergeVersions 那樣不保證順序。
4. **12.0 → 12.1 的差別**（[PR #17890](https://github.com/jellyfin/jellyfin/pull/17890)，修 #17885）：12.0 用樂觀解析、季號缺的時候當 0；
   12.1 只接受非樂觀解析，而且**季號與集號都要有**才分組。註解：「merging is destructive」。新增的兩個測試是標題含數字的絕對編號動畫檔名
   （`IS Infinite Stratos 2 - 01 - …`）在 12.0 會被誤併。Berth 的檔名一律有 `S01E01`，兩版行為相同（§2.3）。
5. **電影規則沒有跟著改分組條件**：`GetVideosGroupedByVersion` 仍要求每個檔名以資料夾名開頭（L121-205），只多了 `_` / `.` / `[` 分隔（§1.3）。
6. **版本選單的名字**：10.11.11 的 `GetMediaSourceName` 只會去掉「資料夾名」前綴（[L1225](https://github.com/jellyfin/jellyfin/blob/v10.11.11/MediaBrowser.Controller/Entities/BaseItem.cs#L1225)），
   劇集的檔名不以季資料夾名開頭，所以顯示整個主幹——m0 §1.3 看到的就是這個。12.0 先算**所有版本檔名的共同前綴，退到最後一個 `-`、`_`、`.`**，
   再去掉它（[v12.0 L1289-1340、L1418-1470](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/BaseItem.cs#L1418-L1470)）；
   12.1 讓數字之間的 `.` 不算分隔（[PR #17931](https://github.com/jellyfin/jellyfin/pull/17931)）。
7. 12.1 另修了「版本同時以群組與個別條目出現在媒體庫」並保留手動合併（[PR #17842](https://github.com/jellyfin/jellyfin/pull/17842)，修 #17942、#17970）。這一輪沒有重現 12.0 的那個症狀【未查成因】。

### 2.3 實測：Berth 真實命名會不會被合併【實測 12.0.0 / 12.1.0】

媒體樹全部由 `berth.naming.episode_target` / `movie_target` / `subtitle_target` 產生：

```
tv/Berth Test Show (2020) [tmdbid-1399]/Season 01/
  Berth Test Show (2020) - S01E01 - Winter Is Coming [BD][1080p][CHT+JP][Sakurato].mkv
  Berth Test Show (2020) - S01E01 - Winter Is Coming [BD][1080p][CHT+JP][Sakurato].CHT.zh.ass
  Berth Test Show (2020) - S01E01 - Winter Is Coming [WEB][1080p][CHS][Hardsub][Lilith-Raws].mkv
  Berth Test Show (2020) - S01E02 - The Kingsroad [BD][1080p][CHT+JP][Sakurato].mkv          ← 單一版本對照
  Berth Test Show (2020) - S01E03-E04 - Lord Snow [BD][1080p][CHT+JP][Sakurato].mkv          ← 多集檔
  Berth Test Show (2020) - S01E03 - Lord Snow [WEB][1080p][CHS][Hardsub][Lilith-Raws].mkv     ← 同起始集的單集
  Berth Test Show (2020) - S01E05 - The Wolf and the Lion [BD][1080p][CHT+JP][Sakurato].mkv  ← 第二版在第二階段才加
tv/Qwxzyv Berth Probe (2099) [tmdbid-999999901]/Season 01/                                    ← TMDB 對不上、沒有集名
  Qwxzyv Berth Probe (2099) - S01E01 [BD][1080p][CHT+JP][Sakurato].mkv
  Qwxzyv Berth Probe (2099) - S01E01 [WEB][1080p][CHT][喵萌奶茶屋].mkv
movies/Berth Movie Plan (2019) [tmdbid-27205]/
  Berth Movie Plan (2019) [tmdbid-27205] - [BD][2160p][CHT+JP][Sakurato].mkv
  Berth Movie Plan (2019) [tmdbid-27205] - [WEB][1080p][CHT][喵萌奶茶屋].mkv
  Berth Movie Plan (2019) [tmdbid-27205] - [WEB][720p][CHS][Hardsub][Lilith-Raws].mkv         ← 第二階段才加
```

四個階段：① 沒有插件，第一次掃描（`RefreshLibrary` 排程任務）；② 照 Berth 的入庫流程加兩個新版本 → `notify_paths`（`POST /Library/Media/Updated`）→ 等 100 秒量一次 → 再掃一次量一次；
③ 照 plan §9.4 第 8、9 步裝 MergeVersions、重啟、跑 `MergeEpisodesTask` 與 `MergeMoviesTask`；④ 裝著插件再掃一次。

**12.0.0 與 12.1.0 四個階段的結果逐項相同**：

| 對象 | 第一階段（無插件） | 第二階段（補版本後，通知 100 秒 / 重掃） | 第三、四階段（MergeVersions 跑過 / 再掃） |
| --- | --- | --- | --- |
| S01E01 兩版 | **1 個 Episode、2 個 `MediaSources`**：`Winter Is Coming [BD][1080p][CHT+JP][Sakurato]`、`Winter Is Coming [WEB][1080p][CHS][Hardsub][Lilith-Raws]` | 不變 | 不變 |
| 外掛字幕 `.CHT.zh.ass` | 只掛在 `[BD]` 那個 MediaSource（外部字幕數 1 / 0） | 不變 | 不變 |
| S01E02 單版 | 1 個 Episode、1 個來源，名稱是整個主幹，`MediaSourceCount` 欄位不存在 | 不變 | 不變 |
| **S01E03-E04 與 S01E03** | **被併成 1 個 Episode**（`IndexNumber=3`、`IndexNumberEnd` 為空），主要版本是單集 `[WEB]`，來源名 `S01E03 - Lord Snow [WEB]…` 與 `S01E03-E04 - Lord Snow [BD]…`；`/Shows/{id}/Episodes` 只有 1、2、3、5，**沒有第 4 集** | 不變 | 不變 |
| S01E05 | 1 個來源 | **通知 100 秒內就變成 1 個 Episode、2 個來源**（`The Wolf and the Lion [BD]…` / `[WEB]…`），不必重掃 | 不變 |
| Probe S01E01（無集名、中文組名） | 1 個 Episode、2 個來源：`S01E01 [BD][1080p][CHT+JP][Sakurato]`、`S01E01 [WEB][1080p][CHT][喵萌奶茶屋]` | 不變 | 不變 |
| 電影 | 1 個 Movie、2 個來源：`[BD][2160p][CHT+JP][Sakurato]`、`[WEB][1080p][CHT][喵萌奶茶屋]` | **通知 100 秒內變成 3 個來源**，順序 2160p → 1080p → 720p | 不變 |
| TV 媒體庫 Episode 總數 | 5（6 部影片檔） | 5（7 部影片檔） | 5 |

- Berth adapter 的 `items()` 在每個階段都拿得到全部路徑（`source_paths` 數 2 / 1 / 2 / 2 / 2；電影 3）：
  **第二個版本不是 item 自己的 `Path`，只出現在 `MediaSources[].Path`**——`services/resolver.py` 已經同時比 `Path` 與 `MediaSources`（票 12），反查不受影響。
- 電影版本標籤含中文組名（`喵萌奶茶屋`）照樣是純 tag。brief §20.1 標「標籤內含中文仍未證實」的那一條，**在 12.x 有答案了**（10.10 / 10.11 仍未測）。
- 限制：dummy 影片解析度都一樣；每版只跑一輪；版本選單只看 API 的 `MediaSources[].Name`，**沒有用瀏覽器看 jellyfin-web 的下拉選單**【未查】
  （m0 §1.8 在 10.x 確認過選單顯示的就是這個欄位）；沒有測「10.11 + MergeVersions 合併過的庫升到 12」【未查】。

### 2.4 與 10.11 的差別，以及對 Berth 命名的結論

| | 10.10.7 / 10.11.11（m0 §1.3） | 12.0.0 / 12.1.0（本節） |
| --- | --- | --- |
| 同集兩版，沒有插件 | **兩個重複的 Episode** | **1 個 Episode、2 個 MediaSources** |
| 版本標籤 | 裝 MergeVersions 後是**整個檔名主幹** | 去掉共同前綴：有集名時是 `集名 + tags`，沒有集名時是 `S01E01 + tags` |
| 版本順序 | 不保證（兩版相反） | 決定性：解析度降冪，再依檔名 |
| 多集檔與同起始集的單集 | 沒測 | **被當成同一集的兩個版本**，`E04` 從集列表消失 |
| 電影 | 1 個 Movie、多個來源，標籤是 ` - ` 之後 | 相同 |

- **Berth 現行的劇集模板在 12.x 不用改就會被原生合併**，唯一的硬要求仍是 brief §7.7 那一條：同一集各版本的檔名在 `S01E01` 之前一致。
  事實上 12.x 的要求更寬：同一個季資料夾、解析得出同一個 `S/E` 就會併。
- **版本標籤的算法和標題的標點有關**（退到共同前綴裡最後一個 `-`、`_`、`.`）：集名本身帶 `.`（例如 `It Didn't Have to Be Magic...`）時，標籤會從那個點之後開始，不一定含集名【原始碼推論，未實測】。

## 3. MergeVersions 插件

### 3.1 repo、manifest 與 12.0 支援【原始碼 + 文件】

- repo：[`danieladov/jellyfin-plugin-mergeversions`](https://github.com/danieladov/jellyfin-plugin-mergeversions)（README 連結沿用 brief §20.1）；
  manifest：`https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json`；套件名 `Merge Versions`、GUID `f21bbed8-3a97-4d8b-88b2-48aaa65427cb`（與 brief §20.7 相同）。
- manifest 內容（2026-09-15 下載）：

  | version | targetAbi | timestamp |
  | --- | --- | --- |
  | **12.0.0** | **12.0** | 2026-07-25 |
  | 10.11.0.1 | 10.11.0.0 | 2025-10-20 |
  | 10.10.0.5 | 10.10.0.0 | 2025-10-20 |

- tag `12.0.0` 的 [`Jellyfin.Plugin.MergeVersions.csproj`](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/12.0.0/Jellyfin.Plugin.MergeVersions/Jellyfin.Plugin.MergeVersions.csproj)：
  `net10.0`，`Jellyfin.Controller` **`12.0.0-rcrc3`**（對 RC3 套件建置，不是正式版）。合併改用新 API `UpsertLinkedChild(..., LinkedChildType.LocalAlternateVersion)`
  （[`MergeVersionsManager.cs` L183-250](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/12.0.0/Jellyfin.Plugin.MergeVersions/MergeVersionsManager.cs#L183-L250)）。
- 12.0.0 的合併規則：
  - 劇集：列出所有非虛擬 Episode，鍵依序是 Episode 的 `Tvdb` / `Tmdb` / `Imdb` provider id，沒有才用 `SeriesName + 季 + 集 + 結束集`（L85-112、L164-181）。**不看資料夾、不看媒體庫**。
  - 電影：依 `ProviderIds["Tmdb"]` 分組，組內有任何一部還沒被連結就合併（L38-64）。
  - 任務 `Key` / `Name` 不變：`MergeMoviesTask` / `Merge All Movies`、`MergeEpisodesTask` / `Merge All Episodes`（[`RefreshLibraryTask.cs` L53-54、L100-103](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/12.0.0/Jellyfin.Plugin.MergeVersions/ScheduledTasks/RefreshLibraryTask.cs)）。
- 12.0 相關的公開 issue（**只當現象紀錄，不當結論**）：
  [#111](https://github.com/danieladov/jellyfin-plugin-mergeversions/issues/111)（升到 12 後插件沒載入；另有人回報合併之後又被隨機拆開）、
  [#112](https://github.com/danieladov/jellyfin-plugin-mergeversions/issues/112)（Split Movies 讓 Jellyfin `database is locked` 而重啟）、
  [#109](https://github.com/danieladov/jellyfin-plugin-mergeversions/issues/109)（合併的電影從主媒體庫消失）、
  [#107](https://github.com/danieladov/jellyfin-plugin-mergeversions/issues/107)（無法停用或解除安裝）。均為 open。

### 3.2 真環境的狀態【實測 真環境，唯讀】

- `GET /Plugins`：`Merge Versions 12.0.0.0`，`Status: Active`，`CanUninstall: true`（其餘 AudioDB、ListenBrainz Similarity Provider、MusicBrainz、OMDb、Studio Images、TMDb 皆 `12.0.0.0` Active）。
- `GET /Repositories`：`Jellyfin Stable` 與 Berth 加的 `danieladov`。
- `GET /ScheduledTasks`：`Merge All Episodes`（`MergeEpisodesTask`，`dcaf151dd1af25aefe775c58e214477e`）與 `Merge All Movies`（`MergeMoviesTask`，`fd957c84b0cfc2380becf2893e4b76fc`），
  最近一次都在 2026-09-14T23:54:58Z `Completed`，耗時約 0.14 秒——Berth 票 12 的 resolver 觸發的。`RefreshLibrary` 最近一次 2026-09-14T23:19Z Completed。
- Berth 的 `settings.services.jellyfin` 存的兩個 task id 與上面一致。
- 內容：49 個 Episode、1 個 Movie，**全部只有 1 個來源**——真環境沒有多版本內容，看不出插件有沒有作用。
- 一次性 12.0.0 / 12.1.0 上兩個任務的 `Id` 也是這兩個值（與 m0 在 10.10 / 10.11 看到的相同），但 plan §9.4 照 `Key` 查 `Id` 的做法不變。

### 3.3 12.x 上還要不要、會不會衝突【實測 12.0.0 / 12.1.0 + 原始碼】

- **Berth 的樹不需要它**：第一、二階段在沒有插件的情況下已經全部合併（§2.3）。
- **裝了是空跑，沒有衝突**：照 plan §9.4 安裝（不指定版本 → `12.0.0`；重啟前 `Status: Restart`，重啟後 `12.0.0.0 Active`；#111 的「沒載入」沒有重現），跑兩個任務：
  - 容器 log：`Found 5 episodes and 0 duplicate episode groups`、`All movies merged`。
  - 合併前後、以及裝著插件再掃一次之後，每個 Episode / Movie 的來源數與名稱**完全不變**（§2.3 表格第三欄）。
  - 原因【原始碼】：原生分組的次要版本在資料庫裡有 `PrimaryVersionId`，一般的 item 查詢會把它們濾掉（[PR #17842](https://github.com/jellyfin/jellyfin/pull/17842) 的說明），插件看到的每一集只剩主要版本，湊不成一組。
- **它還會做、而原生不做的事**：把**不同資料夾或不同媒體庫**裡 provider id 相同的集數或電影合併（§3.1 的鍵不看位置）【原始碼推論，未實測】。
  Berth 自己不會產生這種重複；會碰到的是既有 Jellyfin 的使用者（例如同一部作品同時在舊路徑與 Berth 路徑、或在 TV 與 Anime 兩個媒體庫），而那正是 brief §20.1 記的「跨媒體庫合併」已知問題。
- 結論：**12.x 上不需要 MergeVersions，也不建議裝**——它對 Berth 的樹沒有增益，卻帶來一次 Jellyfin 重啟、對第三方 GitHub 下載的依賴（brief §20.7 記過 TLS 中斷）、跨媒體庫誤併，以及 §3.1 那幾個 open issue 的風險。
  **10.10 / 10.11 上仍然需要**（m0 §1.3：沒有它同一集是兩個重複條目）。

## 4. 對 Berth 的影響

先要做的決定：**Berth 支援哪些 Jellyfin 版本。** 套件內的 `lscr.io/linuxserver/jellyfin:latest` 已經是 12.1，所以「套件內 = 12.x」是現實；
「既有 Jellyfin」可能還是 10.10 / 10.11。下面的「必改」不論怎麼決定都成立；標「依版本決定」的，做法取決於要不要繼續支援 10.x。

### 4.1 必改

1. **文件裡「劇集多版本必須靠 MergeVersions」對 12.x 是錯的**，而那是套件內現在裝的版本：
   - brief §1.2 表格「同一集多版本的合併顯示 → Jellyfin + MergeVersions 插件」、§7.7 第一、二點、§20.1「多版本」段的「劇集原生多版本不可靠」與「結論：劇集多版本必須靠 MergeVersions 插件」。
   - `PRODUCT.md` L49、L99；`README.md` L81「外部服務的前提 → Jellyfin」。
   - brief §20.1 補上：12.0 起劇集原生多版本、分組鍵只有季號與集號（§2.2）、Berth 命名實測會併（§2.3）、中文組名的電影標籤在 12.x 可用。
2. **劇集版本標籤的預覽算錯了**：`berth/services/inventory.py` `_version_label()`（L551-561）對劇集回整個檔名主幹，那是 10.10 / 10.11 + MergeVersions 的樣子；
   12.x 顯示的是去掉共同前綴之後的部分，而且依標點與版本組合而變（§2.2 第 6 點、§2.4）。連帶要改：
   `tests/integration/test_media_holdings.py`（L208 那個測試的前提）、brief §7.7 第二點、`.scratch/m1/issues/13-library-page.md` 驗收的那一句。
   **建議的做法**是不自己算，改讀 Jellyfin 回的 `MediaSources[].Name`（`items()` 已經帶 `MediaSources`）——自己重算就要追著 10.x / 12.0 / 12.1 三種算法跑。
3. **精靈第 3 步的重試在 12.x 會卡住**：`POST /Startup/User` 在第一個使用者已有密碼時回 **403**（§1.4），`HttpSession` 把 403 翻成 `AuthFailedError`（`berth/adapters/http.py` L117-118），
   `_admin_user`（`berth/services/jellyfin.py` L399-408）就失敗。情境是第 3 步成功、第 4 到 6 步之中有一步失敗、Jellyfin 沒有重啟、使用者按重試——10.11 會過，12.x 會一直失敗，
   違反 plan §9.3「每一步都是冪等的」。（Jellyfin 若重啟過，`EnsureStartupWizardIntegrity` 會把精靈標成已完成，
   [ApplicationHost v12.0 L443-459](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/ApplicationHost.cs#L443-L459)，Berth 會走 `_fresh=False` 那條，不會卡。）
   要改的：`_admin_user` 把這個 403 當成「已經設過」繼續往下（之後的登入會驗證密碼對不對）、`berth/adapters/jellyfin/fake.py` 模擬這個行為、補測試、brief §20.7 記一條。
   【原始碼 + 部分實測：403 是在精靈完成後帶 API key 量到的，精靈未完成時匿名送的那條路徑只讀了原始碼】

### 4.2 建議

1. **MergeVersions 依版本安裝（依版本決定）**。只支援 12.x 就整段拿掉；同時支援 10.x 就以 `public_info.version` 的主版號判斷，`>= 12` 時不裝、不觸發：
   - `berth/services/jellyfin.py`：`_plugin` / `_tasks` 兩步（L461-497）與 `install_merge_versions()`（L158-165），以及 `MERGE_VERSIONS_*` 常數（L63-71）。
   - `berth/services/resolver.py` `_merge()` / `_run_merge()`（L306-343）與 `NO_MERGE_TASK`（L74-76）：12.x 上沒有 task id 會寫出 `jellyfin_request_failed(request=merge)`，訊息叫人去裝插件，是錯的指示。
   - `berth/domain/enums.py` `JellyfinRequest` 的說明（L140-145「MergeVersions 沒觸發，同一集的兩個版本會一直是兩個條目」）。
   - `berth/models/setting.py` 的 `merge_movies_task_id` / `merge_episodes_task_id`（L64-67）與 `setup.jellyfin.merge_versions_installed`（L179）；`berth/api/setup.py`（L177-178、L232）與 `web/src/api/schema.d.ts`。
   - 前端：`web/src/setup/JellyfinExisting.tsx`、`web/src/setup/jellyfinSteps.ts`（`plugin` 步）、`web/src/pages/SetupPage.tsx`、`web/src/i18n/resources.ts`（zh-Hant L156、L168、L178、L215-237、L801、L805；en L1178、L1190、L1200、L1239-1263、L1822-1826）。
   - 測試與 fake：`berth/adapters/jellyfin/fake.py`（套件版本寫死 `10.11.0.1`，L293）、`scripts/fake_setup_server.py`（L257-263）、`tests/integration/test_resolver.py` `TestMergeVersions`、
     `tests/integration/test_setup_api.py`、`tests/integration/test_adapter_contracts.py`（L1046、L1180-1241）、`web/src/pages/SetupPage.jellyfin.test.tsx`（L107-116、L260-269）、`web/src/jobs/JobTimeline.test.tsx`（L176）。
   - 文件：plan §8.2 `run_task`、§9.3 第 3 步、§9.4 第 8、9 步、§9.5「安裝 MergeVersions」按鈕、§11.2 T1.6、§12 風險表那一列；README L25 的步驟表與 L268；CHANGELOG 下一版。
2. **決定並寫下支援的 Jellyfin 版本**：README「外部服務的前提」目前沒有 Jellyfin 的版本下限（qBittorrent 有）。至少寫明 12.x 已實測（本文件）、10.10.7 / 10.11.11 的實測範圍（m0），以及 12.x 不需要 MergeVersions。
3. **compose 的 Jellyfin image 釘到大版本線**：`deploy/docker-compose.yml` L81 是 `lscr.io/linuxserver/jellyfin:latest`。12.0 證明大版本可以不可逆地改資料庫、讓插件失效、改變版本分組；
   `latest` 會在使用者 `docker compose pull` 時直接跨過去。linuxserver 沒有「整個 12 系列」的浮動 tag，可選的是 `version-12.1ubu2604`（跟著 12.1 重建）或固定的 `12.1ubu2604-ls49`；
   選哪個、以及 README 怎麼寫升級步驟（先備份 `${CONFIG_ROOT}/jellyfin`、升級後完整掃描），要一起決定。plan §9.1 表格同步。
4. **精靈用到的 deprecated 端點**：`/Startup/Configuration`、`GET /Startup/User`、`/Startup/RemoteAccess` 在 12.x OpenAPI 標 deprecated（§1.4）。現在能用；在 brief §20.7 記下，
   並在下一個 Jellyfin 大版本前評估改用設定端點（`/System/Configuration`、`/System/Configuration/network`）【替代端點的欄位未查】。
5. **多集檔與單集的衝突（§2.3）**：`S01E03-E04` 與 `S01E03` 在同一季資料夾時，12.x 把它們當成同一集的兩個版本，第 4 集從 Jellyfin 的集列表消失。
   Berth 的重複判定（brief §7.8，鍵含結束集）與媒體庫頁的版本分組（`inventory.py` 以 `(folder, season, start, end)` 分組）都把它們當成不同的東西，會與 Jellyfin 對不上。
   建議在 brief §7.7 / §7.8 決定行為（例如 planner 把「同季已有同起始集但結束集不同」送 review），並補 benchmark / 測試。
6. **升級既有 Jellyfin 的說明**：10.11 → 12 要先移除第三方插件、升級後完整掃描才找回自動分組的版本（§1.2）。README 疑難排解與健康檢查可以據 `public_info.version` 提醒；
   升級會不會讓 Berth 帳本上的 `jellyfin_item_id` 失效【未查】。
7. **更正研究紀錄**：`m0-experiments.md` §0「linuxserver 只保留最新 tag，釘不了版本」不成立（§1.7）；brief §20.1「MergeVersions 持續維護到 10.11 與 12.0」可補上 12.0.0 的 `targetAbi` 與 csproj 事實。
   依 CLAUDE.md，推翻 brief 的那一輪要在 `docs/progress.md`「偏差與決定」記一行。

### 4.3 不用改

- **驗證標頭**：`Authorization: MediaBrowser Client=…, Token="…"` 在 12.0 / 12.1 照常可用，被關掉的是舊式寫法（§1.5）。
- **Berth 用到的端點**：24 支在 12.0 / 12.1 都在、授權政策相同，Berth 的 adapter 整段跑通（§1.4）；plan §9.4 既有的四個細節（先 `GET /Startup/User`、`LibraryOptions` 包一層、`/Auth/Keys` 不回 key 也不去重、重啟後輪詢管理員端點）在 12.x 依然成立。
- **命名模板**：`berth/naming/__init__.py` 的劇集、電影、字幕模板在 12.x 不用改就能正確合併，外掛字幕掛在正確的版本上（§2.3）。
- **入庫後的反查**：`items()` 以媒體庫為 parent 並比對 `MediaSources[].Path`，在原生多版本下拿得到每個版本（§2.3）。
- **路徑通知**：已有內容的媒體庫，新版本在 100 秒內出現；「空的媒體庫通知無效」的後備（`SCAN_AFTER_MISSES`）仍然需要，`FileRefresher` 沒改（§1.3）。
- **MergeVersions 的安裝序列本身**（如果依 §4.2 第 1 點保留給 10.x）：不指定版本會自動挑對 `targetAbi` 的版本，任務 `Key` 不變（§1.6、§3.3）。
- 深連結、圖片、`/Items` 會靜默忽略未知參數等 M1.5 的結論：本輪沒有碰，`library-browsing.md` 已是對 12.0.0 查的。

## 5. 摘要

- **12.0 就是本來的 10.12**：拿掉版號前的 `10`；可從 10.10.7 / 10.11.x 直接升，降不回去；第三方插件要重建（.NET 10）；舊式驗證預設關閉。【文件 + 原始碼】
- **劇集原生多版本**：12.0 起，同一季資料夾裡解析出同一個 `S/E` 的檔案就是同一集的版本，不需要 ` - ` 後綴或子資料夾；鍵不含集名與結束集。
  Berth 現行命名在 12.0.0 與 12.1.0 **沒有插件就合併成 1 個 Episode、多個 MediaSources**，版本標籤變成「去掉共同前綴」的部分。【實測 + 原始碼 + 文件】
- **MergeVersions**：有 `12.0.0`（`targetAbi 12.0`），真環境已裝且 Active；12.x 上對 Berth 的樹是空跑，不需要，也不建議裝；10.10 / 10.11 仍需要。【實測 + 原始碼】
- **必改**：多版本相關的事實（brief、PRODUCT、README）、劇集版本標籤的預覽、精靈第 3 步重試遇到 403。**建議**：依版本拿掉插件流程、寫明支援版本、釘 image 大版本線、多集檔衝突的規則。
