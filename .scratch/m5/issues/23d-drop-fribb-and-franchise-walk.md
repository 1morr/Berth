# 23d — 拿掉 Fribb 與 AniList 的系列走圖；整部系列改用精簡流程

**Status:** done

**Blocked by:** 23b

**讀:** `docs/research/agent-sources-ab-2026-10-28.md`（全文，尤其〈結論〉〈補跑：另外 14 部〉與「要一起處理的」）；`scripts/experiments/agent_sources_lean_skills/series-mapping/SKILL.md`（實驗用的精簡版 skill）；`docs/research/fribb-vs-chaining-2026-10-28.md`；brief §15〈offset 建議〉、§20 的 Fribb 與 AniList 條目、§19「M5 的方向」⑥；plan §11.6 的外部資料；`berth/services/agent_tools.py`、`berth/skills/`、`tests/unit/test_skills.py`、`tests/integration/test_agent_injection*.py`；票 16、19 的 Comments

## 為什麼

使用者 2026-10-28 要程式盡量簡單、沒用的拿掉，並要求用真模型比較「精簡組（TMDB + 網路搜尋）」與「完整組（加 AniList / Fribb / Bangumi）」。結果：

- **整部系列**：17 部、49 個判得出正解的 TV 段，精簡組錯 0 段；Fribb 錯 4 段、AniList 集數串接錯 3 段（無職轉生第二季前半兩者同源一起錯，整季標記也救不了）。精簡組沒有一處比 Fribb 差。
- **新番推薦**：精簡組不穩（評分人數 5/5、2/5、2/5、0/5，有一次列錯季），完整組穩定。

使用者決定：**拿掉 Fribb 與 `anilist.search_anime`、`anilist.read_franchise`；留 `anilist.read_season` 與 Bangumi 放送表**（新番推薦用）。票 23c 取消。

## 做什麼

1. **拿掉**：`adapters/fribb`、`services/fribb.py`、`fribb.lookup_anime`；`anilist.search_anime`、`anilist.read_franchise`（只留 `read_season` 與它要的 adapter 部分）；工具清單、skills 的 `tools`、`PENDING`、`toolNames.ts`、i18n、Fake 後端與 fixture 裡沒人用的部分一起刪；`CONFIG_ROOT/cache/fribb` 的下載與每週更新拿掉。沒有呼叫端的介面連同守它的測試一起刪。
2. **`series-mapping` 換成精簡版**（從實驗那份來，但改成產品用語），並補強研究指出的三條：
   - 有第 0 集、.5 集或總集篇落在 Specials 時，那一季**一定**整季標「請確認」（主實驗漏過一次）。
   - **沒有網路搜尋時**（OpenAI 相容接口沒填 Tavily key）：改用 `media_read_media` 的 TMDB 各集播出日，以播出空檔切出各段，每一季都標「沒有網頁核對，請確認」；**不准憑記憶給範圍而不說**（奇諾之旅兩次沒搜就憑記憶）。
   - 搜不到網頁時也照上一條。
3. **上下文**：長系列在找種子那一輪撞過每輪 token 上限（Re:Zero）。限制網搜結果進上下文的摘錄長度，或在找種子那一輪前先壓縮；二擇一，寫理由。
4. **AI 設定頁**：選 OpenAI 相容接口而沒填 Tavily key 時，提示「整部系列與評價需要網路搜尋，建議填 Tavily key」。
5. **brief §15〈offset 建議〉改寫**：不再靠 Fribb / AniList，改用「Mikan 番組頁的開播日 → TMDB 同一天播出的那一集（±1 天）= 起始集，offset = 那一集 − 1」（這就是 `fribb-vs-chaining` 研究算正解的方法，49 段沒錯過）；只 Mikan 來源有開播日，其他來源照現在由第一批確認擋；其餘（只給建議值、一鍵套用、先量 benchmark、看第一批改正頻率決定是否排 M6）照舊。brief §20 的 Fribb 條目註明「M5 票 23d 拿掉，研究見 …」，§19 ⑥ 與 plan §11.6 同步。
6. 注入測試：AniList 標題入口保留（`read_season` 還在）；刪掉的工具從「每個讀取工具都叫一遍」的表移除；`test_injection_claims` 照常過。
7. **真模型確認**：用 `scripts/experiments/agent_sources_ab.py` 跑「產品現在的樣子」（就是精簡組）：Re:Zero、無職轉生、HxH 2011 × 兩種接口 × 1 次；另外 OpenAI 接口**不開 Tavily** 再跑這三部 1 次，看沒有網搜時是否整季標記而不憑記憶。只到清單即可，預算上限 $0.3。實驗用的 `agent-live-lean` 情境與精簡 skill 副本，在產品換成精簡版之後拿掉或併回，寫明理由。

## 驗收

