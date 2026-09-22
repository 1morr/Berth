# 16 — M2 驗收

**Status:** ready-for-agent

**Blocked by:** 01–15 全部

**讀:** plan §11.3（範圍與驗收那兩行）、§10；brief §9、§11、§17

## 做什麼

里程碑收尾。plan §11.3 的驗收是四條：

> 刪掉 library 後一鍵重建；對「Jellyfin 內刪除」「complete 目錄手動刪檔」「用複製取代硬鏈接」
> 三種破壞都能偵測並修復；medium 自動入庫的檔案可在佇列中一鍵撤銷；以 `user` 登入時看不到也
> 按不到審核、修正與刪除。

**e2e 要覆蓋前三條**（compose + 真服務那一套，`tests/e2e/`）。三種破壞分別對應
`library_link_missing`、`orphan_complete` / `source_missing`、`inode_mismatch`。第四條是
權限的整合測試，後端與前端各一半。

**收尾動作**（專案 CLAUDE.md）：

- `/impeccable critique`、`audit`、`polish` 各一輪，P0 / P1 當場修，其餘記進票的 Comments
- 票 01–15 的 Comments 逐條過完，分成「修掉」「延後（寫進 plan §11.4 M3 或 §11.5）」「不做」三類
- `docs/progress.md` 加 M2 的 session 紀錄與偏差；plan §11.3 與 brief 的偏差同一個 commit 改掉
- CHANGELOG

## 驗收

- [ ] e2e 覆蓋三種破壞：各造一次、對帳偵測到、按動作修好，全程自動化（貼 CI run 連結與輸出）
- [ ] 刪掉 library 後一鍵重建在 e2e 裡走得完（票 10 的整合測試之外，這裡是真環境）
- [ ] medium 自動入庫的一筆在佇列中一鍵撤銷（e2e 或整合測試，貼輸出）
- [ ] 以 `user` 登入：`/review/*`、`/issues/*`、`/files/*`、`/reconcile`、`DELETE /jobs/{hash}`、
      `POST /jobs/{hash}/reimport` 全是 403，前端看不到入口（一份把六條列齊的測試，新增 admin
      端點卻忘了加進去會紅）
- [ ] `/impeccable critique`、`audit`、`polish` 各一輪，分數與處理結果記在票裡
- [ ] 票 01–15 的 Comments 逐條有歸屬
- [ ] `docs/progress.md`、`docs/plan.md`、`docs/design-brief.md`、CHANGELOG、README 與 repo 一致
- [ ] lint、type、test、e2e 全綠（貼指令輸出）

## Comments
