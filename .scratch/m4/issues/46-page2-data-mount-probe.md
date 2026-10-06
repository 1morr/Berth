# 46 — 頁 2 測連線時就驗 qBittorrent 看得到 `/data`

**Status:** ready-for-agent

**Blocked by:** 36（補法沿用「只加一條 `/data`」）、38（頁 2 的前進條件先收好）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S3「qBittorrent 沒掛 `/data`」那列、§B1「能不能接被拆在兩頁」、§C3 第 1 條、改進清單 P2-4）；M4 票 19 與它在 progress.md 的偏差（探針會觸發「完成時執行外部程式」）；brief §16.4；plan §9.3

## 為什麼（2026-10-06 審計，實測）

- 掛 `/downloads`、沒掛 `/data` 的 qBittorrent，在頁 2 測試**通過**，要到頁 3 的第三條纜繩才失敗。截圖 s3-11、s3-12。
- Berth 已經有探針（票 19），頁 2 就可以先問一次。

## 做什麼

1. 頁 2 的連線測試通過之後，接著問一次 qBittorrent 看不看得到 `/data`。用票 19 的探針或更輕的方式都可以，以「不觸發完成時執行外部程式」為準；做法記在偏差。
2. 看不到時頁 2 轉紅，補法與 36 相同。
3. 那一台的「完成時執行外部程式」提示沿用票 19 的說法。

## 驗收

- [ ] 整合測試（雙向）：看不到 `/data` 的 qBittorrent 在頁 2 轉紅並附補法；看得到的照常通過
- [ ] 探針 torrent 跑完不留在 qBittorrent 裡（測試斷言）
- [ ] 實跑掛 `/downloads` 的那台（照 34 的隔離），附截圖
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e、真服務 e2e 綠燈
