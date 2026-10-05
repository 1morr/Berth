# 31 — 精靈的文案與顯示細節

**Status:** done

**Blocked by:** 24、25、26、27、29、30（它們會改到同一批文案；這張收尾，避免來回改）

**讀:** `docs/research/wizard-qa-2026-10-01.md`（所有 P3，以及第 21 條）；`PRODUCT.md`；`web/src/i18n/resources.ts`

## 為什麼（2026-10-01 精靈實測）

研究檔問題清單裡標 P3、票欄寫 31 的都在這裡；每條附截圖與程式碼位置。重點：

- 「五條檢查」實際是六項（`resources.ts:65,872,2559-2613`）。
- TMDB 的錯誤借用服務句型（「TMDB 不接受 Berth 的帳密」）、垃圾字串也存下、還沒填就「憑證 待驗證」；qBittorrent 失敗標題寫
  「帳密或 API key」。
- 「另一台」用容器 ID 稱呼；「主機名解得到但連不上」是術語；Jellyfin 啟動中顯示「回的東西不是這個服務」。
- 既有卡片寫「Berth 只連它，不改你的設定」，但 Route 被擋前 Jellyfin 路徑已加上、未初始化的 Jellyfin 會被跑初始精靈。
- 空密碼的 Jellyfin 管理員當不了擁有者、畫面沒說；改位址表單沒有取消鈕；Jellyfin 語言下拉不跟介面語言。
- 被封 IP 時沒說宿主瀏覽器也進不去 WebUI；重新讀取媒體庫沒有回饋；Prowlarr 站數三處不一致、0 站時「尚未執行」；推薦站
  說明是英文。
- 頁 4 測試結果在重新整理、移除站之後消失；「第 6 步」與「共 5 泊位」並列；套件內頁 1 提到「改位址」；設定頁 qBittorrent
  表格用原始鍵名；分類目錄用中文媒體庫名；完成頁沒給三個服務的網址與登入方式；泊位板 BTH 3 完成後仍「—」、Route 照字母
  排序、路徑預覽顯示 `../etc`、「3 個已建立」計數對不上；套件內 qBittorrent 也被提醒「完成時執行外部程式」；改選既有未測時
  右欄仍列套件內位址；Berth 停著時按「設定介面登入」沒有反應。
- 程式碼疑點（未實測）：完成時只再驗頁 3 與頁 5；422 一律說「畫面過時了，重新整理」。

## 做什麼

逐條修；做之前先把清單對一遍，前面的票已經修掉的標「已由 NN 處理」。改不動或決定不改的，記在 `## Comments` 說明理由。
完成時再驗頁 2 與頁 4（另一個分頁改過也擋得住）。

## 驗收

- [x] 研究檔裡每一條 P3 在 `## Comments` 有結論（已修／已由 NN 處理／不改＋理由）
- [x] vitest：改過的文案 zh-Hant 與 en 並列；「五條」不再出現
- [x] 整合測試：`/setup/complete` 在頁 2 或頁 4 不成立時回 422（雙向）
- [x] `/impeccable critique` 與 `audit` 跑過精靈，P0／P1 修掉
- [x] playwright 走一遍全新與既有的快樂路徑，附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

### 進度（2026-10-05 session）

**清單對一遍（開工 `7325deb`）**：

