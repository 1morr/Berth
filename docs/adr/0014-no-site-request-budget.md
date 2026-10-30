# 不做站點請求預算

M3 票 20 與 M4 票 77 曾讓輪詢、補漏、搜尋與人按的讀取共用「每站每小時 60 個」的預算。2026-10-19 拿掉，連同 `GET /health/budget`、健康頁那張卡、搜尋的 `skipped` / `retry_at` / `next_at` / `budget_exhausted`、自動綁定的 `lookup_deferred`。

理由：60 不是量出來的（brief §20.13，三站沒有公開的限速紀錄）；擋到人的只有 Berth 自己的計數；搜尋經過 Prowlarr，它每站有使用者調得了的 Query Limit，Berth 再管一層是雙重限制。站點真的回 429 / 5xx 時照既有退路：讀不到記 `last_error` 下一輪再試、自動綁定 `lookup_retry`。升版 migration 把 `lookup_deferred` 改成到期的 `lookup_retry`、不算一次失敗。

來源：brief §19 舊列「刪除站點請求預算」（原文在 `docs/archive/m4.md`）；`docs/research/request-budget.md`。
