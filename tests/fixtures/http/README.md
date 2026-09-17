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
plan §9.4 的序列之後那台伺服器的狀態，不是手排出來的場景（錄的當時序列還有插件那兩步，票 14b 之後剩七步）：

| 檔案 | 來源 |
| --- | --- |
| `jellyfin/library-virtualfolders.json` | `GET /Library/VirtualFolders`，bootstrap 建好 Movies / TV / Anime 之後。另外含一個**使用者自己的** `Films` 媒體庫：兩條路徑（Berth 加的 + 原本的）、metadata fetcher 掛了 `TheTVDB`，也就是 brief §16.4 那個警告的來源 |
| `jellyfin/auth-keys.berth.json` | `GET /Auth/Keys`，`POST /Auth/Keys?app=Berth` 之後。`AccessToken` 換成同形狀的假值 |
| `jellyfin/authenticate-by-name.json` | `POST /Users/AuthenticateByName`，`AccessToken` 換成同形狀的假值 |
| `jellyfin/scheduledtasks.merge-versions.json` | `GET /ScheduledTasks`。錄的那一台當時裝著 MergeVersions（檔名的由來），所以它同時是「`Id` 與 `Key` 不同」（brief §20.7）與內建 `RefreshLibrary` 的證據；票 14b 起 Berth 只用後者。原文不改，它是一份紀錄 |
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

2026-09-10（票 09），對 `lscr.io/linuxserver/qbittorrent:5.2.3`（API 2.15.1）與 `:4.4.5`
（API 2.8.5）兩台乾淨的容器錄的。**`torrents/add` 的成功形狀兩版不同**，而 brief §20.2
原本記的「一律回 200 `Ok.`」只對舊的那一版成立：

| 檔案 | 來源 |
| --- | --- |
| `qbittorrent/torrents-add.accepted.4.4.5.txt` | 4.4.5，Berth 的那一份表單（`paused=false`）加一個新的磁力連結 → `200` + `Ok.` |
| `qbittorrent/torrents-add.accepted.5.2.3.json` | 5.2.3，同一份表單（`stopped=false`）→ `200` + 一份 JSON 摘要 |
| `qbittorrent/torrents-add.conflict.5.2.3.txt` | 5.2.3，同一個磁力連結送第二次 → `409` + `Conflict`（4.4.5 沒有這個行為，它回 `Ok.`） |
| `qbittorrent/torrents-add.pending.5.2.3.json` | 5.2.3，`urls=http://indexer.invalid/x.torrent` → `202` + `pending_count: 1`（背景抓，失敗永遠不會回來） |
| `qbittorrent/torrents-add.invalid.5.2.3.txt` | 5.2.3，multipart 上傳一段 HTML 當 `.torrent` → `415` + 檔名與原因 |

2026-09-10（票 10），對 `lscr.io/linuxserver/qbittorrent:4.4.5` 與 `:5.2.3` 兩台乾淨的容器錄的
（`scripts/experiments/qbittorrent_poller.py`）。三個 torrent 分別演三種處境：隨機 hash 的磁力連結
（永遠拿不到 metadata）、合法但磁碟上沒有資料的 `.torrent`、以及**資料先寫進 save path** 的那一個
（qBittorrent 自己校驗完就是完成，所以「完成」是它算出來的，不是腳本擺出來的）：

| 檔案 | 來源 |
| --- | --- |
| `qbittorrent/sync-maindata.full.{4.4.5,5.2.3}.json` | `GET /api/v2/sync/maindata?rid=0`。`full_update: true` 加三個 torrent。**未完成時的 `completion_on` 兩版不同**——4.4.5 是 `0`、5.2.3 是 `-1`，所以完成判定只能寫 `> 0`。5.2.3 的欄位多了 `has_metadata`、`private`、`popularity` 等 20 幾個，4.4.5 沒有 |
| `qbittorrent/sync-maindata.partial.{4.4.5,5.2.3}.json` | 同一條連線的下一輪（`?rid=1`），中間又加了一個磁力連結。**增量只帶變動的欄位**：既有的那幾筆有的只剩 `{"num_leechs", "time_active"}`，新加的那一筆才是完整的。不合併就會得到一份沒有 category、沒有 state 的空殼 |
| `qbittorrent/sync-maindata.removed.{4.4.5,5.2.3}.json` | 再下一輪（`?rid=2`），中間刪掉剛才那一筆。`torrents_removed` 是一個 hash 陣列 |
| `qbittorrent/torrents-files.multi.{4.4.5,5.2.3}.json` | `GET /api/v2/torrents/files?hash=…`，完成的那一包（兩個檔案，其中一個在子資料夾）。`name` **含 torrent 自己的根目錄那一層且相對 `save_path`**，兩版一致（再驗一次 brief §20.7）。第二筆**沒有** `is_seed` 這個鍵——欄位是逐筆的，不是逐回應的 |
| `qbittorrent/auth-login.banned.{4.4.5,5.2.3}.txt` | 連續 5 次帳密錯之後第 6 次的 `POST /api/v2/auth/login`：`403` + `Your IP address has been banned after too many failed authentication attempts.`。**兩版同一句話**，而帳密錯本身不是 403（4.4.5 是 `200` + `Fails.`，5.2.3 是 `401`） |
| `qbittorrent/app-version.banned.{4.4.5,5.2.3}.txt` | 被封之後的 `GET /api/v2/app/version`：`403` + `Forbidden`——與「沒有登入」一模一樣。所以「被封了」這個判定只有登入那一支做得到 |

