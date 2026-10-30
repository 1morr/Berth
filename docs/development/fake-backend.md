# 開發指令：UI 的 Fake 後端

UI 演練用的 Fake 後端。其他開發指令見[主檔](../development.md)的索引。

### UI 的 Fake 後端

精靈與健康頁的 UI 不必真的有四個容器也能實跑：`scripts/fake_setup_server.py` 起一台真的 Berth
（真的 API、真的資料庫、真的前端 build），只把三個外部服務換成 `adapters/*/fake.py`。

```bash
pnpm -C web build                                          # 先有前端產物
uv run python scripts/fake_setup_server.py                 # http://127.0.0.1:8484
uv run python scripts/fake_setup_server.py --scenario mixed
uv run python scripts/fake_setup_server.py --port 8383     # 換 port（索引站給的下載連結跟著走）
```

`--port 8383` 是後端的預設 port（`berth/config.py` 的 `DEFAULT_PORT`），也就是 `web/vite.config.ts` 代理
`/api` 的去處——想對著某個演練情境跑 `pnpm -C web dev`（改前端存檔就重載）時用它。

| `--scenario` | 演的是什麼 |
| --- | --- |
| `bundled`（預設） | 乾淨的 compose：三個服務選套件內都連得上、全部走得完。九個預設索引站裡有四個連不上（訊息取自真的 Prowlarr 那一輪），逐站成敗看得到；加完之後試搜，Mikan 演「搜尋時連不上」，其餘站各回幾筆 |
| `outdated` | qBittorrent 的 Web API 低於 2.8.4：頁 2 拒絕接入並給升級指令 |
| `mixed` | NAS 的常見組合：既有 Jellyfin（跑過自己的精靈、兩個媒體庫，其中一個掛 TVDB；管理員 `owner` / `s3cret`）、qBittorrent 已設密碼（選既有：帳密只收 `admin` / `adminadmin`，即 `NAS_QBITTORRENT_LOGIN`；位址的主機名帶 `typo` 是連不上、帶 `old` 是太舊的 4.3.9，其餘位址都接得上；選套件內是「要求帳密」）、Prowlarr 已有索引站。三頁都選既有才走得完。兩個媒體庫的舊路徑是暫存目錄底下真的存在的 `nas/movies`、`nas/anime`，Route 的第三條纜繩才看得到它們，精靈走得完 |
| `mixed-no-sites` | 同 `mixed`，但既有 Prowlarr 一站都沒有：頁 4 待處理，主鍵「測試推薦站，加入通過的」把通過的推薦站加進它（M4 票 67） |
| `starting` | 四個容器同時起來（票 06g 量到的時間線，照測試次數演，前端每 3 秒一次）：選了套件內之後 Jellyfin 先回不像它自己的東西、再回兩次 503「還在載入」，約 9 秒後連上；qBittorrent 第一次連不上；Prowlarr 連不上五次，約 15 秒。不必按「重新測試」，之後與 `bundled` 一樣走得完 |
| `key-missing` | 同 `bundled`，但 Prowlarr 的設定目錄沒有唯讀掛進 Berth：頁 4 選套件內之後讀不到 API key，就地貼上 |
| `unlisted` | 同 `bundled`，但 Prowlarr 連不上 `indexers.prowlarr.com`（M4 票 73）：頁 4 選套件內之後推薦站一個都不在，主鍵的位置說出原因與下一步。`curl -X POST http://127.0.0.1:8484/demo/prowlarr/online` 演網路通了，按「重新讀取」主鍵就回來 |
| `absent` | Jellyfin 不在 `COMPOSE_PROFILES` 裡：頁 1 進頁「套件內」卡片就說它沒在跑、給起回來的兩種補法，選了是「主機名解不到」；改選既有、填任何位址就接得上 |
| `berth-only` | 只有 Berth（`COMPOSE_PROFILES=`）：三個服務頁的「套件內」卡片進頁都說沒在跑；其餘同 `absent` |
| `old-jellyfin` | 既有 Jellyfin 還停在 10.11（其餘兩個服務照 `bundled`，擋路的只留一個）：頁 1 擁有者那一步紅燈，說出目前版本、為什麼要 12，以及升級前後要做的事；健康頁上同一台也是紅的 |
| `signed-out` | 精靈已跑完，畫面從登入頁開始。`skipper` / `harbour` 是管理員，`deckhand` / `rope` 是普通使用者（看不到設定入口）。設定 → AI 的「測試連線」不出網（每個情境都一樣，`adapters/ai/fake.py`）：key `rejected` 是 key 被拒、模型 `missing-model` 是找不到，其餘一律連上 |
| `unmounted` | Jellyfin 少了媒體庫目錄的掛載：泊位 4 的第四條纜繩失敗，看「哪個容器少了哪個掛載」與 compose 修正片段 |
| `rss` | RSS 頁 `/rss`（M3 票 08）：同 `healthy`，一個請求都不出網。**伺服器的時鐘從 2026-09-25 12:00 UTC 起走**（錄下的 Feed 的隔天，`Scenario.clock`，M5 票 01）：「安靜 30 天算完結」拿牆上時間比錄下的日期，用真的時間的話過了那一天整份就收進「已完結」；瀏覽器照真的時間，畫面上的「幾天前」會多算一段。Mikan 是替身：加 `https://mikanani.me/RSS/MyBangumi?token=REDACTED`（任何 token 都一樣，替身只認這一條網址）；TV 與 Anime 都收劇集，所以「劇集送進」要選（M4 票 105，選 Anime），「電影送進」預填 Movies。按「立即輪詢」，票 07 錄下來的聚合 feed 12 筆長出 11 個 RSS Series（單集頁照 `tests/integration/test_rss.py` 合成）。TMDB 也是替身，搜「Kimi ga Shinu made Koi wo Shitai」或「与你相恋到生命尽头」找得到那一部；《与你相恋到生命尽头》的番組頁在，輪詢時就自動綁到它與 Feed 說的 Anime（整季補齊，M4 票 78 起沒有不補的選項），其餘 10 個番組頁查不到、留在待綁定。12 集的 `.torrent` 換成這台自己生的，qBittorrent 收下就當場完成，幾秒後 `/jobs` 上 12 筆都已入庫。票 11 起另有錄下來的 acg.rip 搜尋 feed：加 `https://acg.rip/.xml?term=Kamiina+Botan`、按「立即輪詢」，30 筆停在頁首的第一輪預覽（8 筆合集被排除）。票 19 起在《与你相恋》的詳情頁（`/media/tv:262000`）按「新增訂閱」：以任何一個名字搜 Mikan 都是番組 4009（搜尋頁是合成的），訂閱喵萌奶茶屋&LoliHouse 就是整季 12 筆；acg.rip 以任何一個名字建搜尋 feed 讀到的都是錄下來的《与你相恋》那一份。帳號同 `signed-out` |
| `rss-legacy-feed` | 舊 Feed 選 Route（M4 票 105）：同 `rss`，但聚合 feed 已經在了，是票 105 之前加的——劇集那一格是空的（TV 與 Anime 兩條，migration 推不出來），電影那一格是 Movies。Feed 列標「要選 Route」；輪詢之後《与你相恋》認出來了、停在待綁定（`route_ambiguous`，作品預填成候選，也是手動綁定與補舊集的演練起點）；按「改 Route」選 Anime，確認區說會當場綁上 1 部，存下之後它綁上、補齊整季 12 集 |
| `rss-split-cour` | 改正並套用到 RSS Series（M3 票 13）：同 `rss`，但 TMDB 把《与你相恋》的兩個 cour 併成一季 24 集。綁定時補舊集，12 集全部落在 S01E01–E12（錯的：字幕組的第二 cour 從 01 重數），在 `/review` 是這個 RSS Series 的第一批、一組；把第 1 集改成 S01E13 並勾「套用到這個 RSS Series」，其餘 11 集跟著搬到 14–24，再按「全部確認」 |
| `rss-split-cour-airing` | 從審核裡套用到 RSS Series（M3 票 14b）：同 `rss-split-cour`，但第二 cour 正在播（2026-07-02 起）。綁定時補舊集，12 集照字面對到一月播出的 S01E01–E12，播出日比對把 12 份計劃整批擋在 `/review` 的「要你決定」、一集都沒入庫；在第 1 集那一份按「改」、起集填 13、勾著「套用到這個 RSS Series」套用，其餘 11 份重新規劃、自動入庫（第一批，等全部確認），改的那一份等你核准 |
| `rss-runtime` | 片長驗證（M3 票 15）：同 `rss`，但 mediainfo 是替身——檔名第 11 集的量到 12:05，其餘 24 分鐘（TMDB 每集 24 分鐘）。綁定《与你相恋》之後第 11 集那一份停在 `/review` 的「要你決定」，理由說出兩個片長；其餘 11 集照常入庫（第一批） |
| `healthy` | 精靈已跑完、三條 Route 綠燈、四項健康檢查全綠：健康頁 `/health` 與設定頁 `/settings/*`（五個分頁：換 TMDB key、加站試搜移除都在這裡演得出來）的起點。帳號同 `signed-out` |
| `degraded` | 同上，但索引站在第一輪檢查之後掛掉：按「立即重測」就會看到那一項變紅、其餘三項不動，以及「最後成功」還留著。每個情境都有 `curl -X POST http://127.0.0.1:8484/demo/prowlarr/stop`（`start` 起回來）演 `docker compose stop prowlarr`：健康檢查、站的清單與作品頁的搜尋都連不上（M4 票 61 的「不用 Prowlarr」實跑用它） |
| `review` | 審核佇列 `/review`（M2 票 06）：同 `issues`，另外 SPY×FAMILY 第二季兩集（只寫絕對集號 26、27，累計換算成 S02E01、S02E02，信心 medium）真的硬鏈接進媒體庫、帳本與 Plan Item 都掛 audit。按「確認」清旗標；按「撤銷」真的把那一條鏈接拆掉，那一筆下載回到待審核——之後以 `deckhand` / `rope` 登入，`/jobs` 與 SPY×FAMILY 的詳情頁說「等管理員審核」。這兩集是同一筆下載，收成一組、收起時說出為什麼是 medium，按「全部確認」一次清掉（M3 票 05）。Issue 不在這一頁（M3 票 05），頁尾一行「另有 N 件待處理」連到 `/issues`。另有一筆 `- 05` 下載完成（M2 票 07）：只寫集號、沒超過第一季的 25 集，規劃器算成低信心、提案 S01E05，停在「要你決定」那一段——逐列改季集看目標路徑當場換掉，按「核准並入庫」真的硬鏈接進媒體庫；按「拒絕」就重新規劃。再一筆 S01E03 + OVA 下載完成（M2 票 08）：媒體庫裡已經有一份一模一樣的 S01E03（路徑與 Tags 照解析器算），所以規劃器略過它、佇列上一列「重複」（取代 / 保留兩者 / 跳過，都真的動磁碟）；OVA 2 對不到任何一集，佇列上一列「對不到」，指派到 S00E02 真的建硬鏈接。伺服器起來約 60 秒後規劃器第一輪才算出這兩列 |
| `downloads` | 作品頁的「下載」段（M4 票 12）：同 `import`，SPY×FAMILY 已經有五筆下載——`- 08` 在 qBittorrent 排隊（`queuedDL`、還沒有檔案清單）、`- 25` 下載中而且替身每一輪多 7%（5%–95% 循環，看得到進度自己動；pre-plan 提案 S01E25 待審，季表那一集是「下載中」）、`- 01` 停在待審核（季表 S01E01「卡住」）、`- 05` 已入庫一個檔案待確認、`- 04` 已入庫確認過（只在「全部」） |
| `agent` | 側面板（M5 票 12）：同 `downloads`，另外 AI 開著、模型是照腳本回答的替身（`why_not_script`，不出網、不需要金鑰）。問「SPY×FAMILY 為什麼沒入庫」（或 `Why isn't SPY×FAMILY in the library?`），它先叫搜尋作品、再叫「為什麼沒入庫」，用工具結果的結論分類回答（`- 01` 停在待審核，結論 `awaiting_review`）；問到「圖片」時回一張外部圖片的 markdown（面板只印網址、不載入）；說「下載 SPY×FAMILY」（`Download SPY×FAMILY`）時搜作品、搜發佈、問 Route，再出一張三列的送單卡（`- 04` 到 `- 06`，M5 票 13；送的是第一條 Route，而這台有兩條電視 Route、作品沒送過單，所以卡片上每一列要人選，票 23b），按了之後照逐列結果說送了幾筆；說「加這個 RSS：<網址>」（`Add this RSS: <address>`）時列 Route、再出一張加 Feed 的卡（M5 票 14）；說「上網找 RSS 網址直接加」（`find … on the web`）時拿一個它「在網頁上找到」的網址去加，被守法擋下（網址不是使用者打的），照擋下的理由回答；說「從 Mikan 訂閱 SPY×FAMILY」（`subscribe on mikan SPY×FAMILY`）時搜作品、問 Route、讀番組頁（合成的番組 3310：Berth-Demo 3 集、LoliHouse 12 集、北宇治字幕组 6 集，各有單一 feed），出一張 Mikan 訂閱卡、建議 Berth-Demo；說「在 acg.rip 訂閱 SPY×FAMILY」（`subscribe on acg.rip SPY×FAMILY`）時搜作品、問 Route，出一張關鍵字訂閱卡（合成的搜尋：Berth-Demo 3 筆、ToonsHub 2 筆、黒ネズミたち 1 筆，下載連結是 magnet），按完照卡片上選的字幕組回答（M5 票 26）；壓縮（`/compact`，M5 票 18）的摘要是被換掉的那幾句使用者的話；說「一直查」（`keep checking`）時同一個工具同一組參數一直叫，第 4 次被防護中止（M5 票 21：回覆下的「步驟」連到步驟頁，`/settings/usage` 數得到它）；說「慢慢查」（`take your time`）時翻三頁 Job，每一次模型呼叫先等 1.5 秒（`slow_pause`），最後說翻完了（M5 票 25：重新整理時那一輪一定還在跑）；其餘一律說它只演這幾件事。AI 沒開的樣子用其他任何情境看（`skipper` 看到去設定頁的連結，`deckhand` 看到「管理員還沒設定」） |
| `agent-live` | 側面板對**真模型**跑情境（M5 票 23）：同 `search`（真 TMDB、`BERTH_INDEXER_*` 的索引站），另外模型、網路搜尋、AniList 季表、Bangumi 放送表都打真的；qBittorrent 是收下就一直在下載的替身（確認卡可以放心按，「為什麼沒入庫」答得出「還在路上」）。AI 一開始關著：到 AI 設定填 key，或交給 `scripts/experiments/m5_acceptance_scenarios.py`（`uv run --env-file .env python scripts/experiments/m5_acceptance_scenarios.py`，每種接口自己起一台全新的、照 `.env` 的 `AI_*` 填好再逐句送出、卡片全按確認；結果在 `.local/experiments/results/m5_acceptance/`）。**會花模型的錢** |
| `agent-live-missing` | 補缺集對真模型（M5 票 23d）：替身 TMDB 的 SPY×FAMILY 第一季 12 集都播過、一集都沒有，替身索引站只有單集發佈（Fast 只做前 6 集、做種多排在前面，Slow 每一集一個）；模型與網路搜尋打真的、qBittorrent 收下就留著。驅動 `scripts/experiments/agent_sources_ab.py --set missing --groups missing`。**會花模型的錢** |
| `agent-live-jellyfin` | Jellyfin 已經有、帳本沒有（M5 票 28）：同 `agent-live-missing`，但動漫資料也打真的；替身 Jellyfin 的 Anime 庫（`skipper` 看得到）有 SPY×FAMILY（TMDB 120089）S01E01-E04，帳本沒有它，另有這一季最熱門的兩部新番（無 TMDB id）。替身索引站另有一個整季合集 `[Pack] SPY×FAMILY S01 01-12`（做種最多），挑它的卡上那一列會帶 `preview.held`（第 1–4 集）。驅動 `scripts/experiments/agent_sources_ab.py --set jellyfin --groups jellyfin`。**會花模型的錢** |
| `routes` | Route 設定頁 `/settings/routes`（票 14）：同 `healthy`，另外 TV 媒體庫在 Jellyfin 上多掛一顆碟（新增第二條 Route 會全綠）、Movies 多一條沒掛進 Berth 的路徑（在那裡建 Route 會紅、維持停用），TV 那條 Route 有一筆已入庫的下載（刪除鍵換成「刪不得」與一鍵停用）；新增時選 Anime 沒有空路徑，給一條到 Jellyfin 媒體庫設定的連結 |
| `rss-sweep` | 每日巡檢的 RSS 三項（M4 票 130）：同 `healthy`，Mikan 聚合 feed 的每日補漏、Nyaa 搜尋 feed 的輪詢各壞了兩天（`/rss` 的 Feed 列分開說），SPY×FAMILY 綁著一個 RSS Series、帳本缺第 3 集、第 5 集撞了寫著 `- 05` 與 `- 06` 的兩個發佈；起來時由產品的 `sweep_once` 跑一輪，`/issues` 上是輪詢一直失敗、補漏一直失敗、缺集、同一集多份各一件（Feed 那兩件連到 `/rss#feed-<id>`，另兩件連到作品頁）。Feed 的替身一個網址都不認，按「立即輪詢」是讀不到 |
| `weekly` | 週報頁 `/weekly`（M4 票 131）：同 `healthy`，另外三部作品的帳本列（芙莉蓮 S01E01–E03、E05 與 S02E01；一部作品名很長的；一部電影）、三次核准、兩次 rematch、人解決三件與系統收掉一件 Issue、兩筆待審核、四件開著的 Issue（含三件巡檢開的）、一個待綁定的 RSS Series，最後由產品自己的 `compose_weekly` 產生最近兩週的週報：上一週只入庫長名字那部四集、其餘都是 0（歷史清單看得出兩週不同），最新一週是上面那些。起來時就有，不必等週一 05:00 的排程。帳號同 `signed-out`；`deckhand` 沒有導覽項，直接打網址導到健康頁 |
| `issues` | 待處理頁 `/issues` 與對帳（M2 票 05）：同 `healthy`，另外真的入庫一包三集的動漫（來源在 complete、媒體庫那一份是真的硬鏈接），並把其中第二集的媒體庫檔案刪掉——使用者在 Jellyfin 按刪除之後就是這樣。按「立刻對帳」真的比四方並寫下一件 Issue，按「重新鏈接」真的 `os.link` 把它接回來。另外三種破壞（M2 票 09）：第三集被一份一樣大的複製品取代（「以硬鏈接取代」真的換回硬鏈接）、complete 裡一個沒人認領的目錄（「刪除這個目錄」真的整棵刪掉）、媒體庫裡一個手放的檔案（只列出，沒有會刪的按鈕）。管線與健康檢查那幾種（M2 票 09c）：三筆下載到一半的 SPY×FAMILY，替身 qBittorrent 說一筆 `missingFiles`、一筆 `error`、一筆已經不在——起來之後 poller 第一輪就開出三件，「重新校驗」「重試」「重新送單」各自讓它們離開壞掉的狀態；或者 `curl -X POST 'http://127.0.0.1:8484/demo/qbittorrent/fix?hash=<hash>'` 演使用者在 qBittorrent 裡自己修好那一筆（M3 票 02），poller 下一輪（至多 30 秒）把 Job 接回、那一件由系統收掉，時間線多一筆「已接回」；Anime 媒體庫掛著 TVDB，所以一開始就有一件 TVDB（只有「忽略」，按了之後「立即重測」也不會再開）。磁碟空間那一件要到設定的 qBittorrent 那一頁把門檻調到比這台機器剩的還大，`/issues` 當場多一件，調回來當場收掉。認領類三顆（M2 票 10，替身 TMDB 搜得到 `spy`）：媒體庫裡第四集是真的硬鏈接但帳本上沒有它——「認領進帳本」長回一列，`Hand Placed` 那一件按下去說出配不上的理由；qBittorrent 上一筆 `[Sub] SPY×FAMILY - 07` 沒有 Job——「認領並建立下載」選作品，下載列表多一筆；`[Old] Forgotten Batch` 按「重新入庫」選作品，規劃器接手。`/jobs` 上入庫完的那一筆，在它的詳情頁（展開那一列 → 「下載詳情」）有「重新入庫」 |
| `discover` | 探索頁 `/`：三個外部服務仍是替身，但 TMDB 打**真的** `api.themoviedb.org`。憑證從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 read access token 都收），沒設就變成「憑證缺失」那個畫面 |
| `tmdb-down` | 憑證有、TMDB 連不上：探索頁的每個 feed 各自顯示服務回的原文與「重試」，而不是一片空白 |
| `search` | Media 詳情頁的搜尋結果表：TMDB 與**索引站都打真的**。索引站位址從 `BERTH_INDEXER_URL` / `BERTH_INDEXER_KEY` 讀，沒設就退回替身（結果表是空的，那本身也是要驗的畫面）。一次搜尋 35–85 秒 |
| `submit` | 送單與下載列表 `/jobs`：TMDB 打真的，索引站給三筆磁力連結的替身結果（形狀取自真的那一輪）。送單、解析、Job 與時間線走的都是產品自己的程式碼，只有 qBittorrent 是替身 |
| `submit-failing` | 同上，但 qBittorrent 收不下：送單失敗那一列、服務回的原文，以及「重新送單」 |
| `import` | 送單到入庫整條走完、**一個請求都不出網**（M2 票 15 的前端 e2e 用它）：同 `plan` 那一包對得上的批次，但 TMDB 是替身（與 `issues` 同一部 SPY×FAMILY，`/media/tv:120089`）。送到 Anime 之後幾秒就是「已入庫」，詳情頁的「檔案與版本」列出五個檔案 |
| `global-path` | 同 `import`，但使用者在套件內 qBittorrent 把全域預設儲存路徑改成 `/data/my-downloads`（Berth 的容器裡沒有這個目錄，審計 S5）：健康頁三條 Route 照樣綠、送單照常——Berth 不寫也不看全域偏好（M4 票 32） |
| `plan` | 下載完成 → **Import Plan**（票 11）：索引站給兩包替身結果——一包對得上的批次（自動入庫）與一包對不到任何一集的 OST（停在待審核）。qBittorrent 是替身，但它會把那幾個檔案**真的寫進 save path** 並報成 100%，所以 poller 走完狀態機、planner 算出真的 Plan：解析、命名、mediainfo、TMDB 快照全是產品自己的程式碼 |
| `inventory` | Media 詳情的「檔案與版本」與送單到入庫的媒體庫（票 13）：同 `plan` 的兩包，加上一台會「掃到」入庫檔案的替身 Jellyfin。送單之後那一部先在媒體庫頁的「還沒進 Jellyfin」那一條，約 30 秒後 resolver 反查、替身「掃到」它，它就換到牆上；OST 那一包是「待審」篩選要找到的那一格。深連結指向瀏覽器主機名的 8096，那台 Jellyfin 不存在——Jellyfin 那一端要用真的一套驗 |
| `late-scan` | 作品頁的 Jellyfin 狀態與媒體庫頁一致（M4 票 51）：同 `import`，但替身 Jellyfin 第一次被通知滿 170 秒才「掃到」入庫的檔案——resolver 前兩次（30 秒、2 分 30 秒）都沒找到，下一次排在 10 分鐘後，正是審計 S6 的時間線。送到 Anime、等約 3 分鐘再打開 `/media/tv:120089`：「檔案與版本」先問一次就是「Jellyfin 已收錄」，不必等那 10 分鐘 |
| `reinstall-before` | 重裝之前（M4 票 60）：同 `import`，替身 Jellyfin 被通知就「掃到」。**與 `reinstall` 用同一個 `--config-root`**：在這裡送單入庫一部，停掉 server、把 `berth.db*` 搬走 |
| `reinstall` | 重裝之後重跑精靈（M4 票 60，審計 S4）：精靈從頁 1 開始，三個服務是上一次的樣子——Jellyfin 已初始化（頁 1 用 `skipper` / `harbour` 登入）、三個媒體庫還在、替身列出媒體庫目錄裡真的有的檔案，qBittorrent 掛著 complete 底下還在的那一包（一件無主 torrent），Prowlarr 有站；TMDB key 要重貼（替身收任何 key）。完成頁與 `/issues` 上有「從媒體庫重建帳本」，作品頁 `/media/tv:120089` 在重建之前說「Jellyfin 有這部，Berth 的紀錄裡沒有」 |
| `long-lists` | 長清單的收合（M1.5 票 09）：同 `inventory`，但索引站只給 benchmark 語料裡葬送的芙莉蓮 `[7³ACG]` BD 合集（39 個檔案：S01 28 集、S00 11 集）。在芙莉蓮的詳情頁（`/media/tv:209867`）送到 Anime，計劃、入庫與替身 Jellyfin 的反查約一分鐘走完，之後看「檔案與版本」與 `/jobs` 那一列的計劃；名偵探柯南（`/media/tv:30983`，TMDB 併成一季 1216 集）不必送單，打開就是那張季表。需要 `TMDB_API_KEY`。**Windows 上加 `--config-root` 指一個短路徑**（例如 `C:/Users/<你>/t9`）：預設的暫存目錄太深，S00 那 11 個檔案的目標路徑會超過 260 字元而入庫失敗 |
| `library` | 媒體庫頁 `/library` 的整庫瀏覽與權限（M1.5 票 03）：Movies / TV / Anime 三個媒體庫擺好作品（Movies 有 131 部，翻得到第二頁；有一部沒有 TMDB id），海報經 Berth 代理替身 Jellyfin 的 SVG（票 04；`Home Videos 2019` 沒有圖、`Harbour Film 007` 有 tag 但圖不見了，兩格都是「無海報」），Berth 經手的有在牆上的、還沒進 Jellyfin 的、待審與 Unmatched（M2 票 14：`skipper` 在 TV 媒體庫的「待審」是 Slow Horses 一份等審核的計劃，「對不到」是 The Bear 兩個 Extras 檔案，就地按得了；Anime 上是 Frieren 的計劃）。作品有類型與社群評分（票 06：排序、類型與年份篩選看得出差別；Shōgun 的 `War & Politics` 帶 `&`），Home Videos 2019 兩者都沒有。每部劇六集；`deckhand` 看到 The Bear 第三集、第四集看到 18%，看完 Breaking Bad，Slow Horses、Shōgun、Game of Thrones、The Office 各看了幾集，Oppenheimer 看到 42%、Harbour Film 002 看到 65%、看過 Harbour Film 001，`skipper` 看完 Slow Horses、The Bear 看過一集（票 05，標為已看 / 未看寫進替身 Jellyfin，重開伺服器就還原）。所以 `deckhand` 的媒體庫頁上方有繼續觀看與下一集（票 07：劇有 16:9 的 Thumb 或 Backdrop，Harbour Film 002 沒有橫圖是「無圖」；登入後就落在媒體庫——看得到的媒體庫裡有 Berth 入庫的東西時；一筆都沒有時落在探索，M4 票 10——探索頁只放 TMDB 牆，M3 票 06），`bosun` / `knot`（權限同 `deckhand`、什麼都沒看過）兩列都不出現。`skipper` / `harbour` 看得到三個媒體庫；`deckhand` / `rope` 只開放 Movies 與 TV，開 `/library/item-anime` 是「找不到或沒有權限」。`curl -X POST 'http://127.0.0.1:8484/demo/jellyfin/disable?user=deckhand'` 在替身 Jellyfin 停用他（`enable` 復原），至多 60 秒後他的下一個請求被送回登入頁。Media 詳情的觀看區（票 08）：`deckhand` 開 The Bear 是「繼續看 S01E04」、集有劇照；The Office 有兩季與 Specials，主按鈕是「看下一集 S01E05」；Breaking Bad 看完了；Oppenheimer 是電影；SPY×FAMILY 在他看不到的 Anime，頁面上沒有觀看區（`skipper` 開同一頁就有）；`bosun` 開 The Bear 是「從 S01E01 開始看」。有 `TMDB_API_KEY` 時詳情頁打真的 TMDB |
| `poll` | 送單到完成的狀態**自己走完**（票 10）：qBittorrent 打**真的**那一台，所以 `sync/maindata` 會真的換 state、poller 會真的驅動 §3.1 的轉換、SSE 會真的把那一列推著動。位址從 `BERTH_QBITTORRENT_URL` 讀，準備步驟見下方 |

