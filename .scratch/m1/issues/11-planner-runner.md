# 11 — planner_runner：完成 → Import Plan

**Status:** done

**Blocked by:** 07（解析器要能產出完整 Plan）、10（Job 要走得到 `completed`）

**讀:** plan §3.1（planning 段）、§3.2（planner_runner）、§4.3、§4.5、§8.7、§11.2（T1.6 前半）；
brief §6.5

## 做什麼

torrent 完成之後自動讀 mediainfo、跑解析、產生 Import Plan 並持久化，Job 依信心走向 `importing`
或停在 `review`；Job 詳情頁看得到逐檔的決定、信心與理由。

`metadata_ready` 時就先跑一次 pre-plan（`plans.status = preplan`），所以下載中就看得到預估。

M1 沒有審核 UI（Review Queue 是 M2），停在 `review` 的 Job 就是停在那裡並把原因說清楚。

## 驗收

- [x] `plans` 與 `plan_items` 表與 migration，欄位依 plan §2.3
- [x] `planner_runner` 事件驅動（queue）+ 每 60s 掃 `completed`；例外不讓迴圈死掉
- [x] mediainfo adapter：`probe()` 回 duration / 寬高 / codec / bit depth / 音軌語言 / 字幕軌；
      失敗不阻擋，Plan 只少一個訊號（有測試）
- [x] 時長 < 5 分鐘的「正片」被 mediainfo 降為 `extra`（plan §4.1）
- [x] `metadata_ready` 時跑 pre-plan 並寫 `plans.status = preplan`
- [x] `completed` → `planning`：全 high / medium 且 Route 允許 → `importing`（`auto`）；
      否則 → `review`（`pending_review`），兩條路徑各寫對應的 event
- [x] Route 的 `medium_auto_import = false` 時 medium 進 review
- [x] planning 前若 TMDB 快照超過 6 小時則刷新
- [x] `GET /api/plans/{id}`；Job 詳情頁顯示逐檔決定、信心與理由（M1 唯讀，逐列編輯是 M2）
- [x] 同一個 job 重跑 planning 不產生重複的 plan item（重入測試）
- [x] `POST /jobs/{hash}/replan` 可手動重跑
- [x] 對比 ≥ 4.5:1；zh-Hant 與 en 並列
- [x] lint / type / test 全綠並貼指令輸出

## 驗證

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
237 files already formatted

$ uv run mypy
Success: no issues found in 179 source files

$ uv run lint-imports
Contracts: 6 kept, 0 broken.

$ uv run pytest -q
1145 passed in 209.31s (0:03:29)

$ uv run berth bench
23 fixtures, 333 files
category  files  classify  tags     confidence  auto_correct  auto_wrong  review  missed  unmatched_correct  extra_correct  subtitle_correct  skipped
anime     175    175/175   82/82    82/82       82            0           0       0       42                 24             26                1
tv        75     75/75     55/55    55/55       55            0           0       0       0                  0              11                9
movie     83     83/83     3/3      3/3         3             0           61      0       0                  17             0                 2
overall   333    333/333   140/140  140/140     140           0           61      0       42                 41             37                12
high: 0/83 wrong (0.0%)  medium: 0/57 wrong (0.0%)

$ pnpm -C web lint && pnpm -C web typecheck && pnpm -C web test
Test Files  16 passed (16)
     Tests  213 passed (213)
```

**實跑**（`--scenario plan`，2026-09-11）：qBittorrent 是替身，其餘全是真的——真的 TMDB 快照
（SPY×FAMILY 兩季、集名 `OPERATION STRIX` 進了目標檔名）、真的 poller、真的 planner、真的
mediainfo。送兩包進去：三集的批次走到 `importing`（`auto`、5 個檔案要入庫、high 5），
OST 那一包走到 `review`（`pending_review`、`low_confidence`）。按下「重新規劃」之後 plan id
不變、item 數不變、`created_at` 換成重算的時間（重入）。

無障礙實測（playwright，1280px 與 390px × 深淺兩主題共四輪）：147 個文字節點**最差 5.71:1**、
低於 4.5 的 0 個；390px 無頁面層級橫向捲動。英文版整塊讀得完，畫面上沒有任何一條 i18n key。

## Comments

這一票**沒有做**、或做法與票上字面不同的地方（每一條都記在 `docs/progress.md` 的「偏差與決定」）：

- **`unmatched` 不擋自動入庫**（plan §3.1 已回寫）。照「全 high/medium」的字面它會擋——但那不是
  低信心，是一個已經做完的決定（brief §7.6），而動漫批次幾乎每包都夾著一兩個發佈方自己編號的 SP。
- **Plan 畫在 `/jobs` 的就地展開區**，不是 `/jobs/:hash`（票 09 拍板不另建那一頁）。plan §7 的
  `/jobs/:hash` 仍然留給 T1.7 的完整 Job 詳情。
- **Plan item 的理由不走 i18n**：它們是解析器產生的英文句子（帶著檔名片段與數字），畫面原樣顯示
  並標 `lang="en"`。要翻譯得先把理由變成封閉集合的 code + 參數——那是 M2 Review Queue 的形狀。
- **`job_files.release_info_json` 這一票不填**（plan §3.1 說 planning「更新 `job_files`」）：只填
  `kind` 與 `mediainfo_json`。逐檔的 `ReleaseInfo` 是 `planner._decide` 的中間值，服務層自己再算
  一次會與解析器分岔，而 M1 沒有東西讀它。
- **brief §6.8 的「resolution 以 mediainfo 為優先」還沒接上**：`MediaInfoSummary` 已經存了寬高，
  但 Tags 的 `resolution` 仍然只從發佈名讀。接上要一張「高度 → token」的門檻表，而猜錯的代價是
  磁碟上的檔名。等有真實案例（實測到發佈名說謊）再做。
- **`list_jobs` 的 N+1 多了一支**：`_view` 現在每列多一次 `SELECT plans.id`（原本就有 route /
  media / user 三次）。一頁四十列在 SQLite 上仍然是微秒級，但整支 `_view` 值得在 M2 的 Review
  Queue（同一份清單要帶更多東西）一起改成批次查詢。
- **`.impeccable/design.json` 比 `DESIGN.md` 舊**（hook 提醒）：那是票 10 留下的，`/impeccable
  document` 要在設計系統定稿時跑，留給票 15 的里程碑收尾。
