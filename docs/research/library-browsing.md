# 媒體庫瀏覽所需的 Jellyfin API 查證（M1.5 前置，plan §11.2b）

2026-09-15。回答「Berth 的媒體庫頁像 Jellyfin 那樣瀏覽，但**不保存使用者 token、只用一把伺服器 API key**」
這個前提下，每一個功能能不能做、怎麼做、有什麼風險。2026-09-17 M1.5 票 01 在 12.1.0 上以受限使用者補測
第 2 節的權限表、第 3 節的過濾與排序、第 5 節的標記遞迴與停用帳號，並新增第 10 節（由 TMDB id 找作品）與
第 11 節（12.1.0 與 12.0.0 的比對）。

## 0. 環境、方法與寫入紀錄

- **12.1.0 實測（票 01，2026-09-17）**：`scripts/experiments/jellyfin_permissions.py` 起一次性的
  `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`（`/System/Info` 回 `12.1.0`，就是 `deploy/` 釘的那一個），
  全新的 `/config` 與 dummy 媒體樹（這次以 `--workdir` 放在 session 的 scratchpad，預設是系統暫存目錄下的新目錄），
  跑完連容器與工作目錄一起刪。三個媒體庫：**TV**（4 部劇，
  其中 Hotel Show 沒有 TMDB id）、**Movies**（3 部電影）、**Anime**（2 部劇，其中《Frieren》與 TV 那一份同一個
  TMDB id 209867）。一個管理員，一個一般使用者 `limited`：`EnableAllFolders=false`、`EnabledFolders=[TV, Movies]`，
  **Anime 是他沒有權限的媒體庫**。metadata 全部來自 NFO（網路 fetcher 關掉），類型、年份、評分、分級、片長刻意排成
  彼此不同的順序；觀看紀錄在縮權之前用 API key 寫入（兩部看過第一集、兩集看到一半，其中一集在 Anime）。
  票面寫「兩個媒體庫」，多一個電影庫是為了 `includeItemTypes=Movie`、電影的排序鍵與由 TMDB id 找電影。
  原始 JSON 在 `.local/experiments/results/jellyfin-permissions.json`（不進版控），契約測試用的回應錄在
  `tests/fixtures/http/jellyfin/`（該目錄 README 的 2026-09-17 那一段）。標記【實測 12.1.0】。

- **實測環境**：票 13 驗收環境的 `lscr.io/linuxserver/jellyfin:latest`，`/System/Info/Public` 回
  `Version: 12.0.0`，`localhost:8096`。API key 從 berth 容器的 `/config/berth.db` 以唯讀方式
  （`sqlite3.connect("file:...?mode=ro", uri=True)`）讀 `settings.services.jellyfin.api_key`。
  伺服器上只有一個使用者 `skipper`（`IsAdministrator=true`、`EnableAllFolders=true`），三個媒體庫
  Anime / Movies / TV，兩部劇（葬送的芙莉蓮 39 集、大熊餐廳 10 集）與一部電影。
- **一次性實驗容器**：第 4 節的「第一次掃描後回 0」重現，另起一個 `berth-research-jf12`
  （同一個 12.0.0 image、scratchpad 裡全新的 `/config` 與 dummy 媒體樹、port 18296），跑完即
  `docker rm -f`。沒有碰原本的任何容器。
- **原始碼對照**：`github.com/jellyfin/jellyfin` 的 tag **`v10.10.7`**、**`v10.11.11`**、**`v12.0`**
  （沒有 `v12.0.0` 這個 tag）。jellyfin-web 對照 `v10.10.7`、`v10.11.11` 與 master `f0f7b226`
  （master 已在 v12.1 之後，只當「12.x 的慣例」看）。
- **標記**：【實測 12.0.0】= 對真伺服器打過；【原始碼】= 讀過三個 tag 的程式碼（附行號的是本文作者親自讀的
  v12.0 檔案，其餘由研究子代理逐檔比對）；【未查】= 查不到或沒做。**10.10 與 10.11 沒有任何實測**，
  兩者的結論全部來自原始碼。
- **對 Jellyfin 的寫入（只有第 5 節）**：項目 `0ee15e70738cc8dbf131ee7acd6e09ac`
  （大熊餐廳 S03E01「翌日」）。開始時 `Played=false, PlayCount=0`、無 `LastPlayedDate`。
  新路徑 POST → DELETE 一輪、舊路徑 POST → DELETE 一輪，另有一次不帶 `userId` 的 POST 回 400 沒有寫入。
  **結束時讀回 `Played=false, PlayCount=0, PlaybackPositionTicks=0`、無 `LastPlayedDate`，與開始時相同。**
  其他寫入（Berth 資料庫、Jellyfin 設定、掃描、刪除）一律沒做；原環境沒有觸發掃描。
- brief 裡「10.11 第一次掃描後 `parentId=<seriesId>` 回 0」這一條實際記在 **§20.1 的 API 段**與
  `m0-experiments.md` §1.7，不在 §20.7。

## 1. API key 代讀某使用者的繼續觀看、下一集、UserData

**結論：三個版本都可以。** API key 在驗證層一律被當成 Administrator，因此帶任何存在的 `userId`
都會通過；不帶 `userId` 時各端點行為不同（見下）。

### 1.1 為什麼可以【原始碼】

