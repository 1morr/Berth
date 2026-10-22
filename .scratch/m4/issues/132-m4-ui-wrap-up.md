# 132 — M4 UI 收尾

**Status:** done

**Blocked by:** 125、127、131

**讀:** plan §11.5〈修補段結案時票 Comments 的遺留〉的「M4 UI 收尾一張票」（每條都附了出處票）；CLAUDE.md〈UI〉；DESIGN.md、PRODUCT.md

## 為什麼

CLAUDE.md 要求每個里程碑的 UI 收尾前跑 `critique`、`audit`、`polish`。修補段結案時，還有幾條使用者看得到的遺留被指名留到這一輪。

## 做什麼

1. plan §11.5 列的七條逐條處理，每條先照出處票的描述重現（截圖或測試），再修；重現不了的寫進 Comments 不修：
   - 390 寬精靈 sticky 主鍵遮住下方欄位（M4 票 06）
   - 搜尋區塊 critique 未處理的五條（M4 票 84b）
   - 英文 `Settings → Library paths` 三處（M2 票 03）
   - 作品頁季表不隨背景入庫更新（M4 票 12、M3 票 06）
   - 票 31 留給「M4 收尾 polish」的五項
   - `docs/development.md` 的 `mixed` 情境 qBittorrent 帳密說法（M4 票 103）
   - `.impeccable/design.json` 落後 DESIGN.md（最後跑 `/impeccable document`）
2. 通知設定頁、週報頁跑 `/impeccable critique`、`audit`、`polish`，P0 / P1 修掉，P2 以下寫進 Comments。

## 驗收

- [x] 七條每條有重現紀錄與處理結果（修了附測試或截圖，不修附理由）
- [x] 通知設定頁、週報頁 critique 與 audit 的 P0 / P1 為零
- [x] `.impeccable/design.json` 與 DESIGN.md 同步
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments

### 2026-10-22 實作

截圖在 `132-m4-ui-wrap-up/`。替身都用自己的 port（8631–8637），沒碰 docker 或 `berth-local`。

**七條遺留（做什麼 1）**

| # | 重現 | 處理 |
| --- | --- | --- |
| 1 390 寬 sticky 主鍵遮欄位（票 06） | **重現不了**。`bundled` 頁 1、390×844：逐一 focus `main` 裡每個控制項，被固定在底部那一條蓋住的 0 個（`index.css` 的 `scroll-padding-bottom: 6rem`，票 06h 起）；捲到「Jellyfin 帳號」欄在視窗底時它在主鍵上方（604–648 vs 767–844，`wizard-390-viewport.png`）。看得到「遮住」的是**整頁截圖**：playwright 的 fullPage 把 sticky 那一條畫在原視窗底的位置、蓋在欄位上，原位置留白（`wizard-390-fullpage.png`）——票 119 量到的同一個假象 | 不修 |
| 2 搜尋區塊五條（票 84b） | 交子代理逐條實跑（`import` 情境，390 / 1280）：①停用的原因在 chip 與清單底下，390 寬距搜尋鍵 363px；②打了關鍵字時 chip 照樣按得、按了不影響查詢；③`/search/queries` 慢時缺集搜尋中的預覽與纜繩是作品名那一份（延遲 3 秒重現）；④查詢數沒有 `aria-live`；⑤「追蹤站」拆行**重現不了**（390 寬斷在「一分鐘。」），「會問」重複仍在 | ①原因搬到搜尋鍵那一排正下方（`RefusalLine`），代價句不能搜時不畫；②`QueryChoices` 包 `fieldset disabled`，最上面一句「打了關鍵字時只問那一個；清掉它，名字與季才用得上。」（`search.choose.typed`），`ToggleChips` 停用時字退 `ink-dim`；③已送出、預覽還是 placeholder 時清單與纜繩不畫舊的；④標籤加 `aria-live="polite"`；⑤範圍句改「問的是…缺的那幾集：」。vitest 五條（含改過的舊斷言），實跑 `search-refusal-390.png`、`search-typed-390.png` |
| 3 英文 `Settings → Library paths`（M2 票 03） | 計畫寫「設定頁已不叫這個」已過時：票 06i 起分頁名就是泊位名，英文分頁正是 `Library paths`，三處散文指得對。實際不一致的是 Route 頁 h1 與精靈頁 3 標題寫 `Routes` | 兩個標題改 `Library paths`（中文本來就都是「媒體庫路徑」）。閘門 `web/src/settings/settingsTitles.test.ts`：每個泊位分頁的頁標題要含分頁名，檔內雙向樣本；改前 en 紅兩條 |
| 4 作品頁季表不隨背景入庫更新（票 12、M3 票 06） | 從作品頁送單那條**已好**（票 12 的跟隨，5 秒內更新、與重整一致）。**重現了另一條**：`rss` 情境，作品頁開著、另一分頁加 Feed 並輪詢，RSS 把 12 集入庫，作品頁停在 0/12、沒有「下載」段，重整才 12/12——推播只在這部作品已有下載時才掛 | `useJobStream` 移到 `DownloadsPanel` 頂端，不管有沒有下載都聽；件數一變 `useSeasonsFollow` 讓季表重問。vitest「從沒送過下載時也聽推播」（改前紅）；`FakeEventSource` 抽到 `web/src/test/eventSource.ts` 兩檔共用 |
| 5 票 31 留給 polish 的項目 | 子代理逐條查：頁 4 剖面（`c79da21c` 已修）、qBittorrent 漂移值（`2056d170` 整個拿掉）**已不存在**；頁 3 進頁紅字**重現不了**（票 64 起預勾）；其餘四項重現 | `ServiceDoors` 連結 14px、沒說開新分頁：`min-h-6`（實量 24px）＋ sr-only「（開新分頁）」（`complete.doors.newTab`），vitest 兩語言、`doors-1280.png`。**重現了但不改的三項**：完成頁區塊標題沒有 `border-b-2`——帶線的是剖面板子框內的表頭，精靈各頁區塊 h3 是不帶線的 `label`（7 處），照字面加線反而分岔；`AUTH_REJECTED_TEXT` 用服務名查表——現有呼叫端都傳對的產品名，寫不出失效情境；BTH 3 詳情沒有 `.label`——「1 條 Route」自帶單位，度量名只掛在單看會歧義的值上（「版本」「憑證」） |
| 6 `development.md` 的 `mixed` 帳密說法（票 103） | `NAS_QBITTORRENT_LOGIN` 只收 `admin` / `adminadmin` | 改寫成實際規則（含 `typo` / `old` 主機名） |
| 7 `design.json` 落後 DESIGN.md | generatedAt 2026-09-26，連 M2 票 03 收掉的語言鍵矛盾都還在 | `/impeccable document` 只重寫 sidecar（子代理）：narrative 從 DESIGN.md 重生（規則 18 → 19）、`Berth Board`／`Step Line` 的 snippet 照現在的元件重寫、補 `Toggle Chips`／`Section Heading`／`Rule Cell`。同時找到 DESIGN.md「纜繩列」一節還說端點靠右，照 `StepLine` 改正 |

