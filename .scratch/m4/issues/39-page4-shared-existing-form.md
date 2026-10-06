# 39 — 頁 4 既有表單改用頁 1、2 的元件與端點；錯誤版面與右欄狀態

**Status:** ready-for-agent

**Blocked by:** 37（拿掉 Torznab 之後，共用元件不必背「接法」單選）、34（要更新真服務 e2e）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S3「Prowlarr API key 錯」那列、§A3「兩條寫 `choices` 的路徑」、§C3 第 3 條、「Berth 精靈哪裡不統一」第 2 條、簡化方案 E-2、改進清單 P1-2、P1-4）；票 21；brief §16.3；plan §9.3

## 為什麼（2026-10-06 審計）

- 頁 4 既有表單有自己的元件與端點（`POST /setup/indexers/connect`），錯誤版面和頁 1、2 不一樣，少了「測試結果」那一列。
- key 錯的時候，右欄仍寫「API key 已取得」。截圖 s3-14。
- 寫 `choices` 有兩條路徑：頁 1、2 走 `POST /setup/services/{kind}`，會經過 `_start_over` 的清理；頁 4 那條不經過。

## 做什麼

1. 頁 4 既有表單換成頁 1、2 的 `ExistingForm`。連線改走 `POST /setup/services/{kind}`，`choices` 只剩一條寫入路徑，都經過同一份清理。
2. 刪掉 `POST /setup/indexers/connect`。它是 OpenAPI 公開的端點，屬對外 API 刪除（D5 / E-2 已拍板），要記進 CHANGELOG。
3. 右欄的憑證狀態跟著最近一次連線測試走：失敗時不寫「已取得」。
4. plan §6 的 API 表與 §9.3 同一個 commit 改。

## 驗收

- [ ] 整合測試：Prowlarr 經 `POST /setup/services/prowlarr` 連線、換台時走 `_start_over` 的清理（雙向：換台會清、同一台不清）
- [ ] vitest：頁 4 既有表單與頁 1、2 是同一個元件；key 錯時錯誤區有「測試結果」那一列，右欄不寫「已取得」
- [ ] 舊端點刪掉，OpenAPI 型別重新產生
- [ ] 真服務 e2e 與前端 e2e 更新並綠燈；playwright 實跑 key 錯與 key 對，附截圖
- [ ] 全部檢查（`pre-commit run --all-files`）、test 綠燈
