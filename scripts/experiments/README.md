# 實驗腳本

M0 票 04、M1 票 01（brief §20.6）、M1 票 14d、M1.5 票 01 與 04、M2 票 09c 與 11、M3 票 03 的實驗。**指令在根目錄的 [README](../../README.md#實驗腳本)**（那份是本專案
指令的單一來源）；這裡寫的是每個腳本在回答什麼、為什麼這樣寫、有哪些坑。

結論在 [`docs/research/m0-experiments.md`](../../docs/research/m0-experiments.md)、
[`docs/research/anime-episode-source.md`](../../docs/research/anime-episode-source.md) 與
[`docs/research/profile-effect.md`](../../docs/research/profile-effect.md) 與
[`docs/research/library-browsing.md`](../../docs/research/library-browsing.md) 與
[`docs/research/large-library.md`](../../docs/research/large-library.md)，摘要進
brief §10 / §19 / §20.3 / §20.4 / §20.6 / §20.7 / §20.8。原始 JSON 落在 `.local/experiments/results/`（不進版控），
stdout 是同一份東西的人類版（`absolute_rule_cost.py` 只印 stdout）。

腳本只用 Python 標準庫，不 import `berth`，也不需要專案的虛擬環境 —— 這樣才能原封不動搬到 NAS
或別人的 Linux 宿主上跑。**例外是 `absolute_rule_cost.py` 與 `jellyfin_images.py`**：它們量的就是 Berth
自己的解析器與圖片代理，搬到別台機器上跑沒有意義，所以 import `berth`、要用 `uv run` 跑（`large_library_berth.py`
也 import `berth`，但它跑在 Berth 自己 build 出來的 image 裡，宿主不需要虛擬環境）。唯一的宿主相依是 `make_media.py` 會呼叫 `docker`（借 Jellyfin image 的
ffmpeg 產種子檔），那只影響「造測試素材」這一步，不影響 `hardlink.sh` 的可攜性。

## 每個檔案在做什麼

| 檔案 | 回答的問題 |
| --- | --- |
| `compose.yml` | 實驗環境本身：Jellyfin 10.10 + 10.11、qBittorrent 4.4 + 5.x、Prowlarr。port 與子網都跟 `deploy/` 錯開，兩套可以並存 |
| `make_media.py` | 造 dummy 媒體樹。每個檔案都是同一段 1 秒 MKV 的複本 —— Jellyfin 會對媒體檔跑 ffprobe，零位元組的假檔測不出命名解析 |
| `prepare_qbittorrent.py` | 在容器啟動前寫好 `qBittorrent.conf`，讓腳本免密進得去 API。網段從 `compose.yml` 讀，不另外寫死一份 |
| `jellyfin_naming.py` | 初始精靈 → 建媒體庫 → 掃描 → 查解析結果 → 裝 MergeVersions → 跑合併任務 → 再查一次 |
| `qbittorrent_matrix.py` | `paused`/`stopped`、`contentLayout`、`torrents/files` 的相對基準、category 鍵名、Host 檢查、CSRF |
| `prowlarr_host_config.py` | `config/host` 的欄位名與設 Forms 帳密的完整往返 |
| `hardlink.sh` | 在單一掛載根底下真的做一次 `link()`（brief §4.4）。成功回 0，`EXDEV` 或 inode 不符回 1 |
| `anime_episode_source.py` | M1 票 01：字幕組編號換算到 TMDB 季集 / TVDB aired / TVDB absolute 的失敗率 |
| `anime_sample.json` | 上一支的樣本：10 部動漫、挑選理由、Mikan 的番組 id |
| `qbittorrent_poller.py` | M1 票 10：`sync/maindata` 的 rid 增量形狀、`torrents/files` 的相對基準（多檔）、三種處境下的 `state` / `progress` / `completion_on`，以及**連續登入失敗之後的 403 與帳密錯差在哪裡**。最後一項會封住來源 IP，所以它一定跑在最後 |
| `qbittorrent_recovery.py` | M2 票 09c：`torrents/recheck` 與 `torrents/start`（4.x 叫 `resume`）兩版回什麼、刪資料再重啟之後 torrent 是不是 `missingFiles`、救回來時 recheck 與 start 誰先誰後有沒有差。會 `docker restart` 那個容器，並重錄 `tests/fixtures/http/qbittorrent/` 的五份 fixture |
| `qbittorrent_stopped_recheck.py` | M3 票 03：**停住的** torrent（使用者或分享比率停的）送 recheck、recheck → start、start → recheck 之後的 state 序列，完整的與缺一個檔的各一組，另加做種中缺檔的兩種順序。自己起停一次性容器；上一支的四包都是 `missingFiles`，量不到這一種 |
| `absolute_rule_cost.py` | M1 票 14d：「集號 ≤ 第一季集數就送審核」擋下的是對的多還是錯的多，以及「標題有認不出的多餘字」分不分得開。正解借 `anime_episode_source.py` 的校準，Berth 的讀法是把每筆 Mikan 發佈丟進 `plan`。只印 stdout |
| `jellyfin_permissions.py` | M1.5 票 01：伺服器 API key 代讀某位使用者時，Jellyfin 哪些端點套用他的媒體庫權限（研究 §2 的表逐列，API key 與使用者 token 各一次）；`/Items` 的過濾、排序、分頁是不是真的有作用；由 TMDB id 找作品；Series / Season 標記遞迴；停用帳號。自己起停一次性容器，`--record` 重錄 `tests/fixtures/http/jellyfin/` 的權限 fixture，也錄媒體庫牆、排序篩選與繼續觀看 / 下一集（票 03–07）、Media 詳情觀看區（由 TMDB id 找作品、`/Items/{id}`、這部劇的下一集，票 08）、牆上按名字找（`searchTerm`，M2 票 14）的回應 |
| `jellyfin_images.py` | M1.5 票 04：Jellyfin 的圖經 Berth 代理要不要在 Berth 端另存一份。縮圖參數與格式協商、Jellyfin 自己的縮圖快取（冷熱延遲）、6 條並行下直連與經過 Berth（`berth serve` 子程序）各多少毫秒。自己起停一次性容器 |
| `large_library.py` | M2 票 11：1,000 部 × 12 集的媒體庫上，`GET /inventory/{id}` 的 p95 與對帳一輪各多久（plan §11.3 決定 2 的門檻），加上票上五件（整份清單、不帶 `parentId` 的 TMDB 反查、整份 `MediaSources`、篩選後的牆帶觀看狀態、被刪掉的帳號）。宿主那一半：起停 network、三個 volume、Jellyfin、qBittorrent 與 Berth 的 image |
| `large_library_berth.py` | 上一支在 Berth 的 image 裡跑的那一半：`tree` 造媒體樹，`measure` 灌觀看紀錄、1,000 個 torrent、Berth 的資料庫之後分段量 |
| `air_date_lag.py` | M3 票 14：字幕組發佈比 TMDB 播出日晚多久、播出日比對的規則二在真實 feed 上擋下幾筆，定 `BEHIND_LATEST`。import `berth`（直接呼叫 `parser.check_airing`），要用 `uv run`；會連網，TMDB 憑證讀 `TMDB_API_KEY`；結果記在 `.scratch/m3/issues/14-air-date-check.md` 的 Comments |
| `rss_auto_bind.py` | M3 票 09：RSS Series 自動綁定的規則對真的 Mikan 與 TMDB 認得出幾部、錯幾部。import `berth`（量的就是它的判定），要用 `uv run`；會連網，TMDB 憑證讀 `TMDB_API_KEY`；`docs/research/rss-sources.md` §2.8 |
| `rss_sources.py` | M3 票 07：Mikan / Nyaa / acg.rip 三個索引站的 RSS 欄位事實——feedparser 解析結果、bencode 核對 info hash、guid / hash / 大小 / 日期一致性、pubDate 時區偏移、合集標題掃描。不用容器、不連網，只讀 `tests/fixtures/http/`；`docs/research/rss-sources.md` §7.4 |
| `runtime_gap.py` | M3 票 15：片長驗證的門檻（`RUNTIME_SLACK`、`RUNTIME_RATIO`）：真的 mediainfo 片長（AnimeTosho）對語料的 TMDB 快照，量對得上的正片比例與秒數差落在哪；兩集合併檔以相鄰兩集的真實片長相加模擬，NCOP / SP 沒有量到。不用容器、不需要憑證，只讀本地 `tests/fixtures/`，不下載任何影片內容；結果記在 `.scratch/m3/issues/15-runtime-check.md` 的 Comments |
| `lib.py` | 共用的 HTTP、輪詢、bencode、報告輸出 |

## 幾個不明顯的地方

- **`compose.yml` 的子網 `172.29.0.0/16` 可能與這台機器上別的 docker network 撞**（`Pool overlaps`，
  2026-09-23 撞過）。不要去刪別人的網路：複製一份 compose 改子網，`prepare_qbittorrent.py --compose <那一份>`
  讓白名單跟著換，再以 `EXP_ROOT=<repo>/.local/experiments docker compose -f <那一份> up -d` 起來
  （複製出去之後相對路徑的預設值就不對了）。
- **媒體樹裡有兩組作品是故意的。** `Berth Test Show (2020) [tmdbid-1399]` 會被 TMDB 認出來，標題
  整個被遠端覆寫；`Qwxzyv Berth Probe (2099)` 對不上任何 provider，名稱完全由 Jellyfin 自己的檔名
  解析器決定。方括號 tag 有沒有滲進劇名或集名，只有在後者看得出來。
- **`jellyfin_naming.py` 不能對跑過的實例重跑。** Jellyfin 把掃描結果留在自己的 DB，刪掉媒體庫再建
  也帶得回來；插件裝過就在了，量不到「未裝插件」的基準。要重跑先砍掉 `/config`，指令見根 README。
- **`qbittorrent_matrix.py` 與 `prowlarr_host_config.py` 可以直接重跑**，它們會先清掉上一輪的
  torrent 並把 `web_ui_domain_list` 還原成 `*`。前者還會逐個試 Host 標頭找出進得去的那一個，
  所以上一輪中途壞掉也救得回來。
- **torrent 是腳本現造的**（`lib.py` 的 `make_torrent`），磁碟上沒有對應資料，加進 qBittorrent 後
  永遠不會真的下載。
- **深連結那一項是手動的**：`#!/details?id=…` 是前端路由，伺服器端測不到。`jellyfin_naming.py`
  會把兩種候選網址與可用的 item id 印出來並寫進報告的 `deep_link_candidates`，人開瀏覽器登入後
  貼上去看。實測結果記在 research 文件的 §1.8。
- **`anime_episode_source.py` 不需要容器，但需要一把 TMDB 憑證。** 跑之前設好環境變數
  `TMDB_API_KEY`（v3 API key 或 v4 read access token 都可以，themoviedb.org 的「設定 → API」
  申請）——Berth 不內建任何 provider 的 key，腳本也不留一把（票 02b）。TVDB 資料走 Sonarr 的
  Skyhook 代理，字幕組的實際釋出來自 Mikan 的 RSS。**Skyhook 只能這樣用在實驗裡**——它是 Sonarr 自營
  的封閉服務，不是給第三方的公開 API，理由寫在 research 文件的 §5。
- **它會把抓到的東西快取在 `.local/experiments/cache/`。** Mikan 的頁面動輒 500 KB 以上、
  連線常常中途被掐掉，第一次跑要十來分鐘；重跑分析（例如換 `--gap-days`）則是秒級。要重新
  抓一次就砍掉那個目錄。
- **`absolute_rule_cost.py` 直接 import 同目錄的 `anime_episode_source.py`**（`uv run` 跑腳本時，腳本所在的目錄就在
  `sys.path` 上），吃的是同一份快取，所以也要 `TMDB_API_KEY`（`uv run --env-file .env`）。為了它，後者的 `Trial` 多帶
  一個 Mikan 原始標題；那一支自己的數字不受影響。它的近似——Mikan 只有標題、沒有檔案清單，每筆當成以標題為檔名的
  單檔 torrent，合集逐集重問 `map_episode`——與限制寫在研究文件 `profile-effect.md` §6.1.1。
- **判斷「字幕組寫的 12 是哪一集」靠的是發佈時間，不是編號規則。** 為什麼要這樣做、三道校準
  閘在擋什麼，見 research 文件的 §4.1。動過 `calibrate_offset` 就要重跑 `--self-test`。
- **`jellyfin_permissions.py` 不用 compose，自己 `docker run` 一台再刪掉**（image 從 `deploy/docker-compose.yml`
  讀，跟著套件釘的版本走）。`--record` 只在伺服器是 12.1.0 時錄：fixture README 的規則是新版本開新檔名，
  版本變了就停下來由人決定，不悄悄蓋掉舊的證據。`--only a.json,b.json` 只寫這幾個檔名：加錄新的 fixture 時，
  既有那一組的使用者 id、`ServerId` 與日期不會跟著換掉（item id 由路徑決定，兩輪相同）。工作目錄預設是系統暫存目錄下的新目錄，跑完連同容器與匿名 volume 一起刪；
  `--workdir` 指定的目錄必須是空的，因為結束時整個刪掉。`--keep` 留著除錯；下次跑時腳本開頭會自己砍掉同名容器，
  但那個工作目錄要自己清。它 import 同目錄的 `jellyfin_naming.py`
  借初始精靈與等掃描，那一支的 `/Startup/*` 在 12.x 標 deprecated 但還能用。
- **它的媒體庫把網路 fetcher 全關了，metadata 只來自 NFO**：類型、年份、評分、分級、片長刻意排成彼此不同的順序，
  「伺服器真的有過濾 / 排序」才判得出來，結果也不隨 TMDB 變動。`TypeOptions` 列出型別但 fetcher 清單留空才是
  「全關」（實測：集沒有截圖、劇沒有背景圖與簡介），整個留空是「用預設」（`jellyfin_naming.py` 就是那樣）。
  圖只來自資料夾裡的 jpg：每部都有 `poster.jpg`，幾部另有 `landscape.jpg`（Jellyfin 讀成 Thumb）與 `fanart.jpg`
  （Backdrop），繼續觀看與下一集的橫卡取圖順序才錄得到（`Title.art`，M1.5 票 07）。
- **`/System/Info/Public` 回 200 不代表 Jellyfin 載入完了**：這時精靈的端點是 503，所以它先等
  `/Startup/Configuration` 回 200。每種身分（管理員、API key、受限使用者）用自己的 `DeviceId`：
  Jellyfin 以裝置管理 session，這是預防同一個裝置重新登入時作廢別的身分的 token（沒有實測過會不會）。
- **`jellyfin_images.py` 的 Berth 是另一個程序**（`python -m berth.cli serve`）：量測用 6 條執行緒並行打圖，與伺服器同一個
  程序的話兩邊搶同一把 GIL，量到的是 Python 而不是代理。資料庫直接寫好「精靈跑完、Jellyfin 位址」兩格，登入走真的
  `POST /api/auth/login`（對一次性 Jellyfin 的管理員）。海報是 ffmpeg `testsrc2` 加雜訊的 1000×1500 JPEG：純色圖幾 KB，
  縮圖的大小與時間都會失真。
- **觀看紀錄要在縮權之前寫**：縮權之後 API key 也寫不進沒權限的媒體庫（那正是要量的一列）。
- **`large_library.py` 的 Berth 一定要跑在容器裡**：帳本的路徑要與 Jellyfin 回報的 `Path` 一字不差（brief §20.1），
  Windows 宿主上的 Berth 拿到的是 `C:\...`，反查與對帳會整份對不上。所以它 build `deploy/Dockerfile` 的 `backend`
  那一層、把 `/data` volume 同時掛給 Jellyfin（唯讀）、qBittorrent 與 Berth，與正式部署同形。
- **媒體樹不寫 NFO**：TMDB id 只從資料夾名的 `[tmdbid-N]` 來（網路 fetcher 全關），與 Berth 入庫的樣子相同；寫了
  `tvshow.nfo` 的話它會被對帳當成媒體庫裡 Berth 不認得的檔案。每一集在 complete 裡各自一個 inode，媒體庫那一份是它的硬鏈接。
- **`measure` 冪等**：`viewer` / `gone` 兩個帳號每次先刪再建，重複的 torrent 回 409 照樣算。所以 `--keep` 之後可以
  `--reuse` 只重 build image 再量——改 Berth 的程式碼之後不必再等 6 分鐘的掃描。每一段量完就寫一次報告，只跑一部分時
  報告檔名帶段名（`large-library-inventory.json`）。
- **2026-09-23 這台機器（i9-13900HX）在長時間滿載下，Python 與 Jellyfin 的 .NET 都會隨機 segfault**（VM 核心 log
  有 `segfault at 0 ip 0`、崩在 `libpython` 與 `libc`，沒有 OOM）。所以容器裡的 Python 帶 `-X faulthandler`，
  Jellyfin 被 s6 無聲拉起來的次數由宿主數 `docker logs` 裡的 `Startup complete` 寫進報告，斷線的請求重打一次、不計入延遲。
  在別台機器上重量時先看 `jellyfin_startups` 是不是 1、`dropped_connections` 是不是空的。
- **`qbittorrent_stopped_recheck.py` 的 start 一定要在校驗還沒做完時送到**：5.x 的問題只發生在這個窗口裡，
  校驗一瞬間就做完的話 start 會落在「已經又停住」之後、照常生效，量出來是一片正常。所以每包預設 8 GiB
  （`--size-gib`），用 `truncate` 造稀疏的全零檔：宿主不寫任何資料、piece 雜湊只算一次，而 qBittorrent 照樣
  要讀完、雜湊完（這台機器上約 17 秒）。報告裡的 `first_check_seconds` 是加入時那一次校驗的長度，看它是不是
  遠大於 `requests_seconds`（兩支請求之間隔多久）。
- **Host 標頭帶的是容器裡的 port（`localhost:8080`），不是宿主發佈的 18093**：qBittorrent 比對 Host 的 port 與它
  自己聽的那一個，對不上時 log 是 `Invalid Host header, port mismatch`、回應是 401（不是 403）。
- **`runtime_gap.py` 對 AnimeTosho 的每個檔案頁面要自己節流**：連續無延遲地打 `/file/<id>` 會被 AT 的限速器
  擋下 HTTP 429（回應是 nginx 的預設錯誤頁，長得完全不像 mediainfo，第一版沒特判過就整份快取下來，
  量出 0 筆資料才發現）。腳本每次活的請求前都會 `_pace()`（最少間隔 0.5 秒），429 另外照 `Retry-After`
  或退避重試、不快取；要重新驗證這段邏輯，刪 `.local/experiments/cache/runtime_gap/` 裡對應的 `.bin` 重跑即可。
- **AT 對批次（多檔）種子常回 `status: "skipped"`，哪怕種子本身沒事**：不是只有失效種子才這樣，這次量到
  的 fixture 本身種子有 6+ 個屬於這種情況，腳本因此改抓同一部作品、同一段集數的另一個發佈（`is_alt=True`）
  ——集數對得上、正片內容一樣，但不是 fixture JSON 字面上那個種子／字幕組／編碼。
  fixtures 沒有的一定得靠這招時要留意這一點。
- **TMDB 有些長壽番的季集號不是每季從 1 開始**：One Piece（`tv-37854`）season 22 的 67 集直接沿用全劇累計
  的絕對集號（`episode_number` 從 1089 起），season 內找不到 episode 1；「這一季的第一集」要用
  `season_first_episode()`（該季 `episode_number` 的最小值）動態算，不能寫死 1，否則 runtime 查詢回 `None`。
- **Frieren 的 TMDB season 0「Specials」跟字幕組批次裡的 S00 特典是兩批完全不同的內容**：字幕組把 BD 特典
  編成 S00E01-11（每集長度接近正片），TMDB 的 season 0 卻是另一組 26 支 1-2 分鐘的短篇「OO 魔法」，兩邊
  集號沒有對應關係；就算真的量得到特典時長也不能拿 TMDB season 0 直接比，腳本刻意把 season-0/SP 資料整段
  排除在「正確對應正片」的分析之外，不是「拿不到」而是「這樣比較沒有意義」。
- **AnimeTosho 官方公告 2026 年 10 月初到中旬停止服務**：`runtime_gap.py` 抓到的原始資料快取在
  `.local/experiments/cache/runtime_gap/`，關站後還能對著快取重跑分析，但要擴大樣本（目前只解到 8 部
  作品，`SKIPPED_SHOWS` 裡還有幾組沒 drill down 完）要趁它還在的時候做。
