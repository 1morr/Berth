# 04 — 送單閘門

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.4「M3 之前先做的修補」、§3.1、§3.3（`add_download` 的冪等）、§3.2（`health_checker` 的磁碟門檻）、§6（門禁 `ADMIN_ROUTES`）；brief §9.2

## 做什麼

RSS 送單沒有人按確認，所以原本靠「人在場」擋掉的三件事要改由程式擋。

- **送單前看磁碟門檻**：現在 `settings.disk.min_free_gb` 只拿來開 `low_disk_space` Issue，不擋送單。改成 `add_download` 在 incomplete 那一側低於門檻時拒絕（封閉集合的拒絕理由，進 OpenAPI），手動與 RSS 同一個判斷。門檻是 `0` 時不量。
- **刪除過、沒清紀錄的 Job 不能再下載同一個 hash**：現在 §3.3 的「同 hash 回傳既有 Job」會把 `removed` 的那一列回傳回去，而 RSS 下一輪看到同一筆就等於要再送。定義清楚 `removed` 的同一個 hash 再進來時怎麼回應（拒絕並說出理由），寫進 §3.3。
- **`POST /jobs/*/replan` 在 `review` 狀態要 admin**：現在 `user` 重算一次，就會推翻 admin 做過的撤銷。

## 驗收

- [x] 磁碟低於門檻時，手動送單與 service 層直接呼叫都被拒，拒絕理由在 OpenAPI 裡；門檻 `0` 時不擋（整合測試，雙向）
- [x] `removed` 的 hash 再送一次被拒並說出理由，不回傳那一列當成功；plan §3.3 同步（整合測試）
- [x] `user` 對 `review` 狀態的 Job 按重算是 403，其他狀態照舊；`test_auth_api` 的整張表同步
- [x] 前端送單的地方畫得出兩種新的拒絕理由（zh-Hant 與 en）
- [x] lint、type、test 綠燈

## Comments

- **review 的重算守在命令裡，不在 `ADMIN_ROUTES`**：門禁只看方法與路徑，看不到 Job 狀態。規則只有一支 `services/jobs.replannable(state, role)`，`replan_job`（鎖內、CAS 之前）與 `JobOut.replannable`（API 依按的人算）都問它，所以前端不重算。`test_auth_api` 的 ACCESS 表上 replan 仍是 SIGNED_IN，表上註解指向 `test_plans_api.py` 的 `TestReplanInReviewIsAdmins`。變異：讓 `replannable` 忽略角色，那一組轉紅。
- **磁碟門檻只看 incomplete**，量不到那個目錄不擋（演練伺服器沒建那個目錄時就是這樣，log 一行 warning）；**送單的重試也看**（`retry_job` 本來就與第一次送單同一組前提），**Issue 的「重新送單」（`resubmit_job`）不看**：那是管理員在場按的一顆，而加進去要多一種 `IssueRefusal` 與它的文案。無人值守的 RSS 走的是 `add_download`。要補的話條件是：出現一次「重新送單把磁碟塞滿」的 repro。
- **順序**：索引站報得出 hash 時，`job_removed` 在磁碟檢查之前；報不出時先量磁碟（要 torrent 才知道 hash）。所以磁碟不夠的期間，一筆 `removed` 的條目被拒的理由可能是 `low_disk_space`。最後結果不會錯（空出空間之後拿到 `job_removed`），但 RSS 票（08）若把 `low_disk_space` 當「稍後再試」，要知道它之後可能變成另一種拒絕。
- code-review Standards（無硬違規）：前端重算「review 要 admin」→ 改成後端依人算 `replannable`（Spec 軸同一條）；`admin: bool` → `role: Role`；GB 換算改用 `min_free_gb`、detail 寫 GiB；`_known` 改名 `_existing_outcome`。**沒改**：`check_disk` 與 `health_issues._disk` 的量法相似（後者量兩個根、依 device 去重、記下看不到的），抽共用函式會讓兩邊都多一層；`services/routes` 的 `_gigabytes` 用 10⁹ 而這裡是 1024³，是既有的不一致。
- playwright 實跑（`--scenario import` 與 `review`）：刪除（不清紀錄）後再送同一列 → 紅字理由加「看那一筆下載」連到 `/jobs/<hash>`；清掉紀錄、門檻調到 1,000,000 GB → 「下載目錄的磁碟空間低於門檻」加原文 `…incomplete: 531.3 GB free, below 1000000 GB`（code-review 之後單位改寫成 GiB）、下載列表 0 筆；門檻 0 → 已送出。以 `deckhand` 開停在審核的那一筆：「等管理員審核」、沒有「重新規劃」，直接 POST 是 403 `review_needs_admin`、狀態仍是 review。
