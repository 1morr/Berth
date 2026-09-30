# 21 — 精靈的錯誤訊息分層：人話在上、原文收進技術細節，舊結果不殘留

**Status:** done

**Blocked by:** 18, 19, 20（它們各自新增或改寫錯誤理由；這張把整個精靈的錯誤呈現統一，放最後以免來回衝突）

**讀:** `docs/research/wizard-review-2026-09-30.md`（對照成熟產品那一節）；plan §7（i18n）、§9.3；`PRODUCT.md`、`DESIGN.md`；
先跑 `/impeccable shape` 決定「技術細節」的呈現

## 為什麼（2026-09-30 精靈審查）

成熟產品（*arr、Home Assistant config flow）的做法是：已知的失敗用錯誤代碼，由前端翻成人話、掛在造成它的欄位上；
原始例外只在未知情況下出現。Berth 現在把後端字串直接當標題：

- **原文直出**：`GET /configuration: 401`（TMDB）、`GET /api/v1/system/status: 401`、`/movies is not visible from the Berth
  container ([Errno 2] …)`、`category 'berth-tv-shows' already points at …`、`POST /Library/VirtualFolders/Paths: 404`；
  每條 Route 檢查下列出 `torrents/createCategory`、`Library/VirtualFolders → stat()`、`Environment/ValidatePath`、`link()`、
  `dev=69 · inode=…`；qBittorrent 偏好表用原始鍵名 `temp_path_enabled`；媒體庫類型顯示 `movies` / `tvshows`。
  出處：`web/src/components/RouteCheckList.tsx:39-55`、`StepLine.tsx:56-58`、`QbittorrentStep.tsx:237-241`、
  `JellyfinExisting.tsx:227-239`。
- **說錯原因**：TMDB 401 的手動步驟是「確認這台機器連得到 api.themoviedb.org」，右欄同時「憑證 已取得」、泊位卡
  「失敗 · 憑證 待驗證」；`/setup/routes` 的 422（選擇無效）顯示「Berth 後端可能沒在跑」（`web/src/pages/SetupPage.tsx:492-495`）；
  qBittorrent 登入失敗在 `sign_in` 被吞掉（`berth/services/qbittorrent.py:118-131`），之後在 category 那一條以 403 爆出、
  卻給「分類衝突」的補法（`routeChecks.ts:45`）。
- **沒說**：精靈裡「選服務」的請求失敗（409 `jellyfin_owned`、422、5xx、斷線）完全不顯示（`SetupPage.tsx:165-173`）。
- **舊結果不清**：換到另一台 Jellyfin 後，上一台的版本錯誤還掛著；切到「既有」後泊位卡仍寫「失敗 · 套件內」、右欄列
  套件內的動作；Prowlarr 狀態列停在上一次；取消「沿用 Jellyfin 帳密」後「這不是 qaowner 的 Jellyfin 密碼」還在，舊密碼
  被帶進新欄位、確認欄還沒填就報「不一樣」；刪除 Route 後「已刪除」一直留著。
- **套件內／既有文案混用**：既有 qBittorrent 連線失敗時標題變成「套用建議的 qBittorrent 設定……這台 qBittorrent 是套件內的，
  Berth 直接改它的偏好」；選既有但還沒測試前，「將會做什麼」列的是套件內的動作。
- **IP 被封**：「到它自己的介面解除」做不到（同一台主機的瀏覽器也被封，qBittorrent 也沒有解除封鎖的介面）；沒說要等多久，
  連錯前沒有預警；帳密錯的結果標成「要求帳密」、標題寫「連不上」。
- **版本衝突的雙色**：qBittorrent 4.3.9 同一畫面連線卡綠「連上了」、泊位卡紅「太舊」；升級指令給的是套件內的
  `docker compose pull qbittorrent`，對既有那一台不適用（`QbittorrentStep.tsx:248-251`）。
- **小瑕疵**：「套用這 5 個鍵」實際 6 項；頁首「共 6 步」而泊位板 5 格；1280 寬時 BTH 5 的狀態字被右緣切掉一半；
  「Movies、TV和Anime」少空格。

## 做什麼

1. **錯誤代碼**：後端的失敗（Route 檢查、qBittorrent diff / apply、加 Berth 路徑、TMDB、Prowlarr connect、選服務）一律回
   封閉的代碼＋少量參數（路徑、版本、HTTP 狀態），前端依代碼選 i18n 文案；未知例外才用一個通用代碼帶原文。
2. **呈現**：一行人話（發生什麼＋下一步）掛在造成它的欄位或那一條檢查上；原文、HTTP 狀態、端點、errno、inode 收進可
   展開的「技術細節」。設定頁的 Route 列表與健康頁用同一個元件，一起改。
