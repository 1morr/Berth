# Berth

自託管的媒體取得與入庫協調器：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析、比對 TMDB、以硬鏈接入庫到 Jellyfin，並維護可修復的帳本。本檔只是名詞表；決定與事實在 `docs/design-brief.md`，實作在 `docs/plan.md`。

## Language

### 媒體與目的地

**Media**:
TMDB 上的一部電影或一部劇集，鍵為 `movie:<tmdb id>` / `tv:<tmdb id>`；劇集底下有 Season 與 Episode，編號沿用 TMDB。
_Avoid_: title, show, series, item

**Tracked Media**:
Berth 曾為其下載、訂閱或入庫過的 Media。
_Avoid_: subscribed media, library item

**Display Round**（顯示用那一輪；沒有 UI 文案）:
TMDB 對同一部 Media 回的兩輪資料裡，畫面照 UI 語言挑的那一輪：`zh-Hant` 取 `zh-TW`、`en` 取 `en-US`
（brief §7.5）。成對的欄位一律是 `x` / `x_en`——`title`、`overview`、`poster_url`（M1.5 票 11 起海報也成對，
TMDB 的海報分語言），下載列是 `media_title`。**後端不知道 UI 語言**：兩輪都送，前端 `i18n/displayRound.ts` 挑一個，
換語言當場換、不重抓。`title_en` 同時是檔名與比對用的那一個，不跟 UI 語言走（brief §7.5、§5）。
_Avoid_: locale, translation（那是 TMDB `translations` 端點）, localized title

**Library Route**（UI 顯示「媒體庫」）:
一個入庫目的地：Jellyfin 媒體庫、一個寫入目標路徑、一個 qBittorrent category。
_Avoid_: root folder, destination；程式碼中不要用 `library` 指 Route（`library` 一律指下一條的 Jellyfin Library）

**Inventory**（UI 顯示「媒體庫」頁）:
一個 Jellyfin Library 的整面牆（這位使用者在 Jellyfin 看得到的那幾個之一），疊上 Berth 經手作品的入庫
狀態。牆上是 Jellyfin 的每一部作品、分頁與排序照 Jellyfin，可依類型、年份篩選（M1.5 票 06，只篩 Jellyfin 那一頁）；Berth 經手的作品是指向這個媒體庫的每一條 Route 上
有 Job 的，加上帳本目標落在它們底下的——在 Jellyfin 裡的疊到那一格，還沒進的另列一條。M1（票 13）時
它是一條 Route 一頁、只有 Berth 經手的作品，M1.5 票 03 改成現在的定義。
_Avoid_: library（程式碼中，那是下一條的 Jellyfin Library）, collection, shelf

**Narrowing**（UI 顯示「類型」「年份」）:
Inventory 牆上依類型、年份縮小 **Jellyfin 那一頁**（M1.5 票 06）；同一種之間是「或」、兩種之間是「且」。它和牆的排序合稱
**Wall Query**（`WallQuery`：`sort`、`order`、`genres`、`years`，M2 票 14 起加上名字——網址與 API 是 `q`、後端欄位是
`search`、轉給 Jellyfin 是 `searchTerm`，同一件事）。按名字找也算 narrowing（它讓作品不見，排序不會）。選項清單在程式碼裡
叫 `filters`（`/Items/Filters`、`GET /api/inventory/{id}/filters`），沿用 Jellyfin 的名字；前端的開關與面板叫 narrowing。
**不是**「待審」「Unmatched」那兩個 filter：那兩個是 Review Queue 在這個媒體庫上的子集（M2 票 14），Jellyfin 的類型與名字
套不上。
_Avoid_: filter（指類型、年份時）, facet

**Watch State**（UI 顯示「觀看狀態」）:
一位使用者在 Jellyfin 對一部作品（或一集）的觀看紀錄，Inventory 的卡片上一行字：**已看**、**看到 N%**（只有影片）、
**剩 N 集沒看**（只有劇集，沒開始看的也算），都不成立就是還沒看過。紀錄存在 Jellyfin、屬於那個人，Berth 不存；
Berth 只讀它，並替那個人**標為已看 / 標為未看**（寫回 Jellyfin）。標為未看會清掉觀看次數與最後觀看時間，對劇集是
每一集，復原不了；標為已看會把看到一半的位置歸零（對劇集是每一集），所以兩者清得掉東西時都先確認（M1.5 票 08）。
_Avoid_: seen, history, played state

**Resume**（UI 顯示「繼續觀看」）:
一位使用者在 Jellyfin 看到一半的集與電影（Jellyfin `/UserItems/Resume`），最近看的在前；卡片說的是看到幾 %，看過又重看
到一半的片也算。只在 Inventory 頁上方，只含那個 Jellyfin Library 的（M1.5 票 07；首頁那一份整個帳號的，M3 票 06 隨探索頁只放 TMDB 牆拿掉）。
_Avoid_: continue, in progress, recently watched

**Next Up**（UI 顯示「下一集」）:
一位使用者每部看過的劇的下一集（Jellyfin `/Shows/NextUp`）：最後看過的那一集之後、還沒看的第一集。看到一半的集不算
（它在 Resume），一年內沒看過的劇也不算（jellyfin-web 的預設）；範圍同 Resume。兩者合稱 **Watching**
（`services/watching.py`、`WatchingOut`）。
_Avoid_: upcoming, next episode（TMDB 的「下一集播出」是另一件事）, queue

