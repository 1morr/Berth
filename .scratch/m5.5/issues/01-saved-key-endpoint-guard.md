# 01 — key 只送到存它的端點

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「key 只送到存它的那個端點」；plan §6〈settings〉；brief §20.26；`docs/research/assistant-feedback-2026-11-01.md`

## 為什麼

設定頁的 key 欄空著代表「沿用存著的那把」，但現在的「測試連線」沒有比對網址：改了 base URL 再按測試，舊 key 會送到新網址。打到一半的網址不該收到 key（使用者定）。plan 原本把這條和模型清單排在同一張票，開工時拆開（使用者定 2026-11-03）：02 的 `ai.list_models` 也用這張寫的函式。

## 做什麼

1. 一支共用函式決定這次用哪把 key：
   - key 欄有填就用填的。
   - key 欄空著時，表單的 base URL 與存著的那個，經 `effective_base_url` 比對相同才用存著的那把（留空與填官方網址算同一個）；不同就是 `key_missing`。
2. `ai.test_ai` 改用它。
3. `ai.set_ai`：這個接口有存著的 key、網址改了、key 欄空著時拒絕，什麼都不存。只守測試的話，先存再按就繞過去了。
4. 文案：`settings.aiPage.test.hint` 與 key 欄的提示改說這條規則，錯誤標在 key 欄（zh-Hant、en）。

## 驗收

- [ ] 存著 key、把 base URL 改掉、key 欄空著：測試連線與儲存都是 `key_missing`，儲存什麼都沒寫，fake 記不到任何帶舊 key 的請求（測試）
- [ ] 網址沒改時兩者照常用存著的那把；留空與填官方網址算沒改（測試）
- [ ] 設定頁的錯誤標在 key 欄、提示說得出規則（zh-Hant、en；playwright 實跑）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
