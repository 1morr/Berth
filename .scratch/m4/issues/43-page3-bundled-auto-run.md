# 43 — 頁 3 套件內進頁自動建立並檢查、顯示進度

**Status:** done

**Blocked by:** None — can start immediately（建議排在 40 之後，避免與精靈的其他改動撞檔）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S1 頁 3「約 30 秒…看不到進度」、「Berth 精靈哪裡不統一」第 9 條、簡化方案 E-4、改進清單 P2-1）；brief §19「精靈審計後的八項」D7、§16.3；plan §9.3；M4 票 08、M3 票 06d；`PRODUCT.md`、`DESIGN.md`；先跑 `/impeccable shape`（頁 3 的互動改了）

## 為什麼（2026-10-06 審計）

- 套件內「建立並檢查」大約跑 30 秒，期間只有一顆「建立並檢查中…」，是這次走查最明顯的「卡住感」。截圖 s1-07。
- **D7 拍板**：套件內的預設清單沒改時，進頁就自動建立並檢查，並顯示進度。票 08「進頁不送寫入」只留給既有。

## 做什麼

1. 套件內、媒體庫清單是預設且沒有被改過、這一頁還沒完成時：進頁自動跑一次。要改清單時才展開編輯，改了就回到按鍵。
2. 每條 Route 顯示跑到第幾條纜繩。用已有的 `running` 狀態輪詢就好；只有輪詢真的不夠時才加 SSE，加之前回報。
3. 重新整理、回到這一頁時不重跑已完成的，也不重複寫入（冪等已由票 24 守著，補一條測試）。
4. 既有維持按鍵。
5. brief §16.3、plan §9.3 頁 3 的敘述同一個 commit 改；progress.md 記這張推翻了票 08 在套件內的那一半。

## 驗收

- [x] vitest（雙向）：套件內、預設清單 → 進頁自動跑；改過清單或既有 → 不自動跑
- [x] vitest：進度逐條 Route、逐條纜繩更新
- [x] 整合測試：連進兩次只建一次（媒體庫、分類不重複）
- [x] `/impeccable shape` 的結論記在 `.scratch/m4/`；playwright 實跑 S1 頁 3，附進行中與完成的截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e、真服務 e2e 綠燈

## Comments

**做了什麼**（shape：`.scratch/m4/route-auto-run-shape.md`，使用者三題都照建議：進頁立刻跑、只在什麼都還沒做時、先畫好每條 Route 列）

- 後端：Route 檢查每條纜繩開跑前把那一列寫成 `running` 並 commit（`routes._progress` / `_running_from`；登入 qBittorrent 算第一條，登入前就寫）；`GET /setup/jellyfin` 多 `bundled_default`。
- 前端：`setup/autoDock.startsOnItsOwn`（套件內、清單是預設、沒有建好的、沒有 Route、建媒體庫那一步從沒跑過、版本夠新）加上這一頁還沒做完時，進頁照存下的清單送一次 `dock`（這一次不另外重讀）；頁 3 在送出中或伺服器說建媒體庫／某條纜繩還在跑時每 1.5 秒輪詢（`librariesRunning`、`routesRunning`）。按下那一刻這一輪的 Route 先畫成「等待中」列；跑著的那一列色塊「檢查中」、摘要「第 k / 6 條 · 纜繩名」（`RouteIdentity`、`CheckTally`，三頁共用）。清單跑的時候收起；自動開跑說一句為什麼，留到人自己按為止。
- 輪詢晚到的那一份不蓋掉結果：`dock` 成功時先 `cancelQueries`。

**實跑 S1 頁 3**（工作樹 build，tests/e2e 那一套隔離的 `berth-e2e-*`，port 28383；用完 `down --volumes`）：頁 1 建管理員 → 頁 2 套件內 → 進頁 3 不按任何東西，12.7 秒跑完三條：0–4 秒三列「等待中」、上方「建立清單上的媒體庫」進行中；5 秒起 Movies「檢查中 · 第 3 / 6 條 · qBittorrent 讀得到 Berth 寫的檔案」，其餘等待中；逐條走完 3 × 6 / 6，「前往下一個泊位」亮起。截圖 `.playwright-mcp/t43/t43-progress-*.png`、`t43-done.png`（gitignore）。

**code-review**

- 已修（Spec）：被打斷的一輪留下的 `running` 原本會被健康迴圈的 `_last_probe` 原樣沿用、永遠不消（`_last_probe` 改當成沒問過；連帶發現寫進度會蓋掉上一輪結論，改成先讀好每條的上一次）；Route 建好到第一條纜繩之間（登入 qBittorrent）沒有 `running`，重新整理接不上（登入前先寫）；跑到一半重新整理時沒輪到的也說「等待中」。
- 已修（Standards）：`type: ignore` 補原因、`stillRunning` 拆成兩支、「有纜繩在跑」收成 `routeChecks.checking`、`entry` 改具名 union、兩個 `peek` 抽成 helper。
- 未處理：健康頁與 Route 設定頁的「立即檢查」不輪詢（等結果回來），畫法相同但看不到中途——不在票面範圍。容器在檢查中途被殺時，精靈期間（健康迴圈還沒開始跑）那條 `running` 會留到下一次有人按「重新檢查」，頁 3 在那之前每 1.5 秒輪詢一次；Jellyfin 序列的 `running` 本來就是同一個性質。「等待中」在真的 Route 列上是字、在佔位列上是色塊（佔位列沒有健康色塊可放）。`DockPlan` 帶 `onItsOwn` 給畫面讀（effect 裡不能 setState）。
