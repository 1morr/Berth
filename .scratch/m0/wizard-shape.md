# 設定精靈 — shape brief

**Status:** confirmed（2026-09-07，使用者確認）

`/impeccable shape 設定精靈`（2026-09-07）的產出。涵蓋 plan §9.3 的**全部八步**，橫跨票 05、06、08、09。

這份是「要做什麼、長什麼樣、有哪些狀態」。**不是** impeccable 的 direction contract，也不是 DESIGN.md：
前者由第一個 build session（票 05）以 `impeccable surface-brief write` 寫入，後者在 M0 UI 收尾（票 11）
由 documenter 依實際做出來的東西產生。

## 1. 任務與對象

**Visitor mode：Operate。** 使用者是來完成一件事的，表現力不得妨礙任務、狀態與熟悉的操作慣例。

剛跑完 `docker compose up` 的自架者，桌機瀏覽器，通常在晚上、房間偏暗。兩種輪廓（PRODUCT.md）：
NAS 使用者（已有 Jellyfin 或 qBittorrent，怕動到既有媒體庫）與一般電腦使用者（什麼都沒有）。

他不知道哪個服務是套件內、哪個是既有——**那正是精靈第 2 步要替他判斷的**。他預期會卡在掛載問題上。
這條流程他一生只走一次（雖然每一步之後都能在設定頁重跑）。

## 2. 結果與證據

**主要任務**：把四個泊位接上，走到四項綠燈。
**成功**：`settings.setup.completed` 寫入，健康頁四項綠燈，且**全程沒開過 qBittorrent / Jellyfin / Prowlarr 的介面**（票 11 的字面驗收）。

**真實證據**——畫面上出現的都是實測到的事實，不是承諾：

- 探測到的版本號（qBittorrent webapi、Jellyfin `/System/Info/Public`）
- qBittorrent 現值與建議值的**逐鍵**差異（`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`）
- Jellyfin 回報的媒體庫名稱與各自路徑
- `link()` 的 device 與 inode、`POST /Environment/ValidatePath` 的回應
- 十個索引站的逐站 `indexer/test` 結果

**只有 Berth 能證明的事**：它是唯一同時看得到三個容器掛載視圖的東西。「哪個容器少了哪個掛載」這句話，
其他任何工具都說不出來。

## 3. 選定方向

**視覺權威：新建世界。**（`WORLD_DISCOVERY_REQUIRED`；票 02 的七個色彩 token 是明說要被取代的佔位。）

- **方向**：泊位調度板（berth allocation board）+ 船期表 + ISO 6346 貨櫃標識。seed key `b84bd503`，
  card `assigned`（THE ROLL），2026-09-07 使用者鎖定。
- **結構論點**：精靈不是八張「下一步」的表單，是一塊**調度板**。四個泊位橫列常駐，工作面在下。
  明確拒絕類別預設：左側垂直步驟條 + 深色卡片 + 藍色「下一步」。
- **序列**：泊位板橫幅（常駐狀態）→ 當前泊位的剖面（將寫入什麼）→ 動作 → 靠泊序列 → 泊位格轉綠。
- **焦點時刻：靠泊序列。** 按下靠泊後那一格不是換成 spinner，而是**逐條纜繩繫上**：每完成一項就把它的
  實際結果數值留在旁邊；任一條失敗變紅並就地展開可複製的手動步驟，其餘已完成的纜繩保持繫上。
- **四條 raise**（各自來自被否決的挑戰者，寫進方向裡）：
  - 法定色（來自圖文電視）：整個 app 只有四個信號色，每個顏色只有一個意思，紅色永遠只代表阻擋。
  - 狀態三重編碼（來自 cracktro）：色塊 + 模板字標籤 + 位置，不看顏色也讀得出狀態。同時滿足 WCAG 2.2 AA。
  - 數值貼在物件上（來自張拉整體柱）：容器名、路徑、inode、版本號各自標在它那一行，不進散文。
  - 剖面即預覽（來自雲採石場）：「將會做什麼」是把真實內容切開露出來，套用前後看同一個剖面。
- **Craft bar**：`vernacular-ephemera-boarding-pass-and-gate-board` 的 hero。要達到的是它的**完成度**——
  表格數字、等寬、單一保留警示色、嚴格欄格、寬字距全大寫標籤——不是它的構圖。
  （註：那張圖是同族的目錄世界，不是本方向自己的稿；本方向沒有生成稿，因為這個 harness 沒有圖像生成，
  執行契約是 **code-led**。）
- **實作後果**：`web/src/index.css` 的 `@theme` token 全部重寫；shadcn/ui 只作為行為與無障礙的基礎，
  外觀一律改造成塗裝色塊與模板字——committed form 裡放 stock 樣式的元件算失誤。

## 4. 範圍與邊界

- **涵蓋**：plan §9.3 的八步全部，一次定調進度模型、步驟結構、失敗與重試的形狀。
- **保真度**：完整可上線的流程，不是原型。
- **不動**：後端 API 形狀（各票自己定義）、plan §9.3 的步驟順序與判定規則、既有 Jellyfin 的紅線
  （絕不自動建媒體庫、不改既有 `LibraryOptions`、不呼叫 `DELETE /Items/*`、不建議搬媒體庫路徑）。
