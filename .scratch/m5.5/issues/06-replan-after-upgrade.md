# 06 — 升級後自動重算

**Status:** ready-for-agent

**Blocked by:** None (can start immediately；排在 04、05 之後做，升級時才會用新規則重算被誤擋的列)

**讀:** spec〈範圍〉「升級後自動重算」；plan §3.1（狀態機）、§4.4；`docs/research/review-queue-2026-11-01.md`

## 為什麼

04、05 改了規則，但已經在審核佇列的 Job 要人手動「重新規劃」才會用新規則。升級後應該自動重算，但不能每次啟動全部重算：會蓋掉人改的列、重設等候時間，同版本的結果也一樣。

## 做什麼

1. 啟動時只挑 `state = review`、`plans.engine != user`、`plans.engine_version != VERSION` 的 Job；排除 `review_reason = audit_undone`（人已經說過那一列不對）。
2. 新命令標 `Flag.INTERNAL`，走 `REVIEW → COMPLETED`（同 `replan_job`），交給 `PlannerRunner` 在背景算，不拖慢啟動；TMDB 連不上時照它現有的方式下一輪再算。
3. 算完的計劃蓋上新版本，所以同版本重啟不再重算。已入庫的不動。
4. 文件：plan §3.1 的 `review → completed` 多一個系統觸發。

## 驗收

- [ ] 整合測試：舊版本的 `review` 重算成新版本；`engine = user` 與 `audit_undone` 不動
- [ ] 同版本重啟不重算，`tmdb` 請求數為 0（fake client 計數）
- [ ] 啟動不等重算做完（測試）
- [ ] 全部檢查、pytest 綠；progress.md 已更新