**Watch Area**（UI 顯示「觀看」）:
Media 詳情最上面那一塊：作品在 Jellyfin 裡、而且這位使用者看得到時才有——身分帶裡的主按鈕（**Carry On**），加上 Jellyfin
的季切換與那一季的集（`services/watch_area.py`、`GET /api/media/{id}/watch`，M1.5 票 08）。季與集是 Jellyfin 的，不是 Media 的
Season / Episode（那一份在下面的「季集與入庫」）。不在 Jellyfin 與看不到是同一個答案：沒有這一塊。
_Avoid_: player, playback area, library detail

**Carry On**（UI 在主按鈕上：「繼續看」「看下一集」「從 S01E01 開始看」）:
這位使用者接下來看這部劇的哪一集：Jellyfin 的 NextUp 帶 `seriesId`——看到一半的那一集也算、沒看過是第一集、看完了就沒有。
與 **Next Up** 不同：那是 Inventory 頁上方一整列、每部看過的劇一格，看到一半的不算、沒看過的劇不列。電影沒有 Carry On，主按鈕開那一部。
_Avoid_: next up（指這一顆時）, resume point, up next

**Jellyfin Library**（UI 顯示「Jellyfin 媒體庫」）:
Jellyfin 那一端的 virtual folder：一個名字、一個 collection type、**一到多條**路徑。Berth 不擁有它——
套件內的 Jellyfin 由 Berth 建使用者在精靈列的那幾個（預設 Movies / TV / Anime，每個是內容類型 + 名稱 + `<library root>` 底下一層的資料夾），建好之後改名與刪除在 Jellyfin 做；既有的一律只讀，最多加一條路徑。既有 Jellyfin 缺某類型的媒體庫時，使用者在頁 3 勾了「新建一個媒體庫」Berth 才建那一個（`<library root>/<slug>`，M4 票 64），之後與其他媒體庫一樣。
一個 Library Route 指向它的其中一條路徑。程式碼中的 `library` 指的就是這個。
_Avoid_: virtual folder（對使用者時）, folder, collection

**Library root**:
媒體庫路徑的父目錄（設定值，預設 `/data/library`）。Berth 與 Jellyfin 把同一個宿主目錄掛在同一個
容器路徑，所以這一個字串對兩邊都成立。
_Avoid_: media root, library path（那是單一媒體庫的路徑）

**Berth path**（UI 顯示「Berth 寫入」）:
Library root 底下、Berth 寫入用的那一條路徑（`<library root>/<slug>`）。既有 Jellyfin 是**加**這一條，
舊路徑原地不動。
_Avoid_: target path（那是 Route 上的欄位）, new path

**Complete / Incomplete root**:
Berth 分類的完成與未完成下載根目錄（固定 `/data/torrent/{complete,incomplete}`）；每個 Route 的分類是底下的
`<slug>`，complete 是硬鏈接的來源。未完成目錄開在分類上，不是 qBittorrent 的全域 temp path。
_Avoid_: download folder, save path（僅指 qBittorrent 的欄位時可用）

### 設定

**Service**:
Berth 協調的三個外部服務之一：Jellyfin、qBittorrent、Prowlarr。字串同時是 compose 的服務名。
_Avoid_: integration, provider（Provider 專指 metadata provider）

**Service Origin**:
使用者在精靈替單一服務選的來源：`bundled`（套件內，Berth 代為設定）或 `existing`（既有，使用者自己的那一台）。
逐服務選，沒有全局模式；**是使用者的選擇，不是 Berth 偵測出來的判定**（2026-09-29 起，brief §16.3；之前是偵測）。選完要測試，套件內的測試在容器還在啟動時（連不上、回 503、回的東西不像它自己，M3 票 06g）照舊輪詢，那是測試的狀態，不是來源。**與 Trigger 的「來源」無關**。
_Avoid_: mode, service type

**Bundled service**（UI 顯示「套件內」）:
使用者選「套件內」的服務：這套 compose 起的那一台（容器名 `berth-*`，Berth 以 compose 服務名連它）。
Berth 在它上面做的與 Existing service 同一條——只建立與管理 Berth 擁有的物件——差別只在 Berth 讓它有人登得進去：
Jellyfin 的管理員與初始設定（含伺服器名稱「Berth」）、qBittorrent 與 Prowlarr 的介面登入，以及讓 Berth 自己進得去的免密白名單與掛載的 API key。
套件內 Jellyfin 的媒體庫照精靈的清單由 Berth 建，也算 Berth 擁有的物件。全域偏好不寫（brief §19 D1、D2，M4 票 32、33）。
套件內 Prowlarr 的「移除」只給 Berth 加的站（`added_sites`）；使用者自己加的、票 47 之前沒有紀錄的都不給（M4 票 66）。
已經初始化過的（重裝保留 config）照樣是套件內，只是改成登入。
_Avoid_: managed, built-in, ours

**Existing service**（UI 顯示「既有」）:
使用者選「既有」的服務：使用者自己的那一台，填位址與憑證接進來。Berth 接管它＝**只建立與管理 Berth 擁有的物件**：
Jellyfin 的 API key「Berth」、媒體庫上的 Berth 路徑、使用者在頁 3 勾選後新建的媒體庫（M4 票 64）、`berth-*` 分類與它的目錄、使用者勾選加入的站、檢查用的暫時探測 torrent 與探測檔。
執行期還有（M4 票 66）：送出的 torrent 帶 tag `berth`（刪 Job 時請 qBittorrent 只移除 torrent、不刪檔；勾了刪檔是 Berth 自己刪）；送單前 `ensure_category`，使用者刪掉的 `berth-*` 分類會照 Route 重建；登入過 Berth 的每位 Jellyfin 使用者在 Jellyfin 留一筆裝置「Berth」。
入庫之後 Berth 也會請 Jellyfin 去看它寫的路徑：通知路徑、只刷新那個媒體庫；Berth 的路徑 Jellyfin 還沒列出過任何東西時是整台的全庫掃描（brief §16.4、§20.1，M4 票 62）。
帳密、全域偏好、使用者原有的媒體庫與站都不碰；唯一例外是那台 Jellyfin 還沒跑過初始精靈時，由擁有者建它的管理員、跑完它的初始設定（語言、地區、遠端存取；不給伺服器名稱，brief §16.4、§19 D1）。
Jellyfin 與 qBittorrent 必須與 Berth 同一台主機、把同一個父目錄掛在 `/data`。
_Avoid_: external, remote, byo

