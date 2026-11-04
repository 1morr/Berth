# M5.5 新番與導覽

由 plan §11.6b 細化（2026-11-03 開工 session）。plan 那一節只留標題與連到這裡的一行；程式碼裡的 §11.6b 引用指這份。

## 目標

使用者要找得到當季新番、看得出訂閱的作品有沒有按時入庫；頁首的按鈕也太多了（2026-10-31 使用者定）。這部分不需要 AI，排在 M6 前。

另外收助理側面板的五點修正（2026-11-01 使用者定，查證在 [`docs/research/assistant-feedback-2026-11-01.md`](../../docs/research/assistant-feedback-2026-11-01.md)）：模型清單與搜尋結果排在最前面先修，其餘排在新番之後。

也收審核佇列減量（2026-11-01 使用者定，查證在 [`docs/research/review-queue-2026-11-01.md`](../../docs/research/review-queue-2026-11-01.md)）：正式環境 33 件都不需要 AI。排在模型清單與搜尋結果之後、導覽之前，因為被誤擋的集數進不了 Jellyfin。

## 範圍

- **導覽收斂**（不動後端邏輯，所有網址不變：Discord 週報連 `/weekly/{id}`，`services/deeplink.py`）：
  - 主導覽：探索、新番、媒體庫、下載、待處理（只有 admin，帶數字）。外面留助理開關與帳號選單。
  - 帳號選單：設定、健康、週報（只有 admin）、語言、登出，上面寫名字與角色。Berth 第一個下拉選單；`web/` 沒有 Radix，先用原生元素（`DESIGN.md`〈Navigation〉）。
  - 待處理：頁內兩個分頁「審核」`/review`、「Issue」`/issues`，兩頁仍分開（ADR-0006）。數字照 `services.waiting.waiting_now` 的來源各歸各頁（2026-11-04 使用者定）：待處理是審核加 Issue、待綁定的 RSS Series 掛在「新番」與「訂閱」分頁，三個數加起來仍是 Discord 那個 N；文字標出、不只靠顏色；要多一支 admin 的讀取端點，新增 `/waiting` 進 `api/gate.py` 的 `ADMIN_PREFIXES`。
- **新番區塊**：導覽「新番」連 `/schedule`，分頁為時間表 `/schedule`（每個人）、追更 `/schedule/tracking`（admin）、訂閱 `/rss`（admin，原 RSS 頁）。
- **時間表**：版面照 AutoBangumi Calendar（brief §20.3）。
  - 週一到週日分欄、今天標出，手機單日清單；預設列全部（AutoBangumi 只列已訂閱，這裡要拿來找新番），可切「只看已訂閱」。
  - 卡片：海報、顯示用標題（Display Round）、第幾集、狀態（未訂閱 / 已訂閱 / 已入庫 / 晚 N 天），點進 `/media/:id` 走現有訂閱流程。一般使用者看得到狀態類別，看不到字幕組與 Feed（比照 `services/why_not.py` 的範圍）。
  - 資料：以 TMDB 為主幹（有作品 id、海報、zh-TW）。票 08 的實驗 `scripts/experiments/schedule_sources.py` 量過（brief §20.3）：這週有集的日本作品列得出 93.4% / 90.8%，過九成，主幹不換。條件 `with_genres=16`、`with_original_language=ja|zh`，`air_date` 從週一前一天到週日後一天；每部要再讀 `tv/{id}` 才知道哪一天、第幾集。
  - 放送時刻與評分是第二層：AniList 只給未來的精確時刻、Bangumi 補評分，對不上就不顯示。
  - 請求：有人打開才抓，結果存程序內 `TtlCache`（6–24 小時），不為卡片寫 `media` 列。
