# 13 — 前端品質（M1.5 audit P1 / P2 + P3 九條）

**Status:** done

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

- [x] 1–17 每一條都有結果：修掉（附證據）或在 Comments 說明為什麼不修
- [x] 首頁與媒體庫的 CLS 實測 < 0.1（chrome-devtools 量，貼前後數字）——**有上一次的紀錄時**；第一次來仍是舊值（使用者拍板的取捨，見 Comments）
- [x] 每一條 a11y 修復有 vitest 斷言的是無障礙樹的結果（名稱、角色、`aria-current`），不是 class
      字串；每一條做一次變異驗證（改回去會紅）——第 2 條例外，見 Comments
- [x] 牆的 DOM 節點數實測下降（貼前後數字）
- [x] `Poster.tsx` 與 `ArtSlot.tsx` 合併後只剩一個實作（grep 佐證），`srcset` 實際有多個尺寸
- [x] `?filter=` 守衛擋得住不認得的值（兩個值各判一次，變異驗證會紅）
- [x] `.impeccable/design.json` 與 `DESIGN.md` 一致
- [x] playwright 實跑探索、媒體庫、詳情三頁，附截圖或文字結果
- [x] lint、type、test 綠燈

## Comments

### 量測（`--scenario library`、`deckhand`、chrome-devtools 的 `layout-shift` PerformanceObserver）

| | 開工時 `acf81d2` | 做完 |
| --- | --- | --- |
| 首頁 CLS（1280×800） | 0.3453 | 0（重新整理；第一次來沒有紀錄時 0.3451） |
| 首頁 CLS（視窗最窄 501px） | 0.4400 | 0 |
| `/library/item-movies` CLS（1280） | 0.1538 | 0（第一次來 0.1538） |
| 同一頁 DOM 節點（整頁 / `main`） | 1,732 / 1,702 | 931 / 901 |
| 同一頁 Tab 停留點 | 222 | 121 |
| `GET /api/inventory/item-movies` 傳輸量 | 53,739 B | 27,638 B |
| `bosun`（沒看過任何東西）首頁 CLS | 0（不畫） | 0（紀錄 `{0,0}`，不佔位） |

第一版佔位量到 0.0012：標題列比真的矮 5px（少了計數那一行 `text-xs`），補一個看不見的計數之後是 0。

### 每一條的結果

1. **修掉**，做法與票面不同（使用者拍板）：固定佔位只對 0 / 1 / 2 列其中一種剛好，佔多了下方整頁往上收一樣是 CLS，
   所以照「這個人在這一頁上一次的形狀」佔位（`watching/rememberedRows.ts`，`localStorage`，以使用者與頁面區分，讀不到就不佔）。
   **第一次來沒有紀錄時仍會位移**，這是取捨本身。
2. **修掉**：`NAV_LINK` 走 `data-[status=active]:`，四處都改（頁首、設定子分頁、媒體庫切換列；篩選列見 7）。**這一條的斷言比的是
   class**（`test/navState.ts`：當前與非當前兩格的 class 只能差 TanStack 的 `active` 標記）——缺陷本身不在無障礙樹上，
   `activeProps` 並不影響 `aria-current`，驗收第 3 條「不是 class 字串」對它做不到。三處各做了變異（改回 `activeProps` 會紅）；
   畫面上以 playwright 量計算後的邊框色（當前 `oklch(0.45 …)`、其餘 `oklch(0.74 …)`）。
3. **修掉**：四個卡片元件（`MediaTile`、`InventoryTile`、`WatchingTile`、`EpisodeTile`）。重複的控制項（Jellyfin 那一條、
   「標為已看」）名字帶上作品名；整格連結的名字是作品名，其餘是描述——原本整格的名字從「無海報 TV 2022」念起。每一處拿掉都會紅。
4. **修掉**：四面牆都是 `<ul>` / `<li>`、作品名都是 `<h3>`。
5. **修掉**：牆底那一組叫「牆底的分頁」。
6. **不另外修**：222 → 121 是第 9 條（一頁 50 部）的結果。剩下的每一個停留點都是不同的動作（開詳情、開 Jellyfin、標為已看），
   拿掉任何一個都是拿掉功能；跳過整面牆靠的是既有的 landmark（切換列、篩選、兩組分頁）與每一格的 `h3`（WCAG 2.4.1）。
   roving tabindex 會讓每一格裡的第二、三個動作要多一套方向鍵規則，沒有做。
7. 九條 P3（票面列了八條，第九條 `routes.cutaway.category` 的 zh-Hant 值在 `edae429` 已經是「分類」）：
   - 季表 `<caption>`：修掉（`sr-only`「S01 的每一集」）。
   - 篩選連結掛 `aria-current="page"`：修掉。選著的那一個改成 `aria-current="true"` 的字——TanStack 的 `Link` 當前時一定掛
     `"page"`（`applyLinkState` 在 `activeProps` 之後才設），`activeProps` 蓋不掉。
   - 排序方向只有 `aria-label`：修掉，看得見的「方向」。
   - `ExpandHint` 的字進可存取名稱而 `Dot` 不進：**不修**。「展開 / 收起」是看得見的字，拿出名字違反 WCAG 2.5.3（Label in Name），
     而 `<summary>` 在部分瀏覽器與報讀軟體組合上不暴露展開狀態（見第 8 條），那幾個字是唯一帶狀態的地方；`Dot` 是排版符號，不進名字才對。
   - 集表「片長」「播出」窄版：修掉，收進集名底下一行（`sm:hidden`）。
   - 三處 `alt="TMDB"`：修掉，一份 `TmdbAttribution`，替代文字走 i18n。
   - `TilePlaceholder` 跨目錄與內距：修掉（第 11 條）。
   - 庫存回應 `no-store` 無 `ETag`：見第 12 條。
