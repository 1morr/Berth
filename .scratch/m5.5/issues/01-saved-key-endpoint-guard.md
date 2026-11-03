# 01 — key 只送到存它的端點

**Status:** done

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

- [x] 存著 key、把 base URL 改掉、key 欄空著：測試連線與儲存都是 `key_missing`，儲存什麼都沒寫，fake 記不到任何帶舊 key 的請求（測試）
- [x] 網址沒改時兩者照常用存著的那把；留空與填官方網址算沒改（測試）
- [x] 設定頁的錯誤標在 key 欄、提示說得出規則（zh-Hant、en；playwright 實跑）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 共用函式是 `services/ai.py` 的 `_key_for(provider, base_url, typed_key, saved)`：只收需要的值，02 的 `ai.list_models` 不必湊模型名就能用（code-review 建議）。
- 後端仍只回 `key_missing`；設定頁在「存著 key 卻被說沒 key」時改說 `settings.aiPage.key.savedElsewhere`（只可能是網址改了）。改 Base URL 欄也收掉 `key_missing`。
- 實跑（fake 後端 `healthy`，zh-Hant 與 en、桌機與 390px）：存 key 於 `https://gw.example/anthropic` 後改網址，測試與儲存都標在 key 欄、`aria-invalid`，儲存後讀回仍是舊網址；改回 `…/anthropic/` 測試連上；390px 不溢出。
- code-review 未處理：
  - 網址比對不忽略大小寫（`https://API.example.com` 算不同端點而拒絕）：偏保守、不外洩，不改。
  - `set_ai` 的 inverse「用原值再存一次」：上一次同時換了網址與 key 時，原值撤銷會因 key 欄空著被拒；舊 key 已被覆蓋本來就回不去，拒絕是對的。
  - 被拒的儲存以 `GET` 前後比對證明沒寫，看不到 key 原文；`change` 被拒時直接 `return`，邏輯上不動 key。
  - 「存著的 key 只送到存它的端點」的說明散在數個 docstring：OpenAPI 與 enum 註解是對外說明，保留。
