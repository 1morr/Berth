# 開發指令：實驗腳本

`scripts/experiments/` 的實驗腳本。其他開發指令見[主檔](../development.md)的索引。

### 實驗腳本

`scripts/experiments/` 是對真實外部服務做的驗證（Jellyfin 命名、qBittorrent 版本差異、
Prowlarr 設定 API、硬鏈接），全部可重跑。每個腳本在回答什麼、有哪些坑，見
[`scripts/experiments/README.md`](../../scripts/experiments/README.md)；結果寫在
[`docs/research/m0-experiments.md`](../research/m0-experiments.md)。

媒體樹與 qBittorrent 設定檔都要在容器啟動**之前**備好：

```bash
python scripts/experiments/make_media.py
python scripts/experiments/prepare_qbittorrent.py     .local/experiments/qbittorrent-44 .local/experiments/qbittorrent-52
docker compose -f scripts/experiments/compose.yml up -d      # port 與 deploy/ 錯開
```

跑實驗（各自獨立，順序無所謂）：

```bash
python scripts/experiments/jellyfin_naming.py --base-url http://localhost:18096 --label 10.10.7
python scripts/experiments/jellyfin_naming.py --base-url http://localhost:18196 --label 10.11.11
python scripts/experiments/qbittorrent_matrix.py --base-url http://localhost:18080 --label 4.4.5
python scripts/experiments/qbittorrent_matrix.py --base-url http://localhost:18081 --label 5.2.3

# 票 10 的 poller 端點（`sync/maindata` 的增量、`torrents/files`、IP 封鎖的 403）。
# 最後一項會封住來源 IP，所以錄完那一輪要重建容器才能再跑一次。
python scripts/experiments/qbittorrent_poller.py --base-url http://localhost:18080 --label 4.4.5 --container berth-exp-qbittorrent-44
python scripts/experiments/qbittorrent_poller.py --base-url http://localhost:18081 --label 5.2.3 --container berth-exp-qbittorrent-52

# M2 票 09c 的 recheck / start（`missing_files` 與 `client_error` 的按鈕）。會重啟那個容器。
python scripts/experiments/qbittorrent_recovery.py --base-url http://localhost:18080 --label 4.4.5 --container berth-exp-qbittorrent-44
python scripts/experiments/qbittorrent_recovery.py --base-url http://localhost:18081 --label 5.2.3 --container berth-exp-qbittorrent-52
python scripts/experiments/prowlarr_host_config.py     --base-url http://localhost:19696 --config .local/experiments/prowlarr
```

Jellyfin 的權限與瀏覽 API（M1.5 票 01）自己起停一台一次性的 Jellyfin（image 取 `deploy/` 釘的那一個，
不需要上面的 compose），跑完連容器與工作目錄一起刪。結果見
[`docs/research/library-browsing.md`](../research/library-browsing.md) §2、§3.1、§5、§10、§11：

```bash
python scripts/experiments/jellyfin_permissions.py            # 只量，報告寫到 .local/experiments/results/
python scripts/experiments/jellyfin_permissions.py --record   # 另外重錄 tests/fixtures/http/jellyfin/ 的權限 fixture
python scripts/experiments/jellyfin_permissions.py --record --only items.tv.series.page.json   # 只加錄這幾個，其餘不動
```

Jellyfin 能不能只刷新一個媒體庫、對空的媒體庫有沒有效（M4 票 62）：同樣自己起停一次性 Jellyfin，約 8 分鐘。結果見
brief §20.1：

```bash
python scripts/experiments/jellyfin_scan_scope.py   # 報告寫到 .local/experiments/results/jellyfin-scan-scope.json
```

Jellyfin 的圖經 Berth 代理要不要另存一份（M1.5 票 04）：同樣自己起停一次性 Jellyfin，另外起一個 `berth serve`
量經過代理的延遲，所以要用 `uv run`。結果見 [`docs/research/library-browsing.md`](../research/library-browsing.md) §6.1：

```bash
uv run python scripts/experiments/jellyfin_images.py   # 報告寫到 .local/experiments/results/jellyfin-images.json
```

RSS Series 自動綁定的規則門檻（M3 票 09）：對票 07 錄下的 Mikan 聚合 feed，真的抓 Mikan 單集頁與番組頁、真的打
TMDB，走 Berth 自己的判定、只印不綁。憑證讀環境變數，資料庫是暫時目錄裡的新的一份。結果見
[`docs/research/rss-sources.md`](../research/rss-sources.md) §2.8：