8. **查了，不改**：ARIA in HTML 規定 `summary` 是 `details` 的第一個子元素時**不得指定任何 role**；HTML-AAM 讓各平台自己映射
   （MSAA / UIA 是按鈕加展開狀態、ATK 是 toggle button、AXAPI 是 disclosure triangle）。Playwright 的 `roleUtils` 沒有 `SUMMARY`
   這一項，所以 aria snapshot 印 `generic`——那是工具的表，不是瀏覽器的無障礙樹。硬加 `role="button"` 會讓 Safari / VoiceOver
   丟掉展開狀態、巢狀標題失去語意（Scott O'Hara、Adrian Roselli）。來源：w3.org/TR/html-aria、w3.org/TR/html-aam-1.0/#el-summary。
9. **修掉**：一頁 50 部（數字見上表）。零 memoization 沒有動——減半之後沒有量到要它的症狀。
10. **修掉**：`Poster.tsx` 刪除（`grep -rn "\bPoster\b" web/src` 只剩 `ArtSlot.tsx` 說它曾經存在的那一行註解，與 `schema.d.ts` 的欄位說明 `Poster Url`）；Berth 代理的圖多
    `poster_large` / `wide_large`（684 寬），TMDB 給 `w185`–`w780`，`sizes` 照牆的斷點（`WALL_SIZES`）或詳情頁那一欄。
11. **修掉**：`TilePlaceholder` 搬到 `components/`（`wallGrid.ts` 也搬了——四個目錄都在用它），每一行的高度照卡片抄。
12. **不做自己的快取規則**。圖片那一支能長快取，是因為網址帶著 `ImageTags`、換圖網址就變；庫存的內容（入庫狀態、這個人看到哪、
    標為已看之後那一格）換了，網址不變。`ETag` + `no-cache` 保得住正確，但伺服器每一次仍要問完 Jellyfin、算完整份才比得出 ETag，
    省的只是傳輸——而傳輸已經因為第 9 條減半到 27.6 KB（同機或區網）。要省傳輸，JSON 壓縮（目前沒有任何 `/api` 壓縮）是比 ETag
    便宜的一步，但沒有量到它造成的問題，這一票不做。
13. **修掉**：`isInventoryFilter` 一份。原因找到了：根路由不驗網址，子路由拿到的是根的原樣與自己驗過的合起來，**驗不過的那一格沒寫回
    `undefined` 就原樣留著**——`page=abc`、`sort=` 也一樣漏。`validateSearch` 改成每一格都寫回去，頁面那一道拿掉。
14. **修掉**：`i18n/displayRound.ts`，用 CONTEXT.md 的 **Display Round**。
15. **修掉**：`SearchQueriesOut.problem`（只有 `not_configured`），搜尋區塊按下去之前就畫 `IndexerNotice`，按了之後同一個位置只說一次。
16. **修掉**：缺集模式的 placeholder「留空就問缺的那幾集」。
17. **修掉，但只在有紀錄時說**：第 2 頁（與篩選）那個位置一行「繼續觀看與下一集只列在第 1 頁、沒有篩選的時候」加「到第 1 頁看」。
    那兩列在這些時候不問 Jellyfin，所以只有上一次的形狀可依據；從來沒看過東西的人、或新瀏覽器直接開 `?page=2` 時不說
    （code-review Spec 軸指出這一半沒蓋到，判斷是寧可少說一句也不對沒看過東西的人說一件與他無關的事）。
18. 見下方 `/impeccable document`。

### code-review（基準 `acf81d2`）

**Standards 軸處理了的**：`DETAIL_POSTER_SIZES` 插在 `IdentityBand` 的 JSDoc 與函式之間；DESIGN.md 的橫卡一節還寫著 `sr-only`
新分頁說明；三處用字串接 i18n 片段（`${name}${t('…newTab')}`、`片長 ${runtime}`）改成插值 key；新文字裡的「接著看」改成名詞表的說法
（CONTEXT.md 的 **Watching**，UI 是「繼續觀看與下一集」）；文字連結的 class 第三份抽成 `TEXT_LINK`；讀取紀錄的 hook 收成一份；
後端測試的名字與參數 id 對不上。

**Standards 軸記下、沒改的**：commit `b085c84` 的 body 寫了量測值、兩個 commit 的 scope 是 `web` 卻動了後端對外介面
（已推不回，記在這裡）；`RowPlaceholder` 與 `TilePlaceholder` 的格子形狀相近（兩種比例、不同行數，合一個要多一組參數）；
`TilePlaceholder inventory`、`Pager end` 兩個布林參數；**`PROXY_WIDTHS` 與後端 `IMAGE_SIZES`、`WALL_SIZES` 與 `WALL_GRID` 靠註解同步、
沒有測試守**——前者跨語言，後者要解析 Tailwind 類名，這一票不加閘門；改其中一邊的人要看那兩行註解。

**Spec 軸處理了的**：第 2 條原本只測頁首一處，改成 `test/navState.ts` 一份斷言、三處各一條、各做變異；progress.md 補偏差；
第九條 P3 的交代（見上）。

**Spec 軸記下、沒改的**：`useRememberedRows` 只在第一次畫時讀 key，`me` 那一刻若不在快取就這一次不佔位——`beforeLoad` 的
`requireSignedInPage` 已經 `fetchQuery` 過 `me`，目前走不到。

**`design.json` 的債第四次出現**（M1 票 11 / 13 / 14、M1.5 票 11、這一票）。它沒有閘門：一條比對 DESIGN.md 的 named rules、
Do / Don't 與 sidecar 的測試就能守住，但那是另一件事，沒有排進這一票。
