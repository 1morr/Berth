# 28 — 助理看得到 Jellyfin 裡已有、Berth 沒紀錄的作品

**Status:** done

**Blocked by:** 27

**讀:** brief §9（對帳、重新入庫）、§11（帳號與權限，Jellyfin 媒體庫的允許清單）、§20.8；plan §11.2b M1.5 媒體庫瀏覽、§11.6；`berth/services/inventory.py`（`read_wall`、`read_holdings`）、`berth/services/media.py`（`read_media` 的季集狀態）、`berth/services/search.py`（缺集搜尋怎麼算「缺」）、`berth/services/agent_tools.py`、`berth/skills/new-season-picks`、`missing-episodes`、`series-mapping`；`berth rebuild-ledger` 與審核頁「從媒體庫重建帳本」

## 為什麼

使用者 2026-10-28 問助理「看不看得到庫裡已有的媒體」。現況：

- 助理只看得到 **Berth 帳本**（經 Berth 入庫的）；一次一部作品，沒有列出整個媒體庫的工具。
- Jellyfin 裡有、Berth 沒紀錄的（自己複製進去的、舊安裝入庫的）在助理眼裡是「缺」，補缺集與整部系列可能**重複下載**；新番推薦也不看使用者已經有或已經訂閱的。

使用者決定照建議修：給助理讀媒體庫的能力，推薦、補缺集、整部系列時先標出「你可能已經有」。

## 做什麼

1. 先用 `mattpocock-skills:codebase-design` 想清楚邊界再動手，寫進票 Comments：
   - 「Jellyfin 有、帳本沒有」的集要怎麼讓 `read_media`（給模型的那一份）看得到，例如每集多一個狀態或旁註；畫面要不要跟著改（作品頁現在已有「Jellyfin 有這部，Berth 的紀錄裡沒有」）。
   - 缺集搜尋（`scope.missing`）要不要把這些集當成「不缺」；選「標出來由人決定」還是「直接不搜」，寫理由。預設偏向不重複下載。
   - 權限：照 brief §11，一個人只看得到自己被允許的媒體庫（`read_wall` 已守）；給模型的工具不能繞過。
2. 給模型一支讀媒體庫的工具（例如列出某個媒體庫的作品、或用名字查「我有沒有 X」），照 `audience` 與允許清單。
3. skills：
   - `new-season-picks` 標出已經有、已經訂閱的；
   - `missing-episodes`、`series-mapping` 先看 Jellyfin 已有的，不推薦重下；
   - 有大量「Jellyfin 有、帳本沒有」時，建議使用者跑「從媒體庫重建帳本」。
4. 注入測試：新工具的結果（Jellyfin 的標題）是外部內容嗎？照 plan §11.6 的防線表判斷並補測試（`test_injection_claims`）。

## 驗收

- [x] 給模型的作品資料分得出「帳本有」「只有 Jellyfin 有」「缺」（測試）；缺集搜尋照決定處理（測試）
- [x] 讀媒體庫的工具照允許清單擋（測試，變異會紅）
- [x] 三份 skill 已改（`test_skills.py` 綠）
- [x] 真模型確認（`.env` key，預算上限 $0.5）：情境裡 Jellyfin 已有某部作品的前幾集、帳本沒有，「補 X 缺的集」不會重下那幾集、「推薦這季新番」會標出已有的；逐字稿寫進研究檔與票 Comments
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；brief / plan、CHANGELOG、progress.md 已更新
- [x] 不發版、不 push

## Comments

### 2026-10-30 設計（`codebase-design`，開工前）

**一集多一個狀態 `in_jellyfin`，畫面跟著改。** `EpisodeStatus` 加 `IN_JELLYFIN`（「Jellyfin 有，Berth 的紀錄裡沒有」），優先序在 `downloading` 之後、`missing` 之前：帳本有的仍是 `imported`，Berth 自己在處理的（卡住、下載中）仍照 Berth 說；還沒播卻在 Jellyfin 的也算 `in_jellyfin`。判定在 `inventory.read_holdings` 一處（多收一份 Jellyfin 有的季集，預設空的），`read_media` 給模型與給作品頁的是同一份；季表多一個不塗漆的標籤。理由：缺集一鍵搜（作品頁）與模型的缺集搜尋走同一個 `search._missing`，只改給模型的那一份的話，作品頁的「缺 N 集」與按下去搜的集數會對不上（「判定規則全部在這裡，前端只照畫」）。季表的「已入庫 N / M」仍只數帳本。

**作品多一格 `jellyfin`：`found` / `absent` / `unknown`。** 電影沒有季表，只能看這一格；`unknown` 是問不到 Jellyfin（沒設定、連不上、帳號停用），這時集的狀態照舊（沒有 `in_jellyfin`），模型要照實說「沒能確認 Jellyfin 裡有沒有」。

