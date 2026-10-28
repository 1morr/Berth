# 23b — 整季標記做進程式；多條可用 Route 時在卡片上選

**Status:** done

**Blocked by:** 23

**讀:** 票 23 的 Comments 與 `docs/research/m5-acceptance-2026-10-28.md`（真模型情境 2 的三個變體、Route 那一段）；`docs/research/fribb-vs-chaining-2026-10-28.md`〈結論〉；`berth/skills/series-mapping/SKILL.md` 第 3、8 步；`services/fribb.py`、`services/anilist.py`、`media.route_choices`；票 08、13 的 Proposal 與確認卡（`services/proposals.py`、`decide` 的 body、`web/src/agent/` 的卡片元件）；票 14 的守法（`services/agent_origins.py`）

## 為什麼

使用者 2026-10-28 決定（協調者代問）兩件事：

1. **整季標記做進程式。** 票 23 用真模型跑「整部系列」（Re:Zero、無職轉生、HUNTER×HUNTER 2011），兩種接口都只標出部分「兩種算法不一致」的季：無職轉生漏了第二季前半（實際 E01–E12，第 0 集在 Specials），Re:Zero 與 HxH 也有漏列。實驗證明規則本身對（49 個判得出的季、7 個錯全抓到、沒有誤報），是模型沒照 skill 做。比對與標記要由程式算好，模型只照抄。
2. **可用的 Route 不只一條時一律要人選，由程式強制。** 票 23 裡 Anthropic 接口在兩條電視 Route、這部作品沒有 `default_route_id`（它是「這部作品上次送單用的 Route」，第一次送單一定是空的）時沒問就選了 Anime；OpenAI 接口有問。使用者的意思是：多條可用就永遠問。做法放在確認卡上，不多聊一輪：
   - 只有一條可用：照常帶入。
   - 多條可用：那一列的 Route 是必選的下拉，只列 `media.route_choices` 給的、放得進這部作品的 Route；這部作品用過的那條預選，但仍顯示可改；沒用過就不預選；沒選齊之前確認鍵按不下去。
   - **伺服器驗證**：提出卡片時把那一列的可選 Route 清單存進 Proposal；`decide` 收每列選的 `route_id`，必須在存下的清單裡，否則 422。這放寬了票 08「參數存下後不可改」——只放寬成「Route 只能從存下的清單挑」，其餘參數照舊不可改、不收。

Mikan 訂閱回填同一字幕組同一集的繁日、簡日兩版：使用者決定**維持設計**（brief §15「全部接受、只排除」、§7.7 同一集不同 tags 並存），不在這張改。

## 做什麼

1. **系列對照工具**：新增或擴充一支讀取工具（例如 `fribb.map_franchise` 或在 `fribb.lookup_anime` 的結果裡），輸入 AniList 條目與 TMDB 作品，**伺服器端**算出每個 TV 條目的 A（Fribb）、B（照 AniList 集數串接，對 TMDB 各季集數與編號），並給每一季 `needs_review`（任一列 A、B 不一致、B 超出那一季集數、或那一季沿用連續編號）與原因。規則照 `fribb-vs-chaining` 研究與 `series-mapping` 第 3 步，`scripts/experiments/fribb_vs_chaining.py` 的判定可以抽出來共用，不要寫兩份。Fribb 不可用時只回 B，所有季標「未經對照表」。
2. `series-mapping` 的第 3 步改成「呼叫這支工具，表上照抄它的範圍與標記，不自己算」；格式閘門要過。
3. **確認卡的 Route 選擇**：照〈為什麼〉第 2 點做後端（Proposal 存每列可選清單、`decide` 驗證）與前端（卡片下拉、未選齊不能按）。`media.route_choices` 只有一條時不出下拉。API 形狀照 `gen:api` 同步。
4. 測試：
   - 對照工具：用研究的錄好的回應（`.local/experiments/cache/fribb_vs_chaining/` 可轉成 fixture）測 Re:Zero 第二季、無職轉生第二季前後半、HxH 2011 的 `needs_review`，與研究的結論一致；先改壞確認會紅。
   - 卡片：多條可用時沒選不能決定（422）、選了清單外的 Route 是 422、選了清單內的照它送；只有一條時與現在相同。vitest 守卡片下拉與按鍵停用；playwright 實跑一次多條 Route 的卡。
