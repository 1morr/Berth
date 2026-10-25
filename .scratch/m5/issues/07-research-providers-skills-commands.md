# 07 — 研究：兩種 provider 格式、Skill 格式與對話指令的慣例

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.6〈provider〉〈用量記錄〉〈Skill〉〈上下文管理〉〈對話指令〉與末段〈第一次嘗試的實跑發現〉；參考 `backup/m5-attempt-1-20261024` 的 `89581c1`（第一次的研究，結論要對當下的文件重查，不照抄）；brief §6.10「用量，不設預算」「外部文字是資料」、§19 2026-10-24 那一列第⑤條；CLAUDE.md〈事實與查證〉

## 為什麼

使用者要能填 Anthropic 或 OpenAI 相容格式的第三方 base URL 與 API key（OpenRouter、自架的 vLLM / Ollama、各家相容端點）。兩種格式的 SDK、tool use、串流、prompt caching 與 `usage` 欄位都不同，不能憑記憶寫（CLAUDE.md：外部服務只信 brief §20 與現查）。票 08–10、15–17 依這份結論實作。

## 做什麼

用 `mattpocock-skills:research`（以及 `claude-api` skill、context7），輸出放 `docs/research/`，結論摘進 brief §20 新的一節並附來源。**兩種格式各回答一遍**：

1. **SDK 還是直接 HTTP**：Python `anthropic` 與 `openai` SDK 當前 stable 版本、async client、自訂 base URL 的方式；還是用專案已有的 httpx 直接打。比較依賴、串流解析、錯誤型別、測試（respx）各自的代價，給一個建議。
2. **OpenAI 相容走哪一支 API**：Chat Completions 還是 Responses——第三方實際支援的是哪一支（OpenRouter、vLLM、Ollama、DeepSeek 這類常見端點各查一個）。
3. **tool use 加串流**：工具定義的格式、串流中工具呼叫怎麼一段段拼回來、平行工具呼叫、tool result 怎麼送回去。對話核心要的共同介面長什麼樣。
4. **模型**：Anthropic 目前的模型 id 與建議預設；兩種格式的「列模型」端點（設定頁的模型清單用），端點不支援時退回手填。
5. **prompt caching**：Anthropic 的 cache breakpoint 放哪、最小可快取長度、TTL；OpenAI 相容的自動快取與它的前提。兩者都要求固定的前綴，順序怎麼排才吃得到。
6. **`usage` 欄位**：輸入、輸出、快取寫入、快取讀取在兩種格式各叫什麼、串流時從哪個事件拿；第三方常缺哪幾個。缺的記成「不知道」，快取命中率在缺欄位時怎麼算或不算。
7. **錯誤**：限流、過載、驗證失敗、base URL 連不上在兩種格式的樣子與 retry-after；哪些重試、哪些交給人。
8. **怎麼知道一個端點與模型到底支不支援工具呼叫**：不支援時各自的樣子（直接 400、忽略 `tools` 只回文字、把呼叫寫成文字），有沒有能力欄位可查（例如列模型端點回的 capabilities），還是只能實際試一次。常見端點各查一個（Ollama 哪些模型支援、vLLM 要開哪個啟動選項、OpenRouter 怎麼標）。
9. 官方對 tool result 與 prompt injection 的建議（外部文字怎麼包），與 brief §6.10 對照。
10. **context window 與壓縮**：兩種格式怎麼知道一個模型的 context window（列模型端點有沒有回、要不要設定）；各家伺服器端的壓縮或 context editing（例如 Anthropic 有沒有、什麼條件）——plan §11.6 定的是自己做一套與 provider 無關的，這裡回答「伺服器端的可不可以在 Anthropic 格式下順便用、會不會和自己那套打架」，給建議。
11. **Skill 的格式**：Anthropic Agent Skills 的 `SKILL.md`（frontmatter 必要與可選欄位、名字與說明的長度限制、漸進載入的三層），OpenClaw 的 skill 格式是不是同一種、有什麼差別。給 Berth 內建 skill 的建議格式（票 15 用）。
12. **對話指令的慣例**：Claude Code 與 OpenClaw 當下的指令名稱與語意（`/compact` 帶不帶參數、`/clear` 與 `/new` 的差別、`/usage` 或 `/status` 給什麼），輸入框裡的選單怎麼呈現。給 M5 那一組的最終名單（票 16、17 用），與 plan §11.6 不同時寫進票的 Comments 等使用者拍板。

## 驗收

- [x] `docs/research/` 有一份附來源的結論，兩種格式逐條對照；brief §20 新的一節摘要並連結
- [x] 每一條都有官方文件或實測的出處，沒有憑記憶的版本號
- [x] 給出偵測「支不支援工具呼叫」的做法
- [x] 給出共同介面的草案（訊息、工具、串流事件、usage）與 SDK / httpx 的建議
- [x] 給出 context window 的取法、伺服器端壓縮的建議、`SKILL.md` 的建議格式與對話指令的名單
- [x] progress.md 已更新