- `CustomAuthenticationHandler.HandleAuthenticateAsync`（三版一致）：
  `if (authorizationInfo.IsApiKey || authorizationInfo.User.HasPermission(PermissionKind.IsAdministrator)) role = UserRoles.Administrator;`
  —— [v10.10.7](https://github.com/jellyfin/jellyfin/blob/v10.10.7/Jellyfin.Api/Auth/CustomAuthenticationHandler.cs)、
  [v10.11.11](https://github.com/jellyfin/jellyfin/blob/v10.11.11/Jellyfin.Api/Auth/CustomAuthenticationHandler.cs)、
  [v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Auth/CustomAuthenticationHandler.cs)
- `AuthorizationContext`：API key 分支只設 `IsApiKey`，不設 `User` / `UserId`（三版一致）。
- `RequestHelpers.GetUserId(claims, userId)`（三版逐字相同）：`userId` 為空就回呼叫者自己的 id
  （API key 時是 `Guid.Empty`）；有給且不是自己時，**只要是 Administrator 就放行**，不檢查任何代表關係。
  —— [v12.0 RequestHelpers.cs](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Helpers/RequestHelpers.cs)

### 1.2 端點與實測【實測 12.0.0】

| 呼叫（API key） | 結果 |
| --- | --- |
| `GET /UserItems/Resume?userId=U&limit=5` | 200，3 筆，第一筆 Episode 帶 `UserData.PlaybackPositionTicks=1978440770, PlayedPercentage=59.95, LastPlayedDate` |
| `GET /UserItems/Resume`（不帶 userId） | **400** `Error processing request.` |
| `GET /UserItems/Resume?userId=<不存在>` | **404** |
| `GET /Users/U/Items/Resume`（舊路徑） | 200，與新路徑相同 |
| `GET /UserItems/Resume?userId=U&mediaTypes=Video` | 200，**只剩 1 筆 Episode** |
| `GET /Shows/NextUp?userId=U&limit=5` | 200，1 筆（芙莉蓮 S01E01「冒險結束」） |
| `GET /Shows/NextUp`（不帶 userId） | **400** |
| `GET /Items/Latest?userId=U&parentId=<Anime>` | 200，預設 `groupItems=true` 收成 Series；`groupItems=false` 回個別 Episode |
| `GET /Items?recursive=true&includeItemTypes=Series&enableUserData=true`（不帶 userId） | 200，**沒有 `UserData`**（`user` 為 null） |
| `GET /Items?userId=U&...&enableUserData=true` | 200，Series 帶 `UserData{PlayedPercentage, UnplayedItemCount, Played, PlayCount, IsFavorite, PlaybackPositionTicks}` |
| `GET /UserItems/{id}/UserData?userId=U` | 200，只回 `UserItemDataDto` |
| `GET /Items/{id}?userId=U`、`GET /Users/U/Items/{id}` | 200，完整 DTO 含 `UserData` |

注意事項：

- **`/UserItems/Resume` 不帶 `mediaTypes` 會混進 Season 與 Series**（實測：「Specials」季與「葬送的芙莉蓮」
  劇各一筆，`MediaType=Unknown`）。jellyfin-web 固定帶 `MediaTypes=Video`（第 7 節），Berth 也要帶。
- `UserData` 欄位不是每筆都有：`PlayedPercentage` 只在看到一半或 folder（Series / Season）出現；
  `UnplayedItemCount` 只在 folder；`LastPlayedDate` 只在看過之後。缺欄位要當 0 / null 處理。
- 舊路徑 `/Users/{userId}/Items/*`、`/Users/{userId}/PlayedItems/*` 在三版都還在（`[Obsolete]`），
  12.0.0 伺服器照樣回 200，但 **12.0.0 的 OpenAPI（`/api-docs/openapi.json`）已不列出它們**。
  新路徑 `/UserItems/Resume`、`/Items/Latest?userId=`、`/UserPlayedItems/{id}` 三版都有 → Berth 用新路徑。

### 1.3 版本差異【原始碼】

- `GET /UserItems/Resume` 參數三版相同：`userId, startIndex, limit, searchTerm, parentId, fields, mediaTypes,
  enableUserData, imageTypeLimit, enableImageTypes, excludeItemTypes, includeItemTypes,
  enableTotalRecordCount, enableImages, excludeActiveSessions`。
- `GET /Shows/NextUp`：`userId, startIndex, limit, fields, seriesId, parentId, enableImages, imageTypeLimit,
  enableImageTypes, enableUserData, nextUpDateCutoff, enableTotalRecordCount, enableResumable, enableRewatching`
  三版都有；**`disableFirstEpisode` 在 v12.0 被移除**（10.10.7 / 10.11.11 有）。多送的查詢參數 ASP.NET
  會忽略，所以送了也不會錯，但在 12.0 沒有效果。
  —— [TvShowsController v10.10.7](https://github.com/jellyfin/jellyfin/blob/v10.10.7/Jellyfin.Api/Controllers/TvShowsController.cs)、
  [v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/TvShowsController.cs)

## 2. API key 代讀時會不會套用該使用者的媒體庫權限

**結論：只有一部分會。研究原本推論的每一列在 12.1.0 上都成立。** 另外量了六列研究沒列的（下表標【新】）：
劇或季當 `parentId` 是洩漏，不帶 `parentId` 的 Filters 回空清單是陷阱，其餘三列有擋。Jellyfin 的權限分兩層：

1. **家長分級與標籤**（`MaxParentalRating`、`BlockUnratedItems`、`BlockedTags`、`AllowedTags`）：
   只要查詢帶了 `userId`，`new InternalItemsQuery(user)` 就會 `SetUser(user)` 套用，**三版一致、與憑證種類無關**。
   不帶 `userId` 則完全不套。【原始碼，沒有實測】
2. **媒體庫存取**（`EnableAllFolders` / `EnabledFolders` / `BlockedMediaFolders`）：看**端點與參數**，
   而且有幾條路是 API key 特別放行的。**這是 Berth 的安全邊界問題，下表的 ✘ 必須由 Berth 自己擋。**

**量法**【實測 12.1.0】（環境見第 0 節）：每一列用 API key 帶受限使用者的 `userId` 打一次，再用受限使用者自己的
token（同樣帶自己的 `userId`）打一次。✔ = 回應裡沒有任何屬於 Anime 的項目（本身、所屬的劇、季或上層）；
✘ = 有；類型 / 年份 / 分級清單以只存在於 Anime 的 `Mecha`、`2019`、`TV-Y7` 判定。原始碼依據的行號是 v12.0，
10.10.7 / 10.11.11 的同一段以 grep 比對過結構相同（`!isApiKey` 分支、`AddUserToQuery` 的條件、Resume 的
`ParentId = parentIdGuid`、NextUp 的 `GetUserRootFolder().GetChildren(user, true)`）。

| 呼叫（`userId=U`） | 研究推論 | API key 實測 | 使用者 token 實測 | 原始碼依據 |
| --- | --- | --- | --- | --- |
| `GET /UserViews?userId=U` | ✔ | ✔ 200，2 筆（TV、Movies） | 同左 | `UserViewManager`；這是**權威清單** |
| `GET /Items?userId=U&recursive=true`（**不帶** `parentId` / `ids`） | ✔ | ✔ 200，7 筆（`includeItemTypes=Series,Movie`），沒有 Anime 的兩部 | 同左 | `LibraryManager.AddUserToQuery` 在沒有 `ParentId`、`AncestorIds`、`ItemIds`、`TopParentIds` 時，把 `TopParentIds` 設成 U 的 UserViews（[L2080-2111](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/LibraryManager.cs#L2080-L2111)） |
| `GET /Items?userId=U&parentId=<無權的媒體庫>` | ✘ | **✘ 200，10 筆**（Anime 的 2 劇、2 季、5 集與一個 `Folder`） | 401 `limited is not permitted to access Library Anime.` | `ItemsController.GetItems` 的可見性檢查寫成 `item is not UserRootFolder && !isApiKey && !item.IsVisible(user)`，**API key 直接跳過**（[L342-350](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/ItemsController.cs#L342-L350)）；帶 `ParentId` 時 `AddUserToQuery` 不設 `TopParentIds`，遞迴查詢直接進 `GetItemsResult`，只有 BoxSet / Playlist 才走 `QueryWithPostFiltering`（[Folder.cs L919-942](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/Folder.cs#L919-L942)） |
| 【新】`GET /Items?userId=U&parentId=<無權的劇>` | 未列 | **✘ 200，3 筆**（季與兩集） | **✘ 200，3 筆** | 使用者 token 也擋不住：上一列那道可見性檢查只擋得下媒體庫（原因沒有再讀原始碼） |
| 【新】`GET /Items?userId=U&parentId=<無權的季>` | 未列 | **✘ 200，2 筆**（兩集） | **✘ 200，2 筆** | 同上。**劇或季當 `parentId` 一律不安全** |
| `GET /Items?userId=U&ids=<無權的項目>` | ✘ | **✘ 200，1 筆** | **✘ 200，1 筆** | `ItemIds` 非空時 `AddUserToQuery` 不限縮，`Folder.GetItems` 的 `ItemIds` 分支直接 `GetItemsResult`（[Folder.cs L996-1011](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/Folder.cs#L996-L1011)） |
| `GET /Items/{無權的項目}?userId=U` | ✔ 404 | ✔ 404（problem details JSON） | 同左 | `GetItemById<BaseItem>(itemId, user)` → `ItemIsVisible` → `IsVisibleStandalone(user)`，後者檢查 `EnabledFolders` / `BlockedMediaFolders`（[UserLibraryController L84-108](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/UserLibraryController.cs#L84-L108)、[LibraryManager L1723-1728, L4060-4073](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/LibraryManager.cs#L4060-L4073)、[BaseItem L1512-1566](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/BaseItem.cs#L1512-L1566)） |
| `GET /UserItems/Resume?userId=U&mediaTypes=Video`（不帶 `parentId`） | ✔ | ✔ 200，2 筆（TV 的一集、Movies 的一部）；Anime 看到一半的那集不在 | 同左 | 走 `GetItemsResult` → `AddUserToQuery` |
| `GET /UserItems/Resume?userId=U&parentId=<無權的媒體庫>` | ✘ | **✘ 200，1 筆**（Anime 看到一半的那集） | **✘ 200，1 筆** | 直接 `ParentId = parentIdGuid`，沒有任何可見性檢查（[ItemsController L940-989](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/ItemsController.cs#L940-L989)） |
| `GET /Shows/NextUp?userId=U`（不帶 `parentId` / `seriesId`） | ✔ | ✔ 200，2 筆（TV 兩部劇的下一集）；Anime 那部不在 | 同左 | `parents = GetUserRootFolder().GetChildren(user, true)`（[TVSeriesManager L54-77](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/TV/TVSeriesManager.cs#L54-L77)） |
| `GET /Shows/NextUp?userId=U&parentId=<無權的媒體庫>` 或 `&seriesId=<無權的劇>` | ✘ | **✘ 200，各 1 筆** | **✘ 200，各 1 筆** | `GetItemById(id)` 沒帶 user |
| `GET /Shows/{無權的劇}/Seasons?userId=U`、`/Episodes?userId=U[&seasonId=]` | ✔ 404 | ✔ 404。Seasons 是 problem details；Episodes 是 JSON 字串 `"Series not found"`，帶 `seasonId` 時是 `"No season exists with Id …"` | 同左 | `GetItemById<Series>(seriesId, user)`、`GetItemById<BaseItem>(seasonId, user)`（[TvShowsController L235-261, L351](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/TvShowsController.cs#L235-L261)） |
| `POST` / `DELETE /UserPlayedItems/{無權的集}?userId=U` | ✔ 404 | ✔ 404；`POST` 之後立刻讀回（用不檢查權限的 `ids=`）仍是 `Played=false, PlayCount=0`，沒有寫入 | 同左 | `GetItemById<BaseItem>(itemId, user)`（[PlaystateController L81-88, L147-154](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/PlaystateController.cs#L81-L88)） |
| 【新】`GET /UserItems/{無權的集}/UserData?userId=U` | 未列 | ✔ 404 | 同左 | — |
| `GET /Genres`、`/Years`、`/Items/Filters` 帶 `parentId=<無權的媒體庫>` | ✘ | **✘ 200**：`/Genres` 3 個（含 `Mecha`）、`/Years` 2 個（含 `2019`）；Filters 的類型含 `Mecha`、年份含 `2019`、分級含 `TV-Y7` | **✘** 同左 | `GetParentItem(parentId, userId)` 只是 `GetItemById(parentId)`，不看 user（[LibraryManager L3251-3264](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/LibraryManager.cs#L3251-L3264)） |
| `GET /Items/Filters2` 帶 `parentId=<無權的媒體庫>` | ✘ | **✘ 200**，類型含 `Mecha`（Filters2 沒有年份與分級） | **✘** 同左 | `GetItemById<BaseItem>(parentId.Value)` 不帶 user（FilterController L140） |
| 【新】`GET /Items/Filters?userId=U`（不帶 `parentId`） | 未列 | 200，**四份清單全空**——不是過濾，是不帶 `parentId` 就什麼都不回 | 同左 | — |
| 【新】`GET /Genres?userId=U`（不帶 `parentId`） | 未列 | ✔ 200，7 個，沒有 `Mecha` | 同左 | — |
| `GET /Items/Latest?userId=U`（不帶 `parentId`） | 【未查】 | ✔ 200，5 筆，沒有 Anime | 同左 | — |
| `GET /Items/Latest?userId=U&parentId=<無權的媒體庫>` | 【未查】 | **✘ 200，2 筆** | **✘ 200，2 筆** | — |
| 圖片 `GET /Items/{無權的項目}/Images/Primary` | 無任何權限 | 匿名 200 | — | 第 6 節 |

其他：

- **不帶 `userId` 的 API key 讀取**：`/Items` 回整台伺服器的內容、沒有任何使用者限制（12.0.0 實測 Series /
  Season / Episode / Movie 數與帶管理員 `userId` 時相同）。12.1.0 另外量到【新】：**`/Shows/{無權的劇}/Seasons` 與
  `/Episodes` 不帶 `userId` 回 200 並照樣列出**（沒有 user 就沒有權限可套，而且不報錯），`/Items/{id}` 不帶則回 **400**，
  Resume、NextUp、`POST /UserPlayedItems` 回 400 且沒有寫入。【實測 12.1.0】
- **停用的 Jellyfin 帳號**【實測 12.1.0】：`Policy.IsDisabled=true` 之後，API key 代讀這位使用者的 `UserViews`（2 筆）、
  `/Items`（不帶與帶 `parentId=TV`）、Resume、NextUp、`/Items/{id}`、Seasons **全部照常回 200 與資料**，`POST` /
  `DELETE /UserPlayedItems` 也照常寫入。只有使用者自己這一側被擋：停用前發給他的 token 回 **401**，重新
  `AuthenticateByName` 回 **403**。`GET /Users/{id}`（API key）讀得到 `Policy.IsDisabled`、`EnableAllFolders`、
  `EnabledFolders`（fixture `users.restricted.disabled.json`）；`EnabledFolders` 與 `UserViews` 的 `Id`、
  `/Library/VirtualFolders` 的 `ItemId` 是同一種格式（32 個十六進位字、沒有連字號），可以直接比。縮權也是立即
  生效：改完 policy 馬上打 `UserViews` 就只剩兩個。Berth 的 session 活 30 天且不重新向 Jellyfin 驗證
  （plan §2.1），所以停用與縮權都要 Berth 自己去讀（brief §19 的決定）。
- `/Items` 的**未知查詢參數會被靜默忽略**：12.0.0 實測 `GET /Items?userId=U&seriesId=<S>&recursive=true&includeItemTypes=Episode`
  與 `ancestorIds=<S>` 都回 **整台伺服器的 49 集**（`/Items` 沒有這兩個參數）；12.1.0 重測同樣回全部 10 集，
  打錯字的 `genre=Drama`、`year=2022` 也一樣回全部 7 筆。任何「以為有在過濾」的參數打錯字，就會變成把全部內容交出去。

## 3. 媒體庫內瀏覽：排序、篩選、類型與年份清單

### 3.1 `/Items` 的排序與篩選【實測 12.0.0 + 實測 12.1.0 + 原始碼】

- `sortBy`（逗號分隔，多鍵）＋ `sortOrder`（`Ascending` / `Descending`，可逗號對應每個鍵）。`ItemSortBy`
  在 10.11.11 與 v12.0 完全相同：`Default, AiredEpisodeOrder, Album, AlbumArtist, Artist, DateCreated,
  OfficialRating, DatePlayed, PremiereDate, StartDate, SortName, Name, Random, Runtime, CommunityRating,
  ProductionYear, PlayCount, CriticRating, IsFolder, IsUnplayed, IsPlayed, SeriesSortName, VideoBitRate,
  AirTime, Studio, IsFavoriteOrLiked, DateLastContentAdded, SeriesDatePlayed, ParentIndexNumber, IndexNumber`；
  10.10.7 另多 `SimilarityScore`、`SearchScore`（10.11 移除）。
  —— `Jellyfin.Data/Enums/ItemSortBy.cs` 三個 tag
- 實測 `SortName`、`ProductionYear,SortName`、`DateCreated`、`CommunityRating`、`PremiereDate`、`DatePlayed`、
  `Random`、`DateLastContentAdded` 都回 200 且順序符合。**劇集的「最近更新」用 `DateLastContentAdded`，
  「最近看過」用 `SeriesDatePlayed`**（jellyfin-web 劇集庫的慣例，第 7 節）。
- 篩選參數（10.11.11 / v12.0 原始碼確認分隔符；10.10.7 由子代理比對參數相同）：
  - `genres`、`officialRatings`、`tags`：**`|` 分隔**（`PipeDelimitedCollectionModelBinder`，類型名可能含逗號）
  - `genreIds`、`years`、`ids`、`filters`、`includeItemTypes`：逗號分隔
  - `filters`：`IsFolder, IsNotFolder, IsUnplayed, IsPlayed, IsFavorite, IsResumable, Likes, Dislikes, IsFavoriteOrLikes`；
    另有獨立布林 `isPlayed`、`isFavorite`
  - 實測：`genres=剧情` 3 筆、`genres=动画` 1 筆、`years=2023` 2 筆、`years=2022,2023` 3 筆、
    `genreIds=<剧情 id>` 3 筆、`filters=IsUnplayed` 3 筆、`filters=IsPlayed` 0 筆、`parentId=<Anime>` 1 筆
- 分頁：`startIndex` + `limit` + `enableTotalRecordCount=true`；實測 `startIndex=10&limit=3` 回
  `TotalRecordCount=39, StartIndex=10`。

**12.1.0 逐一驗「伺服器真的有過濾 / 排序」**（M1.5 票 01；API key + 受限使用者的 `userId`，只看得到 TV 與 Movies）。
過濾的判準是「結果等於照 NFO 算出來的預期，而且和拿掉這個參數的對照查詢不同」；排序的判準是升冪與降冪各自照
DTO 上的那個值單調、兩者順序不同：

| 參數 | 結果（對照） | 判定 |
| --- | --- | --- |
| `parentId=<TV 媒體庫>`（`includeItemTypes=Series,Movie`） | 4 部劇（對照 7） | 有過濾 |
| `parentId=<劇>&includeItemTypes=Episode` | 那部劇的 5 集（對照 10） | 有過濾（但見第 2 節：劇當 parent 不套權限） |
| `parentId=<季>&includeItemTypes=Episode` | 那一季的 3 集（對照 10） | 有過濾（同上） |
| `includeItemTypes=Series` / `Movie` | 4 部劇 / 3 部電影（不帶時 24 筆，含季與集） | 有過濾 |
| `genres=Drama` / `genres=Drama\|Comedy` | 2 / 3 筆，跨劇與電影（對照 7） | 有過濾，`\|` 是「或」 |
| `years=2022` / `years=2018,2020` | 1 / 2 筆 | 有過濾，逗號是「或」 |
| `genres=Science Fiction&years=2024` | 1 筆 | 兩個參數之間是「且」 |
| `genres=Mecha`、`years=2019`（只在沒權限的 Anime） | 0 筆 | 不帶 `parentId` 時有照權限過濾 |
| 對照：`genre=Drama`、`year=2022`（少一個 s） | 7 筆，與對照相同 | **被靜默忽略** |
| `sortBy=SortName&startIndex=2&limit=3` | 恰好是整份排序結果的第 3–5 筆；`TotalRecordCount=7`（整份的數）、`StartIndex=2` | 分頁正確 |

排序鍵（每個鍵後面接 `,SortName`，jellyfin-web 的寫法）：

- **劇集庫**：`SortName`、`CommunityRating`、`PremiereDate`、`ProductionYear`、`DateLastContentAdded`、
  `SeriesDatePlayed` 都照值排序；`OfficialRating` 升降冪互為反序；`Random` 不判定。
- **電影庫**：`SortName`、`CommunityRating`、`CriticRating`、`PremiereDate`、`ProductionYear`、`DateCreated`、
  `PlayCount`、`Runtime` 都照值排序；`OfficialRating` 升降冪互為反序。
- **沒有值的排在升冪最前、降冪最後**：沒有評分的劇在 `CommunityRating` 升冪排第一；從沒看過的劇在
  `SeriesDatePlayed` 升冪排前面。「最近看過」要用降冪。
- **`OfficialRating` 照分級高低排，不是照字串**：劇集庫升冪是 `TV-G < TV-PG < TV-14 < TV-MA`，字串順序會是
  `TV-14, TV-G, TV-MA, TV-PG`。電影庫的 `PG < PG-13 < R` 剛好也是字串順序，證明不了。腳本只自動判「升降冪互為反序」，
  高低順序是看報告裡的值得出的。
- **劇的 `DateCreated` 是 Jellyfin 掃描時寫入的時間**，不是資料夾的時間（這次四部劇的值相差幾毫秒、順序剛好等於
  名稱順序，所以劇集庫的 `DateCreated` 證明不了是照它排的；電影庫那一列證明了）。電影的 `DateCreated` 是檔案時間。
  `DateLastContentAdded` 對應 DTO 的 `DateLastMediaAdded`（要在 `fields` 裡要），是最新那一集的檔案時間。
- `SortName` 是小寫化的名稱；`SeriesDatePlayed` 在 DTO 上沒有對應欄位，拿觀看紀錄的日期比對。

### 3.2 取某媒體庫可用的類型與年份

| 端點 | 三版 | 回傳 | 實測 12.0.0 |
| --- | --- | --- | --- |
| `GET /Items/Filters?userId&parentId&includeItemTypes&mediaTypes` | 都有（`GetQueryFiltersLegacy`） | `{Genres: string[], Tags: string[], OfficialRatings: string[], Years: int[]}` | Anime：`Genres` 4 個、`Tags` 30 個、`OfficialRatings ["TW-6+"]`、`Years [2023]`。**12.1.0**：形狀相同（fixture `items-filters.tv.json`）；**不帶 `parentId` 四份清單全空** |
| `GET /Items/Filters2?userId&parentId&includeItemTypes&isAiring&isMovie&isSports&isKids&isNews&isSeries&recursive` | 都有 | 10.10.7 / 10.11.11：`{Genres: NameGuidPair[], Tags: string[]}`；**v12.0 多 `AudioLanguages`、`SubtitleLanguages`**；**三版都沒有 Years / OfficialRatings** | Anime：`Genres` 帶 `Id`，但 **`Tags: []`**（同一庫 Filters 有 30 個）。12.1.0 的鍵是 `AudioLanguages, Genres, SubtitleLanguages, Tags` |
| `GET /Genres?userId&parentId&includeItemTypes&sortBy...` | 都有 | `BaseItemDto[]`（Type=Genre，有 `Id`、可取圖） | TV 回「剧情、喜剧」 |
| `GET /Years?userId&parentId&recursive&includeItemTypes&sortBy&sortOrder` | 都有 | `BaseItemDto[]`（Name 是年份） | **TV 庫不帶 `includeItemTypes` 回 `["2024","2022"]`**——2024 來自集的播出年；帶 `includeItemTypes=Series` 才是 `["2022"]` |

來源：[FilterController v10.10.7](https://github.com/jellyfin/jellyfin/blob/v10.10.7/Jellyfin.Api/Controllers/FilterController.cs)、
[v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/FilterController.cs)、
`MediaBrowser.Model/Querying/QueryFilters.cs` 與 `QueryFiltersLegacy.cs` 三個 tag。

**建議**：類型 / 年份清單用 `GET /Items/Filters?userId=U&parentId=<已驗證的庫>&includeItemTypes=Series`
（或 `Movie`）——三版回傳形狀一致、一次拿到類型與年份，也是 jellyfin-web 篩選面板用的那一支。`parentId` 一定要帶
（不帶就是空的），而且一定要先對 `UserViews` 驗過（帶了就不套權限，第 2 節）。
要用 `genreIds` 篩選才需要 `Filters2` 或 `/Genres` 的 `Id`；用 `genres=`（名稱、`|` 分隔）就不需要。

## 4. 選季選集

### 4.1 查法【實測 12.0.0】

jellyfin-web 的詳細頁（第 7 節）：

```
GET /Shows/{seriesId}/Seasons?userId=U&fields=ItemCounts,PrimaryImageAspectRatio
GET /Shows/{seriesId}/Episodes?userId=U&seasonId={seasonId}&fields=Overview,PrimaryImageAspectRatio
```

實測（主環境，大熊餐廳、芙莉蓮）：

- `Seasons` 回每季的 `Id, Name, IndexNumber, ImageTags.Primary, UserData{UnplayedItemCount, PlayedPercentage, Played}`。
- `Episodes?seasonId=` 與 `Items?parentId=<seasonId>` 數量一致（Specials 11、第 1 季 28、大熊第 3 季 10）。
- 每集 DTO（不用額外 `fields`）就有 `Id, Name, IndexNumber, ParentIndexNumber, SeriesId, SeasonId, SeasonName,
  RunTimeTicks, PremiereDate, CommunityRating, UserData, ImageTags.Primary`（集劇照）、
  `ParentThumbItemId / ParentThumbImageTag`、`ParentBackdropItemId / ParentBackdropImageTags`、
  `SeriesPrimaryImageTag`、`ImageBlurHashes`。`Overview` 要在 `fields` 裡要。
- 參數（三版相同，12.0.0 OpenAPI）：`Episodes`：`seriesId, userId, fields, season, seasonId, isMissing,
  adjacentTo, startItemId, startIndex, limit, enableImages, imageTypeLimit, enableImageTypes, enableUserData, sortBy`；
  `Seasons`：`seriesId, userId, fields, isSpecialSeason, isMissing, adjacentTo, enableImages, imageTypeLimit,
  enableImageTypes, enableUserData`。
- 這兩支會套用使用者的媒體庫權限（第 2 節 ✔），是本文唯一「用 API key 代讀也安全」的季集查法。

### 4.2 「第一次掃描後回 0」在 12.0.0 上【實測 12.0.0，一次性容器】

做法：全新的 12.0.0（`berth-research-jf12`，初始精靈 → 建 `tvshows` 媒體庫，預設 TMDB fetcher），dummy 媒體樹：
`Berth Test Show (2020) [tmdbid-1399]`（S01E01-03、S02E01、S00E01）、`Frieren Beyond Journey's End (2023) [tmdbid-209867]`
（S01E01-02）、TMDB 對不上的 `Qwxzyv Berth Probe (2099)`（S01E01-02）。用 `RefreshLibrary` 排程任務掃描
（107 秒，18 個 item），在「掃完當下」「掃完 120 秒、不重掃」「第二次掃描後」各量一次。
腳本：scratchpad 的 `repro_first_scan.py`（未進版控，量法同 `scripts/experiments/jellyfin_naming.py` 的
`series_child_query`，另加季層查法）。

| 查法 | 權力遊戲（TMDB 認出） | 芙莉蓮（TMDB 認出） | Probe（未認出） |
| --- | --- | --- | --- |
| `/Items?parentId=<library>&recursive=true` 照 `Path` 前綴 | 5 / 5 / 5 | 2 / 2 / 2 | 2 / 2 / 2 |
| 同上照 `SeriesId` 欄位 | 5 / 5 / 5 | 2 / 2 / 2 | 2 / 2 / 2 |
| `/Items?parentId=<seriesId>&recursive=true&includeItemTypes=Episode` | 5 / 5 / 5 | 2 / 2 / 2 | 2 / 2 / 2 |
| `/Shows/{id}/Episodes` | 5 / 5 / 5 | 2 / 2 / 2 | 2 / 2 / 2 |
| `/Shows/{id}/Seasons` | 3 / 3 / 3 | 1 / 1 / 1 | 1 / 1 / 1 |
| 每季 `/Items?parentId=<seasonId>` 與 `/Shows/{id}/Episodes?seasonId=` | 全對（3 / 1 / 1） | 全對（2） | 全對（2） |

（每格依序是：掃完當下 / 120 秒後 / 第二次掃描後）

**結論：12.0.0 沒有重現。** 限制：只跑一輪；媒體樹比 M0 小（沒有多版本、extras、字幕）；
**10.11 沒有重測**，§20.1 與 `m0-experiments.md` §1.7 的 10.11.11 結果仍然成立。

### 4.3 不受影響的替代查法

- **已在 10.10.7 / 10.11.11 / 12.0.0 都驗過**：`GET /Items?userId=U&parentId=<library>&recursive=true&includeItemTypes=Episode&fields=Path`
  再照 Series 的 `Path` 前綴分群（M0 §1.7 + 本節）。
- **只在 12.0.0 驗過**：同一個查詢照 Episode 的 `SeriesId` / `SeasonId` 欄位分群，不需要 `Path`。10.11 第一次掃描後
  Series 被重建時，集上的 `SeriesId` 會不會指向新的 id【未查】。
- 這兩條都帶 `parentId=<library>`，**API key 下不套用媒體庫權限**（第 2 節），而且要把整個媒體庫的集一次抓回來
  （可用 `sortBy=ParentIndexNumber,IndexNumber` 與分頁）。

## 5. 標記已看 / 未看（API key 代寫）

**結論：三版都可以。** 【實測 12.0.0 + 原始碼】

- `POST /UserPlayedItems/{itemId}?userId=U[&datePlayed=]` → 200，回 `UserItemDataDto`
  （`Played=true, PlayCount=1, LastPlayedDate=<現在>`）。
- `DELETE /UserPlayedItems/{itemId}?userId=U` → 200，回 `Played=false, PlayCount=0`，**`LastPlayedDate` 被移除**。
- 不帶 `userId` → **400**，沒有寫入（讀回確認）。
- 舊路徑 `POST/DELETE /Users/{userId}/PlayedItems/{itemId}` → 200，效果相同；兩條路徑 `GET` 都回
  `405 Allow: DELETE, POST`（路由存在）。
- 原始碼：三版 `PlaystateController` 都是 `GetUserId` → `GetUserById` → `GetItemById<BaseItem>(itemId, user)`
  （項目對該使用者不可見時 404）；**沒有呼叫 `RequestHelpers.AssertCanUpdateUser`**，API key 帶任何 `userId` 都能寫。
  —— [v10.10.7](https://github.com/jellyfin/jellyfin/blob/v10.10.7/Jellyfin.Api/Controllers/PlaystateController.cs)、
  [v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/PlaystateController.cs)
- **對 Series / Season 標記會遞迴到底下的集**【實測 12.1.0】（Jellyfin Web「全部標為已看」就是這支）：
  - `POST /UserPlayedItems/{seriesId}` → 每一集 `Played=true, PlayCount=1, LastPlayedDate=<現在>`，**看到一半的那一集
    `PlaybackPositionTicks` 歸零**（從繼續觀看消失）。回應是 Series 自己的 `UserItemDataDto`：
    `Played=true, PlayedPercentage=100, UnplayedItemCount=0`，但 **`PlayCount=0`**——資料夾的 `PlayCount` 不代表集。
  - `DELETE /UserPlayedItems/{seriesId}` → 每一集 `Played=false, PlayCount=0`、`LastPlayedDate` 消失，**連標記之前就
    單獨看過的集也一起清掉**（Alpha Show 第一集 2026-01-01 的紀錄沒了）。
  - 對 Season 標記只動那一季的集，別季單獨看過的集不動；Series 的 `UnplayedItemCount` / `PlayedPercentage` 跟著重算。
  - 單集的兩個方向的回應錄在 fixture `userplayeditems.{post,delete}.json`：`DELETE` 的回應沒有 `LastPlayedDate` 這個鍵。
  - **兩個方向回的是同一種 DTO**【原始碼 v12.0，M1.5 票 05】：`MarkPlayedItem` 與 `MarkUnplayedItem` 都經
    `UpdatePlayedStatus` 回 `_userDataRepository.GetUserDataDto(item, user)`，所以對 Series 標為未看的回應與上面實測的
    標為已看同一個形狀（帶 `UnplayedItemCount`，Berth 靠它分辨劇集與影片，`services/watch.py`）。Series 那兩個回應沒有錄
    fixture。—— [PlaystateController.cs v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/PlaystateController.cs)
- **「標為未看」不可逆**：`PlayCount` 歸零、`LastPlayedDate` 消失，UI 的「復原」沒辦法恢復原本的觀看次數與時間；
  對整部劇或整季做時，清掉的是底下每一集的紀錄。

## 6. 圖片

**結論：不需要驗證，瀏覽器可以直接載入。** 【實測 12.0.0 + 原始碼】

- 實測（**完全不帶 `Authorization`**）：
  - Series `Primary` / `Backdrop` / `Backdrop/0` / `Thumb` / `Logo`、Season `Primary`、Episode `Primary`（集劇照）都回 **200**。
  - 不存在的 item 回 404，不存在的圖片類型（`Banner`）回 404。
  - 回應帶 `Access-Control-Allow-Origin: *`。12.1.0 實測：**只在請求帶 `Origin` 標頭時才有**（瀏覽器跨來源載入一定會帶）。
  - 帶一個假的 `api_key=` 也照樣 200（被忽略）。
- 縮放參數（三版都有）：`maxWidth, maxHeight, width, height, fillWidth, fillHeight, quality, tag, format,
  blur, backgroundColor, foregroundLayer, percentPlayed, unplayedCount, imageIndex`。實測 `fillWidth=300&quality=90`
  原圖 1.13 MB → 45 KB；`format=Webp` 回 `image/webp`。
- **`tag` 只是快取鍵，不驗證**：帶 `tag` 時回 `Cache-Control: public, max-age=31536000, immutable` 與
  `ETag: "<tag>"`；**錯的 tag 一樣回圖**（ETag 就是那個錯的字串）。不帶 `tag` 只有 `Cache-Control: public`。
  所以 URL 一定要帶 DTO 裡的 `ImageTags.<type>`，圖換了 URL 才會變。
- 原始碼：`ImageController` 的 `GET/HEAD Items/{itemId}/Images/{imageType}[/{imageIndex}]` 三版都沒有 `[Authorize]`；
  寫入類（`POST/DELETE`）是 `RequiresElevation`。12.0.0 OpenAPI 對這幾支 `security=None`。
  —— [v10.10.7](https://github.com/jellyfin/jellyfin/blob/v10.10.7/Jellyfin.Api/Controllers/ImageController.cs)、
  [v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/ImageController.cs)
- jellyfin-web 自己也不帶 token：`Items/{id}/Images/{type}?fillHeight=&fillWidth=&quality=96&tag=`（第 7 節）。
- **瀏覽器直連的前提**是瀏覽器連得到 Jellyfin（與深連結同一個主機，plan §2.1 的 `public_url` 推導）。
  Berth 走 HTTPS 而 Jellyfin 是 HTTP 時會被當成 mixed content（圖片是「可選擇性封鎖」類，多數瀏覽器自動升級或警告）。
  另一條路是 Berth 後端代理圖片。
- 空圖占位：DTO 的 `ImageBlurHashes.<type>.<tag>` 有 BlurHash 字串（實測 Episode 帶 Primary / Logo / Thumb / Backdrop 四種）。
- **12.1.0 重測**（票 01，錄成 fixture `images-primary.{no-tag,tag,resized}.headers.json`）：匿名 200；帶對的 tag 與錯的
  tag 都回 `Cache-Control: public, max-age=31536000, immutable` 與照抄的 `ETag`；不帶 tag 只有 `Cache-Control: public`、
  沒有 `ETag`；`fillWidth=100&quality=90&format=Webp` 回 `image/webp`，`Last-Modified` 是縮圖產生的時間（原圖是檔案時間）；
  沒有的圖片類型 404。回應另帶 `Content-Disposition: attachment`、`Vary: Accept`、`Age` 與 DLNA 的兩個標頭
  （`realTimeInfo.dlna.org`、`transferMode.dlna.org`），代理時要決定哪些轉給瀏覽器。

### 6.1 經 Berth 代理：要不要在 Berth 端另存一份【實測 12.1.0，M1.5 票 04】

`scripts/experiments/jellyfin_images.py`，2026-09-17，一次性的 Jellyfin **12.1.0**（`version-12.1ubu2604`）。
一個電影媒體庫 100 部，每部一張 1000×1500、帶雜訊的 JPEG 海報（486 KB；純色圖只有幾 KB，縮圖大小與時間都會失真）。
直連是 urllib 直接打 Jellyfin；經過 Berth 是另一個程序的 `berth serve`，帶真的 session cookie（門禁、兩次 SQLite、
每張圖一個不帶 token 的 httpx client）。本機 Docker Desktop，數字是量級，不是 NAS 上的值。

**縮圖參數（每種 5 張，單條依序）**

| 查詢 | 回應 | 尺寸 | 大小中位數 | 冷 / 熱中位數 |
| --- | --- | --- | --- | --- |
| `fillWidth=342&fillHeight=513&quality=90&format=Webp` | `image/webp` | 342×513 | 23 KB | 246 / 28 ms |
| 同上，`quality=96`（jellyfin-web 的值） | `image/webp` | 342×513 | 51 KB | 238 / 24 ms |
| 不帶 `format`，`Accept: */*`（Berth 的 httpx） | `image/jpeg` | 342×513 | 33 KB | 211 / 26 ms |
| 不帶 `format`，Chromium 的圖片 `Accept` | `image/webp` | 342×513 | 24 KB | 232 / 25 ms |

- 2:3 的原圖帶 `fillWidth` / `fillHeight` 回的就是 342×513。
- **不帶 `format` 時 Jellyfin 照 `Accept` 挑格式**：Berth 自己的請求拿到 JPEG，大 40%。所以代理固定送 `format=Webp`。
- `quality=96` 是 `quality=90` 的兩倍多大。選 90（研究當時在 12.0.0 量的也是 90）；兩者的畫質沒有做肉眼比較。
- 每一種都回 `Cache-Control: public, max-age=31536000, immutable`（帶了 `tag`）。

**40 張、6 條並行（瀏覽器對同一主機的連線數）**

| | 總時間 | 每張中位數 | p90 |
| --- | --- | --- | --- |
| 直連 Jellyfin，冷（第一次縮） | 2,067 ms | 303 ms | 312 ms |
| 直連 Jellyfin，熱 | 161 ms | 21 ms | 37 ms |
| 經過 Berth，冷 | 2,241 ms | 307 ms | 383 ms |
| 經過 Berth，熱 | 403 ms | 54 ms | 69 ms |
| 經過 Berth，Jellyfin 已被直連那一輪熱過 | 469 ms | 60 ms | 88 ms |
| 經過 Berth，熱——**修正之前**（每個 httpx client 各建一個 SSL context） | 993 ms | 140 ms | 174 ms |

- **Jellyfin 自己存了一份縮好的圖**：跑完後 `/config/cache/images/resized-images` 有 100 個檔、2.6 MB（每張海報在這個
  尺寸一份），同一張第二次從 ~250 ms 掉到 ~25 ms。
- **冷的那一次由 Jellyfin 縮圖主導**（直連與經過 Berth 差 8%），Berth 端另存一份也躲不掉：那一份得先由 Jellyfin 縮出來。
- **熱的時候 Berth 每張多約 35 ms**（門禁讀 session、讀設定、每張圖一條新的 Jellyfin 連線）。Berth 端另存一份最多省下
  Jellyfin 那一段（直連熱 21 ms），門禁與資料庫照樣要走。
- **修正之前每張多 120 ms**：httpx 每個 client 預設各建一個 SSL context（讀 certifi 的憑證包，約 14 ms 的 CPU），而
  CPU 工作卡在事件迴圈上，6 條並行時彼此排隊。`adapters/http.py` 改成整個程序共用一個之後降到上表的值
  （`tests/unit/test_adapters.py` 守著）。

**結論：Berth 端不另存。** Jellyfin 已經在磁碟上存了縮好的圖，冷的那一次存不存都得等它縮；熱的時候另存只省二十幾毫秒，
卻要多一份磁碟、照 `tag` 失效、作品刪掉時清掉的邏輯。每個瀏覽器第一次看到之後，`immutable` 讓重新整理不再發請求
（playwright 實跑，票 04 的 Comments）。大媒體庫在 NAS 上若量到牆明顯慢，先看每張圖的連線（共用 keep-alive）與門禁，
而不是存圖。

## 7. Jellyfin Web 自己用的端點與參數（要沿用的慣例）

【原始碼，研究子代理讀 jellyfin-web；未實測抓網路請求——那需要登入 Jellyfin Web 建立 session，屬於不允許的寫入】

| 區塊 | 端點 | 參數 |
| --- | --- | --- |
| 繼續觀看 | 10.10 / 10.11：`GET /Users/{userId}/Items/Resume`（jellyfin-apiclient `getResumableItems`）；master：`@jellyfin/sdk` 的等價新路徑 | `Limit, Recursive=true, Fields=PrimaryImageAspectRatio, ImageTypeLimit=1, EnableImageTypes=Primary,Backdrop,Thumb, EnableTotalRecordCount=false, MediaTypes=Video`（影片區塊） |
| 下一集 | `GET /Shows/NextUp` | `Limit=15`（overflow 24）`, Fields=PrimaryImageAspectRatio,DateCreated,Path,MediaSourceCount, UserId, ImageTypeLimit=1, EnableImageTypes=Primary,Backdrop,Banner,Thumb`（master 拿掉 Banner）`, EnableTotalRecordCount=false, DisableFirstEpisode=false, NextUpDateCutoff=<今天 − 使用者設定 maxDaysForNextUp 天>`（master 只送日期）`, EnableResumable=false, EnableRewatching=<使用者設定>` |
| 最新加入（每個媒體庫一列） | 10.10 / 10.11：`GET /Users/{userId}/Items/Latest`；master：等價新路徑 | `Limit`（依庫類型 16/30/9/8/5）`, Fields=PrimaryImageAspectRatio,Path, ImageTypeLimit=1, EnableImageTypes=Primary,Backdrop,Thumb, ParentId=<庫>`；不送 `GroupItems`（伺服器預設 true） |
| 劇集庫 | `GET /Users/{userId}/Items` | `SortBy=SortName, SortOrder=Ascending, IncludeItemTypes=Series, Recursive=true, Fields=PrimaryImageAspectRatio, ImageTypeLimit=1, EnableImageTypes=Primary,Backdrop,Banner,Thumb, StartIndex=0, Limit=<libraryPageSize>, ParentId`；排序選單：`SortName`、`Random`、`CommunityRating`、`DateCreated`（加入日期）、`DateLastContentAdded`（新集加入）、`SeriesDatePlayed`（最近看過）、`OfficialRating`、`PremiereDate`，每項後接 `,SortName` |
| 電影庫 | 同上 | `SortBy=SortName,ProductionYear, IncludeItemTypes=Movie, Fields=PrimaryImageAspectRatio,MediaSourceCount`；排序另有 `CriticRating`、`PlayCount`、`Runtime` |
| 篩選面板 | `GET /Items/Filters?UserId&ParentId&IncludeItemTypes`（**不是 Filters2**） | 勾選：`Filters=IsPlayed,IsUnplayed,IsResumable,IsFavorite`、`SeriesStatus=Continuing/Ended/Unreleased`、`VideoTypes`、`HasSubtitles`；動態清單 Genres / OfficialRatings / Tags / Years 來自 Filters 回傳 |
| 詳細頁列季 | `GET /Shows/{id}/Seasons` | `userId, Fields=ItemCounts,PrimaryImageAspectRatio,CanDelete,MediaSourceCount` |
| 詳細頁列集 | `GET /Shows/{id}/Episodes` | `seasonId, userId, Fields=ItemCounts,PrimaryImageAspectRatio,CanDelete,MediaSourceCount,Overview` |
| 卡片圖 | `Items/{id}/Images/{type}` | `fillWidth, fillHeight, quality=96, tag`；**不帶 token**。橫向卡（繼續觀看 / 下一集）優先 `Thumb` → `ParentThumb`（集用劇的 Thumb）→ `Backdrop` → `ParentBackdrop`；直向卡優先 `Primary` → `SeriesPrimary` / `ParentPrimary` |

來源：
[resume.ts](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/components/homesections/sections/resume.ts)、
[nextUp.ts](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/components/homesections/sections/nextUp.ts)、
[recentlyAdded.ts](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/components/homesections/sections/recentlyAdded.ts)、
[tvshows.js](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/controllers/shows/tvshows.js)、
[movies.js](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/controllers/movies/movies.js)、
[filterdialog.js](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/components/filterdialog/filterdialog.js)、
[itemDetails/index.js](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/controllers/itemDetails/index.js)、
[cardBuilder.js](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/components/cardbuilder/cardBuilder.js)、
master [url.ts](https://github.com/jellyfin/jellyfin-web/blob/f0f7b226a26e1512a4dac43e6ddec325977d09d4/src/components/cardbuilder/utils/url.ts)。
10.11.11 與 10.10.7 在這些檔案上邏輯相同（電影庫多了「播放全部」）。

### 7.1 卡片上的觀看標記與已看切換【原始碼 v10.11.11，M1.5 票 05】

研究子代理讀 jellyfin-web `v10.11.11` 與 master（兩邊只差幾個 item 型別的增減，判定形狀相同）：

| 區塊 | 行為 |
| --- | --- |
| 計數徽章 | `getPlayedIndicatorHtml`：**先看 `UserData.UnplayedItemCount`**，非 0 就畫集數（≥ 100 畫 `99+`）——**沒開始看的劇也畫**；否則 `PlayedPercentage >= 100 \|\| Played` 才畫勾。可標記的型別由 `itemHelper.canMarkPlayed` 決定（影片、`Series`、`Season`、`BoxSet` 等） |
| 進度條 | `getProgressBarHtml` 只給 `enableProgressIndicator` 成立的 item（`MediaType === 'Video'`，不含 `TvChannel`），`PlayedPercentage` 在 0 到 100 之間才畫。**劇集沒有 `MediaType`，永遠沒有進度條** |
| 已看切換 | `emby-playstatebutton`（React 版 `PlayedButton.tsx` 同）：`POST` / `DELETE /Users/{userId}/PlayedItems/{itemId}`；多選選單的「Mark played / Mark unplayed」也是直接送。**兩個方向都沒有確認**，`confirm()` 只用在刪除 |
| 切換之後 | 按鈕先就地改狀態；卡片網格收到伺服器推的 `UserDataChanged` 之後就地改那一格的標記（`cardBuilder.onUserDataChanged`），**不重抓卡片**；React 版改成 `invalidateQueries` |

來源：[indicators.js](https://github.com/jellyfin/jellyfin-web/blob/v10.11.11/src/components/indicators/indicators.js)、
[useIndicator.tsx](https://github.com/jellyfin/jellyfin-web/blob/v10.11.11/src/components/indicators/useIndicator.tsx)、
[itemHelper.js](https://github.com/jellyfin/jellyfin-web/blob/v10.11.11/src/components/itemHelper.js)、
[emby-playstatebutton.js](https://github.com/jellyfin/jellyfin-web/blob/v10.11.11/src/elements/emby-playstatebutton/emby-playstatebutton.js)、
[multiSelect.js](https://github.com/jellyfin/jellyfin-web/blob/v10.11.11/src/components/multiSelect/multiSelect.js)、
[apiClient.js markPlayed / markUnplayed](https://github.com/jellyfin/jellyfin-apiclient-javascript/blob/v1.11.0/src/apiClient.js#L3087)。

Berth 照前兩列畫牆上那一行（`services/watch.py`），照第四列就地改那一格；**不照第三列**：Berth 不提供「復原」，
而標為未看清掉的次數與時間找不回來（§5），所以標為未看先確認。

## 8. 直接開始播放某一集的 Web URL

**結論：沒有，brief §20.1 維持。** 【原始碼】三版路由表都有 `#/video`（`playback/video/index`），但它不吃
`itemId` 或 autoplay 參數；播放流程是先 `playbackManager.play(...)` 再導到 `#/video` 顯示 OSD。
`itemDetails` 也不處理任何 autoplay 查詢參數。
—— [user.ts（legacyRoutes）](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/apps/stable/routes/legacyRoutes/user.ts)。
所以「播放某一集」只能深連結到**那一集**的詳細頁 `{host}/web/#/details?id={episodeId}`，使用者再按一次播放。

## 9. 對 Berth 設計的影響

1. **權限是 Berth 的責任，不是 Jellyfin 的。** 用 API key 代讀時，任何帶 `parentId`、`ids`、`seriesId` 的查詢，
   以及帶 `parentId` 的 Genres / Years / Filters / Latest，都**不會**套用使用者的媒體庫權限（第 2 節，12.1.0 實測）。
   plan §11.2b 的驗收「使用者在 Jellyfin 沒有權限的媒體庫在 Berth 也看不到」要成立，Berth 必須：
   - 每個請求先取 `GET /UserViews?userId=<session 的 jellyfin_user_id>`（可短時間快取），把前端送來的 library id
     對這份允許清單驗證，**不在清單就拒絕，不轉發**。
   - **`parentId` 只放驗證過的媒體庫 id**。劇或季當 `parentId` 連使用者自己的 token 都擋不住（第 2 節【新】），
     所以季集不走 `/Items?parentId=<劇|季>`。
   - `userId` 一律取自 session，**絕不接受前端傳入**（API key 是 admin，帶誰的 id 就是誰）。
   - 單一作品 / 集的讀取改用會檢查可見性的端點：`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`
     （無權 404），不用 `/Items?ids=`。
   - 首頁「繼續觀看」「下一集」**不帶 `parentId` / `seriesId`**（這時 Jellyfin 會照使用者的庫限縮），
     要分庫顯示就拿回來之後在 Berth 端依允許清單過濾。`/Items/Latest` 同理。
   - 「越權請求被拒」寫成整合測試；第 2 節的表已在一次性 Jellyfin 12.1.0 上實測（M1.5 票 01），M1.5 票 11 放進 e2e。
   這些責任應該集中在 services 的一個地方，而不是散在每個 API 路由裡。
2. **所有讀取都要帶 `userId`**：家長分級只有帶 `userId` 才生效；不帶的 `/Items` 會交出整台伺服器，
   **`/Shows/{id}/Seasons|Episodes` 不帶時回 200 並略過權限，完全不報錯**（12.1.0 實測）。建議 adapter 讓 `userId`
   成為這幾支方法的必要參數，漏帶就過不了型別檢查（plan §11.2b 已採用）。
3. **帳號狀態不會自動跟上**（12.1.0 實測）：Jellyfin 停用帳號之後，API key 代讀這位使用者的 UserViews、`/Items`、
   Resume、NextUp、Seasons 照常回資料，`UserPlayedItems` 照常寫入；只有他自己的 token 失效（401）、重新登入 403。
   Berth session 30 天、只在登入時向 Jellyfin 驗證，所以瀏覽請求要順手讀 `GET /Users/{id}` 的 `Policy.IsDisabled`
   （brief §19 已定：與允許清單同一份短時間快取，停用就結束 session）。`EnabledFolders` 與 `UserViews` 的 id
   同一種格式，但權威清單仍是 `UserViews`（`EnabledFolders` 只在 `EnableAllFolders=false` 時有意義，另外還有
   `BlockedMediaFolders`）。
4. **圖片沒有權限可言**：知道 item id 的人就能匿名取圖，這是 Jellyfin 本身的設計，Berth 無法更嚴。
   瀏覽器直連最簡單，但要求瀏覽器連得到 Jellyfin（同深連結的主機推導），HTTPS / HTTP 混用有 mixed content；
   Berth 代理圖片可以避開這兩點，代價是頻寬與快取要自己處理。URL 一定要帶 `tag`（它才是快取失效的依據）。
5. **季集查法**：主路徑用 jellyfin-web 的 `/Shows/{id}/Seasons` + `/Shows/{id}/Episodes?seasonId=`
   （三版都有、會套權限、12.0.0 第一次掃描後正確）。**10.11 第一次掃描後這兩支仍可能回 0**；
   因為入庫後使用者馬上會點進去，建議：回 0 而該 Series 的 `RecursiveItemCount` / `ChildCount` 或 Berth 帳本說有集時，
   退回「`parentId=<已驗證的庫>` + 遞迴 + 照 `Path` 或 `SeriesId` 分群」。10.11 上 `SeriesId` 分群可不可靠尚未驗證，
   用 `Path` 最保險（入庫 resolver 已經這樣做，plan §8.2）。
6. **`/Items` 會靜默忽略打錯或不存在的參數**（實測 `seriesId`、`ancestorIds`、`genre`、`year` 都變成回全部）：
   adapter 的每個查詢參數都要有測試斷言「伺服器真的有過濾」，而不只是「請求送出去了」。M1.5 要用的
   `parentId`、`includeItemTypes`、`genres`、`years`、`sortBy` / `sortOrder`、`startIndex` / `limit` 已在 12.1.0
   逐一驗過（第 3.1 節），契約測試可以直接引用那份結果與 fixture。
7. **Resume 一定要帶 `mediaTypes=Video`**，否則 12.0.0 會混進 Season / Series 列。
8. **路徑用新的**：`/UserItems/Resume`、`/Items?userId=`、`/Items/Latest?userId=`、`/UserPlayedItems/{id}?userId=`
   三版都有；舊的 `/Users/{userId}/...` 已從 12.0.0 的 OpenAPI 消失。`NextUp` 的 `disableFirstEpisode` 12.0 已移除。
9. **篩選清單用 `/Items/Filters`**（三版形狀一致、含年份、jellyfin-web 的慣例），**一定帶驗證過的 `parentId`**
   （不帶回空清單）；`/Years` 要記得帶 `includeItemTypes`，否則會混進集的播出年。
10. **標為未看會清掉觀看次數與時間**，UI 不要提供「復原」，或只在確認後送出。對整部劇或整季標記會遞迴到每一集
    （12.1.0 實測）：標已看會把看到一半的位置歸零，標未看會連之前單獨看過的集一起清掉——確認文案要說出範圍。
11. **播放**：沒有自動播放的 URL；「播放」按鈕深連結到該集的詳細頁，由使用者在 Jellyfin 按播放。
12. **由 TMDB id 找作品**（Media 詳情的觀看區）：`/Items` 沒有 provider id 過濾參數，但不帶 `parentId` 的
    `/Items?userId=U&hasTmdbId=true&fields=ProviderIds` 會套權限，在 Berth 端比 `ProviderIds.Tmdb` 即可（第 10 節）。

## 10. 由 TMDB id 找到這位使用者看得到的作品【實測 12.1.0】

**結論：一段查詢就會套權限，不需要兩段法。** 兩段法也驗過，留給已經知道 item id 的情況。

- **`/Items` 沒有 provider id 的過濾參數**：12.1.0 OpenAPI 的 `/Items` 參數裡沒有任何名字帶 `provider` 的；
  試了 `anyProviderIdEquals`、`providerIds`、`tmdbId`、`hasProviderId`（值 `Tmdb.209867`）全部被靜默忽略，回全部 7 筆。
  有的是 **`hasTmdbId`**，而且伺服器真的有過濾：沒有 TMDB id 的 Hotel Show 被排除（6 筆，對照 7 筆）。
- **一段法**：
  ```
  GET /Items?userId=U&recursive=true&includeItemTypes=Series,Movie&hasTmdbId=true
            &fields=ProviderIds&enableImages=false&enableUserData=false
  ```
  **不帶 `parentId` / `ids`**，所以 Jellyfin 以 U 的 `UserViews` 限縮（第 2 節第 2 列），再在 Berth 端比
  `ProviderIds.Tmdb`（字串）。實測：209867 只找到 TV 那一份——Anime 裡同一個 TMDB id 的那一份沒有回來；
  37854（只在 Anime）找不到；27205 找到電影。
  - 代價：一次把這位使用者看得到、有 TMDB id 的所有劇與電影拉回來（這裡 6 筆；關掉圖片與 UserData、只多要
    `ProviderIds`）。大媒體庫要分頁，或對同一位使用者短時間快取。
  - **同一個 TMDB id 可能對到好幾筆**（一個 Media 有多條 Route、分屬不同媒體庫，plan §2.2），要全部留下，
    觀看區決定用哪一筆。
- **兩段法**：API key 不帶 `userId` 用同一個查詢找候選（回整台伺服器：209867 有 TV 與 Anime 兩份），再逐一
  `GET /Items/{id}?userId=U` 驗可見性——TV 那份 200、Anime 那份 404；37854 的唯一候選 404。每個候選多一個請求；
  適合 item id 已經在手上的時候（例如帳本的 `jellyfin_series_id`），只做第二段。

## 11. 12.1.0 與研究當時的 12.0.0【實測 12.1.0】

**結論：研究在 12.0.0 上量過的行為，12.1.0 上沒有看到不同**；圖片的 CORS 標頭判定不了（見下）。

- `GET /UserItems/Resume`、`/Shows/NextUp`、`/Shows/{id}/Episodes`、`/Shows/{id}/Seasons` 的 OpenAPI 參數與 §1.3、§4.1
  逐字相同（NextUp 仍然沒有 `disableFirstEpisode`）。`/Items` 有 `audioLanguages`、`subtitleLanguages`、沒有 provider id
  過濾（第 10 節）——研究沒記下 12.0.0 的 `/Items` 參數表，所以兩件事都說不出 12.0.0 是不是一樣。
- Resume 不帶 `mediaTypes` 仍混進 Season 與 Series（8 筆；帶 `mediaTypes=Video` 剩 2 筆）。
- 不帶 `userId`：Resume、NextUp、`POST /UserPlayedItems` 回 400，後者讀回沒有寫入。
- 舊路徑 `/Users/{userId}/Items/Resume`、`/Users/{userId}/Items/{id}` 仍回 200，仍不在 OpenAPI。
- `/Items` 仍靜默忽略 `seriesId`、`ancestorIds`（回全部 10 集）。
- `includeItemTypes=Series` 不帶 `recursive` 會遞迴（4 部劇）。brief §20.9 原本只讀原始碼，這是第一次實測，不算版本比對。
- `/Items/Filters` 形狀相同；`/Items/Filters2` 的鍵是 `AudioLanguages, Genres, SubtitleLanguages, Tags`（與 v12.0 原始碼一致）。
- 圖片：匿名、`tag` 的快取標頭與錯 tag 照回都相同。`Access-Control-Allow-Origin: *` 在 12.1.0 要請求帶 `Origin` 才出現；
  12.0.0 的紀錄只寫「回應帶」、沒記請求有沒有帶 `Origin`，**判定不了是不是版本差異**。
- 舊式驗證 `X-Emby-Token`、`?api_key=` 回 401（brief §20.9）。
- **沒有重測**：`/Years` 不帶 `includeItemTypes` 會混進集的播出年（這棵媒體樹的集沒有播出日，量不到）；
  「第一次掃描後回 0」（§4.2）。
- 12.0.0 沒量過、這次才量到的（不算版本差異）：第 2 節標【新】的六列、`/Items/{id}` 與
  `/Shows/{id}/Seasons|Episodes` 不帶 `userId` 的行為、停用帳號、Series / Season 標記遞迴、排序的空值與分級順序。
