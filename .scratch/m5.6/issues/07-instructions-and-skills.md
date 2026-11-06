# 07 — 共同規則進系統指示，skills 5 → 3

**Status:** ready-for-agent

**Blocked by:** 04、05、06

**讀:** spec〈範圍〉B1–B4、〈共同規則〉；研究文檔 §2、§3、§4 B（草稿都在那裡）；brief §14（skills）；plan §6〈agent〉

## 為什麼

5 個 skill 加起來 351 行，同一段話重複出現 3–4 次（搜尋語言、Route、卡片的說法、重建帳本、`in_jellyfin` 的意思），而且點名了特定作品。照分層原則重新分配：共同規則寫一次在系統指示，skill 只寫決策順序。

## 做什麼

1. **B1、B4**：研究文檔 §4 B1 的草稿加進 `services/agent.py` 的 `INSTRUCTIONS`（英文），其中包含「只在使用者要下載或問有什麼時才搜種子」這一條。
2. **B2**：`download`（取代 `missing-episodes`、`series-mapping` 與 `new-season-picks` 第 8 步，≤ 30 行）、`recommend`（取代 `new-season-picks`，≤ 20 行）。`subscribe` 先只刪掉已經進系統指示的段落與 Route 段落，改寫留給票 09。照研究文檔的草稿寫，依 04–06 的結果調整（`contains`、`episodes`、沒有 Route）。
3. `why-not-imported` 不再是 skill：結論的意思，以及「唯讀、先說結論、最後給下一步」，寫進 `why_not.explain` 的工具說明。
4. **重建帳本的指引只留一處**：`media.read_media` 給模型的輸出在 `in_jellyfin` 佔一整季以上時帶一個 `hint`（格式在這張票定，寫進 Comments 與 plan §6）。skill 與系統指示都不再寫。
5. **B3**：skill 不點名作品，只寫通則。
6. **閘門**：`test_skills.py` 加上 skill 總行數上限（≤ 80，加上票 09 要寫的 `subscribe`），並做雙向變異驗證（超過上限會紅、改格式不會紅）。
7. `m5_acceptance_scenarios.py` 的 `MISMATCH` 依賴舊 skill 的字樣（「未經核對」），改成新 skill 會讓模型說出的字樣，或改用不依賴措辭的判斷。
8. 文件：brief §14 的 skills 清單、plan §6〈agent〉。

## 驗收

- [ ] `berth/skills/` 只剩 `download`、`subscribe`、`recommend`；`download` ≤ 30 行、`recommend` ≤ 20 行
- [ ] 系統指示包含 B1 的四條；skill 裡沒有那四條的重述，也沒有點名作品
- [ ] `why_not.explain` 的說明寫出各結論的意思；`read_media` 在 `in_jellyfin` 佔滿一季時帶 `hint`（測試）
- [ ] `test_skills.py` 的總行數閘門通過雙向變異驗證
- [ ] 驗收腳本不再依賴舊 skill 的字樣
- [ ] brief §14、plan §6 已改；全部檢查、pytest 綠；progress.md 已更新

## Comments
