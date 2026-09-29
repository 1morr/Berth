# Prowlarr 支援下限版本

2026-09-29。依據是 Prowlarr repo 在各 tag 的原始碼（`git clone` 後用 `git show <tag>:<path>`、`git log -S`、`git tag --contains` 查），以及 GitHub Releases 的 `prerelease` 標記。Berth 呼叫的端點與欄位取自 `berth/adapters/prowlarr/`、`berth/adapters/indexer/prowlarr.py`、`berth/services/indexer.py`，以及 brief §20.7。

## 一句話結論

**建議宣告的下限是 Prowlarr 1.3.2.3006**（2023-04-07，第一個包含 `/ping` 的 stable 版）。原始碼上的硬下限是 **1.3.0.2757**（2023-02-23，develop 版），擋住它的只有 `GET /ping`：Berth 用到的其他端點與欄位在第一個 tag `v0.1.0.361`（2021-06）就已經存在。`passwordConfirmation` 要到 1.10.5.4116 才出現，但它**不會把下限往上推**，理由見端點表第 6 列。

## 端點逐條

| # | 端點 / 行為 | 最早版本 | 來源 | 狀態 |
| --- | --- | --- | --- | --- |
| 1 | `GET /ping`：匿名，回 `{"status":"OK"}`，出錯回 500 `{"status":"Error"}` | **1.3.0.2757**（develop）；第一個 stable 是 1.3.2.3006 | commit [`5abb5ad`](https://github.com/Prowlarr/Prowlarr/commit/5abb5ada4991142e871dcfa94c32c8e4cb0ea247)「New: Ping Endpoint」（2023-02-19），新增 `src/Prowlarr.Http/Ping/PingController.cs`，帶 `[AllowAnonymous]`、`[HttpGet("/ping")]`。`git tag --contains` 的第一個結果是 v1.3.0.2757；v1.2.2.2699 雖然在 commit 之後發佈，但不包含這個 commit，`git grep` 在它身上也找不到 ping 路由 | 已驗證 |
| 2a | `GET /api/v1/indexer`、`POST /api/v1/indexer` | 0.1.0.361（第一個 tag） | [`ProviderControllerBase.cs@v0.1.0.361`](https://github.com/Prowlarr/Prowlarr/blob/v0.1.0.361/src/Prowlarr.Api.V1/ProviderControllerBase.cs)：`[HttpGet] GetAll`、`[RestPostById] CreateProvider`。`Enable=true` 時會先跑 `Test(def, false)`，失敗就丟 `ValidationException` 回 400 陣列 | 已驗證（400 的形狀是推論：從程式碼路徑看，每一版都一樣） |
| 2b | 請求本文帶 `appProfileId` | 0.1.0.361 | `IndexerResource.AppProfileId` 在第一個 tag 已經存在；App Sync Profiles 來自 [`f64f8e9`](https://github.com/Prowlarr/Prowlarr/commit/f64f8e915f14ff563a900360afbcebb46712d204)（PR #73，2021-05-18），也包含在 v0.1.0.361 裡。`AppSyncProfileService` 在沒有任何 profile 時會建立 `Standard`，所以 id `1` 會存在 | 已驗證（「id 1 一定是 Standard」是推論） |
| 2c | API 驗證 `appProfileId`：0 或不存在的 id 回 400 | 1.10.1.4059 | [`3963807`](https://github.com/Prowlarr/Prowlarr/commit/3963807c96c13386fdd84aafc06474d4f04bd06c)「New: Add App Profile validation for indexers」。在這之前，0 不會在 API 層被擋下 | 已驗證。這一條不影響下限：Berth 固定送 `1` |
| 3 | `GET /api/v1/indexer/schema` | 0.1.0.361 | 同 2a，`[HttpGet("schema")] GetTemplates` | 已驗證 |
| 4 | `POST /api/v1/indexer/test` | 0.1.0.361 | 同 2a，`[HttpPost("test")]` | 已驗證 |
| 5 | `DELETE /api/v1/indexer/{id}` | 0.1.0.361 | 同 2a，`[RestDeleteById] DeleteProvider` | 已驗證 |
| 6a | `GET /api/v1/config/host`、`PUT /api/v1/config/host/{id}`；欄位 `authenticationMethod`、`username`、`password` | 0.1.0.361 | [`HostConfigResource.cs@v0.1.0.361`](https://github.com/Prowlarr/Prowlarr/blob/v0.1.0.361/src/Prowlarr.Api.V1/Config/HostConfigResource.cs)、`HostConfigController.cs`（`[HttpGet]`、`[RestPutById]`） | 已驗證 |
| 6b | `authenticationRequired`（`enabled` / `disabledForLocalAddresses`） | 1.0.0.2171 | [`c7eb08a`](https://github.com/Prowlarr/Prowlarr/commit/c7eb08a0f024cbed8531d46eaf1029b267d52837)「New: Auth Required」（PR #1245，2022-12-20） | 已驗證 |
| 6c | `passwordConfirmation`：PUT 時必須等於 `password`，除非 `password` 就是資料庫裡的那個雜湊（原樣送回） | **1.10.5.4116**（stable，2023-11-26） | [`26a657f`](https://github.com/Prowlarr/Prowlarr/commit/26a657fa77abb0e46c515b2164d770ffe17207f5)「New: Require password confirmation when setting or changing password」（2023-11-18，從 Sonarr cherry-pick） | 已驗證。**不影響下限**：更舊的版本沒有這個屬性，而 Prowlarr 的 System.Text.Json 設定（`STJson.ApplySerializerSettings`，v1.3.0.2757 確認過）沒有開 `UnmappedMemberHandling.Disallow`，多送的欄位會被忽略。「會被忽略」是從序列化器預設行為推出來的，沒有實跑 |
| 7a | `GET /api/v1/search?query=&indexerIds=`（`indexerIds` 可重複）回陣列 | 0.1.0.361 | [`SearchController.cs@v0.1.0.361`](https://github.com/Prowlarr/Prowlarr/blob/v0.1.0.361/src/Prowlarr.Api.V1/Search/SearchController.cs)：`GetAll(string query, [FromQuery] List<int> indexerIds, …)`。這一版查詢字串空白會直接回空陣列 | 已驗證 |
| 7b | `type=search` 參數；空白查詢也會送到各站 | 0.1.4.1155 | [`5d32bcf`](https://github.com/Prowlarr/Prowlarr/commit/5d32bcf8b9140468da4cd64765f615c4fb15b643)「New: Bulk Grab Releases and Parameter Search」（PR #622）。0.2.0.1678 起改用 `[FromQuery] SearchResource payload`（`query`、`type`、`indexerIds`、`categories`、`limit`、`offset`） | 已驗證（更早的版本 ASP.NET 會忽略 `type`，送了也無害） |
| 7c | 回應欄位 `title`、`indexer`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoUrl`、`infoHash`、`guid`、`publishDate`、`categories` | 0.1.0.361 | `SearchResource.cs@v0.1.0.361` 就有這些欄位；0.2.0 前後改名為 `ReleaseResource`，JSON 欄位名不變（v2.6.5.5623 的 `ReleaseResource.cs` 仍然全部都有） | 已驗證 |
| 8 | `GET /api/v1/system/status` 回 `version` | 0.1.0.361 | [`SystemController.cs@v0.1.0.361`](https://github.com/Prowlarr/Prowlarr/blob/v0.1.0.361/src/Prowlarr.Api.V1/System/SystemController.cs)：`[HttpGet("status")]`、`Version = BuildInfo.Version.ToString()` | 已驗證 |
| — | `/api/v1` 前綴 | 0.1.0.361 | `VersionedApiControllerAttribute.cs@v0.1.0.361`：`Template = $"api/v{version}/{resource}"`；`V1ApiController` 固定是 1。從第一個 tag 到 v2.6.5.5623 都沒有變 | 已驗證 |

取最高的一條：`/ping` 需要 1.3.0.2757，第一個 stable 是 1.3.2.3006。

## `system/status` 的回應形狀與驗證方式

- 形狀（v2.6.5.5623 的 `SystemController.GetStatus`）是一個物件，欄位包括 `appName`、`instanceName`、**`version`**、`buildTime`、`isDebug`、`isProduction`、`isAdmin`、`isUserInteractive`、`startupPath`、`appData`、`osName`、`osVersion`、`isNetCore`、`isLinux`、`isOsx`、`isWindows`、`isDocker`、`isContainerized`、`mode`、`branch`、`authentication`、`databaseType`、`databaseVersion`、`migrationVersion`、`urlBase`、`runtimeVersion`、`runtimeName`、`startTime`、`packageVersion`、`packageAuthor`、`packageUpdateMechanism`、`packageUpdateMechanismMessage`。值為 null 的欄位不會輸出（`DefaultIgnoreCondition = WhenWritingNull`）。
- `version` 來自 `BuildInfo.Version.ToString()`，也就是 `System.Version`，固定四段，例如 `2.6.5.5623`。四段與 release tag 一一對應（tag 是 `v` 加上同一個字串）。v0.1.0.361 用的是同一行程式碼。已驗證。
- **需要 API key。** `Startup.cs` 的 `FallbackPolicy` 是 `AuthorizationPolicyBuilder("API").RequireAuthenticatedUser()`（從 v0.1.0.361 到 v2.6.5.5623 都是），`SystemController` 沒有 `[AllowAnonymous]`。整個原始碼裡標了 `[AllowAnonymous]` 的只有 `/ping`、登入端點與靜態資源。v2.6.5.5623 的 `ApiKeyAuthenticationHandler` 依序接受 `?apikey=`、`X-Api-Key` 標頭、`Authorization: Bearer <key>`；沒帶或帶錯都回 **401**。`authenticationRequired=disabledForLocalAddresses` 只放寬 `UI` policy（前端頁面），不放寬 API 的 fallback policy。已驗證（讀原始碼，沒有實跑）。

## 目前最新 stable

- **2.6.5.5623**，2026-09-16 發佈（`gh api repos/Prowlarr/Prowlarr/releases/latest`）。它之後的 2.6.x 都是 develop（prerelease）。
- 第一個 stable：GitHub Releases 上第一個 `prerelease=false` 的是 **1.0.1.2220**（2023-01-03）。1.0.0.2171 以及所有 0.x 都標成 prerelease。

## 跟下限無關、但 Berth 在新版會碰到的變化

- **Basic 驗證被移除**（2.0.0.5094，[`d36b32f`](https://github.com/Prowlarr/Prowlarr/commit/d36b32f4146164dfd8b71d5fad98124c79f99541)，PR #2399）：PUT `authenticationMethod=basic` 會回 400「'Basic' is no longer supported」。GET 仍然可能讀到舊設定留下的 `basic`。
- **Allowed Hosts／host filtering**（2.6.3.5592，develop；[`c32fc1b`](https://github.com/Prowlarr/Prowlarr/commit/c32fc1ba19972aaa777f2af0e332feea124d5e00)，PR #2798；v2.6.5.5623 已包含）：
  - `HostConfigResource` 多了 `allowedHosts`。PUT 時它不能是 null；當 `authenticationRequired` 不是 `enabled` 時，它必須是非空清單。Berth 先 GET 再原樣送回整份物件、並且送 `authenticationRequired=enabled`，所以不受影響。
  - 使用者如果自己設了 Allowed Hosts，ASP.NET 的 `UseHostFiltering` 會擋掉 `Host` 不在清單裡的請求。清單另外永遠放行 `localhost`、`127.0.0.1`、`[::1]` 與機器名稱。Berth 用 `prowlarr:9696` 之類的 Docker 服務名稱連線時可能被擋，至於回什麼狀態碼沒有查證。預設是空清單，也就是全部接受。
- `forceSave` query 參數從 1.5.2.3484 開始才存在（[`5864a09`](https://github.com/Prowlarr/Prowlarr/commit/5864a090e4e83c44bdae745eb1db07a28ec04b97)），Berth 沒有用到。

## 未查清的地方

- 只讀了原始碼，**沒有**對 1.3.x 實跑。1.3.2.3006 的 `indexer/schema` 內容（Cardigann 定義的 `definitionName`、有哪些站）是執行期從定義伺服器下載的，跟 Prowlarr 版本沒有直接關係，Berth 釘住的 `definitionName` 在舊版上能不能加得起來沒有驗證。
- `POST /api/v1/indexer` 連不上時回的 400 陣列欄位（`isWarning`、`propertyName`、`errorMessage`、`severity`）只在 2.5.2.5491 實測過。舊版走同一條 `ValidationException` 路徑，但錯誤模型的欄位是否完全相同沒有逐版核對。
- 1.10.5 之前的 `GET config/host` 會把 `password` 以雜湊原樣回傳，Berth 送的新密碼會直接 Upsert。這是讀程式碼推出來的，沒有實跑。
- linuxserver 的 Docker image 是否還保留 `1.3.2.3006` 這類舊 tag 沒有查。
- Servarr wiki 沒有列出 API 的版本歷史，本文件的版本全部來自 git tag，沒有 wiki 來源可以交叉比對。