- **遲到判定**（純函式 `parser/overdue.py`，一部作品一個結果）：
  - 對象：有綁好的 RSS Series 的作品；第 0 季不看；季集用 TMDB 編號（帳本本來就是）。
  - 基準：作品最後入庫的一集，不分來源；還沒入庫過時，從作品最早的 RSS Series 的 `created_at` 之後播出的第一集算。
  - 缺的：基準之後已到播出日、還沒入庫的集。超過門檻就算晚，不管卡在哪一步，只有兩種例外：
    - **下載還在動**：蓋到它的 Job 在 `UNDER_WAY_STATES` 裡，但 `stalled` 不算。
    - **已經在等你處理**：蓋到它的 Job 是 `review`（已在審核佇列），或 Job 有開著或被忽略、說著它現在這個狀態的 Issue（`missing_files`、`client_error`、`client_removed`，查法同 `sweep._covered`）。那件 Issue 收掉而這一集還缺時，下一輪巡檢照常開。M6 的三種 Issue（plan §11.7）開了也走這一條。
  - 所以字幕組沒發、送單失敗、下載停滯（`stalled`）、入庫失敗（`import_failed`）都會開。`read_holdings` 的 `missing` 不帶 Job，`stalled` 又算在 `downloading`，光看它分不出來；每一集蓋到哪些 Job 用 `services/why_not.py` 的 `_job_claims` 那一份。
  - 晚：TMDB 只有日期，從播出日隔天 00:00（容器 `TZ`）起算滿門檻。門檻預設 2 天，在設定裡改；單一 RSS Series 可覆寫（`rss_series.overdue_days`，新增可為空的欄位）；一部作品多條訂閱取最大值。例：10/28 播出，10/31 05:00 巡檢才開。
  - 換輪：基準那一集與下一集播出日相隔超過 21 天，理由是 `next_run`（可能是下一個 cour，Mikan 是另一個番組，brief §20.12），不是字幕組遲到；作品上有一條比基準那一集入庫更晚建立的 RSS Series 時回到一般判定。
  - **不讀 `series_finished`**：RSS 頁的「已完結」與每日補漏照舊，安靜 30 天不影響這裡。
  - 視窗：最後一集缺集播出滿 60 天後不再提醒，留在追更頁「斷更很久」；上線第一天舊缺集也走這一條。
  - 中間的洞仍歸 `series_episodes_missing`（7 天寬限），這裡只看最新一集之後（`services/sweep.py` 的 `_missing_episodes` 不看的那一段）。
- **提醒**：新 Issue 型別 `episodes_overdue`，每日巡檢開，條件解除時系統收掉，一部作品一件（`IssueSubject` 新增作品）；`detail_json` 帶 `reason`（`late` / `next_run`）、作品名、缺的集、卡在哪（字幕組沒發、送單失敗、下載停滯、入庫失敗）。下一步：搜這一集或去訂閱（連 Media 詳情）、處理卡住的 Job（連 `/jobs/{hash}`）、忽略（條件持續期間有效）。
- **通知**：走現有的「等你處理」與「放太久」，不加通知種類，收件人同樣是訂閱了它、有 Discord ID 的管理員；週報也沿用。
  - **訊息要寫作品名與集數**：現有訊息只寫種類與數量（`notify._part`），只知道「1 個 Issue（遲到）」還得點進去。這一波有 `episodes_overdue` 時，內文列出作品名與晚的集（`describe_spans`），最多五部，其餘寫「等 N 部」；zh-Hant 與 en 並列，送出時照 `detail_json` 組字。
- **巡檢前刷新**：在巡檢的交易之前、獨立 session 刷新有綁定作品的快照。
  - 跳過：6 小時內刷新過的（`PLANNING_TTL`）、TMDB 說完結且都在庫的。量級：一部 5–7 次請求，20 部約 100–150 次，全域桶每秒 40 次。
  - **刷新失敗的作品這一輪不開也不收**：`_load` 把錯誤吞成回傳值，要看 `tmdb_fetched_at`；`_settle` 收掉「沒被標出」的件，要排除這些作品。`_store` 自己會 commit，所以不能放進 `sweep_once`。
- **追更頁**：依作品一列：字幕組、已播到、已入庫到、狀態（`domain.WhyNot` 的結論，加「晚 N 天」與「可能是下一輪」）。要人動手的在前，準時的在後，「斷更很久」收起。
  - **下載停滯要說出來**：`WhyNot` 把 `stalled` 算成 `DOWNLOADING`，這一頁要另外顯示「下載停滯」。
  - **收不到通知時頁首說一句**：這位管理員沒有 bot、沒填 Discord ID、沒訂閱「等你處理」或 Discord 到不了時，頁首提示遲到只會顯示在這裡、不會通知，連到 `/settings/notifications`；讀 `GET /me/notifications` 就夠，不加端點。不另做其他通知管道（[ADR-0015](../../docs/adr/0015-notifications-discord-dm.md)）。
