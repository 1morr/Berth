# 06 — 媒體庫牆的排序與類型、年份篩選

**Status:** done

**Blocked by:** 03

**讀:** plan §11.2b；brief §13（媒體庫）、§20.8（排序與篩選）；`docs/research/library-browsing.md` §2（`/Items/Filters`
那一列）、§3、§7（劇集庫、電影庫、篩選面板）；票 01 的結論；`.scratch/m1.5/library-shape.md`

## 做什麼

媒體庫牆可以依 Jellyfin 的慣例排序，並依類型與年份篩選。沿用 jellyfin-web 的做法（研究 §7），不自己發明：

- 排序：劇集庫與電影庫的選項不同（劇集有「新集加入」`DateLastContentAdded`、「最近看過」`SeriesDatePlayed`），
  每個排序鍵後面接 `SortName`，可切升降冪。
- 類型與年份清單來自 `GET /Items/Filters?userId=&parentId=&includeItemTypes=`（三版形狀一致、含年份）；
  `genres` 以 `|` 分隔、`years` 以逗號。
- `/Items/Filters` 帶 `parentId` 時 Jellyfin **不套**媒體庫權限（研究 §2），所以只能在票 03 的閘門驗過媒體庫 id
  之後呼叫。
- `/Items` 會靜默忽略打錯的參數：每個參數都要有「伺服器真的有過濾」的測試，而不只是「請求送出去了」。

排序與篩選的狀態放在網址上，與票 03 保留的「待審」「Unmatched」篩選並存；兩者怎麼組合、還沒進 Jellyfin 的作品
在篩選下怎麼呈現，照票 03 的 shape。

## 驗收

- [x] 劇集庫與電影庫各有自己的排序選項（對照研究 §7），可切升降冪
- [x] 類型、年份篩選的清單來自 `/Items/Filters`，只列這個媒體庫有的；可多選
- [x] 排序與篩選的狀態在網址上，重新整理與分享連結都還原得回來；與分頁一起正確運作
- [x] 契約測試：`sortBy`、`sortOrder`、`genres`、`years` 各自證明伺服器真的有過濾或排序（票 01 的實測或錄製）
- [x] 整合測試：對不在允許清單的媒體庫取篩選清單被拒且沒有轉發
- [x] 篩選後沒有結果時說得出原因與怎麼清掉篩選
- [x] playwright 實跑：劇集庫與電影庫各排序一次、篩選一次，附結果；鍵盤可完成；390px 與深淺兩主題
- [x] lint / type / test 全綠並貼指令輸出

## Comments

- 2026-09-17 實跑（playwright，`fake_setup_server.py --scenario library`，`deckhand`）：
  - **劇集庫**：評分遞減 → Breaking Bad 8.9、The Office / Shōgun 8.6、Game of Thrones 8.5、The Bear 8.2、Slow Horses 8.1，
    沒有評分的 Home Videos 2019 最後；鍵盤 Tab 順序「排序 → 排序方向 → 類型 → 年份 → 清單」，Enter 打開類型、Space 勾選，
    換網址之後焦點仍在那一格，帶子收起、分頁 `1–2 / 2`；重新整理（`genres=["Fantasy","War+&+Politics"]`）排序、方向與勾選都還原。
    待審：網址保留 `sort` 與 `genres`、控制項不畫，按「全部」回原本那一頁，整段只有兩個牆的請求（沒有重抓）。
    `?sort=DatePlayed`（電影庫才有）：選單顯示「名稱」，請求不帶 `sort`。
  - **電影庫**：片長遞增（填充片 80 分鐘在前）、勾年份 2023 → 只剩 Oppenheimer；再勾 Documentary →「這個媒體庫沒有符合篩選的作品。」
    「類型：Documentary · 年份：2023」「清除類型與年份」→ `?sort=Runtime`。
  - 1280 / 390 × 深淺：橫向捲動 0；新控制項與清單的文字對比最低 6.53:1（深）/ 5.71:1（淺），與全站現況最低值相同；控制項高 27–29px。
    EN 介面：Sort / Critic rating / Descending / Genres / Years。
  - **抓到並修掉**：`<details>` 展開時清單困在半欄寬、「全部 · 待審」被置中擠開（見 progress.md 偏差與決定），改成按鈕 + 下方面板；
    選了類型的開關比其他高 5px（數字的行高）。
- 2026-09-17 契約測試的證據強度：`sortBy` / `sortOrder` / `years` 直接比對錄製裡的 `CommunityRating`、`LastPlayedDate`、
  `ProductionYear`；**`genres` 的錄製 DTO 不帶 `Genres`**（牆的查詢沒有要），證據是「4 部篩到 2 部、恰好是 NFO 寫了 Drama / Comedy 的
  那兩部」，NFO 內容在實驗腳本的 `TITLES`。要更硬就得讓錄製多帶 `fields=Genres`，而那不是 Berth 送的查詢，契約測試就比不了整份參數。
- 2026-09-17 已知限制（沒修）：**「隨機」排序跨頁會重洗**，Jellyfin 每次請求都重新洗牌，翻頁可能重複或漏掉作品；jellyfin-web 相同。
  驗收「與分頁一起正確運作」對隨機這一種做不到，照 jellyfin-web 留著這個選項。TanStack Query 的快取讓同一頁來回看時順序不變。
- 2026-09-17 code-review（Standards）處理了的：替身排序用的 `Any` 補理由；類型與年份的詞在 CONTEXT.md 補 **Narrowing** / **Wall Query**
  （選項清單在程式碼裡叫 `filters` 沿用 Jellyfin，不是「待審」「Unmatched」那兩個 filter）；`library_page`、`JellyfinAccess.page`、
  `read_wall` 拿掉只給測試用的預設值，「打開牆時的排序」只寫在 `BROWSABLE`（`WallQuery.sort=None`、API 參數預設 `None`）；
  `tiebreak` 一律是 Jellyfin 的字串；前端 `onPage` 收掉三處組網址、`SortOrder` 型別用在方向選單、`NarrowPanel` 的三重判斷改查表
  `NARROWING`、i18n 鍵收進 `narrow.*`；`Browsing` → `LibraryWall`、`wanted` → `page_request`；拿掉 `fixture_path`。
  **沒處理**（判斷題）：adapter 的 `sort_by` / `sort_order` / `genres` / `years` 四個參數一起走（Data Clumps）——它們一對一翻成
  Jellyfin 的查詢參數，adapter 的其他方法也是平鋪參數；`query` 一路傳過 `Filters`、`Pager`、`PageKey`、`EmptyFilter`、`EmptyWall`
  ——與票 03 傳 `page` 的做法相同；`BrowsableLibrary` 轉查 `BROWSABLE` 的屬性（票 03 的形狀）。
- 2026-09-17 code-review（Spec）處理了的：「選著的不在清單上照樣列出」補測試（變異驗證：拿掉合併會紅）；帶著排序與類型切待審不重抓補斷言；
  plan §6 的拒絕清單補 422 `sort_not_offered`。**記在偏差與決定、沒改**：422 本身與換頁先留著上一面牆。面板的清除鍵與讀取中、
  失敗、沒有資料三種狀態是 shape「狀態與範圍值」要列齊的那一類，shape 已記。
