# M4 遺留項審計：票 Comments 與 progress.md 偏差與決定

審計日期 2026-10-27，基準 commit `5fc0bbc8`（v0.3.0 之後）。唯讀：沒有改任何程式碼、票、docs。

## 0. 範圍與方法的限制（先讀）

- `.scratch/m4/issues/` 共 156 檔，其中 140 張有 `## Comments`（全文約 51 萬字元）。我用關鍵字（未處理、留給、後續、M5、延後、待、尚未、另開…）過濾段落後逐段讀完，**沒有每張票的 Comments 逐字全讀**；過濾之外的段落多是實作紀錄。
- Comments 裡「code-review 未處理」的 Standards 判斷題（Duplicated Code、Data Clumps、命名、常數兩份）約 150 條，我**不逐條重驗**，依票歸成幾列（L71–L74、L84）；它們不影響行為，也不擋 M5。逐條驗證的是：行為或正確性缺陷、跨票承諾、「待使用者確認」、M5 相關項。
- `.scratch/m5/` 目前不存在，所以「後續票」只可能是 M4 內較晚的票（≤133）或 M3 以前的票；M4 之後沒有票處理過任何東西。
- progress.md「偏差與決定」(L290–L1640) 約 530 行：多數是「已做的決定」，不算遺留。只收明寫「待使用者確認」「沒開票」「留給之後／M5」「不做但未決」的項目。
- 「已處理」的判定都附票號並用 `grep`/讀碼確認過現況；標「未重驗」的是我只引用票自述。

## 1. 摘要

- 總條數 **85**（其中 L84 把約 150 條 Standards 判斷題合成一列、L71–L74 各合成數條）。
- 後續票已處理：**21** 條；仍未處理：**57** 條；已不適用：**7** 條。
- 與 M5 相關：**11** 條（直接相關 7、間接 4）：L01, L02, L03, L04, L05, L06, L07, L08, L09, L10, L11。
- progress.md 明確寫「留給 M5／M5 再做」的事項見第 4 節（9 條，多數是 M5 開頭的既定工作，不是新發現的缺陷）。
- 會擋 M5 **拆票**的只有決定題（L06 三種停住 Job、L11 非 admin 看 Job 的範圍、L04 `confirm_audit` 反向命令）；會擋 **實作**的是登錄表前置（L01–L05）。細節見第 3 節。

## 2. 全表

判定：**後續票已處理** / **仍未處理** / **已不適用**。證據欄的行號是 2026-10-27 `main` 現況。