- **模型清單**（先修）：按鈕才連外，不自動問（使用者定：打到一半的網址不該收到 key）。內容照 Open WebUI 連線設定的做法，向填的端點問模型，問不到就照打（brief §20.26）。
  - 模型欄旁一顆「取得模型」，按了才打 `POST /settings/ai/models`（命令 `ai.list_models`，`Effect.READ`、`CONNECTS_OUT`）：收表單上還沒存的接口、base URL 與 key。不要模型名。
  - 打 Anthropic 接口的 `{base}/v1/models`（有分頁）或 OpenAI 接口的 `{base}/models`，回 `models`、`source`（`endpoint` / `prices`）與失敗原因。問不到不算請求錯：退回本機表，並說明為什麼。
  - 沒按之前的建議：`known_models(表單的 base URL)`，要多一支只讀本機表、不帶 key、不連外的端點（或併進同一支、`key` 不送時只查本機），改網址就換。按鈕取得的清單在 base URL 或 key 改了時收掉。模型欄仍可自由輸入，AI 開著時模型名仍必填。
- **key 只送到存它的那個端點**（先修，與模型清單同一張票；三支共用一個函式，`effective_base_url` 比對，留空與填官方網址算同一個）：key 欄空著時，表單的 base URL 與存著的相同才用存著的那把，不同就是 `key_missing`。
  - `ai.list_models` 與 `ai.test_ai`：照上面。現在的「測試連線」沒有比對網址，改了網址按測試會把舊 key 送過去。
  - `ai.set_ai`：這個接口有存著的 key、網址改了、key 欄空著時拒絕，什麼都不存；只守前兩支的話，先存再按就繞過去了。
  - `settings.aiPage.test.hint` 與 key 欄的提示改說這條規則，錯誤標在 key 欄（zh-Hant、en）。
- **搜尋結果**（先修）：`web_search` 每筆的 `encrypted_content` 只給服務端用，不給瀏覽器。
  - 串流（`_relay`）與 `GET /agent/conversations/{id}` 兩條路都在 `api/agent.py` 拿掉；`history_json` 不動，模型重播要用。
  - `ToolCall` 把 `web_search` 的結果畫成清單：標題、網址、`page_age`。其他工具照舊。
- **播出日比對認得地上波先行**（brief §20.27）：改 plan §4.4 的規則一。
  - **照字面的列**容忍 `RELEASE_TOLERANCE` 加 `SIMULCAST_LEAD`（7 天，共 9 天），放行時記一條新理由 `released_ahead_of_airing`（兩個日期，zh-Hant、en）。超過 9 天照舊擋。
  - **照字面**與第一批同一個定義，抽成一支共用：`written_episode` 等於對到的集號、沒有換算類的理由、季號寫明或對到第一季。`check_airing` 因此要多收發佈名。人在 Series 上設了季號或 offset 就不算照字面。
  - **有換算的列維持兩天**：換算差一集也剛好早一週，只看日期分不開。
  - **第一批要認這個窗口**：`released_ahead_of_airing` 進 `VOUCHED`，照字面的「剛播」上緣跟著放寬。`mapping._just_aired`（推測虛擬季）不動，所以 `publishing.just_aired` 要拆成兩個窗口。
  - 還被擋的列可能仍是對的（先行超過 9 天），`released_before_airing` 與 `air_date_conflict` 的文案補一句「平台先行的核准就好」（zh-Hant、en）。票 04b 改成只對照字面、早不超過 14 天的列說（`released_far_ahead_of_airing`）；照字面更早的（`released_too_early_for_simulcast`）叫人查作品與 TMDB 的日期，有換算的叫人查季號與 offset。
- **第一批擔保收累計編號**（brief §15）：擔保的條件多一種讀法，其餘條件不變。
  - 條件：理由是 `absolute_cumulative`、季號寫明、Series 沒設季號與 offset、檔名集號剛好等於前面各季集數加對到的集號，而且那一集剛播（上緣維持兩天）。其他絕對編號與重數推測仍不擔保。
  - **閘門**：`scripts/experiments/first_batch_rule.py` 的語料與對抗輪都要擔保錯 0；不是 0 就不收這一條、回報使用者，這一項視為做完。
  - 已入庫的舊列不另外掃：下一集自動落地時，整批照 `first_batch.vouch` 一起看。已經完結、不會再有下一集的，留給人按確認。
