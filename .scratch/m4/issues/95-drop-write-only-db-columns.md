# 95 — 簡化：刪掉沒有用途的資料庫欄位，稽核欄位寫明用途

**Status:** done

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

- [x] 四個欄位已刪，產品程式碼、tests、scripts 沒有殘留；migration 的 upgrade、downgrade、再 upgrade 都過，既有的 schema 比對測試綠
- [x] 用一份舊版（v0.2.4）建出來、帶資料的資料庫實跑升級，資料不丟（隔離環境，**不准碰使用者的 `berth-local`**），貼輸出
- [x] `plan.md` 資料模型同步；CHANGELOG 寫明這版有 migration（升級說明會用到）
- [x] 全部檢查、pytest 綠；progress.md「偏差與決定」記一行

## Comments

### 2026-10-13 實作

- migration `a6c3e9f2b815`：升版四欄原生 `DROP COLUMN`。降版三個 NOT NULL 欄位原生加不回去（SQLite 要非 NULL 預設、當初沒有），先加成可為 NULL、補值，再 batch 改回 NOT NULL；補值：`source_inode = target_inode`、`link_mode = 'hardlink'`、`job_files.updated_at = jobs.added_at`。
- **票上沒寫、實作中發現的**：降版的 batch 重建會 `DROP TABLE`，外鍵開著（遷移在交易裡，關不掉）就觸發 `plan_items.job_file_id`、`plan_items.duplicate_of` 的 `ON DELETE SET NULL`。所以重建前把這兩欄抄進暫存表、重建後寫回。`test_dropping_write_only_columns_keeps_every_row` 守著；拿掉寫回那一段，測試紅在 `(…, None, None)`（手動變異驗證過）。
- `downloads._refresh` 的 `now` 參數、`reimport` 的 `utcnow` import 隨寫入點一起刪；`test_importer` 的「硬鏈接成立」改斷言 `target_inode == 來源的 st_ino`，不變式仍有測試守。
- brief §6 的 `ledger` 描述同步拿掉來源 inode（code-review Standards 軸指出）。

### 實跑：v0.2.4 建的資料庫升級

隔離環境：`git archive v0.2.4` 解到 scratchpad、`uv sync --frozen`，用 v0.2.4 的 `scripts/fake_setup_server.py` 起 `review`、`issues`、`library` 三個情境（各自的 config root、port 8695–8697，種完資料就停），三個資料庫各複製一份，用這個分支的 `upgrade_to_head` 升級，逐表逐列比對（扣掉刪的四欄）。沒有用 docker，`berth-local` 沒碰。

```
== db-review: d71e4b9a3c58 -> a6c3e9f2b815
   rows: {'events': 7, 'issues': 5, 'job_files': 8, 'jobs': 7, 'ledger': 6, 'media': 1, 'plan_items': 7, 'plans': 3, 'routes': 3, 'settings': 8}
   every row identical (minus dropped columns): True
   dropped columns still present: {'jobs': set(), 'job_files': set(), 'ledger': set()}
   foreign_key_check: clean; integrity_check: ok
== db-issues: d71e4b9a3c58 -> a6c3e9f2b815
   rows: {'events': 4, 'issues': 5, 'job_files': 3, 'jobs': 4, 'ledger': 3, 'media': 1, 'routes': 3, 'settings': 8}
   every row identical (minus dropped columns): True
   dropped columns still present: {'jobs': set(), 'job_files': set(), 'ledger': set()}
   foreign_key_check: clean; integrity_check: ok
== db-library: d71e4b9a3c58 -> a6c3e9f2b815
   rows: {'events': 1, 'job_files': 2, 'jobs': 7, 'ledger': 11, 'media': 7, 'plan_items': 4, 'plans': 3, 'routes': 3, 'settings': 7}
   every row identical (minus dropped columns): True
   dropped columns still present: {'jobs': set(), 'job_files': set(), 'ledger': set()}
   foreign_key_check: clean; integrity_check: ok
```

限制：資料是演練情境種的（真的 services 寫入，外部服務是替身），不是使用者真實的資料庫。

### code-review（兩軸 opus）未處理的

- Standards：測試裡兩段 `JOIN` 查詢只差欄位清單（Duplicated Code，判斷題，量小不抽）。CHANGELOG `[Unreleased]` 用「升級須知」而非「從 0.2.4 升級」，發版時對齊。
- Spec：降版用 `jobs.added_at` 回填 `job_files.updated_at`，若有找不到 Job 的孤兒列會在改回 NOT NULL 時失敗；`job_files.job_hash` 有外鍵 `CASCADE`，這種列不該存在，不處理。
