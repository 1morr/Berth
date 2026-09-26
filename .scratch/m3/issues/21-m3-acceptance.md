# 21 — M3 驗收

**Status:** done

**Blocked by:** 01–20 全部

**讀:** plan §11.4（範圍與驗收）、§10；brief §15、§17

## 做什麼

里程碑收尾。plan §11.4 的驗收是八條：

> 一個 Mikan 聚合 feed 加一個 Nyaa 或 acg.rip 搜尋 feed 全自動追完；中途訂閱的一部補齊舊集，之後的新集自動入庫；同一集兩個字幕組、同組 v1 與 v2 都並存；合集被排除；一部 split-cour 在審核裡改正一次之後其餘集數跟著對；一筆發佈時間與換算出的那一集播出日對不上的不自動入庫；Jellyfin 認到的季集與帳本不同時開出 Issue；已確認的 RSS Series 的新集數不出現在 audit 清單。

**e2e**：真服務那一套（`tests/e2e/`）加一個 M3 模組。公開 RSS 站不能進 CI，所以 feed 由一個本地替身 HTTP 伺服器用票 07 的 fixture 提供，下載與入庫走真的 qBittorrent 與 Jellyfin。前端 e2e（`pnpm -C web e2e`）加一條 RSS 流程：加 feed → 綁定 → 看到 Job。

**另外對真站跑一次**：用使用者自己的 Mikan `MyBangumi` 與一個 acg.rip 搜尋 feed，在本機 compose 上跑一輪，貼結果（這一輪不進 CI）。

**收尾動作**（專案 CLAUDE.md）：

- `/impeccable critique`、`audit`、`polish` 各一輪，P0 / P1 當場修，其餘記進票的 Comments
- 票 01–20 的 Comments 逐條分成「修掉」「延後（寫進 plan §11.5 M4 或更後）」「不做」
- `/impeccable document` 把 DESIGN.md 與 `.impeccable/design.json` 追上
- `docs/progress.md` 的 session 紀錄與偏差；CHANGELOG

## 驗收

- [x] e2e 覆蓋八條驗收，全程自動化（貼 CI run 連結與輸出）
- [x] 真站一輪的結果（feed、長出的 RSS Series、自動綁定幾部、入庫幾集）
- [x] critique / audit / polish 結果與分數；P0 / P1 已修
- [x] 票 01–20 的 Comments 已逐條歸屬
- [x] lint、type、test、`berth bench` 綠燈；CI 全綠

## Comments

### 開工時拍板的兩件（2026-09-26）

- **RSS 自動綁定送進哪一條 Route**：預設安裝的 TV 與 Anime 兩條都收劇集，自動綁定一律停在 `route_ambiguous`，驗收第一條「全自動追完」與真站的「自動綁定幾部」都會是 0（票 09 留下的延後項）。使用者拍板 **Feed 帶一條 Route**（照 Sonarr Import List 的 Root Folder）：加 Feed 時選，收得下那部作品的 Route 不只一條時用它（`services/rss._chosen_route`，理由 `feed_route`）；沒選的照舊留給人。brief §15、§19，plan §2.4、§6。
- **票 16 的規則偏差**：使用者**先不追認**，記在 plan §11.4 結尾的延後清單。

### 開工時發現：票 15 之後真服務 e2e 一直是紅的

