# 02 — 模型清單

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** spec〈範圍〉「模型清單」；brief §20.26（Open WebUI 的慣例、模型清單端點）；plan §6〈settings〉；`docs/research/assistant-feedback-2026-11-01.md`

## 為什麼

設定頁的模型下拉現在讀的是本機價目表，填了 DeepSeek 的網址也看不到 DeepSeek 的模型。照 Open WebUI 的做法向填的端點問模型，問不到就照打；但只在按了按鈕才連外，不自動問（使用者定）。

## 做什麼

1. **沒按之前**：建議清單是 `known_models(表單的 base URL)`，改網址就換。要一支只讀本機表、不帶 key、不連外的端點（或併進下面那支：`key` 不送時只查本機）。
2. **「取得模型」**：模型欄旁一顆按鈕，按了才打 `POST /settings/ai/models`（命令 `ai.list_models`，`Effect.READ`、`CONNECTS_OUT`）。
   - 收表單上還沒存的接口、base URL 與 key，不收模型名。key 用 01 的函式決定，網址改了而 key 欄空著就是 `key_missing`。
   - Anthropic 接口打 `{base}/v1/models`（有分頁），OpenAI 接口打 `{base}/models`。
   - 回 `models`、`source`（`endpoint` / `prices`）與失敗原因。問不到不算請求錯：退回本機表，並說明原因。
3. base URL 或 key 改了時，按鈕取得的清單收掉。模型欄仍可自由輸入，AI 開著時模型名仍必填。
4. 帶 key 的回應形狀：adapter 用 fixture 做契約測試；實測一次補進 brief §20.26（要 key 時問使用者；沒有就照官方文件定形狀，在 brief 標「未實測」）。

## 驗收

- [ ] 填 DeepSeek 的 base URL、還沒存：建議馬上換成本機表的 DeepSeek 模型，過程沒有請求帶 key、也沒有連外（測試＋playwright）
- [ ] 按「取得模型」後換成該端點回的模型；Anthropic 的分頁收齊（契約測試）
- [ ] 問不到時退回本機表並說明，仍可照打；base URL 改了之後取得的清單不留著
- [ ] 存著 key、改了 base URL、key 欄空著時，取得模型是 `key_missing`，fake 記不到帶舊 key 的請求
- [ ] brief §20.26 補上模型清單端點的回應形狀與來源
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
