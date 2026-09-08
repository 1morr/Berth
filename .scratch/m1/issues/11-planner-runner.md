# 11 — planner_runner：完成 → Import Plan

**Status:** ready-for-agent

**Blocked by:** 07（解析器要能產出完整 Plan）、10（Job 要走得到 `completed`）

**讀:** plan §3.1（planning 段）、§3.2（planner_runner）、§4.3、§4.5、§8.7、§11.2（T1.6 前半）；
brief §6.5

## 做什麼

torrent 完成之後自動讀 mediainfo、跑解析、產生 Import Plan 並持久化，Job 依信心走向 `importing`
或停在 `review`；Job 詳情頁看得到逐檔的決定、信心與理由。

`metadata_ready` 時就先跑一次 pre-plan（`plans.status = preplan`），所以下載中就看得到預估。

M1 沒有審核 UI（Review Queue 是 M2），停在 `review` 的 Job 就是停在那裡並把原因說清楚。

## 驗收

- [ ] `plans` 與 `plan_items` 表與 migration，欄位依 plan §2.3
- [ ] `planner_runner` 事件驅動（queue）+ 每 60s 掃 `completed`；例外不讓迴圈死掉
- [ ] mediainfo adapter：`probe()` 回 duration / 寬高 / codec / bit depth / 音軌語言 / 字幕軌；
      失敗不阻擋，Plan 只少一個訊號（有測試）
- [ ] 時長 < 5 分鐘的「正片」被 mediainfo 降為 `extra`（plan §4.1）
- [ ] `metadata_ready` 時跑 pre-plan 並寫 `plans.status = preplan`
- [ ] `completed` → `planning`：全 high / medium 且 Route 允許 → `importing`（`auto`）；
      否則 → `review`（`pending_review`），兩條路徑各寫對應的 event
- [ ] Route 的 `medium_auto_import = false` 時 medium 進 review
- [ ] planning 前若 TMDB 快照超過 6 小時則刷新
- [ ] `GET /api/plans/{id}`；Job 詳情頁顯示逐檔決定、信心與理由（M1 唯讀，逐列編輯是 M2）
- [ ] 同一個 job 重跑 planning 不產生重複的 plan item（重入測試）
- [ ] `POST /jobs/{hash}/replan` 可手動重跑
- [ ] 對比 ≥ 4.5:1；zh-Hant 與 en 並列
- [ ] lint / type / test 全綠並貼指令輸出
