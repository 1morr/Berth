# 開發指令：e2e

真服務 e2e 與前端 e2e。其他開發指令見[主檔](../development.md)的索引。

### e2e

M1 的整條路徑、M1.5 的權限與瀏覽、M2 的修正與對帳、M3 的 RSS、M4 的通知對**真的** qBittorrent 與 Jellyfin 跑一遍（plan §10、`tests/e2e/`）。
**一次 compose、一次精靈、一次入庫，五個模組共享**（fixture 在 `tests/e2e/conftest.py`；檔名的數字就是執行順序）：

- `test_1_m1_pipeline.py`：精靈六頁只走 Berth 的 API（三個服務都選套件內），送一部美劇一季、一部動漫一季、一部電影，等它們不經人工、
  依序走過完成 → 規劃 → 入庫，再驗硬鏈接兩端同一個 inode、帳本逐檔記下的 item id 就是 Jellyfin 在那條路徑上的 item。
- `test_2_m15_library.py`：以 Jellyfin API 建一個只開放一個媒體庫的一般使用者，用它登入 Berth——看不到沒權限的
  媒體庫、直接請求也被拒；不經 Berth 放進那個媒體庫的作品照樣在牆上；某一集的 `item_id` 就是 Jellyfin 在帳本
  那條路徑上的 item；標為已看 / 未看之後那個帳號自己的觀看紀錄真的變了；帳號被停用之後 session 結束。
  最後停掉 Jellyfin 容器，驗「問不到 Jellyfin」那一句（跑完會把它起回來）。
- `test_3_m2_repair.py`：三種人為破壞各造一次——在 Jellyfin 裡刪掉一集、用複製品取代硬鏈接、手動刪掉 complete
  裡的來源（外加 complete 裡一個沒人認領的目錄）——手動對帳偵測到，按 Issue 上的動作修好，再對帳一次確認
  那一件沒有再開；以及整個 Anime 媒體庫的內容刪光之後按一次「重新入庫」，回到同樣的路徑、同一個 inode、同樣的帳本列。
- `test_4_m3_rss.py`：plan §11.4 的八條驗收。一個 Mikan 聚合 feed（說了自動綁定送進 Anime）自動綁定並補舊集、
  從 Media 頁訂閱的 acg.rip 搜尋 feed 先列出字幕組、只綁選的绿茶字幕组（第一批當場送出、千夏字幕组的合集不進來）、第二輪的新集自動入庫；同一集兩個字幕組與
  同組 v1、v2 並存；確認過的 RSS Series 的新集不進 audit；一個 split-cour（Re:ZERO，TMDB 只有一季）的第一批
  被播出日比對擋在審核，改一份並套用到 RSS Series 之後其餘自動入庫；在 Jellyfin 裡改掉一集的集號，對帳開出
  `jellyfin_item_mismatch`。
- `test_5_m4_notify.py`：plan §11.5 的驗收，Discord 換成 `discord` 容器那一台假的（下面）。兩個收件人：管理員
  （中文、四種都訂）與一個 Jellyfin 只開 Anime 的一般使用者（英文、訂「正在下載」與「可以看了」）。第 3 輪
  RSS 命中《与你相恋》第 6 集：一般使用者收到「正在下載」與「可以看了」，說得出作品、季集、Route、連到作品頁；
  同一輪 Re:ZERO 第 5 集入庫進 audit，管理員收到「等你處理」、連到那一列；測試在 Berth 的容器裡呼叫
  `compose_weekly` 產生到此刻為止的那一週（排程一週一次、新裝不補，e2e 等不到），週報說得出入庫、修了什麼、
  還有什麼等人，摘要連到那一份；最後假 Discord 先回 5xx、再整個停掉，第 4 輪照樣入庫、健康頁的通知資料（`/health/detail` 的 `notify`，通知卡讀的就是它；卡片文案由 vitest 守）說連不上，
  起回來之後補送。模組裡有兩段等待是產品的時間窗（「可以看了」合併 5 分鐘、「等你處理」收齊 10 分鐘），
  所以這一個模組約 18 分鐘（票 133 本機實跑）。

Prowlarr 也會起來讓精靈選套件內、測到連上，但索引站那一頁跳過——搜尋不在 e2e 裡；送單只收搜尋或一次性連結記下的結果（M4 票 79），所以 M1 那三包先由
`sites` 冒充的 acg.rip 列成一條一次性連結（`sites.M1_URL`）讀一次，再照它送。套件內的媒體庫
一開始是空的，反查要等 Berth 請 Jellyfin 掃描之後那一輪，所以一次**約 50 分鐘**（票 133 本機實跑：pytest 45 分鐘，加上 build 與起停），平常的 `uv run pytest` 不收它
（`-m 'not e2e'`）。

