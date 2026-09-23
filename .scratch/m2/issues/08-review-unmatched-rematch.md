# 08 — Review Queue 3/3：Unmatched 指派 + `rematch_file` + duplicate

**Status:** done

**Blocked by:** 07（佇列的第三、四類要接在 Plan 編輯之後才有清單可放）、04（`rematch` 的舊鏈接刪除走同一組旗標）

**讀:** plan §6（files 群組、review 群組）、§4.1（階段，Unmatched 從哪來）、§11.3 的決定 8；brief §7.4（Unmatched）、§7.8（重複版本）、§9.4（Rematch）

## 做什麼

佇列的最後兩類，加上 Media 詳情上的**修正**入口。

**`POST /files/rematch`**（`{ledger_id | job_file_id, action, season, episode_start, episode_end}`）：
**內部建一份單 item 的 Plan 並立刻套用**（決定 8，brief §9.4「一律經過 Plan」）——
`plans.job_hash = NULL`、`engine = user`、`source_path` 是那個檔案，走同一條 `apply_plan`
（建新鏈接 → 刪舊鏈接 → 改帳本 → 通知掃描）。對外是一支命令，UI 不必看到一份只有一列的 Plan，
但 Plan 歷史與 event 留得下紀錄。

**Unmatched 的三個動作**：指派為 SxxEyy / 標記 extra / 忽略。入口有兩個——`/review` 佇列的
`unmatched` 那一類，以及 Media 詳情的 Unmatched 區（brief §9.4 說的是「Media 頁對某個檔案」）。
兩邊打同一支 `rematch`。

**`duplicate`**（brief §7.8）：新 Plan item 與帳本既有 Entry 的（Media, 季, 集, tags）完全相同。
自動模式**跳過並記事件**；review 提供「取代舊版」「保留兩者」「跳過」。目前這種情況是撞同一個
目標路徑以 `target_exists` 停下——這一票讓它在佇列上成為一列說得出理由的 `duplicate`。

**多集檔與同起始集的單集**（brief §7.8 後半，2026-09-15 拍板）也在這一類：`S01E03-E04` 對
`S01E03` 起始集相同、結束集不同 → 送 review，理由要說出後果（Jellyfin 12 的版本分組鍵只有
季號與集號，會把它們併成同一集的兩個版本，後面那一集從集列表消失）。這條規則 M1 票 14b 已經
擋下來了，這一票是讓它在佇列上有一列能按。

## 驗收

- [x] `rematch` 三個動作各走一次完整路徑：新鏈接建起來、舊鏈接刪掉、帳本改掉、Jellyfin 收到掃描
      通知（整合測試）
- [x] `rematch` 留得下紀錄：`plans` 多一份 `engine = user`、`job_hash = NULL` 的單 item Plan，
      event 說得出誰改的、從什麼改成什麼
- [x] Media 詳情與 `/review` 兩個入口打同一支命令（不是兩套邏輯）
- [x] `duplicate` 在佇列上是一列，三個動作各有整合測試：取代舊版 / 保留兩者 / 跳過
- [x] 多集檔對同起始集的單集出現在佇列上，理由說得出「Jellyfin 會併成同一集的兩個版本、後面
      那一集會從集列表消失」
- [x] `user` 登入時 `/files/*` 是 403，Media 詳情上看不到修正入口
- [x] playwright 實跑一次 Unmatched 指派與一次 duplicate 決定，附截圖或文字結果
- [x] lint、type、test 綠燈

## Comments

- 2026-09-23 code-review（Spec）：`_duplicate_of` 的範圍衝突那一支**照樣比這一筆自己的鏈接**（same-version 那一支
  排除自己）——**刻意不對稱，不改**：同一個來源這一次讀成另一段範圍時，importer 不會把它當成同一條鏈接，
  而是多鏈一條、舊的留著，Jellyfin 把兩條併掉。交給人決定，「取代舊版」正好把它搬到新範圍。寫進
  `_against_ledger` 的 docstring。
- 2026-09-23 code-review（Spec）：取代舊版只鎖新的那一筆（修掉，兩把、照 hash 排序；`TestTheOldDownload`，
  只鎖一把會紅）；取代之後舊 Job 那一份 Plan 的那一列仍說已入庫（修掉，`Move.displaced`）；預估沒記
  `duplicate_of`（修掉）。
- 2026-09-23 code-review（Standards）：`Fix` / `Fixing` 違反 CONTEXT.md 的 Rematch 詞條（改名 `RematchEntry` /
  `Rematching`；按鈕文案「修正」照留）；帳本字幕查詢兩份收成 `rematch.sidecars_of`；路徑重算改用
  `rematch.full_path`；`RematchForm` 的 queryKey 改走 `reviewQueryOptions()`；布林 `follows` 改名 `following`。
- 對不到的字幕只能忽略（使用者拍板）：指派到某一集要選掛在哪一個版本旁邊，是另一道題，**沒有排進任何一張票**。
- 取代舊版時，被取代那一筆 Job 的時間線上沒有事件（新的那一筆有 `duplicate_decided`，帶 `replaced`）；
  它那一份 Plan 的那一列改成略過並多一條 `set_by_user`。沒有 repro 說需要，記一行。
- 同一集的兩份重複**同時下載完**時，規劃那一刻帳本上兩份都還沒有，所以都不算重複；後入庫的那一份在 importer
  撞到路徑，照舊以 `target_exists` 停在 review（規劃時的判斷看不到正在鏈接的東西）。沒有 repro，記一行。
- `review` 情境的 `UnmatchedRow` / `DuplicateRow` 展開區的來源路徑在 Windows 開發機上是反斜線（`fs.under`
  的 `Path` 呈現）；容器裡是 POSIX，不處理。
