# 17 — 推理程度設定

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「推理」；brief §20.26（DeepSeek 的推理程度、pydantic-ai 的推理）；plan §6〈settings〉；pydantic-ai 的 model settings 文件（context7 現查，版本以 `uv.lock` 為準）

## 為什麼

使用者要設得了推理程度。只用 pydantic-ai 統一的 `thinking` 不夠（brief §20.26 實測）：DeepSeek 的 Anthropic 接口會忽略 `budget_tokens`，OpenAI 接口的 profile 認不得的模型會被靜靜拿掉。

## 做什麼

1. `AiEndpointSettings` 新增 `reasoning`：`off`、`low`、`medium`、`high`，**預設 `medium`，沒有「預設」這一級**（使用者定）。兩種接口各記各的；舊資料沒有這一格就是 `medium`，不用 migration。
2. 設定頁：模型欄下面一格，提示說 DeepSeek 只分低與高，中等於高。
3. 由 `chat_settings` 轉成請求參數：
   - Anthropic 接口上 `deepseek-flash` 這類 profile 沒有 `anthropic_supports_effort` 的：程度明寫 `anthropic_effort`，`off` 明寫 `anthropic_thinking={'type': 'disabled'}`。
   - profile 有 `anthropic_supports_effort` 的 Claude 用統一設定。
   - OpenAI 接口：profile 認不得的模型不送（送了不支援的模型會 400），設定頁說明這個模型的程度沒有效果。
   - 以錄下的請求為準（測試錄 HTTP 請求本體），結果補進 brief §20.26。
4. 服務拒絕這個參數（400）時，停下的說明指到設定頁改程度。

## 驗收

- [ ] 沒設過的設定讀回來是 `medium`（測試）
- [ ] 錄下的請求：DeepSeek（Anthropic 接口）上低與高帶 `output_config.effort`、關帶 `thinking.type=disabled`；OpenAI 接口上 profile 認不得的模型不帶參數（測試）
- [ ] 400 時停下的說明連到設定頁（測試）
- [ ] 設定頁的程度欄與提示（zh-Hant、en；playwright 實跑）
- [ ] brief §20.26 補上錄下的請求；全部檢查、pytest、vitest 綠；progress.md 已更新