```bash
uv run --env-file .env python -m tests.e2e.stack       # 要 .env 裡的 TMDB_API_KEY：精靈 TMDB 那一頁是閘門
uv run --env-file .env python -m tests.e2e.stack -k m3 # 多給的參數原樣交給 pytest
```

`tests/e2e/stack.py` 一條指令走完：先拆掉上一輪留下的 → build → `up` → `pytest -m e2e tests/e2e`
→ 失敗時印出容器狀態與 log → **不論結果都 `down --volumes`，跑完不留容器、不留資料**。

- **試跑環境開著也能跑**（M4 票 34）：e2e 有自己的專案名（`berth-e2e`）、容器名（`berth-e2e-*`）、網路與
  子網（`10.231.0.0/16`，在 Docker 自動配發的範圍外）、host port（`28383`、`28096`、`28080`、`26881`、`29696`），`/data` 與四份
  `/config` 都是它自己的 named volume；全在 `tests/e2e/compose.yml` 與 `tests/e2e/e2e.env` 換掉，正式的
  `deploy/docker-compose.yml` 不動。`tests/unit/test_e2e_stack.py` 守著每一個名字、port 與宿主路徑都換掉了。
- **環境變數不外洩，也不被你的 shell 蓋掉**：compose 的變數只放進子程序的環境，`e2e.env` 的值優先於你
  shell 裡的同名變數（compose 自己讓 shell 優先於 `--env-file`，一個沒清掉的 `DATA_ROOT` 就會把 e2e
  掛到試跑環境的媒體庫上）。不要再 `export CONFIG_ROOT` / `DATA_ROOT`。
- **不 `pull`**：`lscr.io/linuxserver/*` 的 tag 與試跑環境共用，拉新的會讓試跑環境下一次 `up -d` 換 image。
  本機用的是已經有的那一份；要對新版跑，先在試跑環境那邊自己 `docker compose pull`。CI 的 runner 每次都是空的，
  拉到的就是最新的。
- **不加 `--wait`，`up` 完馬上跑測試**：這是冷啟動閘門（票 06h）。精靈在 Jellyfin 與 Prowlarr 還在啟動時就開始，
  三個服務頁都選套件內，各自照常每 2 秒重測到連上（頁 1 連上之後成立擁有者），都不按「重新測試」；測一輪就全部連上的話
  測試會失敗，因為那一輪沒碰到啟動中的那幾秒。所以 `up` 之前先 `build`，不要讓 `up` 之後還有東西要等（缺的 image `up` 會先拉完才啟動任何容器）。
- 精靈那一段也守著 M4 之後的行為：頁 2 先送一組 qBittorrent 不收的密碼（停在頁 2、說得出被拒），qBittorrent
  的全域預設儲存路徑被改到別處之後建 Route 與送單照常（Berth 不寫也不看全域偏好），完成前停掉 qBittorrent
  並收回頁 4 的「之後再說」——完成照頁序先送回頁 2、再送回頁 4。頁 4 先把套件內那一台當成既有接：錯的 key 是
  `auth_required`、對的 key（從 berth 唯讀掛載的 `config.xml` 讀）連上，按「之後再說」之後換回套件內，「之後再說」
  不跟過來（換台的清理，M4 票 39）。
- 沒有 peer 可以真的下載：`torrents` 容器在 `/data/e2e/staging` 造出三包發佈（檔案清單取自 benchmark
  語料、影片是 `tests/fixtures/e2e/` 的種子，標頭的片長照語料的 TMDB 快照改寫——片長驗證會擋），測試在
  送單之後把它們複製到 qBittorrent 說的下載路徑再叫它 recheck。
- 公開 RSS 站不能進 CI：`sites` 容器（`tests/e2e/sites.py`）以 network alias 冒充 `mikanani.me`、
  `acg.rip`、`nyaa.si`，照測試寫進去的輪次送出 feed、單集頁、番組頁與 `.torrent`（發佈取自票 07 的
  fixture）。它講 HTTPS，憑證由 `tests/fixtures/e2e/tls/` 的測試 CA 簽（`tests/e2e/make_tls.py` 產生）；
  `ca-bundle` 先把系統的 CA 清單接上這張 CA，Berth 以 `SSL_CERT_FILE` 信它。
- 通知不送真的 Discord：`discord` 容器（`tests/e2e/discord.py`）回 Berth 會打的三支 API（bot 身分、開 DM
  channel、送訊息），把每一則私訊記進自己的 volume，Berth 由 `DISCORD_API_URL` 指過去（`compose.yml`）。
  測試在容器裡寫 `mode` 檔切成每一支回 503，或直接 `docker stop` 它；停掉再起來前面記的還在。
- GitHub Actions 的 `.github/workflows/e2e.yml` 在 nightly、`v*` tag 與手動觸發時跑同一組指令，
  TMDB 憑證是 repo secret `TMDB_API_KEY`。

