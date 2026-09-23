# `/jobs/:hash` Job 詳情頁（M2 票 12，`/impeccable shape`）

2026-09-24。視覺世界沿用 DESIGN.md 的「泊位調度板」；模式 **Operate**。前例是
`.scratch/m1/jobs-shape.md`（下載列表的一列）與 `.scratch/m2/plan-edit-shape.md`（票 07 的 Plan 表格），
這一份只寫它們沒回答的。

## 工作與使用者

**誰來**：兩種人。admin 從 `/jobs` 的一列、`/review` 的一列或 `/issues` 貼過來的網址進來，要**對這一筆做一件
不可回復的事**（刪除範圍、重新入庫）或弄懂它為什麼長這樣；`user` 進來看自己送的那一筆走到哪了。常在手機上。

**成功的樣子**：一進來就知道「這是哪一筆」（發佈名、作品、狀態），往下看得到檔案會落在哪、這份決定怎麼變成
現在這樣、事情怎麼走到這裡；按刪除時，確認區展開的那一頁**從頭到尾只有這一筆**。

**這裡獨有的真話**：一筆 Job 只有**一份現行 Plan**（`plans.job_hash` unique，重新規劃整份換掉），所以
「Plan 歷史」不是一疊舊表格，而是**這份決定被誰、在何時、怎麼改過**——那些事實只在時間線上。

## 使用者拍板（2026-09-24，三題全照建議）

1. **Plan 歷史＝事件推導的修訂紀錄**，不改後端。時間線上與 Plan 有關的九種事件（`preplan`、`plan_generated`、
   `review_required`、`review_decided`、`rematched`、`audit_confirmed`、`audit_undone`、`duplicate_skipped`、
   `duplicate_decided`）收成一段。**畫法是同一個 `JobTimeline` 元件**，只是餵過濾後的事件——rematch 的
   from → to 在那裡已經畫得出來，不寫第二份 renderer。代價已接受：這幾筆在完整時間線上也看得到。
2. **逐檔表格用唯讀 `JobPlan`，不與 `PlanEditor` 共用**。編輯要有 Review Queue 的核准 / 拒絕流程包著，
   搬過來等於多一個審核入口；Plan 停在 `pending_review` 時 admin 看到一條「到審核佇列處理」的連結。
   `JobPlan` 從 `/jobs` 的展開區**搬走**，之後只有這一頁 import 它。
3. **`/jobs` 展開區的動作全部搬到詳情頁**：重試、重新解析、重新入庫、刪除。一筆 Job 的動作只有一個家。
   展開區只剩狀態那一句、時間線摘要、hash、「詳情」連結。

## 頁面的形狀（由上到下，窄版同順序疊成單欄）

1. **回路**：`GHOST_LINK`「← 下載列表」。
2. **身分帶**（`border-b-2 border-rule-strong` 收尾）：
   - 狀態色塊（`JOB_SIGNAL`，唯一的信號色）＋ audit 色塊（`AuditChip`）。
   - `h1`＝發佈名（`.value`，`wrap-anywhere`，不截斷）——它是使用者認得出這一筆的東西。
   - 實測值一行（中點分隔、每格自己說出是什麼，與 `/jobs` 的列同一個 `JobFacts`）：作品（連 `/media/:id`，這一頁沒有
     `<summary>`，連結可以在這裡）· Route · trigger · 大小 · 進度 · 加入時間 · hash 前 12 字。
   - 底下一個 `dl`（`DetailLine`）：送單的人（RSS 與重新入庫沒有人在場）、服務原文、整串 hash。
   - 失敗時服務回的原文（`error`，`blocked-ink` 小字、原樣）。
   - `user` 停在 review：「等管理員審核」；admin 停在 review：「到審核佇列處理」連結。
   - hash：`CopyLine`（整串，拿去 qBittorrent 比對的那一個）。
3. **動作列**：照後端旗標給（`retryable`、`replannable`、`reimportable`＋admin），刪除（admin）排最後。
   **刪除的確認區就地展開在身分帶正下方**——這就是另建一頁的理由：展開時畫面上方就是這一筆的名字，
   不會有另一列擠進來。按鈕是 Ghost（`justify-items-start`），不是主要動作。`JobDelete` 原封不動 import。
