# 07 — AI 設定與用量記錄（Anthropic 格式）

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** plan §11.6〈provider〉〈用量記錄〉、§2.1、§1.3；brief §6.10「用量，不設預算」、§13 設定那一列、§19 2026-10-24 第⑤條、§20 票 06 新增的一節；`docs/research/` 票 06 的結論；CONTEXT.md 的 AI Call

## 為什麼

provider 與用量記錄是側面板與背景任務共用的地基。這一張先做 Anthropic 格式，連同設定與 `ai_calls` 端到端跑通：管理員在設定頁填 base URL 與 key、按測試，看到第一筆用量。OpenAI 相容格式在 07b，接在同一個介面上。

## 做什麼

1. **provider 介面**（照票 06 的草案）：對話核心只看 Berth 自己的型別——訊息、工具、串流事件、usage（缺的欄位是「不知道」，不是 0）、錯誤分成限流、provider 掛掉、驗證失敗、連不上。介面放在 `adapters/` 這一側，不 import services。`adapters/ai.py` 裡還提「預算檢查」的 docstring 一起改掉。
2. **Anthropic 格式的 adapter**：支援自訂 base URL（留空用官方）。
3. **`settings.ai`**：格式（這張只開 Anthropic，07b 加 OpenAI 相容）、base URL、API key、模型。key 的存法、顯示（遮罩）、清除，照現有服務憑證的慣例。模型可從端點的模型清單挑，也可手填。
4. **`ai_calls` 表**與 migration：格式、base URL 的主機、model、輸入與輸出 tokens、快取寫入與讀取 tokens（可為「不知道」）、耗時、出處（對話或 AI 任務，這張先只有「測試」）、誰。不掛在 Job 上（plan §11.6）。
5. **設定頁的 AI 一格**：選格式、填 base URL 與 key、選或填模型，「測試」打一次最小請求，成功顯示回應與這一次的 tokens，失敗說出原因（無效 key、限流、連不上、模型不存在）。新的一格照 CLAUDE.md 先 `/impeccable shape`，或沿用設定頁既有格的形狀並說明。
6. **沒設 key**：整個系統與 M4 相同，後面的票都靠這一條。
7. `docs/guide/` 補一段 AI 設定（英文），README 兩份照 CLAUDE.md 同步。

## 驗收

- [ ] 用假端點（respx）：測試請求寫一列 `ai_calls`，欄位齊全；端點沒回快取欄位時記成「不知道」（pytest）
- [ ] 自訂 base URL 生效：請求打到填的主機（pytest）
- [ ] 限流、無效 key、連不上、模型不存在各自回出對的原因（pytest）
- [ ] 設定頁填 key、按測試、看到結果（playwright 實跑；有真 key 時附一次真的呼叫結果）
- [ ] 沒設 key 時現有測試全部照舊綠
- [ ] 全部檢查、pytest、vitest 綠；brief / plan 有被推翻的同輪改；docs/guide、CHANGELOG、progress.md 已更新
