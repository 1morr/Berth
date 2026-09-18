# 08 — Media 詳情重排與觀看區

**Status:** done

**Blocked by:** 04、05、07

**讀:** plan §11.2b（含 M1 帶過來的 critique 那一段）；brief §12、§13（Media 詳情）、§20.8（選季選集）；
`docs/research/library-browsing.md` §2、§4.1、§5、§7（詳細頁列季、列集）、§8；票 01 的結論（由 TMDB id 找作品）；
`.scratch/m1/media-detail-shape.md`、`.scratch/m1/search-results-shape.md`、`.scratch/m1/library-shape.md`；
`.impeccable/critique/2026-09-17T06-17-18Z__web-src-pages.md`

## 做什麼

探索與媒體庫點進的是同一個 `/media/:id`（brief §13）。作品已在 Jellyfin 裡、而且這位使用者看得到時，
最上面是**觀看區**：

- 主動作：繼續看（有進度的那一集）或下一集，電影是這一部——深連結到 Jellyfin 的那一項。
- 選季選集：`/Shows/{id}/Seasons?userId=` 與 `/Shows/{id}/Episodes?userId=&seasonId=`（會套權限，研究 §4.1）；
  各集有劇照（票 04 的代理）、已看標記，可就地切換（票 05 的命令），點集深連結到 Jellyfin 的那一集。
- 這部作品的 NextUp 要帶 `seriesId`，而帶了就不套權限（研究 §2）——只能在確認這位使用者看得到這部作品之後才問。

搜尋 torrent 與「檔案與版本」收到下面。作品不在 Jellyfin、或這位使用者看不到時，版面維持「搜尋在前」，
而且頁面上不得透出任何 Jellyfin 的東西（item id、圖、觀看狀態）。

**整頁重新 shape**。票 15 的 critique 把這一頁的版面交給 M1.5（plan §11.2b）：動作沉底（1280×900 下「搜尋」在
y=984、390px 在第三屏）、全綠的搜尋纜繩佔 311px。觀看區、Berth 的季表（入庫狀態）與 Jellyfin 的選季選集是
並排、合併還是分層，在 shape 定。shape 同時是票 09（季表與清單不再整份攤開）與票 10（缺集一鍵搜）的版面契約，
那兩票往裡面填，不重排。

只支援 Jellyfin 12 以上，研究 §9 第 5 點給 10.11 的「回 0 時退回遞迴查詢」後備不需要做。

## 驗收

- [x] 作品在 Jellyfin 裡且看得到時，觀看區在最上：主動作深連結到正確的那一集（或那一部電影）
- [x] 選季選集：季列、各集劇照與已看標記；各集可就地切換已看，標未看先確認（沿用票 05）
- [x] 搜尋 torrent 與「檔案與版本」在觀看區下面；不在 Jellyfin 的作品維持搜尋在前
- [x] 整合測試：作品在這位使用者看不到的媒體庫時沒有觀看區，回應裡沒有 Jellyfin item id、圖或觀看狀態；
      這部作品的 NextUp 只在可見性確認之後才問
- [x] 契約測試：Seasons、Episodes 的解析（票 01 的 fixture）
- [x] critique 的兩條（動作沉底、搜尋纜繩 311px）處理完，附 1280×900 與 390px 的前後量測
- [x] 整頁走 `/impeccable shape`（`.scratch/m1.5/media-detail-shape.md`，替票 09、10 留位置）；playwright 實跑
      一部 Jellyfin 裡的劇集、一部電影、一部不在 Jellyfin 的作品，附結果
- [x] 對比 ≥ 4.5:1；390px 窄版可用；鍵盤可完成；zh-Hant 與 en 並列
- [x] lint / type / test 全綠並貼指令輸出

## Comments

- 2026-09-18 shape（`.scratch/m1.5/media-detail-shape.md`）使用者拍板三件：分層、集用橫卡網格、看到一半的項目標為已看先確認
  （媒體庫牆一起改；整部劇一律確認是確認 brief 時同意的解讀）。build 定案在 shape §9。
