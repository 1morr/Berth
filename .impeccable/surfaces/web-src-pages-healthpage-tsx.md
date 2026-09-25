---
version: 1
slug: "web-src-pages-healthpage-tsx"
primary_target: "web/src/pages/HealthPage.tsx"
related_targets: ["web/src/pages/JellyfinSettingsPage.tsx","web/src/pages/QbittorrentSettingsPage.tsx","web/src/settings","web/src/health"]
---

## Scope

健康頁 `/health` 與設定頁 `/settings/*`（票 06i 起一格泊位一頁，見 `.scratch/m3/settings-shape.md`）。**Visitor mode: Operate。** 完整規格
（讀者、狀態、量級、修正建議、開放決定）在 `.scratch/m0/health-shape.md`，不在此重複。
票 10 建這兩頁；M2 的 Reconciler 結果與 Issue 清單會接在健康頁下方。

## Audience and job

平常沒有人看這兩頁。人打開它們只有兩種時刻：**有東西壞了**（Jellyfin 播不出新集、送單失敗），
或**剛改了什麼**（重開 NAS、換了密碼、動了媒體庫路徑）想確認 Berth 還接得上。兩種人都可能是
`user` 而不是 `admin`——診斷是唯讀資訊，人人看得到；動作只有 admin 有（brief §11）。

## Proof

只放實測值：版本號、索引站數量、最後成功時間、連續失敗次數、`dev=… · inode=… · free=…`、
服務回的英文原文。**只有 Berth 說得出來的那句話**：三個容器的掛載視圖只有它同時看得到，
「Jellyfin 看不到 Berth 剛寫進 Route 目標的檔案」qBittorrent 與 Jellyfin 自己都說不出口。

## Direction contract

**THESIS.** 健康頁不是一排綠色勾勾，是**同一塊泊位板的第二個問句**。精靈問「接上了沒」，
這裡問「還繫著嗎」——所以四格的位置與意義完全不變，只是狀態由 `health_checker` 每 5 分鐘寫一次。
拒絕 uptime 儀表板的類別預設（折線圖、百分比、綠色勾勾牆）。

**OWN-WORLD.** 沿用票 05 鎖定的「泊位調度板」（`web-src-pages-setuppage-tsx`）：鋼灰藍船體底、
塗裝色塊填滿整格、重橫線、等寬數字。**四個信號色的規則在這裡多一個用法**——`assigned`
（需要你）指的是「設定漂移」：那台服務好好的，只是有人改了建議值，紅色仍然只代表阻擋。

**STORY.** 一眼看出哪一格紅了 → 讀出服務自己說的那句原文 → 拿到那一項的修正步驟
（套件內是三條 docker 指令，既有是回精靈改連線）。

**FIRST VIEWPORT.** 頂端整寬泊位板（四格：Jellyfin / qBittorrent / 來源 / 媒體庫路徑），
下方是「上次檢查 N 分鐘前」與「立即重測」，再往下逐項明細。**全綠時這一頁很短**：
Route 的五條纜繩收起來，只有紅的那條就地展開。

**FORM.** 署名互動的延伸：精靈的「靠泊序列」在這裡是「複驗序列」——`RouteCheckList` 與
`StepLine` 是同一個元件，所以「精靈當時是綠的、現在紅了」在畫面上是同一種東西。

**FINISH.** unreviewed and undocumented is unfinished；DESIGN.md 由票 11 產生。

## Constraints

React 19 + TS + Vite + Tailwind v4 + TanStack Router / Query + react-i18next。WCAG 2.2 AA 是驗收
條件，深淺兩主題都要達標（票 10 實測最低 5.71:1）。UI 文案全部走 i18n key，zh-Hant 與 en 並列。
**開頁不自動重測**：那一輪檢查會在 qBittorrent 建 category、在媒體庫寫探測檔，不該是重整頁面的
副作用。

## Resolved during build (票 10)

- **兩個路由而不是一頁兩區塊**（使用者決定）。頁首因此長出導覽（`健康` / `設定`），
  `設定` 只對 admin 顯示；`/` 先導向 `/health`，M1 的探索頁接手之前不留兩個網址畫同一頁。
- ~~位址與憑證不在設定頁改~~（票 06i 推翻）：**精靈只管第一次，設定頁接手**。設定頁重用精靈的
  連線表單（同一個元件、同一支 `setup/*` 命令），所以「兩份規則分岔」的顧慮仍然被避開。
- **Route 綠燈收起、紅燈就地展開**（使用者決定）。`display: flex` 會吃掉 `<summary>` 的三角形，
  所以展開與否用模板字自己說出來（`展開檢查` / `收起`），否則收起來的那一列看不出它按得開。
- **漂移的說明不自己指路**：同一張卡片同時出現在健康頁與設定頁，「到服務設定頁看差異」那句話
  在設定頁上是錯的。指路是頁面的事，所以健康頁的漂移卡片多一顆「前往設定：qBittorrent」，設定頁沒有。
- **差異表讓長路徑換行**，不橫向捲動——被切掉的建議值等於沒顯示（實測暫存目錄的長路徑）。
- **時間點兩種都給**：相對說法（`3 分鐘前`）給人掃視，絕對時間留在 `<time datetime>` 與 `title`。
  維運頁面上「三分鐘前」與「三小時前」是兩件事，而 ISO 字串沒有人在掃視時算得出來。