`metaDL` 期間的 `torrents/files` 回的是 `200` + `[]`（兩版皆然），與「這個 torrent 不存在」同形，
所以契約測試直接 `respond(200, text="[]")`，不另存一個空陣列的檔案。

**`sync/maindata` 的 rid 增量掛在 session 上**（同一輪實測）：不帶 cookie 的話每一次請求都是新
session，`rid` 永遠回不到增量（每一輪都 `full_update: true`）。錄製腳本因此裝了 cookie jar，
而產品這一側靠的是 httpx client 自己的 cookie——所以 `Downloader` 把 client 握著不放。

2026-09-15（票 12），對 `lscr.io/linuxserver/jellyfin:latest`（**12.0.0**）錄的。那一台是 M1 驗收時
Berth 自己入庫三部作品（The Bear S03、Frieren S01、Oppenheimer）、Jellyfin 掃完之後的狀態，憑證是
Berth 在精靈第 3 步建的 API key，**不帶 `userId`**：

| 檔案 | 來源 |
| --- | --- |
| `jellyfin/items.tv.series.json` | `GET /Items?parentId=<TV 媒體庫>&recursive=true&includeItemTypes=Series&fields=Path,ProviderIds,MediaSources`。`Path` 是作品資料夾，`ProviderIds.Tmdb` 是字串；Series 沒有檔案，所以沒有來源路徑 |
| `jellyfin/items.tv.episodes.json` | 同一支端點，`includeItemTypes=Episode`。10 筆只留前 2 筆。單一版本時 `MediaSources[0].Path` 就是自己的 `Path` |
| `jellyfin/items.movies.movie.json` | Movies 媒體庫，`includeItemTypes=Movie`。電影的檔案就是 item 自己 |

2026-09-17（M1.5 票 01），`scripts/experiments/jellyfin_permissions.py --record` 對一次性的
`lscr.io/linuxserver/jellyfin:version-12.1ubu2604`（**12.1.0**）錄的。那一台有三個媒體庫 TV / Movies / Anime，
metadata 來自 NFO（網路 fetcher 關掉）；憑證是那一台的 API key，`userId` 一律是**只開放 TV 與 Movies 的一般使用者**
（Anime 是他沒有權限的媒體庫），所以每一份都是「受限使用者看到的樣子」。錄之前用 API key 替他寫了觀看紀錄：
Alpha Show 與 Bravo Show 看過第一集、Frieren（TV）第一集看到 3 分鐘、Foxtrot Movie 看到 5 分鐘、Echo / Golf Movie
看過 3 / 1 次。**重跑腳本會整組重錄**：item id 是 `MD5(型別全名 + 路徑)`（brief §20.9，原始碼；兩輪一次性容器實測相同）
所以不變，使用者 id、`ServerId`、日期與 `traceId` 會變。伺服器不是 12.1.0 時 `--record` 會停下來——依下面的規則，
新版本要開新檔名。
測量結果與判準在研究文件 `docs/research/library-browsing.md` §2、§3.1、§5、§6、§10。