| # | 現況 | 處理 |
| --- | --- | --- |
| 21 | 仍在：`ProwlarrLogin.save` 吞掉 reject、不畫 `prowlarrLogin.error` | 修 |
| 25 | 仍在：7 個 key（zh／en 共 14 處）寫「五條」，`CHECK_LABEL` 是 6 條 | 修：文案不寫數字 |
| 26 | 已由 25 處理（`requestProblem.ts` 401＋`ownerPending`→`ownerElsewhere`） | — |
| 27 | a 失敗句借用「帳密或 API key」仍在；b 垃圾字串照存；c 剖面已由 21、泊位板仍「憑證 待驗證」 | 修 a、c；b 見下 |
| 28 | 仍在：`detail=info.server_name`（容器 ID） | 修 |
| 29 | 建立側已由 29；登入側空密碼仍只說「都要填」 | 修 |
| 30 | 仍在 | 修 |
| 31 | 仍在 | 修 |
| 32 | 仍在 | 修 |
| 33 | busy／失敗已有，成功沒回饋 | 修 |
| 34 | >0 站已由 27；0 站仍三處不一致、連線卡「尚未執行」 | 修 |
| 35 | 仍在（刻意，定義只有英文） | 見下 |
| 36 | 仍在：卡片句與行為矛盾 | 修文案 |
| 37、38 | 仍在 | 修 |
| 39 | 已由 29 處理（`LoginPage` 用 `trimUsername`） | — |
| 40–48 | 仍在 | 逐條 |
| 49 | 仍在：`complete_setup` 只驗頁 3、5 | 修＋整合測試 |
| 50 | 仍在：裸 `ValueError`→422→「畫面過時」 | 修 |

**下一步**：後端 #49（tdd）→ 文案批次（#25 #27 #28 #32 #36 #37 #38 #41 #42 #47）→ 前端行為（#21 #29 #30 #31 #33 #34 #40 #45 #46 #48）→ #43 #44 #50 → critique／audit → playwright 實跑。

**已做（未 commit，工作樹上）**：

- #49：`complete_setup` 照 `_current_step` 再問每一頁，422 說最前面那一頁（`_UNFINISHED`）；`_berthed` 抽出共用。
  前端 `finish.onError` 收到 422 就重讀進度，網址被拉回那一頁。測試：`test_setup_api.py::TestRoutes::
  test_completing_needs_page_{two_still_done,four_still_settled}`（雙向）、`SetupPage.routes.test.tsx`「完成被擋時重讀進度」。plan §6、§9.3 頁 6 已改。
- #25：文案不寫條數（「每一條纜繩」）；閘門 `resources.test.ts`〈route check counts〉（雙向變異在檔內）；程式碼註解與 plan／brief／README 的「五條」一併改。
- #27：`failures.AUTH_REJECTED_TEXT`（qBittorrent 說帳密、TMDB 自己一句、其餘 API key）；`signals.reasonLabel`（連線卡同一條分法）；
  `tmdbKey.looksLikeTmdbKey` 送出前擋形狀不對的 key（b 那一半：形狀對而測不過照舊存，見 `verify_tmdb` 的理由）；泊位板沒 key 說「還沒填」。
- #28：拒絕句不提伺服器名（容器 ID），名字留在「伺服器」那一格。
- #32：banned 補法（服務頁與設定頁）補「你從宿主開 WebUI 也登不進去」。
- #36：既有卡片改說 Berth 會加什麼、什麼時候加（`choice.existing.adds.{kind}`）。
- #37、#38：`reason.unreachable`／`not_deployed` 改日常說法；`waiting` 時 `protocol_mismatch`／`unreachable` 說「還在起來」（`reason.coming_up`）。
- #41：回頭看帶子的「目前走到」用泊位名（完成頁是「收尾」）。
- #42：頁 1 回頭看照 Jellyfin 來源分兩套。
- #47：`routes.dock.probesYours` 只給既有 qBittorrent。

