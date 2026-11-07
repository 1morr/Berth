# 03 — 確認卡同一部作品只選一次 Route，加「全部套用」

**Status:** done

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

- [x] 13 列同一部作品的卡只有一個 Route 選擇，選一次就能確認，送出的 `routes` 是 13 個同值（vitest）
- [x] 兩部作品、可選 Route 有交集時有「全部套用」，選了兩組都填上、之後可以單獨改；沒有交集時不出現（vitest）
- [x] 取消勾選某些列後，送出的 `routes` 只在勾著的列有值
- [x] playwright 實跑桌機與 390px，附截圖
- [x] 全部檢查、vitest 綠；progress.md 已更新

## Comments


**開工對 Sonarr / Radarr 現行版（2026-11-07，`develop` 分支原始碼）**

- Sonarr v4 的 Manual Import → Interactive Import 有一支批次下拉（`bulkSelectOptions`）：Select Series、Season、
  Episodes、Quality、Release Group、Language、Indexer Flags、Release Type，套用到**所有勾選的列**，不逐列重選；
  勾選的列沒有作品時 Season / Episodes 停用，勾選的列季號不一致時 Episodes 停用。
  `frontend/src/InteractiveImport/Interactive/InteractiveImportModalContent.tsx`。
- Radarr 同一支檔案也有批次下拉（Select Movie、Quality、Language 等）。Servarr wiki 的 Manual Import 一節沒寫批次，
  畫面行為以原始碼為準。
- Sonarr issue #4089 的教訓：批次改 quality 會重新解析，清掉先前逐列選的 season；所以順序是 series → season →
  episodes → quality。我們的 Route 是每組獨立的值，勾選變動不會重算列，沒有這個順序問題。

**實作取捨**

- 一組一個選擇放在卡片上方（多部作品時標「<作品> 的 Route」）；列裡的 Route 那一格只重述那一組選的那一條，
  不再是下拉。整組沒勾的作品不必選，選擇留著（勾回來時不跳版面）。
- 「全部套用」只在兩組以上、而且交集非空時畫，選項只列交集；每組選的一致時它顯示那個值，有人單獨改過就回到空。
- 送出照舊逐列展開、未勾的列送 `null`；`decide`、Proposal 與後端不動。

**驗證**

- vitest（`ConfirmCard.test.tsx`〈one route choice per work〉）：13 列一部作品一個選擇、送出 13 個同值；兩部作品交集
  有「全部套用」、填滿後可單改；無交集不畫；整組未勾不擋確認。
- e2e 實跑 `agent` 與 `agent-390`：三列同一部作品的送單卡現在只有一個 Route 選擇，截圖在
  `web/test-results/agent-送單卡…-agent{,-390}/`（`card.png`、`route-unpicked.png`、`route-picked.png`）。
- **「全部套用」的實跑**：替身情境只有一部作品，所以用一次暫存的 playwright spec（`page.route` 給一張兩部作品的
  卡，其餘走真 server 與真前端）在 1280 與 390 跑：三個下拉（全部套用、兩部作品各一）、兩部作品名在標籤上、
  套用後兩組都是 Anime、單改 Frieren 之後全部套用回到空。截圖複本 `.playwright-mcp/t03-apply-all-{1280,390}.png`
  與 `t03-apply-all-changed-{1280,390}.png`（不進 repo）。暫存 spec 跑完已刪；替身情境要長期守這一條時在票 10 加
  第二部作品。
- **code-review 修掉的**：英文文案用 work（不是 title）、作品名還沒讀到時標籤只寫 Route（不印 `media_id`）、
  `media_id` 的窄化只留一處、「全部套用」的空白項不可選且不必選（`required` 只在一組的下拉）、命名
  （`RouteChoices`、`sharedPick`）。未修：`ConfirmCard.tsx` 已超過 1000 行（既有問題，票 10 的 UI 收尾再看）。
