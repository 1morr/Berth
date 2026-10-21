# 127 — 「有 N 件等你處理」（含 Issue 新增）

**Status:** ready-for-agent

**Blocked by:** 122、123、124

**讀:** plan §11.5〈通知〉（「Issue 新增」已併進這一則）；brief §19 2026-10-21 兩條；`berth/services/review.py` 的 `review_total`；`berth/services/issues.py` 的 `count_open`；`berth/services/rss.py` 待綁定的計數（`_awaiting_*` 一帶）；前端審核、Issue、RSS 頁各自的網址（一件時要連到那一件）

## 為什麼

Berth 平常不必打開的前提是「有事需要人的時候它會說」（plan §11.5）。待審核、Issue、待綁定的 RSS Series 是三個要人動手的地方。

## 做什麼

1. 有新的一件出現（進審核、Issue 開或重開、RSS Series 變待綁定）時，給有 Discord ID、訂閱了的管理員排一則，最早送出時間 10 分鐘後；期間再有新的併進同一則。
2. 送出時重算：說出這一波新增了什麼（種類與數量，例如「新增 3 件：1 個 Issue（找不到檔案）、2 件待審核」）與現在的總數；送出前都已處理掉、總數是 0 就不送。
3. 連結（票 124）：這一波只有一件時連到那一件，多件連到對應的清單；沒設網址時不附。
4. 「Issue 新增」不另外送。被忽略、條件仍在的 Issue 不算新增（票 122）。

## 驗收

- [ ] 10 分鐘內三件（各一種）→ 一則，列出種類與數量與總數（pytest）
- [ ] 只有一件時，三種各自連到那一件的網址（pytest）
- [ ] 送出前已處理掉、總數 0 → 不送（pytest）
- [ ] 被忽略的 Issue 隔天對帳不觸發（pytest，依票 122）
- [ ] `user` 角色不收（pytest）
- [ ] 全部檢查、pytest 綠；CHANGELOG、progress.md 已更新
