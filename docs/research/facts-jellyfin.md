# 事實：Jellyfin

查證過的外部事實。編號沿用 brief 原本的節號（`§20.x`），程式碼與文件用它引用，編號不重用。索引在 [brief §20](../design-brief.md)。

## 事實

### 20.1 Jellyfin 命名、extras、字幕、多版本、API

來源：jellyfin.org 官方文件、api.jellyfin.org OpenAPI、jellyfin GitHub issues、原始碼。標「未證實」者需實測。每條的完整原文（含 issue / 原始碼連結與實測細節）在 [`docs/research/jellyfin-12.md`](jellyfin-12.md#從-brief-搬來201)，下稱〈研究檔〉。

**命名**

- 劇集資料夾 `Series Name (2018) [tmdbid-12345]`（年份與 ID 可選但建議加，可疊多個 ID）；季資料夾必須是 `Season NN`（不可 `S01`），Specials 放 `Season 00`；集檔名支援 `S01E01`、`S01E01-E02`、`S02E03 Part 1`。（[identifiers](https://jellyfin.org/docs/general/server/metadata/identifiers)、[shows](https://jellyfin.org/docs/general/server/media/shows)）
- 純數字或數字開頭的劇名會讓 metadata 搜尋失敗（[#15860](https://github.com/jellyfin/jellyfin/issues/15860)）→ 用 `[tmdbid-…]` 鎖定可迴避。
- 集號後接方括號 tag 曾讓 AniDB 插件誤判；**核心解析器沒有這個問題**：方括號與 `+` 不滲進 Series / Episode 名稱，Jellyfin 不從檔名取集標題（2026-09-07 實測，§20.6）。
- 檔名中的 ` - ` 會觸發多版本 regex，沒有 Season 資料夾時不同集會被誤併（[#7855](https://github.com/jellyfin/jellyfin/issues/7855)）。本系統一律有 Season 資料夾，§7.1 的格式已實測無誤（§20.6）。
- Extras 子資料夾名：`extras`、`behind the scenes`、`deleted scenes`、`interviews`、`scenes`、`samples`、`shorts`、`featurettes`、`clips`、`other`、`trailers`、`theme-music`、`backdrops`；劇集層與季層都可放；也支援 `-trailer`、`-short`、`-extra` 檔名後綴。（[官方文件原文](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-extras.md)）
- 空的 `.ignore` 檔讓整個資料夾被掃描排除；10.11 起非空 `.ignore` 支援 gitignore 語法。（[excluding-directory](https://jellyfin.org/docs/general/server/media/excluding-directory)）

**外掛字幕**

- 格式 `<影片名>.{flags}.{language}.{ext}`，flags 有 `default`、`forced`、`sdh`/`cc`/`hi`，另可放自由文字標題（旗標在語言碼**之前**）。（[官方文件原文](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-streams.md)）
- 中文語言碼是已知痛點：`chi`/`zh`/`zho`/`zh-hk` 只被辨識為泛「中文」，`cht`/`zh-cn`/`zh-cht` 不被辨識（[#6302](https://github.com/jellyfin/jellyfin/issues/6302)）；`zh-Hant`/`zh-Hans` **只有 10.11 認得**，10.10 退化成「未定義」（2026-09-07 實測，§20.6）。
- 沒有可靠的語言碼能區分繁簡。**已實測採用**：語言用 `zh`，繁簡放自由文字標題，如 `<stem>.CHT.zh.ass`；10.10 顯示 `CHT - Chi - ASS - 外部`、10.11 顯示 `CHT - Chinese - ASS - 外部`，自由文字排最前，兩版都分得出繁簡（§20.6）。

**多版本**

- 電影：同資料夾內 `Movie (2021) [tmdbid-…] - 1080p.mkv`，檔名必須與資料夾名完全一致直到 ` - `；` - ` 之後為版本標籤，結尾為 `p`/`i` 的標籤依解析度排序，否則字母排序。（[官方文件原文](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-multiversion.md)）標籤內含方括號與 `+` 已實測可用（§20.6）；標籤內含中文在 12.x 已實測是純 tag（中文組名 `喵萌奶茶屋`，[jellyfin-12.md](jellyfin-12.md)；10.10 / 10.11 未測，本系統只支援 12 以上）。
- 劇集原生多版本在 10.x 不可靠（12.0 起原生支援，§20.9）：10.8 起要求每集自己一個子資料夾才視為版本，社群回報同一集兩檔通常變成重複條目（[discussion#7900](https://github.com/orgs/jellyfin/discussions/7900)、[#13432](https://github.com/jellyfin/jellyfin/issues/13432)）。結論（10.x）：**劇集多版本必須靠 MergeVersions 插件**，本系統命名只需保證同集檔名的 `S01E01` 部分一致。
- MergeVersions 插件維護到 10.11 與 12.0（12.0.0 版 `targetAbi 12.0`；12.x 上對本系統的樹是空跑、不裝，§20.9）。靠排程任務或設定頁手動觸發，沒有公開 API；本系統用 Jellyfin 排程任務 API 觸發（任務名已實測，§20.7）。已知問題：偶發錯誤、無法停用、跨媒體庫合併。（[README](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/README.md)）

**API**

- `GET /Library/VirtualFolders` 回 `Name`、`Locations[]`、`CollectionType`、`ItemId`、`LibraryOptions`（含 `TypeOptions[].MetadataFetchers`，可偵測 TVDB 插件）。
- 路徑通知：`POST /Library/Media/Updated` 帶 `{Updates:[{Path, UpdateType: Created|Modified|Deleted}]}`；`POST /Library/Refresh` 是全庫掃描；沒有「掃描單一資料夾」的端點。**`UpdateType` 不影響行為**（`LibraryController.PostUpdatedMedia` 對每條都呼叫 `ReportFileSystemChanged(path)`，2026-09-23 讀 master 原始碼），所以 rematch 拆掉的舊路徑照樣以 `Created` 通知（M2 票 08）。【原始碼】
- **路徑通知對「從來沒掃到過內容」的媒體庫無效**（2026-09-15 對 12.0.0 實測 + master `FileRefresher.GetAffectedBaseItem` 原始碼）：等 `LibraryMonitorDelay`（預設 60 秒）後從路徑往上找第一個已存在的 item，初次掃描時空的媒體庫資料夾不成為 item（log `Library folder … is inaccessible or empty, skipping`），於是**不做事也不寫 log**，`POST` 照回 204。套件內媒體庫一開始必空，**第一次入庫一定踩到**（三個媒體庫送三輪，四分鐘後仍 0 item）。與 `EnableRealtimeMonitor` 無關。
- **只刷新一個媒體庫：`POST /Items/{媒體庫 ItemId}/Refresh?metadataRefreshMode=Default&imageRefreshMode=Default`**（2026-10-13 對 12.1.0 實測 + v12.1 原始碼，M4 票 62，`scripts/experiments/jellyfin_scan_scope.py`）。OpenAPI 上與刷新、掃描有關的只有它、`/Library/Media/Updated`、`/Library/Refresh` 三支；它沒有 `Recursive` 參數，但 `ProviderManager.RefreshItem` 對 `CollectionFolder` 會對每個**實體資料夾**遞迴 `ValidateChildren`。網頁控制台「掃描媒體庫」送的就是這一支加兩個 `Default`（它另帶的 `Recursive: true` 伺服器不收），Berth 照它的慣例。收下即回 204（0.08 秒）排進刷新佇列，新集與新劇約 2 秒出現，**同時放進另一個媒體庫的檔案沒被掃到**。
- **它只認得 Jellyfin 已經有的實體資料夾**：實體資料夾由全庫掃描驗證根目錄時建立，而空資料夾當時被略過（`Folder.IsLibraryFolderAccessible`）。所以**第一次掃描時是空的路徑，之後放了檔案，單一刷新與路徑通知都看不到它**（空的電影媒體庫刷新後 90 秒、再送路徑通知後 90 秒都是 0 item）；**只有全庫掃描建得出它**（`ValidateTopLibraryFolders` 只由全庫掃描與新增、移除媒體庫呼叫），建好之後同路徑再放檔，單一刷新 2 秒就看到。**Berth 怎麼判斷**：Jellyfin 已在 Route 的寫入目標底下列出過東西（Series 或 Movie 的 `Path`）就只刷新那個媒體庫，否則跑全庫掃描——空的媒體庫第一次入庫、既有 Jellyfin 的媒體庫剛加上 Berth 路徑時都是後者。（2026-09-15 那次「只刷新那一個 item」量的是空媒體庫，結論範圍寫錯，已更正。）
- `POST /Library/Refresh` 在請求裡**等整次掃描做完**且**掃整台伺服器所有媒體庫**。要「現在掃」又不卡住呼叫端，用內建排程任務 **`RefreshLibrary`**：`POST /ScheduledTasks/Running/{id}` 收下就回；id 從 `GET /ScheduledTasks` 以 `Key` 找（12.0.0 實測 `7738148ffcd07979c7ceb148e06b3aed`）。它同樣掃整台（12.1.0 實測另一媒體庫的新檔一起被掃，四個小媒體庫 4 秒）。**還在跑時再送是空操作**：一樣回 204，`ScheduledTaskWorker.ExecuteInternal` 對執行中任務丟例外而不排隊（v12.1 原始碼）。
- `GET /Items` **沒有 `path` 篩選**。反查：`parentId=<library>&includeItemTypes=Series&fields=ProviderIds,Path` 找 Series（比對 tmdb id 或路徑），再取集並用 `Path` 比對。取集**不要用 `parentId=<series>`**：10.11 第一次掃描後對已被 provider 認出的 Series 回 0 筆（`/Shows/{id}/Episodes` 同），要再掃一次才正常；改用 `parentId=<library>&recursive=true` 再照 `Path` 前綴篩選，四種情況都對（2026-09-07 實測，§20.6）。12.0.0 沒有重現（2026-09-15，§20.8）。
- **`DELETE /Items/{id}` 會刪除磁碟檔案**（`DeleteFileLocation = true`），本系統絕不呼叫它。【原始碼】
- 登入 `POST /Users/AuthenticateByName` 回 `AccessToken`、`ServerId`、`User`；`POST /Auth/Keys` 建 API key。
- 深連結：`{server}/web/index.html#!/details?id={itemId}&serverId={serverId}` 在 10.10.7 與 10.11.11 都能開到詳細頁，前端正規化成 `#/details?id=…`；客戶端自己產生的連結一律不帶 `!`（2026-09-07 playwright 實測，§20.6）。沒有「直接開始播放」的穩定 URL。
- **`serverId` 可以不帶**：12.0.0 登入後直接開 `{server}/web/#/details?id={seriesId}` 照樣畫出詳細頁與季列（2026-09-15 playwright 實測）；10.10 / 10.11 沒測過不帶的形式。Berth 產生的連結不帶它（票 13）。
- **`GET /Items` 每筆都帶 `ServerId`，Episode 另帶 `SeriesId` 與 `SeasonId`**，不必在 `fields` 要（2026-09-15 對 12.0.0 實測）；反查一集時順手知道所屬 Series，媒體庫深連結靠它開到作品而非某一集（票 13）。
- **剛掃進來的 item 有一段時間還沒認完**（2026-09-26 試跑環境 12.1，BLACK TORCH 一季 12 集，記錄在 `docs/archive/m3.md`「M3 後的全面審查」）：`GET /Items` 已列出該 Episode、`Path` 對得上，但 `Name` 是作品名、`ParentIndexNumber` / `IndexNumber` 為空、所屬 Series 沒有 `ProviderIds.Tmdb`；之後同一 item 讀回 `Episode S01E10`、Series 帶 Tmdb。上界約入庫後 12 分鐘（下一次反查碰巧讀到的時間，不是 Jellyfin 真正花的時間）。反查因此先問「認完了沒」再比（`resolver.still_identifying`，M4 票 02）。
- Webhook 插件有 `ItemAdded` / `ItemDeleted`，但走排程批次且社群長期回報不可靠（[#252](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/252)、[#367](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/367)）→ 支持 §9 以排程對帳為主。

**Provider**

- 內建劇集 provider 預設 TMDb（另有 OMDb 與 .nfo）；TheTVDB、AniDB、AniList 都是插件。TVDB 與 TMDB 混用時 Specials 編號錯配有實例（[#13294](https://github.com/jellyfin/jellyfin/issues/13294)）；多 provider 同時啟用時鎖定 ID 也可能被覆寫（[#16268](https://github.com/jellyfin/jellyfin/issues/16268)）→ 支持 §10 單一 TMDB。
- AniDB / AniList 插件的編號語意沒有文件 → 不納入第一階段。

### 20.8 媒體庫瀏覽用的 Jellyfin API（M1.5 前置）

2026-09-15 查證；全文、端點範例與原始碼連結見 [`docs/research/library-browsing.md`](library-browsing.md)。2026-09-15 在 **12.0.0** 上實測，2026-09-17 在一次性的 **12.1.0** 上以只開放部分媒體庫的使用者補測權限、過濾排序、TMDB 反查、標記遞迴與停用帳號（M1.5 票 01，`scripts/experiments/jellyfin_permissions.py`，研究 §0、§2、§3.1、§5、§10、§11；12.0.0 量過的行為在 12.1.0 上沒看到不同，只有圖片 CORS 標頭的條件判定不了）。原始碼對照 tag `v10.10.7`、`v10.11.11`、`v12.0`。

下面每條只留結論、數值與來源；被壓縮的那幾條逐字原文在 [`library-browsing.md`](library-browsing.md#從-brief-搬來208)（大媒體庫那條在 [`large-library.md`](large-library.md#從-brief-搬來208)）。

- **伺服器 API key 可以代讀代寫任何使用者**：API key 在驗證層一律算 Administrator，帶哪個 `userId` 就是誰（三版一致）。用到的端點：繼續觀看 `GET /UserItems/Resume?userId=&mediaTypes=Video`（不帶 `mediaTypes` 會混進 Season 與 Series）、下一集 `GET /Shows/NextUp?userId=`、附 `UserData` 的 `GET /Items?userId=`、已看 / 未看 `POST|DELETE /UserPlayedItems/{id}?userId=`。不帶 `userId` 時 Resume、NextUp、PlayedItems 回 400，`/Items` 回整台伺服器且沒有 `UserData`。NextUp 的 `disableFirstEpisode` 在 12.0 移除。【實測 12.0.0 + 原始碼；研究 §1】
- **媒體庫存取權限只有一部分會套用**（家長分級只要帶 `userId` 就套，這一條只讀原始碼）：`/UserViews?userId=`、不帶 `parentId` / `ids` 的 `/Items`、`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`、`/UserPlayedItems` 等會照使用者的權限；**帶 `parentId` / `ids` / `seriesId` 的查詢，以及帶 `parentId` 的 `/Genres`、`/Years`、`/Items/Filters(2)`、`/Items/Latest` 不會**。而且**使用者自己的 token 也只擋下 `/Items?parentId=<無權的媒體庫>`（401）**，其餘一樣照回。所以權限要由 Berth 自己擋，`parentId` 只放對 `UserViews` 驗證過的媒體庫 id（§12、plan §11.2b）。完整端點表見研究 §2。【實測 12.1.0 + 原始碼】
- **`/Items` 靜默忽略不存在的參數**：實測帶 `seriesId` 或 `ancestorIds` 都回整台伺服器的集，打錯字的 `genre=`、`year=` 回全部（12.0.0、12.1.0）。每個過濾參數都要測「伺服器真的有過濾」。
- **漏帶 `userId`**：`/Shows/{id}/Seasons|Episodes` 回 200 並**略過權限**（無聲洩漏），`/Items/{id}` 回 400，Resume、NextUp、`UserPlayedItems` 回 400。【實測 12.1.0】
- **排序與篩選**（研究 §3）：`sortBy`（逗號、多鍵）加 `sortOrder`；`genres` 以 `|` 分隔（「或」）、`years` 以逗號（「或」），兩個參數之間是「且」。類型與年份清單用 `GET /Items/Filters?userId=&parentId=&includeItemTypes=Series|Movie`（**不帶 `parentId` 四份清單全空**；`Filters2` 沒有年份；`/Years` 不帶 `includeItemTypes` 會混進集的播出年）。劇集的「新集加入」排序是 `DateLastContentAdded`、「最近看過」是 `SeriesDatePlayed`；電影的「最近看過」是 `DatePlayed`。jellyfin-web 的排序選單兩種媒體庫不同（`tvshows.js` / `movies.js`，v10.10.7 與 v10.11.11 相同，清單見研究 §3.1）；`sortOrder` 只送一個時套在每一個鍵上。12.1.0 逐一驗過 `parentId`、`includeItemTypes`、`genres`、`years`、`startIndex` / `limit` 真的有過濾；排序鍵除了劇集庫的 `DateCreated`、`OfficialRating`（只驗到升降冪互為反序）與 `Random` 之外，都驗到照值排序；`sortBy`、`sortOrder`、`genres`、`years` 各有一份錄製給契約測試（票 06）。**`searchTerm` 是名字裡的任一段、不分大小寫**，照權限過濾，照 `sortBy` 排、不換成相關度；參數名打錯（`search=`）被靜默忽略（2026-09-24 在 12.1.0 實測，M2 票 14）。沒有值的排在升冪最前；劇集的分級照高低（`TV-G < TV-PG < TV-14 < TV-MA`）不是照字串。`enableImages=false`、`enableUserData=false` 真的拿掉 `ImageTags` 與 `UserData`，而 `enableTotalRecordCount=false` 在不帶 `limit` 時照樣回 `TotalRecordCount`。【實測 12.1.0】
- **選季選集**：`/Shows/{id}/Seasons?userId=` 與 `/Shows/{id}/Episodes?userId=&seasonId=`（jellyfin-web 詳細頁的查法，會套權限）。§20.1 的「10.11 第一次掃描後回 0」**在 12.0.0 沒有重現**（一次性容器：掃完當下、兩分鐘後、第二次掃描後都對）；10.11 沒有重測，那一條仍成立，後備是媒體庫遞迴查詢照 `Path` 分群（三版都驗過）。
- **一部劇的每一集**（M5 票 28，作品頁與助理分得出「Jellyfin 已有、帳本沒有」）：`/Shows/{id}/Episodes?userId=&isMissing=false` **不帶 `seasonId`** 一次回整部劇每一季的集（含 S00；多集檔帶 `IndexNumberEnd`；都是 `LocationType: FileSystem`），筆數等於逐季加總；**權限照套**：無權的劇一樣 404 `"Series not found"`。不帶 `fields` 也有 `ParentIndexNumber` / `IndexNumber` / `IndexNumberEnd`。`isMissing` 伺服器認得（`true` 回 0 筆，不是被忽略），但 `false` 真的會濾掉 metadata 補出來的虛擬缺集**沒有量到**：一次性的樹關了網路 metadata，造不出虛擬集。Berth 的 `series_episodes` 接受 `locate` 確認過、或從允許清單媒體庫清單（`index`）讀到的 id；NextUp 仍只認 `locate`。【實測 12.1.0，`scripts/experiments/jellyfin_permissions.py` 第 7 節，fixture `shows-episodes.series*.json`】
- **集對 TMDB 的鍵**（M5 票 28，2026-10-30；網路 metadata 開著、TMDB 對上的 SPY×FAMILY 四集）：**集的 `ProviderIds` 沒有 `Tmdb`**，只有 `Tvdb` 與 `Imdb`（值等於 TMDB 那一集的 `external_ids`；`Tmdb` 只在 Series 上），而且要帶 `fields=ProviderIds` 才回。**`PremiereDate` 不帶 `fields` 也有**，形狀是 `YYYY-MM-DDT00:00:00.0000000Z`（那一天的 00:00 UTC），四集都等於 TMDB 的 `air_date`（只量了 `MetadataCountryCode=TW`、`zh-TW`，別的地區有沒有差一天沒量）。metadata 對不上的集 `ProviderIds` 是 `{}`、沒有 `PremiereDate`。所以 Berth 照播出日對（差一天內、TMDB 只有一集的那一集；使用者 2026-10-30 定的「先照 TMDB 的集 id」做不了；照 Tvdb / Imdb 對要 TMDB 逐集的 `external_ids`，一集一個請求，不做），Jellyfin 的季集號不算數（可能照 TVDB 編），只分特典與正片（特典只與特典比）；同一天兩集、兩個 Jellyfin 的集對到同一集、對不上的都不算有，寧可多下一集。「差一天」是使用者定的寬度，沒有量過時區造成的差。【實測 12.1.0，`scripts/experiments/jellyfin_episode_providers.py`，fixture `shows-episodes.series.providers.json`】
- **圖片不需要驗證**：`GET /Items/{id}/Images/{Primary|Backdrop|Thumb}` 匿名 200，請求帶 `Origin` 時回 `Access-Control-Allow-Origin: *`；縮放用 `fillWidth` / `fillHeight` / `quality` / `format=Webp`。`tag` 只是快取鍵（錯的也回圖），URL 要帶 DTO 的 `ImageTags` 才會在換圖時失效。瀏覽器直連的前提是連得到 Jellyfin（與深連結同一個主機），HTTPS 的 Berth 配 HTTP 的 Jellyfin 是 mixed content（[ADR-0004](../adr/0004-library-browsing-and-discovery.md) 已定由 Berth 代理）。
- **經 Berth 代理的圖**（M1.5 票 04，研究 §6.1，12.1.0 實測）：2:3 的原圖帶 `fillWidth=342&fillHeight=513`；**不帶 `format` 時照 `Accept` 挑格式**，所以代理固定送 `format=Webp`；`quality=90` 約 23 KB，jellyfin-web 的 `quality=96` 是它的兩倍多。**Jellyfin 自己存縮好的圖**，所以 Berth 端不另存。`/Items` 帶 `enableImageTypes=Primary&imageTypeLimit=1` 時連 `ImageBlurHashes` 一起回。
- **標為未看會清掉 `PlayCount` 與 `LastPlayedDate`**，復原不了。**對 Series / Season 標記會遞迴到底下每一集**：標已看把看到一半的位置歸零，標未看連之前單獨看過的集一起清掉；對季只動那一季。**遞迴的結果只有清單端點讀得到**（M1.5 票 11 的 e2e）：對整部劇標記之後，`/Items/{集}?userId=` 仍回 `Played=false`，`/Shows/{劇}/Episodes?userId=` 與 `/Items?ids=` 才對（單集自己標記時兩邊都更新）。Berth 讀集一律走 `/Shows/{id}/Episodes`。【實測 12.1.0】
- **由 TMDB id 找作品**：`/Items` 沒有 provider id 過濾參數（猜的參數名都被忽略），但有 `hasTmdbId`。`GET /Items?userId=&recursive=true&includeItemTypes=Series,Movie&hasTmdbId=true&fields=ProviderIds` **不帶 `parentId`** 就會套權限，在 Berth 端比 `ProviderIds.Tmdb`；沒權限的媒體庫裡的那一份不會回來。已知 item id 時用 `/Items/{id}?userId=` 驗可見性（研究 §10）。【實測 12.1.0】
- **jellyfin-web 卡片上的觀看標記**（M1.5 票 05，研究 §7.1，v10.11.11 原始碼）：劇集 `UnplayedItemCount` 非 0 就畫集數，否則 `Played` 或 `PlayedPercentage >= 100` 畫勾；進度條只給影片（`MediaType=Video`）。已看切換不確認、就地改那一格。Berth 的判定照它（`services/watch.py`），但標為未看先確認（上一條：復原不了）。【原始碼】
- **繼續觀看與下一集**（M1.5 票 07，研究 §7.2）：jellyfin-web 首頁兩列一次取 12 / 24 項；NextUp 另送 `enableResumable=false`（**伺服器預設是 `true`**，不送的話看到一半的集兩列都出現）與 `nextUpDateCutoff=今天 − maxDaysForNextUp`（使用者設定，預設 365；伺服器預設沒有截止日）。`mediaTypes=Video`、`parentId`、`nextUpDateCutoff` 各有對照錄製證明伺服器真的過濾（12.1.0）；`enableResumable` 的效果只讀原始碼。**橫卡取圖**順序（自己的 Thumb → 上層的 Thumb → Backdrop → 自己的 Primary → 劇與季的 Primary）與條件見研究 §7.2；**12.1.0 沒有回 `SeriesThumbImageTag`**，劇的 Thumb 在 `ParentThumb*` 那一對。Berth 照這個順序取到集自己的 Primary 為止（電影不取 Primary：2:3 海報填進 16:9 只剩中間一條）。【原始碼 + 實測 12.1.0】
- **劇集詳情頁：這部劇的下一集**（M1.5 票 08，研究 §7.3）：jellyfin-web 只送 `SeriesId` 與 `UserId`。帶 `seriesId` 時**截止日不套用**，`enableResumable` 預設 `true`；「最後看過」是已標記看過的最大季集號，取它之後第一個還沒看完的，Specials 與缺片不算；**從沒看過回 S01E01**，看完了回空（三種情況各錄一份）。`/Items/{id}?userId=` 沒有 `fields` 參數，不必要就帶 `ProviderIds` 與 `UserData`。Berth 照 §10 找作品、以 `/Items/{id}?userId=` 確認看得到之後才問這部劇的 NextUp（帶 `seriesId` 不套權限）。【原始碼 + 實測 12.1.0】
- **沒有直接開始播放的網址**（§12 維持）：三版的 `#/video` 都不吃 item id，「播放某一集」只能深連結到那一集的 `#/details?id=`。
- **帳號狀態**：Jellyfin 停用帳號之後，**API key 代讀這位使用者的 `UserViews`、`/Items`、Resume、NextUp、Seasons 照常回資料，`UserPlayedItems` 照常寫入**；只有他自己的 token 回 401、重新登入回 403。`GET /Users/{id}` 讀得到 `Policy.IsDisabled` 與 `EnabledFolders`（與 `UserViews` 的 `Id` 同一種格式）。所以 Berth 要自己讀 `Policy`（[ADR-0004](../adr/0004-library-browsing-and-discovery.md) 已定）。【實測 12.1.0】**刪除的帳號**（M2 票 11，[`docs/research/large-library.md`](large-library.md) §4）與停用不同：API key 代讀他的**每一支都是 404**（沒有寫入），重新登入 Berth 是帳密錯。Berth 只把 `Users/{id}` 的 404 當成與停用同一種處置（`UserViews` 的 404 可能是位址設錯，仍是問不到）（刪掉他的每一張 session、401 `account_disabled`，使用者拍板）。【實測 12.1.0】
- **大媒體庫的代價**（M2 票 11，[`docs/research/large-library.md`](large-library.md)；1,000 部 × 12 集、全部由 Berth 經手，Docker Desktop 上的量級）：整份清單（`library_index`）1,000 部 318 KB、p95 35 ms；不帶 `parentId` 的 `hasTmdbId` 反查 303 KB、p95 39 ms；**帶整份 `MediaSources` 的集清單 12,000 列 25.9 MB、p95 5.0 s**（不帶是 8.3 MB、0.55 s），約 8 萬集會撞上 Berth 30 s 的 Jellyfin 逾時，分段取總時間不減；**Series 的觀看紀錄很貴**：整份清單打開 `enableUserData` 從 31 ms 變 1.95 s，`ids=` 500 部回 **414 URI Too Long**。plan §11.3 決定 2 的門檻：`GET /inventory/{id}` p95 修正前 3.4 s（Berth 的分組是二次方，不是 Jellyfin）、修正後 0.66–0.68 s；對帳一輪 27–31 s（Jellyfin 那一方 25–29 s）。不做快取、不做分段取。【實測 12.1.0】

### 20.9 Jellyfin 12（2026-09-15 查證）

全文、原始碼行號與實測紀錄見 [`docs/research/jellyfin-12.md`](jellyfin-12.md)。實測對象是一次性的 linuxserver `12.0ubu2604-ls48`（12.0.0）與 `12.1ubu2604-ls49`（12.1.0），跑完即刪；10.x 的對照引 §20.6 與 `m0-experiments.md`。

下面「從 10.11 升級的阻力」逐條原文在 [`jellyfin-12.md`](jellyfin-12.md#從-brief-搬來209)（研究 §4）；其餘各條維持原文。

- **版號**：12.0 就是原本的 10.12，只拿掉永遠不變的 `10`（2026-09-08 發佈；12.1 在 2026-09-15 發佈）。【文件】
- **升級注意的出處**：官方發佈文 [Jellyfin 12.0](https://jellyfin.org/posts/jellyfin-release-12.0/) 的 TL;DR 段（`#tl-dr`：先停機完整備份、移除第三方插件、升級後完整掃描、不能降級）；精靈「既有」選項旁的版本下限連到它（M4 票 17）。【文件】
- **升級是單向的**：10.10.7 或任何 10.11.x 可直接升；資料庫改動讓降級只能靠備份還原。第三方插件要對 .NET 10 重建，10.11 的插件在 12 載入不了。升級後要完整掃描一次，自動分組的版本才會回來。item id 的算法（`MD5(型別全名 + 路徑)`）在 10.11.11 與 12.1 逐字相同，所以一般 Movie / Episode 主條目升級後 id 不變；型別被修正的條目（含自動分組的次要版本）會換 id，缺檔與孤立的條目會被刪。沒有做升級前後逐筆比對的實測。【文件 + 原始碼】
- **從 10.11 升級的阻力**（2026-09-15 補查，`jellyfin-12.md` §4）：**遷移會失敗**（12.0 發佈一週內仍有 12 條遷移、啟動、媒體庫變空的 open issue，其中 #17862 是 12.1 啟動不了；內建的遷移前備份只保護資料庫）；**舊客戶端與整合要升級才能用**（舊式驗證關閉後 Kodi 要 v2.0.0 以上、Seerr v3.0.0、Sonarr / Radarr 要最近的版本；Ombi 與 Jellyfin Vue 的播放仍壞；暫時打開舊式驗證要手改 `system.xml` 的 `EnableLegacyAuthorization`，官方預告下一個大版本移除）；**升級前後**要先移除第三方插件、只差大小寫的兩個使用者名稱會讓遷移失敗、全域字幕設定改到各媒體庫；**一鍵管道沒到齊**（binhex、QNAP 停在 10.11.11；SynoCommunity、TrueNAS 是 12.0；Debian 11 / Ubuntu 20.04 的 apt 已沒有 12；Docker `latest`、官方 apt、Windows / macOS installer 已是 12.1）；帳號、API key、觀看紀錄保留，12 沒有新增 CPU 架構門檻；Kotlin SDK 1.9.0 已把最低伺服器版本拉到 12，新版 Android app 可能反過來要求伺服器是 12【推論】。【文件 + 原始碼 + 官方 issue】
- **劇集原生多版本**（[PR #16828](https://github.com/jellyfin/jellyfin/pull/16828)、官方文件 [`_video-multiversion.md`](https://github.com/jellyfin/jellyfin.org/blob/187351cd69c532a833c9ed57de036297012f5e9e/docs/general/server/media/_video-multiversion.md)）：同一個季資料夾裡解析出同一個 `S/E` 的檔案，併成同一集的多個 MediaSource。
  - **分組鍵只有季號與集號，不含集名與結束集**：`S01E03-E04` 與 `S01E03` 同季時被當成同一集的兩個版本，第 4 集從集列表消失（實測；本系統的處理見 §7.8）。
  - 12.1 起季號與集號都要解析得出才分組（[PR #17890](https://github.com/jellyfin/jellyfin/pull/17890)）。
  - 本系統的命名在 12.0.0 與 12.1.0 不裝插件就合併，新版本在路徑通知後 100 秒內併入，外掛字幕掛在對的版本上。
  - 版本名是去掉各版本檔名共同前綴後剩下的部分；順序依解析度降冪，再依檔名。
  - 電影規則不變：檔名仍要以資料夾名開頭，分隔符多接受 `_`、`.`、`[`。中文組名的標籤是純 tag。
  - 【實測 + 原始碼 + 文件】
- **MergeVersions**：manifest 有 `12.0.0`（`targetAbi 12.0`），不指定版本的安裝在 12.x 會挑到它。但它在 12.x 上對本系統的樹是空跑：log 是 `Found 5 episodes and 0 duplicate episode groups`，合併前後來源數與名稱不變。原因是原生分組的次要版本帶 `PrimaryVersionId`，一般查詢會濾掉它們，插件湊不成一組。它的分組鍵不看資料夾與媒體庫，會跨媒體庫合併【原始碼推論】。【實測 + 原始碼】
- **本系統用到的 24 支端點**在 12.0 / 12.1 都在、授權政策相同，以本系統的 adapter 跑完 plan §9.4 整段。例外兩條：
  - `POST /Startup/User` 在第一個使用者已有密碼時回 **403**（[PR #17369](https://github.com/jellyfin/jellyfin/pull/17369)）。精靈第 3 步做完、後面某步失敗、Jellyfin 沒重啟時按重試，會一直卡在這裡（M1 票 14b）。【原始碼 + 部分實測：精靈未完成時匿名送的那條只讀了原始碼】
  - `POST /Startup/Configuration`、`GET /Startup/User`、`POST /Startup/RemoteAccess` 在 12.x 的 OpenAPI 標 deprecated，現在還能用。Jellyfin 的政策是至少標滿一個大版本週期才移除，所以 13.0 發佈前要換成設定端點（替代端點的欄位【未查】）。【實測 + 文件】
- **伺服器名稱**（2026-10-07 查證，M4 票 52）：`POST /Startup/Configuration` 的 body 是 `StartupConfigurationDto`，`ServerName` 與另外三格同一層、都可為 null。它**整格覆寫**：`ServerName = dto.ServerName ?? string.Empty`，沒送就是空字串。名稱是空字串時 `/System/Info/Public` 的 `ServerName` 報 `Environment.MachineName`，在容器裡就是容器 ID——所以沒設過的那一台重建容器就換名字（§20.15 的實測）。12.1 與 12.2 這兩段逐字相同。來源：[OpenAPI](https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json)（12.2.0；`StartupConfigurationDto` 四格都是 nullable string，端點標 deprecated）、[`StartupController.cs`](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/StartupController.cs)（`UpdateInitialConfiguration`）、[`StartupConfigurationDto.cs`](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Models/StartupDtos/StartupConfigurationDto.cs)、[`ApplicationHost.cs`](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/ApplicationHost.cs)（`FriendlyName`）。【文件 + 原始碼】
- **舊式驗證預設關閉**，連既有安裝也由遷移關掉：`X-Emby-Token`、`X-Emby-Authorization`、`?api_key=` 回 401。本系統用的 `Authorization: MediaBrowser …, Token="…"` 不受影響。【實測 + 原始碼】
- `GET /Items` 帶 `includeItemTypes` 而沒指定 `recursive` 時預設遞迴（2026-09-17 在 12.1.0 實測，§20.8），本系統一律明確帶 `recursive=true`。`POST /Library/Media/Updated` 背後的 `FileRefresher` 一行沒改，所以「空的媒體庫收到路徑通知無效」（§20.1）仍成立。【原始碼 + 前半句實測 12.1.0】
- **linuxserver image**：
  - tag 變成 `12.0ubu2604-ls48`、`12.1ubu2604-ls49` 這種形式。
  - `latest` 已是 12.1。
  - 舊 tag 會保留，另有跟著同一版號重建的 `version-12.1ubu2604`。所以 `m0-experiments.md` 當時寫的「只保留最新 tag，釘不了版本」不成立。
  - Dockerfile、`/config`、8096、`PUID` / `PGID` 都不變。
  - 【實測 + 原始碼】

### 20.15 「同一台 Jellyfin」怎麼認：ServerId（2026-09-30 查證＋實測，M4 票 18）

全文與來源在 [`docs/research/deploy-and-jellyfin-identity.md`](deploy-and-jellyfin-identity.md)。

- **`GET /System/Info/Public` 的 `Id` 就是伺服器的 `SystemId`**，匿名讀得到；它是第一次啟動時寫進 `<DataPath>/device.txt` 的 GUID（[DeviceId.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/Devices/DeviceId.cs)、[ApplicationHost.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/ApplicationHost.cs)）。
- **實測**（linuxserver 12.1.0 與 10.10.7；`scripts/experiments/jellyfin_server_id.py`）：同一台換位址連（`localhost`、`127.0.0.1`、`host.docker.internal`）、`docker restart`、`--force-recreate`（`/config` 還在），`Id` 都不變；三台不同的 Jellyfin 各自不同。
- **`ServerName` 不能拿來認**：沒設過時是容器的 hostname，重建容器就變。
- 所以 Berth 以 `Id` 判「同一台」：擁有者成立時記下，之後換位址只接受 `Id` 相同的（[ADR-0012](../adr/0012-owner-is-jellyfin-admin.md)、plan §9.3）。擁有者成立**之前**也用它：頁 1 的表單帶回測過的位址與 `Id`，與存下的不同就不送帳密（M4 票 28；未初始化的那一台也有 `Id`）。清掉 `/config`（或複製別人的 `/config`）的那一台會換 `Id`（或撞 `Id`）——前者等於一台新的伺服器，擁有者帳號也不在了；後者不防。

### 20.22 Berth 登入 Jellyfin 留下的裝置（2026-10-14 查證，M4 票 66）

- Berth 以 `Authorization: MediaBrowser Client="Berth", Device="Berth", DeviceId="berth-server"` 呼叫 `AuthenticateByName`（`adapters/jellyfin/client.py`）。Jellyfin 的 `SessionManager.GetAuthorizationToken` 先找同一個 `DeviceId` **且同一個使用者**的裝置、逐一登出（刪掉那一列），再建一筆新的、發新的權杖。所以**登入過 Berth 的每一位使用者在 Jellyfin「裝置」頁各一筆 Berth**，同一位再登入是換掉自己那一筆，不會越積越多；別的使用者的那一筆不刪，但同一個 `DeviceId` 的進行中工作階段會被結束。【[SessionManager.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/Session/SessionManager.cs)（`AuthenticateNewSessionInternal`、`GetAuthorizationToken`、`Logout(Device)`）】
- 審計 S3 實跑看到的「`/Devices` 多一筆 Berth」就是這一筆（`docs/research/usability-audit-2026-10-07.md` 附錄 C.1）。