**Interface login**（UI 顯示「介面登入」）:
套件內 qBittorrent / Prowlarr 自己的登入：給使用者打開那一台的網頁介面用，Berth 自己用不到（qBittorrent 靠免密白名單、Prowlarr 靠 API key）。精靈頁 2、頁 4 設，之後在「設定 → 該服務」換。既有的那一台 Berth 不碰。兩個服務同一個叫法（M4 票 103）。
_Avoid_: WebUI 登入、WebUI login（`web/src/i18n/interfaceLoginName.test.ts` 守 `web/src`）。照留的：qBittorrent 自己的選單路徑「選項 → WebUI」，以及後端與文件裡指它的偏好鍵 `web_ui_username`、既有那一台連線帳密的「WebUI 帳號／帳密」——那是 qBittorrent 的東西，不是這個登入

**Unused service**（UI 顯示「沒有使用」，設定頁的動作叫「不用 Prowlarr」）:
管理員選了不用的服務；目前只有 Prowlarr 可以（M4 票 61，審計 E3）。與精靈頁 4 的「之後再說」是同一個狀態，
存在 `setup.indexer.skipped`、API 的健康那一列是 `unused`。可逆；不用時健康不檢查它、不算阻擋，搜尋說沒有接索引站。
Berth 不動它上面的站與容器。**與 Step status 的 `skipped` 無關**——那一個是「已經是這樣」。
_Avoid_: disabled, removed, off

**Step status**（UI 顯示於每一條纜繩）:
精靈裡一個步驟的結果，五種：`ok`（已完成，這一次真的做了）、`skipped`（已經是這樣，沒動它）、
`running`（進行中，做之前就寫進設定所以輪詢看得到）、`failed`（失敗）、`pending`（尚未執行）。
**`skipped` 不是「跳過不做」**，是「已經是想要的樣子」——重按精靈時大部分步驟都會是它。
_Avoid_: success/error（那是 HTTP 的詞）, done（`ok` 與 `skipped` 都算做完）

**Berth（泊位）**:
設定精靈的五格，一格一頁（之後是完成頁）：Jellyfin、qBittorrent、媒體庫路徑、Prowlarr、TMDB。
一格一個服務（M3 票 06e 把原本的「來源」拆成索引站與 TMDB 兩格；2026-09-29 起 Prowlarr 與索引站同一格、拿掉格子前的擁有者與偵測兩步，擁有者就是 Jellyfin 那一格的結果）。
用在精靈、健康頁的泊位板與設定頁（一格一頁，同一個順序，M3 票 06i）；與產品名 Berth 同字，指的是畫面上那一格。
_Avoid_: stage, section, panel

### 取得

**Download Job**（簡稱 Job）:
一個 torrent 在 Berth 中的生命週期紀錄，以 info hash 為鍵。
_Avoid_: torrent（指 Job 時）, download, task

**Trigger**:
Job 的來源：`manual`、`rss`（`trigger_ref` 是 RSS Series id）、`reimport`。
_Avoid_: source, origin

**Indexer Result**:
索引站的協定回的原始一列：發佈名、大小、做種、來源站、下載連結、info hash、發佈時間。**還沒經過解析器**。
_Avoid_: hit, item, row

**Search Result**:
索引站回傳的一筆候選 torrent，附解析出的 Tags 與預估季集。也就是 Indexer Result 過了解析器之後的樣子。
它的下載連結不出伺服器（帶著 Prowlarr 的 API key）：畫面拿到的是**來源 id**（`source_id`），送單只收它，
Berth 記兩小時、重啟就忘（M4 票 79）。一次性 RSS 連結讀出來的每一筆也是。
_Avoid_: release（僅指發佈名解析時可用）

**Search Verdict**（UI 是篩選按鈕上的類別名）:
作品搜尋裡一筆 Search Result 歸到的那一類，帶著觸發的那一段字當證據（M4 票 83）：符合、年份不符、不是電影（電影搜尋讀得出 `S04E02`
或字幕組的 `- 05`）、成人分類、只對上部分名字（可能是衍生作品，`Law.and.Order.SVU`）、名字對不上。一筆只歸一類（排了先後的粗篩）。
每一類都送到畫面，預設只列「符合」，其他類按了才看，因為判斷只看發佈名。自己打關鍵字時只分「對得上」「對不上」（發佈名含不含打的字或作品的名字，M4 票 83b），不判是不是這部作品。
取代 M4 票 49、69 的「收起來」（Set Aside）與「略過」（discarded）。
_Avoid_: set aside, discarded, filtered, rejected, 過濾掉、收起來

**Search Name**（UI 是搜尋面板上的名字 chip，帶「英文名」「原名」「中文名」「簡體中文名」「別名」）:
作品搜尋拿去問的一個名字，與它是哪幾種（Name Kind）。由人開關（M4 票 84）；種類的開關全域記住，在一部作品開了中文名，
每一部打開時都開著。別名分不出語言，不記、預設關。查詢是開了的名字 × 開了的季（「不指定季」與逐季）。
_Avoid_: title variant, alias（只指「別名」那一種）, 標題變體

