# 實驗腳本

M0 票 04（brief §20.6）的實驗。**指令在根目錄的 [README](../../README.md#實驗腳本)**（那份是本專案
指令的單一來源）；這裡寫的是每個腳本在回答什麼、為什麼這樣寫、有哪些坑。

結論在 [`docs/research/m0-experiments.md`](../../docs/research/m0-experiments.md)，摘要進
brief §20.6 / §20.7。原始 JSON 落在 `.local/experiments/results/`（不進版控），stdout 是同一份
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
