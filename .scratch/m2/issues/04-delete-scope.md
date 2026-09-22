# 04 — 刪除範圍 + `delete_job` + 方法層級門禁

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** plan §6（jobs 群組、門禁開頭那三段）、§7（`/jobs/:hash` 那一條）、§3.1（Job 狀態轉換）、§11.3 的決定 4 與 7；brief §9.2、§11

## 做什麼

M2 的第一個原語。票 06 的 audit 撤銷、票 08 的 rematch、票 05 的 `library_link_missing`
「連 complete 一起刪」、票 12 的 Job 詳情頁動作區，全部走它。

**命令與端點**：`DELETE /jobs/{hash}?unlink=&remove_torrent=&delete_files=&purge=`，四個旗標
（brief §9.2）：移除 library 硬鏈接 / 從 qBittorrent 移除 torrent（不刪檔）/ 刪除 complete 檔案 /
清除帳本與 Job 紀錄。`delete_files` 要求先 `remove_torrent`，否則拒絕。Job 進 `removed`，
寫 event `deleted` 並說得出刪了哪幾樣。

**四個旗標預設全不勾**（2026-09-22 定，brief §9.2）。Sonarr 的對話框預設勾「同時刪除檔案」，
但這裡的刪除以 Job 為單位而不是作品，預設刪檔會誤刪還在做種的東西。

**空間估算同步 `stat`**：逐一 `stat` 每一個來源與目標（慢而準，畫面上說「正在算」），不用來源
大小去猜。只有來源與所有鏈接都刪掉時才是真的釋放，畫面要說清楚這件事。

**對話框是一個元件**，這一輪掛在 `/jobs` 的展開區與 Media 詳情的版本清單；票 12 的 `/jobs/:hash`
掛的是同一個元件（plan §7 說它住在 Job 詳情頁與版本清單，而詳情頁還沒有）。

**門禁要多一個維度**。`api/gate.py` 的 `ADMIN_PREFIXES` 只比路徑前綴，而 `/jobs` 整組不能是
admin——`user` 要送得了單、看得到自己的 job。`DELETE /jobs/{hash}` 是 M2 第一個「同一條路徑、
不同方法、不同門禁」的端點（票 10 的 `POST /jobs/{hash}/reimport` 是第二個），所以在這一票把
規則擴成認得方法。形狀仍然是**預設拒絕**：規則在門禁一處，不散到 router 的相依裡。

## 驗收

- [x] 四個旗標預設全不勾；`delete_files` 沒帶 `remove_torrent` 時是拒絕（有測試，不是靠 UI 擋）
- [x] 四個旗標的每一種組合各自只做它該做的事：整合測試至少涵蓋「只移除鏈接」「移除 torrent 不刪檔」
      「刪檔（含 torrent）」「全勾」四條
- [x] 空間估算逐一 `stat`；估算進行中畫面說得出「正在算」；只有來源與所有鏈接都刪時才報成真的釋放
- [x] 刪完 Job 是 `removed`，時間線有 `deleted` 且說得出刪了哪幾樣
- [x] `user` 登入時 `DELETE /jobs/{hash}` 回 403，而 `GET /jobs`、`POST /jobs`、`GET /jobs/{hash}/events`
      照常（整合測試對兩邊都斷言；把方法規則改回純前綴會讓它紅）
- [x] 前端以 `user` 登入時看不到刪除入口（前端隱藏不是安全機制，後端那條是上一項）
- [x] playwright 實跑一次刪除對話框（含估算中的畫面），附截圖或文字結果
- [x] lint、type、test 綠燈

## 做完之後的樣子

**後端**：`services/deletion.py`（新，命令與估算）、`adapters/qbittorrent` 的 `delete_torrent`、
`adapters/fs` 的 `remove` / `prune_empty_parents` / `root_of`（`PathFacts` 多帶 `size` 與 `links`）、
`api/gate.py` 的 `ADMIN_ROUTES`、`api/jobs.py` 的 `DELETE /jobs/{hash}` 與 `GET /jobs/{hash}/deletion`。
**前端**：`jobs/JobDelete.tsx` 一個元件掛兩處（`JobRow` 展開區、`FilesPanel` 版本清單，
`VersionOut` 因此多帶 `job_hash`）。

