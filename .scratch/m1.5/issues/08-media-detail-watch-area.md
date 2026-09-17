# 08 — Media 詳情重排與觀看區

**Status:** ready-for-agent

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

- [ ] 作品在 Jellyfin 裡且看得到時，觀看區在最上：主動作深連結到正確的那一集（或那一部電影）
- [ ] 選季選集：季列、各集劇照與已看標記；各集可就地切換已看，標未看先確認（沿用票 05）
- [ ] 搜尋 torrent 與「檔案與版本」在觀看區下面；不在 Jellyfin 的作品維持搜尋在前
- [ ] 整合測試：作品在這位使用者看不到的媒體庫時沒有觀看區，回應裡沒有 Jellyfin item id、圖或觀看狀態；
      這部作品的 NextUp 只在可見性確認之後才問
- [ ] 契約測試：Seasons、Episodes 的解析（票 01 的 fixture）
- [ ] critique 的兩條（動作沉底、搜尋纜繩 311px）處理完，附 1280×900 與 390px 的前後量測
- [ ] 整頁走 `/impeccable shape`（`.scratch/m1.5/media-detail-shape.md`，替票 09、10 留位置）；playwright 實跑
      一部 Jellyfin 裡的劇集、一部電影、一部不在 Jellyfin 的作品，附結果
- [ ] 對比 ≥ 4.5:1；390px 窄版可用；鍵盤可完成；zh-Hant 與 en 並列
- [ ] lint / type / test 全綠並貼指令輸出