**下一步**：#21 #29 #30 #31 #33 #34 #40 #45 #46 #48 → #43 #44 #50 → critique／audit → playwright。
- #21：`ProwlarrLogin` 接住 reject，畫 `RequestFailed`。
- #29：登入既有 Jellyfin 時密碼空著說 `owner.error.noPassword`（Berth 不收沒有密碼的擁有者，理由寫在句子裡）。
- #30：「改位址」表單有取消。
- #31：語言下拉沒選過就跟著介面語言（`picked ?? localeForUi`）。
- #33：人按的「重新讀取」讀到了說 `routes.rereadDone`（進頁自動的那次不說）。
- #34：自動重測的條件改成「清單站數 ≠ 測試記的站數」，後端走過頁 4 也看；`StepLine` 收 `status` 覆寫，連上了 0 站寫「還沒有站」。
- #40：測試與試搜結論放 query cache（`setup/remembered.ts`），卸下重掛還在；**重新整理不留**：它們是對活的站的一次探測，「測試」是 `read` 命令，不為了留住它改成寫入。
- #45：完成頁 `ServiceDoors`：三個服務的網址（`jellyfinBase`／`serviceWeb`）與登入方式。
- #46：泊位板 BTH 3 寫「N 條 Route」；套件內 Route 照清單順序建（`jellyfin.listed_position`）、剖面「將建立」同序；
  路徑預覽 `previewUnder`（資料夾不成立寫「…」）；「3 個已建立」對不上的那一半（Extra 被算進 Route）已由 24 處理。
- #48：改選另一格還沒測時，剖面不列存下那一台的位址。

**下一步**：#43 #44 #50、#35 結論 → 全部檢查與全套測試 → critique／audit → playwright 實跑（全新 qa-*、既有 ok-*）。
- #43：設定頁建議設定表每一列先寫頁 2 那一條的名字（`qbittorrentSteps.STEP_LABEL`），原鍵名在下。
- #44：套件內 Route 的 slug 由寫入目標的最後一段（使用者填的資料夾名）算；既有照舊由名稱算。plan §9.3 頁 3 已改。
- #50：`_plan` 的四種不成立改丟 `RouteRejectedError`（新理由 `library_without_path`，422），`POST /setup/routes`
  宣告它們；頁 3 照理由說（`setup/buildRefusal.ts`），原文進技術細節。其他端點的裸 422 仍是「畫面過時」那句：
  它們多半真的是過時的畫面，沒有實測案例，不改。
- #35：不改。說明是 Prowlarr 定義自帶的英文，幾百站譯不完也跟不上；改標 `lang="en"`，讀屏器用英文念。
- 全部檢查綠；vitest 81 檔 1289 條綠。

**下一步**：pytest 全套 → critique／audit → playwright 實跑 → e2e → code-review → commit/push。

**critique／audit（2026-10-05，opus 子代理，Fake 後端 bundled／mixed／healthy，1280 與 390、亮暗、zh／en；detector 零發現）**：
三條 P1 已修——
- 「改位址」表單取消後焦點不回觸發鍵（設定頁掉到 body）：`ServiceChoice` 記 `refocusEdit`，測試列的「改位址」掛上時接手（`TestLine.editRef`）。
- 停用的來源卡片 `opacity-60` 壓暗說明（亮 2.6:1、暗 3.89:1）：拿掉 opacity，選不了的那一格只換底（`bg-hull`）與游標。
- 完成被 422 擋下、拉回某一頁時無聲換頁：拉回去的那一頁頂上說 `complete.pulledBack`（`pulledBack`，到完成頁才清）。
未處理的 P2／P3（不在本票範圍，留給 M4 收尾的 polish）：頁 4 剖面在改選另一格未測時仍列存下那一台（頁 1 已由 #48 修）；
`/settings/qbittorrent` 漂移值用 `blocked-ink`（DESIGN 歸 `assigned`）；頁 3 既有一進頁就紅字「還差一步：勾一個媒體庫」；
`ServiceDoors` 連結命中高度 14px、沒說開新分頁；完成頁區塊標題沒有 `border-b-2`（同頁既有慣例）；`AUTH_REJECTED_TEXT`
用服務名字串查表；BTH 3 詳情沒有 `.label` 度量名。

**playwright 實跑（2026-10-05，image `berth:qa-t31` 由工作樹 build，用完刪掉）**，截圖在 session scratchpad `qa/bundled/`：