**Missing Episode Search**（UI 顯示「搜這部作品缺的集」/「搜 S01 缺的集」）:
從季表上缺的那幾集開始的搜尋：查詢由後端依缺的季集產生（整季缺問季包、缺幾集逐集問、有絕對編號的用絕對編號），
配上開了的 Search Name，不是作品名本身。範圍是整部作品或一季。季記號放不下一次搜尋的查詢上限時**分批**（batch）：每一批是一組季，
問完一批由人按「問下一批」（M3 票 20）。
_Avoid_: gap search, 補集, 一鍵補齊

### 入庫

**Import Source**:
待入庫的檔案集合：Job 的內容目錄，或 complete 下的任一目錄（重新入庫時）。
_Avoid_: input, folder

**Release Info**:
從發佈名或檔名解析出的結構化欄位（標題候選、季、集、版本、字幕組、來源、解析度、字幕語言…）。
_Avoid_: parse result, metadata

**Tags**:
一個檔案版本的可辨識屬性集合（source、resolution、subs、hardsub、group、version、edition），以固定 token 渲染進檔名。
_Avoid_: quality, flags, labels

**Candidate**:
對一個影片檔的一種季集對應，附策略、信心與理由。
_Avoid_: match, guess

**Mapping Strategy**（簡稱 Strategy）:
Candidate 的季集是怎麼決定的：explicit / folder / context / arc_name / single_season /
absolute_group / absolute_cumulative / air_date_offset / cour_offset / published_run / movie。
_Avoid_: method, rule, source

**Arc name**（篇章名）:
一輪播出的名字而不是季號（`柱訓練篇`、`Hashira Training Arc`、`最終季`）。對到 TMDB 的季名就
等同季號提示。
_Avoid_: subtitle, part name

**Cour**:
同一季裡的一輪播出（`第二部分` / `Part.2`）。字幕組可能每個 cour 從 01 重數，也可能季內連號。
_Avoid_: part（`Part 2` 是檔名裡的寫法，不是這個概念的名字）, half

**Virtual season**（虛擬季）:
TMDB 把好幾輪播出併成一季時，用季內 `air_date` 間隔（> 180 天）切回來的那一輪。
_Avoid_: split season, sub-season

**Import Plan**（簡稱 Plan）:
對一個 Import Source 逐檔決定分類、對應 Media / 季 / 集、目標路徑、Tags、信心與理由的可審核計劃；套用前不動任何檔案。
_Avoid_: mapping, import job, rename plan

**Pre-plan**（預先計劃）:
`metadata_ready` 之後、下載完成之前先算的那一份 Plan（`plans.status = preplan`）：不讀檔案、不動狀態，只回答「這一包對不對、還來得及取消嗎」。
_Avoid_: draft plan, preview

**Review Reason**（停下來的理由）:
一份 Plan 停在 review 的七種理由：`low_confidence`、`medium_not_allowed`、`nothing_to_import`、入庫途中目標上已經有別人的檔案的 `target_exists`、管理員撤銷了一個 Audit 的 `audit_undone`，發佈時間與換算出的那一集的播出日對不上的 `air_date_conflict`（**播出日比對**，M3 票 14），以及量到的片長與 TMDB 那一集差太多的 `runtime_conflict`（**片長驗證**，M3 票 15）。七種的下一步不同，所以是封閉集合而不是一句話。停在 review 的 Plan 由管理員**核准**（照提案入庫）或**重新規劃**（丟掉這一份、照目前的 TMDB 資料與設定重算；票 106 之前 UI 叫「拒絕」，端點、`PlanStatus.REJECTED` 與事件仍叫 reject / rejected）。
_Avoid_: error, message

**Air-date check**（UI 顯示「播出日比對」）:
規劃時拿來源的**發佈時間**（索引站的 `publishDate`、Feed Item 的發佈時間，存在 Job 上）比換算出的那一集的 TMDB 播出日：發佈早於播出日超過兩天，或 RSS Series 對到的那一集比作品在發佈當時最近播出的一集早很多，那一列就停下來等人，Plan 的 Review Reason 是 `air_date_conflict`。抓的是規則層有把握卻算錯的集數（offset、絕對編號），不是信心。
_Avoid_: freshness, age score

**Runtime check**（UI 顯示「片長驗證」）:
規劃時拿 mediainfo 量到的片長比換算出的那一集的 TMDB 片長，差太多的那一列停下來等人，Plan 的 Review Reason 是 `runtime_conflict`。抓的是分類錯誤（SP、OVA、兩集合併的檔案被當成一集正片），不是集數；短於五分鐘的「正片」由分類器自己降成 extra，不歸它管。
_Avoid_: duration score, length filter

**Landing**（核准後的落點）:
一份停在 review 的 Plan 上每一列「核准的話會寫到哪裡」：待審核的列照提案算、字幕跟著影片，與核准時真的寫進 Plan 的是同一次計算，所以畫面上看到的就是 importer 待會兒鏈接的那一條。還沒有提案或不會進媒體庫的列沒有落點。
_Avoid_: preview path, target preview

**Plan Item**:
Plan 中一個檔案的決定，`action` 為 import / extra / subtitle / skip / unmatched / review。它的理由是封閉集合的 code 加參數（`ReasonCode`），句子在畫面上翻。
_Avoid_: entry, row

**Confidence**:
Plan Item 的三級信心：high、medium、low。high 與 medium 自動入庫，low 進 Review Queue。
_Avoid_: score, probability