| 檔案 | 來源 |
| --- | --- |
| `jellyfin/userviews.restricted.json` | `GET /UserViews?userId=U`。只有 TV 與 Movies——這是權限的**權威清單**，`Id` 與 `/Library/VirtualFolders` 的 `ItemId` 同一種格式 |
| `jellyfin/users.restricted.json` | `GET /Users/{U}`（API key）。`Policy.EnableAllFolders=false`、`Policy.EnabledFolders` 是兩個媒體庫的 id、`Policy.IsDisabled=false` |
| `jellyfin/users.restricted.disabled.json` | 同一支端點，`Policy.IsDisabled=true` 之後。停用之後 API key 代讀照常回資料（研究 §2），所以「停用」只能從這裡讀出來 |
| `jellyfin/items.tv.series.userdata.json` | `GET /Items?userId=U&parentId=<TV>&recursive=true&includeItemTypes=Series&sortBy=SortName&sortOrder=Ascending&fields=PrimaryImageAspectRatio,ProviderIds,Path&imageTypeLimit=1&enableImageTypes=Primary,Backdrop,Thumb&startIndex=0&limit=100`（媒體庫牆，jellyfin-web 的參數）。每部劇帶 `UserData`：`UnplayedItemCount`、`PlayedPercentage`；**Hotel Show 沒有 `ProviderIds.Tmdb`**、也沒有 `CommunityRating` |
| `jellyfin/items.movies.movie.userdata.json` | 同上，Movies 媒體庫、`includeItemTypes=Movie`。看到一半的那部帶 `PlaybackPositionTicks` 與 `PlayedPercentage`，看過的帶 `PlayCount` 與 `LastPlayedDate` |
| `jellyfin/items.tv.series.page.json` | **M1.5 票 03 加錄**（`--record --only`，另一輪一次性容器，所以使用者 id、`ServerId` 與日期和這一組其他檔案不同；item id 相同）。同 `items.tv.series.userdata.json` 的查詢，`startIndex=1&limit=2`：恰好是 Bravo Show 與 Frieren，`TotalRecordCount` 仍是整份的 4——分頁參數伺服器真的有作用的證據 |
| `jellyfin/items.tv.series.index.json` | **M1.5 票 04 重錄**（`--record --only`，又一輪一次性容器：使用者 id、`ServerId`、日期與圖的 `ImageTags` 都和這一組其他檔案不同——tag 由圖的修改時間算出來；item id 相同）。`GET /Items?userId=U&parentId=<TV>&recursive=true&includeItemTypes=Series&fields=ProviderIds&imageTypeLimit=1&enableImageTypes=Primary&enableUserData=false&enableTotalRecordCount=false`（Berth 端比對用的整份清單，篩選後的牆也從它畫海報）：每部只帶 `ImageTags.Primary` 與它的 `ImageBlurHashes`，沒有 `UserData`，`ProviderIds` 與 `ProductionYear` 還在；**`enableTotalRecordCount=false` 不帶 `limit` 時照樣回 `TotalRecordCount`**。票 03 錄的前一版帶 `enableImages=false`，沒有 `ImageTags` |
| `jellyfin/items.tv.series.sort-rating.{ascending,descending}.json` | **M1.5 票 06 加錄**（`--record --only`，另一輪一次性容器：使用者 id、`ServerId`、日期與 `ImageTags` 和這一組其他檔案不同；item id 相同）。同 `items.tv.series.userdata.json` 的查詢，`sortBy=CommunityRating,SortName`，`sortOrder` 分別是 `Ascending` / `Descending`：沒有評分的 Hotel Show 在升冪最前、降冪最後，兩份互為反序，也都不是名稱順序——`sortBy` 與 `sortOrder` 伺服器真的有作用的證據 |
| `jellyfin/items.movies.movie.sort-dateplayed.descending.json` | 同上一輪。電影庫的牆，`sortBy=DatePlayed,SortName,ProductionYear&sortOrder=Descending`（jellyfin-web 電影庫的寫法）：Golf（5 月看的）、Echo（4 月）、沒看過的 Foxtrot，名稱順序是 Echo、Foxtrot、Golf |
| `jellyfin/items.tv.series.{genres,years}.json` | 同上一輪。牆的查詢加 `genres=Drama\|Comedy` / `years=2020,2023`：各剩 2 部（Alpha 與 Bravo / Bravo 與 Frieren），`TotalRecordCount` 是篩過之後的 2。類型寫在 NFO 裡（實驗腳本的 `TITLES`），DTO 不帶 `Genres` |
| `jellyfin/items-filters.tv.json` | `GET /Items/Filters?userId=U&parentId=<TV>&includeItemTypes=Series`。`{Genres, Tags, OfficialRatings, Years}`；**不帶 `parentId` 時四份全空**，所以沒有另存那一份 |
| `jellyfin/useritems-resume.restricted.json` | `GET /UserItems/Resume?userId=U&mediaTypes=Video`。一集一部電影；Anime 裡看到一半的那一集**不在**（不帶 `parentId` 會套權限） |
| `jellyfin/shows-nextup.restricted.json` | `GET /Shows/NextUp?userId=U`。Alpha 與 Bravo 的第二集；Anime 那部看過第一集的劇**不在** |
| `jellyfin/useritems-resume.watching.json` | **M1.5 票 07 加錄**（`--record --only`，另一輪一次性容器：使用者 id、`ServerId`、日期與 `ImageTags` 和這一組其他檔案不同；item id 相同）。**媒體樹多了橫圖**：Alpha Show 與 Foxtrot Movie 的資料夾有 `landscape.jpg`（Thumb）與 `fanart.jpg`（Backdrop），Bravo Show 只有 `fanart.jpg`，其餘仍只有 `poster.jpg`。`GET /UserItems/Resume?userId=U&limit=12&imageTypeLimit=1&enableImageTypes=Primary,Backdrop,Thumb&enableTotalRecordCount=false&mediaTypes=Video`（Berth 首頁那一支，jellyfin-web 的參數）：Frieren 那一集（沒有任何橫圖）與 Foxtrot Movie（自己的 Thumb 與 Backdrop）；`TotalRecordCount` 照樣回 2 |
| `jellyfin/useritems-resume.watching.mixed.json` | 同上一輪，拿掉 `mediaTypes`：多出三季與三部劇——`mediaTypes=Video` 伺服器真的有過濾的對照 |
| `jellyfin/useritems-resume.watching.tv.json` | 同上一輪，加 `parentId=<TV>`：只剩 Frieren 那一集 |
| `jellyfin/shows-nextup.watching.json` | 同上一輪。`GET /Shows/NextUp?userId=U&limit=24&imageTypeLimit=1&enableImageTypes=Primary,Backdrop,Thumb&enableTotalRecordCount=false&enableResumable=false&nextUpDateCutoff=<錄製當下減 365 天>`：Bravo（最後看 2026-03-01）在 Alpha（2026-01-01）前。Alpha 的集帶 `ParentThumbItemId` / `ParentBackdropItemId`（都是劇），Bravo 的集只有 `ParentBackdrop*`；**兩集都沒有 `SeriesThumbImageTag`** |
| `jellyfin/shows-nextup.watching.cutoff.json` | 同上，`nextUpDateCutoff=2026-02-15T00:00:00.000Z`：只剩 Bravo |
| `jellyfin/shows-nextup.watching.movies.json` | 同上，加 `parentId=<Movies>`：空 |
| `jellyfin/shows-seasons.json` | `GET /Shows/{Alpha}/Seasons?userId=U&fields=ItemCounts,PrimaryImageAspectRatio`。兩季，季名是伺服器 UI 語言的「第 1 季」 |
| `jellyfin/shows-episodes.json` | `GET /Shows/{Alpha}/Episodes?userId=U&seasonId=<第一季>&fields=Overview,PrimaryImageAspectRatio`。三集；集名來自檔名（沒有集的 NFO） |
| `jellyfin/userplayeditems.post.json` | `POST /UserPlayedItems/{Bravo S01E02}?userId=U` 的 200：`Played=true, PlayCount=1, LastPlayedDate` |
| `jellyfin/userplayeditems.delete.json` | 同一集接著 `DELETE`：`Played=false, PlayCount=0`，**沒有 `LastPlayedDate` 這個鍵** |
| `jellyfin/images-primary.no-tag.headers.json` | `GET /Items/{Alpha}/Images/Primary`，**匿名**。只存狀態碼與標頭：`Cache-Control: public`、沒有 `ETag` |
| `jellyfin/images-primary.tag.headers.json` | 同上加 `?tag=<ImageTags.Primary>`：`Cache-Control: public, max-age=31536000, immutable` 與 `ETag: "<tag>"`（錯的 tag 也是這樣，研究 §6） |
| `jellyfin/images-primary.resized.headers.json` | 同上加 `fillWidth=100&quality=90&format=Webp`：`image/webp`，`Last-Modified` 是縮圖產生的時間 |

