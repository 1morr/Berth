# 媒體庫瀏覽所需的 Jellyfin API 查證（M1.5 前置，plan §11.2b）

2026-09-15。回答「Berth 的媒體庫頁像 Jellyfin 那樣瀏覽，但**不保存使用者 token、只用一把伺服器 API key**」
這個前提下，每一個功能能不能做、怎麼做、有什麼風險。

## 0. 環境、方法與寫入紀錄

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

**結論：只有一部分會。** Jellyfin 的權限分兩層：

1. **家長分級與標籤**（`MaxParentalRating`、`BlockUnratedItems`、`BlockedTags`、`AllowedTags`）：
   只要查詢帶了 `userId`，`new InternalItemsQuery(user)` 就會 `SetUser(user)` 套用，**三版一致、與憑證種類無關**。
   不帶 `userId` 則完全不套。
2. **媒體庫存取**（`EnableAllFolders` / `EnabledFolders` / `BlockedMediaFolders`）：看**端點與參數**，
   而且有幾條路是 API key 特別放行的。**這是 Berth 的安全邊界問題，下表的 ✘ 必須由 Berth 自己擋。**

**沒有實測**：伺服器上只有一個全權限的管理員，建立受限使用者屬於不被允許的寫入。下表全部是【原始碼】，
行號是 v12.0；10.10.7 / 10.11.11 的同一段以 grep 比對過結構相同（`!isApiKey` 分支、`AddUserToQuery`
的條件、Resume 的 `ParentId = parentIdGuid`、NextUp 的 `GetUserRootFolder().GetChildren(user, true)`）。
**拆票時應在一次性 Jellyfin 上建一個只開放單一媒體庫的使用者，把這張表逐列實測。**

