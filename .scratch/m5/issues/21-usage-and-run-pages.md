# 21 — 用量頁與每輪步驟頁

**Status:** done

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

- [x] shape 文件在、實作照它
- [x] 用量頁的數字與 `ai_calls` 加總一致（測試）
- [x] 步驟頁看得到被中止那一輪的數字（實跑，附截圖）
- [x] 提醒門檻與異常提醒有測試；不會停用 AI
- [x] i18n zh-Hant 與 en；全部檢查、pytest、vitest 綠；DESIGN.md、CHANGELOG、progress.md 已更新

## Comments

- 2026-10-27 票 17 交接：網搜次數＝`ai_calls.web_searches`（伺服器端）加 `ai_tool_calls` 裡 `web.tavily_search` 的 `ok` / `warned`。**畫面要說明網搜費用**：`ai_calls.web_search_cost_usd` 是 `NULL`（`error` 為空）時是價錢不知道——只有 Anthropic 官方端點每次 $0.01，其他端點（DeepSeek 相容端點、自架閘道）搜了但沒算進 `cost_usd`；Tavily 花的是使用者 Tavily 帳號的 credit，不在估計費用裡。
- 2026-10-27 票 18 交接：`ai_runs` 多一欄 `kind`（`chat` / `compaction`，migration `e6b2d9a4c731`）。壓縮的摘要是自己的一列（`requests = 1`、一列 `ai_calls`、`continues` 永遠是 `NULL`），自動壓縮的那一列 `started_at` 比觸發它的那一輪晚。用量頁的「每輪」只數 `chat`，費用與 token 的合計要含 `compaction`（側面板的 `/usage` 就是這樣算的，`services/slash._usage`）；步驟頁要不要列壓縮由這張決定。
- 2026-10-27 票 21 完成：shape 在 `.scratch/m5/usage-and-run-shape.md`（使用者選定入口是設定分頁「用量」、提醒值在用量頁就地設、異常的中位數只算有用量的日子且至少 3 天、側面板的提醒只給管理員）。實跑截圖在本目錄（`steps-*.png`、`usage-*.png`、`stopped-in-panel-*.png`，1280 與 390；`pnpm -C web e2e` 的 `agent` 情境說「一直查」重現）。
- 2026-10-27 code-review 已修：`tally` 把知道的 0 當成不知道（加 `counted`）、命中率把不知道的快取讀當 0、正式環境分日用固定偏移（跨夏令時錯一天）、`/agent/status` 每次讀整份 30 天（改 `usage.today_alerts`）、步驟頁的名字只給管理員、費用「+未知」說出幾次、aria-label 走 i18n、`Tally.merge`、提醒值 0 的提示。
- 2026-10-27 code-review 沒處理（判斷過）：
  - ~~出錯沒有回應的呼叫在用量頁算「費用不知道」~~（2026-10-27 協調者推翻：沒有 token 就沒有花費可算，用量頁與提醒都不數它；`ai_runs.cost_usd` 的合計不變）。
  - 「新的 input」只扣掉知道的快取寫：OpenAI 相容接口不報快取寫，那部分算在新的 input 裡。
  - 壞味道留著：`RunPage` 的 `STOP_CHIP` 與 `usage/labels.ts` 的 `STOP_TEXT` 兩張表（一張是色塊、一張是說法）；`usage/alerts.ts` 的 `where` 旗標；「窄版先收起面板」的 `onClick` 在面板兩處；`api/agent.py` 從 `api/usage.py` 拿 `SpendAlertOut`。票 22 的 UI 收尾（critique / audit / polish）可以一起看。
- 2026-10-27 合併票 18（協調者）：照它的交接，用量頁的「每輪」只數 `chat`、合計含 `compaction`（測試 `TestCompactionRuns`）；步驟頁不另列壓縮。Tavily 的計數規則與 `/usage` 共用 `services.usage.tavily_searched(_sql)`。
