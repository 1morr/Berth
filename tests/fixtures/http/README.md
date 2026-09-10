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

2026-09-09（票 03），對真的 `api.themoviedb.org` 錄的，用一把使用者自備的 v4 read access token。
每支端點各錄 `en-US` 與 `zh-TW` 兩輪——**兩輪的成員與順序會不同**，那正是要守住的行為：

| 檔案 | 來源 |
| --- | --- |
| `tmdb/trending-{tv,movie}-week.{en,zh}.json` | `GET /3/trending/{tv,movie}/week?language={en-US,zh-TW}`。整份 20 筆太長，`results` 只留前 6 筆（其餘欄位原樣）。`trending-tv-week` 這一對是「`language` 換掉成員」的證據：`en` 的 `258230` 與 `97546` 不在 `zh` 那一輪裡 |
| `tmdb/{tv,movie}-popular.{en,zh}.json` | `GET /3/{tv,movie}/popular?language=…`，同樣只留前 6 筆。這兩支的每一筆**沒有** `media_type` |
| `tmdb/search-multi.spy-x-family.{en,zh}.json` | `GET /3/search/multi?query=spy%20x%20family&include_adult=false&language=…`。整份就是 2 筆（一劇一影），未裁剪；`zh` 那一輪是顯示用標題的證據 |
| `tmdb/search-multi.miyazaki.en.json` | 同一支端點，`?query=miyazaki`。20 筆裡 16 筆是 `person`，只留前 8 筆——人物要被丟掉這件事靠它釘住 |

2026-09-09（票 04），對真的 `api.themoviedb.org` 錄的，同一把使用者自備的憑證。這一組是 Media 詳情
用的四支端點，作品選 SPY×FAMILY（有 Absolute group）與海洋奇緣 2（電影）：

| 檔案 | 來源 |
| --- | --- |
| `tmdb/tv-detail.spy-x-family.{en,zh}.json` | `GET /3/tv/120089?language={en-US,zh-TW}`，英文那一份帶 `append_to_response=alternative_titles,translations,episode_groups`。`translations.translations` 裁到前 6 筆。它同時是「一部作品可以有五個 episode group」的證據——只有 `type: 2` 那一個是絕對編號 |
| `tmdb/tv-season.spy-x-family.s02.json` | `GET /3/tv/120089/season/2?language=en-US`。12 集全留，但每一集的 `crew` 與 `guest_stars` 拿掉了（整份 260 KB，adapter 一個欄位都不讀） |
| `tmdb/tv-season.spy-x-family.s00.json` | 同上，`season/0`。`season_number: 0` 是 Specials，它是一季不是特例 |
| `tmdb/tv-episode-group.spy-x-family.absolute.json` | `GET /3/tv/episode_group/689a2aec017d0bc9ecc6fac8`。`groups[0].episodes` 裁到前 30 筆——第 25 筆（`order: 24`）是 S01E25、第 26 筆（`order: 25`）是 S02E01，跨季那一步正是絕對編號要守的行為 |
| `tmdb/movie-detail.moana-2.{en,zh}.json` | `GET /3/movie/1241982?language=…`，英文那一份帶 `append_to_response=alternative_titles,translations`（同樣裁到前 6 筆翻譯）。電影有 `runtime`、沒有 `seasons` |
| `tmdb/tv-detail.not-found.json` | `GET /3/tv/99999999`，回 404 與 `status_code: 34`。「這個 id 不存在」與「TMDB 壞了」的下一步不同，所以它有自己的一份 |

2026-09-10（M1 票 08），對真的 Prowlarr 2.5.2.5491 錄的。那台上有五個加得起來的公開站
（acgrip / dmhy / mikan / thepiratebay / yts），所以每一筆的成敗都是它自己連出去的結果：