```bash
uv run --env-file .env python scripts/experiments/rss_auto_bind.py   # 要 .env 裡的 TMDB_API_KEY；會連 Mikan 與 TMDB
uv run --env-file .env python scripts/experiments/air_date_lag.py    # 同上；Windows 主控台加 PYTHONIOENCODING=utf-8
```

第一批「證據夠強」的規則（M4 票 11）：語料那一段離線；`--online` 另跑 split-cour 模擬與上面那一套真的 RSS fixture
（重用 `air_date_lag.py` 認作品的那一段，所以要同一把憑證）。結果記在 `.scratch/m4/issues/11-first-batch-skip-when-sure.md`：

```bash
uv run python scripts/experiments/first_batch_rule.py                                  # 只跑語料，不連網
uv run --env-file .env python scripts/experiments/first_batch_rule.py --online          # Windows 主控台加 PYTHONIOENCODING=utf-8
```

前端 e2e `rss-subscribe` 的第一輪預覽為什麼慢（M4 票 13b）：起一台 `rss` 情境的演練 server，打那條 spec 同一串 API、
逐步計時；不連網。結果記在 `.scratch/m4/issues/13b-rss-subscribe-e2e-preview.md`。預覽裡的「重複」為什麼時有時無
（M4 票 121b）用 `--watch`：建好 feed 之後反覆讀預覽與 `/jobs`，各狀態筆數、重複的理由或入庫集數一變就印一行，
結果記在 `.scratch/m4/issues/121b-rss-subscribe-duplicate-count.md`：

```bash
uv run python scripts/experiments/rss_subscribe_timing.py                 # 訂閱 Mikan 之後馬上建 acg.rip 搜尋 feed
uv run python scripts/experiments/rss_subscribe_timing.py --settle 30     # 先等補舊集跑完 30 秒再建
uv run python scripts/experiments/rss_subscribe_timing.py --profile       # 同一個行程起 server，cProfile 包住預覽
uv run python scripts/experiments/rss_subscribe_timing.py --watch 15      # 之後 15 秒看預覽跟著補舊集的入庫變
```

每日巡檢一輪佔用事件迴圈多久（M4 票 129；票 130 加上帳本、作品快照與 Feed，量 RSS 那三項）：暫時的資料庫上灌
一份資料、跑 `sweep_once` 三輪，另一個 coroutine 每 1 ms 醒一次記下晚了多少。不連網；結果記在
`.scratch/m4/issues/129-daily-patrol.md` 與 `130-rss-patrol.md`。第 1 輪多出的 ~400 ms 是行程裡第一次解析發佈名：

```bash
uv run python scripts/experiments/sweep_loop_lag.py                                  # 400 個 Series × 12 筆 Job
uv run python scripts/experiments/sweep_loop_lag.py --series 2000 --issues 1000      # 放大五倍
```

搜尋季的記號（M4 票 84）：對一台有公開站的 Prowlarr 實搜 `Season N` 與 `SNN` 各一組，逐站數筆數與名字對得上的筆數。
不用容器；查詢間隔 3.5 秒、共 14 次，別連跑：

```bash
python scripts/experiments/season_token_compare.py http://127.0.0.1:19784 <Prowlarr API key>   # 或設 PROWLARR_URL / PROWLARR_API_KEY；Windows 主控台加 PYTHONIOENCODING=utf-8
```

1,000 部的媒體庫上量 Berth（M2 票 11，plan §11.3 決定 2 的門檻）：自己 build Berth 的 image（只有 backend 那一層）、
起一次性的 Jellyfin 與 qBittorrent、造 1,000 部 × 12 集的媒體樹（掃描約 6 分鐘），量完連容器、volume、network、image
一起刪。宿主只要 Python 標準庫與 docker；量測本身在 Berth 的 image 裡跑。結果見
[`docs/research/large-library.md`](../research/large-library.md)：

```bash
python scripts/experiments/large_library.py                  # 報告寫到 .local/experiments/results/large-library*.json
python scripts/experiments/large_library.py --series 30      # 先小規模跑通
python scripts/experiments/large_library.py --keep           # 留著環境；改了 Berth 之後用下一行只重 build 與重量
python scripts/experiments/large_library.py --reuse --keep --stages inventory   # 段落：jellyfin,inventory,reconcile
```

