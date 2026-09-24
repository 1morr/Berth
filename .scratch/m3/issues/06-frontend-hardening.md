# 06 — 前端硬化 + 探索頁只放 TMDB 牆 + M2 收尾遺留

**Status:** done

**Blocked by:** None — can start immediately（跟 05 一樣動到審核頁，接在 05 之後做衝突最少）

**讀:** plan §11.4（修補清單的「前端」那一條與「兩個頁面決定」）、§7；brief §13、§19（2026-09-24「M2 後的全面審查」）；`.scratch/m2/issues/16-m2-acceptance.md` 的 Comments（P2 / P3 沒修的那兩段）；`DESIGN.md`

## 做什麼

**四條前端硬化**（plan §11.4）：

- 逐列編輯還有沒套用的改動時，「核准並入庫」要擋住，並說出原因。
- 核准、撤銷、修 Issue 之後讓 `['media']` 失效；現在詳情頁的入庫狀態要等手動重新整理才會變。
- 任何請求回 401 就導回登入頁，登入後回到原本那一頁。
- 動作鍵送出中不可再按（M2 票 16 的 P3 也點到了 `disabled` 對 `aria-disabled`，一起決定）。

**探索頁只放 TMDB 牆**（brief §19 同日①）：拿掉繼續觀看與下一集，這兩列只在媒體庫頁；登入後預設落在媒體庫。`GET /jellyfin/watching` 的消費點若因此歸零，連同它的測試一起刪。brief §13 的探索頁那一列同步。

**M2 票 16 的遺留**（使用者拍板放進這一票）：票 16 Comments 裡「P2 沒修」與「P3 沒修」兩段約 17 條，逐條分成「修掉」「不做（附理由）」「延後（寫進 plan §11.3 D 組）」，結果記在本票的 Comments。其中 **JS bundle 746 KB** 至少要量一次路由拆分的效果再決定。

## 驗收

- [x] 四條硬化各有一條前端測試（拿掉修正會紅）
- [x] 探索頁沒有繼續觀看與下一集；登入後落在媒體庫；沒有消費點的端點與測試已刪；brief §13 同步
- [x] 票 16 遺留逐條有結論，記在本票 Comments；bundle 大小附前後數字
- [x] playwright 實跑探索、登入落點、審核頁擋核准，1280 與 390，附結果
- [x] lint、type、test 綠燈

## Comments

### 四條硬化與頁面決定（2026-09-25）

- **擋核准**：`PlanEditor` 的表單回報「改了沒套用」（與打開那一刻的值比，只是打開看一眼不擋），`PlanRow` 按「核准並入庫」時不送、說出是哪幾列（`review.plan.unapplied`，檔名以 `Intl.ListFormat` 串）。取消、套用成功、整組收合之後不再算。
- **`['media']` 失效**：核准（`PlanRow`）、撤銷與確認（`AuditRow`）、整組 / 整段確認（`useConfirmAudits`）、修好 Issue（`IssueRow`）。rematch、重複版本、刪除本來就有。**沒做**：入庫是背景的，核准之後幾秒才真的入庫；那時正開著詳情頁的人要等 5 分鐘 staleTime 或重新整理——詳情頁沒有訂 SSE。有 repro 再讓 `useJobStream` 也失效 `['media']`、掛到詳情頁。
- **401**：`router.ts` 訂閱兩份快取，任何查詢或 mutation 回 401 就重跑路由守衛（`/auth/me` 的 401 由守衛自己處置、登入那一支是帳密不對，兩者排除）。每頁各自的 `SessionEnded` 與 `WatchToggle` 的 401 分支刪掉。code-review 抓到：正式的 `QueryClient` 預設重試三次，401 也重試的話要七秒才導走——預設重試與 `retryUnlessRefused` 都改成不重試 401（`signedOut`，`router.test.tsx` 用正式的 client 守著）。
- **送出中不可再按，`disabled` 對 `aria-disabled` 定案**：`PrimaryButton` / `GhostButton` 的 `busy` 給 `aria-disabled`、吞掉點擊（連欄位裡 Enter 的隱式送出），焦點留在原地；`disabled` 只留給「現在不成立」。原本沒擋的：Job 的重試 / 重新規劃 / 重新入庫、送單的確認鍵、搜尋、重抓 TMDB、Jellyfin 位址的儲存；其餘約三十處 `disabled={pending}` 一起換成 `busy`。
- **登入落點**：`destination()` 沒有去處時是 `/library`；第一次開 `/` 不記下 `/`（那是打開 Berth 的網址，不是要回探索頁），用到一半被踢出來的才記。
- **探索頁**：`HomeWatching` 與它的佔位、`homeWatchingQueryOptions`、`watching.down` / `retry` 文案刪掉；首頁上測 `WatchingRow` 本身的五條搬到媒體庫頁（展開「接著看」之後）。後端 `GET /jellyfin/watching`、`read_watching` / adapter 的「不帶媒體庫」分支、ACCESS 表那一列與首頁的測試一起刪（2342 passed）。

測試：每一條拿掉修正都跑過一次（腳本改回一行、跑那一檔）——擋核准、四處 `['media']`、401、`busy`（點擊與 Enter）、登入落點、`/` 不記下，全部轉紅。

### M2 票 16 的遺留（17 條）

