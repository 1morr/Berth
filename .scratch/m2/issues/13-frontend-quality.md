# 13 — 前端品質（M1.5 audit P1 / P2 + P3 九條）

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** plan §7（前端那一節，WCAG 2.2 AA 是驗收條件）、§6（inventory 群組）、§11.3 的票 12 那一列與遺留清單 A 組的 P3 九條；`DESIGN.md`、`PRODUCT.md`

## 做什麼

M1.5 的 audit 與 critique 留下的前端品質項，加上 P3 九條，加上落在**探索 / 媒體庫 / 詳情**這一群的
收尾小項。WCAG 2.2 AA 是 plan §7 寫死的驗收條件，所以 a11y 那幾條不是可選的。

**版面穩定（P1）**

1. 首頁 CLS **0.3553**、媒體庫 **0.1605**：`WatchingRows` 讀取中回 `null`，資料回來後插在上方
   整頁下移 440px。改成 `MediaDetailPage` 的 `Loading()` 那種**不動的佔位**。

**a11y（P1 / P2 / P3）**

2. `activeProps` 讓 `border-rule` 與 `border-rule-strong` 同時出現（`AppShell.tsx`、
   `InventoryPage.tsx` 兩處、`SettingsTabs.tsx`）——改走 TanStack 的 `data-status="active"`。
3. **重複控制項的可存取名稱**：四個卡片元件用 `aria-label` 帶上作品名（2026-09-22 拍板的二選一：
   改四處，不走「接受並記進 `DESIGN.md`」）。
4. 兩頁清單語意相反：媒體庫牆 `<h3>` 而探索牆 `<p>`、容器是 `<div>` 而繼續觀看是 `<ul>`。統一。
5. 同一頁兩個 `<nav aria-label="分頁">`。
6. 電影牆 **222 個 Tab 停留點**。
7. 季表沒 `<caption>`；篩選連結掛 `aria-current="page"`；排序方向 `<select>` 只有 `aria-label`；
   `ExpandHint` 的字進可存取名稱而 `Dot` 不進；集表「片長」「播出」在 <640px 沒有替代路徑；
   三處硬寫 `alt="TMDB"`。
8. `<summary>` 在無障礙樹是 `generic` 不是 `button[expanded]`——全站 `<details>` 的共同問題，
   **查一次**能不能用 `role` 補（查不到就記進 Comments，不要硬改成 div）。

**效能與元件**

9. 牆 1,621 個 DOM 節點、零 memoization：`page_size` 100 → 50 先做。
10. `ArtSlot` 寫死 342px 無 `srcset`；`Poster.tsx` 與 `ArtSlot.tsx` 合併（`ArtSlot` 多收 `className`）。
11. `TilePlaceholder` 跨目錄 import 且內距差 4px。
12. 庫存回應 53 KB、`no-store` 無 `ETag`（門禁對 `/api` 一律 `no-store` 是正確性，不動它；
    這裡要問的是這一支能不能像圖片那一支一樣有自己的規則）。

**型別與命名**

13. `?filter=` 抽共用型別守衛（`validateSearch` 擋不住，M1.5 票 11 修過一次症狀）。
14. `i18n/tmdbText.ts` 改名——它從票 11 起也挑圖，名字只說了一半。

**說得出後果**

15. 沒接索引站時 `GET /search/queries` 先帶 `problem`（後端加，前端顯示）。
16. 缺集搜之後關鍵字欄的 placeholder 仍說「留空就用這部作品的各個名字」。
17. `?page=2` 不畫兩列但畫面沒說。

**設計系統**

18. `/impeccable document` 把 `.impeccable/design.json` 追上 `DESIGN.md`——M1.5 票 11 改了後者
    沒動前者，M1 票 11 / 13 / 14 的同一個債重現。這一條放最後做。

## 驗收

- [ ] 1–17 每一條都有結果：修掉（附證據）或在 Comments 說明為什麼不修
- [ ] 首頁與媒體庫的 CLS 實測 < 0.1（chrome-devtools 量，貼前後數字）
- [ ] 每一條 a11y 修復有 vitest 斷言的是無障礙樹的結果（名稱、角色、`aria-current`），不是 class
      字串；每一條做一次變異驗證（改回去會紅）
- [ ] 牆的 DOM 節點數實測下降（貼前後數字）
- [ ] `Poster.tsx` 與 `ArtSlot.tsx` 合併後只剩一個實作（grep 佐證），`srcset` 實際有多個尺寸
- [ ] `?filter=` 守衛擋得住不認得的值（兩個值各判一次，變異驗證會紅）
- [ ] `.impeccable/design.json` 與 `DESIGN.md` 一致
- [ ] playwright 實跑探索、媒體庫、詳情三頁，附截圖或文字結果
- [ ] lint、type、test 綠燈

## Comments
