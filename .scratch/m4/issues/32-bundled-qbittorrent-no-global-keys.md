# 32 — 套件內 qBittorrent 不寫全域鍵；全域偏好不再影響 Route

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S5、§A1 BTH 2 列、§E「簡化方案」E-1、改進清單 P0-1）；brief §19「精靈審計後的八項」D2、§16.3、§16.4、§4.1、§20.2；plan §8.1、§9.3、§9.5

## 為什麼（2026-10-06 審計）

- **會擋送單（實測）**：使用者在套件內 qBittorrent 把全域 `save_path` 改成 `/data/my-downloads`，三條 Route 從 6/6 變 1/6「阻擋」、送單被拒。Route 檢查對套件內那一台另外現查全域 `save_path`，Berth 卻根本不用這個鍵：送單時每個 torrent 都帶分類與 `autoTMM=true`。既有那一台不看全域，同一段 docstring 自己寫了理由。
- **錯誤指錯對象**：錯誤掛在「qBittorrent 的路徑 Berth 看得到 `/data/torrent/complete/movies`」底下，內容講的卻是另一個目錄，還叫使用者「把它建回來」。截圖 s6-05。
- **D2 拍板**：套件內也不寫 `save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`。頁 2 差異表、設定頁漂移表、「還原建議設定」跟著拿掉。理由同 M4 票 22 拿掉 `temp_path`。

## 做什麼

1. 套件內 qBittorrent 的精靈寫入只剩 WebUI 登入。白名單預置不動。
2. Route 檢查對兩種來源都只看分類路徑（complete 與 incomplete），拿掉現查全域 `save_path` 那一段。
3. 拿掉頁 2「將會寫入的鍵」差異表、設定頁的漂移表與「還原建議設定」、健康頁的「設定被改過」，以及它們的 API、i18n 與測試。
   `POST` 還原那一支屬於對外 API 的破壞性刪除（D2 已拍板），要記進 CHANGELOG。
4. 已存在 `setup.qbittorrent.steps` 裡的三鍵步驟紀錄變成孤兒：寫資料 migration 清掉，或改成寬鬆讀取；選哪一種記在偏差。
5. 已經被 Berth 寫過全域鍵的安裝**不改回去**：Berth 沒有存原值，不知道使用者原本設的是什麼。
6. 文件同一個 commit 改：brief §16.3 表格的 qBittorrent 列與「還原建議設定」那一條、§16.4、plan §8.1 與 §9.3、README 的「套用五個建議鍵」。
   brief §16.3 頂端「待改寫」那句裡 D2 的部分拿掉。

## 驗收

- [ ] 整合測試（雙向）：套件內 qBittorrent 的全域 `save_path` 改成不存在的目錄，Route 仍是綠的；分類路徑看不到時才轉紅，錯誤講的是分類路徑
- [ ] 閘門測試：精靈走完套件內與既有兩種流程，Fake qBittorrent 收到的 `setPreferences` 只有 WebUI 登入的鍵。在測試檔內做雙向變異驗證：造一次寫 `save_path` 要變紅，改無關命名不變紅
- [ ] 舊的三鍵步驟紀錄經 migration 或寬鬆讀取後，頁 2 與設定頁都打得開（整合測試用一筆舊格式資料）
- [ ] 前端：頁 2 與設定頁不再出現差異表、漂移表、「還原建議設定」；zh-Hant 與 en 的鍵一起刪
- [ ] playwright 實跑：把套件內 `save_path` 改掉後，健康頁 Route 仍是綠的，送一筆單成功；附截圖
- [ ] brief、plan、README、CHANGELOG 已改；progress.md「偏差與決定」記一行
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
