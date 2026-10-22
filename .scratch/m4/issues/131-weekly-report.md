# 131 — 週報：每週存一筆、週報頁、推摘要

**Status:** done

**Blocked by:** 129、130

**讀:** plan §11.5〈巡檢〉（週報每週存一筆的理由）；brief §14；`berth/models/event.py` 與事件型別（入庫、核准、rematch、Issue 收掉）；`berth/services/deletion.py` 的 `_purge`（會刪事件）；票 123 的通知寫入、票 124 的連結；DESIGN.md

## 為什麼

週報回答三件事：這週入庫了什麼、修了什麼、還有什麼等人。purge 會連事件一起刪，所以當下算好存下來，之後回頭看的舊週報不會跟著變。

## 做什麼

1. **開頭先 `/impeccable shape` 週報頁**（`.scratch/m4/weekly-report-shape.md`）。
2. 每週一次（週一早上，照容器時區）產生一筆週報存起來：入庫了什麼（依作品，季集範圍）、修了什麼（核准、rematch、Issue 被收掉或解決）、還有什麼等人（等你處理的總數與種類、巡檢開出的 Issue）。
3. 週報頁：最新一週與歷史；只有管理員看得到（M4 範圍）。
4. 給訂閱週報的管理員推一則摘要，附週報頁的連結（票 124）。
5. 同一週不重複產生（重啟、補跑都不會多一筆）。

## 驗收

- [x] 一週的假資料 → 週報的三段內容正確（pytest）
- [x] 產生之後 purge 一筆 Job，存下的週報不變（pytest）
- [x] 同一週重跑不多一筆（pytest）
- [x] 摘要推給訂閱的管理員、附連結（pytest）
- [x] 週報頁與歷史（vitest；playwright 實跑 1280 與 390 附截圖）
- [x] 全部檢查、pytest、vitest 綠；CONTEXT.md「週報」；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-22（實作）：shape 在 `.scratch/m4/weekly-report-shape.md`，協調者確認四項：頁首導覽加「週報」、管理員預設訂閱（migration `a8c3f6e1d254` 補既有管理員）、一週一頁＋歷史清單、「巡檢開出的 Issue」取產生當下還開著的巡檢型別（Issue 表沒有開出時間）。截圖 `131-weekly-report/weekly-1280.png`、`weekly-390.png`（e2e `weekly` / `weekly-390`，演練情境 `weekly`）。
- **沒有「現在產生一份」的端點**：票面沒要求，排程（`sweeper`）與重啟補跑已經涵蓋。票 133 的 e2e 要「觸發一次產生」時再定入口（例如 CLI 或只給 e2e 的路徑），而且要想清楚觸發的那一份涵蓋哪一段：週報的一週是週一 05:00 到下一個週一 05:00，當週的入庫要到下週一才進得了週報。
- 排程與巡檢不同的兩處（plan §3.2）：重啟之後補上漏掉的那一週（同一週什麼都不寫，不會多一筆）；只有一份都沒有的新裝不補。寫壞了照樣往前走，由下一次啟動補。
- 前端的兩個小落差，留給票 132 的 critique 判斷：抬頭的「產生於」用瀏覽器時區、週界線用容器時區，兩者不同時日期可能差一天；入庫清單前端照介面語言的標題 `localeCompare` 排，後端存的順序是英文標題。
- code-review（Standards／Spec 兩軸）已改：前端 `requireAdminPage` 只給週報用的半套抽取，改成 `/issues`、`/review`、`/rss` 一起用；演練替身改用 `actor_of(None)` 與 `PlanStatus.APPROVED`。**沒處理的**（判斷題，留給之後有需要時）：
  - `services/weekly` 的三段先組成 dict 存、讀的時候再照同一組鍵拆回 dataclass，形狀寫了兩次（存的就是那個 dict，改鍵要兩邊一起改）；works／episodes／fixed／waiting 四個數在 `WeeklyLine`、API、摘要內容、`_render_weekly` 一起出現。
  - 前端自己加總「修了幾件」「等著幾件」與集數，後端 `Fixed.total`、`StillWaiting.total` 沒有帶出 API，定義有走偏的風險。
  - `FixedSection` 與 `WaitingSection` 的列是同一段 markup；`ImportedSection` 的 ` · ` 寫死、`TypeCounts` 的分隔走 i18n；`isMissing` 與 404 不重試的判斷各寫一次。
  - `weekly` 從 `notify` import `episode_spans`（只為了這一支純函式）；`Sweeper` 同時管巡檢與週報的排程。
  - 沒有 Job 的帳本列（`rebuild-ledger`、認領）rematch 時不寫事件（`rematch.py` 只在有 Job 時記），所以不算進「修了什麼」。