3. **舊結果**：換來源、換位址、重新測試、改欄位時，清掉這一格上一次的結果與錯誤。
4. **文案依來源**：套件內與既有各自一套標題、說明、手動步驟；補法指令只給適用的那一種。
5. **IP 封鎖**：查證 qBittorrent 預設的連錯次數與封鎖時間（`web_ui_max_auth_fail_count`、`web_ui_ban_duration`，補進
   brief §20.2），說「等 N 分鐘，或重啟 qBittorrent」；Berth 自己數連續失敗，第 3 次起預警「再錯 N 次會被封」。
6. **雙色衝突**：連線通過但版本太舊時，連線卡也是警示色，不是綠。
7. 上面的小瑕疵。

## 驗收

- [x] 閘門（`tests/` 或 vitest）：精靈與設定頁的錯誤元件只接受代碼、不把後端字串當標題；**雙向變異**：造一個直接渲染原文的
      元件會紅，改一次無關的格式不會紅
- [x] vitest：每個錯誤代碼都有 zh-Hant 與 en 文案（缺一條就紅）
- [x] vitest：換來源 / 換位址 / 重新測試後，上一次的錯誤不在畫面上
- [x] vitest：既有 qBittorrent 連線失敗時標題與說明是既有的那一套
- [x] playwright 對 `berth-existing` 實跑錯誤組每一台（見研究檔的對照表），附截圖：主文沒有英文原文與 HTTP 狀態碼，
      「技術細節」展開看得到；TMDB 假 key 說 key 不對
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-01 實作紀錄**（shape：`.scratch/m4/error-layers-shape.md`，使用者答了三題，都照建議）

- **代碼**：`StepFailure`（28 個，`domain/enums.py`）加 `SetupStep.failure` / `params`。adapter 的例外由
  `services.steps.failure_of` 對照（`IpBannedError` 排在 `AuthFailedError` 前）；Berth 自己判斷的丟
  `StepFailedError(代碼, 原文, **參數)`——Route 檢查、Jellyfin 序列、TMDB、qBittorrent 套用、索引站加站 / 登入 / 連線
  都走它。舊資料沒有代碼的失敗讀出來是 `unexpected`。連線測試照舊是 `ConnectionReason`，另存原文（`ServiceTest.error`）；
  讀差異、讀清單的失敗是 `failure`；對 Berth 自己的請求照狀態碼分（`requestProblem`）。
- **呈現**：`TechnicalDetails`（原生 `<details>`，通過的列在行尾、失敗的在補法之後）、`failures.ts` 查表、`StepLine`
  改成人話→補法→技術細節，端點與 `detail` 收進去、行首只剩關鍵值（Route 檢查由 Route 本身給：分類名、路徑）。
  健康頁的服務卡、下載迴圈卡、設定頁介面登入、`IndexerSites` 的「Prowlarr 原文」一起換成同一個元件。
- **閘門**：`web/eslint.config.js` 的 `no-restricted-syntax` 只管 `src/setup`、`src/components`、`src/settings`、
  `src/health` 與精靈 / 設定 / 健康頁：`.error` / `.message` 不准直接畫成子節點（含 `?.`、`&&`、三元）。
  `src/lint.test.ts` 用真正的設定檔雙向驗（四種包法都紅；合規寫法換排版與名字不紅；範圍外的頁不管），另外手動
  把規則關掉確認第一條會紅。**擋不到**先賦值給變數再畫、塞進 `t()` 插值。
- **舊結果**：`SetupPage.forgetResults`（選擇或使用者按的重測時 reset 那一頁的 mutation）、測試中不畫上一次的理由與
  補法、既有表單改了一格就收起上一次的結果與拒絕、介面登入的 `edits`（精靈兩處與設定頁；換「沿用」時清掉密碼與
  「不一樣」）、服務頁的草稿提到 `SetupPage`（泊位板跟著它）、「已刪除」8 秒後收起（`useFadingNote`）。
- **文案依來源**：qBittorrent 標題照選下的來源；`Blocked` 的補法照來源（`docker compose` 只給套件內）；頁 1 還沒選時
  右欄不列「建立管理員」。TMDB：401 說 key 不對、給重拿 key 的連結；連不出去才給探測那一行；右欄「已存下，沒通過驗證」。
- **IP 封鎖**：子代理讀原始碼查證（brief §20.2 補了鍵名、單位、預設、只在記憶體、成功才歸零、沒有解除介面）。
  `ServiceTest.auth_failures` 數同一個位址上的連錯（同位址改帳密接著數），第 3 次起預警，數到 5 次說多半已封。
- **雙色**：qBittorrent 的版本也在測連線時擋（`version_unsupported`）。
- 小瑕疵：頁首「第 N 個，共 5 個泊位」、「套用這 N 項」把要設的登入算進去、偏好表與媒體庫類型說人話、中文清單全用
  頓號（`i18n/list.ts`）。1280 寬 BTH 5 在實跑裡（「失敗」、「未指派」）沒有被切掉，沒有改 CSS。

