# 14 — M1.5 critique 剩餘（P1 / P2）

**Status:** done

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

- [x] 「待審 / 對不到」是清單不是牆，每一列說得出為什麼在這（`has_unmatched` 畫出來了）——**字面改了**：列是審核佇列的 `plan` / `unmatched` 列，理由那一句就是「為什麼在這」；`has_unmatched` 旗標與佇列的定義不同、沒有消費點，刪掉（見 Comments 與 progress.md 偏差）
- [x] 那份清單與 `/review` 是同一個元件（同一個 import，grep 佐證）
- [x] 媒體庫頁前置內容是「接著看 N 項」一行、就地展開；首頁的兩排維持原樣（測試對兩頁各斷言一次）
- [x] 牆上按名字找得動，關鍵字寫進網址、重整還在；空結果有像樣的空狀態
- [x] 季表標題列說得出這一份集數是哪個系統；集號欄是 `S01E09` 的寫法
- [x] `InventoryTile` 與 `EpisodeTile` 合併後只剩一個實作，`MediaTile` 沒被順手併掉
- [x] playwright 實跑：篩選 → 清單 → 從一列按進處理入口；牆上搜一次名字，附截圖或文字結果
- [x] lint、type、test 綠燈

## Comments

- **2026-09-24 實作**（`abfe55a`…`1e36ec5`）。使用者拍板三件：兩個篩選只給 admin；子集由後端依 Route 篩（`GET /review?library=`）、篩選鍵數件不數部（與清單同一支查詢，`services/review.library_counts`）；牆上邊打邊搜、500ms 防抖、`replace` 寫網址。
- **同一個元件的佐證**：`grep -rn "from '../review/ReviewItem'" web/src` → `pages/InventoryPage.tsx:46`、`pages/ReviewPage.tsx:7`。`Tile` 只有 `inventory/InventoryTile.tsx` 與 `media/WatchArea.tsx`（集卡）兩個 import；`discover/MediaTile.tsx` 沒動。
- **`searchTerm` 在 12.1.0 實測**（`jellyfin_permissions.py --record --only items.tv.series.search.json`）：名字裡任一段、不分大小寫、照權限過濾、照 `sortBy` 排；打錯參數名被靜默忽略。已寫進 brief §20.8、研究 §3.1、fixture README。
- **playwright 實跑**（`--scenario library`，`skipper`）：1280 寬，TV 媒體庫「接著看 1 項」收成一行（y=218）；按「待審 1」→ 一列「待審核 流人 · 有檔案的季集要你確認」，核准並入庫 / 拒絕就地、下方「審核佇列裡還有 3 件」；「對不到 2」→ 兩列各一個修正表單，第一列按「套用」→ 那一列消失、篩選鍵變「對不到 1」、live region 念「已修正。」。牆上打 `bear` → 網址 `?q=bear`、只剩 The Bear、「還沒進 Jellyfin」收起、焦點留在搜尋框；重整還在。`?q=zzz` 在 390 寬：「這個媒體庫沒有符合篩選的作品。名字含「zzz」＋清除搜尋」，無橫向捲動；390 寬牆的第一格 y=475（critique 當時 y=889，帳號不同）。The Bear 詳情頁季表：「季與集照 TMDB 的編號…上面「觀看」的季與集是 Jellyfin 的，兩邊的編號可能不同。」、集號 `S01E01`…。截圖在 `.local/m2-14/`（不進 repo）。console 只有登入前那一個 401。
- **演練情境補資料**：`library` 情境的對不到那一列原本沒有 `job_files`、Slow Horses 的待審沒有 Plan，照新定義不會進佇列；補上（`7126327`）。
- **code-review**（Standards / Spec 兩軸）處理掉的：CONTEXT.md 的 Wall Query 與 Review Queue 詞條、程式碼與文檔裡沒加引號的「對不到」改回 `Unmatched`、`shown` → `adminFilter`、`Tile` 的 `url` → `art`、`everything` → `queue_total`、一般使用者從 API 讀得到件數（改成非 admin 回 0 也不數，補斷言）、清單被截斷時不說（照 `/review` 說）、搜尋時接著看收起沒有測試、`SEARCH_DEBOUNCE_MS` 的註解只講 TMDB。
- **沒處理（判斷題）**：
  - `services/review.py` 在 plan / unmatched 的六個函式上串了 `library_id: str | None`：現在只有一種範圍條件，第三種出現再改成傳一個條件物件。
  - `abfe55a` 一個 commit 帶了清單與搜尋兩件事（Standards 軸）：已經 commit，不改歷史。
  - 季表的說明在標題列**下方**一行，不在標題列裡（Spec 軸判可接受）：標題列放不下兩句話，窄版會擠掉季數。
  - `.impeccable/design.json` 的牆卡片描述仍寫 `MediaTile / InventoryTile`：它由 `/impeccable document` 產生，里程碑收尾（票 16）時一起刷新。
  - 媒體庫頁第一次來（沒有上一次的形狀）時「接著看」那一行晚一點出現，位移一行高——與票 13 的取捨相同。