**Audit**:
medium 信心自動入庫後掛的旗標（`plan_items.audit` 與 `ledger.audit` 各一份，importer 抄過去），在 Review Queue 顯示為「已入庫待確認」。RSS Series 送的另有一條：**第一批**確認之前 high 也掛，確認之後 medium 也不掛（M3 票 13）。**確認**清掉兩處旗標並記 event；**撤銷**刪掉硬鏈接與那一列帳本，Job 回 review（`review_reason = audit_undone`），那一列 Plan Item 回到沒有提案——撤銷說的是「這一集不對」，原樣再核准不行。
_Avoid_: pending, provisional

**Folder Name**（資料夾名）:
作品在媒體庫裡的資料夾：`Title (Year) [tmdbid-N]`。在第一次送單成功那一刻凍結，之後 TMDB 改名不動它，計劃與入庫都照凍結的那一串寫；在那之前它跟著標題走，畫面上是「將會是」。
_Avoid_: directory name, slug（slug 是 Route 的）

**Version**（版本）:
同一集或同一部電影並存的其中一個檔案，以 Tags 區分。版本選單上的名字由 Jellyfin 算（12 起原生合併），Berth 只抄下來。
_Avoid_: copy, duplicate（Tags 完全相同的才是重複）

**Resolve**（反查）:
入庫之後向 Jellyfin 問出那個檔案是哪一個 item（劇集再加它的 Series）。延遲、會重試，排程存在帳本上；打開作品頁時還沒到時間的那幾列先問一次，找到才算、沒找到不算一次（M4 票 51）。Jellyfin 列出了 item 但還沒認完（季集、作品是空的）不算找到。找到之前卡片說「Jellyfin 還在掃描」。
_Avoid_: sync, lookup, match

**Ledger Entry**:
一條「來源檔案 → 目標硬鏈接」的紀錄，含 hash、來源相對路徑、目標路徑、inode、Media / 季 / 集、Tags、plan item、Jellyfin item id。
_Avoid_: link record, file record, history

**Benchmark Corpus**（語料）:
凍結的真實 torrent 檔案清單加上逐檔正解與 TMDB 快照（`tests/fixtures/parser/`）。`berth bench` 在它上面量解析器，門檻是 `auto_wrong`（自動處置但處置錯）不得上升。e2e 也從它取三包發佈。
_Avoid_: dataset, test data

**Extras**:
可辨識但不屬於正片的內容（NCOP / NCED、PV、CM、Menu、預告、花絮、特典映像），入庫到 Jellyfin 的 `extras/`。
_Avoid_: bonus, specials（Specials 指 TMDB season 0）

**Unmatched**（zh-Hant UI 顯示「對不到」）:
解析後對不到 TMDB 任何一集或一部的影片或字幕檔；留在 complete，不入庫。同時是 Plan Item 的一個 `action`：不是低信心而是一個已經做完的決定，不擋自動入庫，但數進 `summary.low` 讓畫面看得見。程式碼、文檔與英文 UI 一律用
`Unmatched`；zh-Hant 的文案從 M1.5 票 11 起翻成「對不到」（原本直接印英文，與旁邊的「待審」並排讀不順）。
_Avoid_: unknown, orphan（Orphan 是對帳用語）

**Review Queue**:
需要人決定入庫的統一清單：低信心 Plan、Audit、Unmatched、重複版本。一列一件事、需要人動手的排前面；不是一面牆。只有 admin。Issue 不在裡面（M3 票 05），它只在 `/issues`。
Inventory 的「待審」「Unmatched」兩個 filter 是它在一個媒體庫上的子集（M2 票 14）：`plan` 與 `unmatched` 兩類、Job 的 Route
指向那個媒體庫的，列與 `/review` 同一個元件。
_Avoid_: inbox, pending list, interactive import

**Rematch**:
把已入庫或 Unmatched 的檔案改指派到另一季集、標為 Extra 或忽略；一律經過 Plan（一份 `job_hash = NULL`、`engine = user` 的單列 Plan，立刻套用）。字幕不單獨 rematch，跟著它的影片走。UI 上的按鈕叫「修正」。
_Avoid_: fix, remap, move

**Duplicate**（重複版本）:
新的 Plan Item 與帳本上既有的一份撞上：同一集同一組 Tags，或同一個起始集而結束集不同（Jellyfin 12 會把後者併成同一集）。規劃時略過、記 `plan_items.duplicate_of`，Review Queue 上等人決定：取代舊版、保留兩者、跳過。
_Avoid_: conflict, collision（那是同一包裡兩列寫到同一條路徑，`target_contested`）

**Reimport**:
以 complete 下的目錄為 Import Source 重新入庫：Job 退回 `completed`，規劃器與 importer 照常的一輪接手，不要求 torrent 仍在客戶端。帳本以來源冪等（同一個來源永遠是同一列）。沒有 Job 的孤兒目錄按「重新入庫」時建一筆 `trigger = reimport` 的 Job。UI 上叫「重新入庫」。
_Avoid_: re-run, resync

### 修復

**Reconciler**:
比對帳本、qBittorrent、complete 目錄、library 目錄四方一致性的排程工作；同一輪也把反查過的 Jellyfin item 換成 Jellyfin 現在的樣子（第五方），順手做 **Jellyfin 回驗**。
_Avoid_: scanner, sync, health check（Health Check 指服務與 Route 連線）

