# 03 — 搜尋結果

**Status:** done

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「搜尋結果」；brief §20.26（`encrypted_content` 的量）；plan §7〈側面板〉；`docs/research/assistant-feedback-2026-11-01.md`

## 為什麼

`web_search` 每筆結果帶的 `encrypted_content` 只給服務端重播用，一次 10 筆就有兩三萬字，現在原樣印在面板上。

## 做什麼

1. 串流（`_relay`）與 `GET /agent/conversations/{id}` 兩條路都在 API 層拿掉 `encrypted_content`；`history_json` 不動，下一輪模型呼叫要用。
2. 面板的工具呼叫把 `web_search` 的結果畫成清單：標題、網址、`page_age`。其他工具照舊。
3. Fake 後端的 `agent` 情境補一段 `web_search` 回應，前端 e2e 用得到。

## 驗收

- [x] 展開 `web_search` 看到標題、網址與日期（playwright 實跑，桌機與 390px）
- [x] 串流和重新載入的回應裡都沒有 `encrypted_content`（測試）
- [x] 下一輪模型呼叫的歷史仍帶 `encrypted_content`（測試）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 2026-11-04 實作：`api/agent.py` 的 `_unsealed` 拿掉伺服器端工具結果的 `encrypted_content`，`_relay` 與 `_with_stop`（`GET /agent/conversations/{id}`）兩處呼叫；重連（`/stream?turn=`）重播的是 `_relay` 送出的片段，另有一支測試守。只看 `providerExecuted` 的結果，本機工具不動。
- 「下一輪模型呼叫的歷史仍帶 `encrypted_content`」的讀法：M5 票 23d 起，下一則回覆送給模型的歷史本來就拿掉前幾輪的網搜，所以測的是**搜完緊接的那一次模型呼叫**與存著的 `history_json`（`test_the_model_still_gets_it_back`）。照字面「下一則回覆」那一次本來就沒有，與這張票無關。
- 面板：`web_search` 的結果是一串網頁才畫清單，認不得的形狀照原文印；連不連沿用助理 markdown 的 `defaultUrlTransform`。服務拒絕的搜尋（`type: web_search_tool_result_error`）算沒成功，只認這個 type，不把 `error_code` 鍵套到所有工具。空結果說「沒有搜到網頁」。
- fake `agent` 情境：問「評價」（`reviews`）時伺服器端搜一次，三筆、每筆四千字的 `encrypted_content`；e2e 在桌機與 390 都看了串流與重新載入兩次，並查所有 `/api/agent/*` 回應都沒有這個鍵。
- code-review 未處理：
  - Anthropic 的引用（citations）讓文字片段的 `providerMetadata` 帶 `encrypted_index` 與 `cited_text`，串流與重新載入都有。量小、不是 `encrypted_content`，不在這張票；要「不透明資料一概不給瀏覽器」再開票。
  - `searchResults` 寫死 `web_search`：等第二個工具也要特製畫法時再收成「工具名 → 結果元件」的表。
