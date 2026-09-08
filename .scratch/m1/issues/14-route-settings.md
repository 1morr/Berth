# 14 — Route 設定頁：一個媒體庫多條 Route 與明確刪除

**Status:** ready-for-agent

**Blocked by:** 09（Job 開始引用 `route_id`）

**讀:** plan §6（routes 群組）、§9.3（第 7 步）、§9.5、§11.2（T1.9 第三條）；brief §4.3、§16.4；
`.scratch/m0/issues/09-wizard-routes.md` 的決定

## 做什麼

M0 票 09 記下的那條債：精靈第 7 步是以媒體庫名建索引、**重跑會刪掉沒勾的 Route**，而那時候
「M0 沒有任何東西引用 route_id」。票 09 之後 Job 引用了它，所以這條必須改成軟處理，並且要有一個
真正的 Route 管理入口。

brief §4.3 本來就允許一個 Jellyfin 媒體庫掛多條路徑，所以「一個媒體庫多條 Route」是既有需求，
不是新功能。

## 驗收

- [ ] `GET/POST /api/routes`、`PUT/DELETE /routes/{id}`、`POST /routes/{id}/check`
- [ ] 同一個 Jellyfin 媒體庫建得出第二條 Route（不同 slug 與 target_path，劇集可挑不同 profile）
- [ ] 刪除是明確動作並要二次確認；被 Job 或 ledger 引用的 Route 不能直接刪，說明原因並給出路
- [ ] **重跑精靈第 7 步不再隱式刪掉沒勾的 Route**（有測試釘住）
- [ ] 新建或修改的 Route 跑一次 plan §9.5 的五條纜繩檢查，紅的不給啟用
- [ ] `/settings/routes` 只有 admin 進得來，規則在門禁 middleware 而不是 router 的相依
- [ ] 設定頁走 `/impeccable shape`；playwright 實跑並附結果
- [ ] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [ ] lint / type / test 全綠並貼指令輸出