| 呼叫（API key + `userId=U`） | 媒體庫權限 | 依據 |
| --- | --- | --- |
| `GET /UserViews?userId=U` | ✔ 只回 U 看得到的媒體庫 | `UserViewManager`；這是**權威清單** |
| `GET /Items?userId=U&recursive=true`（**不帶** `parentId` / `ids`） | ✔ | `LibraryManager.AddUserToQuery` 在沒有 `ParentId`、`AncestorIds`、`ItemIds`、`TopParentIds` 時，把 `TopParentIds` 設成 U 的 UserViews（[L2080-2111](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/LibraryManager.cs#L2080-L2111)） |
| `GET /Items?userId=U&parentId=<U 無權的媒體庫>` | **✘ 會回內容** | `ItemsController.GetItems` 的可見性檢查寫成 `item is not UserRootFolder && !isApiKey && !item.IsVisible(user)`，**API key 直接跳過**（[L342-350](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/ItemsController.cs#L342-L350)）；帶 `ParentId` 時 `AddUserToQuery` 不設 `TopParentIds`，遞迴查詢直接進 `GetItemsResult`，只有 BoxSet / Playlist 才走 `QueryWithPostFiltering`（[Folder.cs L919-942](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/Folder.cs#L919-L942)）。用使用者自己的 token 同一個請求會回 401 |
| `GET /Items?userId=U&ids=<U 無權的項目>` | **✘** | `ItemIds` 非空時 `AddUserToQuery` 不限縮，`Folder.GetItems` 的 `ItemIds` 分支直接 `GetItemsResult`（[Folder.cs L996-1011](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/Folder.cs#L996-L1011)） |
| `GET /Items/{id}?userId=U` | ✔ 無權時 404 | `GetItemById<BaseItem>(itemId, user)` → `ItemIsVisible` → `IsVisibleStandalone(user)`，後者檢查 `EnabledFolders` / `BlockedMediaFolders`（[UserLibraryController L84-108](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/UserLibraryController.cs#L84-L108)、[LibraryManager L1723-1728, L4060-4073](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/LibraryManager.cs#L4060-L4073)、[BaseItem L1512-1566](https://github.com/jellyfin/jellyfin/blob/v12.0/MediaBrowser.Controller/Entities/BaseItem.cs#L1512-L1566)） |
| `GET /UserItems/Resume?userId=U`（不帶 `parentId`） | ✔ | 走 `GetItemsResult` → `AddUserToQuery` |
| `GET /UserItems/Resume?userId=U&parentId=X` | **✘** | 直接 `ParentId = parentIdGuid`，沒有任何可見性檢查（[ItemsController L940-989](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/ItemsController.cs#L940-L989)）；**使用者 token 也一樣** |
| `GET /Shows/NextUp?userId=U`（不帶 `parentId` / `seriesId`） | ✔ | `parents = GetUserRootFolder().GetChildren(user, true)`（[TVSeriesManager L54-77](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/TV/TVSeriesManager.cs#L54-L77)） |
| `GET /Shows/NextUp?userId=U&parentId=X` 或 `&seriesId=S` | **✘** | `GetItemById(id)` 沒帶 user；**使用者 token 也一樣** |
| `GET /Shows/{S}/Seasons?userId=U`、`/Shows/{S}/Episodes?userId=U[&seasonId=]` | ✔ 無權時 404 | `GetItemById<Series>(seriesId, user)`、`GetItemById<BaseItem>(seasonId, user)`（[TvShowsController L235-261, L351](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/TvShowsController.cs#L235-L261)） |
| `POST/DELETE /UserPlayedItems/{id}?userId=U` | ✔ 無權時 404 | `GetItemById<BaseItem>(itemId, user)`（[PlaystateController L81-88, L147-154](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/PlaystateController.cs#L81-L88)） |
| `GET /Genres`、`/Years`、`/Items/Filters` 帶 `parentId` | **✘**（只洩漏名稱清單） | `GetParentItem(parentId, userId)` 只是 `GetItemById(parentId)`，不看 user（[LibraryManager L3251-3264](https://github.com/jellyfin/jellyfin/blob/v12.0/Emby.Server.Implementations/Library/LibraryManager.cs#L3251-L3264)） |
| `GET /Items/Filters2` 帶 `parentId` | **✘** | `GetItemById<BaseItem>(parentId.Value)` 不帶 user（FilterController L140） |
| `GET /Items/Latest?userId=U` | 【未查】 | 沒有讀 `UserLibraryController.GetLatestMedia` 的限縮邏輯 |
| 圖片 `GET /Items/{id}/Images/*` | **無任何權限**（匿名可取） | 第 6 節 |

其他：

- **API key 不帶 `userId` 的 `/Items`** 回整台伺服器的內容、沒有任何使用者限制（`user` 為 null，實測
  Series / Season / Episode / Movie 數與帶管理員 `userId` 時相同）。
- **停用的 Jellyfin 帳號**：`GetUserId` + `GetUserById` 這條路沒有看到檢查 `Policy.IsDisabled` 的程式碼
  【原始碼推論，未實測，未讀 `UserManager`】。Berth 的 session 活 30 天且不重新向 Jellyfin 驗證
  （plan §2.1），被 Jellyfin 停用或降權的人在 Berth 裡可能繼續看得到。
- `/Items` 的**未知查詢參數會被靜默忽略**：實測 `GET /Items?userId=U&seriesId=<S>&recursive=true&includeItemTypes=Episode`
  與 `ancestorIds=<S>` 都回 **整台伺服器的 49 集**（`/Items` 沒有這兩個參數）。任何「以為有在過濾」的參數
  打錯字，就會變成把全部內容交出去。

## 3. 媒體庫內瀏覽：排序、篩選、類型與年份清單

### 3.1 `/Items` 的排序與篩選【實測 12.0.0 + 原始碼】

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

### 3.2 取某媒體庫可用的類型與年份

| 端點 | 三版 | 回傳 | 實測 12.0.0 |
| --- | --- | --- | --- |
| `GET /Items/Filters?userId&parentId&includeItemTypes&mediaTypes` | 都有（`GetQueryFiltersLegacy`） | `{Genres: string[], Tags: string[], OfficialRatings: string[], Years: int[]}` | Anime：`Genres` 4 個、`Tags` 30 個、`OfficialRatings ["TW-6+"]`、`Years [2023]` |
| `GET /Items/Filters2?userId&parentId&includeItemTypes&isAiring&isMovie&isSports&isKids&isNews&isSeries&recursive` | 都有 | 10.10.7 / 10.11.11：`{Genres: NameGuidPair[], Tags: string[]}`；**v12.0 多 `AudioLanguages`、`SubtitleLanguages`**；**三版都沒有 Years / OfficialRatings** | Anime：`Genres` 帶 `Id`，但 **`Tags: []`**（同一庫 Filters 有 30 個） |
| `GET /Genres?userId&parentId&includeItemTypes&sortBy...` | 都有 | `BaseItemDto[]`（Type=Genre，有 `Id`、可取圖） | TV 回「剧情、喜剧」 |
| `GET /Years?userId&parentId&recursive&includeItemTypes&sortBy&sortOrder` | 都有 | `BaseItemDto[]`（Name 是年份） | **TV 庫不帶 `includeItemTypes` 回 `["2024","2022"]`**——2024 來自集的播出年；帶 `includeItemTypes=Series` 才是 `["2022"]` |

來源：[FilterController v10.10.7](https://github.com/jellyfin/jellyfin/blob/v10.10.7/Jellyfin.Api/Controllers/FilterController.cs)、
[v12.0](https://github.com/jellyfin/jellyfin/blob/v12.0/Jellyfin.Api/Controllers/FilterController.cs)、
`MediaBrowser.Model/Querying/QueryFilters.cs` 與 `QueryFiltersLegacy.cs` 三個 tag。

**建議**：類型 / 年份清單用 `GET /Items/Filters?userId=U&parentId=<已驗證的庫>&includeItemTypes=Series`
（或 `Movie`）——三版回傳形狀一致、一次拿到類型與年份，也是 jellyfin-web 篩選面板用的那一支。
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
- 對 Series / Season 標記會遞迴到底下的集（Jellyfin Web「全部標為已看」就是這支）【原始碼推論，未實測】。
- **「標為未看」不可逆**：`PlayCount` 歸零、`LastPlayedDate` 消失，UI 的「復原」沒辦法恢復原本的觀看次數與時間。

## 6. 圖片

**結論：不需要驗證，瀏覽器可以直接載入。** 【實測 12.0.0 + 原始碼】

- 實測（**完全不帶 `Authorization`**）：
  - Series `Primary` / `Backdrop` / `Backdrop/0` / `Thumb` / `Logo`、Season `Primary`、Episode `Primary`（集劇照）都回 **200**。
  - 不存在的 item 回 404，不存在的圖片類型（`Banner`）回 404。
  - 回應帶 `Access-Control-Allow-Origin: *`。
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

## 8. 直接開始播放某一集的 Web URL

**結論：沒有，brief §20.1 維持。** 【原始碼】三版路由表都有 `#/video`（`playback/video/index`），但它不吃
`itemId` 或 autoplay 參數；播放流程是先 `playbackManager.play(...)` 再導到 `#/video` 顯示 OSD。
`itemDetails` 也不處理任何 autoplay 查詢參數。
—— [user.ts（legacyRoutes）](https://github.com/jellyfin/jellyfin-web/blob/v10.10.7/src/apps/stable/routes/legacyRoutes/user.ts)。
所以「播放某一集」只能深連結到**那一集**的詳細頁 `{host}/web/#/details?id={episodeId}`，使用者再按一次播放。

## 9. 對 Berth 設計的影響

1. **權限是 Berth 的責任，不是 Jellyfin 的。** 用 API key 代讀時，任何帶 `parentId`、`ids`、`seriesId` 的查詢，
   以及 Genres / Years / Filters，都**不會**套用使用者的媒體庫權限。plan §11.2b 的驗收「使用者在 Jellyfin
   沒有權限的媒體庫在 Berth 也看不到」要成立，Berth 必須：
   - 每個請求先取 `GET /UserViews?userId=<session 的 jellyfin_user_id>`（可短時間快取），把前端送來的 library id
     對這份允許清單驗證，**不在清單就拒絕，不轉發**。
   - `userId` 一律取自 session，**絕不接受前端傳入**（API key 是 admin，帶誰的 id 就是誰）。
   - 單一作品 / 集的讀取改用會檢查可見性的端點：`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`
     （無權 404），不用 `/Items?ids=`。
   - 首頁「繼續觀看」「下一集」**不帶 `parentId` / `seriesId`**（這時 Jellyfin 會照使用者的庫限縮），
     要分庫顯示就拿回來之後在 Berth 端依允許清單過濾。
   - 必須在一次性 Jellyfin 上用受限使用者把第 2 節的表逐列實測，並把「越權請求被拒」寫成整合測試。
   這些責任應該集中在 services 的一個地方，而不是散在每個 API 路由裡。
2. **家長分級只有帶 `userId` 才生效**：所有讀取都要帶 `userId`；不帶的 `/Items` 會交出整台伺服器。
3. **帳號狀態不會自動跟上**：Berth session 30 天、只在登入時向 Jellyfin 驗證；Jellyfin 停用或縮權後，
   API key 代讀可能照常回資料（第 2 節，推論未實測）。要嘛瀏覽請求時順手查 `GET /Users/{id}` 的
   `Policy.IsDisabled` 與權限，要嘛縮短 session。
4. **圖片沒有權限可言**：知道 item id 的人就能匿名取圖，這是 Jellyfin 本身的設計，Berth 無法更嚴。
   瀏覽器直連最簡單，但要求瀏覽器連得到 Jellyfin（同深連結的主機推導），HTTPS / HTTP 混用有 mixed content；
   Berth 代理圖片可以避開這兩點，代價是頻寬與快取要自己處理。URL 一定要帶 `tag`（它才是快取失效的依據）。
5. **季集查法**：主路徑用 jellyfin-web 的 `/Shows/{id}/Seasons` + `/Shows/{id}/Episodes?seasonId=`
   （三版都有、會套權限、12.0.0 第一次掃描後正確）。**10.11 第一次掃描後這兩支仍可能回 0**；
   因為入庫後使用者馬上會點進去，建議：回 0 而該 Series 的 `RecursiveItemCount` / `ChildCount` 或 Berth 帳本說有集時，
   退回「`parentId=<已驗證的庫>` + 遞迴 + 照 `Path` 或 `SeriesId` 分群」。10.11 上 `SeriesId` 分群可不可靠尚未驗證，
   用 `Path` 最保險（入庫 resolver 已經這樣做，plan §8.2）。
6. **`/Items` 會靜默忽略打錯或不存在的參數**（實測 `seriesId`、`ancestorIds` 都變成回全部）：
   adapter 的每個查詢參數都要有測試斷言「伺服器真的有過濾」，而不只是「請求送出去了」。
7. **Resume 一定要帶 `mediaTypes=Video`**，否則 12.0.0 會混進 Season / Series 列。
8. **路徑用新的**：`/UserItems/Resume`、`/Items?userId=`、`/Items/Latest?userId=`、`/UserPlayedItems/{id}?userId=`
   三版都有；舊的 `/Users/{userId}/...` 已從 12.0.0 的 OpenAPI 消失。`NextUp` 的 `disableFirstEpisode` 12.0 已移除。
9. **篩選清單用 `/Items/Filters`**（三版形狀一致、含年份、jellyfin-web 的慣例）；`/Years` 要記得帶
   `includeItemTypes`，否則會混進集的播出年。
10. **標為未看會清掉觀看次數與時間**，UI 不要提供「復原」，或只在確認後送出。
11. **播放**：沒有自動播放的 URL；「播放」按鈕深連結到該集的詳細頁，由使用者在 Jellyfin 按播放。
