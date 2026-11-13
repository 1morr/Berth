# Berth 路線圖

> 里程碑的順序、狀態、開工前要讀什麼。還沒開工的里程碑在下面各有一小節；開工 session 把那一節細化成 `.scratch/<里程碑>/spec.md`，這裡縮成一行連到它。已驗收的里程碑，當時的範圍在 `docs/archive/<里程碑>.md` 的 `## plan §11`。

## 里程碑

| 里程碑 | 目標 | 票目錄 | 拆票前讀 | 狀態 |
| --- | --- | --- | --- | --- |
| M0 | 骨架 | `.scratch/m0/issues/` | — | 已驗收（2026-09-08），封存於 `docs/archive/m0.md` |
| M1 | 手動全流程 | `.scratch/m1/issues/` | — | 已驗收（2026-09-17），封存於 `docs/archive/m1.md` |
| M1.5 | 媒體庫瀏覽 | `.scratch/m1.5/issues/` | — | 已驗收（2026-09-19），封存於 `docs/archive/m1.5.md` |
| M2 | 修正與對帳 | `.scratch/m2/issues/` | — | 已驗收（2026-09-24），封存於 `docs/archive/m2.md` |
| M3 | RSS | `.scratch/m3/issues/` | — | 已驗收（2026-09-26），封存於 `docs/archive/m3.md` |
| M4 | 巡檢與通知 | `.scratch/m4/issues/` | — | 已驗收（2026-10-23），封存於 `docs/archive/m4.md` |
| M5 | AI 地基與對話 agent | `.scratch/m5/issues/` | — | 已驗收（2026-10-28），封存於 `docs/archive/m5.md` |
| M5.5 | 新番與導覽 | `.scratch/m5.5/issues/` | — | 已驗收（2026-11-04），封存於 `docs/archive/m5.5.md` |
| M5.6 | AI 對話精簡 | `.scratch/m5.6/issues/` | — | 已驗收（2026-11-08），封存於 `docs/archive/m5.6.md` |
| M6 | 人工接管開關 | `.scratch/m6/issues/` | plan §11.7；brief §14、§6.10、§20.29 | 進行中，已拆 12 張票。人工接管開關、第一批背景 AI 任務、AI 評估；先修 M5.6 遺留並發 0.5.2（2026-11-10 拆出 M6.5） |
| M6.5 | Issue 與巡檢交給 AI | `.scratch/m6.5/issues/` | plan §11.7b；brief §14 | 未開工。Issue 與每週巡檢交給 AI、修正回流（2026-11-10 從 M6 拆出） |
| M7 | Discord 與 MCP | `.scratch/m7/issues/` | plan §11.8；brief §14、§16.2 | 未開工。Discord 與 MCP（2026-09-22 加入、09-24 加 MCP、10-27 改名） |
| docs-diet | 文件瘦身 | `.scratch/docs-diet/issues/` | — | 已驗收（2026-10-30），封存於 `docs/archive/docs-diet.md` |
| docs-diet-2 | brief 與 plan 瘦身 | `.scratch/docs-diet-2/issues/` | `.scratch/docs-diet-2/spec.md` | 未開工。9 張票已拆，和 M6 的票互不相擋；用 `/1morr:ticket-coordinator .scratch/docs-diet-2/issues` 跑 |

開工：使用者在新 session 下 `/to-tickets docs/roadmap.md 拆 <里程碑> 的票`，那個 session 寫 `.scratch/<里程碑>/spec.md`、把本檔它那一節縮成連結、拆票，步驟在 `CLAUDE.md`〈Skills〉。沒開工的里程碑只在本檔；開工後以 spec 與票為準。

## M6 人工接管開關

開工於 2026-11-11，範圍、驗收與票序在 `.scratch/m6/spec.md`。

## M6.5 Issue 與巡檢交給 AI

2026-11-10 從 M6 拆出。沿用 M6 的開關、AI 評估、驗證、`ai_worker` 與 AI 活動頁；新的任務型別一樣附案例集。

範圍：
- **Issue 的各型別**：可逆的自動，刪檔與放棄追蹤做成 Proposal（`docs/research/m5-ai-direction-2026-10-27.md` C1 表的 Issue 與巡檢 Issue 那幾列）。
- **重複版本**（審核頁）：「保留兩者」「跳過」由 AI 做，「取代舊版」做成 Proposal（C1 表那一列；2026-11-10 補進，M6 第一批漏列）。
- **`episodes_overdue`**（M5.5 加的，C1 表沒有）：依 `detail_json` 的卡住原因做——`submit_failed`、`stalled`、`download_failed`、`import_failed` 重試或換字幕組搜尋並送單（受送單的數量與磁碟閘），`not_released` 只記理由、等下一輪。
- **每週巡檢**把程式檢查標出的項目交給 AI：可逆的修、其餘交給人，寫進週報（brief §14〈巡檢〉）。
- **修正回流**：寫回 RSS Series、標題別名、排除條件；改正過的案例進 benchmark 候選語料。