**實跑**（fake server `--scenario plan`，真的送單 → 規劃 → 入庫）：五個硬鏈接 + 六個 complete
檔案，對話框報「媒體庫 5 個鏈接 · 下載目錄 6 個檔案」；只勾移除鏈接時說「不會空出空間」，
三個都勾才說「會空出 126 KB」。按下去之後磁碟上兩棵樹都空了，時間線是
「移除 5 個鏈接 · 刪掉 6 個下載檔案 · 從 qBittorrent 移除」+「空出 126 KB」，狀態 `已刪除`。
以 `deckhand`（`user`）登入同一列，展開區照樣有時間線與 hash，刪除鍵 0 顆。
截圖：`.playwright-mcp/delete-dialog.png`、`delete-estimating.png`（估算中那一刻）。

**變異驗證**（四條都實跑過，確認不是空閘門）：

| 變異 | 變紅的測試 |
| --- | --- |
| 門禁方法規則改回純前綴（`/jobs` 整組 admin） | `test_an_ordinary_user_still_reads_and_submits` |
| 完全拿掉方法規則 | `test_an_ordinary_user_cannot_delete_a_job` + `test_an_ordinary_user_can_neither_delete_nor_estimate` |
| `_measure` 的路徑集合不正規化 | `test_the_same_file_under_two_spellings_is_still_one_name`（141 vs 54） |
| 版本清單那一行刪掉 / 拿掉 `isAdmin` 守衛 | 版本清單的兩條各紅一條 |

## Comments

`/code-review` 兩軸的發現，逐條處理：

**Standards（三條硬性違規全部修掉）**

1. `fs.link_count` 消費點歸零（全域 CLAUDE.md：「消費點歸零的介面，連同守它的測試一起刪」）
   —— 連同 `TestLinkCount` 刪掉，改成把 `size` 與 `links` 併進 `PathFacts`。
2. `services/deletion.py` 直接 `path.stat()` 繞過 adapter —— 改走 `fs.stat`，順帶讓「一次 `stat`
   拿四個值」成立（原本 size 與 nlink 來自同一次呼叫，但 IO 路徑有兩條）。
3. `JobDelete` 的 `onDeleted` 兩個呼叫端都沒傳、註解說給票 11（Speculative Generality）—— 刪掉。
   刪完之後畫面怎麼更新改由元件自己失效兩個 query key 解決（見 Spec 第 3 條）。
4. 判斷題採納：`_measure` 的 list-of-1 計數器改成路徑集合（同時修掉一個真缺陷，見下）；
   `_remove_all` 不再重算 `is_within`（新的 `fs.root_of` 與守衛共用一份）；
   `delete_job_endpoint` 改回 `delete_job`（import 模組而不是函式）；API 兩個 model 的散文
   不再與 service 的 dataclass 逐字重複。

**未處理（判斷題，留在這裡）**

- `DeleteScope` 被編碼三次（service dataclass、端點四個 bool query 參數、前端 camelCase
  型別 + 手寫 `String()`）。讓端點吃一個 pydantic query model 可以少一份，但前端那一份
  是 camelCase ↔ snake_case 的邊界，仍然要手寫一次。等票 12 的 `/jobs/:hash` 也掛上去之後
  再看值不值得。
- `DESIGN.md` 的「就地確認」段沒記 `ConfirmPanel` 多了「勾選 + 即時估算」這第三種內容形狀。
  留給里程碑收尾的 `/impeccable document`。
- 帳本被改成一條 `Path` 收不掉的寫法（含 `..`）時，估算上的**檔案數**會多算一個
  （`_scope_paths` 的去重比的是 `str(Path(...))`，而 `_measure` 的去重比的是正規化後的字串）。
  **真正要緊的那個數字沒有錯**：`reclaimable` 與 `freed` 走的是 `_measure` 那一份，有測試守著。
  兩層都正規化的話那條測試就沒有東西可分辨了（去重在上游就發生），而 Berth 自己寫下的
  `source_abs_path` 永遠是 `str(fs.under(...))`，走不到這個形狀——所以留一個數字的誤差，
  不為一個到不了的情形多一層機制。

**Spec（兩條真缺陷，都修掉）**

1. 版本清單那個掛點**沒有閘門**：整行刪掉 485 條前端測試照樣全綠。補了兩條
   （admin 看得到兩顆、`user` 一顆都沒有），並實跑兩個方向的變異確認它們會紅。
2. 版本清單上刪完**畫面不會更新**：`JobDelete` 只失效 `['jobs']`，而 Media 詳情讀的是
   `['media', id]`，剛刪掉的那個版本還留在畫面上。改成兩個 key 都失效。
3. 審查期間那條「兩種寫法同一個檔案」的測試是紅的 —— 那是我在改的中途，最終是綠的，
   而且它守著一個真缺陷（見變異表第 3 列）。