- 全新（`berth-qa/bundled`，qa-*，1280）：B1 選擇 → 建管理員 → 擁有者；B2 套件內 qBittorrent 沿用帳密套用；B3 資料夾填
  `../etc` 預覽寫「…」、改 `films` 後建立：分類 `berth-films`、Route 照清單順序（電影／TV／Anime）、BTH 3「3 條 Route」、
  「按下之後會」不提外部程式；B4 測 YTS、加入、介面登入；B5 `hunter2` 被形狀檢查擋下、泊位板「憑證 還沒填」，真 key 通過；
  B6 完成頁三個網址（宿主 port 21096／21080／21697，curl 302／200／302）與登入方式；B7 回頭看帶子「目前走到：收尾」、
  頁 1 套件內說明不提改位址；B8 完成落地。之後 `down`。
- 既有（只有 Berth 的 `qa2-berth` 接 `ok-*`，1280）：E1 空密碼說不收沒有密碼的擁有者、改位址→取消焦點回「改位址」、停用卡片
  opacity 1；E2 既有 qBittorrent 確認；E3「重新讀取」說「已重新讀取：Jellyfin 上現在有 2 個媒體庫」、按下之前列出外部程式那句；
  E4 0 站「待處理」、沒有前進鍵、沒有「尚未執行」，加 YTS 之後前進；E6 完成頁——**抓到一個錯**：既有 Jellyfin 的連結是
  `host.docker.internal:48096`（瀏覽器開不了），已修（`serviceWeb.browserReachable`，vitest 補上）；完成落地。
- 測前測後快照（`berth-qa/existing/scripts/snapshot.py`）：差 Jellyfin 的 Berth key 與 Movies 的 `/data/library/movies`、
  Prowlarr 的 YTS、`/data/torrent/incomplete/movies` 兩個空目錄；逐項還原後再拍一次，與測前**完全相同**。ok-* 停回原狀。
- 備註：媒體庫深連結（`jellyfinLink.jellyfinBase`）對 `host.docker.internal` 有同一個問題，不在本票範圍，留給之後。

**下一步**：code-review → 修 → 全套 pytest／vitest／前端 e2e／e2e → 勾驗收 → commit／push。

**code-review（`/code-review 7325deb`，兩軸 opus）**：
- Standards 已處理：CHANGELOG 補上（對外 API：`POST /setup/routes` 的 422 帶理由、新的 `library_without_path`、
  `/setup/complete` 照頁序再驗）；plan §6 的 `POST /setup/routes` 與 §9.3 步驟表第 6 列；殘留的「5 / 5」「五項」「三項」
  註解；`REFUSAL_RESPONSES` 不再替 `routes/*` 宣告它丟不出的 `library_without_path`；`BUILD_REFUSAL` 補雙語閘門
  （`buildRefusal.test.ts`，雙向）；Jellyfin 連結改走具名的 `serviceWeb.jellyfinWeb`。
- Standards 未處理（判斷題，不改）：`x in TABLE` 加 `as` 的兩處、`test_setup_api.py` 三個開 session 的 helper 沒合併、
  `AUTH_REJECTED_TEXT` 以服務名查表（同 critique 的 P3）。閘門 regex 只認「條」：「四項檢查」是健康檢查的四個服務，
  算進去會誤報。
- Spec 已處理：#29 的後半（改了帳密收起上一次的拒絕；`target_changed` 例外，它的出口是重新測試）；完成頁標題不寫死
  「三個」；`complete.pulledBack` 不再只歸因於另一個分頁。
- Spec 未處理：#27b 只在前端擋形狀，`POST /setup/tmdb/test` 照收——「測不過也存」是 `verify_tmdb` 的既定規則，形狀檢查
  是畫面上的提早提醒，不是閘門；#40 重新整理不留（理由見上）。

**收尾（2026-10-05）**：全部檢查綠；pytest 3492 passed；vitest 82 檔 1292 條；前端 e2e 35 passed。後端 e2e（`tests/e2e`）沒跑：
它的容器名、網路與 port 和使用者正在用的 berth-trial 相同，要跑得先停 berth-trial（本次不准動）。實跑截圖在 session
scratchpad 的 `qa/bundled/`（`B*` 全新、`E*` 既有）。
