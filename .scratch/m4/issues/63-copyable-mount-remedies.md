# 63 — 既有服務的補法能照抄：顯示真正的 DATA_ROOT、同一台只說一次、Jellyfin 提早驗

**Status:** done

**Blocked by:** 55（Unraid 模板的寫法照實跑結果）

**讀:** `docs/research/usability-audit-2026-10-07.md` §3 S2（沒掛 `/data` 那兩列）、S3 頁 3、§4.2 C5、C7、§8 P1-6、P1-7、P2-4、P2-6；截圖 s2-11、s2-15、s2-02；票 55 研究檔的 Unraid 段落；brief §16.4（唯一的硬規則、健康檢查會擋下的情況）；M4 票 36、46

## 為什麼（審計實跑）

- 補法片段是 `${DATA_ROOT}:/data`，使用者要自己去 Berth 的 `.env` 找值。
  - 預設 `./data` 是相對路徑，貼進另一份 compose 會指到別處。
  - Windows 路徑在 YAML 怎麼寫沒說；Unraid 使用者改的是模板的「Add another Path」，不是 compose。
- 頁 3 每個媒體庫各重複一整段補法（兩個媒體庫就是兩段、四個複製鍵），其實是整台 Jellyfin 沒掛 `/data`。
- qBittorrent 沒掛 `/data` 在頁 2 就知道（票 46），Jellyfin 要到頁 3 才知道。
- localhost 的說明在黃色提示與紅色錯誤各出現一次，逐字相同；技術細節的位址少了 `http://`。

## 做什麼

1. compose 把 `DATA_ROOT` 的原始字串傳進 Berth（環境變數），畫面上的補法直接印出值。
   - 是相對路徑時，說「換成這個資料夾的絕對路徑」，並寫明它相對於哪裡。
   - Windows 路徑給可貼進 YAML 的寫法。
2. 補法多一種格式：Unraid 模板「Add another Path」的欄位對照（Container Path `/data`、Host Path 某值），措辭照票 55 的實測。
3. 同一台服務缺 `/data` 時，頁 3 合併成一則，列出受影響的媒體庫。
4. 既有 Jellyfin 在頁 1 連線成功、成為擁有者之後，探一次 `/data` 看不看得到（沿用頁 3 的探測檔與 `ValidatePath`），看不到就在頁 1 說，補法同頁 3。
   - 這會動到寫入白名單閘門：照票 46 的做法放行，並做雙向變異。
5. 測試失敗時收起黃色 localhost 提示；技術細節的位址帶上 scheme。

## 驗收

- [x] 整合測試：補法帶真正的值；相對路徑的提示；頁 1 的 Jellyfin `/data` 探測（雙向，白名單閘門跟著改）
- [x] vitest：合併的補法、Unraid 格式、localhost 不重複（zh-Hant 與 en）
- [x] 實跑：既有 Jellyfin 與 qBittorrent 都不掛 `/data`，照畫面的補法一次修好，附截圖
- [x] 全部檢查、test、前端 e2e 綠燈；README guide（接既有服務）、brief §16.4 同步；progress.md 記一行

## Comments

- 2026-10-08 票 55 補（`docs/research/unraid-trial-2026-10-08.md` §6 U6）：使用者 Unraid 上的模板欄位是 `<Config Name=… Target="容器路徑" Mode="rw" Type="Path">宿主路徑</Config>`，畫面上是「Add another Path, Port, Variable, Label or Device」→ Config Type Path、Name、Container Path、Host Path、Access Mode（Unraid 7.1.4 `dynamix.docker.manager` 的介面字串）。CA 的 `jellyfin/jellyfin` 模板預設把媒體掛在 `/data/tvshows`、`/data/movies`，加 Berth 的 `/data` 之後是巢狀掛載（沒實測），補法要說這種情況。
- 2026-10-14 實作（commit 見 git log）：
  - 實跑截圖在 `63-copyable-mount-remedies/`：`p1-jellyfin-no-data.png`（頁 1 擁有者成立後就紅，片段帶 `C:/…/data:/data`，Unraid 欄位展開）、`p2-qbittorrent-no-data.png`、`p3-merged-notice.png`（Jellyfin 還沒修時兩個媒體庫合併一則、一份補法）、`p1-after-fix.png`、`p3-after-fix.png`（兩條 Route 6/6）。環境：Docker Desktop 29.6.2，`deploy/docker-compose.yml` 的隔離副本（`berth-t63`、子網 172.63、image 從工作樹 build），`.env` 的 `DATA_ROOT` 是 Windows 反斜線路徑；既有服務是 Jellyfin 12.1（掛 `/tv`、`/movies`）與 qBittorrent 5.2.3（掛 `/downloads`）。各照畫面多加一行、`docker compose up -d`，同一顆鍵重測就過。跑完全部 `down`、image 刪掉。
  - code-review 沒處理的：(1) Route 檢查列沒有合併（理由在 progress.md 偏差）；(2) `MountFix` 的巢狀掛載那一句寫成定論，但只在 Docker Desktop 實測、沒在 Unraid 上跑（brief §20.14 寫明）；(3) 判斷題的 smell：`claim_owner` 自己組 `ServiceConnection`（與 `_stored_connection` 相近，多一個位址比對）、五條補法裡「多加一條掛載…」那半句中英各重複、`detailLabel` 與 `fixOf` 各自列 `data_*` 三種、`root` 與 `host` 一起傳；(4) `asked_jellyfin_about_shared_root` 是「不是空轉」的斷言，沒有自己的變異測試。
  - `tests/integration/test_rss.py::TestTwoRoundsAtOnce::test_only_one_round_runs_and_neither_fails` 在整套 pytest 與前端 e2e、docker build 同時跑時紅一次，單獨跑 3/3 綠；與本票無關，記下給下一次碰到的人。
