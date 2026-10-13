# 96 — 文件與註解偏差：審計順手找到的 6 處

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的〈文件與註解偏差〉

## 為什麼

票 86 審計順手找到 6 處文件或註解跟程式碼對不上，例如 `plan.md:52` 寫有 `berth reconcile` 這個指令，但它從來沒實作過。寫錯的文件會讓下一個人照著錯的做。

## 做什麼

修審計列的 6 處：

- `plan.md:52` 的 CLI 子指令清單照實際寫：`serve`、`openapi`、`bench`、`rebuild-ledger`；手動對帳的入口是 `POST /api/issues/reconcile`。
- `DATA_ROOT`：如果票 93 已經做了就跳過，沒做就照審計 S22 改文件那一半。
- `EventHub.subscribers` 的 docstring 改成「只給測試」。
- `deeplink.py:49` 的註解改指向現在真正做這件事的地方。
- `PlanEngine.AI` 註解的「M4」改成 M5。
- `plan._duplicate_of` 的 docstring 照實際寫。

只改文件與註解，不動程式行為。

## 驗收

- [x] 6 處都對得上程式碼（`git log -S`、grep 查過再寫）
- [x] 全部檢查綠；progress.md 已更新

## Comments

- 票面「手動對帳的入口是 `POST /api/issues/reconcile`」不對：路由是 `berth/api/issues.py` 的 `@router.post("/reconcile")`，前綴 `/api`，實際是 `POST /api/reconcile`；plan.md 照 §6 的寫法記 `POST /reconcile`。
- 票 93 還沒做，`DATA_ROOT` 做了文件那一半（plan.md:30、development.md 的表格），另外根目錄 `.env.example` 的同一句註解也說它是媒體根，一併改成「本機 `berth serve` 用不到」，變數照留（刪不刪、`Config.data_root` 怎麼收由票 93 決定）。
- `parser/planner.py` 的 `episode_span` docstring 說「比帳本的那一半也用它」，與 `_duplicate_of` 的新 docstring 是同一個偏差的另一面，同輪改。
- code-review 未處理：Standards 軸提「還沒選就當既有」寫了三份（`routes._jellyfin_origin`、`health._view`、`deeplink`）與 `_duplicate_of` 裡帳本那側的 span 攤開三次——前者是審計 S26（票 91），後者審計已判為「單集資料的表示慣例」（複核駁回 A 疑點）；本票只改文件與註解，不動。CHANGELOG 不改：沒有行為或設定項變動。