- **升級後自動重算**：啟動時只重算 `state = review`、`plans.engine != user`、`plans.engine_version != VERSION` 的 Job，**每次啟動全部重算不做**（會蓋掉人改的列、重設等候時間，同版本結果也一樣）。
  - `review_reason = audit_undone` 的排除：人已經說過那一列不對。
  - 新命令標 `Flag.INTERNAL`，走 `REVIEW → COMPLETED`（同 `replan_job`），交給 `PlannerRunner` 背景算，不拖慢啟動；TMDB 連不上時照它現有的方式下一輪再算。
  - 算完的計劃蓋上新版本，所以同版本重啟不再重算。已入庫的不動。
- **搜尋工具查得到**：工具清單本來就是每則訊息重建，**不做 reload 指令**。
  - `/status` 多列這一刻搜得到什麼（伺服器端 `web_search`、Tavily），答案不經過模型。
  - `_instructions` 加一句：工具可能在兩則訊息之間變動，只以當下的清單為準，不沿用先前的說法。
  - `ai_calls` 新增可為空的 `tools_json`（這次呼叫送出的工具名），步驟頁顯示，舊列是「未記錄」。
- **推理**：
  - 面板把 `reasoning` 片段畫成預設收起的區塊，串流時也一樣；重新載入後仍在。
  - `AiEndpointSettings` 新增 `reasoning`（`off`、`low`、`medium`、`high`，**預設 `medium`，沒有「預設」這一級**，使用者定），兩種接口各記各的；舊資料沒有這一格就是 `medium`，不用 migration。設定頁模型欄下面一格，提示說 DeepSeek 只分低與高，中等於高（brief §20.26）。
  - 由 `chat_settings` 轉成請求參數，**只用統一的 `thinking` 不夠**（brief §20.26 實測）：Anthropic 接口上 `deepseek-flash` 的 effort 要明寫 `anthropic_effort`，`off` 要明寫 `anthropic_thinking={'type': 'disabled'}`；profile 有 `anthropic_supports_effort` 的 Claude 用統一設定。OpenAI 接口的 profile 認不得的模型不送（送了不支援的模型會 400），設定頁說明這個模型的程度沒有效果。以錄下的請求為準。
  - 服務拒絕這個參數（400）時，停下的說明指到設定頁改程度。
- **對話清單**：
  - `GET /agent/conversations`：只列自己的，新的在前，上限 50 段；回 id、標題（第一則使用者訊息，截短）、`updated_at`、有沒有在跑。不加標題欄位（沿用 `BusyElsewhere` 的做法）。
  - 面板頁首多一顆「對話」，開清單，選了走現有的 `switchTo`；在跑的那一段標出來。
  - 斜線指令 `/history`（`domain.SlashCommand`，Discord 共用）回同一份清單。**不叫 `/resume`**：`CONTEXT.md` 把 resume 留給 Jellyfin 的繼續觀看。
  - 新瀏覽器自動接上這個人最近的一段：本機沒有 id，或本機的 id 在伺服器上沒有、也不是這個瀏覽器按「新對話」開的（`localStorage` 記一個旗標，第一則訊息送出後清掉）。沒有任何對話才開空白。

## 共同規則

