# 10 — `reimport` + `berth rebuild-ledger`

**Status:** done

**Blocked by:** 04（`POST /jobs/{hash}/reimport` 的方法層級門禁）、05（`rebuild-ledger` 配不到的要建 `unmanaged_library_file` Issue）、09（三種 Issue 的偵測與動作表）

**讀:** plan §6（jobs 群組）、§4.2（核心型別）、§5（命名引擎，反解目標路徑）、§11.3 的決定 9；brief §9.3（重新入庫）、§4.1（三層路徑）

## 做什麼

M2 驗收第一條：**刪掉 library 之後一鍵重建**。兩條路徑，一條走 API 一條走 CLI。

**`POST /jobs/{hash}/reimport`**：以那一筆 Job 的 complete 目錄重跑 planning → review/importing。
**目錄版**：Import Source 可以是「complete 內任一資料夾」，**不要求 torrent 仍存在**（brief §9.3）。
帳本以來源相對路徑冪等，所以「刪了 library、保留 complete、再重新入庫」是一鍵動作。

**`berth rebuild-ledger`**：從 library 的 inode 反查 complete。**配得上的重建完整一列**——季集與
Tags 從目標路徑反解（命名是純函式，反解用同一份規則）。**配不到的一律建
`unmanaged_library_file` Issue，不猜**（決定 9）。

這兩件是同一張票，因為它們是同一個問題的兩個入口：帳本沒了要怎麼從磁碟上的事實把它長回來。

**票 09 移過來的三顆「認領」**（2026-09-23 使用者拍板）：它們用的正是上面兩個原語，在票 09 先做一份
會變成兩條入庫路徑。票 09 已經偵測得出這三種，現在只按得了「忽略」：

- `orphan_complete`「重新入庫（adopt）」：以那個目錄為 Import Source 走目錄版 `reimport`。
- `unknown_torrent`「認領（建 Job 並解析）」：替 qBittorrent 上那一筆建 Job，交給 poller 與規劃器。
- `unmanaged_library_file`「認領進帳本」：單一檔案的 `rebuild-ledger`——配得上的長回一列，配不到的
  照舊只列出。**這一顆不刪任何東西**（`ACTION_DELETES`，`tests/unit/test_issue_types.py` 守著）。

加進 `ISSUE_ACTIONS` 時 `test_issue_types.py::test_what_each_type_offers_this_round` 會紅（刻意會過期），
`web/src/issues/IssueRow.tsx` 的 `CONFIRM` 總表也會在 `tsc` 紅。

## 驗收

- [x] 刪掉整個 library 目錄之後：`reimport` 目錄版一鍵重建，檔案回到 library、帳本重新長出來、
      Jellyfin 掃得到（整合測試走完整條，這是 M2 驗收第一條）
- [x] torrent 已經不在 qBittorrent 時 `reimport` 照樣走得完（brief §9.3）
- [x] 重複 `reimport` 同一個目錄不會產生第二份帳本列（以來源相對路徑冪等）
- [x] `berth rebuild-ledger` 配得上的重建完整一列：季、集、Tags 都從目標路徑反解出來，且與命名
      函式的輸出一致（測試以同一份規則往返斷言）
- [x] 配不到的**一筆都不猜**：全部變成 `unmanaged_library_file` Issue（測試造一個反解不出來的
      檔案，斷言沒有帳本列被寫出來）
- [x] CLI 子命令在 README 有一節（專案 CLAUDE.md：README 是指令的單一來源）
- [x] `user` 登入時 `POST /jobs/{hash}/reimport` 是 403，而 `GET /jobs` 照常
- [x] 三顆認領按下去真的修好：`orphan_complete` 的目錄入庫、`unknown_torrent` 有了 Job、
      `unmanaged_library_file` 長回帳本一列（各一個整合測試，下一輪對帳不再開同一件）
- [x] lint、type、test 綠燈

## Comments

- 2026-09-23 開工時使用者拍板：**認領類兩顆（重新入庫、認領 torrent）由管理員在列上選作品**
  （就地展開的 TMDB 搜尋，`WorkPicker`）。沒有作品的 Job 規劃出來整份停在 review（`no_media`），
  而 Review Queue 指定不了作品、核准會被 `media_missing` 擋——那是死路。
