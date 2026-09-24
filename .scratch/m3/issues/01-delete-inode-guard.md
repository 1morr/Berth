# 01 — 會刪檔的路先比 inode

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.4「M3 之前先做的修補」、§2.3（`ledger`）、§2.4（`issues` 的 `source_missing` 那一段）、§3.1 的 `delete_job` 那一列；brief §9.1、§9.2、§5.2；progress.md 2026-09-24「M2 後的全面審查」那一條偏差（文件落差清單）

## 做什麼

RSS 無人值守之後，下面這幾條會從偶發變成每週都碰到（plan §11.4）。這張票處理的是**會刪到使用者自己檔案**的那一組。

**刪之前先比 inode**。有三條路會拆掉媒體庫裡的鏈接：刪除範圍的「移除鏈接」、audit 撤銷、rematch 拆舊鏈接。使用者把硬鏈接換成自己的檔案之後（複製品、重新壓制的版本），這三條目前都會把它刪掉。改成：目標上那個檔案的 inode 不等於帳本記的（或不等於來源的）就**不刪**，並在回應與時間線上說出原因。三條路共用同一個判斷，不要各寫一份。

**只勾「移除鏈接」之後，對帳不再為那幾列重開 `library_link_missing`**。做法照 `source_missing` 的先例：那是使用者決定過的現況，不是破壞。

**刪除在鎖內讀 Job 狀態**。compare-and-set 輸了就回報失敗，不要回報成功。

**文件落差**，同一票一起收：

- `job_files.release_info_json` 沒有人寫（使用者拍板刪掉）。migration 拿掉這一欄，plan §2.3 同步；RSS 用的是 `rss_items` 自己那一欄。
- brief §13 媒體庫的「有 Issue」篩選沒做，也沒有票接（使用者拍板從 brief 刪掉：`/issues` 已經是獨立頁）。
- brief §5.2 `jellyfin_item_resolved` 的 payload 與程式碼不同：照程式碼更正 brief。
- `models/ledger.py`、`services/review.py` 裡「重新入庫的帳本沒有 Job」的註解已經過時（M2 票 10 之後有了），改掉。

## 驗收

- [ ] 三條刪除路徑各一條整合測試：目標被換成另一個 inode 的檔案時不刪、檔案原封不動，回應與時間線說得出「這不是 Berth 放的那一個」；inode 相同時照常刪
- [ ] 三條路走同一個判斷（拿掉那個判斷，三條測試一起紅）
- [ ] 刪除只勾「移除鏈接」→ 對帳一輪 → 那幾列不開 `library_link_missing`（整合測試）
- [ ] 兩個請求同時刪同一筆 Job，CAS 輸的那一個回報失敗，不是回報成功（整合測試）
- [ ] `job_files.release_info_json` 已被 migration 移除，plan §2.3 同步；brief §13 的「有 Issue」、brief §5.2 的 payload、兩處過時註解都已更正
- [ ] lint、type、test 綠燈