- **同輪要改的文件**：brief §9.1 的 Issue 表與 §13 頁面清單、plan §2.4 與 §7 路由表、`CONTEXT.md`（追更、遲到、換輪的名詞與 Issue 種數）、`DESIGN.md`〈Navigation〉與〈Layout〉；助理修正另改 plan §2.6（`ai_calls.tools_json`）、§6〈settings〉〈agent〉、§7〈側面板〉、`CONTEXT.md`（對話清單）與 brief §20.26（模型清單 API 的實測）；審核佇列減量另改 plan §3.1（`review → completed` 多一個系統觸發）、§4.4、§11.4 與 brief §15、`parser/airing.py` 與 `parser/first_batch.py` 開頭的條件說明。新頁面先 `/impeccable shape`，收尾 `critique`、`audit`、`polish`。
- 不需要 AI：關掉 AI 時整個里程碑照樣完整可用（brief §17 的 M5.5 列）。
- `services` 新增或改動的公開命令都標 `@command`；只讀的端點也走命令（`Effect.READ`）。新端點進 `api/gate.py` 時，`TestWhoEachEndpointIsFor` 補一列。
- 動 `parser/` 的票必跑 `berth bench`，`auto_wrong` 不得上升，貼數字。
- UI 文案一律走 i18n key，zh-Hant 與 en 並列；新頁面先 `/impeccable shape`（輸出 `.scratch/m5.5/<page>-shape.md`），UI 改動用 playwright 實跑、附截圖或文字結果，桌機與 390px 都看。
- 外部服務的端點與回應形狀只信 brief §20 或現查；這個里程碑實測到的（模型清單、時間表資料源）補進 brief §20 並附來源。
- 新增的資料都容得下舊列：`rss_series.overdue_days`、`ai_calls.tools_json` 是可為空的欄位，`AiEndpointSettings.reasoning` 沒有這一格就是 `medium`，都不回填。

## 驗收

- 一般使用者的頁首只有探索、新番、媒體庫、下載與帳號選單，管理員多待處理；舊網址與 Discord 週報連結都打得開（e2e，桌機與 390px）。
- 時間表列出本週當季新番，未訂閱的卡片點進作品頁訂閱成功，下一次打開變「已訂閱」。
- 訂閱的作品 10/28 播出而字幕組沒發：10/30 不開，10/31 巡檢開一件，發了入庫後系統收掉。
- 另一個字幕組或手動下載已入庫那一集時不開。
- 過了門檻的集，下載停滯或入庫失敗時開一件並說出卡在哪，入庫後系統收掉；追更頁把停滯顯示成「下載停滯」，不是「下載中」。
- 下載還在動、等審核、Job 有開著或被忽略的 Issue 時不開；那件 Issue 收掉而這一集還缺時，下一輪開。
- Discord 訊息寫出作品名與晚的集（zh-Hant、en）；超過五部時其餘寫「等 N 部」。
- 沒接 Discord 時 Issue 照開、追更頁頁首有提示；收得到通知的管理員看不到提示。
- Re:Zero fixture（E77 之後停播 56 天）開的是 `next_run`；同一輪停播 14 天仍是 `late`。
- `series_finished` 為真而 TMDB 有最近播出、未入庫的集時仍開（守「不讀」的測試）；播出超過 60 天的不開。
- 刷新失敗的作品，開著的 Issue 不被收掉、也不開新的。
- 一輪巡檢的 TMDB 請求數有上界（fake client 計數）；`/waiting`、`/schedule/tracking` 對一般使用者 403 或導向（`TestWhoEachEndpointIsFor`）。
- 播出日比對：照字面早 8 天放行並記 `released_ahead_of_airing`，早 10 天仍擋；有換算的早 7 天仍擋。正式環境那 16 列做成 fixture 全部放行。`berth bench` 的 `auto_wrong` 不升。
- 第一批：哥布林、裝備仔、野生的大魔王那種照字面先行的 Series 由系統確認；累計編號的（夜櫻 40 → S2E13）在閘門過了時由系統確認，重數推測與其他絕對編號仍要人確認。
- 升級後自動重算（整合測試）：舊版本的 `review` 重算成新版本；人改過的（`engine = user`）與 `audit_undone` 不動；同版本重啟不重算、`tmdb` 請求數為 0。
- 設定頁填 DeepSeek 的 base URL、還沒存，模型欄的建議馬上換成本機表的 DeepSeek 模型，過程沒有請求帶 key、也沒有連外；按「取得模型」後才是該端點回的模型；問不到時退回本機表並說明，仍可照打。base URL 改了之後，取得的清單不留著。
- 存著 key、把 base URL 改掉、key 欄空著：取得模型、測試連線、儲存都是 `key_missing`，fake 記不到任何帶舊 key 的請求；網址沒改時三者照常用存著的那把；留空與填官方網址算沒改。
- 展開 `web_search` 看到標題、網址與日期，串流和重新載入的回應裡都沒有 `encrypted_content`；下一輪模型呼叫的歷史不受影響。
- 清掉 Tavily key、再填回：`/status` 當場說得對，下一則訊息的工具清單跟著變，步驟頁看得到這次送出的工具名。
- 模型回推理文字時，面板收在預設收起的區塊，重新載入後還在；沒設過的設定讀回來是 `medium`；錄下的請求在 DeepSeek（Anthropic 接口）上低與高帶 `output_config.effort`、關帶 `thinking.type=disabled`；OpenAI 接口上 profile 認不得的模型不帶參數。
- 同一帳號換瀏覽器打開面板，接上最近的一段對話；「對話」清單與 `/history` 都能切回舊對話；按「新對話」後重新整理仍是空白的新對話；看不到別人的對話。