停住的 torrent 送 recheck 與重新開始之後狀態怎麼走（M3 票 03，brief §20.2）：自己起停一次性的 qBittorrent
（network、兩個 volume、容器，前綴 `berth-exp-recheck`，只發佈在 `127.0.0.1:18093`），資料是稀疏的全零檔，
一個版本約 5 分鐘，跑完印出 `docker ps -a` / `docker volume ls` 的過濾結果：

```bash
python scripts/experiments/qbittorrent_stopped_recheck.py      # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-stopped-recheck-<版本>.json
python scripts/experiments/qbittorrent_stopped_recheck.py --image lscr.io/linuxserver/qbittorrent:latest   # compose 預設的那一個
python scripts/experiments/qbittorrent_stopped_recheck.py --image lscr.io/linuxserver/qbittorrent:4.4.5    # 對照組
python scripts/experiments/qbittorrent_stopped_recheck.py --only stopped_recheck_start --keep            # 只跑一個情境，留著容器
```

qBittorrent 看不看得到 Berth 寫進分類路徑的檔：探針 torrent 在 4.4.5 與 5.2.3 上怎麼校驗（M4 票 19，brief §20.2）：
自己起停一次性的 qBittorrent（前綴 `berth-exp-visibility`，只發佈在 `127.0.0.1:18095`），一個版本不到一分鐘：

```bash
python scripts/experiments/qbittorrent_visibility_probe.py     # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-visibility-<版本>.json
python scripts/experiments/qbittorrent_visibility_probe.py --image lscr.io/linuxserver/qbittorrent:4.4.5   # 支援下限
```

精靈頁 2 的探針「看得到但校驗不完」：看得到的那一台停在 50%、不觸發「完成時執行外部程式」（M4 票 46，brief §20.2）。
用的是 Berth 自己的 `probe_torrent(unfinished=True)`，沿用上一支的容器名，只發佈在 `127.0.0.1:18096`：

```bash
uv run python scripts/experiments/qbittorrent_unfinished_probe.py     # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-unfinished-probe-<版本>.json
uv run python scripts/experiments/qbittorrent_unfinished_probe.py --image lscr.io/linuxserver/qbittorrent:4.4.5
```

分類自己的未完成目錄（`createCategory` 的 `downloadPath`）下載中是不是落在那裡、完成後搬到 save path，全域
temp path 開關時誰贏（M4 票 22，brief §20.2）：自己起停一台做種的 5.2.3 與一台受測版本（前綴
`berth-exp-catpath`，只發佈在 `127.0.0.1:18093`、`18094`），一個版本約兩分鐘：

```bash
python scripts/experiments/qbittorrent_category_download_path.py     # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-category-download-path-<版本>.json
python scripts/experiments/qbittorrent_category_download_path.py --image lscr.io/linuxserver/qbittorrent:4.4.5   # 支援下限
```

套件容器撞名、撞 port 時 `docker compose up -d` 怎麼收場，以及 `berth` 的 `host.docker.internal` 解到哪
（M4 票 16，brief §20.14）：以 `deploy/docker-compose.yml` 改出一套隔離的 compose project（`berth-exp-collide`、
子網 `172.26.0.0/16`、容器名前綴 `bexp-`、port 4xxxx），不碰這台機器上正在跑的部署；`berth` 用本地已有的 image，
不 build。約 2 分鐘，結束時全部清掉並印出殘留。換 Docker 或 Compose 版本之後重量：

```bash
python scripts/experiments/compose_collisions.py --berth-image berth:e2e   # 報告寫到 .local/experiments/results/compose-collisions.json
```

選了既有之後，哪一個指令停得掉已經在跑的套件內容器（M4 票 36，brief §20.14）：同樣改出一套隔離的 compose project
（`berth-exp-profiles`、子網 `10.232.0.0/16`、容器名前綴 `bexp-`、port 4xxxx），image 都用本地已有的、不 pull，
依序量拿掉 profile 再 `up -d`、加 `--remove-orphans`、`stop`、再 `up -d`、不帶 profile 的 `down`。約 1 分鐘，結束時全部清掉：

```bash
python scripts/experiments/compose_profile_removal.py --berth-image berth:e2e   # 報告寫到 .local/experiments/results/compose-profile-removal.json
```

