# 13 — 通知寫作品名與集數

**Status:** ready-for-agent

**Blocked by:** 10

**讀:** spec〈範圍〉「通知」；brief §14（通知）；ADR-0015；`services/notify.py`（`_part`）；`describe_spans`

## 為什麼

遲到走現有的「等你處理」與「放太久」，不加通知種類，收件人也一樣（訂閱了它、有 Discord ID 的管理員），週報沿用。但現在的訊息只寫種類與數量，只知道「1 個 Issue（遲到）」還得點進去看。

## 做什麼

1. 這一波有 `episodes_overdue` 時，內文列出作品名與晚的集（`describe_spans`），最多五部，其餘寫「等 N 部」。
2. 送出時照 `detail_json` 組字，zh-Hant 與 en 並列。`reason = next_run`（11）的件寫成「可能是下一輪」，不寫成晚了。
3. 其他 Issue 種類的訊息不變。

## 驗收

- [ ] Discord 訊息寫出作品名與晚的集（zh-Hant、en；測試）
- [ ] 超過五部時其餘寫「等 N 部」（測試）
- [ ] 沒有 `episodes_overdue` 的一波，訊息與現在相同（測試）
- [ ] 全部檢查、pytest 綠；progress.md 已更新
