# 05 — 第一批收累計編號

**Status:** ready-for-agent

**Blocked by:** 04

**讀:** spec〈範圍〉「第一批擔保收累計編號」；brief §15、§20.27；`docs/research/review-queue-2026-11-01.md`；`scripts/experiments/first_batch_rule.py`

## 為什麼

審核佇列另外 17 件是第一批確認，其中累計編號的（夜櫻 40 → S2E13）讀法其實是確定的，但第一批現在不擔保。量過才收。

## 做什麼

1. 第一批擔保的條件多一種讀法，其餘條件不變：理由是 `absolute_cumulative`、季號寫明、Series 沒設季號與 offset、檔名集號剛好等於前面各季集數加對到的集號，而且那一集剛播（上緣維持兩天）。其他絕對編號與重數推測仍不擔保。
2. **閘門**：`scripts/experiments/first_batch_rule.py` 的語料與對抗輪都要擔保錯 0。不是 0 就不收這一條、回報使用者，這張票視為做完（結果記在 Comments 與 brief §15）。
3. 已入庫的舊列不另外掃：下一集自動落地時，整批照 `first_batch.vouch` 一起看。已經完結、不會再有下一集的，留給人按確認。
4. 文件：brief §15、`parser/first_batch.py` 開頭的條件說明。

## 驗收

- [ ] 閘門跑完、數字貼在 Comments（語料與對抗輪的擔保錯數）
- [ ] 閘門過了：累計編號的（夜櫻 40 → S2E13）由系統確認；重數推測與其他絕對編號仍要人確認（測試）。沒過：程式不改，已回報使用者
- [ ] `berth bench` 的 `auto_wrong` 不升（貼前後數字）
- [ ] 全部檢查、pytest 綠；progress.md 已更新