- 2026-09-18 **前後量測**（`fake_setup_server.py --scenario submit`，真的 TMDB，同一台機器同一套資料）：

  | | 改之前 | 改之後 |
  | --- | --- | --- |
  | 1280×900「搜尋」y（葬送的芙莉蓮 / 奧本海默） | 1027 / 953（第二屏） | 579 / 501（第一屏） |
  | 390×844「搜尋」y（同上） | 1757（第三屏）/ 1281（第二屏） | 999 / 862（第二屏） |
  | 搜尋結束後五條纜繩的高度（1280 / 390） | 287 / 315 px | 44 px（一行摘要） |

  390px 的頁首本身佔 245 px（四行），搜尋鍵落在第二屏頂端；頁首不在這一票的範圍。
- 2026-09-18 **實跑**（`--scenario library`，`deckhand`）：The Bear 主按鈕「繼續看 S01E04」連到 `http://127.0.0.1:8096/web/#/details?id=<那一集>`、
  描述「Episode 4 · 看到 18%」，六張劇照經代理載入；The Office 預設選 Season 1（主按鈕「看下一集 S01E05」）、換 Season 2 只多一支
  `episodes` 請求、Specials 那一格是「無圖」；Breaking Bad「在 Jellyfin 開啟」+「全部看完了」；Oppenheimer「繼續看」+「看到 42%」，
  標為已看的確認說「會清掉你看到 42% 的位置」；SPY×FAMILY（他看不到的 Anime）與 Severance（不在 Jellyfin）沒有觀看區、`h2` 從
  「搜尋 torrent」開始、`/api/media/{id}` 的回應裡沒有任何 32 位十六進位 id 或 `/api/jellyfin/`；`skipper` 開 SPY×FAMILY 有觀看區；
  `bosun` 開 The Bear 是「從 S01E01 開始看」。鍵盤：Tab 順序 頁首 → 主按鈕 → 立即重抓 → 在 Jellyfin 開啟 → 每一格（連結 → 切換鍵）；
  沒進度的 E05 Enter 標為已看、焦點留在那一顆（變成「標為未看」），再 Enter 進確認、Esc 回到鍵、Tab + Enter 確認之後焦點回到鍵。
  EN：`Watch`、`RESUME S01E04`、`First aired 2022`。1280 深 / 淺、390 深 / 淺 `scrollWidth == clientWidth`；新文字對比最低
  深 7.74:1、淺 5.71:1（主按鈕 12.35:1）。impeccable detector 0 findings。截圖 `.playwright-mcp/t08-*.png`（不進版控）。
- 2026-09-18 code-review **處理了的**：Standards——`title` 是 CONTEXT.md「Media」的禁用詞，改 `locate` / `tmdb_index` /
  `watch_area_queries`；前端 Jellyfin 共用的 API 搬到 `api/jellyfin.ts`；`watchLine` 共用；`PRIMARY_LINK`；兩個「一行字 + 重試」合一；
  `_watch` 抽出；替身不用 `getattr` 字串分派。Spec——集卡標為未看的確認補測試；shape 補「一季不畫季切換」與端點名；替身的
  `episodes` 不再發明劇季關係；劇集沒有下一集但沒看完時不說「全部看完了」；沒看過的電影切換鍵不指向不存在的描述；確認之後權限
  被收回回 `null` 不是 500（各補一條測試，前兩條做了變異驗證）。
- 2026-09-18 **沒處理**（判斷題 / 之後再量）：
  - `jellyfin_link`（帳本 → Jellyfin 作品 id）放在 `services/inventory.py`，Feature Envy 的判斷題；它依 Media 的類型選欄位，
    搬到 model 上要多帶一個 kind。
  - i18n 有 `watch.*` 與 `inventory.watch.*` 兩個命名空間：後者是標記與觀看那一行（牆、詳情共用），前者是觀看區自己的字；改名會動到
    所有牆的測試文案鍵，沒有做。
  - `WatchTarget`（`series` / `movie` / `episode`）與 `MediaKind`（`tv` / `movie`）兩套字，只在牆卡一處轉換。
  - 季與集的請求照 jellyfin-web 詳細頁送 `fields`（fixture 就是那一組參數錄的），`Overview` 等沒用到；註解已說明。
  - 一季上千集（名偵探柯南）整季照畫、劇照 lazy；由 TMDB id 找作品每次整份拿回來比（`/Items` 沒有 provider id 過濾）——兩者的代價
    都沒量，與票 03 的整份清單同一個待量。
  - 研究 §9 第 5 點給 10.11 的「回 0 時退回遞迴查詢」照票面不做（只支援 Jellyfin 12）。