**修掉**
1. audit P2：`RematchEntry` 與 `PlanEditor` 打開時焦點進到表單（`autoFocus`；`/review` 攤在列上的對不到那一種不搶焦點）。
2. audit P2：`JobDelete` 的結果 live region 一直掛著（`role="status"`，空的時候 `empty:mt-0`）。
3. audit P2：`QueueRow`「展開」命中區 11px → `min-h-6`（實測 24px）。
4. audit P3：`/jobs` 的 h1 用 `PAGE_TITLE`。
5. audit P3：`/review` 段標題的計數念成「2 件」。
6. audit P3：送出中的鍵 `disabled` → `aria-disabled`（上面「送出中」那一條）。
7. audit P3：`/issues` 進頁問兩次 `GET /issues`——`ReconcileBanner` 第一次讀到的那一輪也讓清單失效；改成只記下來。
8. audit P3：bundle。**壓縮做了、路由拆分量了不做**。數字：票 16 量到 746 KB；這一票開工時 759.82 kB（gzip 218.76 kB）。加 `GZipMiddleware` 之後實際傳輸 759,826 → 215,747 bytes（`review` 情境 curl 實測）。路由拆分（`lazyRouteComponent` 包 13 個頁面）入口 chunk 759.82 → 457.83 kB（gzip 218.76 → 147.19 kB），首次載入省約 70 kB gzip。**不做的理由**：壓縮之後剩下的差距在區網上看不出來；而大部分頁面包在 `AppShell` 裡，要拆又不讓頁首在載入 chunk 時閃掉，得把 `AppShell` 改成版面路由（route id 全換）或每頁各包一層，這個複雜度換 70 kB 不值。入口裡約 1/3 是兩種語言的文案，真要再減從那裡下手。
9. critique P2：同一張計劃卡上兩個同名「展開」——`QueueRow` 的「展開」可存取名稱接上這一件的標題（`aria-labelledby`）。
10. critique P2：「改」「修正」離檔名約 1100px——檔名那一欄不再撐滿那一行（實測「改」緊接在檔名後 8px）。
11. code-review：`test_auth_api.py` 從 unit 測試模組 import `api_endpoints`——移到 `tests/endpoints.py`。

**不做**
12. audit P2：`/review` 的 CLS 0.08–0.097——低於 0.1；計劃表的高度隨列數（1 到 39 列）變，固定佔位只對其中一種剛好。

**延後（寫進 plan §11.3 D 組）**
13. audit P2：Job 摘要列只浮上 audit，對不到與重複待決沒有（要後端多兩個計數）。
14. audit P3：佇列列是絕對時間、Job 頁是相對時間；15. code-review：`whenText` 與 `Timestamp` 各自格式化——同一件事，先定全站慣例。
16. code-review：七處欄位的 class 字串手寫；17. code-review：輸入框 `rule-strong` 的規則沒有閘門——下一次改輸入框外觀時收成常量，閘門就是「都用它」。

### playwright 實跑（`review` 情境，1280 與 390）

- 登出之後開 `/` → `/login`（沒有 `redirect`）→ 登入落在 `/library/item-movies`；兩個寬度都一樣。
- 探索頁只有「本週趨勢」「熱門」兩個區塊，沒有打任何 `watching` 請求；390 無橫向捲動。
- 審核頁：「改」SPY×FAMILY - 05 → 焦點在「處置」→ 改季 → 按「核准並入庫」→ 那一列留著，`alert`：「還有改動沒有套用，先按「套用」或「取消」：[ANi] SPY×FAMILY - 05 …mkv」；「展開」的名字是「展開 SPY×FAMILY 間諜家家酒」、高 24px；390 無橫向捲動。
- `/jobs` 的 h1 是 `PAGE_TITLE`；Job 詳情的 `role="status"` 在刪除前就在、高 0、無外距。
- `pnpm -C web e2e` 4 passed。截圖在 session scratchpad，不進 repo。

### code-review 未處理的發現（基準 `4b167c6`）

已修：壓縮測試那一條名不符實（401 不到壓縮門檻）刪掉並改正註解；`busy` 的 Enter 路徑補測試（拿掉 `preventDefault` 兩條紅）；擋核准那一句改走 i18n 插值與 `Intl.ListFormat`；DESIGN.md 的 `QueueRow` 摘要與 `JobDelete` 結果那一行；401 重試（上面）；D 組三條與壓縮的架構決定寫進 plan。

判斷題、沒改：
- `['media']` 失效散在六處（這一票加了四處），各帶一句同樣的理由；要收成 `api/media.ts` 的一支 helper 時連 rematch / 刪除 / 重複版本一起收。
- `router.ts` 兩段 `subscribe` 形狀幾乎一樣；`controls.tsx` 兩顆按鈕各寫一次 `aria-disabled:` 的停用外觀。
- `watching_out` 只剩 `api/inventory.py` 在用，仍住在 `api/jellyfin.py`。
- `onUnapplied` 從 `PlanEditor` 往下傳三層；再多一層就該改 context。
- DESIGN.md「送出中用 `busy`」沒有靜態閘門，靠各頁的測試；要收成規則時補一條掃 `disabled={…Pending}` 的測試。
- 契約測試的 `useritems-resume.watching.json` 是不帶 `parentId` 錄的，現在呼叫都帶 `parentId`，respx 只比對路徑——「帶了真的會過濾」沒有被這幾條驗到（M1.5 票 07 的研究實測過）。
