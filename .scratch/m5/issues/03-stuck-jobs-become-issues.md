# 03 — 卡住的 Job 開成 Issue

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5「2026-10-24 已定」那一條、§2.4、§3.1、§3.2（`reconciler` / 巡檢的排程）；brief §9.1、§19 2026-10-24「AI 不設預算、接管開關、側面板提前」第④條；M4 票 129 的做法與 Comments；`IssueType` 的 docstring（加型別要過 `SUBJECT_OF` 與 `ISSUE_ACTIONS` 兩道閘門）

## 為什麼

M4 票 129 只把卡住的 Job 放在下載頁「需要人」的篩選與 Job 頁上，沒有開 Issue。M6 的接管開關只看得到 Issue、審核與待綁定這三份清單，所以卡住的 Job 要先變成 Issue，AI 才碰得到。這件事本身不需要 AI，也讓人在「等你處理」與推播裡看得到它們。

## 做什麼

1. 新的 Issue 型別涵蓋三種卡住：重試用完的 `submit_failed`、永久失敗的 `import_failed`、`stalled`。一種型別一個，還是一種型別帶原因，照 `IssueType` 既有的取捨定，並寫進 plan §2.4。
2. 每一種給齊 `SUBJECT_OF` 與 `ISSUE_ACTIONS`：可用的動作沿用 Job 頁已有的那幾顆（retry、resubmit、放棄……），不另發明。
3. 開與關：誰開（巡檢或 Job 轉狀態的那一刻，二選一，理由寫進票）、冪等鍵、Job 被救回來之後 Issue 自動收掉（照 `close_settled` 的路）。
4. 算進「等你處理」的數字與推播（M4 的通知），通知文案走 i18n，zh-Hant 與 en 並列。
5. 下載頁「需要人」的篩選與 Job 頁的提示，改從 Issue 來或保持現狀但不重複計數，二選一並說明。

## 驗收

- [x] 三種卡住各自開出一筆 Issue，同一個 Job 不重複開（pytest）
- [x] Job 重試成功或被放棄後，Issue 收掉（pytest）
- [x] Issue 頁看得到、按得到動作；「等你處理」計數與推播都算進去（pytest＋vitest，UI 用 playwright 實跑）
- [x] `SUBJECT_OF`、`ISSUE_ACTIONS` 的閘門綠
- [x] 全部檢查、pytest、vitest 綠；plan §2.4、CHANGELOG、progress.md 已更新

## Comments

- **型別**（做什麼 1）：一種狀態一種，`submit_failed` / `import_failed` / `stalled`，與 Job 狀態同名。理由同管線那三種：
  每一種的按鈕與「還是現況」由 `ISSUE_ACTIONS`、`issues.STANDS_WHILE` 照型別寫死；一種型別帶原因的話兩張表都得改成看
  `detail_json`，閘門也守不到。`subject` 是 `job_hash`（同一個 Series 停兩筆是兩件，各自重試）。寫進 plan §2.4。
- **誰開**（做什麼 3）：**每日巡檢**（`sweep._stuck_jobs`，05:00），不在轉狀態那一刻。理由：進 `submit_failed` 的路有五條
  （送單、重試、重新送單、`retry_due`、啟動時的 `fail_interrupted`），掛在寫入點遲早漏一條，而 `jobs` / `importer` 也
  import 不了 `issues`（會繞回來）；停滯本來就要量「停了多久」；與「等你處理」看清單不掛寫入點同一個理由。代價是最慢晚一天
  才開，但下載頁「需要人」當下就看得到它們。「卡住」的定義：送單失敗是最後一筆 `submit_failed` 事件沒有排著的 `retry_at`
  （再問也一樣、次數用完），或排著卻過期滿 24 小時（Route 停用、紅著時 `retry_due` 留在原地不送，code-review 抓到）；
  入庫失敗一律算（沒有自動重試）；停滯要從最後一筆 `stalled` 事件起滿 `STUCK_AFTER`（24 小時）。
- **收**：Job 離開那個狀態時 poller 每一輪的 `close_settled`（重試成功、放棄、刪除）；送單失敗又排上自動重送的由下一輪巡檢
  `_settle` 收。三種加進 `STAYS_IGNORED`（不然每天巡檢都重開）；`close_settled` 也替被忽略的那一件記 `cleared_at`，兩輪
  巡檢之間走開又停住的是新的一件（code-review 抓到，先紅後綠）。
- **動作**（做什麼 2）：重試＝Job 頁那一顆（`jobs.retry_job`；又送不出去時那一件仍開著，`resubmit_failed`；磁碟不夠是新的
  `IssueRefusal.LOW_DISK_SPACE`）；放棄＝新的 `IssueAction.ABANDON`，就是 Job 頁的刪除範圍四個旗標全不勾（`_accept`，
  同兩顆「承認」），不刪東西；停滯只有放棄（Job 頁也沒有重試）。`_BROKEN_BY` 拿掉：`retry` 掛在兩種型別上時「一顆一份狀態」
  會互相蓋掉，改成 `_actions` 直接看 `STANDS_WHILE[row.type]`。
- **與第一批卡住**：巡檢先跑卡住的 Job，停在送單失敗的那一筆有了自己的 Issue 之後 `first_batch_stuck` 不再為它開（`_covered`
  多一個 `excluding`）。`test_sweep.py` 的 helper 改成「自動重送還排著」的那一種，第一批的語意測試照舊。進了 progress 偏差。
- **做什麼 5**：下載頁「需要人」的篩選與 Job 頁**維持現狀**。篩選是照狀態列 Job 的一個視角，不是「等你處理」的三份清單之一；
  「等你處理」只數 Issue 那一件（`waiting_now` 不看 Job），不重複計數。
- **實跑**：新演練情境 `stuck-jobs`（`docs/development.md`），playwright zh-TW 1280 / 390、en-US 1280：三件各自的標籤、
  一句話、停住於、原因、下一步與「下載」連結，390 沒有水平溢出；1280 上按入庫失敗的「重試」那一件收掉、停滯的「放棄這一筆」
  之後 Job 頁顯示「已刪除」。截圖在 `03-stuck-jobs-become-issues/`。
- **code-review 沒處理的**：
  - 停滯的「放棄」讓 Job 進 `removed`，torrent 照樣留在 qBittorrent 上跑（Spec，判斷題）：與兩顆「承認」同一個不刪東西的
    規矩，下一步那一句說了要一起移除走 Job 頁的刪除範圍。要不要讓放棄停滯時也移除 torrent，留給使用者。
  - `_retry` 經 `retry_job` 寫的 `retried` 事件 actor 是 `"user"`，不是按的那位管理員（Spec）：Job 頁的重試本來就是這樣寫，
    不在這張改。
  - 加一種型別要動七、八處（Standards，Shotgun Surgery）：`IssueType` 封閉集合加兩道閘門的既有取捨。
  - 前端 `NEXT_STUCK` 的鍵抄了後端 `_STUCK_JOBS`、`resolve_issue` 裡 `retry` 依型別分兩條路（Standards，Duplicated Code /
    Repeated Switches）：只有兩條，再多一種再改成表。