| # | 來源 | 發現 | 判定 | 依據 | 與 M5 相關？ |
| --- | --- | --- | --- | --- | --- |
| L01 | progress 2026-09-26 全面審查（L1282）；plan §11.6；M4 票06 | `BEFORE_M3` 豁免 41 個 service 模組，其中 34 個仍有公開 `async def` 未標 `@command`：共 149 支公開 async def，142 支沒有標記（jobs 15、routes 13、jellyfin 9、setup 9、issues 8 中 5 支、rematch 7、health 7 …；含純讀函式，AST 計數）。M5 登錄表要讀這些 | 仍未處理 | `tests/unit/test_command_marks.py:31-72`（BEFORE_M3）；本審計 AST 計數；`.scratch/m4` 無任何票處理 | 是 |
| L02 | M4 票06 Comments | `claim_owner`、`open_session` 是寫入命令，落在豁免的 `setup`、`auth`，閘門守不到（票寫「M5 補標記時一起」） | 仍未處理 | `berth/services/setup.py:267`、`berth/services/auth.py:97`（無 `@command`） | 是 |
| L03 | M4 票126 Comments | `test_command_marks` 只認 `inspect.iscoroutinefunction`，被 `@asynccontextmanager` 包過的公開命令（`download_round`）不標也不紅；票內只手標，閘門沒補 | 仍未處理 | `tests/unit/test_command_marks.py:97`；`berth/services/downloading.py:60-62`（手標 `@command(IRREVERSIBLE)` 疊在 `@asynccontextmanager` 上） | 是 |
| L04 | plan §11.6（M3 票05 遺留） | `confirm_audit(s)` 的反向命令標成 `review.undo_audit`，但 `undo_audit` 是拆入庫、且拒絕確認過的列，語意不是反向；plan 要求登錄表開工時另立「取消確認」或改 `inverse=None` | 仍未處理 | `berth/services/review.py:347,365,392`（仍是 `inverse="review.undo_audit"`） | 是 |
| L05 | M4 票60 Comments | `rebuild_ledger` 標 `REVERSIBLE` 卻無反向命令（冪等寫入）；票寫「M5 做登錄表時若要分出冪等的寫入再改」 | 仍未處理 | `berth/services/ledger_rebuild.py:87-89` | 是 |
| L06 | M4 票129、133 Comments；progress L288 | 停住的三種 Job（重試用完／永久失敗的 `submit_failed`、`import_failed`、`stalled`）沒有 Issue、不進「等你處理」；列為「待使用者決定」，沒實作。M5 的 AI 任務「交給人」走等你處理，範圍取決於此 | 仍未處理 | `berth/services/sweep.py:80-81,84`（`_STUCK_STATES` 只含 `SUBMIT_FAILED`、`CLIENT_ERROR`）；progress.md:288 寫「待決三條」 | 是 |
| L07 | M4 票123 Comments | DEBUG 底下 aiosqlite 會印 SQL 參數，含 `settings` 整份 JSON（所有憑證）；root level 固定 INFO 所以沒事，之後若加調 log 等級的開關要先處理。M5 會把 AI provider 憑證放進 `settings.ai`，同一風險 | 仍未處理 | `berth/logs.py:128-140`（`configure_logging(level=INFO)`，無開關）；票 123 Comments | 是 |
| L08 | M4 票13b、130 Comments | 背景規劃／輪詢的 guessit 解析仍在事件迴圈上（第一次 ~400 ms、一批新發佈名卡住別的請求），根治（`to_thread` 或 process pool）沒做；票 130 的巡檢已自行讓出迴圈。M5 的 `ai_worker` 與 planner 觸發會加量 | 仍未處理 | `berth/services/plan.py:579`（只有 mediainfo 用 `asyncio.to_thread`；`grep to_thread berth` 僅此一處） | 弱 |
| L09 | M4 票71b Comments | 七個迴圈的 `run()` 骨架相同未收斂；對帳 task 關機仍直接 cancel；關機等正在跑的一輪沒有總上限。新增 `ai_worker` 迴圈必須走 `pipeline/ticks.py` 並過 `test_every_loop_is_here` | 仍未處理 | `berth/pipeline/ticks.py`；票 71b Comments | 弱 |
| L10 | M4 票130 Comments；票132 P2 | 「檔案與版本」檔案列沒有發佈名（`LedgerFileOut` 無欄位），撞集 Issue 的下一步要人從檔名認；要後端從 `job_hash` 帶 `jobs.name`。AI 判斷撞集時也需要這欄 | 仍未處理 | `berth/api/media.py:103-121`（無 `job_name`） | 弱 |
| L11 | progress L1283（M3 後審查，沒開票） | 非 admin 看得到所有人的 Job（brief §11 與 §13 說法不一，要使用者拍板）。M5 的 AI 活動頁、Proposal 的可見範圍會碰同一題 | 仍未處理 | `berth/api/jobs.py:339` 取 `current_user`；progress.md:1283 無後續決定 | 弱 |
| L12 | M4 票125 Comments | 升級前排著的「可以看了」沒有 `library`，送出時當成看不到而放棄 | 已不適用 | 待送表從票 123 起、與 125 同版以 v0.3.0 發布（progress.md:288），沒有舊資料需要 migration | 否 |
| L13 | M4 票123 Comments | `set_bot_token` 收 `user_id` 只為回 view，等票 125 開放給每個人時一起看 | 後續票已處理 | 票 125；`berth/services/notify.py:389-391`（簽名已無 `user_id`） | 否 |
| L14 | M4 票123 Comments | 待送表太舊的不送；一輪不控速 | 後續票已處理 | 票 128（`_give_up_stale`、單則 429 停這一輪，決定寫在 plan §11.5） | 否 |
| L15 | M4 票125 Comments | 管理員另有的「等你處理」「週報」沒有勾選 | 後續票已處理 | 票 127、131；`web/src/pages/NotifySettingsPage.tsx:86-90`（`waiting`、`weekly` 兩種） | 否 |
| L16 | M4 票125 Comments | 只併還在合併窗口的那一則：故障期間延後的那一則不再併，同一部作品每 5 分鐘一則；要併得多一個狀態，「留給里程碑收尾看要不要」 | 仍未處理 | `berth/services/notify.py` `_MERGE_GUARD`；133 之後無票處理 | 否 |
| L17 | M4 票126 Comments | 收件人查詢有三份（`queue_ready`、`_queue_waiting`、`queue_downloading`） | 後續票已處理 | 票 131（progress.md:1633：抽成 `services/recipients`）；`berth/services/recipients.py` 存在 | 否 |
| L18 | M4 票126 Comments | `moment`／`batch` 成對穿過 `_prebind`…`_subscribe`；關機 cancel 的那一輪已送出的沒有通知；人按重試、自動重送成功的不補「正在下載」 | 仍未處理 | 未重驗（票自述判斷題／邊角） | 否 |
| L19 | M4 票127 Comments | 審核佇列超過 `QUEUE_LIMIT`(200) 時排在後面那件的錨點找不到；一般使用者升管理員不自動補「等你處理」勾選；錨點形狀前後端各寫一份無閘門 | 仍未處理 | `berth/services/review.py:85`；票 132 列為 P3 | 否 |
| L20 | M4 票128 Comments | `series_review.py:377` 有同樣的 `extra={"job":…}` 會 `KeyError` | 後續票已處理 | 票 133（progress.md:1640；`tests/unit/test_logs.py` 掃 `berth/` 的閘門）；現況 `series_review.py:380` 無 `job` 鍵 | 否 |
| L21 | M4 票128 Comments | 「24 小時」寫在 `GIVE_UP_AFTER` 又寫死在 i18n 與 CHANGELOG 無閘門；`notify.backoff` 與 `downloads.backoff` 同形；退避中按「測試」不清退避 | 仍未處理 | 未重驗（票自述判斷題） | 否 |
| L22 | M4 票132 Comments（協調者點名 P2） | 週報「產生於」用瀏覽器時區、週界用容器時區，容器 UTC+8、瀏覽器在洛杉磯會落在週日 | 仍未處理 | `berth/services/weekly.py:164`（`created_at=moment` 無 offset）；`web/src/pages/WeeklyPage.tsx:96`（`new Date(report.created_at)`） | 否 |
| L23 | M4 票132 Comments | 週報入庫清單前後端排序不一致（P3）、後端 `sorted` 註解說錯用途；週報其餘 P2/P3（404 頁 `aria-current`、並排成同級列易加總成 10、`/weekly/1` 沒說不是最新…） | 仍未處理 | `berth/services/weekly.py:242`（仍 `sorted(... title_en ...)`） | 否 |
| L24 | M4 票132 Comments（P2） | 390 寬 `Notice` 內文 `flex-1`（basis 0）被擠成約 140px；建議 `flex-[1_1_16rem]` | 仍未處理 | `web/src/components/controls.tsx:279`（仍是 `min-w-0 flex-1`） | 否 |
| L25 | M4 票132 Comments | 通知設定其餘：失敗說明出現兩次、兩個 `role=alert`（P2）；草稿無未儲存標示、token placeholder 截斷、token 被拒沒提 Reset Token（P3） | 仍未處理 | 未重驗；票 132 自述未處理 | 否 |
| L26 | M4 票132 Comments | 頁面標題全站都是 "Berth"（WCAG 2.4.2）「全站另開票」 | 仍未處理 | progress.md / .scratch 無對應票（`grep -l '2.4.2' .scratch/m4/issues` 只有票 132 本身） | 否 |
| L27 | M4 票132 Comments | 名字 chip 一按就記進伺服器（全關也記）；`useSeasonsFollow` 仍是啟發式，非票 12 說的根治（推播帶作品、失效 `['media', id]`） | 仍未處理 | 票 132 殘留邊界；票 12 同 | 否 |
| L28 | M4 票132 Comments | DESIGN.md 與程式碼矛盾：精靈窄版摘要列展開鍵 `▾`/`▴` 沒登記到 Known contradictions | 仍未處理 | 票 132 自述未處理 | 否 |
| L29 | M4 票06 Comments | 390 寬 sticky 主鍵遮欄位（critique P1） | 已不適用 | 票 132 #1 逐一 focus 重現不了，是整頁截圖假象（`scroll-padding-bottom: 6rem`） | 否 |
| L30 | M4 票06 Comments | `flat-type-hierarchy`（整頁 h1/h2 同字級） | 仍未處理 | 票 132 沒處理這一條；未重驗 | 否 |
| L31 | M4 票06 Comments | 非管理員在精靈跑一半時自己去 `/login`，`/setup` 守衛只看有沒有 session，每支回 403；罕見 | 仍未處理 | 未重驗（`berth/api/gate.py`） | 否 |
| L32 | M4 票31 留給 polish 的項目（見票56/132） | ServiceDoors 連結 14px 沒說開新分頁、頁 4 剖面、qBittorrent 漂移值 | 後續票已處理 | 票 132 #5（`min-h-6` + sr-only「（開新分頁）」）；其餘兩項已在 `c79da21c`、`2056d170` 消失 | 否 |
| L33 | M4 票31 → 票132 #5 | 完成頁區塊標題無 `border-b-2`、`AUTH_REJECTED_TEXT` 以服務名查表、BTH 3 詳情無 `.label` | 已不適用 | 票 132 #5 決定重現但不改（精靈 h3 慣例不帶線；寫不出失效情境） | 否 |
| L34 | M4 票04 Comments；票12 Comments | e2e `rss-subscribe`／`rss-preview-390` 時序 flake | 後續票已處理 | 票 13b（guessit 重複解析 → `parse_release` lru_cache）；票 24（`poll_feed` singleflight）；票 121b（spec 先等入庫） | 否 |
| L35 | M4 票04 Comments | `?page=1e20` 過得了前端驗證，SQLite offset 溢位回 500，畫面說「後端不可達」（媒體庫牆同寫法） | 仍未處理 | `web/src/routes.tsx:311,350`（`Number.isInteger(1e20)` 為 true） | 否 |
| L36 | M4 票04 Comments | 看著的那一筆入庫從清單消失時鍵盤焦點掉回 `body`（`useFocusAfterRemoval` 只認 `<article>`，下載列是 `<details>`） | 仍未處理 | 未重驗；票自述「沒做」 | 否 |
| L37 | M4 票12 Comments；progress L1283 | 作品頁季表 5 分鐘 `staleTime`、SSE 不使其失效 | 後續票已處理 | 票 132 #4（`useJobStream` 移到 `DownloadsPanel` 頂端），殘留邊界見 L27 | 否 |
| L38 | M4 票01 Comments | `LISTED_STATES` 不含 `missing_files`／`client_error`：接回時落在 `submitted` 的那種晚一輪建清單 | 仍未處理 | `berth/services/downloads.py:129`（仍只有三個）；已記 plan §3.3 | 否 |
| L39 | M4 票01 Comments | `_plan` 的 TMDB 刷新與 mediainfo、importer 的 Jellyfin 通知是否在寫交易之後才跑沒有閘門（無 repro） | 仍未處理 | 未重驗；`plan.py:579` 已是 `to_thread` 但無交易外閘門 | 否 |
| L40 | M4 票03 Comments | 重啟時被打斷那筆 `attempt` 從 1 重數；`_due_retries` 每輪讀全部 `submit_failed` 事件；時間線顯示過去的「自動再送」；重送在 poller 輪內串行 | 仍未處理 | `berth/services/jobs.py:606-627`（仍全量讀）；票自述無 repro | 否 |
| L41 | M4 票08 Comments | 加路徑失敗後改選別的路徑建成 Route，Jellyfin `libraries` 那一步仍 `failed`，直到下次加路徑成功（票 06h 起的行為） | 仍未處理 | 未重驗；票寫「沒有 repro 票先不動」 | 否 |
| L42 | M4 票100 Comments | `poll_due` 一次 `select` 判到期，與走進 `poll_feed` 之間「立即輪詢」整輪跑完時，背景那輪仍用舊判斷多輪一次 | 仍未處理 | `berth/services/rss.py:845-855`（形狀未變） | 否 |
| L43 | M4 票13 Comments | `latest_episode` 不套 offset（split-cour 第二輪說 E25）；從作品頁訂閱建的單一 feed 網址帶 `bangumiId=…&subgroupid=…` 仍印出；安靜門檻與列上「最近」口徑不同 | 仍未處理 | 未重驗 | 否 |
| L44 | M4 票14 Comments | 綁定框預填（`searchTerm.ts`）是 `parser.binding.skeleton` 在前端的手抄、不拆季名 | 後續票已處理 | 票 88（預填取後端 `search_terms` 第一個） | 否 |
| L45 | M4 票88 Comments | 千夏一例：`skeleton` 不切底線，預填是整格；括號標題結尾（尼古喵喵）退步 | 仍未處理 | 底線：票 88 決定另開票未開；括號：已由票 98 修（`binding._NOTE`）。底線部分仍未處理 | 否 |
| L46 | M4 票24 Comments | `test_setup_api.py` 撿到前面測試漏關的 aiosqlite 連線（既有不穩定） | 後續票已處理 | 票內自述同 session 另一 commit 修（`berth/db/engine.py`，關機 cancel 時連線沒人關）；票 71b 另有迴圈關機 | 否 |
| L47 | progress L1357（M4 票22） | 已存在的 Berth 分類「`downloadPath` 不同」只算有設而且不同；**待使用者確認** | 仍未處理 | progress.md:1357；全文搜尋無後續確認紀錄 | 否 |
| L48 | progress L1378（M4 票27） | 「還差」多列「加入至少一個站」、只在桌機固定（窄版兩條 sticky 疊在一起）；**待使用者確認** | 仍未處理 | progress.md:1378；票 119 只保留「一屏一顆主鍵」，沒有明確確認紀錄（拿不準，列入） | 否 |
| L49 | progress L1504（M4 票83） | 搜尋結果判定順序與 shape 原稿不同；**待使用者確認** | 仍未處理 | progress.md:1504；83b/83c 沿用該順序，無推翻或確認紀錄 | 否 |
| L50 | progress L952（M3 票14） | 停用的 Route 不算完成條件 + `/api/routes` 精靈前匿名開放；待使用者確認 | 後續票已處理 | 票 14a（progress.md:952 末句「已解（票 14a）」） | 否 |
| L51 | M4 票55 Comments；progress L1454 | U4：mover 搬過之後帳本 inode 過期，只有「先在 qBittorrent 連檔刪 torrent 再被搬」會碰到，結果是不刪；「留給下一批拆票決定」 | 仍未處理 | progress.md:1454；`grep -rn mover berth` 無處理 | 否 |
| L52 | progress L1443（M4 票52） | 既有而還沒初始化的 Jellyfin，`system.xml` 事先放的名字會被 `/Startup/Configuration` 清成空字串；要保住得先讀 `GET /Startup/Configuration` | 仍未處理 | 記在 plan §9.4；`berth/services/jellyfin.py` 無讀回 | 否 |
| L53 | M4 票54 Comments | 移除分類與送單之間沒有鎖（qBittorrent 可能自建預設路徑同名分類，沒查證）；`definitionName` 比對可能把使用者自加的站列成 Berth 加的；連不到時列全部 Route 的分類 | 仍未處理 | 未重驗；票自述「記著」 | 否 |
| L54 | M4 票54 → 票101/38 | `apply_qbittorrent` 對既有那一台仍收（前端已無呼叫端），改 422 是破壞性變更 | 後續票已處理 | 票 101（existing-qbittorrent-apply-422） | 否 |
| L55 | progress L1461（M4 票58） | tag 與 `pyproject.toml` 版號一致目前沒有 CI 守，「留給下一次發版前決定」；v0.3.0 又是手改版號（commit `4f94b222`） | 仍未處理 | `.github/workflows/release.yml`、`ci.yml` 無 pyproject 與 tag 比對；`tests/` 無對應測試 | 否 |
| L56 | M4 票57 Comments | `deploy/.env.example` 與 compose 註解仍是中文 | 後續票已處理 | `grep -cP '[\x{4e00}-\x{9fff}]' deploy/.env.example deploy/docker-compose.yml` 兩份皆 0（已為英文，票 58 發版前處理） | 否 |
| L57 | M4 票67 Comments | `.torrent` 下載不進請求預算（32 個）；番組頁以 `bangumi_id` 去重 | 已不適用 | `.torrent` 部分：票 107 整個刪掉請求預算；番組頁去重：票 82（`_ShowPages`） | 否 |
| L58 | M4 票67 Comments | 《Law & Order》TPB 回 0 筆，要不要多一個 `and` 變體 | 後續票已處理 | 票 84（`berth/services/search_queries.py:209` `Law & Order` / `Law and Order` 兩種拼法） | 否 |
| L59 | M4 票67 Comments | 跳過一部分站後剩下的站被 Prowlarr 自己停用，帶 `indexerIds` 查詢回 400 | 已不適用 | 票 107 刪預算，查詢不再帶 `indexerIds`（`test_gaps_in_twelve_seasons_are_asked_batch_by_batch` 斷言 `indexer_ids == ()`） | 否 |
| L60 | M4 票107 Comments | 每個查詢都 `ServiceError` 失敗時一律回 `unreachable`（5xx/429 也說「連不上」）；要分開得拆 `ServiceUnavailableError` | 仍未處理 | `berth/services/search.py:670-676`（`_problem` 只分 `AuthFailedError` 與其餘）；票 114 只分出逾時 | 否 |
| L61 | M4 票74 Comments | `freed` 與估算用表觀大小，sparse 檔會多報 | 後續票已處理 | 票 102 #4（`fs.PathFacts.allocated`、`st_blocks`） | 否 |
| L62 | M4 票73 Comments | 換台後還在下載中的 Job 變 `client_removed` 待處理沒預告；「改位址」從既有換既有沒走換台框；同一台只換 IP 被當成換台 | 後續票已處理 | 票 102（in_flight 例外段、改位址就地換台說明）；同一台認不出來是決定，見 brief §20.2〈同一台 qBittorrent 認不出來〉 | 否 |
| L63 | M4 票76 票外發現 | `/api/search` 的 `download_url` 帶 Prowlarr API key 交給一般使用者 | 後續票已處理 | 票 79（`source_id`；`berth/services/sources.py:3,67`） | 否 |
| L64 | M4 票79 Comments | 結果的 `key`、`info_url` 是索引站給的值，私有站 guid 可能帶 passkey（範圍外） | 仍未處理 | 未重驗；票自述不在範圍 | 否 |
| L65 | M4 票69 Comments | 已知限制：無集號的動畫合集擋不到；`Law & Order: SVU` 混進主表；字幕組集號 regex 誤判兩位數光碟；探索年份拆分；成人分類只擋有映射的站 | 仍未處理 | 票 69「已知限制（判斷題，留著）」；票 83/83b 重構了判定但未宣稱解決 | 否 |
| L66 | M4 票56 Comments（audit 未處理表） | 表中標「修」的條目（#21、25、27a/c、28–34、36–38、40–50） | 後續票已處理 | 票 56 同票修掉並加 `resources.test.ts:64` 的條數閘門（「五條」→不寫數字）；逐條未重驗，除 #25 外 | 否 |
| L67 | M4 票56 Comments | #27b `POST /setup/tmdb/test` 不擋垃圾字串、#40 重新整理不留、#35 定義只有英文 | 仍未處理 | 票 56 自述「刻意」；屬決定而非缺陷（拿不準，列入） | 否 |
| L68 | M4 票117 Comments | `Media.default_route_id` 也是 `SET NULL`，刪 Route 無聲清掉，`RouteUsage` 沒算它 | 仍未處理 | `berth/models/media.py:108`；`berth/services/routes.py:469-480`（`RouteUsage` 只有 jobs、ledger_entries、rss_feeds、rss_series） | 否 |
| L69 | M4 票109 Comments | 前端 `DEFAULT_FEED_INTERVAL=900` 與後端 `DEFAULT_INTERVAL_SEC` 無閘門 | 仍未處理 | 票自述「先記著」 | 否 |
| L70 | M4 票111 Comments | Series 綁了但 Route 被清掉（`route_id` 空）時「仍然下載」鍵仍可按；兩分頁同時放行靠 `_sent_before` 沒專屬測試；清單每列 `await _release_block` 無批次預載 | 仍未處理 | 未重驗 | 否 |
| L71 | M4 票112／110／113／105 Comments | UI 小項：Feed 表單 `OneshotSection` 自有拒絕串接、`BACKFILL_LEDE` 字面兩份、兩層 toggle 命名、全域查詢失敗時合集那行不顯示… | 仍未處理 | 票自述判斷題／critique 項；未逐條重驗 | 否 |
| L72 | M4 票130 Comments | `sweep` 非預期例外冒到 `poll_due` 被記成輪詢失敗；`IssueRow.tsx` 又抄一份 `INLINE_LINK`（抽共用留給 UI 收尾） | 仍未處理 | 未重驗 | 否 |
| L73 | M4 票129 Comments | `Sweeper` 與 `Reconciler` 排程逐行相同；前端 `STUCK_STATES` 抄後端；`_render_lingering` 與 `_render_waiting` 重複 | 仍未處理 | 票寫「第三個每日迴圈出現再抽」；現有 `weekly` 排程也在 `Sweeper` 內（票 131） | 否 |
| L74 | M4 票133 Comments | 版本下限在後端常數、`VERSION_FLOOR`、`choice.existing.floor.*` 三處無閘門；`_Outcome.detail` 一欄多義；`kind === 'jellyfin'` 特判散落 | 仍未處理 | 票 133 自述未處理（票 17 起就記過） | 否 |
| L75 | progress L1283（M3 後審查，沒開票） | 角色只在登入時讀、session 30 天，Jellyfin 降權不反映；`EVENT_TYPES` 手抄無閘門；SSE 遇非 200 永久斷線；`preview_feed`/`list_series` 無上限且 N+1；正式規劃失敗每 60 秒無退避；直接開不存在路徑拿純文字 `Not Found` | 仍未處理 | `web/src/jobs/eventTypes.ts:10`（手抄）；`berth/pipeline/planning.py:31`（TICK 60s、無退避）；其餘未重驗 | 否 |
| L76 | progress L1283 | RSS「全部下載」與補舊集在同一 HTTP 請求裡逐筆送單 / TMDB 429 與 Mikan 暫時失敗讓自動綁定永久 `lookup_failed` | 後續票已處理 | 後者：票 14（`ProtocolMismatchError`/429/5xx 分類、`lookup_retry` 重認，上限三次）；前者：`download_round`／背景送單（票 126、18），未逐條驗證 | 否 |
| L77 | progress L1288、L1015 | RSS Series 去留與 Mikan 補舊集預設「使用者要再討論」；EN 介面海報仍取 zh-TW 那一輪（要不要開票待使用者決定） | 仍未處理 | RSS：M3 票 13 起已重設計（「RSS 重新設計」），後續票 105–116 已實作 Series 呈現，視為 H 的可能性高，但無明確結案紀錄，拿不準列入；海報：`grep poster` 未驗 | 否 |
| L78 | M4 票44 Comments | 兩個分頁幾乎同時按主鍵時，推薦站撞同名被記成「測過、加不進去」 | 仍未處理 | 票自述無 repro | 否 |
| L79 | M4 票89／90／95 Comments | 精靈 `indexer.remove.failed`、`routes.rereadFailed`、`inventory.narrow.failed` 不管錯誤是什麼都怪外部服務／不說原因 | 後續票已處理 | 票 95（`RemoveFailed`、`RereadFailed`、`NarrowFailed`；502 `IndexerNotRemovedError`） | 否 |
| L80 | M4 票119 Comments | 桌機把介面登入搬到剖面欄（`aside`）、Tab 順序不一致、`64rem` 三處 | 已不適用 | 票 119 自己撤回（critique 28→28），「新 commit 撤回」 | 否 |
| L81 | M4 票120／progress L1599 | 頁 2、頁 4 位址 placeholder 跟著頁 1 的主機 | 已不適用 | 使用者決定不做（progress.md:1599，票 120 改名縮範圍） | 否 |
| L82 | M4 票60 Comments | `POST /rebuild-ledger` 只在開始時看對帳有沒有在跑，重建途中 04:00 對帳可能開始、兩邊替同一檔開件會撞鍵；待處理頁同步走訪媒體庫；`_library_files` 與 `reconcile._ask_library` 重複 | 仍未處理 | 票自述「要等 `ReconcileRunner` 有一把能讓重建一起拿的鎖」；未重驗 | 否 |
| L83 | M4 票51／62 Comments | 同一筆 Job 兩列被兩邊同時找到可能沒人寫 `_all_found`；Issue 只能寫條件句；入庫當下就掃再快 30 秒沒做 | 仍未處理 | 票自述無 repro／沒做 | 否 |
| L84 | M4 票02(jellyfin-verify)／09／21／33 等 Comments | Standards 判斷題：重複常數／名字（`QbittorrentOut.web_ui_login` 與 `writes_preferences`、`_refuse_existing` 兩份、站的描述欄位六份、`ExistingServices` 兩份組裝…） | 仍未處理 | 各票自述「判斷題，留著」；共約 150 條，**未逐條重驗**，見第 5 節 | 否 |
| L85 | M4 票56 Comments | `ProwlarrLogin.save` 吞掉 reject、不畫 `prowlarrLogin.error`（#21） | 後續票已處理 | 票 56 自己修（表內「修」）；未重驗現況 | 否 |