5. **真模型重量**：用 `scripts/experiments/m5_acceptance_scenarios.py` 的 `agent-live`，兩種接口重跑情境 2 的三個變體與一個「兩條電視 Route、作品沒有預設」的送單情境；數字與逐字稿補進 `docs/research/m5-acceptance-2026-10-28.md`（新的一節）。費用預估約 $0.1，照需要跑，不重複。
6. 文件：plan §6 / §11.6、brief §14（確認卡）、票 08 的放寬記進 progress.md「偏差與決定」；CHANGELOG。

## 驗收

- [ ] ~~對照工具在伺服器端算出整季標記，與研究結論一致（測試，改壞會紅）；`series-mapping` 照抄它~~（移到票 23c）
- [ ] ~~真模型兩種接口重跑情境 2 的三個變體：該標的季全部標出、沒有誤報（逐字稿）~~（移到票 23c）
- [x] 多條可用 Route 時卡片上必選、伺服器只收存下清單裡的 Route（測試＋playwright 截圖）；真模型的送單情境走到卡片上選 Route
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；plan、brief、CHANGELOG、progress.md 已更新
- [x] 收尾列出發版建議（版本號、CHANGELOG 段落），不發版、不 push，由協調者問使用者

## Comments

### 2026-10-28 第一個 session：Route 卡片必選做完，整季標記暫停

**協調者改順序**（session 途中）：使用者要先用真模型比較「只有網路搜尋 + TMDB」與「再加 AniList / Fribb / Bangumi」，可能拿掉那三個來源。所以**第 1、2 點（系列對照工具、`series-mapping` 第 3 步照抄）與第 5 點的情境 2 三個變體重跑暫停**，等比較結果再決定做不做。本 session 沒動那兩點（沒有半成品），研究的回應快取 `.local/experiments/cache/fribb_vs_chaining/` 在這個 worktree 與主 checkout 都已不在，之後要做的話得重錄（需要 `TMDB_API_KEY`，AniList 約 100 次、每次間隔 2.5 秒）。所以 `Status` 維持 `ready-for-agent`。

**做完的（第 3、4 點，第 5 點的送單情境，第 6 點）**：

- 後端：`proposals.propose` 對輸入有 `media_id` 與 `route_id` 的命令（送單、Mikan 與關鍵字訂閱）逐列讀 `media.route_offer`，兩條以上就把清單與預選（`default_route_id`，在清單裡才算；模型給的那一條不算）存進 `preview.routes`；`decide` 收 `routes`（與列對齊），勾著的要選的列沒選是 422 `route_required`，清單外、沒得選的列帶了值、長度不對是 422 `route_not_offered`；沒勾的列帶來的 Route 不記；`execute` 用選的蓋過存下的 `route_id`，雜湊仍比存下的那一份。新欄 `proposals.routes_json`（migration `c2f6a8d4e917`）。卡片結果給模型多 `route_chosen_on_card`。
- 前端：要選的列是必選的下拉（只列伺服器存的清單、預選上次用的），**勾著的列沒選齊時確認鍵不畫**、改說「還有 N 列沒選 Route」——票面寫「按不下去」，照 DESIGN.md「先選再確認」（按了必被拒的鍵不畫；停用的鍵接不住焦點）做成不畫，與「一列都沒勾」同一個做法。一條的照舊是文字。
- skills（`series-mapping` 第 8 步、`missing-episodes` 與 `new-season-picks` 的同一步）：不在對話裡問 Route，卡片會讓人選。
- 測試：`tests/integration/test_proposal_routes.py`（13 條：一條時不問、多條沒選 422、清單外 422、選了照它送且 `default_route_id` 跟著改、預選、沒勾的列、長度不對、拒絕不必選、三支命令都有 `media_id`/`route_id`）；變異三種（拿掉沒選就拒、拿掉清單外就拒、執行不套用選的）各紅過。`test_proposals_api.py` 的 422 形狀；`test_agent_cards.decide` 在沒說 `routes` 時選存下的那一條（那台 Berth 有兩條電視 Route）。vitest 4 條；e2e `agent` 的送單卡改成逐列選 Route 再按，驗 Job 在選的 Anime（模型給的是 TV），1280 / 390 截圖 `route-unpicked.png`、`route-picked.png`。
- 真模型 S7（兩條電視 Route、宝石の国沒送過單，兩種接口）：都沒在對話裡問、直接出卡，卡片那一列要人選（TV、Anime、無預選），約 $0.012。研究檔新的一節。

