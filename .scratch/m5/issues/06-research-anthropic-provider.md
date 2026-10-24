# 06 — 研究：Anthropic provider

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.6〈provider〉〈用量記錄〉；brief §6.10「用量，不設預算」「外部文字是資料」；CLAUDE.md〈事實與查證〉

## 為什麼

provider 的 SDK 版本、模型 id、tool use、prompt caching 與 `usage` 欄位不能憑記憶寫（CLAUDE.md：外部服務只信 brief §20 與現查）。票 07 與 08 依這份結論實作。

## 做什麼

用 `mattpocock-skills:research`（以及 `claude-api` skill、context7），輸出放 `docs/research/`，結論摘進 brief §20 新的一節並附來源：

1. Python `anthropic` SDK 當前 stable 版本、async client、串流加 tool use 的寫法（含 tool runner 與手寫迴圈的取捨）。
2. 目前的模型 id 與建議預設（側面板用哪一個、設定裡給使用者選哪些）。
3. prompt caching：cache breakpoint 放哪、最小可快取長度、TTL、工具定義與 system 的順序怎麼排才吃得到。
4. `usage` 的欄位：輸入、輸出、快取寫入、快取讀取各叫什麼；串流時從哪個事件拿；快取命中率怎麼算。
5. 錯誤：限流、過載、驗證失敗的型別與 retry-after，哪些該重試、哪些交給人。
6. 官方對 tool result 與 prompt injection 的建議（外部文字怎麼包），與 brief §6.10 對照。
7. 測試怎麼做：假 provider 的形狀，respx 錄放的可行性。

## 驗收

- [ ] `docs/research/` 有一份附來源的結論，brief §20 新的一節摘要並連結
- [ ] 每一條都有官方文件或實測的出處，沒有憑記憶的版本號
- [ ] progress.md 已更新