**通知設定頁、週報頁 critique / audit（做什麼 2）**：A（設計審查＋audit，opus）與 B（偵測器＋overlay，sonnet）分開跑；B 兩頁 CLI 0 條、overlay 1280 / 390 都 "No anti-patterns found."。

- 通知設定：critique 30/40、audit 17/20。**P1 一條已修**：Discord ID 改了沒存就按測試，送的是存著的那一個（舊 ID 到得了是假成功，到不了就一直照錯的補法修）——ID 草稿提到 `MyHalf`，測試鍵在 `aria-disabled` 並說「先儲存你改過的 Discord ID，再測試。」，`unreachableRetry` 改「補好、儲存之後…」（vitest 改前紅）。polish 順手修兩條同一段的誤導狀態：協調者點名的「改了網址說明仍寫預填的是…」（評 P3）改 `berth.unsavedEdited`；清空並儲存時「已儲存」與「還沒儲存」並列（P2）改說「已清掉：通知不附連結。」（vitest 兩條）。
- 週報：critique 29/40、audit 16/20，**沒有 P0 / P1**；polish 沒有要改的（P2 以下照票面只記）。
- 快照：`.impeccable/critique/2026-10-22T02-38-35Z__web-src-pages-notifysettingspage-tsx.md`、`…__web-src-pages-weeklypage-tsx.md`。修後重驗：通知頁那條 P1 由 vitest（改前紅）與實跑（`aria-disabled`、描述）確認，其餘照 critique 時的分級。

**P2 以下未處理（含協調者點名的）**

