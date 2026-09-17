# 05 — 牆上的觀看狀態與已看切換

**Status:** done

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

- [x] 卡片顯示已看 / 看到一半 / 剩幾集沒看三種狀態，不只靠顏色
- [x] 卡片上可標為已看、標為未看；標為未看先確認，確認文案說得出會清掉觀看次數與時間
- [x] 寫入是 services 的命令；整合測試證明：`userId` 取自 session、對看不到的項目被拒且 Jellyfin 端沒有被寫
- [x] 契約測試：`UserData` 缺欄位時的解析、`UserPlayedItems` 兩個方向的回應（票 01 的 fixture）
- [x] 切換之後牆上的狀態更新，不必重新整理
- [x] `CONTEXT.md` 補上觀看狀態的名詞
- [x] playwright 實跑：標已看、標未看（含確認）各一次，附結果；鍵盤可完成；390px 與深淺兩主題
- [x] lint / type / test 全綠並貼指令輸出

## Comments

- 2026-09-17 判定照 jellyfin-web 卡片（v10.11.11 `components/indicators`，研究 §7.1）：劇集只要 `UnplayedItemCount` 非 0
  就說「剩 N 集沒看」——**沒開始看的劇也說**；「看到 N%」只給影片（夾在 1–99）；`Played` 或 `PlayedPercentage >= 100`
  是已看，已看優先。資料夾才有 `UnplayedItemCount`（研究 §1.2），所以寫入的回應（只有 `UserData`）也分得出劇集與影片
  （`services/watch.py`）。切換鍵照 jellyfin-web 只看 `played`：看到一半的片、剩幾集的劇只給「標為已看」。
- 2026-09-17 介面：`POST` / `DELETE /api/jellyfin/items/{item_id}/played` → `WatchStateOut`。動詞成對沿用 Jellyfin 的
  `/UserPlayedItems/{id}`、使用者不在網址上（GitHub `PUT|DELETE /user/starred/...`）。命令是 `JellyfinAccess.mark_played`
  （`services/jellyfin_access.py`），`userId` 只從 session；**不先查可見性**：`UserPlayedItems` 自己查，404 → 拒絕
  `item_not_visible`。`api/inventory.py` 的 `_user` / `_refusal` 搬到 `api/jellyfin.py` 兩邊共用（`session_user`、
  `access_refusal`），前端 `inventoryRefusal` → `accessRefusal`。寫完拿回應 `setQueriesData` 改那一格、不重抓牆
  （jellyfin-web 收到 `UserDataChanged` 也是就地改）。`apiDelete` 改成泛型（這一支回 body）。
- 2026-09-17 **`tracked` 與還沒進 Jellyfin 的卡片 `watch` 是 `null`**：「待審」「Unmatched」篩選後的牆沒有觀看狀態與切換鍵。
  那一份來自 `library_index`（`enableUserData=false`）；要帶就是整個媒體庫每一部都要一份觀看紀錄，代價沒量，而那一份是
  Berth 的工作清單。偏差記在 progress.md。
- 2026-09-17 替身 Jellyfin：每個帳號記看過的集 / 電影與看到一半的百分比，劇集的紀錄由它的集算；`mark_played` 對看不到的
  item 回 404 不寫入、對劇集遞迴、清掉看到一半的位置。演練情境 `library` 每部劇 6 集，`deckhand` / `skipper` 各看過一些。
- 2026-09-17 playwright 對 `--scenario library` 實跑（`deckhand`，一般使用者）：
  - 1280 滑鼠：The Bear「剩 3 集沒看」→ 標為已看 → 「已看」，網路只多一支 `POST …/played` 200，牆沒重抓；Movies 第二頁
    Oppenheimer「看到 42%」；Harbour Film 001 標為未看 → 確認文案「會清掉你看這部片的觀看次數與最後觀看時間，清掉就找
    不回來。」→ 取消（沒有送出）→ 再開 → 確認 → 一支 `DELETE` 200，卡片沒有觀看那一行、鍵換回「標為已看」。
  - 1280 鍵盤：Breaking Bad（已看）Enter → 焦點進確認 group（名字是劇集那段文案，說得出「每一集」）→ Tab → Enter →
    「剩 6 集沒看」。**抓到確認送出之後焦點掉到 `body`**：送出中鍵被 `disabled`，接不住 `useInPlaceConfirm` 送回的焦點。
    改成 `aria-disabled` + 送出中忽略點擊，vitest 補焦點斷言（改回 `disabled` 會紅）；重跑 Game of Thrones 兩個方向，
    焦點都留在那一顆鍵上。
  - 390px × 深 / 淺：The Office 標已看 → 標未看（確認）→ 「剩 6 集沒看」；`scrollWidth == clientWidth`（375，無橫向捲動）；
    卡片 163px 寬，確認區塊兩顆鍵疊一欄；EN 介面「Mark watched / Mark unwatched」鍵 121×24、卡片內除 `sr-only` 外沒有
    溢出。新文字對比：深 16.20:1、淺 13.31:1（切換鍵與觀看那一行，canvas 換算 oklch）。截圖在 `.playwright-mcp/`（不進版控）。
  - 沒在瀏覽器裡實跑：寫入失敗（404 / 503）的訊息與 401 送回登入頁，只有 vitest。
- 2026-09-17 code-review 處理了的：**Standards**——寫入失敗的訊息改成說下一步、Jellyfin 問不到時貼服務原文（PRODUCT
  原則 4，補測試）；API 層不再碰 adapter 型別，`mark_played` 直接回 `WatchState`；`InventoryRefusal` 改名
  `AccessRefusal`（它也裝 `item_not_visible`）；替身去掉重複的帳號反查與媒體庫可見性、404 訊息照方法印；兩處把「讀回確認」
  錯引成研究 §5 的註解改成 §2 的表；演練資料的註解與 README 補齊。**Spec**——Series 標記的回應沒有錄 fixture：讀 v12.0
  `PlaystateController` 確認兩個方向都回 `GetUserDataDto(item, user)`，與實測的標為已看同一形狀（帶 `UnplayedItemCount`），
  寫進研究 §5。
- 2026-09-17 **沒處理**（判斷題 / 待拍板）：
  - **標為已看不確認**，而它會把看到一半的位置歸零（劇集是每一集）；要清掉「看到一半」的紀錄得先標已看再標未看。
    與 jellyfin-web 相同，票面只要求標為未看確認——這個副作用沒人拍板過，票 08 做各集時再問。
  - `api/jellyfin.py` 同時放圖、已看與兩邊共用的 `access_refusal`（Divergent Change）；`mark_played(played=False)` 的布林旗標；
    `libraryId` 從 `InventoryTile` 穿到 `WatchToggle` 只為組快取鍵（用 `['inventory']` 前綴就得在更新函式裡分辨切換列那份
    陣列）；演練資料三張表。
