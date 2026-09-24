# 01 — 會刪檔的路先比 inode

**Status:** done

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

- [x] 三條刪除路徑各一條整合測試：目標被換成另一個 inode 的檔案時不刪、檔案原封不動，回應與時間線說得出「這不是 Berth 放的那一個」；inode 相同時照常刪
- [x] 三條路走同一個判斷（拿掉那個判斷，三條測試一起紅）
- [x] 刪除只勾「移除鏈接」→ 對帳一輪 → 那幾列不開 `library_link_missing`（整合測試）
- [x] 兩個請求同時刪同一筆 Job，CAS 輸的那一個回報失敗，不是回報成功（整合測試）
- [x] `job_files.release_info_json` 已被 migration 移除，plan §2.3 同步；brief §13 的「有 Issue」、brief §5.2 的 payload、兩處過時註解都已更正
- [x] lint、type、test 綠燈

## Comments

- 2026-09-24 實作：判斷是 `deletion.Placed.holds`——目標的 `(device, inode)` 等於帳本記的（`source_dev`, `target_inode`），或等於來源現在的，才是 Berth 放的。會拆媒體庫鏈接的每一步都走 `remove_one(..., placed=)`，連 rematch 收回剛建的鏈接與 importer 收掉換了落點的舊鏈接也是（後者原本自己 `same_inode` 一份，行為等價）。沒刪的列在回應與事件的 `unmanaged`；撤銷的回應從 204 改成 `{unlinked, unmanaged}`。只勾「移除鏈接」拆掉的帳本列寫新的 `LedgerStatus.UNLINKED`。刪除的 CAS 搬到鎖裡第一件事、`expected` 是請求進來時讀到的狀態，輸了 409 `moved_on`；之後被拒絕（qBittorrent 問不到）時連轉換一起 rollback。
- 變異驗證（手動）：`Placed.holds` 恆真 → `test_unmanaged_targets.py` 8 條紅（三條路一起）；對帳拿掉 `UNLINKED` 的判斷 → `TestLinksTheUserRemoved` 紅；CAS 的 `expected` 改用鎖內讀到的狀態 → `TestTwoTabs[False]` 紅；前端 `Kept` 恆不畫 → 時間線兩條紅。`TestOneJudgement` 把第一條編碼進測試。
- playwright 對 `--scenario review` 實跑（截圖在 `.playwright-mcp/`，不進 repo）：把 S02E01 的硬鏈接換成自己的檔案 → `/review` 撤銷 → 回應 `{"unlinked": false, "unmanaged": true}`、結果那一句說沒有刪、檔案內容原封不動、時間線那一筆同一句；把 S01E01 換掉 → Job 頁刪除只勾「移除鏈接」→ E01 與情境本來就放的 E03 複製品都沒刪、E02 本來就不在（0 個鏈接），畫面多一句「2 個媒體庫檔案已經不是 Berth 放的那一個，沒有刪」、時間線列出兩條路徑；「立刻對帳」之後沒有 E02 的 `library_link_missing`，E01 / E03 是 `inode_mismatch`、S02E01 是 `unmanaged_library_file`。
- code-review Standards：無硬性違規；修了兩條（`rematch._take_back` 只收目標那一半的 facts、`_placed` 改名 `_ours` 避免與 `Placed` 撞名）。不修：估算時同一批鏈接 `stat` 兩輪（`_ours` 一輪、`_measure` 一輪；估算本來就慢而準，合併要讓 `_measure` 認得 `Placed`）；`_unlink_all` / `_remove_all` 迴圈形狀相似但回傳不同；`jobs.delete.kept_*` 與 `jobs.timeline.keptUnmanaged_*` 刻意分開（後者接路徑清單）。撤銷的 204 → 200 是 Berth 自己前端唯一的消費點，不是公開 API，CHANGELOG 有記。
- code-review Spec：修了 plan §2.3 `plans.job_hash` 那一句仍說「重新入庫以目錄為 Import Source」（與這一票改的 `models/plan.py` 矛盾）。**沒修、留著**：第二個請求若在第一個 commit **之後**才進來（進鎖前就讀到 `removed`），`removed → removed` 的 CAS 成立，它是一次合法的「再刪一次」而不是輸家——伺服器分不出使用者的分頁看到的是刪除前的畫面。要堵它得讓前端把看到的狀態送上來（`expected_state`），留給之後真的撞到時再開票。
- 沒做、同一類的第四條路：重複版本的「取代舊版」走 rematch 的同路徑分支（`fs.replace_link`），目標上若是使用者換進去的檔案會被蓋掉，沒有比 inode。不在票列的三條路裡，也沒有測試，所以不動；要修就在 `_carry_out` 的 `replace_link` 之前用同一個 `Placed.of(move.old).holds` 擋、拒絕 `target_taken`，並在 `test_duplicates.py` 補一條。
- 原本多改的：`models/plan.py`、`api/plans.py`、`api/media.py`、`services/rematch.py` 的 `locked` docstring 也說「重新入庫沒有 Job」，同一個過時事實，一併改掉。