- **帳本以來源冪等**的鍵是「Job + `source_rel_path`」：目標路徑先認、再認來源。TMDB 改了集名之後
  重新入庫，那一列換到新路徑、舊路徑上與來源同 inode 的鏈接收掉（`test_reimport.py`
  `TestRepeating`，拿掉那一段會紅，實跑確認過）。
- 孤兒目錄沒有 torrent，所以 Job 主鍵是路徑的 SHA-1（`claims.adopted_hash`），不另開一條沒有 Job 的
  入庫路。
- `resolver` 的排程抽成 `services/resolve_schedule.py`：`issues → claims → resolver → issues` 是環。
- 演練 `--scenario issues` 多造三份認領材料（替身 TMDB 搜得到 `spy`），playwright 實跑三顆認領、
  `/jobs` 的重新入庫、`deckhand` 的 403 與 390px。

### `/code-review` 的發現

兩軸各跑一次（第一次撞額度上限中斷，恢復後續跑）。**修掉的七條**：

1. **CONTEXT.md 的 Claim 詞條插在 Unmanaged 與它的 `_Avoid_` 中間**（Standards，硬）：拆回來。
2. **函式名用了詞表迴避的 adopt**（Standards，硬）：`adopt_folder` / `adopted_hash` 改成
   `reimport_folder` / `reimport_hash`，`adopt` 只剩 `IssueAction.ADOPT` 這個按鈕值。
3. **`NEEDS_MEDIA` 沒有閘門**（Standards）：`test_issue_types.py::TestWhichClaimsNeedAWork`，檔內雙向變異。
4. **走訪目錄的那一支逐字寫了兩份**（Standards）：收成 `fs.files_under`，對帳與認領共用。
5. **`resolve_issue` 先合併兩顆、`_claim` 裡再拆**（Standards）：各自一個 `elif`。
6. **目錄版重複重新入庫沒有斷言帳本列**（Spec）：補 `test_reimporting_the_adopted_folder_again_grows_no_second_ledger`。
7. **`source_index` 量 inode 時檔案消失會讓整次 `rebuild-ledger` 中斷**（Spec）：跳過那一個，
   測試先紅再綠。

**看過但沒改的**：

- **反解對「只有一個沒有形狀的 token」是兩可的**（Spec）：`[X]` 可能是發佈組也可能是版本名，兩種重算
  出來一字不差。讀法固定放進發佈組；只有版本名、沒有發佈組的那一種（`[Director's Cut]` 單獨出現、或沒有
  發佈組的「保留兩者」序號）長回來的 Tags 會把它記成發佈組，路徑仍然對，但重複判斷比的是 Tags。實際上
  Berth 寫得出這種檔名的情況很少（發佈組幾乎都在），沒有 repro；要解得回頭看來源檔名的解析結果，另開。
- **`claim_file` 的 Job 由來源決定、作品由資料夾名決定，不互相核對**（Spec）：來源被硬鏈到另一部作品的
  資料夾時會長出「Job 屬於 A、作品是 B」的一列。那一列說的仍是事實（鏈接確實是 A 的來源、確實住在 B 的
  資料夾），沒有 repro 說它會讓哪個判斷出錯。
- **`rebuild-ledger`（CLI）與服務是兩個程序，`job_lock` 管不到**（Spec）：同時寫同一條目標路徑會撞
  unique 約束而沒有明確理由。單人自架、手動跑的指令，沒有 repro。
- **importer 換落點時收掉舊鏈接是所有入庫路徑都會走到的**（Spec，範圍）：刻意的——重新規劃、重新入庫、
  rematch 之後同一個來源都不該在媒體庫裡留兩條；只收與來源同 inode 的那一條。plan §3.1、CHANGELOG 已寫。
- 判斷題（Standards）：`SYSTEM = "system"` 散在三個模組、`_user_id` 把 `actor_of` 的字串解析回 int、
  前端 `CLAIM_MISSES` 手抄後端 `ClaimMiss`（它在 `detail` 這個沒型別的 dict 裡，OpenAPI 產不出來）、
  `IssueResolveIn.media` 用空字串代表沒選、`_media_of` 與 `ensure_media` 同一個形狀。都只有兩三處。
- 演示伺服器從 `tests.integration.test_media` 借替身 TMDB（Standards，判斷題）：留著，import 那一行寫了理由。
