# 06 — 升級後自動重算

**Status:** done

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

- [x] 整合測試：舊版本的 `review` 重算成新版本；`engine = user` 與 `audit_undone` 不動
- [x] 同版本重啟不重算，`tmdb` 請求數為 0（fake client 計數）
- [x] 啟動不等重算做完（測試）
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- **做法**：`plan.replan_outdated` 只把挑到的列 CAS 退回 `completed`、寫 `retried(state=completed, engine_version=舊版本)`（actor `system`，時間線照「重新規劃」那一句顯示），lifespan 在迴圈起來前呼叫、有挑到才 `nudge` 規劃器。算在 `planner_runner` 那一輪，啟動不碰 TMDB。
- **測試**：`tests/integration/test_replan_outdated.py`。啟動那一條用讀詳情時停住的 TMDB 替身：lifespan 五秒內起來、Job 停在 `planning`，放行後落回 `review` 且蓋上新版本；連跑 20 次綠。變異：拿掉 `engine` / `audit_undone` / 版本條件、啟動同步算一輪，各自有測試變紅；`requests == []` 單獨也抓得到。
- **TMDB 連不上**：沿用 `snapshot_for_planning` 的「失敗不擋」，用存著的快照照算、照樣蓋上新版本，不是字面上的「下一輪再算」；規劃本身爆掉才由 `guarded` 下一輪再算。
- **code-review 未處理的發現**：importer 擋下的 `target_exists` 也會被挑中，重算後多半入庫時又撞回 `review`（時間線多三筆）；spec 只排除 `audit_undone`，照 spec 沒排除。`engine_version` 是空字串的舊列也算舊版本。`PlanEngine.AI` 現在沒人寫，將來有 AI 計劃時這裡要重想（目前條件是 `!= user`，會被規則蓋掉）。`PlanSummary.model_validate(plan.summary_json or {})` 在 services 裡第七次出現，沒收成 helper。
- **驗證**：`uv run pre-commit run --all-files` 全過；`uv run pytest -q -n auto` 5467 passed, 1 skipped。
