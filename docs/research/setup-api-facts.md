# 開箱即用所需的 API 與 Windows Docker 事實

從 design-brief §20.7（開箱即用所需的 API 與 Windows Docker 事實）搬來，原文不改字；各段前的 `##` 標題是為了讓 brief 連得到錨點而加。


## Windows Docker Desktop 硬鏈接

**Windows Docker Desktop 硬鏈接（本機實測，2026-09-07）**

- 環境：Windows 11、Docker Desktop 29.6.2（WSL2 後端）、NTFS 系統碟。把同一個 Windows 目錄 bind mount 為 `/data`，容器內對 `/data/torrent/complete/a.bin` 做 `ln` 到 `/data/library/b.bin`：**成功**，兩者 `dev=70`、inode 相同、`nlink=2`；掛載型態為 `9p (aname=drvfs)`。宿主端 `fsutil hardlink list` 列出兩個路徑，證明是真正的 NTFS 硬鏈接。
- 把 `torrent/` 與 `library/` 分開掛成兩個 bind mount：`ln: Cross-device link`，與 Linux 行為一致（單一掛載根的規則不變）。
- Docker named volume（WSL2 內 ext4）：成功。
- 結論：**Windows 使用者可以用一般的 bind mount**（`DATA_ROOT=D:\Berth\data`），不需要 named volume；exFAT 隨身碟不支援硬鏈接（[TRaSH](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)）。§4.4 的「不退回複製」維持。
- 其他查證：named volume 可從 `\\wsl.localhost\docker-desktop\mnt\docker-desktop-disk\data\docker\volumes\` 瀏覽；WSL2 VHD 預設上限 1 TB（[Microsoft](https://learn.microsoft.com/en-us/windows/wsl/disk-space)）；搬移 VHD 的設定介面有多起失效回報（[docker/for-win#13269](https://github.com/docker/for-win/issues/13269)）→ 這些都是不用 named volume 的理由。bind mount 經 9p 的吞吐比 volume 低（[Docker blog](https://www.docker.com/blog/file-sharing-with-docker-desktop)），下載寫入會慢一些，硬鏈接本身是 metadata 操作不受影響。


## Jellyfin 初始化與插件 API

**Jellyfin 初始化與插件 API**（[OpenAPI](https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json)、[FirstTimeSetupHandler.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Auth/FirstTimeSetupPolicy/FirstTimeSetupHandler.cs)）

- `GET /System/Info/Public` 無需憑證，回 `StartupWizardCompleted`。
- `POST /Startup/Configuration`（`ServerName`、`UICulture`、`MetadataCountryCode`、`PreferredMetadataLanguage`）、`POST /Startup/User`（`Name`、`Password`）、`POST /Startup/RemoteAccess`（只有 `EnableRemoteAccess`，沒有 `EnableAutomaticPortMapping`）、`POST /Startup/Complete`，以及 **`GET/POST/DELETE /Library/VirtualFolders`**，都掛 `FirstTimeSetupOrElevated` 政策：精靈未完成時匿名可呼叫，完成後需管理員 token。
- `POST /Library/VirtualFolders?name=&collectionType=&paths=&refreshLibrary=`，`collectionType` 可為 `movies` / `tvshows` / `music` / `musicvideos` / `homevideos` / `boxsets` / `books` / `mixed`；body `{LibraryOptions}` 含 `PathInfos`、`EnableRealtimeMonitor`、`PreferredMetadataLanguage`、`MetadataCountryCode`、`TypeOptions[]`、`SeasonZeroDisplayName`、`EnableAutomaticSeriesGrouping`、`EnableEmbeddedTitles`、`AutomaticRefreshIntervalDays`。
- 為既有媒體庫加路徑：`POST /Library/VirtualFolders/Paths?refreshLibrary=`，body `MediaPathDto {Name, Path, PathInfo{Path}}`；移除為 `DELETE /Library/VirtualFolders/Paths?name=&path=`。路徑驗證：`POST /Environment/ValidatePath`，body `{ValidateWritable, Path, IsFile}`；另有 `GET /Environment/DirectoryContents?path=`。兩組都是 `FirstTimeSetupOrElevated`（本機對 OpenAPI 直接查核，2026-09-07）。
- **`POST /Environment/ValidatePath` 看得到回 204、看不到回 404**：`IsFile: true` 時走 `File.Exists`、`false` 時走 `Directory.Exists`、不給則兩者皆否才算沒有；`ValidateWritable: true` 會讓 Jellyfin 自己在那裡建一個暫存檔再刪掉，Berth 不送它——要問的只是「你看不看得到我寫的這一個」（查核 master 的 [EnvironmentController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/EnvironmentController.cs)，2026-09-08）。**404 是答案不是失敗**，adapter 因此把它翻成 `False` 而不是例外。
- `GET/POST /Repositories`（`{Name, Url, Enabled}`）、`POST /Packages/Installed/{name}?assemblyGuid=&version=&repositoryUrl=`、`POST /System/Restart`、`GET /ScheduledTasks`、`POST /ScheduledTasks/Running/{taskId}` 都需管理員（`RequiresElevation`）。
- MergeVersions：manifest `https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json`，套件名 `Merge Versions`，GUID `f21bbed8-3a97-4d8b-88b2-48aaa65427cb`；排程任務 `Key` 為 `MergeMoviesTask` 與 `MergeEpisodesTask`（[RefreshLibraryTask.cs](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/Jellyfin.Plugin.MergeVersions/ScheduledTasks/RefreshLibraryTask.cs)），觸發時要用 `GET /ScheduledTasks` 回傳的 `Id`，不是 `Key`。


## Jellyfin 精靈序列實測

**Jellyfin 精靈序列實測**（2026-09-07，票 06；`jellyfin/jellyfin:10.11.11`，由 Berth 自己的 adapter 跑完 plan §9.4 全序列並錄下回應，fixture 在 `tests/fixtures/http/jellyfin/`）

- **`POST /Auth/Keys?app=` 回 204 而且不回傳 key**，只能再 `GET /Auth/Keys` 從 `Items[].AppName` 找回來。它**不檢查重複**：同一個 `app` 按兩次就有兩把 `AppName="Berth"` 的 key。所以要先列再建、建完再列。
- **`POST /Library/VirtualFolders` 同名不會被拒**：第二次一樣回 204，並建出名為 `Movies2` 的第二個媒體庫指向同一個路徑。冪等要靠呼叫端先 `GET /Library/VirtualFolders`。
- **`POST /Library/VirtualFolders/Paths` 不去重**：同一條路徑送兩次，該媒體庫的 `Locations` 就有兩個一樣的字串。目錄不存在時回 **404**（`Error processing request.`），所以路徑要先由 Berth 建好——Berth 與 Jellyfin 掛同一個宿主目錄在同一個容器路徑（§16.4），建完 Jellyfin 立刻看得到。**那一句說不出原因**（2026-09-30 對 12.1 的 `bad-jellyfin-elsewhere` 再測，M4 票 19）：Jellyfin 看不到目錄與**媒體庫不存在**回的是同一個 `404` + `Error processing request.`（`text/plain`），`The path does not exist` 只在它自己的 log。所以 Berth 在送之前先寫探測檔、以 `ValidatePath {IsFile: true}` 問它。**不問目錄本身**：linuxserver 的 Jellyfin image 自己就有一個空的 `/data`，沒掛任何東西時 `ValidatePath {Path: "/data", IsFile: false}` 也是 204。
- **`LibraryOptions.TypeOptions[]` 省略 `ImageFetchers` 會被存成空陣列**（實測送 `{Type, MetadataFetchers, MetadataFetcherOrder}` 讀回來 `ImageFetchers: []`），該類型從此不抓圖。要嘛整個 `TypeOptions` 留空用 Jellyfin 的預設，要嘛兩種 fetcher 都給值。
- **`GET /Libraries/AvailableOptions?libraryContentType=movies|tvshows`** 回這台伺服器實際裝了哪些 fetcher（`{Name, Type}` 物件陣列），政策是 `FirstTimeSetupOrDefault`，精靈期間匿名讀得到。乾淨的 10.11.11：Movie 的 metadata 是 `TheMovieDb` / `The Open Movie Database`，image 多了 `Embedded Image Extractor` / `Screen Grabber`；tvshows 分 Series / Season / Episode 三個型別。裝了官方 TVDB 插件之後每個型別各多一個 `TheTVDB`，Series 還多 `Missing Episode Fetcher` —— 這正是「image fetcher 不可以寫死」的證據。
- **登入 token 與 API key 在標頭裡是同一個形狀**：`Authorization: MediaBrowser Client="…", Device="…", DeviceId="…", Version="…", Token="<token 或 key>"`，兩者都吃得下 `RequiresElevation` 的端點。
- **重啟的三個階段**：`POST /System/Restart` 當下連線直接被切（httpx 的 `RemoteProtocolError`）→ 一段時間所有端點回 **503** → 才回 200。所以「還沒好」有兩種形狀（連不上與 503），輪詢兩種都要當成繼續等。
- `StartupRemoteAccessDto` 在 10.11.11 的 schema **有** `EnableAutomaticPortMapping`（本節前面說「沒有」是過時的），但 Berth 只送 `EnableRemoteAccess`。
- MergeVersions 的排程任務 `Id` 在這台是 `MergeMoviesTask=fd957c84b0cfc2380becf2893e4b76fc`、`MergeEpisodesTask=dcaf151dd1af25aefe775c58e214477e`。**不要假設它跨安裝相同**，一律從 `GET /ScheduledTasks` 讀。
- 整段九步對真伺服器跑完 **69 秒**（大半花在插件下載與重啟）；第二次跑 **0.2 秒**，除了第 1 步之外全部是 `skipped`。


## Prowlarr API

**Prowlarr**（[OpenAPI](https://raw.githubusercontent.com/Prowlarr/Prowlarr/develop/src/Prowlarr.Api.V1/openapi.json)、[supported-indexers](https://wiki.servarr.com/prowlarr/supported-indexers)、[environment-variables](https://wiki.servarr.com/prowlarr/environment-variables)）

- `GET /api/v1/indexer/schema`、`GET/POST /api/v1/indexer`、`DELETE /api/v1/indexer/{id}`（回 200，OpenAPI）、`POST /api/v1/indexer/test`；`GET /api/v1/search?query=&indexerIds=&categories=&type=` 回 `ReleaseResource`（`title`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoHash`、`indexer`、`categories`、`publishDate`、`guid`、`infoUrl`、`tmdbId` …）。Prowlarr 明言**不提供跨站聚合 Torznab**，單站 Torznab 為 `/{id}/api?t=search&apikey=`。
- **`indexer/schema` 的第一次呼叫很慢**（2026-09-08 票 11 M0 驗收實測）：容器剛起來時它要把 627 份 Cardigann 定義從 `/config` 讀進來再組出 **5.6 MB** 的回應，Windows Docker Desktop 的 9p bind mount 上量到 **9.42 秒**；同一支端點第二次 0.34 秒。慢的儲存（NAS）只會更久，所以這一支必須有自己的逾時，不能沿用探測用的 5 秒。**未量測**：成因是冷容器從 `/config` 讀那 627 份定義，不是回應大小，所以同一時刻的 `config/host` 理論上也慢；它目前仍用 5 秒，沒有數據支持那樣安全。
- API key 在 `config.xml` 的 `<ApiKey>`，可用 `PROWLARR__AUTH__APIKEY` 預設。
- 支援的公開索引站含：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、**Mikan**、1337x、YTS、EZTV、The Pirate Bay；TorrentGalaxy 目前不在清單。