**缺集搜尋（`scope.missing`）直接不搜 `in_jellyfin` 的集**，不是「標出來由人決定」：`missing` 的意思就是「我沒有的集」，Jellyfin 有就是有；要換更好的版本的人照名字搜（`query` 或作品頁的一般搜尋），那一條路不受影響。問不到 Jellyfin 時照舊當缺（退回票 28 之前的行為，比整個不能搜好）。

**權限：一位使用者的 Jellyfin 只由執行器打開。** 執行器多拿 `AccessCache`，命令簽名要 `JellyfinAccess` 時照 actor 的使用者開 `jellyfin_access`（`userId` 只從 Berth 的使用者列來，模型給不了）；參數是 `JellyfinAccess | None = None` 的（`read_media`、`refresh_media`、`search_torrents`）問不到時給 `None`，必填的（新工具、`read_wall`）照丟。作品頁的三支（讀、重抓、反查）改經執行器（`Command(...)`），與搜尋同一條。找作品照觀看區：`locate` 不帶 `parentId`（Jellyfin 套權限），集清單只問 `locate` 確認過的劇（`JellyfinAccess.series_episodes`，同 `series_next_up` 的規矩）。新的 adapter 呼叫 `GET /Shows/{id}/Episodes?userId=&isMissing=false`（不帶 `seasonId`，一次整部；OpenAPI 有這兩個參數，實測交子代理，結果補 brief §20.8）。

**讀媒體庫的工具 `inventory.find_in_library(names)`**（`audience=user`）：一次給好幾個名字（新番推薦一次 20 幾部），每個名字在這個人**看得到的每一個媒體庫**（`access.libraries`）找，每個名字每個媒體庫最多 5 部（實作時改：一個媒體庫讀一次整份清單 `access.index`、名字在 Berth 這邊比，忽略大小寫、空白與標點，名字是較長標題的一段也算——真模型第一輪 Jellyfin 的 `searchTerm` 對不上少了冒號的資料夾名，見下方〈真模型〉）；結果是名字 → 作品（Jellyfin 的名稱、年份、種類、媒體庫名、`media_id`（Jellyfin 有 TMDB id 時）、`in_ledger`：Berth 的帳本有沒有它）。不做「列出整個媒體庫」：一個媒體庫上千部，截斷之後模型看到的是前幾十部，答不了「有沒有 X」。

**注入**：Jellyfin 的名稱是外部內容嗎？Jellyfin 認不出的作品名稱就是資料夾名，自己複製進去的常常就是發佈名——與 torrent 標題同一種字，所以是**注入的入口**（`test_agent_injection.ENTRIES` 加一個 `jellyfin_title`，跑過每一條「守法不分入口」的測試），但**不算 External Content**（同 torrent 標題：算的話每一張卡都亮「出自外部來源」）。

**不改的**：`why_not.explain`（只讀 Berth 的紀錄；skill 叫模型先讀 `read_media`）、RSS 的缺集補抓（`sweep`，背景迴圈沒有使用者，看不到誰的 Jellyfin）、媒體庫牆。

### 2026-10-30 實作紀錄

- **Jellyfin 實測**（子代理，12.1.0 一次性容器）：`/Shows/{id}/Episodes?userId=` 不帶 `seasonId` 回整部劇（含 S00、多集檔的 `IndexNumberEnd`），無權的劇一樣 404；`isMissing=true` 回 0 筆（伺服器認得），`false` 會不會濾掉虛擬缺集**沒量到**（樹上造不出虛擬集）。補進 brief §20.8，fixture `shows-episodes.series*.json`。
- **變異**：`find_in_library` 改成搜 Route 的媒體庫、直接打 client 繞過 `access` → `test_a_library_this_user_cannot_see_is_never_searched` 紅（Frieren 漏給 `deckhand`）；`read_holdings` 把 Jellyfin 的判斷移到「卡住」之前 → `test_what_berth_knows_outranks_what_jellyfin_has` 紅。兩者還原後綠。
- **畫面**：演練情境 `agent-live-jellyfin`、`skipper` 登入、`/media/tv:120089` 展開 S01：E01–E04「Jellyfin 已有」（不塗漆、沒有「為什麼」），E05–E12「缺」＋「為什麼」，季頭仍是「0 / 12 集入庫」；檔案區照舊說「Jellyfin 有這部，Berth 的紀錄裡沒有」。截圖 `.playwright-mcp/t28-season.png`（不進 repo）。
- **名字比對改在 Berth 這邊**（偏離開工時的設計）：真模型第 1 輪 Jellyfin 的 `searchTerm` 對不上少了冒號的資料夾名（`Cyberpunk Edgerunners 2`），改讀每個媒體庫的整份清單、NFKC + 不分大小寫、只留字母數字，名字是較長標題的一段也算（雙向，太短的只算整名），結果帶 `exact`；請求數從「名字 × 媒體庫」降成「媒體庫數」。

