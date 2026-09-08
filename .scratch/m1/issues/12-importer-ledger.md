# 12 — importer、ledger 與 Jellyfin 反查

**Status:** ready-for-agent

**Blocked by:** 11

**讀:** plan §3.1（importing 段）、§3.2（importer / jellyfin_resolver）、§3.3、§8.2、§8.6、
§11.2（T1.6 後半）；brief §4.4、§5.3、§7.7、§20.1

## 做什麼

**M1 的驗收就在這一票**：Plan 套用 → 硬鏈接進 library → 寫 ledger → 通知 Jellyfin → 反查 item id
→ 觸發 MergeVersions。做完之後，一部美劇一季、一部動漫一季、一部電影三者不經人工就入庫，並在
Jellyfin 正確顯示。

硬鏈接的方向照 brief §4.4：來源在 complete，目標在 Route 的 `target_path` 之下。寫入 library 的
路徑一律要在某個 Route 的 `target_path` 底下，否則 fs adapter 丟 `PathEscapeError`（plan §8.6）。

Jellyfin 反查用 brief §20.1 的兩段查詢，**不要用 `parentId=<seriesId>` 或 `/Shows/{id}/Episodes`**
（10.11 第一次掃描後兩者都回 0，plan §8.2）。

## 驗收

- [ ] `ledger` 表與 migration，`target_path` unique
- [ ] `importer` 事件驅動 + 每 60s 掃 `importing`；逐 item：建目錄 → `link()` → 寫 ledger → event；
      一次只處理一個 job
- [ ] 目標已存在且 inode 相同 → 視為已完成並補上缺的 ledger；inode 不同 → item 標
      `target_exists_foreign` 並進 review（plan §3.3）
- [ ] 任一 item 失敗且不可跳過 → `import_failed`；重試時已完成的 item 跳過
- [ ] 全部套用後 `POST /Library/Media/Updated` 通知 Jellyfin；失敗只記 event，不阻擋 `imported`
- [ ] `jellyfin_resolver` 以 brief §20.1 的兩段查詢找 item id，重試 30s → 2m → 10m → 1h 共 6 次；
      耗盡記 event（`issues` 表在 M2）
- [ ] MergeVersions 以 `settings.services.jellyfin` 存下的任務 Id 觸發；找不到只記 event
- [ ] 硬鏈接後來源與目標的 inode 相同（測試實際比對，不是只看回傳值）
- [ ] `EXDEV` 等 `OSError` 往上丟並帶 `errno`，訊息說得出是哪個掛載的問題
- [ ] 寫入 library 的路徑不在任何 Route 的 `target_path` 之下時丟 `PathEscapeError`（有測試）
- [ ] event 的去重規則（`(job_hash, type, payload hash)` 同一分鐘內）有測試，重啟不重複「completed」
- [ ] **一部美劇一季、一部動漫一季、一部電影三者不經人工入庫，並在真的 Jellyfin 顯示正確的
      季集、標題與海報**（brief §17 M1 驗收），附證據
- [ ] lint / type / test 全綠並貼指令輸出