## Prowlarr 索引站與 TMDB 憑證實測

**Prowlarr 索引站與 TMDB 憑證實測**（2026-09-08，票 08；Prowlarr 2.5.2.5491，fixture 在
`tests/fixtures/http/prowlarr/` 與 `tests/fixtures/http/tmdb/`）

- **`POST /api/v1/indexer` 會先連一次那個站再存**：成功回 201 與整份資源；連不上回 **400 加一個陣列**，
  每列是 `{isWarning, propertyName, errorMessage, severity}`。站沒有被建立。所以「逐站成敗」來自新增
  那一支，`indexer/test` 是給**已經存在**的站用的（回 200 空物件）。`?forceSave=true` **不會**跳過這個檢查。
  **測試通過不保證新增成功**：新增那一次是另一次連站，時好時壞的站兩次結果可能不同（2026-10-06 審計實測
  Internet Archive：`indexer/test` 通過、緊接著新增回「連不上」，`docs/research/wizard-audit-2026-10-06.md` S1 頁 4）。
  頁 4 的主鍵因此把「測過而加不進去」與「測試就沒過」分開記（M4 票 44）。
- **同名的第二個站被拒**：400 `{"propertyName": "Name", "errorMessage": "Should be unique"}`。冪等只能靠
  呼叫端先 `GET /api/v1/indexer`。