## 3. 仍未處理的條目，依嚴重度，說明是否擋 M5

嚴重度只看對 M5 的影響；非 M5 的 UI／邊角缺陷排在最後一段，全部不擋。

- **L01（高，142 支命令未標記）** M5 開頭的既定工作，量比預期大：142 支未標記函式含 `jobs.add_download`／`delete_job`、`rematch.*`、`plan_review.*`、`deletion.*`——正是 AI 工具最可能呼叫的命令。**不擋拆票**（plan §11.6 已把「表本身 + 補標記」寫成 M5 第一步），但會決定票數與順序：建議拆成「登錄表骨架 + 閘門」與「逐模組補標記（每模組一票或一批）」，且補標記時要判每一支是 read／reversible／irreversible，這是設計決定，不是機械工作。
- **L06（高，三種停住的 Job 沒有 Issue）** 擋 **AI 任務範圍** 的設計題。M5 的結果是「已處理」或「交給人（走等你處理通知）」；目前 `submit_failed`（用完）、`import_failed`、`stalled` 沒有 Issue，AI 和通知都無從「交給人」。要在拆票前由使用者決定這三種是否各開 Issue 型別（progress.md:288 已列為待決三條之一）。
- **L04（高，confirm_audit 反向命令錯指）** 擋登錄表的 `inverse` 語意。`confirm_audit(s)` 的 `inverse=review.undo_audit` 是錯的（它拆入庫、拒絕確認過的列）；AI 對 audit 的「自動確認」依賴一個真的反向命令（「取消確認」）。拆票時要先決定：新增 `unconfirm_audit` 或改 `inverse=None`。
- **L03（中，asynccontextmanager 閘門漏洞）** 閘門漏洞：登錄表若靠 `inspect.iscoroutinefunction` 或 `mark_of` 掃模組，`@asynccontextmanager` 包過的 `download_round` 會漏。登錄表實作票要順手修 `commands_of`（`test_command_marks.py:97`），否則 AI 的「正在下載」類命令不在表裡。
- **L02（中，claim_owner／open_session 未標）** `claim_owner`、`open_session` 是寫入命令但屬 auth／setup，AI 永遠不該呼叫。登錄表要能標「不可由 AI 使用」（例如 `irreversible` 之外的 `human_only`），或明確排除 `setup`／`auth`；這是登錄表 schema 的設計輸入。
- **L11（中，非 admin 可見 Job 範圍未定）** 非 admin 能否看所有人的 Job（brief §11 與 §13 不一致，M3 後審查起沒拍板）。AI 活動頁、Proposal 與 `ai_tasks` 會顯示 Job 與使用者操作，可見範圍要先定，否則 API 與 i18n 會做兩遍。
- **L07（中，settings 憑證與 DEBUG log）** M5 把 AI provider 憑證放進 `settings.ai`；目前靠「log 固定 INFO」避開 aiosqlite DEBUG 印出整份 settings JSON。M5 若加 log 等級開關或 AI 呼叫的 debug log，必須先處理（遮罩或憑證另存）。不擋拆票，擋「加 log 開關」這種小功能。
- **L05（低，rebuild_ledger 無反向命令）** `rebuild_ledger`（冪等寫入、無反向命令）屬 `REVERSIBLE` 的灰區。登錄表若沒有「冪等」這一級，AI 要不要自動跑它要在 schema 決定；可併入 L01 的設計題。
- **L09（低，迴圈關機與 ticks）** 新增 `ai_worker` 迴圈：沿用 `pipeline/ticks.py` 即可，`test_every_loop_is_here` 會逼你接上。對帳 task 關機 cancel 與「關機無總上限」不是新問題，但 AI 呼叫是網路長請求，關機等一輪的上限值得在拆票時說清楚。
- **L08（低，guessit CPU 在事件迴圈）** planner 的 guessit CPU 在事件迴圈上；M5 的「規則層 low 的 Plan → AI 任務」會多一次完整規劃或重算，量大時延遲疊加。無 repro，不擋；`ai_worker` 的呼叫量上限（預算）能緩衝。
- **L10（低，檔案列無發佈名）** 撞集的 AI 任務要「發佈名」：`LedgerFileOut` 沒有欄位；AI 工具自己讀 Job 即可，不擋。
- **L47（低，票22待確認）** 票 22 舊分類 `downloadPath` 待確認：與 M5 無關，不擋。
- **L55（低，版號與 tag 無檢查）** tag／版號一致 CI 檢查：發 M5 版本前會再手改一次，不擋。
- **L22（低，週報時區）** 週報時區：不擋；M5 若把 AI 活動併進週報再碰到。
- **L60（低，搜尋 5xx 說連不上）** 搜尋 5xx 說「連不上」：不擋；AI 任務遇到搜尋失敗時的「交給人」理由要靠它分類，可在該任務票順手做。
- **L35（低，page=1e20 回 500）** `?page=1e20` 回 500：獨立小 bug，不擋。