既有服務已經把別的資料夾掛在 `/data` 底下（Unraid CA 的 Jellyfin 模板），再照補法多掛一條 `DATA_ROOT:/data` 會怎樣
（M4 票 63，brief §20.14）：兩個臨時資料夾、`alpine:latest`，幾秒，只印 stdout。Git Bash 上要關掉路徑轉換：

```bash
MSYS_NO_PATHCONV=1 sh scripts/experiments/nested_data_mount.sh
```

qBittorrent 的 preseed 腳本內嵌進 compose（頂層 `configs` 的 `content`，加 `mode: 0555`）之後 linuxserver 的 init
認不認、白名單對不對、重啟與重建冪不冪等、qbittorrent 的 profile 關掉時 `up -d` 會不會報錯，另跑不寫 `mode` 的
對照組（M4 票 70，brief §20.18）。內嵌的腳本取自部署檔 `deploy/docker-compose.yml` 的
`configs.qbittorrent-preseed`（票 71 起它就住在那裡）；compose project 與 network 叫 `berth-t70`、容器 `berth-t70-qbittorrent` 與 `berth-t70-idle`（子網
`10.70.0.0/16`，WebUI port 7080），用本地已有的 `qbittorrent:latest`、不 pull。三個變體約 3 分鐘，結束時 `down` 並刪掉工作目錄。
換 Compose、Docker 或 linuxserver 版本之後重量；別的 Compose 版本用官方的獨立二進位，不換掉系統的：

```bash
python scripts/experiments/inline_preseed.py --label desktop     # 報告寫到 .local/experiments/results/inline-preseed-<label>.json
python scripts/experiments/inline_preseed.py --label compose-2.40.3 --compose-bin <docker-compose 執行檔>
python scripts/experiments/inline_preseed.py --label debug --variant mode --keep   # --keep 只能配一個變體：留著容器與目錄
```

搬到 Linux 宿主上跑時保留相對位置（只用標準庫，宿主要有 `python3`）：

```bash
tar cf - scripts/experiments/inline_preseed.py scripts/experiments/lib.py deploy/docker-compose.yml \
  | ssh <host> 'mkdir -p ~/berth-t70 && tar xf - -C ~/berth-t70'
ssh <host> 'cd ~/berth-t70 && python3 scripts/experiments/inline_preseed.py --label vm-rootless'
```

`jellyfin_naming.py` 必須從乾淨的 `/config` 跑（Jellyfin 的 DB 會留住舊掃描結果，插件裝過
就在了，量不到「未裝插件」的基準）：

```bash
docker compose -f scripts/experiments/compose.yml rm -sf jellyfin-1010 jellyfin-1011
rm -rf .local/experiments/jellyfin-1010 .local/experiments/jellyfin-1011
docker compose -f scripts/experiments/compose.yml up -d jellyfin-1010 jellyfin-1011
```

硬鏈接檢查（沒有相依，NAS 上 ssh 進去直接 `sh hardlink.sh /volume1/<share>` 也行）：

```bash
docker run --rm -v /srv/berth/data:/data -v "$PWD/scripts/experiments:/exp:ro"     alpine:3 sh /exp/hardlink.sh /data                        # 應該 PASS
docker run --rm -v /srv/a:/data/torrent -v /srv/b:/data/library     -v "$PWD/scripts/experiments:/exp:ro" alpine:3 sh /exp/hardlink.sh /data   # 應該 EXDEV 並回 1
```

rootless Docker 上容器的 uid 落到宿主是誰、`berth` 容器連得到宿主上的哪些位址（M4 票 42）：在宿主上、Berth 那一套
`up -d` 之後跑，第一個參數是宿主的區網 IP，其餘是要多打的 port（既有服務）；只讀，自己起的兩個暫時 http 服務會收掉：

```bash
sh scripts/experiments/rootless_host_probe.sh 192.168.50.99 18096 18080
```

入庫的那一部片 Jellyfin 認不認得、播不播得到（M4 票 55，Unraid 上 mover 前後各問一次）：在已經跑完精靈的
`berth` 容器裡跑，用 Berth 存的 Jellyfin API key（不印出），只讀。item id 在作品頁「在 Jellyfin 看」的連結裡：

