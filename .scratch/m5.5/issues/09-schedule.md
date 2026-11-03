# 09 — 時間表最小版

**Status:** done

**Blocked by:** 07, 08

**讀:** spec〈範圍〉「新番區塊」「時間表」；brief §20.3（含 08 的結論）、§13；plan §7；`docs/research/` 裡 08 留下的數字；`.scratch/m5.5/navigation-shape.md`

## 為什麼

找得到當季新番，並一鍵走到訂閱。時刻與評分（14）、「晚 N 天」（12）是之後的層，這張先端到端跑通。

## 做什麼

1. **先 `/impeccable shape`**：版面照 AutoBangumi Calendar（brief §20.3）。輸出 `.scratch/m5.5/schedule-shape.md`。
2. **資料**：TMDB 當主幹（08 量過，brief §20.3、`docs/research/schedule-sources-2026-11-04.md`）列本週當季新番。
   - `discover/tv`：`with_genres=16`、`with_original_language=ja|zh`，`air_date.gte` 為週一前一天、`air_date.lte` 為週日後一天（深夜檔兩邊差一天），全部頁數。
   - discover 的每筆沒有集與播出日：每部再讀 `tv/{id}` 的 `last_episode_to_air` / `next_episode_to_air`，照 TMDB 的 `air_date` 放進那一天的欄。
   - 約一半是長壽 / 兒童節目與國產動畫（Bangumi 放送表沒有的）；要不要篩看版面再定，篩的話記在票的 Comments。
   - 有人打開才抓，結果存程序內 `TtlCache`（6–24 小時），不為卡片寫 `media` 列。
   - 卡片的狀態每次照資料庫算，不進快取，所以訂閱完下一次打開就變。
   - 讀取命令 `Effect.READ`，每個人都能讀；端點進路由表。
3. **頁面**（`/schedule`）：
   - 週一到週日分欄、今天標出；手機是單日清單。
   - 預設列全部（AutoBangumi 只列已訂閱，這裡要拿來找新番），可切「只看已訂閱」。
   - 卡片：海報、顯示用標題（Display Round）、第幾集、狀態（未訂閱 / 已訂閱 / 已入庫）。點進 `/media/:id` 走現有的訂閱流程。
   - 一般使用者看得到狀態類別，看不到字幕組與 Feed（比照 `services/why_not.py` 的範圍）。
4. **導覽**：「新番」對所有人顯示，分頁為時間表 `/schedule`（預設，每個人）、訂閱 `/rss`（admin）。
5. Fake 後端補時間表的資料，UI 驗證不需要金鑰；`docs/development.md` 的情境表補一列（如有新情境）。
6. 文件：brief §13、plan §7 路由表、`CONTEXT.md`（時間表的名詞，若有新詞）。

## 驗收

- [x] 時間表列出本週當季新番；未訂閱的卡片點進作品頁訂閱成功，下一次打開變「已訂閱」（e2e，桌機與 390px）
- [x] 一般使用者看得到時間表與狀態，看不到字幕組與 Feed；看不到「訂閱」分頁（測試＋e2e）
- [x] 同一個快取期間內再打開不再打外部來源（fake client 計數）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-11-04 shape（`.scratch/m5.5/schedule-shape.md`）使用者定兩件：**全部列、不篩**（長壽 / 兒童節目與國產動畫都留著，等用過再定），卡片是**小海報橫列**（一天十幾到三十部，2:3 直卡會把一週拉到七、八個螢幕高）。
- 放哪一天、第幾集：每部只看 TMDB 的上一集與下一集，落在這一週的才列。一週播兩集、兩集都播過的，較早那一集不出現（票上定的做法，接受）。
- 詳情讀 `zh-TW`（顯示用標題、海報、上一集與下一集一次拿到），discover 讀 `en-US`（清單本身與英文標題），一週約 9 頁 + 160 部；並行 8 部，速率走全域的桶。快取 6 小時（spec 說 6–24，取下限：季初 TMDB 一天裡會補集）。
- 縮圖用 `w154`（`THUMB_SIZE`）；`poster_url` 從 `discover` 抽成公開的、多收一個尺寸。
- Fake 情境 `schedule`（以 `rss` 為底、時鐘 2026-09-25）：《与你相恋》整季往後挪一週，第 12 集落在這一週；e2e 用 acg.rip「只追之後的」訂閱，一筆都不送，不會被入庫搶先變成「已入庫」。
- code-review 已處理：「已訂閱」原本只看 `rss_series.media_id`，與 `CONTEXT.md`〈訂閱〉不一致（刪掉 Feed 後仍說已訂閱、預先綁定的關鍵字 Feed 說未訂閱），改成 `rss.subscribed_media`（與 `list_subscriptions` 同一個來源）並補兩條測試；拿掉憑證後快取命中仍出資料，改成每次先看憑證；兩個同名不同值的 `POSTER_SIZE` 改名；`docs/guide/setup-wizard.md` 的頁面表補 Schedule。
- code-review 未處理：
  - 快取未命中時同時打開的人各抓一輪（每輪約 170 次請求）。沒做 in-flight 合併：同一個程序跨 event loop 的鎖要另外處理，一個家同時第一次打開的機會小，速率有全域桶擋著。
  - 「只看已訂閱」也留著沒訂閱但已入庫的卡（狀態只有一格，入庫蓋過訂閱）。接受：那一集已經在庫裡，也是「我在追」的訊號。
  - `ScheduleSlot` 與 `ScheduleCard` 九欄重複（Data Clumps）：API 的 `from_attributes` 要平的欄位，先不包。
  - `image_base`、`poster_url` 住在 `services/discover`（Feature Envy），時間表與作品頁都從那裡拿；搬到 `services/tmdb` 是另一張整理票的事。
  - `parse_page` 帶 `kind`、`discover_tv` 收 `genre` 參數：條件是 services 的決定，adapter 不寫死，留著。
  - `read_schedule` 標 `Effect.READ`，但 `image_base` 第一次可能寫設定，沿用 discover 的既有標法。
  - 票 07 留下的「區塊設定散在 `sections.ts`、`SectionLink`、`SectionTabs`、`AppShell` 四處」這一票加了 `/schedule` 仍是四處改；票 12 加追更分頁時形狀才定，屆時收成一個區塊物件。