**Issue**:
Reconciler、管線或健康檢查發現、要有人決定的事，有固定型別——對帳的七種（library_link_missing、source_missing、inode_mismatch、orphan_complete、unknown_torrent、unmanaged_library_file、job_without_files）、管線的四種（missing_files、client_error、client_removed、jellyfin_item_unresolved）健康檢查的兩種（library_uses_tvdb、low_disk_space）、Jellyfin 回驗的一種（jellyfin_item_mismatch）與巡檢的五種（first_batch_stuck：RSS Series 的第一批被停住的 Job 卡住，M4 票 129；feed_poll_failing、feed_backfill_failing：Feed 的輪詢或每日補漏一直失敗超過一天；series_episodes_missing：RSS Series 已入庫的集數中間缺了幾集；series_episodes_collide：同一集意外多份，同一個 RSS Series 兩個發佈名寫不同集的發佈被入庫成同一集，M4 票 130）；`issues.type` 與 `issue_detected` 事件共用這十九種。同一個 `(type, subject)` 只有一筆 open。健康檢查那兩種、回驗那一種與巡檢那五種條件解除時由系統收掉。健康檢查那兩種、回驗那一種、巡檢那五種與 `unknown_torrent` 的「忽略」在條件持續期間有效，條件解除過一次之後再發生才重開；其餘的忽略是「這一次不處理」。
_Avoid_: error, problem, orphan（僅作 Issue 型別名的一部分）

**Jellyfin 回驗**:
反查或對帳找到入庫檔案的 Jellyfin item 之後，比 Jellyfin 認到的季號、集號（多集檔是範圍）與所屬作品的 TMDB id 是否與帳本一致；不一致是一件 `jellyfin_item_mismatch`。Jellyfin 還在認（季集是空的、作品沒有 TMDB id）不算不一致，照反查的排程再問，六次都還認不出才算。抓的是 Jellyfin 那邊的意外，抓不到 Berth 自己算錯的集數。
_Avoid_: verify, validation（單說「驗證」會和播出日比對、片長驗證混在一起）

**Unmanaged**:
library 內不是 Berth 建立的檔案；只列出，永不刪除。
_Avoid_: foreign, external, legacy

**Claim**（認領）:
把 Berth 不認得、但磁碟或 qBittorrent 上確實存在的東西收回來，不另開入庫的路：孤兒目錄 → Reimport、無主 torrent → 建一筆停在 `submitted` 的 Job、Unmanaged 檔案 → 帳本長回一列（inode 反查 complete、路徑照命名模板反解；配不上的不猜）。前兩種由管理員選作品。`berth rebuild-ledger` 是對整個媒體庫做第三種。
_Avoid_: adopt（只當 `IssueAction.ADOPT` 這個按鈕值，函式一律叫 reimport）, import（那是 importer 的事）

**Delete Scope**:
刪除時可組合的四個旗標：移除 library 鏈接（`unlink`）、從 qBittorrent 移除 torrent（`remove_torrent`）、刪除下載目錄裡的檔案（`delete_files`；complete，或還沒下完時的 incomplete）、清除帳本與 Job 紀錄（`purge`）。預設全不勾。
_Avoid_: purge level, cleanup mode

**Health Check**:
對服務連線、版本、Route 硬鏈接與跨服務可見性的檢查，結果顯示在健康頁。**四項**：Jellyfin、
qBittorrent、索引站、Route；三個服務與 Route 各對應精靈的一個泊位（BTH 1、2、4 與 BTH 3），第四項是所有 Route 的總結。
TMDB 那一格（BTH 5）不是檢查：它讀精靈 TMDB 泊位那一次憑證測試的結果。
背景迴圈每 5 分鐘跑一次，也可以在畫面上按「立即重測」。
_Avoid_: diagnostics, status check

**Event**:
Job 時間線上的一筆事件：型別、時間、actor、payload。
_Avoid_: log, activity, history

**Why Not**（為什麼沒入庫；程式碼 `WhyNot`）:
一部作品或其中一集為什麼還沒在媒體庫裡的**結論分類**，十種：入庫失敗、沒下載成、等審核、待綁定、被排除、沒有來源、還在下載、Jellyfin 還沒掃到、還沒播、已入庫（宣告順序就是優先序，整部作品說最前面那一種）。規則只在 `domain/why_not.py` 一份；`GET /media/{id}/why-not`（`services/why_not.explain`，M5 票 10）把季表、Job 與事件、Issue、RSS 那一側收在一份回答裡，agent 與畫面都讀它。
_Avoid_: diagnosis, status（status 是季表那一格）, reason（reason 是拒絕理由與 Review Reason）

### RSS

**Feed**:
一個 RSS 來源（Mikan、Nyaa、acg.rip、generic），有輪詢間隔、排除條件，與自動綁定送進的 Route——劇集、電影各一條。Mikan 的 `MyBangumi` 聚合 feed 是主要用法。
_Avoid_: subscription（Subscription 是 UI 上「訂閱一部作品」的動作）, source

**RSS Series**:
一部作品 × 一個來源（Mikan 的番組 + 字幕組，或標題骨幹 + 字幕組），由 Feed Item 自動長出，綁到 Media 與 Route，帶季號、offset、排除條件。還沒綁到 Media 的是**待綁定**（unbound）：它的 Feed Item 留著不送，綁定那一刻凍結資料夾名並送出。長出來的那一輪先**自動綁定**（`bound_by = system`）：名字相等、開播日期對得上、只有一部才綁，送進長出它的 Feed 那一種的 Route（Feed 沒說時 Route 只有一條才綁）；沒綁上的記下理由與**候選**（認得出、留給人一鍵選的作品）。不屬於任何一個 Feed。2026-09-24 取代 Rule：字幕組是使用者在來源端挑的，Berth 不再挑一次。
_Avoid_: rule, subscription, follow（`follows` 是字幕跟著影片的那個函式）