**實跑（playwright，受測 Berth 是工作樹 build 的 `berth:t21`，容器 `berth-t21`、`127.0.0.1:28383`、自己的網段
172.23.0.0/16、config 與 data 在 scratchpad；腳本用 `web/node_modules/@playwright/test` 的 chromium，1280 × 900）**

每一個畫面都檢查主文（收著的技術細節不算）沒有 `GET /`、`: 401` 這類狀態碼與已知的英文原文，再展開技術細節截圖：

1. 頁 1 `bad-jellyfin-old`（10.10.7）：沒通過、「至少要 Jellyfin 12.0，這一台是 10.10.7」；技術細節是端點。改到
   `:58097`：上一台的補法不在了。`guest` 登入：「不是管理員」。管理員登入成為擁有者。
2. 頁 2 `bad-qbittorrent-old`（4.3.9）：連線卡「沒通過」、泊位卡「失敗」、「至少要 qBittorrent 4.4，這一台是 v4.3.9」，
   沒有 `docker compose pull`。`bad-qbittorrent` 連錯：第 3、4 次密碼欄下預警「最多再錯 2 / 1 次」，第 6 次「qBittorrent
   預設連錯 5 次就封鎖這個 IP 60 分鐘…等 60 分鐘，或重啟 qBittorrent」，原文 `Your IP address has been banned…` 在技術
   細節。實跑抓到第 5 次之後預警消失（剩 0 次），已改成說「多半已經封了」並補 vitest。
3. 頁 3（`bad-jellyfin-elsewhere` + `bad-qbittorrent`）：TV Shows 選新的 Berth 路徑——「Jellyfin 看不到…」，原文在技術
   細節；改選 `/tv` 與 `/movies`：TV Shows 紅在分類「已經有一個叫 berth-tv-shows 的分類，存到 /downloads/tv」，Movies 紅在
   「qBittorrent 看不到 Berth 放在 /data/torrent/complete/movies 的檔案」＋ `qbittorrent:` 片段。
4. 頁 4（Route 在受測 Berth 自己的資料庫標成通過，同票 20）：`bad-prowlarr-old`「至少要 Prowlarr 1.3.2」；`ok-prowlarr`
   配錯的 key「Prowlarr 不接受 Berth 的帳密或 API key」＋去哪裡複製 key，上一台的版本補法不在。
5. 頁 5 TMDB 假 key：「TMDB 不接受…」＋「TMDB 不收這把 key…重新複製」，沒有叫人查網路；技術細節 `GET /configuration: 401`。
   主文裡唯一的 `GET /3/configuration` 是右欄「測試打的端點」那一列（剖面即預覽），不是錯誤訊息。

收尾：`bad-qbittorrent` 重啟解除封鎖（封鎖只在記憶體）、分類與實測前一樣、沒有留下 torrent；`bad-jellyfin-elsewhere`
的 API key 與實測前同一把（Berth 沿用了既有的「Berth」）、媒體庫路徑沒變，刪了核對時自己留下的 `t21-snap` 裝置（Berth
的 `berth-server` 裝置之前的票就有，分不出新舊，沒動）；受測容器、網段、image 與它的 config / data 都刪了，截圖留在該
session 的 scratchpad，沒有進 repo。

**code-review 沒有處理的發現**

- 擁有者的 `jellyfin_failed` 人話只說「那一段沒做完」，原因（例如版本）只在技術細節的英文裡。版本已在測連線時擋，
  走到這裡的是其他 Jellyfin 步驟的失敗；要說原因得讓 `OwnerRefusal` 帶那一步的代碼。
- `IndexerSites` 的 `indexer.add.requestFailed` 與 `JellyfinSignInForm` 的 `jellyfin.existing.requestFailed` 仍是布林加
  「Berth 後端可能沒在跑」，沒有換成 `RequestFailed`（呼叫端只傳布林）。
- 「例外 → 理由」有三張表：`steps._FAILURES`、`setup._classified`、`indexer._failed_probe`（後兩張是 `ConnectionReason`）；
  `IpBannedError` 的順序在兩處各守一次。
- `requestError` 的三元在 `SetupPage.choiceOf` 與 `ServiceConnection` 各一份；`sentAt === form.edits` 在三處各一份；
  產品名字面值（`'qBittorrent'`、`'Jellyfin'`…）散在幾個呼叫端，與 `SERVICE_LABEL` 兩個來源。
- `auth_failures` 只數服務頁的測試；Route 檢查那一次登入失敗也算進 qBittorrent 的次數，所以文案寫「Berth 這邊數到」、
  「最多再錯 N 次」。
- 健康頁服務卡的人話是固定句（健康檢查沒有代碼）。
- 搜尋那一排（`services/search.py`）也帶了代碼：`StepLine` 的介面換了，搜尋的纜繩一起換，否則失敗會一律說「沒預料到」。
