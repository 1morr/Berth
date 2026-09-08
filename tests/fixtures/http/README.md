# 錄製回應

adapter 契約測試的輸入（plan §1.2、§10）。每個檔案都是**對真服務錄下來的回應原文**，
不是手寫的假 payload——手寫的 payload 只會證明程式與自己的想像一致。

## 來源

2026-09-07（票 05），用 `deploy/docker-compose.yml` 起一套乾淨的服務錄的：

| 檔案 | 來源 |
| --- | --- |
| `jellyfin/system-info-public.setup-pending.json` | `lscr.io/linuxserver/jellyfin`（10.11.11）第一次啟動，`GET /System/Info/Public` |
| `jellyfin/system-info-public.configured.json` | 同一台跑完 `POST /Startup/Complete` 之後的同一支端點 |
| `qbittorrent/app-version.txt` | `lscr.io/linuxserver/qbittorrent`（v5.2.3），從白名單內的 IP 打 `GET /api/v2/app/version` |
| `qbittorrent/app-webapiversion.txt` | 同上，`GET /api/v2/app/webapiVersion` |
| `qbittorrent/app-version.forbidden.txt` | 同一支端點，從**不在**白名單的宿主打，回 403 |
| `prowlarr/ping.json` | `lscr.io/linuxserver/prowlarr` 第一次啟動，`GET /ping` |
| `prowlarr/indexer.empty.json` | 同一台，`GET /api/v1/indexer`（還沒加任何索引站） |
| `prowlarr/indexer.configured.json` | 由同一台的 `GET /api/v1/indexer/schema` 的 Nyaa.si 條目裁出常用欄位並補上 `id`。**不是**整包錄下來的：容器連不出去（TLS 被中斷），`POST /api/v1/indexer` 建不起來 |
| `../prowlarr/config.xml` | 同一台的 `/config/config.xml`，`<ApiKey>` 換成同形狀的假值 |

2026-09-07（票 06），對 `jellyfin/jellyfin:10.11.11` 錄的。這一組是 Berth 自己跑完
plan §9.4 的九步之後那台伺服器的狀態，不是手排出來的場景：

| 檔案 | 來源 |
| --- | --- |
| `jellyfin/library-virtualfolders.json` | `GET /Library/VirtualFolders`，bootstrap 建好 Movies / TV / Anime 之後。另外含一個**使用者自己的** `Films` 媒體庫：兩條路徑（Berth 加的 + 原本的）、metadata fetcher 掛了 `TheTVDB`，也就是 brief §16.4 那個警告的來源 |
| `jellyfin/auth-keys.berth.json` | `GET /Auth/Keys`，`POST /Auth/Keys?app=Berth` 之後。`AccessToken` 換成同形狀的假值 |
| `jellyfin/authenticate-by-name.json` | `POST /Users/AuthenticateByName`，`AccessToken` 換成同形狀的假值 |
| `jellyfin/scheduledtasks.merge-versions.json` | `GET /ScheduledTasks`，MergeVersions 裝好並重啟之後。`MergeMoviesTask` / `MergeEpisodesTask` 的 `Id` 與 `Key` 不同，正是 brief §20.7 那一條 |
| `jellyfin/plugins.merge-versions-installed.json` | `GET /Plugins`，同一台 |
| `jellyfin/repositories.with-merge-versions.json` | `GET /Repositories`，Berth 加完 danieladov 之後（所以也證明「重按不會加第二次」認得出自己加的那筆） |
| `jellyfin/packages.merge-versions.json` | `GET /Packages` 裡 `Merge Versions` 那一筆（整份太大，只留這個套件） |
| `jellyfin/libraries-availableoptions.{movies,tvshows}.with-tvdb.json` | `GET /Libraries/AvailableOptions`，**額外裝了官方 TVDB 插件之後**。插件會替每個型別多掛 fetcher，這正是「圖片 fetcher 不可以寫死」的證據 |

