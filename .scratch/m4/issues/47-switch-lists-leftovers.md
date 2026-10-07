# 47 — 換一台 qBittorrent / Prowlarr 時列出 Berth 在舊那台留下的東西

**Status:** done

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

- [x] 整合測試：確認框的清單只含 Berth 擁有的物件；使用者自己的分類不出現
- [x] 整合測試（雙向）：空的 `berth-*` 分類會被移除；有 torrent 的、或不是 `berth-*` 的不會
- [x] vitest：確認框列出遺留物、移除鍵的狀態；連不到舊那台時的說明
- [x] playwright 實跑換 qBittorrent，附截圖（演練情境 `healthy`，設定頁 → qBittorrent 換既有：`.playwright-mcp/t47-switch-leftovers.png`、`t47-switch-leftovers-removed.png`，目錄不進版控）
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

code-review（2026-10-07）已處理：白名單 `remove_categories` 補雙向變異測試；`IRREVERSIBLE` 的註解改說為什麼回不去；Route 分類查詢共用 `qbittorrent.route_categories`；元件改名 `LeftoverList`；清單 `gcTime: 0`（換台後再開確認框不會先畫上一台的清單、移除鍵對錯台）；移除連不到改成 502、畫面說「沒有移除」。

未處理（記著）：

- **移除與送單之間沒有鎖**：`jobs` 剛 `ensure_category`、還沒 `torrents/add` 時分類被刪，qBittorrent 收 add 時可能自己建一個用預設路徑的同名分類（沒查證）。時間窗只在使用者於設定頁換台確認框按移除、同時有送單的那一刻；要擋得在送單與移除之間共用鎖。
- **Prowlarr 連得到時以 `definitionName` 比對**：使用者在 Berth 加過之後自己刪掉、又以同一個定義加回來，會被列成 Berth 加的。只列不刪，影響是多列一列。
- **連不到 qBittorrent 時列的是全部 Route 的分類**：換過台之後新那台若從沒跑過 Route 檢查，其實沒建過；文案說的是「Berth 記得建過、確認不了現況」。
- `choice.switchAway.prowlarr` 與 `choice.switchWarning.prowlarr` 現在同一句：`ServiceChoice` 以 `choice.switchAway.${kind}` 動態取鍵，收斂要改那一段，不在本票。
- 精靈頁 4 換台的判準仍是 `hasResults`（頁 4 的纜繩），頁 2 改成選過就確認：既有 Prowlarr 一連上就有纜繩，加站也記在纜繩，兩者實際上等價。
