# 實驗腳本

M0 票 04 與 M1 票 01（brief §20.6）的實驗。**指令在根目錄的 [README](../../README.md#實驗腳本)**（那份是本專案
指令的單一來源）；這裡寫的是每個腳本在回答什麼、為什麼這樣寫、有哪些坑。

結論在 [`docs/research/m0-experiments.md`](../../docs/research/m0-experiments.md) 與
[`docs/research/anime-episode-source.md`](../../docs/research/anime-episode-source.md)，摘要進
brief §10 / §20.3 / §20.6 / §20.7。原始 JSON 落在 `.local/experiments/results/`（不進版控），stdout 是同一份
東西的人類版。

腳本只用 Python 標準庫，不 import `berth`，也不需要專案的虛擬環境 —— 這樣才能原封不動搬到 NAS
或別人的 Linux 宿主上跑。唯一的宿主相依是 `make_media.py` 會呼叫 `docker`（借 Jellyfin image 的
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
- **判斷「字幕組寫的 12 是哪一集」靠的是發佈時間，不是編號規則。** 為什麼要這樣做、三道校準
  閘在擋什麼，見 research 文件的 §4.1。動過 `calibrate_offset` 就要重跑 `--self-test`。
