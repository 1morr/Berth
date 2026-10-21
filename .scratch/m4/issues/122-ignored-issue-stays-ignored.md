# 122 — 忽略的 Issue 在條件持續期間不再重開

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.5〈M3 收尾帶過來的兩條〉（含 2026-09-26 補）；M3 票 17（`.scratch/m3/issues/17-jellyfin-verify.md`）的 Comments；`berth/services/health_issues.py` 的 `_settle`、`_still_ignored`；`berth/services/resolver.py` 的 `settle_verdicts`；brief §9.1

## 為什麼

`jellyfin_item_mismatch` 被「忽略」之後，第二天對帳又把它重開。健康檢查那邊已經有「條件持續期間忽略有效、條件消失（`cleared_at`）之後再發生才重開」的規則，但 `cleared_at` 只有 `health_issues._settle` 會寫，`resolver.settle_verdicts` 不寫、也不看 `IGNORED`。不修的話，票 127 的「等你處理」會為同一件被忽略的事每天推一次。

## 做什麼

1. `settle_verdicts` 管的 Issue 類型用同一套規則：條件消失時寫 `cleared_at`；條件仍在、上一筆被忽略而且沒有 `cleared_at` 時不重開。規則只有一份——把 `_still_ignored` 與寫 `cleared_at` 的那一段搬到兩邊都用得到的地方，不複製。
2. 盤點其他會重開 Issue 的路徑（對帳的各種類型）是否有同樣的洞；有就一起修，沒有就在票的 Comments 說查過哪些。

## 驗收

- [ ] 忽略一件 `jellyfin_item_mismatch`，下一輪同樣不一致：不重開（pytest）
- [ ] 條件消失一輪之後再出現：重開（pytest；變異：拿掉 `cleared_at` 的寫入會紅）
- [ ] 規則只有一份實作（兩條路徑呼叫同一支）
- [ ] 全部檢查、pytest 綠；CHANGELOG〈Fixed〉一條；plan §11.5 那兩條標「票 122 做完」的那一條；progress.md 已更新
