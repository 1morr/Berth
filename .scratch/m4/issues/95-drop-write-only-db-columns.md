# 95 — 簡化：刪掉沒有用途的資料庫欄位，稽核欄位寫明用途

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S33；`berth/migrations/` 最新幾支與 `7c3e5a9b2d41` 的 docstring（batch 重建時外鍵順序的地雷）；`docs/plan.md:105,127,131,134`（資料模型）；`docs/development.md`（migration 怎麼寫、怎麼測）

## 為什麼

票 86 審計找到七個只寫不讀的資料庫欄位。使用者（2026-10-13）照協調者建議：沒有用途的 4 個刪掉；另外 3 個當稽核紀錄保留，寫明用途。

## 做什麼

- **刪**（一支 migration，加上所有寫入點與測試斷言）：
  - `jobs.last_seen_in_client_at`：註解說的那個消費者不存在。
  - `job_files.updated_at`：只有兩條路徑寫入，語意說不清。
  - `ledger.link_mode`：值永遠是 `hardlink`。`HARDLINK` 常數與它的 re-export 沒人用了，一起刪。
  - `ledger.source_inode`：判斷 inode 不符與刪除檢查用的是 `source_dev` 加 `target_inode`。
- ledger 用 SQLite 原生 `DROP COLUMN`，**不要用 batch 重建**（`7c3e5a9b2d41` 記載了原因）。`source_inode` 是 NOT NULL，建列的 tests、scripts 約 11 處要改。
- **留，寫明用途**：`plans.decided_by` / `decided_at`（誰、什麼時候批准了計畫；plan 承諾過）、`users.last_login_at`、`settings.updated_at`。在 `plan.md` 的資料模型寫明它們是稽核欄位、目前沒有讀者。
- migration 要有 downgrade；升級再降版再升版的 schema 比對測試要綠。

## 驗收

- [ ] 四個欄位已刪，產品程式碼、tests、scripts 沒有殘留；migration 的 upgrade、downgrade、再 upgrade 都過，既有的 schema 比對測試綠
- [ ] 用一份舊版（v0.2.4）建出來、帶資料的資料庫實跑升級，資料不丟（隔離環境，**不准碰使用者的 `berth-local`**），貼輸出
- [ ] `plan.md` 資料模型同步；CHANGELOG 寫明這版有 migration（升級說明會用到）
- [ ] 全部檢查、pytest 綠；progress.md「偏差與決定」記一行
