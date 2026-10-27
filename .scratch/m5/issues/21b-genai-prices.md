# 21b — 費用估算改用 genai-prices（依網址與模型名查價）

**Status:** ready-for-agent

**Blocked by:** 21

**讀:** plan §8 的 `adapters/ai/prices.py` 那一條、§2 的 `ai_calls` / `ai_runs`、§11.6〈已定〉的價目那一條；brief §6.10、§20.24（`ModelResponse.cost()` 那一條）；`berth/adapters/ai/prices.py`、`berth/services/ai.py` 的 `price_of` 呼叫端；票 09、17、21 的 Comments（價目只看模型名、非官方端點網搜費用）；pydantic-ai 的 `_genai_prices.py`（`iter_provider_references`、`fill_response_cost`）

## 為什麼

使用者 2026-10-27 決定（協調者代問）：價目改用 Pydantic 維護的 `genai-prices`。它已經是 pydantic-ai 的相依（uv.lock 0.1.13），先依 **base URL** 認出服務商、再查模型名，所以「Anthropic 接口 + DeepSeek 端點」會套 DeepSeek 的價，而現在的手寫表只看模型名。

協調者在 0.1.13 實測（`calc_price`）：
- `provider_api_url=https://api.deepseek.com/anthropic`、`model_ref=deepseek-flash`、不指定 provider → 認成 `deepseek / deepseek-flash`，100 萬 input + 100 萬 output = $0.75。
- 指定 `provider_id=anthropic` 時同一組查不到（`LookupError`）：**不能把接口種類當 provider_id 傳**，要讓網址決定。
- `anthropic` + `https://api.anthropic.com` + `claude-sonnet-5-5` 查得到。

這推翻 plan §8「不用 `genai_prices` 補位」與 brief §20.24「不認得的模型要有自己的價目表」的寫法：改成 genai-prices 為主、Berth 的表只補它認不得的模型。

## 做什麼

1. **相依**：`genai-prices` 直接列進 `pyproject.toml`（現在是間接相依），版本與 uv.lock 一致；確認與 pydantic-ai 要求的範圍相容。
2. **查價**：`adapters/ai/prices.py` 改成先問 genai-prices（帶 base URL 與模型名，照 pydantic-ai 的 `iter_provider_references` 由具體到一般），查不到再看 Berth 自己的補位表，再查不到是 `None`（費用 NULL、畫面「未知」，不當 0）。四個價（輸入、輸出、快取讀、快取寫）照 genai-prices 的 `calc_price` 結果算，不自己乘。
3. **不在執行時連網更新價目**：genai-prices 的自動更新（從 GitHub 抓新資料）關掉，價目跟著套件版本走；寫一條測試證明查價不發任何網路請求。
4. **來源標示**：原本的「查證日期」改成「價目來源：genai-prices <版本>」或「Berth 補位表（查證日期）」，用量頁與設定頁照這個顯示（票 21 的頁尾說明一起改）。
5. **既有的 `ai_calls.cost_usd` 不回填**：只影響之後的呼叫；progress.md 記一行。
6. 文件：plan §8、§11.6、brief §20.24 改寫並附來源（genai-prices 的 GitHub 與版本）；progress.md「偏差與決定」記這次推翻；CHANGELOG。

## 驗收

- [ ] DeepSeek 的 Anthropic 相容端點 + `deepseek-flash` 算得出費用，與 genai-prices 的結果一致（測試，不打網路）
- [ ] Anthropic 官方、OpenAI 官方各一個模型算得出費用；genai-prices 與補位表都不認得的模型是 `None`，畫面「未知」（測試）
- [ ] 查價過程不發網路請求（測試）
- [ ] 用量頁與 AI 設定頁的價目來源說明正確（vitest；playwright 實跑附截圖）
- [ ] 全部檢查、pytest、vitest 綠；`pnpm -C web gen:api` 無 diff；plan、brief、CHANGELOG、progress.md 已更新

## Comments
