# 47 — 換一台 qBittorrent / Prowlarr 時列出 Berth 在舊那台留下的東西

**Status:** ready-for-agent

**Blocked by:** 33（「Berth 擁有的物件」定義定下來）、39（頁 4 換台也走 `POST /setup/services/{kind}` 那一條）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S2「bad-qbittorrent 留下 `berth-shows`」、§B3、「Berth 精靈哪裡不統一」第 10 條、簡化方案 E-7、改進清單 P2-5）；brief §19「精靈審計後的八項」D6、§16.4；plan §9.3

## 為什麼

- 換台之後，Berth 在舊那台建的分類、站、介面登入都留著，畫面只用文案說「不撤回」。
- **D6 拍板**：換台時列出 Berth 在舊那台建的東西，可以一鍵移除 Berth 建的空分類。

## 做什麼

1. 換 qBittorrent / Prowlarr 的確認框列出舊那台上 Berth 擁有的物件：`berth-*` 分類（各有幾個 torrent）、加入的站、Berth 設的介面登入。
2. 舊那台連不到時，列「Berth 記得建過的」，並說明沒辦法確認現況。
3. 一鍵移除只刪 Berth 建的、而且裡面沒有 torrent 的分類。站與登入只列出，不刪。
4. 移除是寫入命令：在 services 裡標 `@command`（M3 起的規則）。

## 驗收

- [ ] 整合測試：確認框的清單只含 Berth 擁有的物件；使用者自己的分類不出現
- [ ] 整合測試（雙向）：空的 `berth-*` 分類會被移除；有 torrent 的、或不是 `berth-*` 的不會
- [ ] vitest：確認框列出遺留物、移除鍵的狀態；連不到舊那台時的說明
- [ ] playwright 實跑換 qBittorrent，附截圖
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
