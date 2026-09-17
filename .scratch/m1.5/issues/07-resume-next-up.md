# 07 — 繼續觀看與下一集

**Status:** done

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

- [x] 首頁上方有繼續觀看與下一集兩列，各自沒有內容時不出現；探索牆照舊
- [x] 媒體庫頁上方有同樣兩列，只含這個媒體庫的（使用者拍板：只在第 1 頁、沒有篩選時畫，`.scratch/m1.5/watching-shape.md`）
- [x] 卡片顯示作品名（Jellyfin 的名稱）、季集與集名；繼續觀看帶進度；圖依研究 §7 的順序取（完整順序見研究 §7.2，電影不取 Primary）
- [x] 點卡片深連結到 Jellyfin 的那一集
- [x] 契約測試：Resume 帶 `mediaTypes=Video` 之後不含 Season / Series；NextUp 的解析（改用票 07 加錄的 fixture，理由見 progress.md）
- [x] 整合測試：首頁兩列的請求不帶 `parentId` / `seriesId`；媒體庫頁那兩列對不在允許清單的媒體庫被拒且沒有轉發
- [x] Jellyfin 連不上時兩列不出現或說明原因，探索牆照樣畫得出來
- [x] `CONTEXT.md` 補上繼續觀看、下一集的名詞
- [x] playwright 實跑：有進度與沒有進度兩種使用者各看一次首頁，附結果；390px 與深淺兩主題；鍵盤可完成（後半段 playwright MCP 斷線，改用 chrome-devtools MCP）
- [x] lint / type / test 全綠並貼指令輸出

## Comments

code-review（2026-09-17，基準 `e736fec`，Standards 與 Spec 兩軸）

**處理了的**

- Spec：在牆上標為已看之後當場重問兩列 → 拿掉（牆會在指標底下移動），vitest 斷言不重問；只收集與電影的理由改準；
  `mediaTypes` 那條契約測試自己斷言請求參數；截圖檔名的主題改正；「電影不取 Primary」與改用新 fixture 記進 progress.md。
- Standards：替身的區域變數 `upcoming`（CONTEXT.md 避免的詞）→ `candidate`；i18n 註解位置、`api/jellyfin.py` 的 docstring；
  `episode` → `episode_start`（照帳本與計劃）；`watch.progress` → `shown_progress`；`_card` 分成集與電影兩個建構函式；
  `SessionEnded`、小一號按鈕共用一份；收起的斷點與 `WALL_GRID` 同一個檔案；client 兩支共用參數、閘門的 `page` 也走
  `_reachable`；演練情境的 Primary tag 用 `_demo_tag`。

**沒處理的**

- Standards：`services/watch.py` 與 `services/watching.py` 名字相近（判斷題）。前者是牆上的觀看狀態（CONTEXT.md 的
  **Watch State**），後者是 **Watching** 兩列，名字各自對得上名詞表，不改。
- Spec：Jellyfin 連不上沒有實跑（演練情境沒有讓替身 Jellyfin 失聯的開關），由 vitest 覆蓋；票 11 的 e2e 對真的 Jellyfin 時可以補。
- 票 01 的 `useritems-resume.restricted.json`、`shows-nextup.restricted.json` 沒有測試引用（這一票之前就是），留作權限實測的證據。