### 2026-10-30 code-review（兩軸 opus）

處理了：
- Standards：`JellyfinLookup` / `NameLookup` / `LibraryLookup` 撞 CONTEXT 裡 Resolve 的 _Avoid_（lookup）→ 改名 `InJellyfin` / `FoundUnderName` / `FoundInLibrary`，CONTEXT 新增 **Jellyfin Holding**；`_matches` 太短的查詢對上每一部、大小寫不同的名字查兩次 → 修並補測試；`rss._every_subscription` 與一部作品的那一份對同一條 Feed 答案不同（Feed 預綁 Y、帶著綁到 X 的 RSS Series）→ 一部作品的改成從全部的挑。
- Spec：優先序（帳本、下載中、卡住都排在 Jellyfin 前）與電影的 `jellyfin: found` 沒有測試 → 補；季記號的缺集搜尋仍會回已有那幾集的列，skill 卻說「不問」→ skill 改說「列可能回來，挑掉」；前作的資料夾對上續作的名字會被標成「已有」→ 結果帶 `exact`，skill 只把 `exact` 的當成同一部；補缺集出卡前沒說 Jellyfin 已有哪幾集 → skill 改成出卡前那一則要說（第 3 輪驗）。

沒處理（理由）：
- 執行器對每一支選填 `access` 的命令都先開 Jellyfin（`search_torrents` 不搜缺集時用不到）：允許清單有快取（`ACCESS_TTL_SECONDS`），快取在時開它不發請求；Jellyfin 連不上時多的是一次逾時。要延後到真的用時才開得改成 lazy 注入，等量到慢再做。
- 選填時吞掉 `AccountDisabledError`：`jellyfin_access` 已結束他的 session，這一頁照回、下一個請求 401——與觀看區直接 401 不一致，但結果相同（被登出）。
- 必填 `access` 而使用者列不在了是 `RuntimeError`：只有模型的工具走得到，而 AI 一定替一位存在的使用者。
- 季記號那種缺集搜尋不在產品裡濾掉已有那幾集的列：帳本已入庫的那幾集本來就是這樣，一起改要動作品頁的結果表，另開票再議。
- `refresh_media` 用完整的 `Annotated[...]`、`read` 用別名 `ReadMedia`；替身的 `series_episodes` 記進 `watch_area_queries`：小事，不動。
- 三份 skill 各寫一段「從媒體庫重建帳本」的按鈕說明：skill 各自載入、不能互相引用。

### 2026-10-30 真模型（`agent_sources_ab.py --set jellyfin --groups jellyfin`，情境 `agent-live-jellyfin`）

逐字稿與每一輪的細節：`docs/research/m5-acceptance-2026-10-28.md`〈票 28〉、`docs/research/m5-acceptance-2026-10-28/t28-r{1,2,3}-*.md`。三輪合計 $0.054（上限 $0.5）。情境：替身 Jellyfin 的 Anime 有 SPY×FAMILY S01E01–E04（帳本沒有）、本季最熱門的兩部（Cyberpunk Edgerunners 2、Kusuriya no Hitorigoto 3rd Season，資料夾名、無 TMDB id）。

- **補缺集**（「SPY×FAMILY 第一季缺的集幫我補齊…直接出卡給我確認」）：三輪、兩種接口，確認卡都只有 E05–E12（8 列），**沒有重下 E01–E04**。兩種接口都先叫 `inventory_find_in_library`（`in_ledger: false`、`exact: true`）。**沒做到的**：出卡前那一則沒寫「Jellyfin 已有 1–4」（第 3 輪 skill 已要求，仍是只叫工具就出卡）；題目本身說「直接出卡」，票 27 也量過模型在這種時候不寫字。卡上逐列寫了蓋到哪幾集，所以使用者看得到少了 1–4，但沒被告知原因。
- **推薦新番**：第 1 輪兩種接口都**沒標出**已有的兩部（Jellyfin 的 `searchTerm` 對不上少了冒號的資料夾名；模型沒傳羅馬字）→ 改成 Berth 自己比對名字、skill 叫模型傳每一種名字；第 2、3 輪兩種接口都標出兩部「已有」並建議從媒體庫重建帳本，第 3 輪的結果帶 `exact`，兩部都是 `exact: true`。原文：「藥屋少女的呢喃 第三季 … | **已有**（Anime 資料庫）」（Anthropic）、「**你片庫裡已經有的兩部（這次不重複推薦下載）**」（OpenAI）。