main 上的 e2e（[run 36199357169](https://github.com/1morr/Berth/actions/runs/36199357169)）10 failed：美劇那包停在審核。種子影片 330 秒，片長驗證（票 15）拿它對 TMDB 半小時的集數，差太多。票 15 那一輪只跑了 `pnpm -C web e2e`，沒跑真服務的 e2e；nightly 還沒跑到那一版（票 15–20 沒推上去）。修法：`payload.py` 照語料的 TMDB 快照改寫每一支 `.mkv` 標頭的 Segment Duration（libmediainfo 的 General 片長讀的就是這一格，Windows 與容器裡實測），只拉長不縮短——短於五分鐘會被分類器降成特典。

### 票 01–20 的 Comments 歸屬

子代理逐條對 repo 現況（`6c0caf9`）核過（2026-09-26），約 170 條分成四類。「已修」是後續票已經做掉的，其餘三類照票上要求。

**修掉（這一票）**

- 票 09：兩條以上收 tvshows 的 Route 時自動綁定一律 `route_ambiguous`——使用者拍板 Feed 帶 Route（見上）。
- 票 01：重複版本「取代舊版」走 `fs.replace_link`，不比 inode——使用者換進去的檔案會被蓋掉。
- 票 06b：套件內 Jellyfin 靠泊之後重跑偵測（`restart`）會判成 `existing / setup_completed`——qBittorrent 與 Prowlarr 都被釘住，只有它沒有。
- 票 06：「送出中用 `busy`」出現第一個違規——`rss/FirstRoundSection.tsx` 同時給 `disabled={prime.isPending}`，按下之後焦點掉回 body。
- 票 06h：淺色主題錯誤狀態的輸入框邊框 `blocked` 對 `hull` 2.58:1（WCAG 1.4.11）；`BundledLibraries` 刪列之後焦點沒落到下一列；健康卡的 Jellyfin detail 寫死英文「N libraries」。
- 票 10：規則格一格一個 `×` 的樣式 → 由這一票的 `/impeccable document` 寫進 DESIGN.md。

**延後**：M4 兩條寫進 plan §11.5——補漏與輪詢的失敗拼在同一個 `last_error`（票 12）、「忽略」的 Jellyfin 回驗不一致第二天又開（票 17）。M5 兩條寫進 §11.6——`confirm_audit(s)` 的反向命令語意不對（票 05）、`services/issues` 仍在豁免表（票 17）。其餘寫進 §11.4 結尾，不排里程碑：核准被擋的列與 `held_proposal` 不比帳本（票 14 / 14b）；每集 5 分鐘以下的短篇被整包降成 extra（票 15）；RSS 的兩個並行窗口（票 10 / 11）；`QUEUE_LIMIT` 截斷時整個 Series 被標成確認過（票 13）；精靈跑完再改 `QBITTORRENT_WEBUI_PORT`（票 06b）；既有 Jellyfin 帳密錯只顯示原文 401（票 06h）；票 16 的偏差待追認。票 06 的五條已在 §11.3 D 組。

**已修（後續票）**：RSS 送單走標題認作品（票 05 → 08 帶 `media_id`）；第 2 步寫死的探測位址與試跑環境的 `HostHeaderValidation`（票 06b → 06h）；精靈四張步驟表（票 06d → 06e）；實驗腳本的環境（票 07 → 08）；`SeriesBinder` 的重複（票 08 → 18 的 `Choices`）；季號寫回 RSS Series（票 09 → 13）；補漏的請求量（票 12 → 20）；從審核改正連載中的 split-cour（票 14 → 14b）。

**不做**：其餘約 145 條——判斷題票上已結（重複、命名、Data Clumps、分層的轉手函式，約 90 條）；刻意的行為（下一批由人按、Torznab 不共用預算、逐列確認不標 Series、預先綁定不改綁等，約 25 條）；記錄項（實跑、研究檔 §11 沒解的四題、容器清理，約 10 條）；沒有 repro 的（`removed → removed` 的 CAS、壞掉狀態之間不互轉、`resubmit_job` 不看磁碟、單一重探的連帶、`Part N` 多算、網路先行配信、輪詢計時器被重繪重設等，約 12 條）。票 06h 的其餘 P2 與票 11 的「留著 0 集」交給這一票的 critique 重評，沒升到 P0 / P1 的歸這一類。依全域規則「寫不出失效條件的修復不做」。

### e2e（`tests/e2e/test_4_m3_rss.py`，八條驗收）

公開 RSS 站由 compose 裡的 `sites` 容器冒充（`tests/e2e/sites.py`）：network alias `mikanani.me` / `acg.rip` / `nyaa.si`、HTTPS（`tests/fixtures/e2e/tls/` 的測試 CA，`tests/e2e/make_tls.py` 產生；`ca-bundle` 容器先把系統 CA 清單接上它，Berth 以 `SSL_CERT_FILE` 信它——**檔案不在時 Berth 建不出任何 HTTP client**，所以它先寫好、Berth 才起來）。Berth 對番組頁與單一字幕組 feed 的網址寫死 `https://mikanani.me/`，替身一定要講 TLS。發佈取自票 07 的 fixture，位元組與 info hash 是替身自己造的，輪次由測試寫進替身。TMDB 是真的，所以作品選了資料不會再變的：

- 《与你相恋到生命尽头》（TMDB 285574、Mikan 番組 4009）：聚合 feed（說了自動綁定送進 Anime）第一輪第 3、4 集 → 自動綁定（依據 `title_equal`、`premiere_near`、`feed_route`）並補舊集補上 1、2；確認第一批；第二輪同組第 5 集與 v2、北宇治字幕组第 5 集自動入庫——三份並存（兩份同組、一份是 v2），確認過的那一組不進 audit、北宇治那一組照樣進。
- 《上伊那牡丹，醉姿如百合》（TMDB 283905）：從 Media 頁訂閱 acg.rip 搜尋，第一輪「全部下載」送出第 11 集、千夏字幕组的整季合集 `excluded / not_single`；第二輪第 12 集自動入庫。
- 《Re：从零开始的异世界生活》（TMDB 65942，**整部只有一季、85 集**）：合成的 split-cour（LoliHouse 把第二季後半從 01 重數，發佈時間是 2021 年每一集播出的隔天）。四份計劃全部 `air_date_conflict` 停在審核、帳本是空的；改一份成 S01E39 並套用到 RSS Series → offset 38，其餘三份重新規劃、自動入庫，改的那一份核准之後 E39–E42 齊全。**不用 SPY×FAMILY**：TMDB 有三季，純集號在播出日比對之前就因信心低進審核，驗不到第六條。
- 在 Jellyfin 裡把第 1 集的 `IndexNumber` 改成 7 並鎖住 → 對帳開出 `jellyfin_item_mismatch`，路徑對上帳本那一列。

片長驗證（票 15）讓 payload 也得改：M1 那三包的 `.mkv` 標頭照語料的 TMDB 快照寫片長（`payload.lasting`），TMDB 說短於五分鐘的迷你特典寫成 mediainfo 讀不出來的位元組——量到真的片長會被分類器降成特典、量到 330 秒片長驗證說差太多，兩道檢查對它們沒有一致的答案（plan §11.4 結尾延後的那一條）。

- CI：[run 36201830927](https://github.com/1morr/Berth/actions/runs/36201830927) M3 模組 7 passed、M1 的 Frieren 特典被片長驗證擋下（5 failed）→ 修 payload → [run 36203982775](https://github.com/1morr/Berth/actions/runs/36203982775) **22 passed in 1077.90s**（`b5336ff` + `fd68d62`）。code-review 補強斷言之後的最終一輪見 progress.md。
- 前端 e2e `rss-auto-bind`：加 Feed 時選「自動綁定送進 Anime」→ 輪詢 → 那一部自動綁定、補舊集送出 12 筆、依據說出是 Feed 挑的 Route → 下載列表已入庫（`pnpm -C web e2e --project rss-auto-bind --project rss` 2 passed）。「加 feed → 綁定 → 看到 Job」原本就是 `rss.spec.ts`。

### 真站一輪（2026-09-26，試跑環境換成這一票的 image）

`C:\Users\Roxy\berth-trial` 沿用 06h 的 config / data，只換 `berth:trial-m3`。兩個 Feed：

- **MyBangumi 聚合 feed**（自動綁定送進 Anime）：第一輪 10 筆長出 9 個 RSS Series，**自動綁定 8 個**（每一個的依據都是 `title_equal` + `premiere_near` + `feed_route`），補舊集一次送出 144 筆（88.6 GB）。沒綁上的是《Re：从零开始的异世界生活 第四季》（`no_candidate`：Mikan 的番組名帶「第四季」，TMDB 只有一部同名作品、一季）。之後背景輪詢又長出一部（尼古喵喵），自動綁定並補 12 集。
- **acg.rip 搜尋**《擅長逃跑的殿下 第二季》（TMDB 222623，從 Media 頁訂閱）：第一輪 30 筆、五個字幕組（黒ネズミたち的 CR / Baha / ABEMA 三個來源、ANi、LoliHouse 的重數 07–10、猎户压制部的 `[21]`）全部預先綁定成 4 個 RSS Series，選「全部下載」送出 30 筆。

一小時後：187 筆 Job、**入庫 36 集**（才女的侍從、魔法少女奈葉、BLACK TORCH 各 12 集，全部照規矩進第一批 audit），147 筆在 qBittorrent 排隊。**1 筆 `submit_failed`**：一次送進近兩百個 torrent 時 qBittorrent 回 `GET /api/v2/torrents/categories: ReadTimeout`——沒送到它那邊，票 02 的「poller 認回」接不到，要人按重試（記進 plan §11.4 結尾，M4 巡檢或送單重試再處理）。

### `/impeccable critique`：24 / 40（M1 26 → M1.5 29 → M2 34 → M3 24）

雙代理（A 設計審查、B 偵測器 + chrome-devtools overlay），演練情境 `rss`、`rss-split-cour-airing`、`issues`、`budget`，1280 與 375 / 390、zh-Hant 與 EN。快照 `.impeccable/critique/2026-09-26T01-47-40Z__web-src-pages.md`。分數比 M2 低是評的面不同：M3 的 `/rss` 是一頁七段、十個待綁定長成約 3000px 的牆。偵測器 CLI 0 筆；overlay 39 筆裡 37 筆是誤判（well / hull 兩層、收合 `<details>` 的幾何），健康頁 h1 → h3 跳級與字級比 1.14 是真的。

- **[P0] 輪過但一次都沒讀到的搜尋 Feed 仍能選「全部下載」** → 修掉：讀不到的那一輪照樣寫 `last_polled_at`，前端 `read` 與 `prime_feed` 都只看它。改成「至少讀到過一次」（`services/rss._ever_read`，`FeedOut.ever_read` 給畫面），畫面說出上一次為什麼沒讀到。整合測試與 vitest 各一條，紅 → 綠。
- **[P1] 窄版英文整頁橫向捲動** → 修掉：計數的分隔點放到不換行那一格外面。瀏覽器實測 390 寬中英文 scrollWidth = clientWidth。
- **[P1] 輪詢讀不到時仍說「這一輪：新 0 筆…」** → 修掉：`PollOut.failed` 帶出去，畫面說「這一輪沒讀到」。
- 其餘記在這裡不修：[P2] 待綁定列的標題是最新一集的發佈名、來源欄印 id；[P2] `/review` 的 Plan 沒有依 RSS Series 分組、「套用到這個 RSS Series」沒重述範圍；待綁定與 Plan 沒有批次；預算原文沒本地化；回驗不符的「下一步」沒依不同之處挑修法；每列待綁定 3 個 Tab 停留點；「全部下載」在「會送出 0」時名實不符；一次性連結的搜尋預填取第一筆。票 06h 的其餘 P2 與票 11 的「留著 0 集」這一輪沒有升到 P0 / P1，歸「不做」。

### `/impeccable audit`：16 / 20（A11y 3、Perf 2、Responsive 3、Theming 4、Integrity 4）

Lighthouse 兩頁兩種裝置 Accessibility 與 Best Practices 都 100；深淺兩主題逐節點 0 筆 AA 不合格（深 5.12、淺 5.71 最低）；390 寬五個面中英文都不溢出。P0 0、P1 1、P2 4、P3 4。

- **[P1] 輪詢之後待綁定長在上方，那一列與結果句被推出畫面（CLS 0.74；390 上從 y 356 到 2443）** → 修掉：重讀之後那一列不在畫面內就捲回來（`FeedSection` 的 `bringBack`）。vitest 紅 → 綠；瀏覽器實測輪詢後那一列在 y 458 / 844。
- 偵測器那一條真的：健康頁卡片標題改成 h2（`ServiceCard` 收 `level={2}`，「怎麼修」跟著低一層），vitest 紅 → 綠，瀏覽器實測 h1 → 六個 h2。
- 不修，記在這裡：[P2] 手機上 GhostButton 35px 高、`COMPACT_BUTTON` 24px（過 AA 下限、低於 44px）；[P2] JS 一個 898 KB 的 chunk、i18n 兩種語言整包送；[P2] `/review` 12 列 article 的名稱都是作品名；[P3] 勾選框本體 16px、預算「6 / 6」沒有已用 / 上限的語意、訂閱失敗的原文是 UTC 微秒時間、390 上頁首導覽佔 34%。

### `/impeccable polish`

瀏覽器實跑這一輪的每一條修正（`rss` 與 `budget` 情境，1280 與 390、zh-Hant 與 EN）：390 寬 EN / zh 無橫向捲動、輪詢後那一列留在視野內、預算用完的第二、三輪說「這一輪沒讀到」、健康頁標題 h1 → h2。截圖 `.local/screens/m3-21/`（不進 repo）。

### `/impeccable document`

documenter 子代理把 DESIGN.md 與 `.impeccable/design.json` 追上 M3：新增「RSS 頁」一節、Chips 的「一條一格」（票 10 要求的）、健康頁卡片（`level`、預算延後不塗漆）、`SubscribePanel`、RSS Series 分組、回驗不符並排、輪詢後捲回來；修正三處過時（輸入框錯誤邊框、Select 邊框、sidecar 的四個泊位）。排除條件的 `×` / `+` / `−` 字元圖示記成 Known contradiction，不寫成系統做法。它指出的「健康頁從 h2 跳到 h4」當場修掉。

### code-review（基準 `6c0caf9`）

**Standards**：硬性兩條——plan §6 的輪詢回應沒寫 `bound` / `failed`（補上）、progress.md 缺偏差（補上）。判斷題收了兩條：前後端各算一次 `everRead` → `FeedOut.ever_read` 單一來源；`ServiceCard` 的 `level` 改成 DESIGN.md 的數字形狀。不改、記下：`FeedRoutePicker` 與 `media/RoutePicker` 的外框重複（資料來源不同）；`_pin_jellyfin` 與 `indexer._pin_probe` 只差種類；`library_count` 在兩張卡各畫一次；`PollOut.failed` 是字串（同 `PollOutcome.failed` 與 `last_error`）；RSS 站主機名散在四處（e2e 基礎設施）；`d03f6dd` 一個 commit 收了四件修正。

**Spec**：兩條斷言偏弱已補——v1 / v2 並存改成比對同一字幕組的兩份、一份是 v2；「確認過的不進 audit」那一條自己先斷言那兩份已入庫（停在審核的也不在 audit 清單上，否則空泛成立）。docstring 寫明搜尋 feed 的「全自動」是從 Media 頁訂閱的那一種。
