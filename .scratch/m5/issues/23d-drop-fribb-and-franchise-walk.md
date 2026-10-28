# 23d — 拿掉 Fribb 與 AniList 的系列走圖；整部系列改用精簡流程

**Status:** ready-for-agent

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

- [ ] Fribb 與 `anilist.search_anime` / `read_franchise` 從程式、工具、skills、Fake 後端、文件拿乾淨；`read_season` 與 Bangumi 照舊（測試）
- [ ] `series-mapping` 精簡版含三條補強；有網搜時三部全對、該標的全標；沒網搜時每季都標「沒有網頁核對」、不憑記憶給範圍而不說（真模型逐字稿）
- [ ] 長系列找種子那一輪不再撞每輪 token 上限（測試或實跑）
- [ ] AI 設定頁的 Tavily 提示（vitest；playwright 截圖）
- [ ] brief §15〈offset 建議〉改成 Mikan 開播日的做法；brief §19、§20 與 plan 同步
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；CHANGELOG、progress.md 已更新
- [ ] 收尾列出發版建議（版本號、CHANGELOG 段落），不發版、不 push

## Comments
