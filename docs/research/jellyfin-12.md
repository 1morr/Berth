# Jellyfin 12 查證：版本差異、劇集原生多版本、MergeVersions 的去留

2026-09-15。回答三件事：12.0 與 10.10 / 10.11 差在哪（只看與 Berth 有關的）、劇集原生多版本之後
MergeVersions 還要不要裝、Berth 要改哪裡。結論摘要在第 6 節。

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

## 4. 從 10.11 升級到 12 的阻力（2026-09-15 補查）

回答：既有 10.11 使用者升到 12 會碰到哪些 breaking change 或阻力，哪些會讓人不方便或不敢升。§1 只挑了和 Berth 有關的，本節看一般使用者。

### 4.0 方法與來源

- **這一輪沒有起任何容器、沒有碰本機服務**，只讀文件、release notes、原始碼與官方 issue。標記沿用 §0，另加：
  【未查到】= 找過但沒有一手來源；【未查證】= 只有非一手（社群討論、摘要）來源。
- 伺服器原始碼：`v10.11.11`（`1fbd8739`）、`v12.1`（`ee91c75e`）shallow clone 後以 `git grep` / `git show` 讀；`v12.0` 的個別檔案以 GitHub API 讀。
  客戶端讀各 repo 2026-09-15 的 default branch，或註明的 tag。