`healthy` 沒有 TMDB 憑證，所以它同時是探索頁「還沒填憑證」的樣子——那一步是精靈的必填閘門
（見 [README〈What you need〉](../../README.md#what-you-need)），畫面要指得出下一步。

```bash
# 把 TMDB_API_KEY 寫進 repo 根目錄的 .env（`.env.example` 有欄位，`.gitignore` 已擋），
# 再用 uv 的 --env-file 帶進去——與 `berth serve` 同一個慣例。
uv run --env-file .env python scripts/fake_setup_server.py --scenario discover
```

搜尋結果表要看真的發佈名——中日英混排、100 字以上、每個字幕組各寫各的，那是替身演不出來的：

```bash
# $KEY 是那台 Prowlarr 的 API key（`config.xml` 的 <ApiKey>）。
BERTH_INDEXER_URL=http://127.0.0.1:19696 BERTH_INDEXER_KEY=$KEY   uv run --env-file .env python scripts/fake_setup_server.py --scenario search
```

下載列表要看它**自己動**——狀態與進度不重整就一路走到「下載完成」——那需要一台真的 qBittorrent，
因為替身收下 `torrents/add` 之後什麼都不會發生：

```bash
# 1. 一台乾淨的 qBittorrent。**發佈 port 必須是 8080**：它的 Host 檢查連 port 都比對，
#    偏移的 port 會讓每一個請求回 401（brief §20.7）。
docker run -d --name berth-poll-demo -p 8080:8080 \
  -e PUID=1000 -e PGID=1000 -e WEBUI_PORT=8080 \
  -v "$PWD/.local/experiments/poll-demo:/config" lscr.io/linuxserver/qbittorrent:5.2.3

# 2. 把那一份 torrent 的資料先放進 category 的 save path，qBittorrent 校驗完就是「完成」。
#    `demo_torrent()` 用的是 `scripts/experiments/lib.py` 的 `make_torrent`，pieces 是真的 SHA-1。
python - <<'EOF'
import subprocess, sys, tempfile
from pathlib import Path
sys.path[:0] = ["scripts", "scripts/experiments"]
from fake_setup_server import POLL_FILES, POLL_RELEASE
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / POLL_RELEASE
    for rel, size in POLL_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(bytes((i % 251) for i in range(size)))
    subprocess.run(["docker", "exec", "berth-poll-demo", "mkdir", "-p", "/downloads/complete/anime"], check=True)
    subprocess.run(["docker", "cp", str(root), "berth-poll-demo:/downloads/complete/anime/"], check=True)
EOF

# 3. 起 Berth，開 http://127.0.0.1:8484/jobs（skipper / harbour），在 Media 詳情頁
#    用關鍵字 `Berth.Poller.Demo` 搜、選 Anime、送單。那一列會自己走完。
BERTH_QBITTORRENT_URL=http://127.0.0.1:8080   uv run --env-file .env python scripts/fake_setup_server.py --scenario poll
```

這個情境的三層路徑用的是**容器裡的**那一組（`/downloads/complete`），因為真的 qBittorrent 只用得了
它自己看得到的路徑。**Windows 上的副作用**：`Path("/downloads")` 在那裡是「目前磁碟機的根目錄底下」，
所以建 Route 那一步會在 `C:\downloads` 留下幾個空目錄——跑完刪掉它，否則
`tests/integration/test_setup_routes.py` 裡「Berth 看不到那條 save path」的兩條會誤判成通過。

這些環境變數**只給開發時的演練與 `scripts/experiments/*` 用**。Berth 自己不讀它們：產品的
唯一來源是 `settings.services.tmdb.api_key` 與 `settings.services.indexer`，由精靈寫進資料庫。

Fake 是**有狀態**的，每個情境只有一份，所以頁 1 與頁 3 真的會把那台假 Jellyfin 一步一步改掉，
重按也真的會標成「已經是這樣」。

每次啟動都用一個新的暫存 `CONFIG_ROOT`，所以永遠是乾淨環境；`--config-root` 可指定成固定目錄
以便跨次保留進度。精靈頁 3（媒體庫路徑）會**真的**建目錄、寫探測檔並呼叫 `link()`，所以三層
路徑（`settings.paths`）由這支腳本指到該次的暫存 `DATA_ROOT` 底下，不會碰到容器裡的 `/data`。

`healthy` / `degraded` / `global-path` 這幾個情境在啟動時就真的跑過一輪 `build_routes` 與健康檢查，
所以畫面上的 inode、可用空間與版本號都是那一輪量到的值，不是寫死的假資料。