- schema 的 `appProfileId` 是 **0**，原樣送回去建不起來；要換成 `1`（Prowlarr 內建的同步設定檔）。
- 十個預設站的 `definitionName` 實測為 `nyaasi`、`dmhy`、**`Anidex`**（不是文件寫的 `AniDex`）、
  `animetosho-xyz`（唯一 `semiPrivate`）、`acgrip`、`mikan`、`1337x`、`yts`、`eztv`、`thepiratebay`。
  站名 Prowlarr 自己會改，機器名不會，所以清單釘 `definitionName`。
- 本機這一輪十個站有五個加得起來、五個失敗（`nyaasi` 查得到但沒有結果、`Anidex` 與
  `animetosho-xyz` 連不上、`1337x` 與 `eztv` 被 CloudFlare 擋）。**幾個公開站連不上是常態**，UI 因此逐站顯示而不是整批成敗。
  另外：容器預設的憑證驗證會擋下 TLS 被攔截的環境（`config/host.certificateValidation`），那是使用者
  環境的事，Berth 不改它。
- **每個定義帶 `language` 與 `description`**（2026-09-24 / 09-25 在 Prowlarr 2.5.2.5491 實測，OpenAPI 的
  `IndexerResource` 兩者皆為 nullable string）：`language` 是 BCP 47（dmhy `zh-TW`、ACG.RIP / Mikan `zh-CN`、
  其餘 `en-US`），`description` 是一句英文（「dmhy is a TAIWANESE Public magnet tracker for ANIME」）。
- **AniDex 的定義還在、站連不上**（2026-09-25 實測，票 06e）：`Anidex` 是 C# 內建實作，2.5.2.5491 的
  schema 照樣有它；拿它去 `indexer/test` 回 `Unable to connect to indexer ... [502:BadGateway]`，anidex.info
  直接打也是 502（09-08 那一輪也連不上）。預設清單因此拿掉它，理由是站掛了，不是定義消失。
- **空白查詢回各站最新的發佈**（2026-09-25 實測）：`GET /api/v1/search?query=&indexerIds=<id>&type=search`
  對 dmhy 回 80 筆、YTS 96 筆，各約 1.3 秒。精靈的試搜（票 06e）以它當預設：不必先想一個標題也證明得了
  那一站回得出東西。`indexerIds` 限定那一站，逐站各發一個才分得出哪一站失敗。