其餘仍未處理（41 條，**皆不擋 M5**，多為 UI 邊角、判斷題、無 repro 的競態）：L16, L18, L19, L21, L23, L24, L25, L26, L27, L28, L30, L31, L36, L38, L39, L40, L41, L42, L43, L45, L48, L49, L51, L52, L53, L64, L65, L67, L68, L69, L70, L71, L72, L73, L74, L75, L77, L78, L82, L83, L84。其中有行為缺陷且有明確位置、值得在 M5 期間順手修的：L38（`LISTED_STATES`）、L40（`_due_retries` 全量讀）、L42（`poll_due` 窗口）、L68（`RouteUsage` 漏 `default_route_id`，Route 被刪時無聲清空預設）、L24（Notice 擠壓）、L19（佇列 200 列錨點）。

## 4. progress.md 明確寫「留給 M5／M5 再做」的事項

`grep -n 'M5' docs/progress.md` 在 L15、L81、L108、L303、L304、L1081、L1223、L1282 與 L288 有命中；其中 L81、L304、L1081 是里程碑編號的重排歷史，不是待辦。真正的待辦：

| 行 | 內容 | 現況 |
| --- | --- | --- |
| L15 | M5 = AI 核心，票放在 `.scratch/m5/issues/`，讀 plan §4.5、§11.6、brief §6.10、§14 | 目錄尚不存在；拆票等使用者（L288「拆 M5 票」） |
| L288 | 拆 M5 前的全面盤點結論在對話，**待決三條：停住的三種 Job、M5 切不切、拆票時的設計題** | 第一條 = L06；其餘兩條只存在對話，不在任何檔案裡（見 §5 建議） |
| L108 | 命令副作用標記方式與閘門（票 05）；「登錄表本身仍在 M5」 | = L01–L05 |
| L303 | 命令登錄表本身在 M5（M3 拆票註記） | 同上 |
| L304 | 「從 M3 起的規矩」：新 services 命令標等級與反向命令；登錄表開頭做 | 規矩已遵守（M3 以後新模組皆有標記），豁免表未動 |
| L1223 | M3 票 11：`prime_feed` 標 `irreversible`，「M5 的 AI 不自己選」 | 已標（`rss.py:770`）；M5 只需確認 AI 工具白名單排除它 |
| L1282 | M3 後審查：plan §11.6「M3 起新增的命令先標」不準，豁免表 42 個模組、M3 加進舊模組的四支命令沒標；另 `rss.poll_due`、`rss.delete_feed` 的標記要重看，「M5 登錄表開工時處理，M4 不受影響」 | 豁免表現為 41 個模組；`poll_due`（`REVERSIBLE`，`rss.py:844-845`）與 `delete_feed`（`REVERSIBLE, inverse="rss.add_feed"`，`rss.py:670-671`）已標，但 `poll_due` 是否真的可逆（它會送單、寫 Item）仍待登錄表時重看 |
| plan §11.6（非 progress） | 登錄表開工要處理兩條（M3 票05、票17）：`confirm_audit` 反向命令；`services/issues` 逐顆標 `resolve_issue` 動作 | 前者 = L04；後者 `issues` 仍有 5 支未標（見 L01） |
| L1081 / plan §326 | `AiPlanner.propose` 無呼叫端；M5 需補：回 tokens 與費用、理由加自由文字欄、「猜作品」另一個方法 | 屬 M5 設計，非遺留；`adapters/ai.py` 尚為 `NullAiPlanner` |

## 5. 建議與未涵蓋範圍

1. 動工拆 M5 票前，把 L288 的「待決三條」從對話寫進 `docs/progress.md` 或 plan §11.6——目前只有一條（停住的三種 Job）有檔案依據，其餘兩條在 repo 裡查不到內容，違反「文件是唯一的記憶」。
2. L84 與 L71–L74 合併的約 150 條 Standards 判斷題沒逐條重驗。若要在 M5 開頭清債，建議只挑：重複常數無閘門的（`DEFAULT_FEED_INTERVAL`、`GIVE_UP_AFTER` 的 24 小時、`VERSION_FLOOR`），其餘不值得。
3. 我沒有對「後續票已處理」做行為層面實跑，只讀碼與 grep；L66、L85 引用票自述。
