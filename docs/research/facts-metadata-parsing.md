# 事實：Metadata、解析與季集

查證過的外部事實。編號沿用 brief 原本的節號（`§20.x`），程式碼與文件用它引用，編號不重用。索引在 [brief §20](../design-brief.md)。

## 事實

### 20.3 Metadata provider 與動漫 ID 對應

細節（逐筆實測、數字、原文引用）在 [`docs/research/anime-episode-source.md`](anime-episode-source.md#從-brief-搬來203)；下面只留結論與來源。

**TMDB**（細節：[研究](anime-episode-source.md#203-tmdb)）

- 季/集 schema：`season_number: 0` 為 Specials；每集有 `episode_number`、`name`、`air_date`、`episode_type`、`runtime`（未播的集 `runtime` 是 `null`）。（[tv-season-details](https://developer.themoviedb.org/reference/tv-season-details)；2026-09-09 實測）
- Episode Groups 類型：Original air date / **Absolute** / DVD / Digital / Story arc / Production / TV。Absolute 只在有人替該劇建立 group 時存在（實測 10 部只有 6 部）。（[episode-group-details](https://developer.themoviedb.org/reference/tv-episode-group-details)）
- **Absolute group 不能當備援，絕對編號要自己從 0-based 的 `order` 推**（2026-09-08 / 09-09 實測）：group 內 `episode_number` 保留播出序原值（SPY×FAMILY S02E01 仍是 `episode_number: 1`，絕對編號 26、`order: 25`）；有的部有多個互相衝突的 Absolute group（進擊的巨人四個，集數 89/97/97/97），柯南那個叫 "China Online Version"；同一部作品有五個 group，只有 `type: 2` 是絕對編號。
- 標題：`name` 依 `language`（預設 `en-US`）回傳，翻譯缺時可能是空字串，**要自己 fallback 到 `original_name`**；2026-09-09 實測 `zh-TW` 未翻譯時回英文，兩種都當「顯示英文」。`alternative_titles` 是各國別名、與 translations 無關，兩者都應納入標題比對。（[translations](https://developer.themoviedb.org/reference/tv-series-translations)、[alternative-titles](https://developer.themoviedb.org/reference/tv-series-alternative-titles)）
- `find/{external_id}` 支援 `imdb_id`、`tvdb_id` 等反查。（[find-by-id](https://developer.themoviedb.org/reference/find-by-id)）
- 速率：官方未列；員工在論壇稱約 50 req/s、20 併發/IP。條款：**非商業免費，需顯示 TMDB logo 與聲明「This product uses the TMDB API but is not endorsed or certified by TMDB.」**（[faq](https://developer.themoviedb.org/docs/faq)）
- 探索三支端點（2026-09-09 實測，fixture `tests/fixtures/http/tmdb/`）：`trending/{tv,movie}/week` 與 `search/multi` 的每筆帶 `media_type`，`{tv,movie}/popular` 不帶；劇集用 `name` / `original_name` / `first_air_date`，電影用 `title` / `original_title` / `release_date`；`search/multi` 也回 `person`（`?query=miyazaki` 20 筆中 16 筆）。
- `language` 換掉的不只文字，還有清單成員與順序（2026-09-09 實測：`trending/tv/week` 的 `en-US` 與 `zh-TW` 各 20 筆只有 17 筆相同）→ 清單以 `en-US` 為準，`zh-TW` 只當「這一部叫什麼」的查表（plan §8.3）。`popularity` **不是**清單排序依據（`tv/popular` 首五筆 583 / 440 / 692 / 417 / 398），要照 TMDB 排名就用陣列順序。
- 詳情四支端點（2026-09-09 實測，票 04）：`tv/{id}` 的 `seasons[]` 有 `season_number` / `name` / `episode_count` / `air_date`；`movie/{id}` 有 `runtime` 無 `seasons`；不存在的 id 回 **404 加 `status_code: 34`**，與「TMDB 壞了」是兩件事。
- 劇集 `status`（2026-09-27 查證，M4 票 13；官方未列，維護者在[論壇](https://www.themoviedb.org/talk/6685c10585e1cbe90c4a5fe0)確認）：`Returning Series`、`Planned`、`In Production`、`Ended`、`Canceled`、`Pilot`。Berth 把 `Ended` 與 `Canceled` 讀成「不會再播了」（`MediaSnapshot.ended`，RSS Series 完結看它，§15「呈現」）。
- 動漫 split-cour 正被 TMDB 與 TVDB 同步合併成單季連續編號（[TMDB talk](https://www.themoviedb.org/talk/697d0680d564e13094e4e270)、[TVDB KB](https://support.thetvdb.com/kb/faq.php?id=61)），字幕組多數按 cour 從 01 重算。2026-09-09 實測：TMDB 連獨立的連續季也併（咒術迴戰 3 季→1 季 59 集、Re:Zero 4→1 共 85 集、芙莉蓮 2→1 共 38 集、柯南 34→1 共 1213 集），TVDB 這幾部維持分季；但合併只造成 0.4 個百分點差距，**主要錯誤來源是檔名沒有季號**（§10、[研究](anime-episode-source.md#0-結論)）。
- **季名逐語言翻譯，三套字都有人用**（2026-09-10 實測 `tv/85937`、`tv/1429`，票 06）：同一季 `name` 在 `en-US` / `zh-TW` / `zh-CN` 分別是 `Hashira Training Arc` / `柱訓練篇` / `柱训练篇`；進擊的巨人第四季為 `The Final Season` / `第4季` / `最终季`。**篇章名比對必須三套都留**（真實發佈最常見是簡體，只留英文則 plan §4.4 規則一個都不會命中）；代價是 `tv/{id}` 多打一輪 `zh-CN`（只取季名，電影不打，plan §4.3、§8.3）。
- `alternative_titles` 帶篇章名但不帶季號（2026-09-10 實測）：CN 只有兩筆、TW 五個篇章齊全、JP 是羅馬字；「第幾季」只有 `seasons[].name` 給得出來，比對主力是季名，別名只補充。
- split-cour 兩個 cour 之間可超過半年（2026-09-10 實測：進擊的巨人 S3 E12 播於 2018-10-15、E13 播於 2019-04-29，相隔 196 天）→ plan §4.4 的 180 天門檻同時切得出「虛擬季」與「同一季裡的 cour」。
- **字幕組編號習慣有四種且同一部並存**（2026-09-09 實測 7,833 筆）：每 cour 從 01 重算 68%、官方編號 16%、正篇序位 13%、季內連號 3%（第二 cour 從 13 接下去）。Dandadan 第二季同時有 `S01 | 01-24`、`[13-24]`、`S2 - 10`、`S2 - 20` 四種寫法。解析器不能假設編號一致。

**TheTVDB v4**（細節：[研究](anime-episode-source.md#203-thetvdb-v4)）

- 存取（2026-09-07 重查，原記載過度已更正）：v4 key **免費**自助申請（[KB#81](https://support.thetvdb.com/kb/faq.php?id=81)）；`/login` 的 `pin` **選填**，不帶可取 token 並讀資料（本機實測；[v4-api swagger](https://thetvdb.github.io/v4-api/)）。
- **授權是硬牆，模型未變**：key 須「commercial license 或 subscriptions enabled for end users」（[KB#62](https://support.thetvdb.com/kb/faq.php?id=62)）；user-supported 模式每位使用者 $12/年（[v4-api](https://github.com/thetvdb/v4-api)）；ToS 第 2 節 key "non-transferable"、"solely for the product or project…"（[tos](https://www.thetvdb.com/tos)）。→ 個人自用沒問題；**Berth 內建一把 key 給所有使用者靠執行寬鬆、隨時可能被關**；若採用走「使用者自己申請免費 key」。「每人自己申請一把免費 key」官方從未表態，**未證實**。
- Jellyfin 官方 TVDB 插件同形狀：內建 project key 加選填 subscriber's pin（[PluginConfiguration.cs](https://github.com/jellyfin/jellyfin-plugin-tvdb/blob/master/Jellyfin.Plugin.Tvdb/Configuration/PluginConfiguration.cs)）→ Jellyfin 媒體庫切 TVDB 刮削不需付費，§10「Jellyfin 同源」理由被削弱。
- 季類型 default(aired) / absolute / dvd / alternate / regional，**每部都有**（TMDB 的 Absolute group 要有人手動建）；Sonarr 只用 TVDB（經 Skyhook），靠 TheXEM 做 scene 編號（[xem-guide](https://wiki.servarr.com/sonarr/xem-guide)）。
- **`absolute` 把 OVA 與劇場版也編進去**（2026-09-09 實測 10 部）：SPY×FAMILY 劇場版佔掉 absolute 38，正篇第 38 集是 39；absolute ≠ 正篇第幾集，而字幕組「接著往下算」數的是正篇。
- 取資料要打兩次：`/series/{id}/extended` 只回 default order，絕對編號另打 `/series/{id}/episodes/absolute`（`page` 必填、每頁 100 筆），`absoluteNumber` 只在 `EpisodeBaseRecord`；[issue #98](https://github.com/thetvdb/v4-api/issues/98) 開了五年未做。（2026-09-08，swagger 4.7.10）

**Jellyfin 對絕對編號的支援**（2026-09-08 讀原始碼；細節：[研究](anime-episode-source.md#203-jellyfin-絕對編號skyhook-與-sonarr)）

- **Jellyfin 沒有「絕對編號」概念**：`EpisodeInfo` 只有 `EpisodeNumber` / `SeasonNumber`，沒有季資料夾時 `EpisodeResolver` 把季號設成 1。走 absolute 得把**整部劇**的 `Series.DisplayOrder` 設成 `absolute`（`tvshow.nfo` 的 `<displayorder>`，或 `POST /Items/{id}` 但會觸發整劇 FullRefresh + ReplaceAllMetadata）；jellyfin-plugin-tvdb 沒有任何排序設定。absolute + specials 目前壞的（[issue #91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91)，2023 起 open）。

**Sonarr Skyhook 不能寫進產品**：`https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdbId}` 免認證、有 `absoluteEpisodeNumber`，只適合當量測替身（10/10 與 thetvdb.com 一致）；封閉源、無文檔、無 SLA，servarr 政策 "We do not support directly hitting any metadata service that isn't our own"。

**Sonarr 作為先例**

- Series Type：Standard / Daily / Anime（絕對編號）；預設動漫命名含 `S{season:00}E{episode:00} - {absolute:000}`。（[settings](https://wiki.servarr.com/sonarr/settings)）v4 以 Custom Formats 取代 Preferred Words，Release Profiles 保留 must / must-not contain。
- EpisodeFile（帳本先例）欄位：`relativePath`、`path`、`size`、`dateAdded`、`sceneName`、`releaseGroup`、`language`、`quality`、`mediaInfo`、`qualityVersion`。（[starr sonarr](https://pkg.go.dev/golift.io/starr/sonarr)）**§8 的 `ledger` 至少要涵蓋這些。**

**動漫 ID 對應**（細節：[研究](anime-episode-source.md#203-動漫-id-對應)）

- **Fribb/anime-lists** `anime-list-full.json`：每筆含 `anidb_id` / `anilist_id` / `mal_id` / `kitsu_id` / `imdb_id` / `themoviedb_id` / `tvdb_id`，另有 `season` 與 `episode_offset`（`{tvdb, tmdb}`）。（[Fribb/anime-lists](https://github.com/Fribb/anime-lists)）**M5 票 23d 拿掉**：實測錯在季與 offset，見 [fribb-vs-chaining](fribb-vs-chaining-2026-10-28.md)、[agent-sources-ab](agent-sources-ab-2026-10-28.md)。
- Anime-Lists `anime-list.xml` 只有 AniDB→TVDB，無 TMDB；[anibridge-mappings](https://github.com/anibridge/anibridge-mappings) 目標是集級對應，可觀察。
- AutoBangumi v3.2 的 Episode Offset Auto-Detection 用 TMDB 各集 `air_date` 偵測虛擬季並建議 offset。（[autobangumi](https://www.autobangumi.org/en/feature/bangumi.html)）**§6.4 的絕對編號換算應同時用「累計集數」與「air_date 區間」兩種訊號。**
- Shoko + Shokofin（AniDB ED2K hash）自成生態、與 TMDB 路線不相容，不納入。

**動漫資料來源：AniList、Bangumi、Fribb**（2026-10-28 查證＋實測，M5 票 16；細節：[研究](anime-episode-source.md#203-動漫資料來源-anilist-bangumi-fribb)、[m5-anime-sources](m5-anime-sources-2026-10-28.md)）

**M5 票 23d 拿掉 Fribb 與 AniList 的標題搜尋、系列走圖**（[agent-sources-ab](agent-sources-ab-2026-10-28.md)）：Berth 只用 AniList 的季表（M5.5 票 14 起加上放送 `airingSchedules`）與 Bangumi 放送表；fixture 只剩 `tests/fixtures/http/{anilist,bgm}/`，`scripts/experiments/anime_sources.py` 錄的。

- **AniList**（`POST https://graphql.anilist.co`，免 key、不要求 User-Agent）：文件寫 90 次 / 分，頁首警告**目前降級成 30 次 / 分**（[Rate Limiting](https://docs.anilist.co/guide/rate-limiting)；實測 `X-RateLimit-Limit: 30`）；超過就**封一分鐘**，期間全回 429 帶 `Retry-After` 與 `X-RateLimit-Reset`，所以重試要全程序一起停。錯誤寫在 `errors`（錯參數回 400），`Page.media(id_in)` 問不存在的 id 回 200 加空清單；`Page` 一頁最多 50 筆（要 60 回 50）。條款（[Terms of Use](https://docs.anilist.co/guide/terms-of-use)）：月營收 < $150 免費；**禁止當備份 / 儲存服務、禁止 hoarding**，所以 Berth 只按需問、程序內快取 6 小時、不落地。`relations` 用 `relationType(version: 2)`。打分人數是 `stats.scoreDistribution[].amount` 加總。
- **Bangumi**（`GET https://api.bgm.tv/calendar`，免 key）：**非瀏覽器要帶 User-Agent（開發者 ID 與應用名，分發的帶版本、開源的帶主頁）**，預設的可能被擋（[user agent.md](https://github.com/bangumi/api/blob/master/docs-raw/user%20agent.md)）；Berth 送 `1morr/berth/<版本> (https://github.com/1morr/Berth)`。`/calendar` 在 `open-api/api.yml`（不在 `v0.yaml`），欄位全非必填（112 部裡 57 部有 `rank`、93 部有 `rating.score`）；回 `cache-control: max-age=3600`，Berth 記一小時；無公布速率上限。
- **Fribb**（`raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json`，7.5 MB、39,579 筆）：**倉庫無授權檔**，上游 anime-offline-database 為 **ODbL 1.0**；判讀（非法律意見）嚴格說保留所有權利，Berth 的結論是執行時下載到使用者自己的 `CONFIG_ROOT`、只自己查詢，**不打包進 repo 或 image**（那才是再散布），不加 ODbL 署名（無公開使用，§4.3）。每週二約 16:04 UTC 更新，下載會斷（要先解得開才換舊檔）；僅約兩成條目有 TMDB id；`episode_offset.tmdb` 差一集（Re:Zero 第 2 季寫 26，實際 E26–E38）。17 部實測見 [fribb-vs-chaining](fribb-vs-chaining-2026-10-28.md)：Fribb 錯在季與 offset，只靠集數串接錯在 Specials 與 TMDB 拆條目，所以 `download` 的整系列段兩種都算、不一致整季交給人（M5.6 起 skill 只寫通則）。

**放送時間表的來源**（2026-10-31 查證，M5.5 規劃，plan §11.6b）

- **AniList `AiringSchedule`**：`airingAt`、`timeUntilAiring`、`episode`、`mediaId`；官方註明**只保證未來的放送資料存在且準確**，所以不能拿它當「該入庫了沒」的基準。（[AiringSchedule](https://docs.anilist.co/reference/object/airingschedule)）
- **AutoBangumi Calendar**（v3.2 起）：只列已訂閱的作品，週一到週日加一欄「未知」，放送資料來自 Bangumi.tv，同一部作品多條規則合成一張。（[Calendar View](https://www.autobangumi.org/en/feature/calendar.html)）
- **TMDB `tv/on_the_air`**：未來 7 天會播的劇集，官方說它只是 discover 的包裝，要調條件就用 discover。（[On The Air](https://developer.themoviedb.org/reference/tv-series-on-the-air-list)）它不分類型（2026-11-04 實測 1703 筆、86 頁），時間表改用 discover。
- **時間表以 TMDB 為主幹【決定】**（2026-11-04 實測，M5.5 票 08；細節：[研究](schedule-sources-2026-11-04.md)，`scripts/experiments/schedule_sources.py`）：
  - 條件：`discover/tv`，`with_genres=16`、`with_original_language=ja|zh`，`air_date.gte` 為週一前一天、`air_date.lte` 為週日後一天。實驗另帶 `language=zh-CN`，只為了對 Bangumi 的中文名；時間表的語言照 plan §8.3。`air_date.*` 官方沒寫篩什麼（[Discover TV](https://developer.themoviedb.org/reference/discover-tv)），實測是「這段期間有一集播出」。放寬一天是因為深夜檔兩邊常差一天。
  - 覆蓋率：分母是 Bangumi 放送表上 Bangumi 說這一週有一集的日本作品（只算日本，使用者定）。2026-11-02 那一週 71/76 = 93.4%，上一週 69/76 = 90.8%；不放寬是 92.1% / 89.5%（上一週靠放寬一天才過線，結論在線邊，換季要重量）。不分產地是 88.4% / 84.1%。
  - 漏掉的作品（這一週）：猫猫のひとりごと 第3期、ミニアニメ「ホタルの嫁入り」ちょいたし、ダークサモナーとデキている ミニアニメ劇場（三部 WEB 迷你動畫，TMDB 沒有或只有本篇），シルバニアファミリー フレアのカラフル・エブリデイ（兒童，TMDB 查不到），ぷにるんず ぷに４（TMDB 的集停在 2025-12-27）。上一週另漏歯ならび～ズ（WEB 短篇）、凶乱令嬢 ニア・リストンミニ（WEB 迷你動畫）。沒有一般的深夜番。
  - 反方向：這一週 164 部裡 85 部不在 Bangumi 放送表上（國產 65、日本 20，日本的是長壽 / 兒童節目與夏季開播仍在播的作品）。Bangumi 放送表本身也不完整，它是對照、不是正解。
  - discover 的每筆沒有集與播出日：要放進週幾的欄、寫第幾集，每部再讀 `tv/{id}` 的 `last_episode_to_air` / `next_episode_to_air`。
  - **第二層：時刻與評分**（2026-11-04 實測，M5.5 票 14；細節：[研究](schedule-mapping-2026-11-04.md)，`scripts/experiments/schedule_mapping.py`）：
    - 時刻：AniList `Page(page, perPage: 50){pageInfo{hasNextPage} airingSchedules(airingAt_greater, airingAt_lesser, sort: TIME){airingAt episode media{id isAdult title{native}}}}`，`airingAt` 是 Unix 秒。一週（日本時間的週一前一天 00:00 到週日後兩天 00:00）三頁、117 部；過去的也回，Berth 只顯示未來的。fixture `tests/fixtures/http/anilist/airing.week-2026-11-02.json`。評分：Bangumi `/calendar` 的 `rating.score` 與 `total`，名字是 HTML 跳脫過的（`&amp;`）。
    - **對應【決定】**：TMDB `original_name` 與 AniList `title.native`、Bangumi `name` 壓平後（NFKC、不分大小寫、只留字母與數字）完全相同才算同一部；時刻另外要日本日期與 TMDB 播出日差一天以內；評分另外要 Bangumi 條目的開播日與卡片那一季的開播日（`seasons[].air_date`）差一天以內（TMDB 多季併一部、Bangumi 一季一條，否則續作會掛上第一季的分數；這一週 48 部全在一天以內），沒有日期就不顯示。同名不只一部就不顯示。這一週日本作品的卡片 AniList 對到 57.0%、Bangumi 51.6%，對不到的多半是續作（一季一條、名字帶「第2期」）。
    - Wikidata（`tv/{id}` 的 `external_ids.wikidata_id` → P8729 AniList、P5732 Bangumi）只對到 46.2% / 16.1%：Wikidata 多半只記第一季的 id。與標題都對到的 52 部 0 件不一致，只多 6 部，不接。
    - 標準庫 `urllib` 預設的 User-Agent 打 AniList 被 Cloudflare 擋（403、`error code: 1010`），帶一個 User-Agent 就過。
  - 回應形狀（票 08 錄下、票 09 做成 fixture `tests/fixtures/http/tmdb/discover-tv.airing.json` 與 `tv-detail.luo-xiao-hei.zh-cn.json`）：discover 帶 `page`、`total_pages`、`total_results`，每筆沒有 `media_type`；`last_episode_to_air` / `next_episode_to_air` 與季詳情的 `episodes[]` 同一種形狀（`season_number`、`episode_number`、`air_date`、`runtime`，未播的 `runtime` 是 `null`），完結的作品 `next_episode_to_air` 是 `null`。

**Seerr（前 Jellyseerr / Overseerr）**（細節：[研究](anime-episode-source.md#203-seerr)）

- 2026 年 3 月起 Jellyseerr 與 Overseerr 合併為 **Seerr**（[seerr-release](https://docs.seerr.dev/blog/seerr-release)）；本文件所有「Seerr」指它。以 Jellyfin / Emby / Plex 帳號登入，第一個以媒體伺服器管理員登入者成為 owner，權限為細粒度旗標（[users](https://docs.seerr.dev/using-seerr/settings/users)）。
- 可用性判定（來源碼 `server/lib/scanners/jellyfin/index.ts`）：`ProviderIds.Tmdb`，缺則 `Imdb` → TMDB find，再缺則 `AniDB` → 內建 anime-list。§9 認領 unmanaged 檔案可沿用這條鏈。
- 深連結（`server/entity/Media.ts`）：`{externalUrl}/web/index.html#!/details?id={itemId}&context=home&serverId={serverId}`。§12 採用此格式。

### 20.4 解析先例與真實 torrent 內容

細節與逐字原文在 [research/profile-effect.md](profile-effect.md#從-brief-搬來204)（本檔 §6.4 絕對編號量測見同檔 [§0](profile-effect.md#0-結論)、[§6.1.1](profile-effect.md#611-規則-1-的代價m1-票-14d-第-1-步2026-09-17)）。

**解析庫現況（2026-09）**：guessit（Python，v4.4.0，2026-07）欄位最完整但 CJK 弱（[#929](https://github.com/guessit-io/guessit/issues/929) 仍開著，fansub 括號格式常錯）；anitopy（2022 停滯）、anitomy（C++，重寫中）、anitomyscript（2019，落後）無 CJK 專門處理；[@ctrl/video-filename-parser](https://github.com/scttcper/video-filename-parser)（TS，v5.11，Radarr 風格）、parse-torrent-title（JS）、[PTT](https://github.com/dreulavelle/PTT)（pip `parsett`）、torrent-name-parser（Rust，2023 停滯）都只管西方 scene 命名。

**結論**：沒有現成庫能處理中文字幕組命名，CJK 詞典一定要自己維護；西方命名交給 guessit（Python）或 @ctrl/video-filename-parser（TS）。可直接借鑑的 CJK regex 有兩處：

- **AutoBangumi `backend/src/module/parser/analyser/tokenizer/classic.py`**（[repo](https://github.com/EstrellaXD/Auto_Bangumi)）：字幕標記、季 / 集（含中文數字）、合集 / 特典、番外、劇場版、★前綴、招募廣告、僅限港澳台、來源（Baha / B-Global / Bilibili / CR / AT-X / Abema / AMZN / NF…）、codec、audio 的 regex（`_CJK_SUBTITLE_TAG`、`_SUBTITLE`、`_CHINESE_SEASON`、`_CHINESE_EPISODE`、`_FULL_COLLECTION` / `_COLLECTION`、`_SPECIAL_CJK`、`_MOVIE_CJK`、`_PREFIX`、`_RECRUIT`、`_REGION`、`_SOURCE`、`_CODEC`、`_AUDIO`）。
- **Sonarr `Parser.cs`**（[raw](https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/NzbDrone.Core/Parser/Parser.cs)）：約 8 條中文動漫 pre-substitution（LoliHouse / Lilith-Raws / Skymoon-Raws 無括號、GM-Team 多括號、`第?(\d+)(话|集)?( END|完| Fin)?`），以及韓劇 `\.E(\d{2,4})\.\d{6}\.(.*-NEXT)$ → S01E$1`。

**AutoBangumi 現況（main，2026-08）**：

- 解析輸出 `ParsedRelease`（title_en / zh / jp、group、season、episode、episode_end、media_type、release_kind(SINGLE|RANGE|BATCH|COLLECTION)、resolution、source、subtitle、codecs、audio、version、tags、evidence）；§6.3 的欄位設計與此對齊。
- LLM 解析支援 OpenAI / Anthropic / Gemini，`primary` 與 `fallback` 兩種模式（記憶體快取、斷路器、併發上限）；§6.10 與其 `fallback` 一致，並多加 schema 驗證與防護上限（ADR 0016 不設月預算）。
- `offset_detector.py`：以 TMDB 各集 `air_date`、播出間隔 > 6 個月切「虛擬季」算 season_offset / episode_offset。
- 明確限制：**不支援合集 / 批次**、OVA 與電影 RSS 不支援、路徑必須是 `Title/Season X/`——正是 §6.6 要超越的地方。
- RSS 預設過濾 regex `720|\d+-\d+`；建議一部作品只訂一個字幕組；§15 的 Rule 預設沿用「排除合集、字幕組白名單」。

**真實內容樣本**（現場列表，benchmark v0 的種子；v0 語料 20 筆 = 動漫 8、非動漫劇集 8、電影 4，清單與逐字原文在 [研究檔](profile-effect.md#從-brief-搬來204)「真實內容樣本」，逐筆出處在 `tests/fixtures/parser/README.md`）：

- 單集：Erai-raws `- 07 [1080p NF WEB-DL AVC AAC][MultiSub][A5D38B89]`；三明治摆烂组同集三個 torrent（`[繁日内嵌]`、`[简日内嵌]`、`[简繁日内封]`，內嵌 vs 內封）；楓葉字幕組 `[089][繁體][1080P][MP4]`；悠哈璃羽字幕社 `S2_…[x264 1080p][CHT]`；DHR Fansub `[04][JPN&BIG5][720P][AVC_Hi10P_AAC][MKV]`；LoliHouse `- 81 v2 WebRip 1080p HEVC-10bit AAC`。
- 合集 / BD：7³ACG `S01 | 01-28+SPx11`、`S01 | 01-26+SPx1`；`★百姓贵族★29~40(完)★1920x1080★`（`★` 分隔、`完` 標記）；`jibaketa TVB … S1 S2 S3 BD`（多季合一）；`Solo Leveling S01 + S02 BDRIP`。
- 外掛字幕：`sub/…第01話(DVD 640x480).gb.ass` / `.big5.ass`；`[十二国记]…tc.ass`；Mikan 的「生肉 / 不明字幕」標記。
- 西方劇集：RARBG 季包 `Show/Subs/Episode 1/2_English.srt`（[renamer README](https://github.com/img02/Rarbg-Subtitle-Renamer)）；Sonarr Daily 型 `Some.Daily.Show.2021.03.04.1080p.HDTV.x264-GROUP`；`S01E01E02` 多集檔。
- 電影：`Oppenheimer (2023) [1080p] [BluRay] [5.1] [YTS.MX]/…mp4` + `www.YTS.MX.jpg` + `YTSProxies.com.txt`；Jellyfin 多片段 `Movie Name-cd1.mkv`（parttype：cd/dvd/part/pt/disc/disk）。
- 韓劇：`Show.E01.YYMMDD.1080p…-NEXT` 無季編號（Sonarr 特別處理），`E01-16 COMPLETE (HDTV NEXT)` 全季字幕包。
- **已證實（2026-09-10，M1 票 05，抓真實 torrent metadata）**：BD 包附屬資料夾名兩家不同，成了 §6.9 的語料（`tests/fixtures/parser/`）。
  - [VCB-Studio 魔王2099](https://share.dmhy.org/topics/view/726629_VCB-Studio_2099_Demon_Lord_2099_10-bit_1080p_HEVC_BDRip_Fin.html)（223 檔）：`SPs/`、`CDs/`（每碟一子資料夾，flac + webp）、`CDs/…/Scans/`、`Scans/`；**沒有** `Fonts/` 與 `Menu/`。
  - [DBD-Raws 不死者之王 第二季](https://share.dmhy.org/topics/view/668157_DBD-Raws_Overlord_Overlord_S2_01-13TV_SP_1080P_BDRip_HEVC-10bit_FLAC_MKV.html)（106 檔）：`SP/`（帶編號，各配 `.sc.ass` / `.tc.ass`）、`PV/`、`NCOP&NCED/`、`menu/`（小寫）、`Fonts/Fonts.zip`（壓縮檔不是散檔）。

**只有集號、TMDB 上多季的真實發佈（2026-09-16，M1 票 14c，[研究](profile-effect.md#0-結論)）**：§6.4「只有集號 → 絕對編號」在 v1 的 23 筆語料上一次都沒走到（34 次全是 TMDB 只有一季），補 5 筆走得到的才量得出 Route profile 的作用。

- **動漫跨季連號換算得對**：SubsPlease `Spy x Family - 26`–`37`、`Boku no Hero Academia - 139`、Erai-raws `One Piece - 1089 ~ 1104`；TMDB 航海王第 22 季沿用官方集數當 `episode_number`（S22E1089–1155），所以只有 absolute group 換對，各季累加換成 S22E01 是錯的。
- **非動漫的「集號」可能是另一套數法**：《Home and Away》`Episode.8214.2024-02-29` 累加換成 S37E32，TMDB 的 S37E39 才是 `Episode 8214`（TMDB 前 36 季比官方多收 7 集）；`The.Return.of.Superman.E079.150524` 換成 S03E21 是對的。**「是不是動漫」預測不了換算對錯**（ADR 0003 移除 Route profile 的依據，見研究檔 §0）。
- **字幕組每 cour 重數、篇章名只寫羅馬字會被當絕對編號**：Erai-raws `Bleach - Sennen Kessen Hen - Soukoku Tan - 01 ~ 14` 換成 S01E01–14，正解 S02E27–40。
- **`guessit` 預設把韓國電視台 `YYMMDD` 讀錯**：`150524` 讀成 2024-05-15（本機實測），要加 `date_year_first`（[guessit 文件](https://guessit-io.github.io/guessit) `-Y, --date-year-first`）；加上後讀成 2015-05-24，四位數年份不受影響。
- 韓劇第二季以後、檔名沒有季號的 `Show.2.E01.YYMMDD` 在 TPB、Knaben、dmhy 都沒找到，第二季發佈全部帶 `S02E`。
- **「集號 ≤ 第一季集數就送審核」擋下的多半是對的**（2026-09-17，M1 票 14d，[研究 §6.1.1](profile-effect.md#611-規則-1-的代價m1-票-14d-第-1-步2026-09-17)，`scripts/experiments/absolute_rule_cost.py`）：5 部 ≥ 2 季的 Mikan 發佈走到絕對編號換算的檔案裡，集號 ≤ 第一季集數的**正解在第一季 928 個、在後面某季 167 個**；超過的 1,219 對、54 錯（錯的全是播出日對不上、退回序位，本身存疑）。「標題有認不出的多餘字」分不開兩者（連 TMDB `titles` 比放行 793 個第一季、漏 14 個後面季；只比三個主標題放行 328 個不漏，但英文標題同寫法的作品會入錯），故維持原形。限制：Mikan 只有標題沒有檔名、樣本以中文字幕組與動漫為主。

**Jellyfin 動漫命名的社群痛點**：

- One Piece / Detective Conan 這類長篇的 TVDB arc 順序 vs 絕對編號長期無解（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1sny587/one_piece_tvdb_arc_order_vs_absolute_episode)、[tvdb-plugin#91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91)）；本系統只承諾「與 TMDB 一致」，不承諾符合任何社群偏好。
- Split-cour 被 Jellyfin 併成一季的抱怨很多（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1r5sk02/any_way_to_have_anime_seasons_shown_in_parts_like)）；本系統不對抗 provider，只做正確對應。
- Sonarr FAQ 承認 Bleach TYBW 這類新 arc 只有編號與 TVDB 對上才自動匹配。

**mediainfo（pymediainfo 7.0.1，2026-09-11 對真檔案實測）**：

- `pip install pymediainfo` 的 wheel **內含 libmediainfo**，不需系統套件（[README](https://github.com/sbraz/pymediainfo)）。
- `MediaInfo.parse(path)` 回 track 清單，`track.to_data()` 是該條所有欄位。**同一個 `duration` 型別不同**：General 是整數毫秒（`2023`），Video 是字串（`"2000.000000"`）。
- 布林是字串 `"Yes"` / `"No"`（`forced`、`default`）；語言兩碼（`ja` / `en` / `zh`），`other_language` 另有別名；繁簡分不出來，字幕軌繁簡只寫在 `title`（與 §20.1 的 Jellyfin 同一限制）。
- 讀得完但不是媒體的檔案（如 `.txt`）**不丟例外**，回只有 General 的清單——所以「有沒有影像軌」才是「是不是影片」的判準。
- 證據：`tests/fixtures/mediainfo/two-second-episode.mkv`、`tests/unit/test_mediainfo.py`。

### 20.5 名稱衝突檢查

以 tavily basic 搜尋 GitHub / npm / PyPI / Docker Hub / App Store，非窮盡商標檢索。完整比對表在 [`docs/research/name-conflict-check.md`](name-conflict-check.md#205-名稱衝突檢查)。

- **Berth：可用（已定案）**。精確比對（2026-09-07）：GitHub 無同領域專案，最接近的是 macOS SSH 客戶端 xinghelee/Berth（31★）；PyPI `berth` 是 2017 年停更的打包工具；npm `berth` 已標記 deprecated；Docker Hub 有 `berth/` 組織（舊 OpenStack 容器化專案，已停）。本系統以 `ghcr.io/<owner>/berth` 發佈，不需要這三個註冊名。
- 備選名稱：Lading、Cleat、Longshore、Mooring、Keelhaul 可用；Wharf、Gangway、Drayage 輕微衝突；Dockhand（5.8k★ 自託管 Docker 管理工具）、Stow、Quay、Tally、Stevedore **衝突**。

### 20.6 實作前必做的實驗【研究】

**已完成（2026-09-07，票 04）**。完整結果與量測方式在 [`docs/research/m0-experiments.md`](m0-experiments.md)，腳本在 `scripts/experiments/`，可重跑；brief 原記載的逐條清單在同檔 [〈從 brief 搬來（§20.6）〉](m0-experiments.md#從-brief-搬來206)。結論與尚未完成的項目：

- **硬鏈接通過**（`hardlink.sh`）：NTFS 9p bind mount 與 ext4 bind mount 皆 nlink=2、inode 相同；分成兩個 volume 回 `Cross-device link` 並退出 1。但 ext4 那一輪跑的是 Docker Desktop 自己的 Linux VM（`docker-desktop` 發行版），不是另一台實體 Linux 宿主。原生 Linux 已在 2026-10-09 跑過（M4 票 42，§20.14）；Unraid 7.1.4 user share 已在 2026-10-08 跑過（M4 票 55，§20.14）。**剩下：至少一台 NAS**（Synology / QNAP / TrueNAS 其一），`sh hardlink.sh /volume1/<share>` 即可。
- 標籤含中文：12.x 已實測是純 tag（`docs/research/jellyfin-12.md`），見 §20.1「多版本」。
- qBittorrent 4.4 與 5.x 參數相容：完成，見 §20.7「qBittorrent 版本矩陣」。`WebUI\ServerDomains=qbittorrent` 足以通過 Host 檢查，但使用者從 `localhost:8080` 進不了 WebUI，所以維持不預置（§20.7、plan §9.2）。Prowlarr `config/host` Forms 帳密欄位名：完成，見 §20.7「Prowlarr」。
- Jellyfin 10.10/10.11 命名實測：完成，見 §20.7「Jellyfin 命名實測」。§7.2 電影範例與 §7.7 版本標籤說法已據此更正；plan §5 的模板凍結。
- Mikan / Nyaa 實際 RSS 擴充欄位（infoHash、大小、做種數、enclosure、發佈時間）：完成（2026-09-25，M3 票 07，含 acg.rip），見 §20.12。
- **未完成**：建立 20 筆真實 torrent fixture（動漫 8、美劇/韓劇 8、電影 4）作為 benchmark v0 → M1 解析器票。
- 字幕組編號換算失敗率：完成（2026-09-09，M1 票 01）。7,833 筆真實釋出，TMDB 8.0% / TVDB aired 7.6% / TVDB absolute 7.6%；§10 的【研究】據此結案為**維持 TMDB**。方法與結果在 [`docs/research/anime-episode-source.md`](anime-episode-source.md)，腳本 `scripts/experiments/anime_episode_source.py`。順帶推翻兩件事：§20.3 合併政策比原記載更激進（TMDB 連獨立的連續季也併，咒術 3 季→1 季、Re:Zero 4 季→1 季）；**TVDB absolute 會把 OVA 與劇場版也編號**（SPY×FAMILY 的 CODE: White 佔掉 absolute 38），所以 absolute ≠ 正篇第幾集。

### 20.27 地上波先行配信與 TMDB 的播出日（2026-11-01 查證，審核佇列調查）

細節在 [`docs/research/review-queue-2026-11-01.md`](review-queue-2026-11-01.md)。

- **TMDB 記的是電視台的日期，字幕組常從更早的平台取片**：2026 秋季的 ABEMA「地上波 1 週間先行」有 [転生したら剣でしたII](https://prtimes.jp/main/html/rd/p/000004053.000064643.html)、[転生した大聖女](https://prtimes.jp/main/html/rd/p/000004029.000064643.html)、[転生ゴブリン](https://prtimes.jp/main/html/rd/p/000004076.000064643.html)，[野生のラスボス第 2 期](https://gamebiz.jp/news/433310)同樣先行 1 週。
- **正式環境量到發佈比 TMDB 早 4–8 天**（5 部 16 集）：深夜檔的 TMDB 日期常再晚一天，所以先行一週會量到 8 天。裝備仔早 4–5 天，沒有查到官方的先行公告。
- **所以「發佈早於播出日超過兩天就一定算錯」不成立**（§20.11 的規則一、`parser/airing.py`）：照字面的讀法會被誤擋。改法在 plan §11.6b（2026-11-01 使用者定），M5.5 票 04 落地：照字面容忍九天、有換算的維持兩天（plan §4.4）；超過九天被擋的照字面列另記理由，「平台先行的核准就好」只對早不超過十四天的說，更早的叫人先查作品與 TMDB 的日期（票 04b：只對照字面說是使用者 2026-11-04 定；十四天上限是協調者同日追加，取量到的最大 8 天加約一週餘裕，沒有更長的先行樣本）。16 列做成 fixture `tests/fixtures/airing/simulcast-2026-fall.json`；2026-11-04 重查時 TMDB 已把野生的大魔王的日期改成 ABEMA 的日期，TMDB 的播出日本身也會移動。

### 20.28 只有一季的作品：整季缺時不接季記號（2026-11-07 實測，M5.6 票 02）

腳本 `scripts/experiments/single_season_marks.py`，本機 Prowlarr（Mikan、dmhy、ACG.RIP、Anime Tosho、The Pirate Bay、YTS；**Nyaa 連不上**，DNS／SSL，與 §20.21 同一個狀況）。逐查詢數每一站的總筆數與**發佈名含作品名字**的筆數（The Pirate Bay 對查不到的字回熱門清單，純筆數會騙人），以及名字對得上的那些自己寫了哪一種季記號。原始 JSON 在 `.local/experiments/results/single_season_marks.json`。

| 作品 | 查詢 | 動畫站名字對得上的筆數 | 說明 |
| --- | --- | --- | --- |
| 私を喰べたい、ひとでなし（只有一季） | `私を喰べたい、ひとでなし 第1季` | Mikan、dmhy、ACG.RIP、Anime Tosho **0** | 只剩 The Pirate Bay 100、YTS 116 筆，名字對得上 0 |
| 同上 | `私を喰べたい、ひとでなし` | Mikan 114、dmhy 80、ACG.RIP 30 | 全部對得上，**沒有一筆寫季記號** |
| 同上（中文名） | `想吃掉我的非人少女 第1季` | **0** | 同上 |
| 同上（中文名） | `想吃掉我的非人少女` | Mikan 138、dmhy 80、ACG.RIP 30 | 全部對得上 |
| Death Note（只有一季，拉丁字） | `Death Note S01` | Mikan、dmhy、ACG.RIP **0**；Anime Tosho 43 | Anime Tosho 寬鬆比對，43 筆裡只有 12 筆真寫 `S01` |
| 同上 | `Death Note Season 1` | 動畫站 **0**；Anime Tosho 6 | |
| 同上 | `Death Note` | Mikan 13、dmhy 27、ACG.RIP 21、Anime Tosho 95 | |
| 進撃の巨人（多季對照，CJK） | `進撃の巨人 第1季` | dmhy 18；Mikan **0** | 第 1 季的記號在 dmhy 問得到 |
| 同上 | `進撃の巨人` | Mikan 78、dmhy 80 | 混著各季（Anime Tosho 的 100 筆裡 38 筆寫別季） |
| SPY x FAMILY（多季對照，拉丁字） | `SPY x FAMILY S01` | Mikan、dmhy **各 1** | `S01` 幾乎沒有站用 |
| 同上 | `SPY x FAMILY Season 1` | Mikan 181（**沒有一筆真寫 `Season 1`**，Mikan 是寬鬆比對）；Anime Tosho 39 筆真寫 `Season 1` | 與 §20.21 一致：動畫站寫 `Season N` |
| 同上 | `SPY x FAMILY` | Mikan 949 | 混著各季 |

- **只有一季的作品，發佈名不寫季記號**：Mikan、dmhy、ACG.RIP 對「名字 第1季」／`S01`／`Season 1` 一筆都不回，名字本身則整季都回得來。所以整季缺時問**名字本身**（`services/search_queries.missing_batches` 的 `single_season`），特別篇（`S00`）照舊接記號。
- **多季作品照舊**：第 1 季的記號在 dmhy（CJK）問得到 18 筆，`Season N` 在 Anime Tosho 有 39 筆真寫；不接記號的名字會混進其他季，也會多吃 `MAX_QUERIES` 的配額。
- **殘留**：多季 CJK 作品在 Mikan 對 `第1季` 零筆（`進撃の巨人 第1季`）。這張票只修只有一季的作品；要補的話是「第 1 季另送不帶記號的名字」那一種修法，會把其他季的發佈一起撈進來。
- **量測的限制**：Prowlarr 的 REST 搜尋只回結果列、不回逐站成敗，所以「某站掛掉」與「某站 0 筆」在表上長得一樣；Nyaa 是從 Prowlarr 的 log（`Unable to connect to indexer`）與直接 curl 判定的。
- The Pirate Bay、YTS 對查不到的查詢回一整頁無關結果（表上名字對得上 0 筆）——另一個問題，這個里程碑不修。

### 20.29 以作品訂閱時選不出「第幾季」（2026-11-07 實測，M5.6 票 11）

`rss.subscribe` 只收作品的 `media_id` 與字幕組，伺服器用 `services.bangumi.match_bangumi` 拿作品的 **`first_air_date`** 比對 Mikan 番組頁的開播日（設計在 plan §6〈agent〉與 M5.6 票 08 的 Comments）。同一部作品在 TMDB 只有一個條目、Mikan 卻每季各一頁時，首播年對到的是第一季那一頁。

實測（真 TMDB、真 Mikan、DeepSeek `deepseek-flash`，兩種接口各一次，逐字稿在 `.local/experiments/results/m5_acceptance/after-core/` 的 `{anthropic,openai}-S1.md` 與 `anthropic-S6.md`）：

| 情境 | 推薦的作品 | 伺服器挑到的番組 | 後果 |
| --- | --- | --- | --- |
| S1 | 《黑色五葉草 第二季》（`tv:73223`，2017 起的同一個 TMDB 條目，Season 2 在 2026） | Mikan 2017 年那一個（bangumi 1433） | 卡片列第一季的字幕組；按下確認後 backfill 送出 **100 筆** 2017–2021 的舊集 |
| S6 | 《葬送的芙莉蓮 第二季》（TMDB 併進 Season 1 的 E29–E38） | Mikan 第一季的番組 | backfill 送出 **39 筆** S1 種子（同一集還有三種字幕變體） |

模型兩個情境都自己發現（比對集數與發佈日）、刪掉訂閱並說明，但已經送進 qBittorrent 的送單要人清。基準（M5.6 之前）不會這樣：那時模型自己搜 Bangumi、自己挑番組 id。

修法方向（未實作，排 M6 第一張票）：訂閱帶上「第幾季」，或把比對用的日期從作品首播日改成**使用者被推薦的那一季**的開播日（`media.read_media` 的季表每一季都有 `air_date`）。兩者都要處理「Mikan 把 split-cour 拆成兩頁」與「Mikan 的頁比 TMDB 的季粗」的情形；決定前先對 Mikan 的實頁再量一次。