## 票序

票在 `.scratch/m5.5/issues/`，編號即建議的開工順序；依賴寫在各票的 `Blocked by`，編號在前不代表擋住後面。

| 票 | 標題 | Blocked by |
| --- | --- | --- |
| 01 | key 只送到存它的端點 | — |
| 01b | 核准卡片的整合測試偶發紅燈（協調者 2026-11-04 插） | — |
| 02 | 模型清單 | 01 |
| 03 | 搜尋結果 | — |
| 04 | 播出日比對認得地上波先行 | — |
| 05 | 第一批收累計編號 | 04 |
| 04b | 「平台先行的核准就好」只給照字面的列（使用者 2026-11-04 定，協調者插） | 05 |
| 05b | 累計編號的第一批：下一集已播就不擔保（使用者 2026-11-04 定，協調者插；06 排在它之後） | 04b |
| 06 | 升級後自動重算 | —（排在 04、05 之後，升級時才用新規則） |
| 07 | 導覽收斂 | — |
| 08 | 時間表資料源實驗 | —（可與 07 平行） |
| 09 | 時間表最小版 | 07、08 |
| 10 | 遲到判定與 `episodes_overdue` | — |
| 11 | 換輪、提醒視窗與巡檢前刷新 | 10 |
| 12 | 追更頁 | 09、11 |
| 13 | 通知寫作品名與集數 | 10 |
| 14 | 時刻與評分 | 09 |
| 15 | 搜尋工具查得到 | — |
| 16 | 面板畫推理 | — |
| 17 | 推理程度設定 | — |
| 18 | 對話清單 | — |
| 12b | 預先綁定、還沒收到任何一集的訂閱也看遲到（使用者 2026-11-04 定，協調者插） | 12 |
| 17b | 認不得的 Anthropic 相容閘道：推理「關」不送參數（使用者 2026-11-04 定，協調者插） | 17 |
| 19 | M5.5 UI 收尾 | 01–18、12b、17b |
| 20 | M5.5 驗收 | 19 |

01–03 最先做（現在每次用助理都會碰到）；04–06 接著做（被誤擋的集數進不了 Jellyfin）；07 與 08 可平行。

plan 原票序：

票序：① 模型清單 ② 搜尋結果 ③ 播出日比對認得先行 ④ 第一批收累計編號 ⑤ 升級後自動重算 ⑥ 導覽收斂 ⑦ 時間表資料源實驗 ⑧ 時間表最小版（只用 TMDB）⑨ 遲到判定與巡檢前刷新 ⑩ `episodes_overdue` 與追更頁 ⑪ 時刻與評分 ⑫ 搜尋工具查得到 ⑬ 推理 ⑭ 對話清單 ⑮ 驗收。①②最先做（現在每次用都會碰到）；③到⑤接著做（被誤擋的集數進不了 Jellyfin）；⑥與⑦可平行。

和原票序的差異（2026-11-03 使用者定）：
- 原①拆成 01 與 02：key 的防護先落地，三支命令仍共用 01 寫的那支函式。
- 原⑨⑩重切成 10–13：10 先端到端跑通最基本的遲到 Issue，11 補換輪、視窗、覆寫門檻與巡檢前刷新，12 是追更頁，13 是通知內文。
- 「新番」在 07 只給 admin、只有「訂閱」分頁；09 加上時間表後才對所有人顯示。
- 多一張 19 UI 收尾（`CLAUDE.md`〈UI〉）。