驗收：
- 一件 `library_link_missing` 不經人修好；刪 complete 的請求停在 Proposal（整合測試）。
- 新的任務型別的 AI 評估達到 M6 的同一個門檻（件數照風險分級、套用的錯 0 件、交回人的比例 ≤ 5%）；缺集搜尋與 `episodes_overdue` 的重送照樣受送下載的閘。
- 週報說得出 AI 這週修了什麼、交給人什麼。
- 關掉 AI 時與 M4 相同。

## M7 Discord 與 MCP

範圍：
- **個人 API token**（brief §16.2）：Discord 身分綁定與 MCP 都靠它，帶著使用者的角色。
- **Discord 對話**：把 M4 的 bot 接上 M5 的同一個核心，同一個 bot 既推通知也收訊息。
  - gateway 長連線；家用伺服器沒有公開網址，所以不用 Interactions Endpoint，brief §20.23。
  - 只處理已綁定 Berth 帳號的人。
  - 確認卡是帶按鈕的訊息：persistent view，重啟後仍可點；只有發起人按得到。確認 / 拒絕回到同一個 `proposals` 列。
  - 長度切分、3 秒初始回應、沒有按鈕時的文字備援（`/approve <id>`）。
  - 斜線指令與 M5 共用同一份登錄表。
- **MCP server**：命令登錄表匯出，同一組個人 API token 與門禁。MCP 的 tool annotations 只是提示，「永遠要人」的命令在 server 端照樣擋。
- **外部 MCP client**（例如 Tavily MCP）：只放行 allowlist 內的工具、用 Berth 自己寫的工具描述、描述雜湊一變就停用，結果當不可信資料。
- 給外部 agent 的 skills 文件。

驗收：
- 在手機的 Discord 裡收到「S02E05 正在下載」，回一句「下好了通知我並標成已看」，Berth 在入庫後推第二則並標成已看。
- 一般使用者在 Discord 與 MCP 上碰到的是同一道門禁。
- Claude Code 經 MCP 查得到本週入庫。

## 不排里程碑

M0–M5.6 驗收與回顧時留下、沒有排進 M6 / M6.5 / M7 的項目。有 repro 或使用者要求再開票。原文都在 `docs/archive/` 的 `## plan §11`，這裡只留索引。

| 項目 | 原出處 |
| --- | --- |
| `ROUTE_CHECKS`（`web/src/api/schemas.ts`）仍是手寫字面聯集；收緊要先為 Route 檢查另開 `RouteCheckOut` | `m2.md` §11.3 D 組 |
| 對不到的字幕只能忽略、不能指派到某一集（rematch 的延伸） | `m2.md` §11.3 D 組 |
| `issues.detail_json.action` 一鍵兩義（偵測是 `PlanAction`、resolve 被覆寫成按的那顆） | `m2.md` §11.3 D 組 |
| `AccountDisabledError` 也涵蓋帳號被刪，名實不符（對外 `account_disabled` 不動） | `m2.md` §11.3 D 組 |
| `.impeccable/design.json` 沒有閘門，一條比對測試守得住 | `m2.md` §11.3 D 組 |
| Job 摘要列只浮 audit，對不到與重複待決沒有（`JobOut` 要多兩個計數） | `m2.md` §11.3 D 組 |
| 時間兩套寫法（`whenText` 絕對、`Timestamp` 相對），要先定全站慣例 | `m2.md` §11.3 D 組 |
| 七處輸入框 class 手寫、`rule-strong` 邊框沒有閘門 | `m2.md` §11.3 D 組 |
| 頁首不 sticky、`/` 快捷鍵、探索頁手機兩面牆無跳轉、說明無文件出口 | `m2.md` §11.3 C 組 |
| 每集短於 5 分鐘的短篇動畫被 `classify` 整包降成 extra（註解說的批次一致性救回不存在） | `m3.md` §11.4 收尾延後項 |
| `_rescreen` 先讀再寫會把剛送出的 Item 改回 `excluded`（要條件式 `UPDATE`） | `m3.md` §11.4 收尾延後項 |
| 全站頁面標題都是 `Berth`（`web/index.html`，沒有逐頁 `document.title`） | `m4.md` §11.5 M4 收尾遺留 |
| 角色只在登入時更新：在 Jellyfin 降權的人，已登入的 session 可能最長 30 天仍是 admin（推斷：`read_session` 只讀本地 `users` 列）；先寫一條會紅的測試，紅了再排小票，排在 M6 票 04 之後 | M5.6 回顧（2026-11-12） |
| 探索卡只標「追蹤中」，brief §13 寫的未追蹤／部分／完整／下載中四種沒做（`services/discover.py` 註解說等帳本）；補做或改 brief 等使用者定 | M5.6 回顧（2026-11-12） |
| 5 分鐘的健康迴圈不跑 qBittorrent 探針（會觸發使用者「完成時執行外部程式」），掛載事後壞掉要按「重新檢查」才看得到；是取捨，留著記錄 | M5.6 回顧（2026-11-12） |
