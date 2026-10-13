# 96 — 文件與註解偏差：審計順手找到的 6 處

**Status:** ready-for-agent

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

- [ ] 6 處都對得上程式碼（`git log -S`、grep 查過再寫）
- [ ] 全部檢查綠；progress.md 已更新
