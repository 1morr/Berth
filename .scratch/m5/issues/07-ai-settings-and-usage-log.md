# 07 — AI 設定與用量記錄

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** plan §11.6〈provider〉〈用量記錄〉、§2.1、§1.3；brief §6.10「用量，不設預算」、§13 設定那一列、§20 票 06 新增的一節；`docs/research/` 票 06 的結論；CONTEXT.md 的 AI Call

## 為什麼

provider 與用量記錄是側面板與背景任務共用的地基。這一張做完，管理員就能在設定頁填 key、按測試，看到第一筆用量：這是第一條端到端的路。

## 做什麼

1. **provider adapter**（`adapters/`，不 import services）：Anthropic 實作，介面保留給其他家。介面只放對話核心要的：送訊息加工具、串流回來、回報 usage。錯誤分成限流、provider 掛掉、驗證失敗。`adapters/ai.py` 裡還提「預算檢查」的 docstring 一起改掉。
2. **`settings.ai`**：憑證與模型。key 的存法、顯示（遮罩）、清除，照現有服務憑證的慣例。
3. **`ai_calls` 表**與 migration：model、輸入與輸出 tokens、快取寫入與讀取 tokens、耗時、出處（對話或 AI 任務，這張先只有「測試」）、誰。不掛在 Job 上（plan §11.6）。
4. **設定頁的 AI 一格**：填 key、選模型、「測試」打一次最小請求，成功顯示回應與這一次的 tokens，失敗說出原因（無效 key、限流、連不上）。新的一格照 CLAUDE.md 先 `/impeccable shape`，或沿用設定頁既有格的形狀並說明。
5. **沒設 key**：整個系統與 M4 相同，後面的票都靠這一條。
6. `docs/guide/` 補一段 AI 設定（英文），README 兩份照 CLAUDE.md 同步。

## 驗收

- [ ] 用假 provider 時，測試請求寫一列 `ai_calls`，欄位齊全（pytest）
- [ ] 限流、無效 key、連不上各自回出對的原因（pytest）
- [ ] 設定頁填 key、按測試、看到結果（playwright 實跑；有真 key 時附一次真的呼叫結果）
- [ ] 沒設 key 時現有測試全部照舊綠
- [ ] 全部檢查、pytest、vitest 綠；brief / plan 有被推翻的同輪改；docs/guide、CHANGELOG、progress.md 已更新
