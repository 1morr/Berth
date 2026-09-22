# 14 — M1.5 critique 剩餘（P1 / P2）

**Status:** ready-for-agent

**Blocked by:** 06（「待審 / 對不到」的清單用 `/review` 那一個元件）

**讀:** plan §6（inventory 群組、search 群組）、§7、§11.2b（M1.5 的範圍與驗收）、§11.3 的票 13 那一列；`PRODUCT.md`、`.scratch/m1.5/library-shape.md`、`.scratch/m1.5/media-detail-shape.md`

## 做什麼

M1.5 票 11 的 critique 判為 P1 / P2、當時沒排進範圍的五件。

1. **「待審 / 對不到」篩出來的卡片要說為什麼在這**——`has_unmatched` 在 payload 裡卻沒畫。
   而且這一份**做成一列一件事的清單，不是牆**：篩出來的東西是「要處理的事」而不是「要看的作品」。
   用票 06 在 `/review` 建的那個元件（同一個 import；這一頁只放 `plan` 與 `unmatched` 兩類的子集）。
2. **媒體庫頁的前置內容收成「接著看 N 項」就地展開**（2026-09-22 拍板的二選一，沿用票 07 的
   `watching-shape` 慣例）。**首頁不動**——首頁上方放繼續觀看與下一集是 §11.2b 拍板過的。
3. **牆上按名字找**：`WallQuery` 加 `q` → Jellyfin 的 `SearchTerm`，寫進網址。
4. **詳情頁四個集數系統**至少在季表標題列說明這一份是哪一個；集號欄用 `S01E09` 的寫法。
5. **`InventoryTile` ↔ `EpisodeTile` 合併**——只有這一對值得合併，`MediaTile` 是離群值
   （票 13 已經把它改走 `ArtSlot`，不要順手把它一起併掉）。

## 驗收

- [ ] 「待審 / 對不到」是清單不是牆，每一列說得出為什麼在這（`has_unmatched` 畫出來了）
- [ ] 那份清單與 `/review` 是同一個元件（同一個 import，grep 佐證）
- [ ] 媒體庫頁前置內容是「接著看 N 項」一行、就地展開；首頁的兩排維持原樣（測試對兩頁各斷言一次）
- [ ] 牆上按名字找得動，關鍵字寫進網址、重整還在；空結果有像樣的空狀態
- [ ] 季表標題列說得出這一份集數是哪個系統；集號欄是 `S01E09` 的寫法
- [ ] `InventoryTile` 與 `EpisodeTile` 合併後只剩一個實作，`MediaTile` 沒被順手併掉
- [ ] playwright 實跑：篩選 → 清單 → 從一列按進處理入口；牆上搜一次名字，附截圖或文字結果
- [ ] lint、type、test 綠燈

## Comments
