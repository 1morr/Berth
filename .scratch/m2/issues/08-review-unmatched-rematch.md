# 08 — Review Queue 3/3：Unmatched 指派 + `rematch_file` + duplicate

**Status:** ready-for-agent

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

- [ ] `rematch` 三個動作各走一次完整路徑：新鏈接建起來、舊鏈接刪掉、帳本改掉、Jellyfin 收到掃描
      通知（整合測試）
- [ ] `rematch` 留得下紀錄：`plans` 多一份 `engine = user`、`job_hash = NULL` 的單 item Plan，
      event 說得出誰改的、從什麼改成什麼
- [ ] Media 詳情與 `/review` 兩個入口打同一支命令（不是兩套邏輯）
- [ ] `duplicate` 在佇列上是一列，三個動作各有整合測試：取代舊版 / 保留兩者 / 跳過
- [ ] 多集檔對同起始集的單集出現在佇列上，理由說得出「Jellyfin 會併成同一集的兩個版本、後面
      那一集會從集列表消失」
- [ ] `user` 登入時 `/files/*` 是 403，Media 詳情上看不到修正入口
- [ ] playwright 實跑一次 Unmatched 指派與一次 duplicate 決定，附截圖或文字結果
- [ ] lint、type、test 綠燈

## Comments
