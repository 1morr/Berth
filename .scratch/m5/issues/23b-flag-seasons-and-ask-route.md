# 23b — 整季標記做進程式；多條可用 Route 時在卡片上選

**Status:** ready-for-agent

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

- [ ] 對照工具在伺服器端算出整季標記，與研究結論一致（測試，改壞會紅）；`series-mapping` 照抄它
- [ ] 真模型兩種接口重跑情境 2 的三個變體：該標的季全部標出、沒有誤報（逐字稿）
- [ ] 多條可用 Route 時卡片上必選、伺服器只收存下清單裡的 Route（測試＋playwright 截圖）；真模型的送單情境走到卡片上選 Route
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；plan、brief、CHANGELOG、progress.md 已更新
- [ ] 收尾列出發版建議（版本號、CHANGELOG 段落），不發版、不 push，由協調者問使用者

## Comments
