# 21 — M3 驗收

**Status:** ready-for-agent

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

- [ ] e2e 覆蓋八條驗收，全程自動化（貼 CI run 連結與輸出）
- [ ] 真站一輪的結果（feed、長出的 RSS Series、自動綁定幾部、入庫幾集）
- [ ] critique / audit / polish 結果與分數；P0 / P1 已修
- [ ] 票 01–20 的 Comments 已逐條歸屬
- [ ] lint、type、test、`berth bench` 綠燈；CI 全綠

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