**code-review（`02993d56...HEAD`）**：已處理——下拉照 DESIGN.md〈Select〉的尺寸；「可選清單 + 上次用的」搬進 `media.route_offer`（原本 proposals 自己解析 media id、讀 Media）；前端「這一列要不要選」只判斷一次；`routeLead` 改成沒預選時也成立；沒勾的列帶來的 Route 不記（否則 `route_chosen_on_card` 會出現在沒做的列）；補三支命令的欄位守門；plan §6 黏句。未處理（判斷題）：`routes` 的「整格 `None`」與「逐列 `None`」兩種表示在 `execute`、`_routes`、`card_outcome` 各轉一次（API 形狀是 `null` = 沒選過，留著）；`route_not_offered` 也涵蓋長度不對（`selection_invalid` 是勾選的形狀，分開較清楚）；`SubmitRowBody` / `SubscribeRowBody` 各自算 fallback 名字；提出到決定之間 Route 被停用沒有專門測試（清單凍結在提出時，執行前重驗讓那一列 `refused`，與其他參數同一個機制）。

**發版建議**（不發版、不 push，由協調者問使用者）：這張的整季標記還沒做、M5 也還沒收尾，建議**不單獨發版**，併進 M5 的版本；若要先發，屬新行為加 API 欄位與 migration，照 SemVer 0.x 是 minor（例如目前版本的下一個 minor），CHANGELOG 用〈Unreleased〉→〈Changed〉那一條「作品放得進的 Route 不只一條時，確認卡上要你選」。

**驗證輸出**（code-review 修正後）：`uv run pre-commit run --all-files` 全過；`uv run pytest` 5173 passed、1 skipped、28 deselected；`pnpm -C web test` 123 files、2299 passed；`pnpm -C web e2e` 62 passed（3.6m）；`pnpm -C web gen:api` 無 diff；`alembic heads` 只有 `c2f6a8d4e917`。

### 2026-10-28 拆票與關鍵字訂閱（協調者）

- **拆票**：〈做什麼〉第 1、2 點與第 5 點的情境 2 三個變體拆到票 23c（`.scratch/m5/issues/23c-server-side-season-flags.md`，等「只有網搜 + TMDB」與「加 AniList / Fribb / Bangumi」的比較決定做或取消）。驗收的那兩條劃掉、註明移到 23c；這張只剩 Route 卡片，已做完，`Status` 改 `done`。
- **關鍵字訂閱也要問 Route**（協調者讀了收尾報告後，照使用者「多條可用就一定問」）：`rss.subscribe_search` 平常可逆、直接做，但作品放得進的 Route 不只一條、這部作品又沒有 `default_route_id` 時，改走出卡那條路（與 `term` 出自外部內容時同一條，`Turn.run_write` → `_route_unsettled`），卡上照送單卡的規則選；只有一條或有預設時照舊直接做。「命令有沒有 Route 可選」抽成 `proposals.sends_into_a_route`，出卡與 `_route_asks` 共用。測試 `test_agent_write_tools.py::TestTheRouteIsAskedOnACard`（三條：兩條沒預設出卡、沒選 422、選了照它建 Feed；有預設直接做；只有一條直接做）；變異兩種（拿掉出卡條件、不看預設）各紅過。`test_agent_injection` 的「種子名稱叫模型建關鍵字訂閱」那一條守的是直接建的路，這台 Berth 有兩條電視 Route，所以讓作品先有預設。plan §6、§11.6，brief §14，CHANGELOG 已補。
