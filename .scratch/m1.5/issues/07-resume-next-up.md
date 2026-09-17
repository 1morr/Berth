# 07 — 繼續觀看與下一集

**Status:** ready-for-agent

**Blocked by:** 04

**讀:** plan §11.2b；brief §12、§13（探索首頁、媒體庫）、§19（首頁上方放繼續觀看與下一集）、§20.8；
`docs/research/library-browsing.md` §1、§2（Resume 與 NextUp 那幾列）、§7（繼續觀看、下一集、卡片圖）、§8；
`.scratch/m1/discover-shape.md`；`.scratch/m1.5/library-shape.md`

## 做什麼

使用者打開 Berth 就接得上正在看的東西：

- **首頁 `/` 上方**兩列——這位使用者的繼續觀看與下一集，沒有內容就不出現；下面維持探索（brief §19 拍板）。
- **媒體庫頁上方**同樣兩列，只含這個媒體庫的（brief §13）。

權限上的差別（研究 §2）：Resume 與 NextUp **不帶** `parentId` / `seriesId` 時 Jellyfin 會照使用者的媒體庫限縮；
帶了就不會。所以首頁那兩列不帶；媒體庫頁那兩列只能在票 03 的閘門驗過媒體庫 id 之後才帶 `parentId`。
Resume 一定要帶 `mediaTypes=Video`，否則會混進 Season 與 Series（研究 §1.2）。

橫卡的圖沿用 jellyfin-web 的順序：`Thumb` → 劇的 `Thumb` → `Backdrop` → 劇的 `Backdrop`（研究 §7），經票 04 的
代理。繼續觀看的卡片帶進度。點下去**深連結到 Jellyfin 的那一集**（`#/details?id=<那一集>`，主機照票 13 的規則）——
Jellyfin 沒有直接開始播放的網址（研究 §8）。

## 驗收

- [ ] 首頁上方有繼續觀看與下一集兩列，各自沒有內容時不出現；探索牆照舊
- [ ] 媒體庫頁上方有同樣兩列，只含這個媒體庫的
- [ ] 卡片顯示作品名（Jellyfin 的名稱）、季集與集名；繼續觀看帶進度；圖依研究 §7 的順序取
- [ ] 點卡片深連結到 Jellyfin 的那一集
- [ ] 契約測試：Resume 帶 `mediaTypes=Video` 之後不含 Season / Series；NextUp 的解析（票 01 的 fixture）
- [ ] 整合測試：首頁兩列的請求不帶 `parentId` / `seriesId`；媒體庫頁那兩列對不在允許清單的媒體庫被拒且沒有轉發
- [ ] Jellyfin 連不上時兩列不出現或說明原因，探索牆照樣畫得出來
- [ ] `CONTEXT.md` 補上繼續觀看、下一集的名詞
- [ ] playwright 實跑：有進度與沒有進度兩種使用者各看一次首頁，附結果；390px 與深淺兩主題；鍵盤可完成
- [ ] lint / type / test 全綠並貼指令輸出
