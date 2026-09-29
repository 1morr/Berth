# 08 — 媒體庫與路徑頁：按鈕觸發檢查、逐條收合、失敗說出怎麼改掛載

**Status:** done

**Blocked by:** 15（15 把精靈改成一個服務一頁、把套件內 Jellyfin 的媒體庫清單搬進這一頁；這張在它之上改）

**讀:** plan §9.3 頁 3「媒體庫與路徑」、§9.5（既有 Jellyfin 的「加入 Berth 路徑」、〈檢查與訊息〉）；brief §16.4（同主機、同容器路徑的條件）、§19 2026-09-26「精靈與探索的試跑回饋」與 2026-09-29「精靈改為每個服務手動選擇」兩列；開工先 `/impeccable shape` 這一頁

## 為什麼

2026-09-26 使用者試跑與 `berth-lab` 實測：

- **一進這一格就自動跑**。它不只是檢查：會建 qBittorrent 分類、在媒體庫目錄寫探測檔與硬鏈接測試檔——有副作用的動作要由人按。
- **五條纜繩 × 每條 Route 全部攤開**，四條 Route 就是二十列，「前往下一個泊位」被擠出畫面要往下捲。
- **既有 Jellyfin 的「加入 Berth 路徑」按了之後還要「確認加入」**，沒按確認也能直接前往下一格，到後面才發現那個媒體庫沒有 Berth 路徑。
- **slug 帶空格**：媒體庫叫「TV Shows」時 qBittorrent 分類是 `berth-tv shows`、下載路徑 `/complete/tv shows`
  （`berth/services/jellyfin.py` 的 `library_slug` 只換掉路徑不收的字元）。

2026-09-29 的重新設計（brief §19）之後，這一頁是頁 3，套件內 Jellyfin 的媒體庫清單、既有 Jellyfin 的媒體庫勾選與
「加入 Berth 路徑」、Route 與檢查都在這裡。而既有服務最關鍵的條件——與 Berth 同一台主機、把同一個父目錄掛在同一個
容器路徑（brief §16.4，不做 remote path mapping）——正是在這一頁的探測檔與硬鏈接檢查現形，失敗時要說出怎麼改掛載。

## 做什麼

1. 進這一頁不自動跑；一顆「建立並檢查」（第一次）/「重新檢查」按鈕，按下之前說出會做哪些事（套件內建媒體庫、建分類、寫測試檔）。
2. 每條 Route 收成一列：名稱、寫入目標、「5 / 5 通過」；有一條失敗就自動展開那一條，全過預設收起。
   設定頁的 Route 列表用同一個元件。
3. 「加入 Berth 路徑」的確認沒完成時，「建立並檢查」與「前往下一個泊位」擋下並說出還差哪一步（或把確認併進同一個動作，shape 時定）。
4. **檢查失敗時說出怎麼改掛載**：第 2–5 條（`download_path`、`library_path`、`probe_visible`、`hardlink`）失敗時，除了
   現有的「哪個容器少了哪個掛載」與 compose 修正片段，對既有服務另說出同主機、同容器路徑的條件；Jellyfin 在另一台
   主機（`probe_visible` 看不到）與分開掛載（`EXDEV`）各一句。
5. **票 15 critique 留下的這一頁的雜訊**：剖面與纜繩列把同一份端點列兩遍（剖面只放纜繩列沒有的）；Route 建完之後剖面
   「這一輪要建的 Route」仍是 0；套件內媒體庫建完出現「這個泊位的事做完了」但泊位板仍是「待靠泊」、真正的下一步
   「前往 Route 與檢查」是上方的次要鈕；「開始靠泊」看不出會建媒體庫；每屏只留一顆 `assigned` 主鈕。
6. `library_slug`：空白換成 `-`（中日文照留）。已經存在的 Route 與分類不改名（改分類路徑會搬走 torrent，brief §20.2），只影響新建的。

## 驗收

- [x] 進入這一頁不送任何請求（vitest 斷言 + playwright 的 network 紀錄）
- [x] 全過時每條 Route 一列、失敗那條自動展開；1280 與 390 兩份截圖，「前往下一個泊位」在不捲動的情況下看得到（四條 Route、全過）
- [x] 加路徑沒確認時被擋（vitest）
- [x] 既有 Jellyfin 的 `probe_visible` 失敗與 `EXDEV` 各有改掛載的說明（整合測試或 vitest；`berth-lab` existing 故意少掛一個目錄實跑一次）
- [x] `library_slug("TV Shows") == "tv-shows"`，既有 Route 不受影響（單元測試，雙向）
- [x] 剖面不重複纜繩列的端點；建完媒體庫之後主要動作是前往 Route 那一步（vitest）
- [x] plan §9.3 頁 3、§9.5〈檢查與訊息〉與實作一致
- [x] lint、type、test、前端 e2e 綠燈