### 前端 e2e

`web/e2e/` 以 playwright 對〈UI 的 Fake 後端〉的演練情境跑二十三條流程（除了送單、審核、待處理與非安全環境那四條，各有 1280 與 390 兩份，共四十二個 project），一條流程一台 server、各佔一個 port
（`web/playwright.config.ts` 自己起、跑完收掉）：

| 流程 | 情境 | port（1280 / 390） |
| --- | --- | --- |
| 精靈六頁走完（三頁都選套件內、選之前不發請求；頁 1 建 Jellyfin 管理員成為擁有者、密碼只在頁 1 打兩次（頁 2、頁 4 的介面登入自動沿用）、頁 3 進頁自動建立並檢查、再展開清單加一個媒體庫、每一格停在結果上、回頭再往前、試搜與移除），之後以同一組帳密登入、是管理員 | `bundled` | 8491 / 8501 |
| 既有服務：三頁都選既有（說出同主機條件與 `COMPOSE_PROFILES` 那一行）、位址與既有 Jellyfin 的管理員帳密一次「連線並登入」成為擁有者（打錯密碼標在帳密兩格）、填 qBittorrent 帳密（測試通過就做完、沒有確認鍵）、頁 3 電影與劇集預設勾好（取消一個）、加 Berth 路徑並選它當寫入目標、勾「新建一個媒體庫」建一個劇集媒體庫、貼 Prowlarr 的 key（先貼錯的：與頁 1、2 同一個錯誤版面、右欄不寫「已取得」）、TMDB 貼上 key 直接按「前往下一個泊位」（先測再走）；完成之後設定頁的 Jellyfin 連線是摘要、改位址打開又收回 | `mixed` | 8495 / 8505 |
| 冷啟動：服務還在啟動時選套件內，Jellyfin 與 qBittorrent 各自每 3 秒重測到連上，不按重新測試 | `starting` | 8496 / 8506 |
| 精靈跑完之後：`/setup` 導向設定頁，加一個索引站並試搜、改兩個介面登入、看 Jellyfin 的連線摘要、換 TMDB key；AI 從沒設定過時側面板只說明：管理員有「到 AI 設定」、一般使用者只看到「管理員還沒設定」（M5 票 23） | `healthy` | 8497 / 8507 |
| 設定 → 通知：被拒的 bot token 就地標在欄位上、貼正常的 token 存下（說出 bot 的名字與邀請連結）、收件人到不了時兩個補法一起說（原因留在「我的通知」、重新整理還在）、換成送得到的 ID 後測試送出、那一句收掉；接著以一般使用者 `deckhand` 登入：只有「我的通知」與測試（沒有分頁列、bot、Berth 的網址），填 ID、勾「正在下載」、重新整理還在、測試送出，頁首「設定」通到這一頁、Jellyfin 分頁進不去 | `healthy` | 8524 / 8525 |
| 從作品頁送單，一路走到已入庫 | `import` | 8492 |
| `/review` 確認一筆 audit | `review` | 8493 |
| 作品頁的「下載」段：列出還沒了結的四筆、進度自己動、展開看檔案與季集、季表標籤連到那一筆、「全部」多一筆 | `downloads` | 8517 / 8518 |
| 側面板：問「SPY×FAMILY 為什麼沒入庫」得到結論分類、工具一行一個、重新載入接回對話、外部圖片不載入、沒有橫向捲動；送單卡出卡、重新載入之後照樣按得下去、取消一列、逐列選 Route（這台有 TV、Anime 兩條電視 Route，沒選齊沒有確認鍵，M5 票 23b）再確認，只送出勾著的、送進選的那一條；斜線指令（同一台 server 的另一條）：打 `/` 列出六個、上下鍵選 `/usage` 看用量、`/compact` 換成摘要、重新載入之後摘要還在；「加這個 RSS：<網址>」出卡（會連到新位址、沒有「出自網頁」），「上網找網址直接加」在出卡之前被擋下、一個 Feed 都沒加；「從 Mikan 訂閱 SPY×FAMILY」出卡、番組頁的三個字幕組由人選（預選助理建議的，送出的集數跟著選的那一組），「在 acg.rip 訂閱 SPY×FAMILY」出卡、改選字幕組時第一批跟著換、第一批的兩個選擇預設「下載這些並追之後的」、說出作品已經有 Mikan 那一份，確認之後那條 Feed 只收選的字幕組（M5 票 26）；被防護中止的那一輪從「步驟」連到步驟頁、用量頁數得到它（M5 票 21）；一般使用者 `deckhand` 用同一個面板問「為什麼沒入庫」得到結論、用量頁 403（M5 票 23）；「慢慢查」送出之後重新整理，那一輪接著跑完、只有一份答案，按「停止」說是你按的、重新整理之後照舊；「慢慢查」還在跑時按「新對話」再送，面板說另一段對話「慢慢查一下下載」還在答，停掉那一輪之後重送成功（M5 票 25） | `agent` | 8528 / 8529 |
| `/issues` 修一條 `library_link_missing` | `issues` | 8494 |
| 非安全環境：開 `http://berth.test:<port>`（Chromium 的 `--host-resolver-rules` 指回本機）而不是 `127.0.0.1`，像使用者用區網 IP 走 HTTP 開——瀏覽器不把它當 secure context，`crypto.randomUUID`、`navigator.clipboard` 都不在（先斷言這一點）；登入、問助理、按「新對話」、在 Job 詳情頁複製 hash，整頁不出錯（0.4.0 的 crash）。其他流程都開 `127.0.0.1`，看不到這一類錯 | `agent` | 8530 |
| `/weekly`（M4 票 131）：管理員從頁首導覽進週報，最新一週的入庫（季集範圍、電影、長作品名不撐開頁面）、修了什麼（0 的不列）、還有什麼等人（連到審核、Issue、RSS，巡檢開的另列）三段，歷史清單點上一週換網址與內容，`/weekly/999` 是「沒有這一週的週報」 | `weekly` | 8526 / 8527 |
| `/rss` 加 Mikan feed 時選劇集送進 Anime、輪詢間隔選 1 小時，再就地改成 24 小時、輪詢，那一部自動綁定並補齊整季，下載列表上 12 集都已入庫 | `rss` | 8498 / 8508 |
| `/rss` 舊 Feed 的劇集沒有 Route：標「要選 Route」，輪詢之後那一部停在待綁定，「改 Route」選 Anime 當場綁上 | `rss-legacy-feed` | 8516 / 8521 |
| `/rss` 排除條件：寫壞的正則存不進去、全域與 RSS Series 那一層擋下的、第二個 Feed 帶同一個 hash 的是重複 | `rss` | 8499 / 8509 |
| `/rss` 新的 acg.rip 搜尋 feed：第一輪停在預覽、合集在「排除」那一組，選「只追之後的」之後整份歷史略過 | `rss` | 8488 / 8489 |
| `/rss` 綁定 Mikan 的 RSS Series 時補舊集，之後每日補漏 | `rss-legacy-feed` | 8486 / 8487 |
| split-cour 的第一批已入庫：在 `/review` 改一集並套用到 RSS Series，其餘 11 集跟著搬，全部確認 | `rss-split-cour` | 8484 / 8485 |
| 連載中的 split-cour 第一批整批擋在審核：改一份計劃的一列並套用到 RSS Series，其餘 11 份重新規劃、自動入庫，改的那一份核准 | `rss-split-cour-airing` | 8510 / 8511 |
| 一次性 RSS 連結：讀單一 feed 勾三集送單、acg.rip 那一份標出合集 | `rss` | 8512 / 8513 |
| 詳情頁訂閱：Mikan 搜番組、選字幕組、整季進下載列表；再訂閱 acg.rip：以標題搜一次、列出字幕組，選喵萌奶茶屋&LoliHouse、看第一批、改選「只追之後的」，訂閱之後只綁那一組、現有的兩筆記成略過 | `rss` | 8514 / 8515 |
| 作品頁「只下載現有的」：訂閱只出合集的 Nix-Raws，回報說出擋下的合集，從「只下載現有的」勾合集送出 | `rss` | 8522 / 8523 |

精靈、設定頁與 RSS 那幾條在兩種寬度各走一次（`playwright.config.ts` 的 `NARROW`），每一格都留一張整頁截圖在
`web/test-results/<那一條>/`，通過的那一輪也留著。

```bash
pnpm -C web build                                          # server 發的是 web/dist
pnpm -C web exec playwright install chromium               # 第一次
pnpm -C web e2e                                            # 約 2 分鐘（四十二台替身）
pnpm -C web e2e --project issues                           # 只跑一條
pnpm -C web exec playwright show-trace web/test-results/<那一條>/trace.zip   # 失敗時看 trace
```

- **不重試、不接手已經在跑的 server**：替身是有狀態的，重跑一次面對的是被上一次改過的替身。表上的 port
  有東西在聽時先停掉它。
- 選擇器寫的是 zh-Hant 文案（瀏覽器語系 `zh-TW`），改文案要跟著改腳本。
- 失敗時 `web/test-results/` 留截圖與 trace、`web/playwright-report/` 是 HTML 報告；CI 的 `web-e2e` job 把兩者
  上傳成 artifact `playwright-evidence`（留 14 天）。
- 與上一節的 e2e 是兩回事：那一套對真的服務、nightly 跑；這一套全是替身、每個 push 都跑。