- 文件：[v12.0 release notes](https://github.com/jellyfin/jellyfin/releases/tag/v12.0)、[v12.1 release notes](https://github.com/jellyfin/jellyfin/releases/tag/v12.1)、
  官方部落格原檔 `jellyfin.org/blog/2026/09-07-jellyfin-release-12.0/index.mdx`（下稱「部落格 TL;DR 第 n 點」）。
- issue、release 與發佈管道都是 **2026-09-15 08:50Z 前後的快照**。
- 第三方客戶端 / 整合與 NAS 發佈管道由兩個子代理查（表中標「子代理查」）；其中 Home Assistant 釘版、Ombi、Sonarr、Radarr、Seerr PR、
  SynoCommunity、TrueNAS、binhex、apt 的 armhf 與 `build.yaml` 另外親自重打過一次。

### 4.1 12.0 / 12.1 的升級注意與行為變更【文件】

「一般使用者」欄：**是** = 一般管理者升級就會碰到或要動手；看情況 = 只影響有特定設定或內容的人；否 = 開發者或無感。

**Notes on Updating 與部落格 TL;DR**

| # | 內容 | 來源 | 一般使用者 |
| --- | --- | --- | --- |
| 1 | 升級前**停掉 Jellyfin，完整手動備份資料與設定目錄**；資料庫變更讓「沒有完整還原就回不去」 | Notes 第 1 段；TL;DR 開頭 info 框（「a backup is the only way back」）與第 1 點 | **是** |
| 2 | 10.10.7 或任何 10.11.x 可直升；更舊的先升 10.10.7 | Notes 第 2 段；TL;DR 第 2 點 | 看情況（10.11 使用者不用中繼） |
| 3 | **遷移前移除所有第三方（repository）插件**，等作者出新版再裝回 | Notes 第 3 段；TL;DR 第 7 點「Plugins built for 10.11 will not load on 12.0」 | **是**（有第三方插件的人） |
| 4 | 插件庫若改成 unstable，改回 `https://repo.jellyfin.org/files/plugin/manifest.json` | Notes 第 4 段 | 看情況 |
| 5 | **升級後必須完整掃描媒體庫**，否則自動分組的版本看起來像不見；首次掃描比平常久很多，部分電影會顯示為新加入 | Notes「After migrating」；Server「Performance PR implications」（[PR #16062](https://github.com/jellyfin/jellyfin/pull/16062)）；TL;DR 第 4、5 點 | **是** |
| 6 | **先檢查使用者名稱**：只差大小寫的兩個帳號會讓資料庫遷移失敗 | Breaking 最後一條（[PR #17229](https://github.com/jellyfin/jellyfin/pull/17229)）；TL;DR 第 3 點 | 看情況，但**命中就是遷移失敗** |
| 7 | **遷移進行中不要停伺服器**；可以用 `--mode MigrateSystem` 先跑完遷移、不啟動伺服器 | TL;DR 第 5 點；Operations 第 1 條；部落格「What runs on first boot」 | **是**（大媒體庫遷移可能很久，§4.4） |
| 8 | 升級後瀏覽器強制重新整理或清快取 | TL;DR 第 6 點 | 是（無害） |
| 9 | **很舊的第三方客戶端會停止運作**：`/emby/`、`/mediabrowser/` 位址移除，舊式登入方式停用（含既有伺服器） | TL;DR 第 8 點；Breaking 第 1、2 條 | **是**（§4.2） |
| 10 | 含安全修正，建議準備好就升 | TL;DR 第 9 點 | — |
| 11 | 回報問題的標題加 `[12.0]` | Notes 最後；TL;DR 第 10 點 | 否 |

**Packaging、Breaking and behavior changes 與其他使用者看得到的變更**

| 內容 | 來源 | 一般使用者 |
| --- | --- | --- |
| Debian Bullseye、Ubuntu Focal 不再建置套件 | Packaging | 看情況：這兩個發行版的 apt 使用者要先升 OS（§4.3、§4.6） |
| 移除 `/emby/*`、`/mediabrowser/*` 路由前綴（[PR #15669](https://github.com/jellyfin/jellyfin/pull/15669)） | Breaking 第 1 條 | **是**（依客戶端，§4.2） |
| 舊式驗證預設關閉，遷移把既有安裝也關掉（[PR #15559](https://github.com/jellyfin/jellyfin/pull/15559)） | Breaking 第 2 條 | **是**（依客戶端，§4.2） |
| 移除 obsolete 路由：`POST /Users/{userId}/EasyPassword`、`GET /Items/{itemId}/CriticReviews`、`GET /Environment/NetworkShares`、`POST /System/MediaEncoder/Path`、`GET /LiveTv/Recordings/Groups/{groupId}`、`GET /QuickConnect/Initiate` | Breaking 第 3 條；部落格說前五個原本就是回 403 / 404 / 空結果的 no-op，只有 `GET /QuickConnect/Initiate` 真的能用，要改用 POST | 看情況（用 GET 發起 Quick Connect 的舊客戶端） |
| 全域字幕設定移除，改在各媒體庫設定（[PR #14957](https://github.com/jellyfin/jellyfin/pull/14957)） | Breaking 第 4 條；部落格「Changes you may notice after upgrading」 | **是**：要到每個媒體庫重看字幕設定。10.11.11 的 `MediaBrowser.Model/Providers/SubtitleOptions.cs` 在 12.1 已不存在，12.1 裡 `git grep SubtitleOptions` 只剩 `EmbeddedSubtitleOptions`，**舊的全域值會不會帶進媒體庫【原始碼推論：找不到搬移程式碼；實際結果未查】** |
| `.ogg` 改當音訊、`.aifc` 當音訊、`.aiff` 不再當圖片 | Breaking 第 5 條 | 看情況（有 `.ogg` 影片的人，下次掃描會被重新歸類） |
| symlink 只在播放時解析（[PR #16965](https://github.com/jellyfin/jellyfin/pull/16965)） | Breaking 第 6 條 | 看情況（用 symlink 組媒體庫的人） |
| 名稱排序改用 `SortName` / `CleanName`，順序可能與 10.11 不同（[PR #16804](https://github.com/jellyfin/jellyfin/pull/16804)、[#17402](https://github.com/jellyfin/jellyfin/pull/17402)） | Breaking 第 7 條 | 是（外觀） |
| 圖片端點不再放大超過原始解析度（[PR #17569](https://github.com/jellyfin/jellyfin/pull/17569)） | Breaking 第 8 條 | 是（外觀，低解析度海報變小） |
| 首次啟動清理資料：合併重複的音樂藝人與人物、移除孤立 extras 與外部資料、修正 owner 關係、重算 clean name / forced sort name / series presentation key | Database and performance 第 3 條 | **是**（耗時；§4.4 的遷移失敗多半出在這些遷移） |
| 已停用的插件重啟後不再被自動啟用 | Operations | 是（正面） |
| Web：Modern 版面成為預設，舊版改叫 Legacy；所有主題改從共用 base theme 衍生，**自訂主題可能要調** | Web；部落格「The Modern layout is now the default」 | 是（有自訂主題 / CSS 的人） |
| 內建 TLS 的移除**延後**到未來版本 | TLS Configuration；部落格最後一節 | 否（12.x 仍可用） |
| .NET 10、插件介面變更、Swashbuckle v10、`GetItems` 的遞迴行為 | Developers（API Changes / Platform / Plugin changes） | 否（開發者；使用者端的後果就是第 3 點「插件要等作者更新」） |

**12.1**：release notes 沒有 Breaking 或 Notes on Updating 段，只有 47 條 changelog，開頭照例「please ensure you take a full backup before upgrading」。和升級直接相關的修正：
[#17835](https://github.com/jellyfin/jellyfin/pull/17835) Clean up invalid data before running migrations、
[#17836](https://github.com/jellyfin/jellyfin/pull/17836) Fix database optimization memory use and pre-migration backup integrity、
[#17873](https://github.com/jellyfin/jellyfin/pull/17873) Delete the full ownership closure when deleting items、
[#18030](https://github.com/jellyfin/jellyfin/pull/18030) Stop wrong-type alternate version cleanup from recursing、
[#17842](https://github.com/jellyfin/jellyfin/pull/17842)（版本列表與手動合併）、
[#18044](https://github.com/jellyfin/jellyfin/pull/18044) Fix nested unnumbered season folders collapsing onto the first one、
[#18007](https://github.com/jellyfin/jellyfin/pull/18007) Preserve library items when directory enumeration fails、
[#17881](https://github.com/jellyfin/jellyfin/pull/17881) Fix /UserViews exhausting memory。
**10.11 使用者直接升 12.1，就避開了 §4.4 第一張表那批已修的問題。**

### 4.2 客戶端相容性

#### 4.2.1 官方說法與開關【文件 + 原始碼】

- **官方沒有逐一列出客戶端的相容性表**【未查到】。release notes 與部落格只有 TL;DR 第 8 點「Clients that have not seen an update in years are the ones at risk here」。
  最接近清單的是 PR #15559 的留言：
  - 維護者 nielsvanvelzen（2025-11-30）：「It is expected that some clients will break as they're not using our best practices.」
  - 團隊成員 oddstr13（[2026-01-19](https://github.com/jellyfin/jellyfin/pull/15559#issuecomment-3768297081)）列了**當時仍用 `api_key` 的不完整清單**：Jellyfin for Kodi、Mopidy、JellyCon、
    Python apiclient 與所有用它的東西、Chromecast、MPV Shim、Vue、Roku、iOS、數個官方插件。同一則留言指出 `ApiKey` 拼法從 10.8.0 就有。
    這是 2026-01 的狀態，§4.2.2 / §4.2.3 逐一對到已修版本。
- **使用者可以自己把舊式驗證打開**：
  - 開關是 `ServerConfiguration.EnableLegacyAuthorization`（[v12.0 L287-290](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Model/Configuration/ServerConfiguration.cs#L287-L290)，沒有初始值，所以是 `false`），
    存在設定目錄的 `system.xml`（[`BaseApplicationPaths.cs` v12.1 L70](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/AppBase/BaseApplicationPaths.cs#L70)）。
    遷移 `DisableLegacyAuthorization` 在升級時跑一次、設成 `false`（§1.5），之後手動改回 `true` 並重啟即可【原始碼推論，未實測】。
  - **後台沒有這個開關**：jellyfin-web v12.1 的 `src/strings/en-us.json` 沒有任何 legacy authorization 字串，只能改 `system.xml`，或以管理員身分透過 `POST /System/Configuration` 改【原始碼推論】。
  - **官方怎麼說**：PR #15559 說明「allowing a user to (temporarily) keep using the legacy method if they use an client that is not updated yet」，
    以及「We'll remove this configuration option (and the authorization methods) in a future release, likely 10.13」。依新版號，10.13 就是 13.0【推論】。
    官方文件站沒有提到這個設定【未查到：jellyfin org 內 code search `EnableLegacyAuthorization` 只命中 server 原始碼、各 SDK 的生成模型、jellyfin-mpv-shim 與 jellyfin-apiclient-python】。
- 被擋的寫法見 §1.5（`X-Emby-Token`、`X-MediaBrowser-Token`、`?api_key=`、`X-Emby-Authorization`、`Emby` scheme）；`Authorization: MediaBrowser …` 與 `?ApiKey=` 不受影響。

#### 4.2.2 官方客戶端

| 客戶端 | 12.x | 最低版本與依據 |
| --- | --- | --- |
| Jellyfin Web | 伺服器內建，跟著伺服器升 | v12.0（2026-09-08）、v12.1（2026-09-15）與伺服器同日發佈。web 從 **10.11.0** 起把 `api_key` 改成 `ApiKey`（[jellyfin-web PR #7014](https://github.com/jellyfin/jellyfin-web/pull/7014)，列在 v10.11.0 release notes）【文件】 |
| Android（jellyfin-android） | 可用 | 用官方 Kotlin SDK，SDK 以 `AuthorizationHeaderBuilder` 組 `Authorization` 標頭（sdk-kotlin master `jellyfin-api/src/commonMain/kotlin/org/jellyfin/sdk/api/client/util/AuthorizationHeaderBuilder.kt`；app v2.3.0 release notes 已用它）。最新 v2.7.3（2026-09-14），12.0 之後的 issue 沒有登入或驗證類回報【原始碼 + 文件；沒有找到明文的最低版本】。v2.7 是最後支援 Android 5 / 5.1 的版本（部落格 `2026/08-02-android-2-7`） |
| Android TV（jellyfin-androidtv） | 可用 | 穩定版 v0.19.10（2026-08-16）；[#5807](https://github.com/jellyfin/jellyfin-androidtv/issues/5807) 是「Server 12.0 + Android TV v0.19.10」的 Dolby Vision 播放問題，代表連得上、播得動。v0.19.10 release notes：0.20 將要求伺服器 10.11 以上；v0.20.0-beta.2（2026-09-14）【文件 + 官方 issue】 |
| iOS（jellyfin-expo / jellyfin-ios） | 可用 | v1.8.0.5（2026-08-14）release notes：「Fix server version display for 12.0」「Fix background audio playback pre-12.0」。在 oddstr13 2026-01 的清單上，**修掉 `api_key` 的是哪一版【未查】**；master 已找不到 `X-Emby` / `api_key=` 字串【原始碼】 |
| Swiftfin（iOS / tvOS） | 可用 | [Swiftfin#1859](https://github.com/jellyfin/Swiftfin/issues/1859)（「[10.12] Login not possible as LegacyAuthentication is disabled by default」）維護者回覆：jellyfin-sdk-swift 0.5.3（2025-09-22）已修，**Swiftfin 1.4（2025-12-12）起**實測可用。1.6（2026-08-12）升到 SDK 3.0.0（12.0）；[#2260](https://github.com/jellyfin/Swiftfin/issues/2260) 維護者說 1.6 仍可連 10.11.x【官方 issue】 |
| Jellyfin Media Player（jellyfin-media-player / jellyfin-desktop） | 可用【原始碼推論】 | **1.11.0（2024-06-06）起介面改用伺服器提供的 jellyfin-web**（v1.12.0 tag 的 `debian/changelog`），驗證跟著伺服器的 web 走；原生程式碼只在 `src/utils/Log.cpp` 遮蔽 log 裡的 `api_key` / `X-MediaBrowser-Token`，沒有拿它們發請求。最新穩定版仍是 v1.12.0（2025-03-20），v2.0.0 是 prerelease；沒有找到 12.0 的實測紀錄 |
| Jellyfin for Kodi（jellyfin-kodi） | **需 v2.0.0 以上** | [PR #1097 Migrate to current auth methods](https://github.com/jellyfin/jellyfin-kodi/pull/1097)（`api_key` → `ApiKey`、舊多標頭 → `Authorization`，merged 2026-02-11）；GitHub compare 顯示它在 **v2.0.0（2026-03-07）** 裡、不在 v1.1.1。[#1212 Jellyfin 12 Support](https://github.com/jellyfin/jellyfin-kodi/issues/1212)（closed）：維護者在 12.0 測試機上可用，但**同步（sync queue / websocket）有問題**，暫時解法是 Add-ons → Jellyfin → Manage libraries → Repair libraries；伺服器端的同步插件也要是 12.0 版【官方 issue】 |
| JellyCon（Kodi） | 需 v1.0.0 以上 | [jellycon PR #407](https://github.com/jellyfin/jellycon/pull/407)「Stop using deprecated auth methods」merged 2026-03-01，第一個含它的版本 v1.0.0（2026-06-13）【子代理查】 |
| Roku（jellyfin-roku） | 可用 | master 用 `Authorization` 標頭（`source/api/baserequest.bs` L238-244），trickplay 用 `?ApiKey=`（`components/video/PreloadTrickplayImagesTask.bs` L13）；3.1.8（2026-04-08）「Change trickplay code to be Jellyfin 12.0.0 compatible」（[PR #815](https://github.com/jellyfin/jellyfin-roku/pull/815)），最新 3.2.3（2026-08-03）。**哪一版開始完全不用 `api_key`【未查】**；12.0 相關 issue 只有相簿幻燈片（[#1079](https://github.com/jellyfin/jellyfin-roku/issues/1079)，closed） |
| webOS（jellyfin-webos） | 跟著伺服器 | README L3：「a small wrapper around the web interface provided by the server」，驗證跟伺服器的 web 走【原始碼】；12.0 回報遙控器暫停鍵失效 [#360](https://github.com/jellyfin/jellyfin-webos/issues/360)（open，標題寫 Regression） |
| Tizen（jellyfin-tizen） | **看打包進去的 web 版本** | 沒有 GitHub release；README 要使用者自己 clone jellyfin-web 打包，寫「It is recommended that the web version match the server version」，範例分支還是 `release-10.10.z`。用 10.10 以前的 web 打包，會帶 `api_key`（web 10.11.0 才改）【推論】。12.0 回報：[#432](https://github.com/jellyfin/jellyfin-tizen/issues/432) 照片全螢幕顯示破圖（open，另有留言說海報不顯示）【成因未查】 |
| MPV Shim（jellyfin-mpv-shim） | 需 v3.0.0 | v3.0.0（2026-09-08）release notes：「Jellyfin v12 is supported and all auth goes through the `Authorization` header」；3.0.0pre11 起「gaining Jellyfin v12 compatability without enabling legacy auth」【文件】 |

另外：Kotlin SDK v1.9.0（2026-09-08）release notes「Increase minimum supported server version to 12.0」。Android 與 Android TV 換上它的 PR（[jellyfin-android #2198](https://github.com/jellyfin/jellyfin-android/pull/2198)、[jellyfin-androidtv #5804](https://github.com/jellyfin/jellyfin-androidtv/pull/5804)）仍 open；
合併發佈之後，這兩個 app 的新版**會反過來要求伺服器是 12**【推論：app 是否另做相容層未查】。

#### 4.2.3 第三方客戶端與整合

| 名稱 | 12.x | 依據 |
| --- | --- | --- |
| Infuse | 已修於 8.3.6 | Firecore 官方社群公告 [Infuse 8.3.6](https://community.firecore.com/t/infuse-8-3-6-now-available/58792)（2025-12）：「Fixed authorization for Jellyfin 10.12」【子代理查】 |
| Findroid | 【未查到】直接紀錄 | 依賴官方 Kotlin SDK 1.8.12（`gradle/libs.versions.toml`），SDK 走 `Authorization` 標頭，推論不受驗證變更影響；沒有 12.0 相關 issue【子代理查，原始碼推論】 |
| Streamyfin | 不受影響 | `utils/jellyfin/jellyfin.ts` 用 `Authorization: MediaBrowser …`，依賴 `@jellyfin/sdk ^0.13.0`；沒有 12.0 相關 issue【子代理查，原始碼】 |
| Jellyseerr / Seerr | 已修於 Seerr v3.0.0（2026-02-14） | [seerr-team/seerr#2211](https://github.com/seerr-team/seerr/pull/2211)「fix(jellyfin-api): use standard Authorization header」merged 2025-12-08，取代 `X-Emby-Authorization`；[#2249](https://github.com/seerr-team/seerr/issues/2249) closed【PR 親查；版本號子代理查】。更名前的 Jellyseerr 舊版會壞【推論】 |
| Sonarr（Jellyfin / Emby 通知） | 已修於 4.0.19.2997（2026-08-04） | [Sonarr#8842](https://github.com/Sonarr/Sonarr/issues/8842)「Import Notification queue on Jellyfin 12+ produces 401 Unauthorized」closed 2026-08-04（PR #8845）；前一次修正 #8805（4.0.19.2995）不完整【issue 親查；版本號子代理查】 |
| Radarr（Jellyfin / Emby 通知） | 已修於 v6.4.3.10645（2026-08-31） | release notes「Fixed: Connecting to Jellyfin 12+ (#11663)」【文件】 |
| Home Assistant（Jellyfin 整合） | **可能仍會壞**【推論】 | 底層 [jellyfin-apiclient-python](https://github.com/jellyfin/jellyfin-apiclient-python) v1.18.0 已改用 `ApiKey`（`http.py` 註解寫明 v12 關閉 `api_key`），但 `home-assistant/core` 的 `homeassistant/components/jellyfin/manifest.json` 仍是 `jellyfin-apiclient-python==1.16.0`。整合實際哪些功能壞【未查；沒有找到 HA 的 12.0 issue】 |
| Jellystat | 不受影響 | `backend/classes/jellyfin-api.js` 用 `Authorization: MediaBrowser Token=…`；沒有 12.0 相關 issue【子代理查，原始碼】 |
| Jellyfin Vue | **目前會壞（播放）** | [jellyfin-vue#2693](https://github.com/jellyfin/jellyfin-vue/issues/2693)「Video playback does not work in Jellyfin Vue, but works in classic Jellyfin web」open；2026-07-25 的留言在 Server `12.0-rc3` + `ghcr.io/jellyfin/jellyfin-vue:unstable` 重現，主控台顯示 WebSocket 連 `ws://…/socket?api_key=…`（小寫，被舊式驗證開關擋掉的寫法）失敗、播放卡在載入。GitHub release 停在 0.3.1（2023），改以 `unstable` image 滾動發佈；也在 oddstr13 2026-01 的 `api_key` 清單上。正式 12.0 / 12.1 上是否相同【未查】 |
| Ombi | **目前會壞** | [Ombi#5478](https://github.com/Ombi-app/Ombi/issues/5478)「Jellyfin 12.0 - Unable to log in」，open，2026-09-15 建立 |
| Homepage（dashboard widget） | 改設定 `version: 2` | widget `version: 1` 走舊的 `/emby/` 路由會壞，`version: 2` 用 `Authorization` 標頭（gethomepage/homepage Discussion #7132）【未查證：Discussion 不是官方文件】 |

### 4.3 發佈管道：能不能「一鍵」拿到 12

| 管道 | 12.x | 版本 / 日期 | 來源 |
| --- | --- | --- | --- |
| 官方 Docker `jellyfin/jellyfin` | 有 | `latest` / `12` / `12.1`（2026-09-15 01:21Z）、`12.0`；**只有 amd64、arm64** | Docker Hub tags API（親查） |
| linuxserver `lscr.io/linuxserver/jellyfin` | 有 | `latest` = `12.1ubu2604-ls49`（§1.7）；amd64、arm64 | Docker Hub tags API（親查） |
| Debian apt（`repo.jellyfin.org/debian`） | bookworm、trixie 有 | `jellyfin-server` `12.1+deb12` / `12.1+deb13`（amd64、arm64） | `dists/<codename>/main/binary-<arch>/Packages`（親查） |
| Debian bullseye | **沒有** | 停在 10.11.11 | 同上（子代理查）；`jellyfin-packaging` `build.yaml` [v10.11.11 L29](https://github.com/jellyfin/jellyfin-packaging/blob/v10.11.11-202606061137/build.yaml#L27-L31) 有 bullseye，[v12.0 L27-30](https://github.com/jellyfin/jellyfin-packaging/blob/v12.0-202609072105/build.yaml#L27-L30) 沒有 |
| Ubuntu apt | jammy、noble、resolute 有 | `12.1+ubu2404` 等 | 同上（noble 親查） |
| Ubuntu focal | **沒有** | 停在 10.11.11 | 同上；`build.yaml` v10.11.11 L48 有 focal，v12.0 L44-48 沒有；移除的 commit `b19fe643`（2026-09-04，jellyfin-packaging #143，子代理查） |
| Windows installer | 有 | 12.1（exe / zip，2026-09-15） | `repo.jellyfin.org/files/server/windows/latest-stable/amd64/`（子代理查） |
| macOS | 有 | 12.1（dmg / tar.xz，2026-09-15） | `repo.jellyfin.org/files/server/macos/latest-stable/amd64/`（子代理查；arm64 目錄【未查】） |
| Synology（SynoCommunity） | 有，**但是 12.0，還沒 12.1** | `cross/jellyfin/Makefile` `PKG_VERS = 12.0`；`spk/jellyfin/Makefile` `REQUIRED_MIN_DSM = 7.2`、`UNSUPPORTED_ARCHS = $(32bit_ARCHS)`（L11-15） | [SynoCommunity/spksrc](https://github.com/SynoCommunity/spksrc) master（親查） |
| unRAID Community Apps 官方模板 | 【未查到】 | 模板原始檔沒找到；若模板指向 `jellyfin/jellyfin:latest` 就已經是 12.1【推論】 | — |
| unRAID binhex `arch-jellyfin` | **沒有** | 最新 `10.11.11-1-02`（2026-08-12） | [binhex/arch-jellyfin releases](https://github.com/binhex/arch-jellyfin/releases)（親查） |
| unRAID hotio | 有 | `release-12.1` | hotio.dev 容器頁（子代理以 WebFetch 讀）【未查證】 |
| TrueNAS apps | 有，**但是 12.0，還沒 12.1**；community train | `ix-dev/community/jellyfin/app.yaml`：`app_version: '12.0'`、`version: 1.3.14`、`train: community`；更新 commit `1b8c4452`（2026-09-08，子代理查） | [truenas/apps](https://github.com/truenas/apps) master（親查） |
| QNAP | **沒有官方套件** | 社群 myqnap.org「Jellyfin QMultimedia」10.11.11（2026-06-07） | myqnap.org 產品頁（子代理查）；官方 App Center 套件【未查到】 |
| Proxmox community-scripts | 跟著官方 apt | `ct/jellyfin.sh` 接官方 apt repo，不鎖版本 | [community-scripts/ProxmoxVE](https://github.com/community-scripts/ProxmoxVE)（子代理查） |

- Docker `latest`、官方 apt、Windows / macOS installer 的使用者**已經能一鍵拿到 12.1**；反過來說，`latest` 與 apt 的使用者下一次 pull / upgrade 就會直接跨過去，不需要主動選擇。
- SynoCommunity、TrueNAS 目前給的是 12.0（沒有 §4.1 列的 12.1 遷移修正）；binhex 與 QNAP 社群套件還停在 10.11.11，用它們的人**現在沒辦法一鍵升**。

### 4.4 升級失敗與回報【官方 issue】

範圍：`jellyfin/jellyfin` 在 2026-09-07 之後建立的 issue，挑出和升級、資料庫遷移、啟動失敗、媒體庫變空、觀看狀態有關的。
**沒有任何一條標 `regression` 標籤**（只有 #17942 標 `confirmed`）；「維護者回應」指 MEMBER / COLLABORATOR 的留言。

**12.1 已修**（維護者留言「Fixed by #… in 12.1」或「Should be fixed in 12.1」，issue 已 closed）

| issue | 標題（節錄） | 修正 |
| --- | --- | --- |
| [#17874](https://github.com/jellyfin/jellyfin/issues/17874) | Upgrade from 10.11.11 fails during ConsolidateLocalizedUserViews migration with FOREIGN KEY constraint failed | #17835 |
| [#17875](https://github.com/jellyfin/jellyfin/issues/17875) | Startup blocked: ConsolidateLocalizedUserViews fails … when AncestorIds contains orphaned rows | #17835 |
| [#17863](https://github.com/jellyfin/jellyfin/issues/17863) | Error during database migration: SQLite Error 19: 'FOREIGN KEY constraint failed' | #17835 |
| [#17830](https://github.com/jellyfin/jellyfin/issues/17830) | Migration RemoveOrphanedUserPermissionsAndPreferences fails with FOREIGN KEY constraint on 10.x → 12.0.0 upgrade | #17835 |
| [#17870](https://github.com/jellyfin/jellyfin/issues/17870) | FixIncorrectOwnerIdRelationships migration fails with FOREIGN KEY constraint failed | #17873 |
| [#17831](https://github.com/jellyfin/jellyfin/issues/17831) | Jellyfin 12.0 Docker Restart results in SQLite errors（重複的 [#17843](https://github.com/jellyfin/jellyfin/issues/17843) 維護者回覆：「If you have a broken db you need to restore from a backup」） | #17836 |
| [#18024](https://github.com/jellyfin/jellyfin/issues/18024) | Jellyfin v12.0 migration stuck in infinite loop deleting duplicate media | #18030 |
| [#18043](https://github.com/jellyfin/jellyfin/issues/18043) | Upgrade does not handle nested folders as Jellyfin previously did | #18044 |
| [#17942](https://github.com/jellyfin/jellyfin/issues/17942) | Library Scan splits manually merged Versions | #17842 |
| [#17918](https://github.com/jellyfin/jellyfin/issues/17918) | Login crashes the docker container after the upgrade | 未指明 PR |
| [#17871](https://github.com/jellyfin/jellyfin/issues/17871) | a single `GET /UserViews` request allocates 25 GB of heap and OOM-kills the server on a large library | 未指明 PR（應是 #17881） |
| [#17934](https://github.com/jellyfin/jellyfin/issues/17934) | Jellyfin 12.0 leaks native memory until OOM killed | 未指明 PR |

**仍 open**

| issue | 標題（節錄） | 維護者回應 |
| --- | --- | --- |
| [#17849](https://github.com/jellyfin/jellyfin/issues/17849) | [12.0]: Jellyfin migration broken after upgrade（13 則留言） | 無 |
| [#17840](https://github.com/jellyfin/jellyfin/issues/17840) | Upgrade to 12.0 stuck for more than 2 hours | 有（要 debug log，懷疑 VACUUM） |
| [#17936](https://github.com/jellyfin/jellyfin/issues/17936) | Upgrading from 10.11.11 to 12.0 Migration RefreshCleanNamesAndValues failed | 無 |
| [#17907](https://github.com/jellyfin/jellyfin/issues/17907) | ChangeOwnerIdToGuid migration fails with "FOREIGN KEY constraint failed" | 無 |
| [#18032](https://github.com/jellyfin/jellyfin/issues/18032) | Migration ConsolidateLocalizedUserViews fails with FOREIGN KEY constraint on 10.11.8 to 12.0.0 upgrade | 無（和已修的 #17874 同一個遷移，是否同因【未查】） |
| [#18050](https://github.com/jellyfin/jellyfin/issues/18050) | Migration "20260508130000_MergeDuplicatePeople" failed | 有（要完整 log） |
| [#17862](https://github.com/jellyfin/jellyfin/issues/17862) | **[12.1]** Jellyfin doesn't startup after upgrade | 無 |
| [#17868](https://github.com/jellyfin/jellyfin/issues/17868) | [12.0] cant start server even after cleaning /var/lib/jellyfin | 無 |
| [#17919](https://github.com/jellyfin/jellyfin/issues/17919) | Upgrading from 10.11.11 to 12.0 (Docker) fails | 無 |
| [#17900](https://github.com/jellyfin/jellyfin/issues/17900) | … post-upgrade scan wiped both my libraries to 0 | 無 |
| [#18023](https://github.com/jellyfin/jellyfin/issues/18023) | [12.0] library scan removed seasons | 無 |
| [#17877](https://github.com/jellyfin/jellyfin/issues/17877) | [12.0] Random shows locked on "watched" status | 有（詢問資料夾結構與媒體庫設定） |

其他值得記的（closed，但原因不是伺服器 bug）：

- [#17921](https://github.com/jellyfin/jellyfin/issues/17921)：Docker 升級後 `CultureNotFoundException` 崩潰。維護者：拿掉 compose 裡的 `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`，「an old config that is no longer needed」。
- [#17916](https://github.com/jellyfin/jellyfin/issues/17916)：升 12.0 後伺服器隨機關閉。維護者：「TMDb Box Sets: the old plugin will 100% crash your system」，要跑插件更新任務再重啟。
- 標題直接是「觀看紀錄遺失」的官方 issue【未查到】；相近的是 #17877（觀看狀態卡住）與 #17900（媒體庫變 0）。

**遷移前的自動備份**【原始碼】：`JellyfinMigrationService.PrepareSystemForMigration`（[v12.1 L361-438](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Server/Migrations/JellyfinMigrationService.cs#L361-L438)）在有待跑的 EF 遷移時，
先把 `jellyfin.db` 複製到資料目錄下的備份資料夾（[`SqliteDatabaseProvider.MigrationBackupFast` L233-258](https://github.com/jellyfin/jellyfin/blob/v12.1/src/Jellyfin.Database/Jellyfin.Database.Providers.Sqlite/SqliteDatabaseProvider.cs#L233-L258)）；
遷移丟例外時嘗試還原（L258-298，`RestoreBackupFast`），全部成功後刪掉備份（`CleanupSystemAfterMigration` L316 起）。
它只保護資料庫，還原之後執行檔仍是 12，要回 10.11 還是得換回舊 image 或套件【推論】；12.0 的這份備份本身有完整性問題（#17831 → #17836，12.1 修）。**不能取代 TL;DR 第 1 點的手動完整備份。**

### 4.5 資料是否保留【原始碼】

| 資料 | 結論 | 依據 |
| --- | --- | --- |
| 使用者帳號 | 保留；新增 `NormalizedUsername`（`Username.ToUpperInvariant()`）與 unique index。**只差大小寫的帳號會讓遷移失敗**，不會被合併或刪除 | EF 遷移 `20260522092303_AddNormalizedUsername`、`20260524120336_AddUniqueNormalizedUsernameIndex`；routine `20260522092304_UpdateNormalizedUsername.cs`（v12.1）；TL;DR 第 3 點 |
| 使用者權限與偏好 | 刪掉孤立的列 | EF 遷移 `20260815063607_RemoveOrphanedUserPermissionsAndPreferences`（只看到檔名，內容因 Windows 路徑長度沒讀到【未查】）；相關失敗 #17830 |
| API key | 保留：12.0 / 12.1 新增的 routine 與 EF 遷移沒有任何一支碰 `ApiKeys`。**但是 key 的送法會影響能不能用**：用 `?api_key=` 或 `X-Emby-Token` 送 key 的腳本與工具升級後會 401（§1.5） | `git grep` v12.1 `Jellyfin.Server/Migrations/Routines/2026*`；EF 遷移清單（v10.11.11 → v12.1 新增 17 支，沒有 ApiKeys 相關） |
| 觀看紀錄（UserData） | 保留。刪除 item 時 UserData 不跟著刪，而是改掛到 placeholder item（`00000000-0000-0000-0000-000000000001`）並設 `RetentionDate`；item 再出現時由 `ReattachUserDataAsync` 接回。所以下方 item id 段落裡「被刪後重建」的 item，觀看紀錄有機會接回【接回的比對鍵與保留期限未查】 | 10.11.11 `BaseItemRepository.cs` L61、L132-139、L773-794；12.1 `BaseItemRepository.cs` L35、`ItemPersistenceService.cs` L126-132、L221-242 |
| 人物與音樂藝人 | 重複的會合併；`MergeDuplicatePeople`、`MergeDuplicateMusicArtists` 內有處理 UserData（檔內 6 / 4 處引用），收藏等是否完整轉移【未查】 | v12.1 routines `20260508130000_MergeDuplicatePeople.cs`、`20260508120000_MergeDuplicateMusicArtists.cs` |
| 媒體庫設定 | 大致保留；全域字幕設定移除且找不到搬移程式碼（§4.1）。另有 `FixLibrarySubtitleDownloadLanguages`（修正媒體庫字幕語言值）、`EnableLocalSimilarityProviders`（新選項） | v12.1 routines |
| 使用者檢視（UserView） | **id 可能改變**：`ConsolidateLocalizedUserViews` 把「id 由在地化名稱算出」的整類檢視（例如 Live TV）搬到與名稱無關的 canonical id；子項目的 `ParentId` / `TopParentId`、ancestor 與使用者設定改掛新 id，舊 id 的列刪除。媒體庫本身（CollectionFolder）不在範圍內 | [`20260825200000_ConsolidateLocalizedUserViews.cs` v12.1 L58-173](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Server/Migrations/Routines/20260825200000_ConsolidateLocalizedUserViews.cs#L58-L173) |
| 第三方插件的設定 | 插件要先移除（§4.1），設定檔會不會留著【未查】 | — |

**item id（Berth 帳本的 `jellyfin_item_id`）**

- **算法沒變**：`LibraryManager.GetNewItemIdInternal` 在 [10.11.11 L636-658](https://github.com/jellyfin/jellyfin/blob/v10.11.11/Emby.Server.Implementations/Library/LibraryManager.cs#L636-L658)
  與 [12.1 L797-819](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/Library/LibraryManager.cs#L797-L819) 逐字相同：`MD5(type.FullName + path)`，
  `EnableCaseSensitiveItemIds` 預設 `true`（`ServerConfiguration.cs` L89，兩版相同）時不轉小寫。**同一路徑、同一型別的 item，升級前後 id 相同**。
- **會變或會消失的**（`MigrateLinkedChildren`，[v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Server/Migrations/Routines/20260113120000_MigrateLinkedChildren.cs)）：
  1. **型別錯的自動分組次要版本**被刪（`CleanupWrongTypeAlternateVersions` L285-321，例如主版本是 `Movie`、次要版本是泛用 `Video`）。註解明寫「Since IDs are computed from type + path, just updating the Type column would break ID lookups」，
     下次掃描以正確型別重建，**重建後 id 不同**【原始碼推論：型別換了，雜湊就換了】。帳本若記的是次要版本自己的 item id 會失效，記主版本的不受影響。
  2. 有 `OwnerId`、不是 extra、又沒有 LinkedChild 指向的孤立版本被刪（L323-348）。
  3. `TopParentId` 指向已不存在媒體庫的 item 被刪（L350-373）。
  4. **檔案已不存在的 item 被刪**（`CleanupStaleFileEntries` L375-495）。根目錄不存在或是空的就跳過該路徑下的檢查（L386-402）；任一根目錄不可讀時，不刪「不在任何媒體庫路徑下」的 item（L415-418、L462-470）。
     根目錄存在且非空、但底下部分檔案暫時讀不到（例如只掛上一部分）時仍會刪【原始碼推論】。
- 其他型別變動也會換 id：`.ogg` 影片改當音訊；部落格 TL;DR 第 5 點「some movies may appear as newly added」與 release notes「due to type issues that got fixed on-scan」指的就是型別被修正的條目以新 item 出現【文件 + 原始碼推論】。
- 結論：**一般 Movie / Episode 主條目的 id 升級後不變**；會變的是型別被修正的條目（包括自動分組的次要版本），以及被清掉的孤立或缺檔條目。
  沒有做「同一個 10.11 媒體庫升級前後逐筆比對 id」的實測【未查】。

### 4.6 系統需求變動

| 項目 | 10.11.11 | 12.0 / 12.1 | 來源 |
| --- | --- | --- | --- |
| .NET | `net9.0` | **`net10.0`** | 兩個 tag 的 `Jellyfin.Server/Jellyfin.Server.csproj`【原始碼】；release notes Platform |
| 官方建置的 CPU 架構 | amd64、arm64（Linux 另有 musl 版）；**armhf 已在 10.11 分支移除** | 相同 | `jellyfin-packaging` `build.yaml` v10.11.11 與 v12.0 的 `archmaps` 都只有 amd64 / arm64（親查）；移除 armhf 的 commit `499fddfa`（2025-06-07「Remove deprecated armhf builds for 10.11.x」，子代理查）；apt 的 armhf `jellyfin-server` 最高 **10.10.7**（bookworm、noble），trixie 沒有 armhf 套件（親查） |
| Debian / Ubuntu | bullseye、bookworm、trixie；focal、jammy、noble、resolute | **bookworm、trixie；jammy、noble、resolute** | `build.yaml` v10.11.11 L27-51 → v12.0 L27-48（親查） |
| Docker image | amd64、arm64 | amd64、arm64 | Docker Hub tags API（親查 12.x） |
| Synology | — | DSM ≥ 7.2，x64 / armv8，排除 32 位元 | SynoCommunity `spk/jellyfin/Makefile` L11-15（親查） |
| FFmpeg | 【未查確切版本】 | **jellyfin-ffmpeg 8.1**，套件名改成 `jellyfin-ffmpeg8`，目前 v8.1.2-5 | release notes Transcoder「New upstream version of FFmpeg 8.1」；[jellyfin-ffmpeg v8.1.1-1](https://github.com/jellyfin/jellyfin-ffmpeg/releases/tag/v8.1.1-1)（自述 targets 12.0，子代理查） |
| 硬體轉碼驅動 | — | 官方文件沒有為 12.x 改門檻：NVIDIA 頁仍寫「Jellyfin 10.11」時的 522.25 / 520.56.06；Intel、AMD 的 12.x 專屬門檻【未查到】 | jellyfin.org `docs/general/post-install/transcoding/hardware-acceleration/nvidia.md`（子代理查） |
| 最低 Windows / macOS 版本 | — | 【未查】（.NET 10 自身的支援範圍沒查） | — |

- 對舊 NAS 的實際影響：32 位元 ARM 在 10.11 就已經沒有官方建置，**從 10.11 升 12 不會新增 CPU 架構門檻**；
  新增的是 **Debian 11 / Ubuntu 20.04 的 apt 使用者要先升級 OS**，以及 FFmpeg 8.1 換版（驅動門檻未見調整）。

### 4.7 對「只支援 12 以上」的判斷依據

**會讓使用者不方便或不敢升級的**

1. **不可逆，而且遷移失敗仍有 open issue**：回不去只能靠完整備份（§1.2、§4.1）。12.0 發佈一週內，§4.4 的 open 表有 12 條遷移、啟動、媒體庫變空的回報，多數沒有維護者回應，其中 #17862 是 12.1。
   內建的遷移前備份只保護資料庫，且 12.0 的這份備份有完整性 bug（12.1 修）。
2. **舊客戶端與整合會壞，官方又沒有相容性表**（§4.2.1）。要升級才能用的：Jellyfin for Kodi（v2.0.0+，同步仍有問題）、JellyCon（v1.0.0+）、MPV Shim（v3.0.0）、
   Seerr（v3.0.0；更名前的 Jellyseerr）、Sonarr（4.0.19.2997+）、Radarr（6.4.3.10645+）、Infuse（8.3.6+）。**目前還沒修的**：Ombi（open）、Jellyfin Vue 的播放（open，RC 上重現），Home Assistant 整合（依賴仍釘 1.16.0，推論）。
   Tizen 要看自己打包的 web 版本。可以打開 `EnableLegacyAuthorization` 暫時繞過，但後台沒有開關、要手改 `system.xml`，官方也預告下一個大版本移除（§4.2.1）。
3. **第三方插件要先移除，等作者出 12.0 版**（§4.1）；舊插件可能讓 12.0 當機（#17916 的 TMDb Box Sets）。
4. **部分一鍵管道還沒有 12.1，或根本沒有 12**：binhex（unRAID）與 QNAP 社群套件停在 10.11.11；SynoCommunity、TrueNAS 是 12.0，沒有 12.1 的遷移修正；
   Debian 11 / Ubuntu 20.04 的 apt 使用者要先升 OS（§4.3、§4.6）。
5. **升級當下與升級後的工作**：只差大小寫的使用者名稱要先處理，否則遷移失敗；遷移期間不能停；之後要完整掃描（大媒體庫很久），再到每個媒體庫重看字幕設定（§4.1）。

**只是要注意的**

1. 10.11.x 可直升，不需要中繼版本；直接升 12.1 就避開了一批已修的遷移 bug（§4.1、§4.4）。
2. 主要官方客戶端（Web、Android、Android TV、iOS、Swiftfin、Roku、webOS、JMP）在 12.x 可用，或跟著伺服器的 web 走（§4.2.2）。
   反過來，Kotlin SDK 1.9.0 已把最低伺服器版本拉到 12.0，Android / Android TV 換上新 SDK 之後，新版 app 可能反而要求伺服器是 12（§4.2.2 末段，推論）。
3. 帳號、API key、觀看紀錄、一般媒體條目的 item id 原則上保留；會變的是型別被修正的條目、自動分組的次要版本、UserView（§4.5）。API key 本身在，但用舊寫法送 key 的工具會 401。
4. 外觀與行為變更：排序、圖片不再放大、Modern 版面成為預設、自訂主題、`.ogg`、symlink（§4.1）。
5. 系統需求：armhf 在 10.11 就沒有官方建置，12 沒有新增 CPU 架構門檻；FFmpeg 換成 8.1，官方文件沒有為 12.x 提高驅動門檻（§4.6）。
6. Docker 的舊環境變數 `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` 會讓 12 啟動崩潰，要拿掉（#17921）。
7. 內建 TLS 的移除延後，12.x 仍可用（§4.1）。

## 5. 對 Berth 的影響

先要做的決定：**Berth 支援哪些 Jellyfin 版本。** 套件內的 `lscr.io/linuxserver/jellyfin:latest` 已經是 12.1，所以「套件內 = 12.x」是現實；
「既有 Jellyfin」可能還是 10.10 / 10.11。下面的「必改」不論怎麼決定都成立；標「依版本決定」的，做法取決於要不要繼續支援 10.x。

### 5.1 必改

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

### 5.2 建議

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

### 5.3 不用改

- **驗證標頭**：`Authorization: MediaBrowser Client=…, Token="…"` 在 12.0 / 12.1 照常可用，被關掉的是舊式寫法（§1.5）。
- **Berth 用到的端點**：24 支在 12.0 / 12.1 都在、授權政策相同，Berth 的 adapter 整段跑通（§1.4）；plan §9.4 既有的四個細節（先 `GET /Startup/User`、`LibraryOptions` 包一層、`/Auth/Keys` 不回 key 也不去重、重啟後輪詢管理員端點）在 12.x 依然成立。
- **命名模板**：`berth/naming/__init__.py` 的劇集、電影、字幕模板在 12.x 不用改就能正確合併，外掛字幕掛在正確的版本上（§2.3）。
- **入庫後的反查**：`items()` 以媒體庫為 parent 並比對 `MediaSources[].Path`，在原生多版本下拿得到每個版本（§2.3）。
- **路徑通知**：已有內容的媒體庫，新版本在 100 秒內出現；「空的媒體庫通知無效」的後備（`SCAN_AFTER_MISSES`）仍然需要，`FileRefresher` 沒改（§1.3）。
- **MergeVersions 的安裝序列本身**（如果依 §5.2 第 1 點保留給 10.x）：不指定版本會自動挑對 `targetAbi` 的版本，任務 `Key` 不變（§1.6、§3.3）。
- 深連結、圖片、`/Items` 會靜默忽略未知參數等 M1.5 的結論：本輪沒有碰，`library-browsing.md` 已是對 12.0.0 查的。

## 6. 摘要

- **12.0 就是本來的 10.12**：拿掉版號前的 `10`；可從 10.10.7 / 10.11.x 直接升，降不回去；第三方插件要重建（.NET 10）；舊式驗證預設關閉。【文件 + 原始碼】
- **劇集原生多版本**：12.0 起，同一季資料夾裡解析出同一個 `S/E` 的檔案就是同一集的版本，不需要 ` - ` 後綴或子資料夾；鍵不含集名與結束集。
  Berth 現行命名在 12.0.0 與 12.1.0 **沒有插件就合併成 1 個 Episode、多個 MediaSources**，版本標籤變成「去掉共同前綴」的部分。【實測 + 原始碼 + 文件】
- **MergeVersions**：有 `12.0.0`（`targetAbi 12.0`），真環境已裝且 Active；12.x 上對 Berth 的樹是空跑，不需要，也不建議裝；10.10 / 10.11 仍需要。【實測 + 原始碼】
- **必改**：多版本相關的事實（brief、PRODUCT、README）、劇集版本標籤的預覽、精靈第 3 步重試遇到 403。**建議**：依版本拿掉插件流程、寫明支援版本、釘 image 大版本線、多集檔衝突的規則。
