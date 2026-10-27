# 10 — 「為什麼沒入庫」的聚合讀取命令

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** plan §11.6〈分段〉第 4 段；`docs/research/m5-ai-direction-2026-10-27.md` C6 情境 3；`docs/research/m5-prototype-2026-10-27.md` 的 S4 逐字稿（`docs/research/m5-prototype-2026-10-27/anthropic-S4.md`）；`berth/services/jobs.py`、`events.py`、`issues.py`、`rss.py`、`inventory.py`（`read_holdings` 的 `missing`）

## 為什麼

「為什麼這集沒入庫」的答案散在五張表：Job 時間線、事件、Issue、RSS Item（被排除？沒綁定？）、作品的缺集。prototype 裡模型要叫四到八次工具才拼得出來。一支聚合的唯讀命令讓 agent 一次拿到，人也用得到。它不需要 AI，是 M5 第一個 tracer 情境的資料來源。

## 做什麼

1. 讀取命令（`READ`）：給一部作品，或一部作品加一集。回傳：
   - 季表上的狀態（播了沒、入庫沒）。
   - 相關的 Job 和它們的狀態與最後幾筆事件。
   - 開著的 Issue。
   - RSS 那一側：有沒有綁 Series、Item 是不是被排除、在不在待綁定。
   - 一個**結論分類**：沒有來源、還在下載、等審核、入庫失敗、Jellyfin 還沒掃到、被排除。
2. 結論分類的規則只寫一份，前端與 agent 都讀它。
3. 一般使用者看得到的範圍照 brief §19「M5 的方向」⑦。
4. 這張不做 UI；Media 詳情頁要不要露出，等票 22 收尾時再看。

## 驗收

- [ ] 每一種結論分類各有一個情境測試（用現有的 fixture 與 Fake 情境）
- [ ] 一般使用者看不到別人的 Job（測試）
- [ ] plan §6 補 API；`pnpm gen:api`；全部檢查與 pytest 綠；progress.md 已更新

## Comments