- 週報「產生於」用瀏覽器時區、週界用容器時區（協調者點名，**P2**）：容器 UTC+8、瀏覽器在洛杉磯時「產生於 10-18 14:00」落在週日（`weekly-tz-los-angeles.png`）。數字不錯，只是讓人懷疑週日之後沒算；容器 TZ 照 `.env.example` 設成自己的時區就一致。修法：後端 `weekly._view` 回帶容器 offset 的 `created_at`、前端 `monthDayTime` 照字串切牆上時間。
- 週報入庫清單排序前後端不一致（協調者點名，**P3**）：後端照 `title_en` 排、前端照介面語言重排；沒有任何畫面拿後端順序對照（Discord 摘要只送數字）。後端那行 `sorted` 的註解說錯用途，該改成「只為存檔可重現」或刪。
- 週報其餘 P2：404 頁「看最新一週」帶 `aria-current="page"`（`activeOptions={{ exact: true }}`）；「巡檢開出的」與 Issue 並排成同級列，容易加總成 10（標題 7 件）；換週後焦點掉到 body（全站的換頁焦點）；頁面標題全站都是 "Berth"（WCAG 2.4.2，全站另開票）。P3：歷史列「入庫 3」沒單位、h1 沒週次、`/weekly/1` 沒說不是最新、空的「還有什麼等人」照樣有快照說明、en 區塊計數只有數字、` · ` 寫死、前端自己加總（API 沒帶 `total`）。
- 通知設定其餘：收件人到不了時失敗說明出現兩次、兩個 `role=alert`（P2）；草稿沒有未儲存標示、離頁就丟（P3）；en 390 寬 token placeholder 截斷、「顯示」鍵對不齊標籤、三欄寬度不一、三處「已儲存」位置不一、token 被拒沒提 Reset Token（P3）。
- 票 130：390 寬 `Notice` 內文用 `flex-1`（basis 0）永遠排在標籤旁、被擠成約 140px 一條（**P2**；實際在 `/rss` 的 Feed 列，不是 `/issues`）——改 `flex-[1_1_16rem]` 就會換行；「檔案與版本」檔案列沒有發佈名（**P2**）：`LedgerFileOut` 沒有欄位，要後端從 `job_hash` 帶 `jobs.name`（`UnmatchedFileOut.job_name` 是先例），動 API，留給有需要的票。
- 票 127：審核佇列超過 200 列時錨點找不到（**P3**）：`review.QUEUE_LIMIT = 200` 只回最舊的 200 件，`useHashTarget` 找不到就不動；頁面已說只列出最舊的 200 件。
- 搜尋區塊 Standards 軸（84b 末條）：`.label` 裡的數字只加 `tabular-nums`、`SearchPanel.test.tsx` 三組斷言重複——照留。
- 名字 chip 一按就記進伺服器（全關也記），下一部作品就是一個名字都沒開（票 84 的設計，子代理實跑時注意到）。
- 第 4 條的殘留邊界：跟隨仍是 `useSeasonsFollow` 的啟發式（看件數與看得到的列），不是票 12 說的根本解（推播帶作品、失效 `['media', id]`）；「件數沒變、又不在這一頁」的那一筆換了狀態仍看不到。實跑的兩條路（送單、RSS 背景）都對。
- document 時找到、沒處理的兩條 DESIGN.md 與程式碼矛盾：精靈窄版摘要列的展開鍵帶 `▾`／`▴`（`aria-hidden`），DESIGN.md 的 Shapes 與 Don't 禁止字元裝飾、Known contradictions 沒登記；`RulesEditor` 的 `×`／`+`／`−` 已登記。

### code-review（`768f78e7` 起）

- **Standards**：沒有硬性違規；`settingsTitles.test.ts` 符合雙向變異規則（違規樣本與無關改動都在檔內）。改了：`events.test.tsx` 檔頭過時的那段、`SearchPanel` 的 `queries` 改名 `shownQueries`。沒改（判斷題）：`80ff5e76` 一次包了搜尋區塊五件事（已 commit，不改寫歷史）；`lookup` 是第三份同形狀的 dotted-key 走訪（`failures.test.ts`、`buildRefusal.test.ts`）；`TITLES` 的 key 是裸字串；`FakeEventSource.opened` 在兩檔各自清；en `newTab` 開頭的空白放在翻譯裡（沿用 `inventory.jellyfin.newTab` 的寫法）。
- **Spec**：七條都有重現紀錄與處理；票 31 三條「重現了但不改」與通知頁多修的兩條判為可接受（理由已在偏差）。補了：週報的 polish 結果、critique 快照、第 4 條的殘留邊界（上面三行）。

### 驗證

- `uv run pre-commit run --all-files`：全部 Passed（ruff、mypy、import-linter、prettier、eslint、knip 與檔案衛生）。
- pytest：4330 passed、2 skipped、24 deselected（14 分 53 秒，一次跑完，沒碰到 WinError 10055）。
- vitest：115 檔 2183 passed。
- 前端 e2e：第一輪 `exit 1` 但 `.last-run.json` 沒有失敗的測試（輸出被 `tail` 截掉，原因沒看到）；重跑 44 passed（3.2 分）。