## Comments

- 2026-09-30 實作（shape：`.scratch/m4/route-berth-shape.md`，使用者拍板兩題：套件內併成一個畫面一顆鈕；Berth 路徑
  併進「建立並檢查」當寫入目標的一個選項，沒有「確認加入」）。第 3 條因此是「沒有半途狀態」而不是「擋下」：
  vitest `SetupPage.jellyfin.test.tsx`「Berth 路徑是寫入目標的一個選項」「加路徑沒加上就停」「勾了媒體庫、還沒選寫入目標」。
- 「進入這一頁不送任何請求」照 shape 讀成**不送寫入**：頁面照舊 `GET /setup/routes`、`GET /setup/jellyfin` 讀狀態。
  vitest 與兩支 e2e（`wizard`、`existing`，`page.on('request')`）斷言的是非 GET 為零。
- 「前往下一個泊位」不捲動看得到：`BerthNav` 有下一個時**不分寬度** sticky（DESIGN.md 記為例外）；1280 × 720 上
  fake server 的暫存路徑很長、Route 列換兩行，不 sticky 放不下。影響精靈每一頁，不只頁 3。截圖在 e2e 的
  `3-routes-viewport.png`（1280 與 390）。
- berth-lab existing 實跑（image `berth:m4-08`，既有 Jellyfin 的「TV Shows」、它票 17 時建的 Route `berth-tv shows`）：
  - berth 另掛 `./shadow-library:/data/library`（Jellyfin 看不到）→ 重新檢查：`probe_visible` 紅、那一列自己展開 3 / 5，
    compose 片段下多「這是你自己的 Jellyfin：…多半是它在另一台主機…」。
  - berth 另掛同一個宿主目錄 `../home-media/data/library:/data/library` → `hardlink` 紅
    `[Errno 18] Invalid cross-device link`，4 / 5，多「你自己的服務多半把下載與媒體庫分開掛…」。
  - 拿掉 override（compose 的 image 改成 `berth:m4-08`）→ 重新檢查 5 / 5；那條 Route 與分類仍是 `tv shows`（不改名）。
- code-review（Standards、Spec 兩軸）修掉的：頁做完之後回頭補建時兩條 sticky 疊在一起、一屏兩顆 `assigned`（改看
  `done`＝後端過了這一頁）；收起的清單展開後「加一個媒體庫」會重新掛載、焦點掉回 body（清單永遠是同一個 `<details>`）；
  票 08 之前加的 `…/tv shows` Berth 路徑被當成沒加過、會再加一條 `…/tv-shows`（`berth_path` 先認 `locations` 裡已有的
  舊寫法，整合測試雙向）；`aria-describedby` 的 id 用媒體庫名拼、帶空白就斷（改 `useId`）；`NAV_STICKY` 手抄
  `STICKY_ACTION`（抽 `STICKY_BAR`）；`librariesFailed` 兩份；DESIGN.md 補 `RouteRow`；CHANGELOG。新測試對修法做過
  變異（`quiet` 改回舊規則那一條會紅）。
- **沒處理的**：
  - 加路徑失敗之後改選別的路徑建成 Route，Jellyfin 的 `libraries` 那一步仍是 `failed`：失敗說明與泊位板的阻擋留著，
    直到下一次加路徑成功。票 06h 起就是這樣（失敗記在那一步上、沒有人清），不是這張票造成的；要修得讓成功的
    `build_routes` 或下一次讀狀態時作廢它，沒有 repro 票先不動。
  - 健康頁、Route 設定頁讀不到服務來源，改掛載那一句只在精靈（plan §9.5 已寫明）。
  - Smell：`{library, target}` 收成 `Planned`；`RouteRow` 的 `open` 改名 `attention`。`BundledLibraries` 在
    `<details>` 裡仍有自己的標題「要建的媒體庫」，與摘要列「媒體庫清單」重複一層，留給 UI 收尾的 critique。