4. **檔案與決策**（`h2` 模板字壓重橫線 + 計數）：`JobPlan`。還沒有 Plan 時一句「下載完成前還沒有計劃」。
5. **Plan 歷史**（`h2`）：`JobTimeline` 餵九種 Plan 事件，最舊在前。沒有任何一筆時一句「這份計劃還沒被改過」
   之類的空狀態。沒有 Plan **而且**時間線上沒有任何一筆 Plan 事件時不畫這一段（實作時改的：被拒絕之後、下一份還沒
   算出來的那一刻 `plan_id` 可能是空的，但歷史是真的）。
6. **時間線**（`h2`）：完整的 `JobTimeline`。

**寬版**（`lg` 以上）：1–3 整寬；4–5 與 6 分成 `7fr / 5fr` 兩欄（左：接下來會發生什麼＋決定怎麼改過；右：發生過什麼），
欄距 `gap-8`、每一段自己的重橫線標題當分隔（實作時改的：`gap-px` 的縫在兩段長度差很多時會留下一條懸空的線）。頁寬 `max-w-[80rem]`（決策與清單那一種）。**窄版** 390px：單欄，順序同上，
沒有任何一格橫向捲動。

## `/jobs` 展開區瘦身之後

- 作品連結、`waitingForAdmin` 照舊。
- **時間線摘要**：同一個 `JobTimeline`，只畫最近三段（`linked` 收段規則照舊），上面一句「較早的 N 筆在詳情頁」。
- hash `CopyLine`。
- 「Job 詳情」`GHOST_LINK` → `/jobs/$hash`。
- **沒有** `JobPlan`、沒有動作按鈕、沒有 `JobDelete`（票 04 在這裡掛的那一處拿掉；Media 詳情版本清單那一處不動）。

## 深連結

- `/jobs` 的一列：展開區的「Job 詳情」。
- `/review` 的 `plan` / `audit` / `unmatched` / `duplicate` 四類：展開區「所屬下載」那一格原本連 `/jobs`，改連
  `/jobs/$hash`（列上都帶 `job_hash`；audit 列沒有 Job 時整格不畫，照舊）。
- `/issues`：有 `job_hash` 的那一格由純字改成連結。`unknown_torrent` 除外：那一格放的是 torrent 自己的 hash，定義上沒有 Job，
  連過去一定是空狀態（實跑抓到），照舊只印字。
- 貼網址：`/jobs/<hash>` 直接進得來（路由守衛與 `/jobs` 相同：登入即可）。

## 狀態

| 狀態 | 畫面 |
| --- | --- |
| 讀取中 | 身分帶位置兩條不動的 `deck` 色條（同 `/jobs` 的 `Loading`） |
| 不存在的 hash（404） | 一塊 `well` 面板：「找不到這筆下載」＋「可能打錯了，或它已被刪除並清除紀錄」＋回下載列表的連結 |
| 後端問不到 | 一句 `jobs.off` 同類的話，不當成 404 |
| 刪除且勾了清除紀錄 | 查詢重問得到 404 → 同一個空狀態（它說得出「已被刪除並清除紀錄」這個可能） |
| 刪除沒勾清除 | 留在頁上，狀態變「已刪除」，`JobDelete` 自己的結果句 |
| SSE 提示 | `useJobStream` 讓 `['jobs']` 失效；這一頁的 key 都掛在 `['jobs', hash, …]` 底下，自己會更新 |
| `user` | 看得到一切唯讀內容與重試 / 重新解析；重新入庫、刪除不畫（後端門禁照舊 403） |

## 範圍與約束

- 不改後端（`GET /jobs/{hash}` 已經有，404 就是空狀態的訊號）。
- 不新增元件庫：`JobPlan`、`JobTimeline`、`JobDelete`、`CopyLine`、`AuditChip`、`GHOST_LINK` 全部既有。
  `JobRow` 裡的 `Action` 與 `Facts` 搬到詳情頁需要的地方，不留兩份。
- 文案全走 i18n，zh-Hant 與 en 並列。`<title>` 與 `h1` 照現有頁面的慣例。
- 反目標：dialog、第二份 Plan 表格、把 Plan 歷史做成舊表格的疊放、在 `<summary>` 裡放連結。