**沒權限時回什麼**（同一個受限使用者、API key，對象都在 Anime）：

| 檔案 | 來源 |
| --- | --- |
| `jellyfin/items-id.forbidden.json` | `GET /Items/{無權的劇}?userId=U` 的 **404**。body 是 problem details（`type`、`title`、`status`、`traceId`） |
| `jellyfin/shows-seasons.forbidden.json` | `GET /Shows/{無權的劇}/Seasons?userId=U` 的 **404**，problem details |
| `jellyfin/shows-episodes.forbidden.json` | `GET /Shows/{無權的劇}/Episodes?userId=U` 的 **404**。body 是**一個 JSON 字串** `"Series not found"`，不是 problem details——解析 404 不能假設是物件 |
| `jellyfin/userplayeditems.forbidden.json` | `POST /UserPlayedItems/{無權的集}?userId=U` 的 **404**，problem details；打完立刻讀回（`ids=` 不檢查權限）確認沒有寫入 |
| `jellyfin/items.parent-forbidden.json` | `GET /Items?userId=U&parentId=<Anime>&recursive=true` 的 **200**：Anime 的劇、季、集與一個 `Folder` 共 10 筆。**這是洩漏的證據**，不是正常回應——API key 帶 `parentId` 時 Jellyfin 不套權限，所以 Berth 要先對 `UserViews` 驗 `parentId` |
