# 07 — 研究：兩種 provider 格式、Skill 格式與對話指令的慣例

**Status:** ready-for-agent

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

- [ ] `docs/research/` 有一份附來源的結論，兩種格式逐條對照；brief §20 新的一節摘要並連結
- [ ] 每一條都有官方文件或實測的出處，沒有憑記憶的版本號
- [ ] 給出偵測「支不支援工具呼叫」的做法
- [ ] 給出共同介面的草案（訊息、工具、串流事件、usage）與 SDK / httpx 的建議
- [ ] 給出 context window 的取法、伺服器端壓縮的建議、`SKILL.md` 的建議格式與對話指令的名單
- [ ] progress.md 已更新