## Comments

結論在 `docs/research/ai-providers.md`，摘要在 brief §20.24。

**等使用者拍板**（與 plan §11.6 或票面不同、或是取捨）：

- **對話指令**：名單與 plan §11.6 相同（`/help`、`/new`、`/compact [重點]`、`/usage`、`/skills`、`/undo`），只建議 `/new` 多一個別名 `/clear`（Claude Code 的主名；它的 `/clear` 別名有 `/new`）。`/undo` 在 Claude Code 是 `/rewind`（倒回對話與程式碼）的別名，Berth 的語意是撤銷最近一次 AI 的寫入，名字保留、`/help` 寫清楚。不收 `/status`、`/context`、`/resume`、`/stop`、`/reset`、`/cost`（理由在研究文件結論 12）。票 16 開工前定。
- **OpenAI 相容走 Chat Completions 的代價**：OpenAI 官方的 GPT-6 Astra / 6.1 Sol 在 Chat Completions 不能呼叫工具，設定頁會測成「只能聊天」。第三方（OpenRouter、vLLM、Ollama、DeepSeek）不受影響。要用這兩個模型做工具呼叫得另加 Responses adapter，建議等有人要再開票。

- **研究自己加的、plan 與票面沒寫的決定**（後面的票開工時可以推翻）：`/usage` 多報「輸入佔 context window 的比例」（把 `/context` 併進來，票 16）；保險絲④細化成「已經有輸出送到人面前的不重試」、「連不上重試一次」、「沒有 `retry-after` 的 Anthropic 429 照限流重試」（票 10、18）；`SKILL.md` 的 `description` 收緊到 ≤ 200 字元、不認得的欄位讓測試紅、沒有第三層（票 15）；context window 讀不到時預設 32k（票 17）。

**給後面的票**：

- 票 17：plan §11.6〈上下文管理〉已補三條（只在回覆邊界壓、壓縮時 Anthropic adapter 拿掉全部 thinking、之後 append-only）。票面「先把舊的工具結果換成已收起」「最近幾輪原樣保留」照做沒問題，前提是這三條；不照做的話，2026-08-31 之後建立的 Anthropic 帳號壓縮後第一個請求就 400。換掉工具結果時 `tool_use_id` 不變。
- 票 08：Anthropic adapter 建議送 `x-api-key`（官方仍支援、DeepSeek 只列它）；OpenRouter 收不收要用真 key 實測。研究文件最後一節列了要真 key 才確認得了的事，實測後補回 brief §20.24。「AI 有沒有設定」不能只看 key（自架的 Ollama / vLLM 可以沒有）。
- 票 08 / 09：context window 讀不到時用保守預設 32k，設定頁多一格選填的 context window（讀到時預填）。
- 票 08：探測工具支援是三步（不帶工具 → 帶假工具 → 把結果送回去），第三步是研究加的建議。
- 票 08：錯誤分類票面寫四種（限流、provider 掛掉、驗證失敗、連不上），研究分七種，多了**額度用完**（402、OpenAI 429 的額度類 `error.code`、Anthropic spend-cap 429——不重試）、**模型不存在**、**請求被拒 / 看不懂**；照研究結論 8 做，否則額度類會被當成限流重試。
- 票 17：驗收「快取只失效在被換掉的那一段之後」在 Anthropic 格式下要改寫——壓縮時拿掉全部 thinking，messages 段的快取從第一則帶 thinking 的回覆起失效（tools、system 照樣吃得到）。OpenAI 相容格式照原驗收。
- 票 09：DeepSeek 思考模式帶工具時要不要回送 `reasoning_content` 未查到，實測；要的話共同介面的 `OpaquePart` 也收它。

### code-review（基準 `e1ff4381`）

已改：claude-api skill 來源的三條（Opus 5.5 thinking 關不掉與 effort 預設、Sonnet 5.5 的使用者訊息位置、壓縮時丟 thinking 的代價）改引官方頁；OpenClaw 兩頁改下載 GitHub 原文逐字對過；Mythos 5.1 與「現役四個」的矛盾；「prompt is too long」在結論 8 與 10 說法統一；plan §11.6〈Skill〉〈對話指令〉的「開工時查證」改指 brief §20.24；brief §6.10 的括號限在側面板；progress 新列補結尾的 `|`；development.md 補研究文件連結；上面幾條交接。

未處理：`scripts/experiments/README.md` 開頭的票、研究文件與 brief 章節清單沒加 M5 07（清單早就停在 M3，不在這張補）；brief §20.24 逐條沒附 URL，只在段首連研究文件（研究文件逐條有出處）；`ai_sdk_mocking.py` 的 `_call_both` 兩段 try/except 重複（一次性腳本，照第一次嘗試原樣）；共同介面草案的 `OpaquePart.format` 目前只有 Anthropic 用、`ChatRequest` 與 CONTEXT.md 的 AI Call 擦邊——草案，票 08 定名字。
