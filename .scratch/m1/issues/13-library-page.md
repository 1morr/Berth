# 13 — 媒體庫頁、版本清單與 Jellyfin 深連結

**Status:** ready-for-agent

**Blocked by:** 12

**讀:** plan §7、§11.2（T1.7）；brief §12、§13（媒體庫、Media 詳情）

## 做什麼

入庫的東西要看得見、點得進去播。媒體庫頁依 Route 分頁、卡片牆顯示已入庫作品與狀態，點卡片
深連結到 Jellyfin 播放；Media 詳情頁補上最後一塊——檔案清單與多版本並存清單。

深連結用 ledger 的 `jellyfin_item_id`；反查還沒完成或耗盡時要說明原因，不給死連結。

Berth 不做內嵌播放器（brief §12），播放一律交給 Jellyfin。

## 驗收

- [ ] `/library/:routeSlug` 依 Route 分頁，卡片牆顯示已入庫作品與狀態
- [ ] 篩選：有 Unmatched / 有待審（資料來源是 plan 與 ledger；Issue 篩選留 M2）
- [ ] 卡片深連結到 Jellyfin 的該作品；`jellyfin_item_id` 還沒反查到時說明原因而不是死連結
- [ ] Media 詳情頁補上檔案清單：每個檔案的季集、Tags、目標路徑、ledger 狀態
- [ ] Media 詳情頁補上多版本並存清單（brief §7.7；劇集經 MergeVersions 合併後顯示的是整個檔名主幹）
- [ ] Media 詳情的各集狀態反映實際入庫情形（已入庫 / 下載中 / 缺）
- [ ] 一條 Route 都還沒有東西時的空狀態說得出下一步該做什麼
- [ ] 媒體庫頁走 `/impeccable shape`；playwright 實跑並附結果
- [ ] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [ ] lint / type / test 全綠並貼指令輸出