```bash
ssh root@tower 'docker exec -i berth python - <jellyfin item id>' < scripts/experiments/jellyfin_stream_probe.py
```

收工：

```bash
docker compose -f scripts/experiments/compose.yml down -v
```

Windows 的 Git Bash 要在 `docker run` 前加 `MSYS_NO_PATHCONV=1`，否則 `/data` 這種容器內路徑
會被改寫成 `C:\Program Files\Git\data`。

動漫季集來源的量測（不需要任何容器，只打外部 API）。除了 `--self-test` 以外都要一把 TMDB 憑證，
從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 token 都可以，取得步驟見 [README〈What you need〉](../../README.md#what-you-need)）：

```bash
export TMDB_API_KEY=...                                              # Windows PowerShell 是 $env:TMDB_API_KEY
python scripts/experiments/anime_episode_source.py --self-test       # 換算器的手算樣例
python scripts/experiments/anime_episode_source.py                   # 完整量測（門檻 180 天，同 plan §4.4）
python scripts/experiments/anime_episode_source.py --gap-days 60     # 虛擬季門檻的敏感度比較
python scripts/experiments/anime_episode_source.py --discover        # 重新找 Mikan 的番組 id
```

第一次跑要抓好幾百個頁面（Mikan 的頁很大且常斷線），大約十來分鐘；抓過的東西會快取在
`.local/experiments/cache/`，之後重跑分析是秒級。結果見
[`docs/research/anime-episode-source.md`](../research/anime-episode-source.md)。

「集號 ≤ 第一季集數就送審核」這條規則的代價（M1 票 14d）。拿上面 `anime_episode_source.py` 的快取當正解、
丟進 Berth 的解析器，所以要憑證也要 `uv run`（快取被清掉的話會先重抓，約十分鐘）：

```bash
uv run --env-file .env python scripts/experiments/absolute_rule_cost.py    # A / B、收窄規則 R 的放行與漏掉
```

結果見 [`docs/research/profile-effect.md`](../research/profile-effect.md) §6.1.1。

片長驗證的門檻（M3 票 15，比對 mediainfo 量出的片長與 TMDB 該集 `runtime`）：真的 mediainfo 時長對
AnimeTosho 的公開端點查，不需要任何憑證、不連 TMDB（讀本地 `tests/fixtures/tmdb/`）、不下載任何
影片內容。第一次跑要抓不少 AnimeTosho 的頁面，會自動節流；抓過的東西快取在
`.local/experiments/cache/runtime_gap/`，之後重跑是秒級：

```bash
python scripts/experiments/runtime_gap.py                  # Windows 主控台加 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
```

Discord bot 私訊（M4 票 121）對真的 Discord 量。事前使用者要在 Developer Portal 建一個**新的** application、
Bot 頁 Reset Token（intents 都不開），建一個只有自己的測試伺服器，在那個伺服器的隱私設定打開「私人訊息」，並以開發者模式
複製自己的 user ID。token 只放環境變數；`#` 後面的「使用者：」是兩步之間要在 Discord 上做的事。坑見
`scripts/experiments/README.md`，結論在 brief §20.23：

```bash
export DISCORD_BOT_TOKEN=... DISCORD_USER_ID=...
uv run python scripts/experiments/discord_dm.py invite                  # 只私訊的邀請連結（scope=bot、permissions=0）
uv run python scripts/experiments/discord_dm.py send no-guild-fresh     # 還沒邀請：沒有共同伺服器
# 使用者：點邀請連結，把 bot 加進測試伺服器
uv run python scripts/experiments/discord_dm.py baseline                # 純文字、embed、超長、錯 token
uv run python scripts/experiments/discord_dm.py ratelimit               # 連續送到第一個 429 就停
# 使用者：在測試伺服器的隱私設定關掉「私人訊息」
uv run python scripts/experiments/discord_dm.py send dm-closed
# 使用者：打開回來，把 bot 踢出伺服器
uv run python scripts/experiments/discord_dm.py send no-mutual-guild
uv run python scripts/experiments/discord_dm.py send too-long-no-mutual-guild --length 2001  # 長度檢查先於共同伺服器
uv run python scripts/experiments/discord_dm.py fixtures                # 遮掉 id 與名字，寫 tests/fixtures/http/discord/
uv run python scripts/experiments/discord_dm.py embed-url               # 票 124：embed url 與 Markdown 連結收哪些主機
```
