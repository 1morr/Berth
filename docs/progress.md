# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、session 紀錄、偏差與決定。

M0–M5 已驗收，只留進行中的里程碑在本檔。M0–M5 的 session 紀錄與偏差在 `docs/archive/<里程碑>.md`（`m0`、`m1`、`m1.5`、`m2`、`m3`、`m4`、`m5`）；舊文件與舊票指到「progress.md 的偏差與決定」的，到那裡找。

## 里程碑與閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| M0 | `.scratch/m0/issues/` | — | 已驗收（2026-09-08），封存於 `docs/archive/m0.md` |
| M1 | `.scratch/m1/issues/` | — | 已驗收（2026-09-17），封存於 `docs/archive/m1.md` |
| M1.5 | `.scratch/m1.5/issues/` | — | 已驗收（2026-09-19），封存於 `docs/archive/m1.5.md` |
| M2 | `.scratch/m2/issues/` | — | 已驗收（2026-09-24），封存於 `docs/archive/m2.md` |
| M3 | `.scratch/m3/issues/` | — | 已驗收（2026-09-26），封存於 `docs/archive/m3.md` |
| M4 | `.scratch/m4/issues/` | — | 已驗收（2026-10-23），封存於 `docs/archive/m4.md` |
| M5 | `.scratch/m5/issues/` | — | 已驗收（2026-10-28），封存於 `docs/archive/m5.md` |
| M5.5 | `.scratch/m5.5/issues/` | `.scratch/m5.5/spec.md`（2026-11-03 開工） | 新番時間表、追更、遲到提醒與導覽收斂（2026-10-31 加入，排在 M6 前）；助理五點修正（2026-11-01 加入） |
| M6 | `.scratch/m6/issues/` | plan §11.7；brief §14、§6.10 | 人工接管開關與背景 AI 任務（含 Issue）、影子模式（2026-10-27 改） |
| M7 | `.scratch/m7/issues/` | plan §11.8；brief §14、§16.2 | Discord 與 MCP（2026-09-22 加入、09-24 加 MCP、10-27 改名） |
| docs-diet | `.scratch/docs-diet/issues/` | — | 已驗收（2026-10-30），封存於 `docs/archive/docs-diet.md` |

開工：使用者在新 session 下 `/to-tickets docs/plan.md 拆 <里程碑> 的票`，那個 session 寫 `.scratch/<里程碑>/spec.md`、把 plan §11 那一節縮成連結、拆票，步驟在 `CLAUDE.md`〈Skills〉。沒開工的里程碑只在 plan §11；開工後以 spec 與票為準。

## 寫法與封存

