# 05 — 牆上的觀看狀態與已看切換

**Status:** ready-for-agent

**Blocked by:** 03

**讀:** plan §11.2b；brief §12、§20.8（已看 / 未看）；`docs/research/library-browsing.md` §1.2（`UserData` 欄位）、
§5；票 01 的結論（Series / Season 標記是否遞迴）；`.scratch/m1.5/library-shape.md`

## 做什麼

媒體庫牆的卡片說得出這位使用者看到哪了：已看、看到一半、還剩幾集沒看；並且可以就地切換，寫回 Jellyfin
該使用者的紀錄。這是 M1.5 第一條**寫入** Jellyfin 使用者資料的路徑。

- 讀：`/Items?userId=` 帶 `UserData`。欄位不是每筆都有（`PlayedPercentage` 只在看到一半或 folder 出現、
  `UnplayedItemCount` 只在 folder），缺欄位當 0 / null（研究 §1.2）。
- 寫：`POST` / `DELETE /UserPlayedItems/{id}?userId=`，是 services 裡的命令函式，`userId` 取自 session。
  Jellyfin 對這位使用者看不到的項目回 404，Berth 照實轉成拒絕。
- **標為未看不可逆**：`PlayCount` 歸零、`LastPlayedDate` 消失（研究 §5）。送出前要確認，不提供「復原」。
- 劇集整部標記是否遞迴到每一集，以票 01 的實測為準。

票 08 的觀看區會在各集上重用同一個命令。

## 驗收

- [ ] 卡片顯示已看 / 看到一半 / 剩幾集沒看三種狀態，不只靠顏色
- [ ] 卡片上可標為已看、標為未看；標為未看先確認，確認文案說得出會清掉觀看次數與時間
- [ ] 寫入是 services 的命令；整合測試證明：`userId` 取自 session、對看不到的項目被拒且 Jellyfin 端沒有被寫
- [ ] 契約測試：`UserData` 缺欄位時的解析、`UserPlayedItems` 兩個方向的回應（票 01 的 fixture）
- [ ] 切換之後牆上的狀態更新，不必重新整理
- [ ] `CONTEXT.md` 補上觀看狀態的名詞
- [ ] playwright 實跑：標已看、標未看（含確認）各一次，附結果；鍵盤可完成；390px 與深淺兩主題
- [ ] lint / type / test 全綠並貼指令輸出
