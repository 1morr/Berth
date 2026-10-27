# 21 — 用量頁與每輪步驟頁

**Status:** ready-for-agent

**Blocked by:** 12, 20

**讀:** plan §11.6〈分段〉第 8 段；brief §6.10（花費只提醒）、§14；`docs/research/m5-ai-direction-2026-10-27.md` C5；`docs/research/m5-prototype-2026-10-27.md`〈數字〉那一節（頁面要回答的就是這些問題）

## 為什麼

使用者決定不以總花費停用 AI，所以要看得到用了多少、哪裡在燒。每一輪的步驟頁則是除錯與信任的依據：AI 做了什麼、為什麼停。

## 做什麼

1. **先 `/impeccable shape`**：用量頁（admin）與步驟頁。
2. **用量頁**：
   - 每日 token（新的 input、快取讀、快取寫、output）、快取命中率、估計費用、網搜次數。
   - 各種防護觸發的次數、被擋下的工具呼叫數。
   - 價格未知的模型寫「未知」。
3. **步驟頁**：一輪裡每一次模型呼叫與工具呼叫，各自的 token、耗時、結果（含被擋的理由），以及停止原因。從側面板每一則回覆連得過來。
4. **花費提醒**（只提醒、不停用）：
   - 使用者自訂的每日提醒值。
   - 近 14 天日中位數 5 倍的異常提醒。
   - 出現在用量頁與側面板，不推 Discord。
5. 一般使用者看得到自己的對話步驟，看不到用量頁。

## 驗收

- [ ] shape 文件在、實作照它
- [ ] 用量頁的數字與 `ai_calls` 加總一致（測試）
- [ ] 步驟頁看得到被中止那一輪的數字（實跑，附截圖）
- [ ] 提醒門檻與異常提醒有測試；不會停用 AI
- [ ] i18n zh-Hant 與 en；全部檢查、pytest、vitest 綠；DESIGN.md、CHANGELOG、progress.md 已更新

## Comments

- 2026-10-27 票 17 交接：網搜次數＝`ai_calls.web_searches`（伺服器端）加 `ai_tool_calls` 裡 `web.tavily_search` 的 `ok` / `warned`。**畫面要說明網搜費用**：`ai_calls.web_search_cost_usd` 是 `NULL`（`error` 為空）時是價錢不知道——只有 Anthropic 官方端點每次 $0.01，其他端點（DeepSeek 相容端點、自架閘道）搜了但沒算進 `cost_usd`；Tavily 花的是使用者 Tavily 帳號的 credit，不在估計費用裡。
