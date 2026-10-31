# 助理側面板的五點回饋（2026-11-01）

使用者在正式環境（0.4.1，Anthropic 接口接 DeepSeek `deepseek-flash`）測助理後提的五點。本文只記查證結果與建議，**還沒有改任何程式碼**。v0.4.1 到調查時的 HEAD 之間，下面提到的程式檔沒有行為差異。

## 1. Tavily 填回之後助理說沒有

| 時間（UTC） | 事件 | 來源 |
| --- | --- | --- |
| 08:39:54 | 「重新測試」：真的叫了 2 次 `web_tavily_search` | `ai_runs`、步驟頁 |
| 08:40:30 | 「現在呢」：沒有 key，改用 `web_search` | 同上 |
| 08:40:54.8 | `settings.ai` 最後一次寫入，key 有值；WAL 裡沒有更新的版本 | `berth.db` |
| 08:41:03 | 「現在是不是有了」：助理沒有叫任何工具就說沒有 | `ai_runs` |
| 08:41:26 | 「再看看」：同上，列出 22 個工具 | `ai_runs` |

- 工具清單每則訊息重建：`open_turn` 當場讀設定（`services/agent.py` 的 `tavily = bool(settings.tavily_api_key)`），沒有快取、沒有 MCP、沒有對話層級的工具清單。
- 臨時測試跑「無 key → 填 → 清 → 填 → 再一則」，模型看到的 `web_tavily_search` 依序是 `False, True, False, True, True`，有 key 時 22 支函式工具，加上伺服器端 `web_search` 共 23 支。
- 助理當時的推理寫著「the system prompt is fixed for this conversation」「Perhaps this is a test」，說明它在堅持先前的答案。它列的 22 支與第 4 輪推理裡的清單完全相同。「要重開對話才會重新載入工具」「MCP」都是它自己編的。

**結論：幾乎可以確定是模型回報錯誤，不是工具不見。** 限制：實際送出的工具清單沒有記錄，無法從線上資料直接證明。

**建議**：不做 reload 指令，因為沒有東西可以 reload。改做：
1. `/status` 列出這一刻搜得到什麼（伺服器端 `web_search`、Tavily），答案不經過模型。
2. instructions 加一句：工具可能在兩則訊息之間變動，只以當下的清單為準，不要沿用先前的說法。
3. 每次模型呼叫記下送出的工具名，顯示在步驟頁（要 migration）。

## 2. 看不到推理文字，也不能設推理程度

- 推理文字有收到也有存：這段對話每一輪都有 `reasoning` 片段。`Conversation.tsx` 的 `Message` 只畫 text、tool 與 data，其餘丟掉。
- 程度設定完全沒有接：`chat_settings` 只給 `max_tokens` 與快取標記，`AiSettings` 也沒有這一格。
- [DeepSeek 的 Anthropic 接口](https://api-docs.deepseek.com/guides/anthropic_api)支援 `thinking`（忽略 `budget_tokens`）與 `output_config.effort`。
- 注意：pydantic-ai 的統一設定 `thinking` 要在模型 profile 有 `anthropic_supports_effort` 時才轉成 effort，`deepseek-flash` 走 Anthropic 接口時可能不會帶上。實作時要驗實際送出的內容，必要時明寫 `anthropic_effort`。

**建議**：面板把推理畫成預設收起的區塊；設定頁加「推理程度」（預設、關、低、中、高）。

## 3. 模型下拉選單

- 下拉選單來自 `known_models(base_url, provider)`，那是 **genai-prices 的本機價目表**，用**已存**的 base URL 認服務商，既不連網，也不看表單上剛打的網址。所以存之前是 Claude，存之後才是 DeepSeek。自架閘道認不出服務商，而補位表 `FALLBACK` 是空的，會完全沒有建議。
- AI 開著時模型名必填（`_require_key_and_model`），所以形成先有雞還是先有蛋。

**建議**：加 `POST /settings/ai/models`，收表單上未存的 base URL 與 key（語意同「測試連線」），打那個端點的模型清單 API，失敗退回本機表。未帶 key 時 `api.anthropic.com/v1/models`、`api.deepseek.com/anthropic/v1/models`、`api.deepseek.com/models` 都回 401，代表路由存在；帶 key 的回應內容還沒驗，查到後補進 brief §20。

## 4. 網路搜尋展開內容很長

Anthropic 格式的 `web_search` 結果每筆帶 `encrypted_content`，那是給服務端解的不透明資料，人看不懂。實測這段對話 3 次搜尋各 10 筆，JSON 分別 41,654、36,521、22,628 字，`ToolCall.tsx` 原樣印出。模型重播用的是伺服器存的歷史，不靠瀏覽器。

**建議**：串流與 `GET /agent/conversations/{id}` 兩條路都在 API 邊界拿掉 `encrypted_content`，前端把結果畫成標題、網址、日期的清單。歷史裡的不動。

## 5. 新瀏覽器沒有對話紀錄

符合目前設計：對話 id 只存在 `localStorage`（`panelState.ts`），新瀏覽器會產生新的 id；對話清單在 M5 明列為不做（`.scratch/m5/side-panel-shape.md`）。資料沒有丟，用另一個瀏覽器以同一帳號可以從 API 讀回整段 13 則。按「新對話」之後，舊對話同樣回不去。

**建議**：
1. 加 `GET /agent/conversations`（只列自己的，標題取第一則使用者訊息）。
2. 面板加清單，另加斜線指令。**指令不要叫 `/resume`**：`CONTEXT.md` 把 resume 留給 Jellyfin 的繼續觀看，建議 `/history`。
3. 新瀏覽器沒有本機 id 時，自動接這個人最近一段對話，而不是空白。