**第一批**（first batch）:
一個 RSS Series 在 `confirmed = false` 期間送進來的集數：入庫之後不論信心都掛 Audit，在 Review Queue 以 RSS Series 分組，一組一顆「全部確認」——按了之後 Series `confirmed = true`，之後它的 medium 入庫不再進 audit 清單。第一批裡改正一集時可以**套用到這個 RSS Series**：由那一集算出季號與 offset 寫回 Series，還沒確認的集數跟著重算（已入庫的走 rematch 搬過去、仍留在第一批；停在 review 的重新規劃）。**證據夠強的第一批由系統確認**（M4 票 11）：整批每一集都照字面、剛播、播出日對得上時不掛 Audit，Series 直接 `confirmed = true`，時間線記 `series_confirmed`。
_Avoid_: initial batch, pilot

**已完結**（finished）:
RSS Series 的一種**照現況算出來**的樣子，不是存下來的狀態：TMDB 說作品完結而且它入庫過的那幾季都在庫、沒有在路上的，或 30 天沒有新的一筆。RSS 頁把它收進預設收起的一段；紀錄不刪，新的一筆出現就不再是。
_Avoid_: 封存（archived）——沒有人按，也沒有東西被搬走

**Feed Item**:
Feed 中的一筆項目及其結果：unbound（待綁定）/ matched（綁好還沒送成）/ downloaded（送出去了）/ excluded（**排除條件**擋下）/ duplicate（去重擋下：同一個 torrent 已經送過，或媒體庫已有同一個版本）/ passed（新 Feed 的**第一輪預覽**選了「只追之後的」時已經在 feed 裡的；或綁定時取消**補舊集**、那一刻之前發佈的舊集）。擋下的都不是錯誤，帶著「為什麼沒下載」的理由。

**第一輪預覽**（priming）:
新的搜尋 feed（Nyaa、acg.rip）第一輪就帶著歷史，所以選過之前一筆都不送：畫面列出每一筆會怎樣，使用者選「全部下載」或「只追之後的」，選的那一刻記在 Feed 的 `primed_at`。Mikan 加的那一刻就算選過。
_Avoid_: dry-run, backfill（backfill 是 Mikan 的補舊集）

**補舊集**（backfill）:
Mikan 的 RSS Series 綁定時讀它的**單一 feed**（番組 × 字幕組的 `/RSS/Bangumi?bangumiId=&subgroupid=`，整季都在），聚合 feed 沒帶到的舊集寫成 Feed Item 一起送，一律補、沒有開關；之後每天再讀一次，叫**每日補漏**，接住停機期間被聚合 feed 捲掉的集數；RSS Series 完結之後再補最後一次就停，新的一筆出現時恢復（M4 票 108、116）。補下來的與一般 Feed Item 走同一條路（排除條件、去重、`trigger = rss`）。
_Avoid_: catch-up, sync（sync 是 qBittorrent 的 `sync/maindata`）

**一次性 RSS 連結**（one-shot link）:
貼一條 RSS 網址讀一次、勾幾筆送出去：送的是手動的 Job（`trigger = manual`），不建 Feed、不長 RSS Series、不寫 Feed Item，之後的集數不追。排除條件不擋它。
_Avoid_: import feed, quick feed（它不是 Feed）

**排除條件**（exclusion rule）:
Feed Item 不自動下載的條件：一條關鍵字或正則（Sonarr 的格式），比對整個標題。分全域、Feed、RSS Series 三層，三層取聯集；畫面上叫**標題規則**（title rule）。全域另有「不自動下載合集」的開關，預設開：它看解析器的 `release_kind`、不是規則，畫面上叫**內建判斷**（built-in check），只在全域那一層，Feed 與 RSS Series 那兩層只說出它目前的值。Berth 全部接受、只排除（brief §15），沒有白名單。
_Avoid_: filter（「篩選」是清單上的顯示操作）, blacklist
_Avoid_: entry, post

### AI 與通知（M4–M7，2026-09-22 定名、09-24 改）

**Notification**（通知）:
送給某一個人、在他不在 Berth 頁面上時看得到的一則（M4 是 Discord 私訊）。種類有「可以看了」（一筆 Job 的正片在 Jellyfin 全部認出來，M4 票 123）、「正在下載」（RSS 一輪、一部作品一則；人手按的不送給按的人，M4 票 126）、「有 N 件等你處理」（待審核、開著的 Issue、待綁定的 RSS Series 有新的一件，只送管理員，M4 票 127）、週報的摘要（只送管理員，M4 票 131）。用收件人自己的語言寫（存 Discord ID 那一刻的介面語言）。**收件人**是訂閱了那一種（每個人自己勾，`users.notify_kinds_json`）、有 Discord ID 的人；說的是某個媒體庫裡的作品時，還要 Jellyfin 的 `UserViews` 看得到那個媒體庫——送出那一刻問，問不到就延後（M4 票 125）。不是 SSE 推給瀏覽器的那一種，也不是 `events` 的一筆：事件一定掛在一筆 Job 上。
_Avoid_: alert, push（push 是瀏覽器推播）, message（message 是管道上送出去的那一則）

