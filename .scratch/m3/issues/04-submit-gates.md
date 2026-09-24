# 04 — 送單閘門

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §11.4「M3 之前先做的修補」、§3.1、§3.3（`add_download` 的冪等）、§3.2（`health_checker` 的磁碟門檻）、§6（門禁 `ADMIN_ROUTES`）；brief §9.2

## 做什麼

RSS 送單沒有人按確認，所以原本靠「人在場」擋掉的三件事要改由程式擋。

- **送單前看磁碟門檻**：現在 `settings.disk.min_free_gb` 只拿來開 `low_disk_space` Issue，不擋送單。改成 `add_download` 在 incomplete 那一側低於門檻時拒絕（封閉集合的拒絕理由，進 OpenAPI），手動與 RSS 同一個判斷。門檻是 `0` 時不量。
- **刪除過、沒清紀錄的 Job 不能再下載同一個 hash**：現在 §3.3 的「同 hash 回傳既有 Job」會把 `removed` 的那一列回傳回去，而 RSS 下一輪看到同一筆就等於要再送。定義清楚 `removed` 的同一個 hash 再進來時怎麼回應（拒絕並說出理由），寫進 §3.3。
- **`POST /jobs/*/replan` 在 `review` 狀態要 admin**：現在 `user` 重算一次，就會推翻 admin 做過的撤銷。

## 驗收

- [ ] 磁碟低於門檻時，手動送單與 service 層直接呼叫都被拒，拒絕理由在 OpenAPI 裡；門檻 `0` 時不擋（整合測試，雙向）
- [ ] `removed` 的 hash 再送一次被拒並說出理由，不回傳那一列當成功；plan §3.3 同步（整合測試）
- [ ] `user` 對 `review` 狀態的 Job 按重算是 403，其他狀態照舊；`test_auth_api` 的整張表同步
- [ ] 前端送單的地方畫得出兩種新的拒絕理由（zh-Hant 與 en）
- [ ] lint、type、test 綠燈
