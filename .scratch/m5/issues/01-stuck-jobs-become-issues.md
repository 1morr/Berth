# 01 — 卡住的 Job 開成 Issue

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

- **一種型別還是帶原因**：一種卡住一種型別（`submit_failed` / `import_failed` / `stalled`），同
  `feed_poll_failing` / `feed_backfill_failing` 的取捨：出路與按鈕不同，型別就是「哪一組按鈕」。寫進 plan §2.4。
- **誰開**（使用者選定）：`qbit_poller` 每一輪（`issues.flag_stuck_jobs`，在 `close_settled` 旁、同一個交易），不是巡檢也
  不是各個轉換點。理由：三個狀態有五個以上的生產者（送單、重試、自動重送、重新送單、`fail_interrupted`、importer、
  poller 的停住），`jobs` 與 `importer` import 不了 `issues`；巡檢一天一輪，`import_failed` 最晚要等 29 小時，M6 的事件
  觸發也慢一天；升級前就卡住的那幾筆第一輪補上、不需要資料 migration。冪等鍵 `(type, job_hash)`；因為每一輪都量，
  三種都 `STAYS_IGNORED`。
- **第 5 點選「保持現狀但不重複計數」**：下載頁「需要人」與 Job 頁數的是 Job，「等你處理」數的是 Issue，兩邊不相加；
  同一筆已有別的管線 Issue 說著（重新送單被拒的 `client_removed`）就不開第二件，巡檢的第一批卡住也不為有
  `submit_failed` 那一件的 Job 再開。
- 實跑：`fake_setup_server.py --scenario issues`，三件由 poller 第一輪開出；停滯與入庫失敗的列截圖在
  `.playwright-mcp/m5-01-stalled.png`、`m5-01-import-failed.png`，送單失敗那一列以英文 snapshot 核對（標籤
  `SEND FAILED`、按鈕 Send it again / Give up / Ignore）；按「放棄」Job 進已刪除，按「再試一次入庫」回入庫中。
- **code-review**（兩軸，起點 `e615860`）處理掉的：人按重試又暫時失敗、重新排上自動重送的那一筆，那一件還開著說「不會再
  自動重送」（Spec，先紅後綠：沒判成卡住的照 `_settle` 收）；`flag_stuck_jobs` 不更新 `detected_at` 推翻了 plan §2.4
  的字面，補進 plan 與 progress 偏差（Standards）；`issues.py` 模組 docstring 前後矛盾；plan §2.4 與 brief §9.1 的
  「十四種」；「放棄」與通知的 `abandoned` 同詞，CONTEXT.md 註明是兩件事；`fake_setup_server` 的 `STUCK_JOBS` 與
  `issues.STUCK_JOBS` 同名不同義（改 `STUCK_DEMO_JOBS`）、前端 `NEXT_STUCK` / `isStuck` 與第一批卡住的 `STUCK_STATES`
  撞詞（改 `STUCK_JOB_NEXT` / `isStuckJob`）；enums 上「重新送單是 Job 頁的重試」的註解不準（它走 `resubmit_job`，不檢查
  磁碟門檻）；`kind_of` 每輪重建（改模組層級 `_STUCK_KIND`）。
- **code-review 沒處理的**：
  - qBittorrent 停機時不開新的（`import_failed` 也一樣）：poll 失敗的那一輪走不到 `flag_stuck_jobs`。選 poller 時已向使用者
    說明的代價；健康頁本來就說得出 qBittorrent 掛了，回來的第一輪補上。
  - 自動重送被前提擋下的那一筆（Route 刪了、停用、種類不符、磁碟不夠）`retry_at` 一直排著，所以永遠不算「重試用完」、
    不開 `submit_failed`（Spec）。RSS 的第一批由巡檢的第一批卡住接住；其餘要有 repro 或使用者要求再開票（判定「排著但
    過期多久算卡住」要另外定門檻，qBittorrent 剛回來那一輪也是過期）。
  - 慢的 torrent 反覆停住又恢復，每次停住都是新的一件、可能一則新推播（`WAIT_WINDOW` 只擋 10 分鐘內恢復的）（Spec）：
    選每一輪偵測時說明過；要再收斂是 M6 或之後有 repro 時。
  - 升級那一刻已開著的第一批卡住會與新的 `submit_failed` 並存到下一輪巡檢（最多一天）（Spec）：只有升級時碰得到。
  - 「等你處理」計數沒有新的 vitest（Spec）：前端數的是通用的開著 Issue 數，這張沒改它；推播有 pytest。
  - `_retry_import` 是第四份 `JobRejectedError → IssueRejectedError` 的換手（Standards，Duplicated Code）；i18n 中英與
    CHANGELOG 寫死「五次」「十分鐘」（`SUBMIT_RETRIES` 長度加一、`STALL_AFTER`），沒有閘門，同 plan §11.5 記過的「24 小時」；
    加一種 Issue 型別要改的地方多（Shotgun Surgery，既有模式，plan 已列為不做）。