**Notification Outbox**（待送表）:
`notifications` 表：還沒送與送過的每一則，一列一位收件人。與觸發它的狀態變更寫在同一筆交易，由送出迴圈（`notify_sender`，每 10 秒）送；沒送到的留著下一輪再送，滿 24 小時還沒送到、收件人到不了或 Discord 拒收的是**放棄**（`abandoned`，原因留在那一列，M4 票 128）。存的是事實（作品、季集、Route 與它的媒體庫），句子在送出那一刻組。寫入時的最早送出時間是 5 分鐘後，這段時間裡同一個收件人、同一部作品、同一條 Route 的下一筆**合併**進同一列（季集範圍合起來，M4 票 125）。收件人看不到那個媒體庫或 Jellyfin 帳號停用的也是放棄。「有 N 件等你處理」不是哪一筆狀態變更寫的：送出迴圈每一輪先看三份清單上有誰、與上一輪比，新出現的寫進那一則（合併時間 10 分鐘）；送出時再看一次，這一波都處理掉了就放棄（M4 票 127）。
_Avoid_: queue（佇列是程序內的東西，這一張活過重啟）, outbox table

**Channel**（管道）:
送通知與收訊息的外部服務，一個 `adapters/notify/` 的 adapter。M4 唯一的是 Discord bot 私訊（不做頻道 webhook，2026-10-21）。同一個管道在 M7 也收使用者的話。
_Avoid_: integration, webhook（webhook 是別人打進來的那一種）

**AI Task**（AI 任務）:
交給 AI 的一件事：規則層 low 的 Plan、Unmatched 檔案、待綁定的 RSS Series、offset 修正、audit、程式檢查標出的可疑入庫、Issue、巡檢標出的項目。帶資料包、允許的工具與預算，結果是「已處理」或「交給人（附理由）」。M5 起；每一種都有同一個命令的人工版本。
_Avoid_: job（Job 是一包 torrent）, ticket

**Command Registry**（命令登錄表）:
services 命令的清單：輸入、結果與拒絕理由、副作用等級（`read` / `reversible` / `irreversible`）、反向命令與旗標（`connects_out` / `sends_out` / `downloads` / `settings` / `internal`；`internal` 的不收）、給模型的說明，以及可以乾跑的驗證（`validate`，確認卡的預覽先跑它）。AI 的工具、確認卡、M7 的 MCP server 都只從這裡來。程式在 `services/registry.py`。
_Avoid_: tool list, API list

**Command Executor**（命令執行器）:
叫 Command Registry 上的命令的那一條路，API、AI 的工具、Proposal 與之後的 Discord、MCP 共用（`services/executor.py`，M5 票 07）：查登錄表、照命令的 **audience**（`admin` 預設 / `user`）擋角色、驗輸入、注入伺服器手上的東西與 Actor、事後替動到的 Job 推播並叫醒接手的迴圈、把命令宣告的拒絕換成同一個形狀。「自己的送單」由命令看注入的 `user_id`。
_Avoid_: dispatcher, runner

**Actor**（誰做的）:
做一件事的是誰，寫進 `events.actor`：人（user id）、`system`、`rss:<id>`、`ai:<user id>`（AI 替那個人做；角色與碰得到的範圍也照那個人）。寫法只在 `domain/actor.py`。
_Avoid_: user（user 是帳號）, operator

**Shadow Mode**（影子模式）:
一種 AI 任務型別的試用狀態：AI 照跑，只記錄它會怎麼做，照舊由人決定，統計與人的一致率。使用者看數字後切成自動。
_Avoid_: dry-run（dry-run 是 RSS 的預覽）, test mode

**AI Activity**（AI 活動）:
AI 做過的每一件事、理由、花費，逐筆可撤銷。
_Avoid_: log, history

**Sweep**（巡檢）:
每天一次只跑程式檢查（不花 token）、每週一次產出週報。M4 起，不需要 AI；M5 起標出來的交給 AI 任務。每日那一輪由 `sweeper` 迴圈在 05:00 跑（M4 票 129）：要人動手的寫成 Issue（第一批卡住；M4 票 130 起還有一直失敗的 Feed、RSS Series 缺集、同一集意外多份——版本並存不算），「等你處理」最舊的一件等滿 3 天再提醒管理員一次（**放太久**，同一件 3 天內一次）。
_Avoid_: audit（audit 是 medium 自動入庫的確認）, reconcile（對帳比的是帳本與磁碟）

**Weekly Report**（週報）:
一週一份、產生那一刻算好存下來的回顧：這一週**入庫了什麼**（依作品，季集範圍）、**修了什麼**（核准的計劃、rematch 的檔案、人解決與系統收掉的 Issue）、**還有什麼等人**（產生那一刻「等你處理」的三份清單，巡檢開的 Issue 另外點出來）。一週是週一 05:00 到下一個週一 05:00（容器時區），週一巡檢跑完接著產生；同一週只有一份，重啟補上漏掉的那一週也不多一份（M4 票 131）。存下來而不是每次重算：purge 會連帳本與事件一起刪，舊週報不跟著變。週報頁 `/weekly` 只有管理員看得到；訂閱了的管理員收到一則摘要，連到那一週。
_Avoid_: digest（digest 是摘要那一則通知）, summary, stats

**Assistant**（助理）:
AI 核心對人的介面：M6 的側面板、M7 的外部管道。工具是 Command Registry，可逆的直接做並給撤銷，不可逆的提出 Proposal。
_Avoid_: agent（對外的說法用助理）, bot（bot 是管道那一端的帳號）, copilot

**Proposal**（提案）:
AI 想做但**不可逆**或沒把握的一個命令：命令名、參數、理由、狀態（proposed / approved / rejected / applied / failed）、誰決定的。人確認才執行。畫面上是一張卡，外部管道上是一則帶按鈕的訊息。2026-09-24 起只用在這兩種情況，可逆的 AI 自己做。
_Avoid_: suggestion, action, task