2026-09-08（票 08）。qBittorrent 兩個版本各起一個容器錄同樣四支端點；Prowlarr 是同一台真的
2.5.2.5491，索引站的成敗是它自己連出去的結果；TMDB 打的是真的 `api.themoviedb.org`：

| 檔案 | 來源 |
| --- | --- |
| `qbittorrent/app-{version,webapiversion}.{4.4.5,5.2.3}.{txt}` | `lscr.io/linuxserver/qbittorrent:4.4.5` 與 `:5.2.3`，從白名單內的容器打 `GET /api/v2/app/version` 與 `/webapiVersion`。兩版差在 `2.8.5` 與 `2.15.1`，`paused` / `stopped` 的判斷就綁在這兩個字串上 |
| `qbittorrent/app-preferences.{4.4.5,5.2.3}.json` | 同上，`GET /api/v2/app/preferences`。乾淨實例，所以精靈第 4 步的五個鍵全部與建議值不同；`save_path` 的尾斜線兩版不同 |
| `qbittorrent/torrents-categories.{4.4.5,5.2.3}.json` | 同上，`GET /api/v2/torrents/categories`（票 04 的實驗留下的 `berth-exp` 分類）。兩版都是 `savePath` |
| `prowlarr/indexer-schema.defaults.json` | `GET /api/v1/indexer/schema` 裡精靈預設勾的那十個站（整份 627 筆太大，只留這十筆，順序同 `DEFAULT_INDEXERS`） |
| `prowlarr/indexer.created.dmhy.json` | `POST /api/v1/indexer` 加 dmhy 成功時的 201 回應 |
| `prowlarr/indexer.rejected.nyaasi.json` | 同一支端點加 nyaa.si 失敗時的 400。**新增之前 Prowlarr 會先連一次那個站**，這份就是連不上的原文 |
| `prowlarr/indexer.rejected.duplicate.json` | 同名再加一次的 400（`Should be unique`） |
| `prowlarr/indexer.defaults-added.json` | `GET /api/v1/indexer`，加完那一輪之後。十個站裡加得起來的是這五個，另外五個從這台機器連不出去 |
| `prowlarr/config-host.json` | `GET /api/v1/config/host`，`apiKey` 換成 `0000…0001`、密碼欄位清空 |
| `torznab/caps.xml` | Prowlarr 的單站 Torznab 網址 `?t=caps`（Jackett 與單站的形狀相同） |
| `tmdb/configuration.json` | `GET /3/configuration`，帶 v4 read access token |
| `tmdb/configuration.unauthorized.json` | 同一支端點帶一把無效的 key，回 401 |

2026-09-08（票 11），M0 驗收時對同樣那兩個版本的 `POST /api/v2/auth/login` 錄的。這一組存在的
理由是**成敗的形狀跨大版本不同**，而原本的實作只認 4.x 的成功樣子（brief §20.2）：

| 檔案 | 來源 |
| --- | --- |
| `qbittorrent/auth-login.ok.4.4.5.txt` | `:4.4.5`，正確的 `admin` / `adminadmin`，`200` + `Ok.` |
| `qbittorrent/auth-login.fails.4.4.5.txt` | 同一台，錯的密碼。**仍然是 `200`**，只有 body 說得出失敗 |
| `qbittorrent/auth-login.unauthorized.5.2.3.txt` | `:5.2.3`，錯的密碼，`401` + `Unauthorized` |

5.2.3 **成功**沒有對應的檔案：它回的是 `204` 空 body（契約測試直接 `respond(204)`）。免密白名單上的
來源在 5.x 一律拿到這個 204，錯的帳密也一樣——那正是套件內 Berth 的處境。

## 規則

- 檔案裡不放真的秘密。`config.xml` 的 API key 是拋棄式容器產的，仍然換成 `0000…0001`。
- 要重錄就重跑一次上面的來源，不要手改內容——改過的 fixture 就不再是證據。
- 新增服務或版本時開新檔案，不要覆寫既有的：舊版本的行為差異正是契約測試要守的東西
  （qBittorrent 4.4 與 5.x 的差異在票 08）。
