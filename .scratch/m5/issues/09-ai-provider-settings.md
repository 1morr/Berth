# 09 — AI provider 設定

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** plan §11.6〈已定〉的 provider 那一條、〈分段〉第 4 段；brief §14〈provider〉、§20.24 的 provider 那幾條；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R13、R15、C5 的價目表；`scripts/experiments/m5_agent_chat.py` 的 `build_model`、`PRICES`；`berth/models/setting.py`；設定頁現有的分頁（`web/src/settings/`）

## 為什麼

M5 的一切都要先有一個模型可以叫。使用者決定兩種接口都做，各自設 base URL 與 key（brief §19「M5 的方向」⑧）。設定存在資料庫，跟 TMDB key 一樣，不從環境變數讀。

## 做什麼

1. **相依**：
   - 後端：`pydantic-ai-slim[anthropic,openai,ui]`，釘當前的 stable。它帶進 `httpx2`，確認與既有的 `httpx` 並存沒有問題。
   - 版本相關的寫法照 brief §20.24 與 context7，不憑記憶。
2. **`settings.ai`**：
   - provider 種類（`anthropic` / `openai`）、base URL、key、模型名。
   - Tavily key（選填，票 17 用）。
   - 開關：關掉 = 沒有 AI。
3. **adapter**：依設定組出模型物件（`adapters/ai/`）。
   - Anthropic 的 base URL 不含 `/v1`；OpenAI 相容的照那家服務的文件。
   - 價目表附查證日期；認不得的模型費用是 NULL，畫面寫「未知」，不當 0。
4. **設定頁的 AI 分頁**（admin）：先 `/impeccable shape`，再實作。
   - 填完按「測試連線」打一次最小呼叫，說出成功或服務回的原文。
   - key 只寫不讀：API 回 `has_key`，不回原值。
5. **key 不進 log**（R13）：補一條會紅的測試，DEBUG 也不會印出整份 settings 裡的 key。
6. **刪掉沒有呼叫端的 `AiPlanner` / `NullAiPlanner`**（R15）與守它的測試；M6 重設計，plan §4.5 已改。

## 驗收

- [ ] 兩種 provider 都組得出模型；Anthropic 與 OpenAI 相容的 base URL 各有測試（用假的 transport，不打網路）
- [ ] 測試連線的成功與失敗都說得出原因（測試＋playwright 實跑，附截圖）
- [ ] key 不出現在 API 回應與 log（測試）
- [ ] `adapters/ai.py` 的舊介面刪掉
- [ ] `.env.example` 不加任何 AI 變數（產品不讀環境變數）；i18n zh-Hant 與 en
- [ ] 全部檢查、pytest、vitest 綠；plan §2、§8 補；CHANGELOG、progress.md 已更新

## Comments
