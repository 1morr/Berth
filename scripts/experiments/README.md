# 實驗腳本

M0 票 04、M1 票 01（brief §20.6）、M1 票 14d、M1.5 票 01 與 04 的實驗。**指令在根目錄的 [README](../../README.md#實驗腳本)**（那份是本專案
指令的單一來源）；這裡寫的是每個腳本在回答什麼、為什麼這樣寫、有哪些坑。

結論在 [`docs/research/m0-experiments.md`](../../docs/research/m0-experiments.md)、
[`docs/research/anime-episode-source.md`](../../docs/research/anime-episode-source.md) 與
[`docs/research/profile-effect.md`](../../docs/research/profile-effect.md) 與
[`docs/research/library-browsing.md`](../../docs/research/library-browsing.md)，摘要進
brief §10 / §19 / §20.3 / §20.4 / §20.6 / §20.7 / §20.8。原始 JSON 落在 `.local/experiments/results/`（不進版控），
stdout 是同一份東西的人類版（`absolute_rule_cost.py` 只印 stdout）。

腳本只用 Python 標準庫，不 import `berth`，也不需要專案的虛擬環境 —— 這樣才能原封不動搬到 NAS
或別人的 Linux 宿主上跑。**例外是 `absolute_rule_cost.py` 與 `jellyfin_images.py`**：它們量的就是 Berth
自己的解析器與圖片代理，搬到別台機器上跑沒有意義，所以 import `berth`、要用 `uv run` 跑。唯一的宿主相依是 `make_media.py` 會呼叫 `docker`（借 Jellyfin image 的
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
| `absolute_rule_cost.py` | M1 票 14d：「集號 ≤ 第一季集數就送審核」擋下的是對的多還是錯的多，以及「標題有認不出的多餘字」分不分得開。正解借 `anime_episode_source.py` 的校準，Berth 的讀法是把每筆 Mikan 發佈丟進 `plan`。只印 stdout |
| `jellyfin_permissions.py` | M1.5 票 01：伺服器 API key 代讀某位使用者時，Jellyfin 哪些端點套用他的媒體庫權限（研究 §2 的表逐列，API key 與使用者 token 各一次）；`/Items` 的過濾、排序、分頁是不是真的有作用；由 TMDB id 找作品；Series / Season 標記遞迴；停用帳號。自己起停一次性容器，`--record` 重錄 `tests/fixtures/http/jellyfin/` 的權限 fixture，也錄媒體庫牆、排序篩選與繼續觀看 / 下一集（票 03–07）的回應 |
| `jellyfin_images.py` | M1.5 票 04：Jellyfin 的圖經 Berth 代理要不要在 Berth 端另存一份。縮圖參數與格式協商、Jellyfin 自己的縮圖快取（冷熱延遲）、6 條並行下直連與經過 Berth（`berth serve` 子程序）各多少毫秒。自己起停一次性容器 |
| `lib.py` | 共用的 HTTP、輪詢、bencode、報告輸出 |

## 幾個不明顯的地方

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