- session 紀錄一列、偏差一條都 ≤ 200 字（整行的字元數，Python `len`）。細節放票的 `## Comments` 或 `docs/research/`，這裡只寫結論與連結。
- 每列、每條標里程碑：票欄寫 `<里程碑> <票號> <短標題>`（沒有票的工作省略票號），偏差寫 `- <日期> <里程碑> 票 <NN>：…`。
- 偏差只記跨票的決定：推翻 plan / brief、改流程、影響後續的票。票內取捨記在票的 `## Comments`。
- 大小：整檔 ≤ 20,000 字（`CLAUDE.md` ≤ 6,000 字），由 `tests/unit/test_reading_budget.py` 守。超過時，把進行中里程碑較舊的列與條也封存到 `docs/archive/<里程碑>.md`（同下面的做法），不要縮短措辭湊數。
- 只留進行中的里程碑：驗收票收尾時，把那個里程碑的列與條搬到 `docs/archive/<里程碑>.md`，用 `scripts/docs_moved_lines.py` 證明沒丟（遺失 0），里程碑表那一列改成「已驗收（日期），封存於 `docs/archive/<里程碑>.md`」。封存後 session 紀錄加一列，票欄標下一個里程碑（`<里程碑> 準備`），「下一步」寫它的開工指令，否則封存會把下一步一起搬走；沒有下一個里程碑時，紀錄留空，只在對話告訴使用者。
- 「下一步」寫新 session 要下的完整指令（反引號包住、`/` 開頭），或以 `等使用者：` 開頭；`tests/unit/test_progress_rules.py` 查最後一列。

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-10-31 | M6 流程 | 里程碑開工改成一個指令，所有 session 結尾給下一步指令；閘門 `test_scratch_specs.py`、`test_progress_rules.py` | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-10-31 | M5.5 規劃 | 新番時間表、追更與遲到提醒、導覽收斂排在 M6 前，寫進 plan §11.6b、brief §17 與 §20.3 | 新 session 下 `/to-tickets docs/plan.md 拆 M5.5 的票` |
| 2026-11-01 | M5.5 規劃 | 遲到提醒補上下載停滯與入庫失敗，已在等你處理的不重複開；通知寫作品與集數，沒接 Discord 時追更頁提示（plan §11.6b、§11.7、brief §17） | 新 session 下 `/to-tickets docs/plan.md 拆 M5.5 的票` |
| 2026-11-01 | M5.5 助理回饋調查 | 五點查完未改碼：Tavily 判定為模型誤報、推理未畫未接、下拉用本機價目表、`encrypted_content` 原樣印、對話 id 只在瀏覽器（`docs/research/assistant-feedback-2026-11-01.md`） | 等使用者：這五點要先修還是排進 M5.5 |
| 2026-11-01 | M5.5 規劃 | 助理五點修正寫進 plan §11.6b 與 brief §17、§20.26：模型清單、搜尋結果排最前面，其餘排在新番之後；不做 reload，指令用 `/history` | 新 session 下 `/to-tickets docs/plan.md 拆 M5.5 的票` |
| 2026-11-01 | M5.5 規劃 | 模型清單改成按鈕才連外；key 欄空著時網址相同才用存著的 key，取得模型、測試連線、儲存都守；推理程度預設中，拿掉「預設」一級（plan §11.6b、brief §20.26） | 新 session 下 `/to-tickets docs/plan.md 拆 M5.5 的票` |
| 2026-11-01 | M5.5 審核佇列調查 | 33 件查完未改碼：16 件是地上波先行被播出日比對誤擋，17 件是第一批確認，都不需要 M6（`docs/research/review-queue-2026-11-01.md`、brief §20.27） | 等使用者：要不要把規則一放寬、第一批收累計編號、升級後自動重算排進 M5.5 |
| 2026-11-01 | M5.5 規劃 | 審核佇列減量寫進 plan §11.6b 與 brief §17：照字面的先行放寬到 9 天、第一批收累計編號（量過才收）、升級後只重算舊版本的 review；票序排在搜尋結果之後 | 新 session 下 `/to-tickets docs/plan.md 拆 M5.5 的票` |
| 2026-11-03 | M5.5 開工 | spec 寫好、拆 20 張票：原①拆成 key 防護與模型清單，⑨⑩重切成遲到 Issue、換輪與刷新、追更頁、通知，加 UI 收尾；plan §11.6b 縮成連結 | 新 session 下 `/implement .scratch/m5.5/issues/01-saved-key-endpoint-guard.md` |
| 2026-11-04 | M5.5 04 地上波先行 | 照字面容忍 9 天並記 `released_ahead_of_airing`，有換算的仍兩天，第一批同窗口；正式環境 16 列 fixture 全放行；auto_wrong 0→0 | 新 session 下 `/implement .scratch/m5.5/issues/05-first-batch-cumulative.md` |
| 2026-11-04 | M5.5 01 key 防護 | key 欄空著時網址與存著的相同才用存著的 key（`_key_for`，02 共用）；測試連線與儲存都守，設定頁錯誤標在 key 欄、提示說出規則；plan §6 同步 | 新 session 下 `/implement .scratch/m5.5/issues/02-model-list.md` |
| 2026-11-04 | M5.5 01b 核准測試賽跑 | 測試的問題：核准叫醒 importer，fixture 的 Job 沒 Plan 被打回 `import_failed`；改斷言 `retried` 事件；repro 修前必紅，壓力 40 次綠 | 新 session 下 `/implement .scratch/m5.5/issues/02-model-list.md` |
| 2026-11-04 | M5.5 05 第一批累計編號 | 閘門過（含線上輪，擔保錯皆 0；累計編號只語料 2 筆）：寫明季號的累計編號由系統確認；TMDB 前季多記一集時擔保錯，測試固定，守衛候選在票上；auto_wrong 0→0 | 新 session 下 `/implement .scratch/m5.5/issues/06-replan-after-upgrade.md` |
| 2026-11-04 | M5.5 02 模型清單 | 沒按時建議照表單網址查本機表、不帶 key；按「取得模型」才問端點，問不到退回本機表。實測 DeepSeek 的 Anthropic 接口沒有模型清單（404，brief §20.26） | 新 session 下 `/implement .scratch/m5.5/issues/03-search-results.md` |
| 2026-11-04 | M5.5 03 搜尋結果 | `encrypted_content` 在 API 層拿掉（串流、重連、重新載入），歷史照留給模型；`web_search` 畫成標題、網址、日期的清單 | 新 session 下 `/implement .scratch/m5.5/issues/05-first-batch-cumulative.md` |
| 2026-11-04 | M5.5 07 導覽收斂 | 頁首五項加帳號選單（第一個下拉，disclosure、Esc 回觸發鍵）；待處理與新番帶件數（`GET /waiting`，admin）；審核/Issue、訂閱掛區塊分頁，網址不變 | 新 session 下 `/implement .scratch/m5.5/issues/05-first-batch-cumulative.md` |
| 2026-11-04 | M5.5 04b 平台先行只給照字面 | 照字面早 10–14 天的說平台先行就核准，更早的叫人查作品與 TMDB 日期，有換算的查季號與 offset；auto_wrong 0→0 | 新 session 下 `/implement .scratch/m5.5/issues/05b-cumulative-next-aired-guard.md` |
| 2026-11-04 | M5.5 05b 累計編號下一集已播 | 累計編號的第一批要下一集晚於發佈加兩天才擔保，TMDB 前季多記一集改擋下；照字面不套。閘門前後相同、擔保錯 0，SPY×FAMILY 仍擔保；auto_wrong 0→0 | 新 session 下 `/implement .scratch/m5.5/issues/06-replan-after-upgrade.md` |
| 2026-11-04 | M5.5 06 升級後自動重算 | 啟動時舊版本的 review（排除 user、audit_undone）退回 completed，規劃器在背景重算並蓋新版本；同版本重啟 TMDB 0 次 | 新 session 下 `/implement .scratch/m5.5/issues/08-schedule-sources-experiment.md` |
| 2026-11-04 | M5.5 08 時間表資料源 | 這週有集的日本作品 TMDB 列得出 93.4% / 90.8%，主幹照 TMDB；漏的是迷你番與兒童節目（brief §20.3） | 新 session 下 `/implement .scratch/m5.5/issues/09-schedule.md` |
| 2026-11-04 | M5.5 06 CI 偶發紅 | RSS 少送因送單門檻量到 CI 機器真實磁碟（`low_disk_space`），非本票；測試預設 1 TiB（`test_host_disk.py`） | 新 session 下 `/implement .scratch/m5.5/issues/10-overdue-issue.md` |
| 2026-11-04 | M5.5 09 時間表 | `/schedule` 給每個人：TMDB discover 加每部的上下一集，程序內快取 6 小時；全部列、小海報橫列；已訂閱照〈訂閱〉算 | 新 session 下 `/implement .scratch/m5.5/issues/14-airing-time-and-rating.md` |
| 2026-11-04 | M5.5 10 遲到 Issue | 巡檢開 `episodes_overdue`，一部作品一件：最後入庫之後播出滿門檻未入庫，在路上、審核、有 Issue 管著的除外，說出卡在哪；門檻在訂閱頁 | 新 session 下 `/implement .scratch/m5.5/issues/11-next-run-window-refresh.md` |
| 2026-11-04 | M5.5 11 換輪、視窗與刷新 | 隔 >21 天開 `next_run`、缺集播出滿 60 天不提醒、門檻可逐條覆寫取最大；巡檢前刷新快照，失敗的不開不收；協調者追加：退訂（刪 Feed）後不再開 | 新 session 下 `/implement .scratch/m5.5/issues/12-tracking-page.md` |
| 2026-11-04 | M5.5 14 時刻與評分 | 原文名完全相同才對（Fribb 已拿掉，Wikidata 對到太少）：AniList 給未來時刻、Bangumi 給評分，各要日期或開播日差一天內；對不上或掛掉只少兩格 | 新 session 下 `/implement .scratch/m5.5/issues/15-search-tools-status.md` |
| 2026-11-04 | M5.5 13 通知寫作品與集數 | 「等你處理」與「放太久」遇到遲到時，內文一部一行寫作品名與晚的集，換輪的說「可能是下一輪」，最多五部、其餘「等 N 部」；英文私訊用 `title_en` | 新 session 下 `/implement .scratch/m5.5/issues/12-tracking-page.md` |
| 2026-11-04 | M5.5 12 追更頁 | `/schedule/tracking`（admin）一部一列：字幕組、已播到、已入庫到、狀態；停滯說「下載停滯」、晚的寫「晚 N 天」（從播出日算），斷更很久收起；判定與巡檢共用 | 新 session 下 `/implement .scratch/m5.5/issues/16-reasoning-in-panel.md` |

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-10-31 M6 流程：M6 起 spec 由開工 session 寫到 `.scratch/<里程碑>/spec.md`，plan §11 對應節縮成一行連結、編號不變（改 plan §11 導言、`CLAUDE.md`〈Skills〉）；M0–M5 與 docs-diet 不補。
- 2026-10-31 M5.5 排程：M6 之前插入 M5.5（使用者定），M6 改在它驗收後開工；改 plan §11.6b、brief §17、`PRODUCT.md` 里程碑表、`CLAUDE.md` 的 spec 起始里程碑。
- 2026-11-01 M5.5 範圍：助理五點修正併入 M5.5（使用者定），模型清單與搜尋結果最先做；改 plan §11.6b、brief §17 與 §20.26、`PRODUCT.md`。
- 2026-11-01 M5.5 範圍：審核佇列減量併入 M5.5（使用者定），排在模型清單與搜尋結果之後；規則一「早於播出日就一定算錯」不成立（brief §20.27），實作時改 plan §4.4、brief §15。
- 2026-11-01 M5.5 範圍：存著的 key 只送到存它的端點（使用者定按鈕，範圍由調查補上），改既有的 `ai.test_ai` 與 `ai.set_ai`；改 plan §11.6b。
- 2026-11-03 M5.5 票序：原①拆成 01 key 防護與 02 模型清單（仍共用一支函式），⑨⑩重切成 10–13；「新番」在 07 只給 admin、只有訂閱分頁，09 才對所有人顯示（使用者定；`.scratch/m5.5/spec.md`〈票序〉）。
- 2026-11-04 M5.5 票 04：規則一改成照字面的列九天、有換算的兩天（改 plan §4.4、brief §15、§20.11、§20.27、`CONTEXT.md`）；「照字面」抽成 `parser/literal.py` 與第一批共用，`check_airing` 多收發佈名，`publishing.just_aired` 分兩個窗口；offset 設 0 算照字面。
- 2026-11-04 M5.5 票 07：頁首件數各歸各頁（使用者定）：待處理＝審核＋Issue、待綁定掛在新番，頁首數字才對得上點進去的件數；三格加總仍是 Discord 的 N（`test_notify_waiting.py` 守）。改 spec〈範圍〉、plan §6–7、DESIGN.md、brief §13。
- 2026-11-04 M5.5 票 04b：規則一擋下的照字面列早 ≤14 天記 `released_far_ahead_of_airing`（說平台先行），更早記 `released_too_early_for_simulcast`；`released_before_airing` 只剩有換算的（改 plan §4.4、brief §20.27、spec）。
- 2026-11-04 M5.5 票 08：時間表覆蓋率只算日本作品（使用者定），TMDB 主幹不換；discover 用 `ja|zh`、窗口前後放寬一天，每部再讀 `tv/{id}` 才知道哪天第幾集（改 brief §20.3、spec〈範圍〉、票 09）。
- 2026-11-04 M5.5 票 09：時間表的「已訂閱」照 `CONTEXT.md`〈訂閱〉（預先綁定的 Feed 或帶著綁好 Series 的 Feed，刪 Feed 就不算），不是「有綁好的 RSS Series」；票 07 留下的區塊設定收斂轉給票 12（改 plan §6–7、brief §13、shape）。
- 2026-11-04 M5.5 票 10：遲到門檻放訂閱頁全域區、存 `RssSettings.overdue_days`（使用者定，票寫設定頁）；卡在哪多一種 `download_failed`；`IssueSubject` 加作品（改 plan §2.1、§2.4、§3.2、§6，brief §9.1，`CONTEXT.md`）。
- 2026-11-04 M5.5 票 11：遲到只看還訂著的作品、帶著 Item 的 Series（協調者追加，`rss.subscribed_media`）；`rss-sweep` 替身的 SPY×FAMILY 過了 60 天視窗不再開遲到，票 12、13 要遲到的替身得另做（改 plan §2.4、§3.2，fake-backend.md）。
- 2026-11-04 M5.5 票 14：時刻與評分改用原文名完全相同對 AniList / Bangumi（Fribb 已拿掉，Wikidata 只對到 46% / 16%），時刻要日期、評分要開播日差一天內；改 brief §20.3、plan §6–7、DESIGN.md、`CONTEXT.md`。
- 2026-11-04 M5.5 票 13：`episodes_overdue` 的 `detail_json` 多 `title_en`（英文通知用，舊件退回 `title`），票 12 的追更頁也可讀；改 plan §3.2〈`notify_sender`〉〈`sweeper`〉。
- 2026-11-04 M5.5 票 12：「晚 N 天」從播出日算（使用者定）；追更的程式碼叫 `keeping_up`（`tracking` 是 Tracked Media），遲到判定抽成 `watch_overdue` 與巡檢共用；區塊設定收成 `web/src/nav/sections.ts`（改 plan §6–7、brief §13、`CONTEXT.md`、DESIGN.md）。
