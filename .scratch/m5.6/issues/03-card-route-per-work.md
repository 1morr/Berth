# 03 — 確認卡同一部作品只選一次 Route，加「全部套用」

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉A1、A2；研究文檔 §4 A；plan §6〈proposals〉、§7〈確認卡〉「Route 由人在卡片上選」；`DESIGN.md`

## 為什麼

「非人少女」的送單卡 13 列都是同一部作品，`preview.routes` 有 13 個 `RouteAsk`，使用者要點 13 個下拉，而且每個都選 Anime。

## 做什麼

1. 開工先對一次 Sonarr / Radarr 現行版本的 Manual Import（勾選的列整批設定 Series、Season、Quality），記在 Comments。
2. **A1**：卡片上有 `RouteAsk` 的列依 `media_id` 分組，每組一個 Route 選擇，套到那組勾著的每一列。預選照舊（這部作品上次用的）。沒勾的列不算。
3. **A2**：一張卡有兩部以上作品要選 Route，而且它們的可選 Route 有交集時，頂部多一個「全部套用」，選了就填進每一組，之後仍可逐組改。沒有交集就不畫。
4. 送出時 `routes` 照舊逐列展開，**API 與後端不動**。勾著的列沒選齊之前不畫確認鍵的規則不變。
5. 文案走 i18n（zh-Hant、en）；鍵盤操作得到。

## 驗收

- [ ] 13 列同一部作品的卡只有一個 Route 選擇，選一次就能確認，送出的 `routes` 是 13 個同值（vitest）
- [ ] 兩部作品、可選 Route 有交集時有「全部套用」，選了兩組都填上、之後可以單獨改；沒有交集時不出現（vitest）
- [ ] 取消勾選某些列後，送出的 `routes` 只在勾著的列有值
- [ ] playwright 實跑桌機與 390px，附截圖
- [ ] 全部檢查、vitest 綠；progress.md 已更新

## Comments