- [x] Fribb 與 `anilist.search_anime` / `read_franchise` 從程式、工具、skills、Fake 後端、文件拿乾淨；`read_season` 與 Bangumi 照舊（測試）
- [x] `series-mapping` 精簡版含三條補強；有網搜時三部全對、該標的全標；沒網搜時每季都標「沒有網頁核對」、不憑記憶給範圍而不說（真模型逐字稿）
- [x] 長系列找種子那一輪不再撞每輪 token 上限（測試或實跑）
- [x] AI 設定頁的 Tavily 提示（vitest；playwright 截圖）
- [x] brief §15〈offset 建議〉改成 Mikan 開播日的做法；brief §19、§20 與 plan 同步
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；CHANGELOG、progress.md 已更新
- [x] 收尾列出發版建議（版本號、CHANGELOG 段落），不發版、不 push

## Comments

- **第 3 點選「找種子那一輪前先壓縮」，做法是拿掉前幾輪的伺服器端網搜**（`compaction.without_earlier_searches`，`agent._DropEarlierSearches`）。理由：撞上限的兩次都是 Anthropic 接口，網搜只有 1 次，而同一題 OpenAI 接口（Tavily 搜 2.5 次）的 input 少了約 28 萬；Anthropic 的 `web_search` 回的是整頁加密內容，Berth 截不短，「限制摘錄長度」只管得到 Tavily（它已截在 1000 字）。拿掉的是**送給模型的那一份**、不動存著的歷史：加密內容 Berth 本來就比對不了，存著的照留，`external_texts` 不受影響；那幾頁讀到的已寫進那一輪的回答。不用既有的摘要壓縮：它保留最後兩輪，第二輪時第一輪原封不動，而且多一次模型呼叫。同一輪的搜尋照留。
- **沒有網搜時的切段要 TMDB 各集播出日，`media.read_media` 給模型的那一份原本把逐集換成「狀態 → 集數範圍」、日期丟了**：補 `aired_blocks`（相鄰兩集隔超過 28 天就算另一段，`agent_tools.AIRING_GAP_DAYS`；一季裡停播一兩週不斷開）。
- **真模型確認**（$0.121，研究 `docs/research/agent-sources-ab-2026-10-28.md`〈票 23d〉、逐字稿 `t23d-*.md`）：有網搜時三部 × 兩種接口範圍全對；OpenAI + Tavily 的 HxH 第一次 S1 漏標（貪婪之島跨 S01–S02），skill 補「一段跨兩季兩季都標」後重跑三季全標（逐字稿 `t23d-openai-hxh2011-before.md` / `t23d-openai-hxh2011.md`）。沒有網搜時三部每季都標「沒有網頁核對」，Re:Zero 明說季名憑記憶。
- **長系列找種子那一輪**：照票面只跑到清單，沒有真模型量；由 `test_agent_web_search.py::TestEarlierSearchesLeaveTheContext` 與 `test_compaction.py::TestEarlierSearches` 守。清單那一輪的數字支持判斷：Anthropic 接口 Re:Zero 搜 1 次、5 次呼叫吃 245,821 input。
- **AI 設定頁 playwright 實跑**（fake 後端 `healthy`，以 `skipper` 登入、選 OpenAI 相容）：Tavily 欄下讀回「OpenAI 相容接口沒有自己的網路搜尋。整部系列與評價需要網路搜尋，建議填 Tavily key；沒有的話，整部系列的每一季都會標「請確認」。」1280 與 390 截圖都看過（`.playwright-mcp/`，不進 repo）。
- **code-review 未處理的發現**：
  - `_aired_blocks` 與 `_compact_season` 各自過濾一次同一批集（判斷題，留著：合在一起反而讓 `_compact_season` 多管一件事）。
  - 已存 Tavily key、在同一頁按「移除」之後，提示要重新整理才出現（影響小）。
  - skill 裡「matched by title, please check」只寫英文、另兩種標記有中文（票 16 留下的寫法，模型照使用者語言翻，這次實跑都翻對）。
  - `scripts/experiments/fribb_vs_chaining.py` 的說明還指著已刪的 `services/anilist.read_franchise`（保留的歷史實驗，不改）。
  - skill 那句「TMDB moved one of that part's episodes to specials」是 review 後收窄的寫法（原本「任何一集在 specials」讓 OpenAI 對 Re:Zero 誤標），改後沒有重跑真模型。
- **發版建議**（不發版、不 push）：`v0.4.0`。最近的 tag 是 `v0.3.0`，`[Unreleased]` 收的是 M5 整個 AI 側面板（新功能、加了 AI 設定），照 SemVer 0.x 升 minor。CHANGELOG 把 `## [Unreleased]` 那一段原樣改成 `## [0.4.0] - <發版日>`，其中「助理會推薦新番、整理整部系列（M5 票 16、23d）」那一條已是拿掉 Fribb 之後的寫法。
