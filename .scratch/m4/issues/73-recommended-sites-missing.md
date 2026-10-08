# 73 — 頁 4：Prowlarr 裡沒有推薦站時說出原因

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（與 67 的頁 4 改動同一區，後做的那張合併）

**讀:** `docs/research/linux-trial-2026-10-09.md` §3.1（04:54 那兩列）、§6、§7 L4；brief §20.14「原生 Linux、rootless Docker 實跑」的最後一條；`berth/services/indexer.py` 的 `add_recommended_indexers` 與 `DEFAULT_INDEXERS`；頁 4 套件內的元件；`PRODUCT.md`

## 為什麼

票 42 實跑時 Prowlarr 連不上 `indexers.prowlarr.com`（`IndexerDefinitionUpdateService: Definition update failed`，SSL EOF），只剩磁碟上的 5 個站定義（Anidex、Knaben、SubsPlease、showRSS、TorrentsCSV），推薦清單上的站一個都不在。結果：

- 頁 4 的「推薦站」區只剩標題「Recommended sites」與「Do this later」，**主鍵不見、也不說為什麼**；
- 直接打 `POST /api/setup/indexers/recommended` 回 200、`checks: []`：沒測、沒加、沒有理由。

使用者只看到少了一個按鈕。那一次的根因是 VM 自己的代理，但任何擋了那個網域的網路（公司防火牆、DNS 過濾、地區封鎖）都一樣。

**失效條件**：套件內 Prowlarr 的 `GET /api/v1/indexer/schema` 裡沒有推薦清單上任何一個 `definitionName`。

## 做什麼

1. 推薦清單上的站在 Prowlarr 的定義裡一個都找不到時，頁 4 說出來：Prowlarr 還沒拿到站的清單（多半是它連不上 `indexers.prowlarr.com`），去 Prowlarr 的 System → Logs 看、網路通了之後按「重新讀取」；同時保留「之後再說」與進階的逐站挑選。
2. 只找到一部分時，照現在的做法測找得到的那幾站，回報裡列出「Prowlarr 裡沒有這幾站」。
3. API 的回應帶得出這兩種情況（不要只是空的 `checks`），前端照它顯示；zh-Hant 與 en 並列。

## 驗收

- [ ] services 單元測試：schema 裡一個推薦站都沒有 → 結果標明「全部不在」；只有一部分 → 測找得到的、列出不在的（先寫紅燈）
- [ ] vitest：全部不在時頁 4 顯示原因與下一步，主鍵不消失得無聲無息
- [ ] playwright 實跑截圖（用演練伺服器或把套件內 Prowlarr 的定義目錄清空造情境）
- [ ] 全部檢查（`pre-commit run --all-files`）、test 綠燈
