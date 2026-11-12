# 02 — `download` skill：只要列清單時不搜種子

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** spec〈範圍〉M5.6 遺留第 2 點、〈共同規則〉；`docs/research/agent-slimming-2026-11-06.md` §7、§8（數字與品質）；brief §14〈skills 只寫決策順序〉

## 為什麼

M5.6 收斂 skills 之後，`download` skill 第 4 步要模型「一次一季用 `scope.missing` 搜、再用 `contains` 列一個字幕組」。模型照做的結果是：只要列清單的 S2-mushoku 也先搜了 20 次種子（基準 0），S2 為了湊齊 E01–E85 用了十幾次 `contains`（基準 6／7）。品質沒變差，但這是白花的工具呼叫。

## 做什麼

1. 改寫 `download` skill 第 4 步：使用者只要清單時不搜種子；要下載時一季先搜一次、需要時才用 `contains` 縮小。共同規則（「只在使用者要下載或問有什麼時才搜種子」）已在系統指示，skill 不重述。
2. **一般使用者拿回 `recommend`**（2026-11-12 M5.6 回顧，使用者同意）：M5.6 票 07 讓 `recommend` 宣告了 `rss.list_subscriptions`，`skills_for(Role.USER)` 因此只剩 `download`。改成不宣告這支工具（「有這支工具時才查有沒有訂過」寫在 skill 裡），一般使用者與管理員都看得到 `recommend`；`test_skills.py` 加一條守它。
3. 守住 `test_skills.py` 的預算（三份合計 ≤ 80 行），不點名作品。
4. 用真模型重跑 S2 與 S2-mushoku（兩種接口），和基準、M5.6 改後並列；品質照 M5 驗收逐項檢查，S2 的範圍標記不能變差。數字與結論寫進研究文檔新的一節。

## 驗收

- [ ] S2-mushoku 兩種接口都沒有種子搜尋
- [ ] S2 的種子搜尋與 `contains` 次數不比 M5.6 改後多，品質不比基準差；數字在研究文檔
- [ ] 一般使用者的 `skills_for` 有 `recommend`（`test_skills.py`）；CHANGELOG 記一條
- [ ] `test_skills.py` 綠
- [ ] 全部檢查、pytest 綠

## Comments