- **反目標**：左側垂直步驟條；藍色 primary 按鈕；插畫或吉祥物；百分比進度條；
  「歡迎使用 Berth」式的行銷首屏；任何把失敗說成「發生錯誤，請稍後再試」的訊息。

## 5. 狀態與量級

**八步 → 四個泊位**（與 M0 驗收的「四項綠燈」對齊）：

| 泊位 | 步驟 |
| --- | --- |
| （前置） | 1 建立管理員 · 2 偵測服務（泊位板第一次點亮） |
| 泊位 1 Jellyfin | 3 |
| 泊位 2 qBittorrent | 4 |
| 泊位 3 來源 | 5 索引站 · 6 TMDB（同一泊位的兩條纜繩） |
| 泊位 4 媒體庫路徑 | 7 媒體庫 → Route + 硬鏈接檢查 |
| （收尾） | 8 完成 |

**量級**：

- 服務判定五種：套件內 / 既有 / 探測中 / 逾時（輪詢上限 2 分鐘）/ 不存在（從 `COMPOSE_PROFILES` 拿掉）。
  三個服務可任意組合 = 八種佈局都要成立。
- Jellyfin 媒體庫：套件內固定 3 個；既有 1–20 個，每個 0–5 條路徑。
- 索引站：10 個預設站，逐站 pending / ok / failed。
- qBittorrent 差異：0–5 個鍵。
- Route：套件內 3 個；既有 0–20 個（使用者勾選）。

**每一步的狀態**：idle / 執行中（逐條纜繩）/ 部分失敗 / 全成功 / 已跳過。

**錯誤**（每個都要有可複製的手動步驟；掛載類另附該容器的 compose `volumes:` 片段）：
連不上、qBittorrent 低於 4.4、`EXDEV`、路徑 `stat` 不到、Jellyfin 重啟逾時、Prowlarr 讀不到 API key、
category 已存在但 save path 不同、媒體庫掛 TVDB 插件（警告不阻擋）。

**空狀態**：既有 Jellyfin 一個媒體庫都沒有。

**續行與跳過**（2026-09-07 使用者決定，文檔原本未寫）：

- **能續行**：關掉瀏覽器再回來回到原本那一步，狀態在後端 `settings.setup`。
- **非必要步可跳**：索引站與 TMDB 可以「之後再說」；Jellyfin、qBittorrent、媒體庫路徑不可跳。
  完成頁必須列出跳過了什麼、以及在哪裡補。

## 6. 互動與版面

- **拓撲**：常駐的泊位板橫幅（四格）+ 單一工作面。沒有第二層導覽。
- **桌機**：橫幅一列四格；工作面兩欄，左剖面（將寫入什麼）／右動作。
- **手機**（PRODUCT.md：手機要能完成日常操作）：橫幅收成水平捲動的四格，當前泊位固定可見；
  工作面單欄，剖面在上，主要動作固定在底部安全區之上。八步全部要在手機上做得完。
- **鍵盤**：泊位板可 Tab 巡覽；主要動作焦點明確；靠泊序列每完成一條以 `aria-live="polite"` 播報，
  失敗用 `assertive`；錯誤訊息與其欄位可程式關聯。
- **回饋**：靠泊序列逐條顯示並保留數值；失敗就地展開，**不跳離當前泊位**。
- **轉場**：泊位格換狀態是色塊填充；工作面切換是橫向推進（船靠泊的方向）。
  `prefers-reduced-motion: reduce` 時全部降為即時切換。
- **語言切換**：橫幅右上角一組雙字碼 `ZH / EN`。預設讀 `navigator.language`，選擇存 localStorage，
  setup 完成後寫回使用者設定。

## 7. 限制與未決

**限制**

- React 19 + TypeScript + Vite + Tailwind v4 + TanStack Router / Query + react-i18next（已在 repo）。
  plan §7 指定 shadcn/ui 為元件基礎。
- WCAG 2.2 AA 是驗收條件。四個信號色在深淺兩主題都要達對比；狀態不得只靠顏色。
- 外部服務的行為一律以 brief §20 與 `docs/research/m0-experiments.md` 為準，不憑文件猜。
- 檔名 token、log、識別符英文；UI 文案全部走 i18n key。

**未決，實作時要解**

- **字體**。方向要求「模板噴字 + 貨櫃編號等寬」，但字面未選。**中文沒有大小寫**——
  `text-transform: uppercase` 對中文無效，寬字距在中文的可讀性也不同，所以「標籤」這個樣式
  必須在 zh-Hant 與 en 下**各自**成立。這是這個方向最大的實作風險。
- **亮色主題**。plan §7 要求深色預設、亮色跟隨系統。塗裝色塊的語彙在亮色下怎麼成立要實作時定案。
- direction contract 與 surface brief 由票 05 的 build session 寫；DESIGN.md 在票 11 由 documenter 產生。