- **`indexerIds` 可以一次帶好幾站，空的是每一個啟用中的站**（2026-10-09 查證，M4 票 77）：`SearchResource`
  的 `IndexerIds` 是 `List<int>`，查詢字串重複帶（`indexerIds=3&indexerIds=7`）綁得進去；控制器交給
  `_releaseSearchService.Search(request, payload.IndexerIds, true)`，空的時是全部啟用中的站；帶的每一站都不可用時回 400
  （上一條）。M4 票 77 曾靠它跳過請求預算放不下的站；M4 票 107 拿掉請求預算之後搜尋不帶它（問全部），只剩精靈的逐站試搜在用。
  【原始碼 [`SearchResource.cs`](https://github.com/Prowlarr/Prowlarr/blob/develop/src/Prowlarr.Api.V1/Search/SearchResource.cs)、
  [`_autodocs/api-reference/search.md`](https://github.com/Prowlarr/Prowlarr/blob/develop/_autodocs/api-reference/search.md)，經 context7】
- **`indexer/test` 也測得了還沒加入的定義；搜尋只吃已加入的站**（2026-09-30 berth-lab `bundled` 的
  Prowlarr 2.6.5.5623 實測，M4 票 09；OpenAPI 的 `POST /api/v1/indexer/test` body 是 `IndexerResource`、
  另有 `forceTest` 查詢參數）：把 `indexer/schema` 的定義原樣送（`appProfileId` 換 1），通過回 **200 `{}`**
  （YTS 1.9 秒、dmhy 1.1 秒），不通過回 **400 加逐條理由**，形狀與新增那一支相同；兩種都**不建立任何東西**
  （測完 `GET /api/v1/indexer` 仍是 0 站）。這就是 Prowlarr 自己「新增索引站」對話框的 Test。
  `GET /api/v1/search?indexerIds=99999` 回 400「Search failed due to all selected indexers being unavailable」：
  `indexerIds` 只認已加入的站，所以「加入之前先搜」做不到，流程是「測試 → 勾通過的 → 加入 → 逐站 / 全部試搜
  → 不要的移除」。錄下的原文在 `tests/fixtures/http/prowlarr/indexer-test.rejected.*.json`：
  `Unable to access 1337x.to, blocked by CloudFlare Protection.`、`Unable to connect to indexer. This is
  typically caused by DNS/SSL issues. …`（nyaasi 的 SSL 失敗）；加上 09-08 那一份
  `Query successful, but no results were returned …`，畫面分成 Cloudflare / 查無結果 / 連不上 / 其他四種理由。
- **schema 裡的公開站**（同一次實測）：645 個定義，privacy 是 `public` 88、`semiPrivate` 64、`private` 493。
  公開站裡 NZBIndex 是 usenet（`protocol: usenet`，Berth 只接 qBittorrent），`Torrent RSS Feed` 的
  `definitionName` 出現兩次（它自己與 preset showRSS）。所以「全部公開站」只收 `protocol == torrent`、依
  `definitionName` 去重。語言分布：`en-US` 59、`ru-RU` 15、`zh-CN` 5、其餘各 1–2。
- **TMDB 的兩種憑證都打得動 v3 端點**：v4 的 read access token 走 `Authorization: Bearer`（官方建議、
  不進網址），v3 的 32 字元 API key 走 `?api_key=`；key 不對回 401。Berth 認憑證的**形狀**，
  所以使用者貼哪一種都成立。


## 索引站搜尋實測

**索引站搜尋實測**（2026-09-10，票 08；Prowlarr 2.5.2.5491 + 五個公開站 acgrip / dmhy / mikan /
thepiratebay / yts，fixture 在 `tests/fixtures/http/prowlarr/search.*.json` 與
`tests/fixtures/http/torznab/` 已刪，M4 票 37）

- **`GET /api/v1/search` 很慢而且不吃 `limit`**：單次冷查詢 60–85 秒（Prowlarr 現場去連五個站），
  `limit=20` 仍然回 1200 筆。**三個查詢併發共 35 秒**，所以逐標題併發是對的，逾時要給到 120 秒。
- **`downloadUrl` / `magnetUrl` 每次請求都不一樣**：`link=` 的密文帶 nonce，同一個查詢連跑兩次
  1021 筆只有 1 筆重疊。`guid` 穩定（1200/1200）。所以身分是 infohash 或 `guid`，不是下載網址。
  兩者都是 Prowlarr **自己的代理網址**（主機來自它的 `config/host`，不是 Berth 打過去的位址），
  磁力站（TPB、dmhy）沒有 `downloadUrl`，只有被包成代理網址的 `magnetUrl`。
  **兩者都帶 `?apikey=<Prowlarr API key>`**（M4 票 76 實作時發現；拿到它就能改 Prowlarr 的設定、索引站與帳密），
  所以不出伺服器（M4 票 79）：搜尋把每一列的連結記在 Berth 程序裡，前端只拿 id，送單收 id 換回連結。
  慣例照 Sonarr 的 interactive search（`Sonarr.Api.V3/Indexers/ReleaseController.cs`：搜尋結果以
  `{indexerId}_{guid}` 放進快取 30 分鐘，送單只帶 `guid` 與 `indexerId`，找不到回 404「try searching again」），
  Berth 的 id 是隨機的、記兩小時（理由在 `berth/services/sources.py`）。
- **info hash 有兩種寫法**：同一個發佈在 Mikan 是 40 字十六進位、在 dmhy 是 32 字 base32，
  base32 解碼後位元組相同。不正規化的話單次查詢的 1200 筆裡有 47 筆會重複顯示。
- **多標題是真的多一批東西**：`Spy x Family` / `SPY×FAMILY` / `间谍过家家` 各搜出 1200 / 908 / 1210 筆，
  聯集 1854 筆，各自帶來 391 / 196 / 169 筆另外兩個問不到的結果。
- **tmdbid 是私站的功能**：627 份 Cardigann 定義裡 93 份的 `tvSearchParams` / `movieSearchParams`
  含 `tmdbId`，**全部是 private 或 semiPrivate**；十個預設公開站一個都沒有（YTS 只有 `imdbid`）。
  所以 `q=` 才是常態（Prowlarr 的 REST 本來就只收關鍵字；M4 票 37 前 Torznab 端點依 `t=caps` 選問法）。
- **分類碼不是可靠的篩子**：dmhy 對 `cat=5000`、`cat=5070` 與不帶 `cat` 都回同樣 80 筆；
  它一筆帶 5070 / 100002 / 2020 而沒有 5000。Berth 因此不送 `categories`，只把分類當顯示資料。
- **The Pirate Bay 對搜不到的關鍵字會回它自己的熱門清單**：搜 SPY×FAMILY 時前六筆是 Spider-Man、
  Lanterns、Ted Lasso、Reacher，做種四千到六千。純做種排序時它們會把真正的結果整批擠出前 100 筆，
  所以 Berth 先用標題粗篩再逐站輪流取。
- **公開中文站的做種數是個位數**：Mikan / ACG.RIP / dmhy 的發佈多半 0–2 個做種，TPB 的 scene 發佈
  28–86 個。取「做種前 100 筆」等於把中文字幕組整批刪掉。
- **`parse_release` 每筆 14 毫秒**（1200 筆 17.4 秒，含 guessit）。一兩千筆全解析會把事件迴圈卡住
  半分鐘，所以粗篩要用純字串比對，解析只跑在留下來的那一百筆上。


## Jackett

**Jackett**（[repo](https://github.com/Jackett/Jackett)）

- API key 在 `ServerConfig.json` 的 `APIKey`；聚合 Torznab `/api/v2.0/indexers/all/results/torznab/api?t=search` 有文件（上限 1000 筆、站專屬分類不可用）；`GET/POST /api/v2.0/indexers/{id}/Config` 只是 UI 內部介面，無文件。有 `mikan.yml`、`dmhy.yml`、`nyaasi.yml`、`acgrip.yml` 定義。
- ~~結論維持 §19：套件預設 Prowlarr，Jackett 以 Torznab 端點接入。~~ **已不採用**（2026-10-06 D3、M4 票 37）：只支援 Prowlarr；以上來源與事實留作紀錄。


## compose 套件實測

**compose 套件實測（2026-09-07，Windows 11 + Docker Desktop 29.6.2，票 03）**

- **發佈 port 的來源位址**：Docker Desktop 把 `-p 8080:8080` 進來的流量 SNAT 成 bridge 閘道位址（`172.28.0.1`），而閘道本身就在 compose 網段內。所以 `WebUI\AuthSubnetWhitelist=172.28.0.0/16` 等於讓宿主與 LAN 上任何人免密打 qBittorrent 的 API —— 實測 `curl http://localhost:8080/api/v2/app/version` 直接回 `v5.2.3`。白名單縮成 Berth 容器固定 IP 的 `172.28.0.2/32` 之後：berth 容器回 200、宿主 403、同網段的其他容器 403。§16.3「LAN 使用者開 8080 仍要密碼」只有在白名單是單一位址時才成立。
- Docker 的動態 IP 從網段開頭配發（實測 `172.28.0.2` 給了先啟動的 prowlarr），固定 IP 要靠 `ip_range` 把動態池隔到別的段，否則會撞。
- **linuxserver/qbittorrent 的啟動順序**：`init-qbittorrent-config`（依賴 `init-config`）排在 `init-custom-files`（依賴 `init-mods-end`，而該鏈在 `init-config-end` → `init-qbittorrent-config` 之後）之前。custom-cont-init.d 的腳本跑到時 `/config/qBittorrent/qBittorrent.conf` **一定已經存在**，由 image 從 `/defaults/qBittorrent.conf` 複製。因此「檔案不存在才寫」的預置條件永遠不成立，改為「缺鍵才補」。
- **缺鍵才補的另一面：在 WebUI 關掉或改掉白名單，重啟補不回來**（M4 票 53，2026-10-07 實跑 `5.2.3_v2.0.15-ls478`）：首次啟動腳本印 `added to …`；以 WebUI API（`app/setPreferences` 的 `bypass_auth_subnet_whitelist_enabled: false`）關掉之後 `docker restart`，腳本印 `already configured`，`WebUI\AuthSubnetWhitelistEnabled=false` 不變，而 `WebUI\AuthSubnetWhitelist=172.28.0.2/32` 那一行留著。所以補法在 WebUI：「選項 → WebUI → 驗證」的「讓已在白名單中的 IP 子網路略過驗證」（英文 *Bypass authentication for clients in whitelisted IP subnets*；標籤取自 qBittorrent `release-5.0.0` 的 [`preferences.html`](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.0/src/webui/www/private/views/preferences.html) 與 [`webui_zh_TW.ts`](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.0/src/webui/www/translations/webui_zh_TW.ts)）。
- `/defaults/qBittorrent.conf` 的內容：`LegalNotice\Accepted=true`、`WebUI\Address=*`、`WebUI\ServerDomains=*`、`Downloads\SavePath=/downloads/`、`Downloads\TempPath=/downloads/incomplete/`、`Connection\UPnP=false`、`Connection\PortRangeMin=6881`。整份覆蓋會掉 `LegalNotice\Accepted`，qbittorrent-nox 會卡在法律聲明；而 `ServerDomains` 既然預設是 `*`，Host 檢查本來就過得了，寫死成 `qbittorrent` 反而讓使用者從 `localhost:8080` 進不去。
- `init-custom-files` 只檢查 executable bit（不檢查擁有者），以 `/bin/bash <script>` 執行（[docker-baseimage-alpine](https://github.com/linuxserver/docker-baseimage-alpine/blob/master/root/etc/s6-overlay/s6-rc.d/init-custom-files/run)、[container-customization](https://docs.linuxserver.io/general/container-customization/)）。
- `lscr.io/linuxserver/qbittorrent:latest` 目前是 qBittorrent v5.2.3。
- Berth image（node:24-slim build → python:3.13-slim runtime）：281 MB 未壓縮、62.8 MB gzip，遠低於 400 MB 的上限。
- `python:3.13-slim`（Debian 13 trixie）內建 `setpriv`、`usermod`、`groupmod`、`getent` 與 tzdata，`PUID` / `PGID` 降權不需要額外裝 gosu；但沒有 curl。
- 空的 named volume 與 Docker 替 bind mount 新建的目錄都是 `root:root`，非 root 的容器寫不進去。入口腳本因此只在 `/data` 還是空目錄時接手擁有者，已經有內容的媒體根不碰（實測：空目錄 → 檔案為 `1500:1500`、`umask 002`；非空目錄 → 維持 `root:root`）。
- compose 內再次確認 `/data` 的硬鏈接：`dev=70`、inode 相同、`nlink=2`（與 §20.7 開頭的 Windows 實測一致）。


## TMDB 憑證由使用者自備

**TMDB 憑證由使用者自備**（2026-09-09 決定，推翻本節原本的「沿用 Seerr 的專案級 key」）

- Jellyseerr / Seerr 在 `server/api/themoviedb/index.ts` 寫死一把專案 key，使用者無處填自己的 key（[overseerr#3887](https://github.com/sct/overseerr/issues/3887)）；Jellyfin 團隊也曾討論專案級 key（[jellyfin#36](https://github.com/jellyfin/jellyfin/issues/36)）。TMDB 條款只區分商業與非商業，未明文規範「一 app 一 key」，所以那條路是走得通的。
- **本系統仍然不走**：一把發給所有使用者的共用憑證由專案背著它的用量與行為，而 TVDB 的 ToS 明文擋的也正是這件事（§20.3）。兩個 provider 在「使用者自己申請一把」上對稱，於是這裡也對稱處理。憑證的唯一來源是 `settings.services.tmdb.api_key`，精靈第 6 步是**必填的閘門**（plan §9.3）。
- 申請路徑：themoviedb.org 免費帳號 → 設定 → API → 用途選 Personal / Education，即時核發。同一頁同時給 v3 API key 與 v4 read access token，兩種形狀 Berth 都收（plan §8.3，2026-09-08 實測）。


## qBittorrent 預置

**qBittorrent 預置**（[sessionimpl.cpp](https://github.com/qbittorrent/qBittorrent/blob/master/src/base/bittorrent/sessionimpl.cpp)、[linuxserver/qbittorrent](https://docs.linuxserver.io/images/docker-qbittorrent)、[qbittorrent-nox](https://github.com/qbittorrent/docker-qbittorrent-nox)）

- 4.6.1 起首次啟動用隨機臨時密碼印在 log；已知密碼要預置 `WebUI\Password_PBKDF2`（PBKDF2-HMAC-SHA512、100000 次）。官方 image 沒有密碼環境變數，也沒有 `PUID` / `PGID`；linuxserver image 有，且設定檔在 `/config/qBittorrent/qBittorrent.conf`。
- `[Preferences]`：`WebUI\Port`、`WebUI\AuthSubnetWhitelistEnabled`、`WebUI\AuthSubnetWhitelist`、`WebUI\LocalHostAuth`、`WebUI\HostHeaderValidation`、`WebUI\CSRFProtection`；`[BitTorrent]`：`Session\DefaultSavePath`、`Session\TempPath`、`Session\TempPathEnabled`、`Session\DisableAutoTMMByDefault`（**預設 true，即 autoTMM 關閉**）、`Session\DisableAutoTMMTriggers\CategorySavePathChanged`、`Session\Port`。
- Web API `app/setPreferences` 對應鍵：`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`、`bypass_auth_subnet_whitelist(_enabled)`、`bypass_local_auth`、`web_ui_password`（只寫）。


## Jellyfin 命名實測

**Jellyfin 命名實測**（2026-09-07，票 04；`jellyfin/jellyfin:10.10.7` 與 `:10.11.11`，dummy 檔 + API 查驗，[完整結果](../research/m0-experiments.md#1-jellyfin-命名10107-與-101111)）

- **`S01E01` 一律認得**，`S01E03-E04` 解析為 `IndexNumber=3` + `IndexNumberEnd=4`，`S00E01` 進 `Specials` 季。**方括號與 `+` 不會滲進 Series 或 Episode 名稱** —— Jellyfin 根本不從檔名取集標題（TMDB 對不上的作品，帶 tag 與不帶 tag 的兩集名稱完全相同）。
- **電影多版本**：檔名在 ` - ` 之前必須與資料夾名一字不差（含 `[tmdbid-<id>]`），否則變成兩部獨立的電影。標籤含方括號沒問題，版本選單顯示的就是 `[BD][2160p][CHT+JP][Sakurato]`；結尾 `p`/`i` 的標籤依解析度降冪（`2160p` → `1080p` → `720p`），其餘字母序。§7.2 已據此更正。
- **劇集多版本**：未裝插件 → 同一集的兩個檔案變成**兩個重複的 Episode 條目**。裝 MergeVersions 跑 `MergeEpisodesTask` → 合併成 1 個 Episode、2 個 MediaSource，但**版本標籤是整個檔名主幹**而非只有 tags，且順序不保證（10.10 與 10.11 相反）。§7.7 已據此更正。12.x 不裝插件就原生合併，見 §20.9。
- **extras**：劇集層 `<作品>/extras/`、季層 `<作品>/Season 01/extras/`、電影層 `<電影>/extras/` 三者都成立，分別掛在 Series / Season / Movie 的 `SpecialFeatures`，不會被當成正片集數。
- **外掛字幕**：`<stem>.CHT.zh.ass` 在 10.10 顯示 `CHT - Chi - ASS - 外部`、10.11 顯示 `CHT - Chinese - ASS - 外部`（`Title` 欄排最前面，繁簡分得出來）。`.default.` 旗標兩版都生效。`zh-Hant`/`zh-Hans` **只有 10.11 認得**，10.10 顯示「未定義」→ 不採用。
- **深連結** `#!/details?id=…&serverId=…` 在兩個版本都開得到詳細頁（前端正規化成 `#/details?id=…`）。
- **精靈**：`POST /Startup/User` 之前**必須先 `GET /Startup/User`**，否則回 500（`Sequence contains no elements`）—— GET 會先建立預設使用者。`POST /Library/VirtualFolders` 的 body 是 `AddVirtualFolderDto`，`LibraryOptions` **要包一層**（`{"LibraryOptions": {...}}`），直接送會靜默丟掉整份設定。
- **MergeVersions**：`POST /Packages/Installed/Merge%20Versions?assemblyGuid=…` 不必指定版本，10.10.7 裝到 `10.10.0.5`、10.11.11 裝到 `10.11.0.1`；下載由 Jellyfin 連 GitHub，實測遇過 TLS 中斷回 500，要能重試。以上是 M0 時對 10.x 的紀錄；本系統只支援 12 以上、不再安裝它（§19）。排程任務 `Key` 為 `MergeEpisodesTask` / `MergeMoviesTask`，`Name` 為 `Merge All Episodes` / `Merge All Movies`，`Category` 為 `Merge Versions`。
- **重啟後不能只等 `/System/Info/Public`**：它在伺服器還在載入時就回 200，這時管理員 API（如 `/ScheduledTasks`）回 **503「Jellyfin 伺服器載入中」**。要輪詢真正要用的那個端點回 200 才算重啟完成（實測踩到過）。
- **`find_episodes` 的陷阱**：10.11 在第一次掃描後，對已被 provider 認出來的 Series，`/Items?parentId=<seriesId>` 與 `/Shows/{id}/Episodes` **都回 0**，再掃一次才正常；10.10 沒有這個問題，12.0.0 也沒有重現（§20.8）。改用 `parentId=<library>&recursive=true` 再照 `Path` 前綴篩選，四種情況都對。


## qBittorrent 版本矩陣

**qBittorrent 版本矩陣**（2026-09-07，票 04；`lscr.io/linuxserver/qbittorrent:4.4.5`（API 2.8.5）與 `:5.2.3`（API 2.15.1），[完整結果](../research/m0-experiments.md#2-qbittorrent-445-與-523)）

- **`torrents/add` 的回應形狀兩版不同**（2026-09-10 票 09 對 5.2.3 / 4.4.5 兩台乾淨容器實測，fixture 在 `tests/fixtures/http/qbittorrent/torrents-add.*`）：4.4.5 成功回 `200` + `Ok.`；**5.2.3 成功回 `200` 加一份 JSON 摘要**（`{"added_torrent_ids": […], "failure_count": 0, "pending_count": 0, "success_count": 1}`）。**這推翻本節原本記的「一律回 200 `Ok.`」**——那句話只對 4.4.x 成立。失敗也說得出話：同一個磁力連結送第二次在 5.2.3 是 `409 Conflict`（4.4.5 照樣回 `Ok.`），category 的 save path 當下用不了也是 `409`；multipart 上傳一份不是 torrent 的東西是 `415` 加檔名與原因。
- **交一條 http 網址給 `torrents/add` 是背景抓取**：5.2.3 回 `202` + `pending_count: 1`，抓失敗之後**永遠沒有下文**——torrent 不會出現，而用戶端已經回過 2xx 了。所以 Berth 自己先把 torrent 抓下來（`adapters/torrent.py`），交出去的一律是磁力連結或位元組，這樣「收不收」當場就有答案（票 09）。
- **`paused` 與 `stopped` 各版本只認一個，送錯的那個會靜默地開始下載**：4.4.5 `paused=true` → `pausedDL`、`stopped=true` → `queuedDL`（沒暫停）；5.2.3 `paused=true` → `stalledDL`（沒暫停）、`stopped=true` → `stoppedDL`。`torrents/add` 一律回 200，不認得的參數不報錯。plan §8.1 的版本判斷是必要條件，不是最佳化。
- **`torrents/files[].name` 相對 `save_path`**（多檔會含 torrent 根目錄那一層），四種 `contentLayout` 組合都成立；`content_path` = save_path + 根目錄，單檔時指向檔案、多檔時指向目錄。單檔 + `Subfolder` 的子資料夾名是去掉副檔名的 torrent 名。**`save_path` 的尾斜線兩版不同**（4.4.5 `/downloads/`、5.2.3 `/downloads`），組路徑前要正規化。
- **還沒下完時 `content_path` 落在分類的未完成目錄，`save_path` 已經是下完要搬去的那一個**（2026-10-13 M4 票 74 對 5.2.4 實測，e2e 套件內那一台）：`berth-tv` 分類底下停在 `stalledDL` 的一包，`torrents/info` 回 `save_path=/data/torrent/complete/tv`、`download_path=/data/torrent/incomplete/tv`、`content_path=/data/torrent/incomplete/tv/<根目錄>`。`torrents/files[].name` 照樣相對那一層（同上一條，只是那一層換成未完成目錄）。所以刪掉下到一半的那一包看的是 `content_path`，不是 `save_path`（`services/deletion._where_files_are`）。
- `torrents/files` 的鍵兩版相同：`index`、`name`、`size`、`progress`、`priority`、`is_seed`、`piece_range`、`availability`。
- **`torrents/categories` 兩版都回 `savePath`**（駝峰），沒有出現 `save_path`；5.2.3 另有 `download_path`、`ratio_limit`、`seeding_time_limit`、`inactive_seeding_time_limit`、`share_limit_action`。
- **Host 檢查除了網域還比對 port**：`ServerDomains=*` 也擋 port 不符的 Host（實測 `Host: localhost:18080` → 401，容器 log 寫 `Invalid Host header, port mismatch`）。設成 `qbittorrent` 之後 `localhost:8080` 與 `127.0.0.1:8080` 全被擋。沒有 port 的 Host 一律放行。偏好鍵是 `web_ui_host_header_validation_enabled`（兩版都有）。實驗改的是 Web API 的 runtime 偏好 `web_ui_domain_list`，它對應設定檔的 `WebUI\ServerDomains`（同一個設定的兩種寫法），沒有另外測「預置 ini 鍵」那條路徑。→ compose 的 qBittorrent **發佈 port 只能內外兩側一起改**（只改外側，使用者就開不了 WebUI）：M3 票 06b 以 `QBITTORRENT_WEBUI_PORT` 同時設兩側與 `WEBUI_PORT`（plan §9.2）。
- **CSRF**：送了 `Origin`/`Referer` 就必須與 Host 一致（不一致 → 401），完全不送則放行。兩版相同。


## Prowlarr host config

**Prowlarr `config/host`**（2026-09-07，票 04；Prowlarr 2.5.2.5491）

- `GET /api/v1/config/host` 回 39 個欄位；認證相關為 `authenticationMethod`（`none`/`basic`/`forms`/`external`）、`authenticationRequired`（`enabled`/`disabledForLocalAddresses`）、`username`、`password`、`passwordConfirmation`、`apiKey`。
- 設 Forms 帳密：`PUT /api/v1/config/host/1`，body 是完整的 config/host 物件加上上述五個欄位（**少了 `passwordConfirmation` 會被拒**）→ 回 **202**，Prowlarr 隨即自行重啟，要等它回來才能繼續。
- 設完之後：不帶 `X-Api-Key` 的 API 回 401，**`GET /ping` 仍然匿名 200**（所以健康檢查不會因為使用者加了密碼而變紅）。`password` 讀回來是雜湊。
- API key 從 `config.xml` 的 `<ApiKey>` 讀得到（首次啟動即產生，32 字元），與 plan §9.2 的做法一致。


## Jellyfin 帳號規則與 metadata 語言

**Jellyfin 帳號規則與伺服器的 metadata 語言**（2026-10-03，M4 票 29；原始碼 v12.1 的 [UserManager.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Server.Implementations/Users/UserManager.cs)、[StartupController.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/StartupController.cs)、[ConfigurationController.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/ConfigurationController.cs)、[ServerConfiguration.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/MediaBrowser.Model/Configuration/ServerConfiguration.cs)；實測 `scripts/experiments/jellyfin_username_rules.py`）

- **帳號**：`ThrowIfInvalidUsername` 要求不是空白、符合 `ValidUsernameRegex` = `^(?!\s)[\w\ \-'._@+]+(?<!\s)$`、而且不是 `.` 或 `..`；違規丟 `ArgumentException`（`Usernames can contain unicode symbols, numbers (0-9), dashes (-), underscores (_), apostrophes ('), and periods (.)`）→ HTTP 400。.NET 的 `\w` 是 `[\p{L}\p{Mn}\p{Nd}\p{Pc}]`，所以中日文帳號照收；`< > & " / \ : #`、空格以外的空白（tab）都不收，前後不能是空白。master 與 release-12.z 同一條。建立（`CreateUserAsync`）與改名（`RenameUser`）都過它。前端照它先擋（`web/src/setup/jellyfinUsername.ts`）。
- **`POST /Startup/User` 的順序**：第一個使用者已經有密碼 → 403；密碼 `IsNullOrWhiteSpace` → 400 `Password must not be empty`；然後 `UpdateUserAsync`、**名字不同才 `RenameUser`**（帳號在這裡被拒）、最後才 `ChangePassword`。所以帳號被拒時密碼沒設，第一個使用者仍是「沒有密碼」，改個名字再送就好。
- **`GET /System/Configuration`** 掛 `[Authorize]`（任何登入的使用者，API key 也行），回 `ServerConfiguration`：`PreferredMetadataLanguage`（預設 `en`）、`MetadataCountryCode`（預設 `US`）、`UICulture`（預設 `en-US`）——`/Startup/Configuration` 寫的就是這三格。套件內媒體庫照前兩格建（plan §9.4 第 4 步），fixture 在 `tests/fixtures/http/jellyfin/system-configuration.json`。
- **實測**（`lscr.io/linuxserver/jellyfin:version-12.1ubu2604`，一次性容器）：初始精靈期間 `POST /Startup/User` 對 `a<b`、`a>b`、`a&b`、`a"b`、`a/b`、`a`、`a:b`、`a#b`、含 tab、`.`、`..` 都回 **400 `Error processing request.`**（原文不說是帳號的問題，這就是畫面只能說「那一段沒做完」的原因），每一次之後照樣能再試；只有空白的密碼回 400 `Password must not be empty`；`船長 01` 回 204。管理員之後以 `POST /Users/New` 試：`skipper`、`o'brien`、`a.b@c+d-e_f`、`José`、`ナミ`、`..x` 收（200），`a<b`、`.`、` lead`（前導空白）拒（400）。`GET /System/Configuration` 帶 token 200、讀回剛寫的 `zh-TW` / `TW`，匿名 401。


## 硬鏈接腳本

**硬鏈接腳本**（`scripts/experiments/hardlink.sh`，2026-09-07）

- Linux ext4 單一掛載根：PASS（nlink=2、inode 相同）。Windows NTFS bind mount（9p）：PASS（dev=70）。`torrent/` 與 `library/` 分成兩個 volume：`ln: Cross-device link`，退出碼 1。
- ext4 那一輪的來源是 **Docker Desktop 自己的 Linux VM**（`/mnt/docker-desktop-disk/...`），daemon 端的檔案系統，與原生 Linux 宿主是同一條 `link()` 路徑，但**不是另一台實體 Linux**。
- 腳本沒有相依，NAS 上 `sh hardlink.sh /volume1/<share>` 可直接跑。2026-10-08 在 Unraid 7.1.4 的 user share 上直接跑 PASS（§20.14 的 Unraid 那一條）；其他原生 Linux 宿主與 NAS 尚未實測（§20.6）。
