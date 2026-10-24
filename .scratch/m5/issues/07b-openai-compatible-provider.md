# 07b — OpenAI 相容格式的 provider

**Status:** done

**Blocked by:** 07

**讀:** plan §11.6〈provider〉〈用量記錄〉；brief §19 2026-10-24 第⑤條、§20 票 06 新增的一節；`docs/research/` 票 06 的結論；票 07 定下的 provider 介面

## 為什麼

使用者要能填 OpenAI 相容格式的第三方端點（OpenRouter、自架的 vLLM / Ollama、各家相容端點）。票 07 的介面已經定好，這張只加一個 adapter，並讓設定頁選得到它。不擋 08：側面板用哪一種格式都一樣。

## 做什麼

1. **OpenAI 相容的 adapter**：走票 06 建議的那一支 API；把工具定義、串流中的工具呼叫、tool result 轉成票 07 的共同型別。
2. **usage**：輸入、輸出、快取讀取照實記；格式沒有快取寫入、或第三方沒回的，記成「不知道」。
3. **設定頁**：格式多一個選項；模型清單從端點的列模型端點拿，拿不到退回手填。
4. **錯誤**：限流、驗證失敗、連不上、模型不存在照票 07 的分法；第三方回出非標準錯誤時，有安全的退路（說「端點回了看不懂的錯誤」並記下原文）。
5. **工具呼叫偵測**：沿用票 07 的「測試順便試一次工具呼叫」。OpenAI 相容的第三方最常不支援（Ollama 的部分模型、沒開工具選項的 vLLM），三種不支援的樣子（400、忽略 `tools`、把呼叫寫成文字）都要判成「不支援」，不能誤判成功。
6. `docs/guide/` 的 AI 設定段補上 OpenAI 相容的填法與幾個常見端點的例子，含各自怎麼開工具呼叫。

## 驗收

- [x] 用假端點（respx）：一般回覆、串流、工具呼叫一來一回都轉得對（pytest）
- [x] 回 400、忽略 `tools`、把呼叫寫成文字三種假端點都判成「不支援工具呼叫」（pytest）
- [x] 沒回快取欄位、沒有列模型端點、回非標準錯誤，三種情況都不壞（pytest）
- [x] 設定頁切到 OpenAI 相容、按測試成功（playwright；有第三方端點時附一次真的呼叫）——沒有第三方端點，真的呼叫沒做（Comments）
- [x] 票 08 之後的測試若已存在，用兩種格式的假端點都跑得過——票 08 還沒做，不適用
- [x] 全部檢查、pytest、vitest 綠；docs/guide、CHANGELOG、progress.md 已更新

## Comments

- 2026-10-24 實作（session 紀錄在 progress.md）。**playwright 實跑**（`scripts/fake_setup_server.py --scenario healthy --port 8497`，新的 `/demo/openai/v1` 假端點走真的 `OpenAiProvider` 與真的 HTTP）：格式選「OpenAI 相容（Chat Completions）」後 base URL 的 placeholder 換成 `https://api.openai.com/v1`、說明換成含 `/v1` 的例子、模型說明換成「這個端點沒有預設模型」；填 `http://127.0.0.1:8497/demo/openai/v1`、不填 key 儲存，讀模型清單「讀到 2 個模型」；模型 `demo-gpt` 儲存並測試：連得上、「模型回的話：ok」、「支援工具呼叫。」、三列 tokens 都是 31 / 5 / 不知道 / 0；換 `demo-chat-only`：「只能聊天。」「端點忽略了工具，模型只回了文字。」。console 只有登入前 `/api/auth/me` 的兩個 401。
- **沒有真 key、也沒有第三方端點**：驗收的「附一次真的呼叫」沒做。有端點時用 `BERTH_AI_REAL=1` 實測 brief §20.24「票 07b 實作時定的」標未實測的幾條（官方 OpenAI 不送 `reasoning_effort` 時的工具呼叫、探針 256 tokens 對推理模型夠不夠、`prompt_tokens` 含不含快取讀取），以及研究最後一節第 5 條。
- **API 欄位 `default_model` 換成 `official_models`**（每一種格式的官方預設）：設定頁要照草稿裡的格式說「留空用哪一個」。這支 API 只有 Berth 自己的畫面在用、而且是同一天票 07 才加、還沒發版，所以沒有另外問、也沒有留舊欄位；CHANGELOG 寫了。
- code-review 處理了的：「忽略工具」被誤標成「寫成文字」（探針改看呼叫的形狀，兩種格式共用，brief §20.24）、串流中途字串型的限流 code、錯誤原文進 log、`is_error` 丟掉的註解、拼到一半的呼叫改成 `_PendingCall`、`_int` 共用、`formats.official_models()`、兩個逾時常數搬進 `wire.py`。
- code-review 沒處理、判斷題：
  - 兩個 adapter 的 `stream()` 錯誤包裝（`opened` 旗標、`ServiceError` → 掛掉 / 連不上、補 usage）仍各一份：差在 SSE 的讀法與結束條件，抽出來要多一層 callback，等第三種格式再說。
  - `_classify(status=None)` 表示「串流中途」：只有兩個呼叫端，拆兩個入口不划算。
  - OpenRouter 的 403 也用在預算上限與 guardrail，照狀態碼歸「憑證不對」；`_says_model` 只看訊息有沒有 model 這個字；`id` 比名字晚到時 `ToolCallStarted` 的 id 是 `call_{index}`（OpenAI 規格第一片同時帶 id 與名字）。有真端點看到再改。
  - 研究文件結論 4 的 Ollama 連結寫成 `search?c=tool`，正確的是 `c=tools`（頁面標題「Tools models」）；guide 用的是對的，研究文件是當時的紀錄、沒改。