| 檔案 | 來源 |
| --- | --- |
| `prowlarr/search.spy-x-family.json` | `GET /api/v1/search?query=SPY%20x%20FAMILY&type=search`。整份 1200 筆，只留能證明形狀差異的 8 筆：ACG.RIP（**沒有** `infoHash` 也沒有 `magnetUrl`）、Mikan（40 字十六進位 hash）、dmhy（**32 字 base32** hash，而且沒有 `downloadUrl`）、The Pirate Bay（`guid` 就是磁力連結）、YTS（電影，有 `posterUrl` 與 `imdbId`）。Mikan 與 dmhy 那兩筆是**同一個發佈**，base32 解碼後與十六進位那一個位元組相同 |
| `prowlarr/search.severance.json` | 同一支端點，`?query=Severance`。美劇的命名風格，另含兩筆同名的 2006 電影 |
| `prowlarr/search.moana-2.json` | 同上，`?query=Moana%202` |
| `prowlarr/search.no-results.json` | 同上，一個查不到的關鍵字。**空陣列加 200**，搜不到不是錯誤 |
| `torznab/search.acgrip.xml` | Prowlarr 的單站 Torznab 網址 `/2/api?t=search&q=`。前 2 筆。`torznab:attr` 有 `seeders` 與 `peers`（**沒有** `leechers`），這一站不報 `infohash` |
| `torznab/search.dmhy.xml` | 同上，`/6/api`。前 2 筆。`infohash` 是 base32，`guid` 是磁力連結，一筆帶三個 `category` |
| `torznab/caps.yts.xml` | `/4/api?t=caps`。`movie-search` 的 `supportedParams` 是 `q,imdbid`——`supportedParams` 是逗號清單，而**公開站沒有 tmdbid** |

這一組的 `apikey` 一律換成 `0000…0001`（Prowlarr 的號碼）。下載網址裡的 `link=` 密文原樣留著：
它每次請求都不一樣（實測 1021 筆只有 1 筆重疊），所以它不是秘密，而它的形狀正是「不能拿它當身分」
的證據。**沒有** tmdbid 版本的 caps：627 份定義裡支援 tmdbid 的 93 份全部是私站，錄不到；
那條分支由 `capability_of()` 的純函式單元測試守著，不偽造一份「錄製回應」。

重錄的指令（`$KEY` 是那台 Prowlarr 的 API key）：

```bash
curl -s -H "X-Api-Key: $KEY" "http://localhost:19696/api/v1/search?query=SPY%20x%20FAMILY&type=search"
curl -s "http://localhost:19696/2/api?t=search&apikey=$KEY&q=SPY%20x%20FAMILY"
```

重錄的指令（`$TOKEN` 是自己的 v4 read access token 或 v3 key）：

```bash
curl -s -H "Authorization: Bearer $TOKEN"   "https://api.themoviedb.org/3/trending/tv/week?language=en-US"
```

裁剪只砍陣列的尾巴（`results`、`episodes`、`translations`），不改任何一筆的內容；重新輸出時用
`json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)`，與 `configuration.json` 那一份
同一個格式。**唯一的例外**是季那兩份：每一集的 `crew` 與 `guest_stars` 整欄拿掉，因為它們佔掉整份
檔案的 96%（260 KB → 9 KB）而 adapter 一個欄位都不讀；留下來的欄位仍然多過它讀的那五個。

## 規則

- 檔案裡不放真的秘密，**測試檔裡也不放**。同形狀的假值一律是 `0000…000n`，每個服務一個號碼：
  `…0001` Prowlarr API key、`…0002` Jellyfin access token、`…0003` TMDB v3 API key。
  2026-09-09 發現票 08 把一把**真的** TMDB v3 key 當成「同形狀的假值」寫進
  `tests/integration/test_adapter_contracts.py`，而 repo 是公開的——所以這條規則管的不只是
  fixture 檔，也管任何寫得出憑證形狀的測試。看起來像秘密的常數就照這個號碼表挑一個。
- 要重錄就重跑一次上面的來源，不要手改內容——改過的 fixture 就不再是證據。
- 新增服務或版本時開新檔案，不要覆寫既有的：舊版本的行為差異正是契約測試要守的東西
  （qBittorrent 4.4 與 5.x 的差異在票 08）。
