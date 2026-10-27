# 03 — 補完命令標記：管線、媒體庫與審核這一批模組

**Status:** done

**Blocked by:** 02

**讀:** plan §11.6〈分段〉第 1 段；brief §14；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R1；票 02 定下的旗標與「要不要人」的規則；`tests/unit/test_command_marks.py` 的 `BEFORE_M3` 豁免表

## 為什麼

`services` 有 219 支公開的 `async def`，其中 139 支沒有標記，全在 `BEFORE_M3` 豁免表的模組裡。登錄表只收有標記的命令。豁免表分兩批清，這是 第一批；另一批是票 03b。

## 做什麼

1. 這一批模組：claims、complete、deletion、downloads、duplicates、events、hints、importer、inventory、issues（`resolve_issue` 除外，見票 04）、jobs、media、plan、plan_review、plan_view、reconcile、reimport、rematch、resolve_schedule、resolver、steps、tracking。
2. 每支公開的 `async def` 都標上 Effect、inverse 與旗標。背景迴圈的入口標 `INTERNAL`。標的依據寫在 docstring，或留下一行說明為什麼。
3. 標的時候發現不該是公開命令的（只有內部用），改成私有，不要硬標。
4. 從豁免表移掉這一批模組。豁免表在票 03b 清完之後整張刪掉。
5. 有疑問的標法（可逆性看參數、要不要人有爭議的）列在 Comments，不自己發明新規則。

## 驗收

- [x] 這一批模組都不在豁免表，`test_command_marks` 守住
- [x] 每支命令的 inverse 指到存在、而且有標記的命令（閘門已守）
- [x] 豁免表只剩票 03b 那一批
- [x] 全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27（票 02 留）：閘門現在也認 `@asynccontextmanager` 包過的公開函式。這一批模組裡的 `jobs.job_locks`、`rematch.locked` 會被掃到：只有內部用的改成私有；跨模組要用的鎖或入口標 `INTERNAL`。
- 2026-10-27（票 03 做完）：標法的依據與有疑問的地方。
  - **`INTERNAL` 怎麼判**：只被管線、`main.py` 或別的 service 命令叫的標 `INTERNAL`（背景迴圈入口、別的命令那一段）；被 API 叫的不標，是工具的候選。讀的底層（`complete.route_folders`、`plan.proposal`、`tracking.is_tracked` 這一類，多半收 ORM 物件）也照這條標 `READ` + `INTERNAL`。`Flag.INTERNAL` 的說明只寫了「與別的命令同一個交易的一段」，沒明說讀的底層算不算；票 06 做登錄表時若要它們當工具，再回來拿掉。
  - **改成私有**：`claims.ensure_media`、`claims.settle`、`plan.plan_id_of`、`jobs.check_disk`（正式程式碼只有自己的模組叫；`plan_id_of` 原本被兩個整合測試拿來讀計劃 id，改成讀 `jobs.read_job` 的 `plan_id`）。`downloads.poll_downloads`、`reconcile.reconcile_once` 也只被自己模組裡的迴圈類別叫，但它們是一輪的入口、測試直接驅動，保留公開、標 `INTERNAL`。其餘都有跨模組的呼叫端。兩把鎖 `jobs.job_locks`、`rematch.locked` 跨模組要用，標 `READ` + `INTERNAL`（鎖本身不改東西）。
  - **`issues.resolve_issue` 暫標 `IRREVERSIBLE` + `downloads`**：票說它歸票 04，但不標的話 `issues` 離不開豁免表、驗收第 1、3 條做不到。照最嚴的標（有幾顆刪東西、「重新送單」送 torrent），票 04 拆開時換掉。
  - **`issues.ignore_issue` 標 `IRREVERSIBLE`**：brief §14 說忽略要人，但現有旗標沒有一個說「藏起問題」；沒有收回忽略的命令，所以照不可逆標，`needs_person` 因此成立。要不要另外一個旗標，留給票 04（它也要處理「忽略」類）。
  - **`media.read_media` 標 `READ`、`media.refresh_media` 標 `REVERSIBLE`**：兩支都會重抓 TMDB 快照、跟著改 `folder_name`。`read_media` 是詳情頁的讀，過期順手重抓當成快取；`refresh_media` 按下去就是要換標題，算改（code-review 兩軸都指出 `READ` 與「什麼都不改」字面衝突）。
  - **`jobs.add_download` 不帶 `CONNECTS_OUT`**：它照傳進來的下載連結去要 torrent。照票 02 對 `downloading.add_manual_download` 的判斷（連結來自搜尋結果、不帶 key 連新位址）一樣不帶；登錄表若讓模型直接給連結，要回來重看。
  - **inverse 一律 `None`**：`rematch.rematch_file`、`plan_review.edit_items` 看起來能「同一個命令換參數回去」，但取代舊版被換掉的那一條、`following` 連帶換掉的列不會跟著回來，所以不寫指向自己。
  - `importer.notify_jellyfin`、`rematch.announce` 標 `REVERSIBLE` + `INTERNAL`：叫 Jellyfin 照磁碟現況重讀，不是 Discord 那種對外發訊息，不帶 `SENDS_OUT`。
  - **旗標要不要從被叫的命令往上傳，沒有規則**：`resolver.sweep_resolutions` 經 `_announce` 叫 `notify.queue_ready`（`IRREVERSIBLE` + `sends_out`），照 `sweep.sweep_once` 的先例標 `IRREVERSIBLE` + `internal` + `sends_out`。但同模組既有的 `resolver.resolve_early`（Issue 的「重新反查」）也走 `_announce`，標的是 `REVERSIBLE`、沒有 `sends_out`；`rss.poll_due` 叫 `download_round` 也沒帶 `sends_out`。`resolve_early` 照傳的話會變成要人，與 brief §14「重新反查 AI 自己做」衝突，所以沒動。票 06 做登錄表時要定：「排一則通知」算不算命令自己的 `sends_out`。
- 2026-10-27（票 04 合併時補）：`issues.resolve_issue` 的暫標已隨票 04 拿掉——它拆成 17 支以按鈕為名的命令，各自標記（見票 04 Comments）。`record_issue`、`list_issues`、`ignore_issue`、`close_settled` 的標法兩張票一致，合併時保留這張的註解；「忽略」不另立旗標，照不可逆標。
