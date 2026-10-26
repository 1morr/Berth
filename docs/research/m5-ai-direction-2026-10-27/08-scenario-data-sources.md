# 08 對話情境的資料來源與可行性

查證日期 2026-10-27（除非另註）。commit `5fc0bbc8`（v0.3.0 之後）。唯讀研究，沒有改程式碼。名詞照 `CONTEXT.md`。
已查過的事實不重查：brief §20.3（TMDB schema、split-cour 併季、episode group 的絕對編號）、§20.4（字幕組命名先例）、§20.12（RSS 欄位）、§20.21（季記號 `Season N` vs `SNN`）、`docs/research/anime-episode-source.md`、`docs/research/rss-sources.md`。本檔只補新的。

**環境限制**：repo 設定與環境變數裡沒有 TMDB key（`.env` 不存在），所以 TMDB 的資料是兩種來源湊的：(a) 網頁 themoviedb.org 的現況（WebFetch，2026-10-27）；(b) repo 內已凍結的 API 快照 `tests/fixtures/tmdb/tv-65942.json`（Berth 自己的 `refresh_media` 路徑錄的）。**TMDB discover / recommendations / keywords / collection 端點沒有實打**，參數清單來自官方 OpenAPI（本檔 §1.1）。AniList、Bangumi、Fribb 是實打 / 實下載。Jikan 從本機連線失敗（`SSL_ERROR_SYSCALL`），只有文件。

---

## 0. 結論先行

1. **「推薦新番」用 AniList + TMDB 組合最合理，不要押單一來源。** 動漫的「這季有什麼」AniList（`season` + `seasonYear` 篩選、`popularity`、`averageScore`）最直接、免 key；Bangumi `/calendar` 免 key 且有中文評分，但本週 113 部裡 46 部不到 20 票（見 §2.2）。TMDB 擅長一般劇集，動漫只能靠 `with_genres=16` + `with_original_language=ja` + anime keyword `210024` 組合篩。
2. **「完整系列清單」的最佳鏈是 AniList relations 走圖 → Fribb anime-lists 對應到 TMDB tv id + 季 + `episode_offset`。** Re:Zero 實測：從 TV 第一季 id 21355 走 12 次 GraphQL 呼叫就列出 12 個 AniList 條目（含 TV 四季、兩個 part 的分割、五部 Break Time ONA/短篇、OVA），Fribb 的 `episode_offset.tmdb` = 26 / 38 / 50 / 66 正好等於 TMDB 合併成單季後各輪的起始集減一。這條鏈直接給出「字幕組絕對編號 → TMDB `S01Exx`」的換算依據，與 Berth 現有 `parser` 的虛擬季方法互相驗證。
3. **劇場版 / OVA 在三個來源的歸屬互相不一致**（TMDB：獨立 movie + 一個 collection；AniList：OVA 格式；Fribb：把 OVA 對到 TMDB tv 的 Season 0；Bangumi：OVA 平台 + 「番外篇」關聯）。Re:Zero 的 Memory Snow / Frozen Bond 是最好的實例（§1.3）。**結論：確認卡必須逐個 TMDB id 分開建，不能一張卡包整個系列。**
4. **TMDB 現況：Re:Zero 只有 `Specials`（90 集）與 `Season 1`（85 集）兩季**，S2–S4 全併進 S1（E1–E85）；episode group 有四個，但 Absolute 那個（`season4`）是空的（0 集），Production 的 `Seasons` 有 5 組 170 集。所以「TMDB 的季」不能當作「使用者說的第幾季」，系列清單一定要自己組。
5. **網路搜尋工具：對自託管用戶最省事的是 Anthropic 的 server-side `web_search`**（同一把 Anthropic key、免新帳號、$10 / 1,000 次搜尋，支援 `allowed_domains`），但綁定 Anthropic provider；要 provider 無關就加一個可選的 Tavily（1,000 credit 免費/月）或 SearXNG（自架、零費用、但 JSON 要手動開、穩定度差）。
6. **Trakt、IMDb、豆瓣都不適合當預設來源**：Trakt 建 app 的門檻 2026 年變了（見 §3.1），IMDb 無免費 API（只有非商業 dataset），豆瓣沒有公開 API。
7. **情境 1 / 2 技術上可行，但缺口集中在兩處**：(a) Berth 的 TMDB adapter 只有 trending / popular / search / detail / season / episode_group / configuration，沒有 discover、recommendations、collection、keywords、find；(b) 「一次下載整個系列」要把多個作品拆成多張確認卡、多個 Route 決定、多個 torrent 選擇——這是 UX 風險不是技術風險。
8. **所有「進流程」的動作 Berth 現有命令都夠**（`rss.subscribe_mikan`、`rss.subscribe_search`、`jobs.add_download`、`search.search_torrents`、`bangumi.search_bangumi`），缺的是讀取面的外部資料工具（TMDB discover / AniList / 網搜），不是寫入面。

---

## 1. TMDB API 能給推薦與系列清單用的什麼

### 1.1 端點與參數（官方 OpenAPI，2026-10-27 抓）

來源：`https://developer.themoviedb.org/reference/<slug>.md` 的 OpenAPI 區塊（最後更新 2025-10-01）。

| 端點 | 參數 | 用在 |
| --- | --- | --- |
| `GET /3/trending/tv/{day\|week}` | `language` | Berth 已有（week） |
| `GET /3/discover/tv` | `air_date.gte/lte`、`first_air_date.gte/lte`、`first_air_date_year`、`with_genres`、`without_genres`、`with_keywords`、`without_keywords`、`with_original_language`、`with_origin_country`、`with_status`、`with_type`、`with_networks`、`with_companies`、`vote_average.gte/lte`、`vote_count.gte/lte`、`with_runtime.*`、`watch_region`、`with_watch_providers`、`with_watch_monetization_types`、`sort_by`、`timezone`、`include_null_first_air_dates`、`page`、`language` | 新番篩選（見下）|
| `GET /3/tv/on_the_air` | | 官方註明「其實就是 discover」，預設 `sort_by=popularity.desc`、`air_date` 區間為未來 7 天 |
| `GET /3/tv/{id}/recommendations`、`/similar` | `language`、`page` | 「喜歡 X 的人也看」；similar 是 genre + keyword 比對 |
| `GET /3/tv/{id}/keywords` | | 取 anime keyword |
| `GET /3/tv/{id}/watch/providers` | | 依國家列出串流平台（JustWatch 提供，**必須標示 JustWatch**，違反會被撤銷 API 存取）|
| `GET /3/tv/{id}/episode_groups`、`GET /3/tv/episode_group/{id}` | | Berth 已用後者 |
| `GET /3/collection/{id}` | `language` | 電影系列（`parts[]`）|
| `GET /3/find/{external_id}`、`/tv/{id}/external_ids` | | 與 IMDb / TVDB 互查 |

- AND / OR：逗號 = AND，管線 `|` = OR（discover 文件原文）。
- **動漫篩法**：TMDB 沒有 anime genre，社群標準做法是 Animation genre `16` 加 anime keyword。keyword id **`210024` = "anime"**（2026-10-27 WebFetch `themoviedb.org/keyword/210024-anime` 確認名稱與 id，電影端 2,544 筆，也有 TV 分頁）。論壇舊貼文建議同一組合（[TMDB Talk](https://www.themoviedb.org/talk/628b76ac5cea184d122c137e)）。建議的新番查詢草稿（**未實打**）：`discover/tv?with_genres=16&with_keywords=210024&with_original_language=ja&first_air_date.gte=<季初>&first_air_date.lte=<季末>&sort_by=popularity.desc&vote_count.gte=<N>`。
- Re:Zero 的 TMDB 頁（2026-10-27）顯示 21 個 keyword，包含 `anime`、`isekai`、`based on light novel`——證明 keyword 有被標，但標得夠不夠全靠社群，新作品可能還沒人補。
- 速率：官方文件寫舊限制 2019-12-16 已停用，「仍有上限，約 40 req/s 量級，會變動，遵守 429」（[rate-limiting](https://developer.themoviedb.org/docs/rate-limiting)）。brief §20.3 引的論壇數字是 50 req/s，量級相同。對話 agent 的使用量遠低於此。

### 1.2 評分可靠度

- TMDB 回的是 `vote_average` 與 `vote_count`，沒有最低票數保證。**新番剛播時票數很少**，`vote_average` 會被個位數票數拉到極端值，所以要用 `vote_count.gte` 過濾，或乾脆不用評分排序，改用 `popularity.desc`。
- 但 `popularity` 也不能當排序依據：brief §20.3（2026-09-09 實測）已記載 trending / popular 回應的 `popularity` 不是清單排序依據，清單順序本身就是 TMDB 的排名。discover 的 `sort_by=popularity.desc` 是伺服端排序，行為和 trending 陣列順序是兩回事，**需實打確認**。
- 旁證（非 TMDB，同類問題）：Bangumi `/calendar` 本週 113 部，票數中位數 53、四分位 1 / 53 / 175；**46 部不到 20 票**。例如 2026-10-05 開播的某部是 8 票、均分 3.6。任何「新番」評分都有同樣問題。AniList 同季 `averageScore` 也可為 null（我查的 Fall 2026 前 50 筆有 1 筆）。
- 建議：給 AI 的工具回傳要**同時帶分數與票數**，系統提示寫明「票數少於 N 的分數不要當評價用」。這是 prompt 與工具輸出格式的設計，不需要額外的 API。

### 1.3 實例：Re:Zero 在 TMDB 上

TV id **65942**（`Re:ZERO -Starting Life in Another World-`，network TV Tokyo / AT-X，狀態 Ended）。以下除另註外都是 2026-10-27 的網頁現況（WebFetch `themoviedb.org/tv/65942-…`）。

| 項目 | 現況 | 來源 |
| --- | --- | --- |
| 季 | 只有 `Specials`（Season 0，90 集）與 `Season 1`（85 集，2016-04-04 起）；沒有 Season 2 / 3 / 4 | `…/seasons` |
| Season 1 的結構 | S1E1–25 = 第一季；E26–38 = 第二季 part 1（2020-07）；E39–50 = part 2（2021-01）；E51–66 = 第三季（2024-10 ~ 2025-03）；E67–85 = 第四季（2026-04-08 起，分 part：Loss Arc 11 集 4–6 月、part 2 自 2026-08-12 起至 E85 `Shaula / Hero` 2026-09-30）| repo 快照 `tv-65942.json` 的 `air_date` 序列；[Wikipedia season 4](https://en.wikipedia.org/wiki/Re:Zero_season_4)（總集數 67–85、19 集）、[Radio Times](https://www.radiotimes.com/tv/fantasy/anime/rezero-starting-life-in-another-world-season-4-part-2-release-schedule) |
| Specials 裡有什麼 | Break Time（2016 11 集）、Petit（14 集）、Break Time 2nd/3rd/4th Season 的短篇…全部塞在 Season 0。快照時 82 集，現況 90 集，仍在增加（Break Time 4th Season 每週追加）| 快照 + 網頁 |
| Episode groups | 四個：`season4`（type Absolute，**0 組 0 集**，空的）；`Story Arc`（5 組 66 集）；`Seasons`（type Production，5 組 170 集）；`Director's Cut Seasons`（Production，1 組 0 集）| `…/episode_groups` |
| 劇場版 / OVA | **獨立 movie 而不是 specials**：Memory Snow（id **532321**，2018-10-06）與 Frozen Bond（id **566451**，2019-11-08），同屬 collection **689287**（`Re:ZERO -Starting Life in Another World- Collection`，`parts` 共 2 部）。collection 與 TV 系列**沒有連結**| `…/collection/689287-re`；movie 頁 |
| 別名 | `alternative_titles` 含 `Re:ゼロから始める異世界生活 2nd season`、`… 3rd season 襲撃編`、`… 3rd season 反撃編`、`… 4th season`、`… 新編集版`、`リゼロ`、`Re:Zero kara Hajimeru Isekai Seikatsu` | 快照 `titles` |
| 頁面異常 | TV 頁最後一集 `1x85` 的日期顯示 2026-09-30，而系列狀態為 Ended；網頁抓取工具對此有提示「可能是資料錯誤」，實際上就是播出日（Wikipedia 同日）| 網頁 |

**對照字幕組發佈名**（取自 repo 已錄的真實 RSS / 語料，不是新抓的）：

| 輪次 | 字幕組寫法 | 對 TMDB 的意義 |
| --- | --- | --- |
| 第二輪 2020 | `[…hyakuhuyu] … S2][02]`（每輪重數，丟掉季號就是「只有集號、TMDB 一季」）| 正解 `S01E27`；repo 語料 `anime/rezero-s2-02-hyakuhuyu` |
| 第四季 2026 | `[黒ネズミたち] Re：从零开始的异世界生活 第四季 夺还篇 / Re:Zero 4th Season - 84 (CR 1920x1080 …)` | 用的是**總集數 84**，與 TMDB S01E84 一致；同時帶「第四季」與「夺还篇」（篇章名）|
| 第四季 LoliHouse | `Re:从零开始的异世界生活 / Re:Zero kara Hajimeru Isekai Seikatsu - 81 v2 [WebRip 1080p HEVC-10bit AAC]` | 同樣是總集數 81；沒寫季號 |
| 合集 | Nyaa：`Re:ZERO -Starting Life in Another World- (Season 1-2+Movies+Specials) [Dual Audio 10bit BD1080p][HEVC-x265] (Break Time + Petit + …` | 一個 torrent 含 TV 兩季 + 劇場版 + specials，單一確認卡無法對應 |
| 劇場版 BD | Beatrice-Raws：`Re Zero kara Hajimeru Isekai Seikatsu – Hyouketsu no Kizuna / The Frozen Bond [1080p]`（BDRip HEVC FLAC，1/1 集）；同站另有 `… Shin Henshuu-ban / Director's Cut`（13 集 BDRip）| 劇場版以**日文羅馬字副標**命名；導演版（新編集版）是另一個作品，不是第一季重發 |

來源：repo `tests/fixtures/http/mikan/rss-classic.xml`、`tests/fixtures/parser/anime/rezero-*`（brief §20.4 已錄）；Beatrice-Raws 兩頁（[Frozen Bond](https://beatrice-raws.org/release/beatrice-raws-re-zero-kara-hajimeru-isekai-seikatsu-hyouketsu-no-kizuna-the-frozen-bond-bdrip-1920x1080-hevc-flac-1080p)、[Director's Cut](https://beatrice-raws.org/release/beatrice-raws-re-zero-kara-hajimeru-isekai-seikatsu-shin-henshuu-ban-directors-cut-bdrip-1920x1080-hevc-flac-1080p)）；Nyaa 搜尋頁 `nyaa.si?q=re:zero`（2026-10-27 Tavily 摘要，內容未逐筆驗證）。

> 我對 repo 語料名稱 `rezero-s2-02-hyakuhuyu` 的字幕組拼法照語料檔名，未再核對原始 RSS。

---

## 2. 動漫專用來源

### 2.1 AniList（GraphQL，`https://graphql.anilist.co`）

- **免 key 可讀**（本次實測匿名查詢成功）。
- **速率**：官方文件寫正常 90 req/min，但頁首警告「API 目前處於降級狀態，限制 30 req/min，是暫時措施」；實測回應標頭 `X-RateLimit-Limit: 30`（2026-10-27）。另有 burst limiter，超過會被 1 分鐘 timeout。**目前不接受提高上限的申請**。（[Rate Limiting](https://docs.anilist.co/guide/rate-limiting)）
- **條款**（[Terms of Use](https://docs.anilist.co/guide/terms-of-use)）：非商業免費（月營收 < $150 的商業也免費）；禁止拿來當備份/儲存服務；**禁止大量收集資料（hoarding）**；禁止用在「競爭性、非互補」的同類服務（anime / manga list 或 tracker）；名稱含 AniList 要標 UNOFFICIAL / "for AniList"。Berth 是下載協調器，屬互補；但對話 agent 按需查詢即可，**不要預抓全站**。
- **季表**：`Page.media(season: FALL, seasonYear: 2026, type: ANIME, sort: POPULARITY_DESC, format_in: [TV, ONA])`，回 `popularity`、`averageScore`（0–100，可為 null）、`episodes`、`status`。實測 Fall 2026 前 50 筆：`Cyberpunk: Edgerunners 2`（popularity 105626）、`Kusuriya no Hitorigoto 3rd Season`（105262, 85 分）…
- **relations**：`Media.relations.edges { relationType(version: 2) node {…} }`。實測 Re:Zero：第一季（id 21355, MAL 31240）的 relations 含 `SPIN_OFF`（Break Time、Petit）、`SIDE_STORY`（OVA 100049）、`SEQUEL`（2nd Season 108632）、`CHARACTER`（Isekai Quartet 系列，應過濾）；`relationType` 還有 `PREQUEL`、`PARENT`、`ALTERNATIVE`、`SUMMARY`…。
- **實例走圖**：以 `{PREQUEL, SEQUEL, SIDE_STORY, PARENT, SUMMARY, ALTERNATIVE, SPIN_OFF}` 為邊，從 21355 BFS，**12 次呼叫 = 12 個節點**：

  | AniList id | 格式 | 開播 | 集數 | 名稱 |
  | --- | --- | --- | --- | --- |
  | 21355 | TV | 2016-04-04 | 25 | Re:Zero kara Hajimeru Isekai Seikatsu |
  | 21780 / 21891 | TV_SHORT | 2016 | 11 / 14 | Break Time / Petit |
  | 100049 | OVA | 2018-10-06 | 2 | Re:Zero … OVAs（含 Memory Snow）|
  | 108632 | TV | 2020-07-08 | 13 | 2nd Season |
  | 119661 | TV | 2021-01-06 | 12 | 2nd Season Part 2 |
  | 120700 / 128306 | ONA | 2020 / 2021 | 13 / 12 | Break Time 2nd Season（兩段）|
  | 163134 | TV | 2024-10-02 | 16 | 3rd Season |
  | 182417 | ONA | 2024-10-03 | 16 | Break Time 3rd Season |
  | 189046 | TV | 2026-04-08 | 19 | 4th Season |
  | 210687 | ONA | 2026-04-08 | 19 | Break Time 4th Season |

  AniList **把分割 cour 當成兩個條目**（2nd Season / Part 2），TMDB 全併一季；兩者的差正是字幕組命名的來源（`2nd Season Part 2`）。**Frozen Bond 沒有出現在這張圖**：100049 的 `ALTERNATIVE` 關聯指向一個 Manga 條目，我用日文羅馬字查詢也沒命中獨立動畫條目。→ AniList 對這部劇場版的覆蓋不可靠，要靠 TMDB collection 補。
- 優點：一個查詢拿到格式（TV / MOVIE / OVA / ONA / TV_SHORT）、集數、開播日、狀態；MAL id 直接帶出（`idMal`）。缺點：30 req/min 目前很緊，走圖一次要 ~12 次，必須快取。

### 2.2 Bangumi（bgm.tv，`https://api.bgm.tv`）

- **免 key 可讀**。必須帶有意義的 User-Agent（含開發者 ID 與應用名，預設 UA 可能被禁用）；官方文件範例 `trim21/bangumi-episode-ics (https://github.com/…)`（[user agent.md](https://raw.githubusercontent.com/bangumi/api/master/docs-raw/user%20agent.md)）。需要授權的是個人收藏類端點（OAuth 2.0）。我沒查到公開的速率數字，文件也沒寫。
- **`GET /calendar`**（新番放送表）：2026-10-27 實測回 7 個 weekday × `items[]`，共 113 部，每筆有 `name`、`name_cn`、`air_date`、`rating.{score,total,count}`、`rank`、`images`。**中文名直接給**，這是對中文社群使用者最大的優勢。回應 `cache-control: max-age=3600`。
- **評分分布（本週放送表）**：票數最大 14,902（航海王）、中位數 53、<20 票有 46 部。
- **relations**：`GET /v0/subjects/{id}/subjects`。實測 Re:Zero 第一季（id 140001，評分 7.5、25,178 票）回 **48 筆**，但雜訊極多：遊戲、CD、廣播劇、原聲集、聯動動畫（Isekai Quartet）。有用的 `relation` 值：`續集`（278826）、`番外篇`（225462 雪之回憶、261805 冰結之絆，`platform: OVA`，日期 2019-06-07 / 2019-11-08）、`總集篇`（296195 新編集版）、`衍生`（Break Time、Petit）。**必須依 `type`（2 = 動畫）與 `relation` 過濾**。Bangumi 把 Memory Snow 的日期記成 2019-06-07（OVA 的 BD 發售），TMDB 記 2018-10-06（劇場上映）——**日期不能跨來源比對**。
- 與 Berth 的連結：Mikan 番組頁有 bgm.tv 連結（brief §20.12 已記），所以「Mikan 番組 id → Bangumi subject id」是現成的；Bangumi **沒有** TMDB id 對應，要靠 Fribb 或標題比對。
- 適合：中文使用者的「這季有什麼好看」「評價」；不適合：完整系列的 TMDB 對應。

### 2.3 MyAnimeList / Jikan

- Jikan 是非官方 REST（`api.jikan.moe/v4`，MIT，免 key，只讀），背後抓 MAL 網頁。文件列的限制是 **3 req/s、60 req/min**（Jikan 官方 issue 與各 wrapper 文件一致，[issue #221](https://github.com/jikan-me/jikan-rest/issues/221)；舊版 wrapper 文件寫 30/min、2/s，視版本而定）；回應有 `ETag` 可做 304 快取；MAL 本身限流時回 429。
- 端點：`/seasons/{year}/{season}`、`/seasons/now`、`/anime/{id}/relations`、`/top/anime`。
- **本機連線失敗**（`SSL_ERROR_SYSCALL`，2026-10-27），無法實測；Jikan 是社群營運的單點服務，穩定性風險高於 AniList。
- MAL 本身的官方 API 需要 OAuth app 註冊（本次未查細節），對自託管用戶不友善。
- 角色：**備援**。AniList 回應裡已經帶 `idMal`，需要 MAL 分數時再補。

### 2.4 ID 對應：Fribb/anime-lists 與 Anime-Lists

- **Fribb/anime-lists**（[GitHub](https://github.com/Fribb/anime-lists)）：`anime-list-full.json`，2026-10-27 下載 **7.5 MB、39,579 筆**，倉庫最後提交 2026-10-20。欄位：`type`（TV / MOVIE / OVA / ONA / SPECIAL）、`anidb_id`、`anilist_id`、`mal_id`、`kitsu_id`、`imdb_id`、`tvdb_id`、`themoviedb_id`（TV 為 `{"tv": id}`，電影可為陣列）、`season.{tvdb,tmdb}`、`episode_offset.{tvdb,tmdb}`。
- **TMDB 覆蓋率**：39,579 筆裡只有 **8,530 筆（21.6%）** 有 `themoviedb_id`。對近年有名的 TV 作品通常有；OVA / 特別篇 / 冷門作多半沒有。
- **Re:Zero 實測**（這是 §0 第 2 點的證據）：

  | AniList | MAL | Fribb `themoviedb_id` | `season.tmdb` | `episode_offset.tmdb` | TMDB 實際 |
  | --- | --- | --- | --- | --- | --- |
  | 21355（S1）| 31240 | tv 65942 | 1 | — | S01E01–25 |
  | 108632（S2）| 39587 | tv 65942 | 1 | 26 | E26 起（正好）|
  | 119661（S2 P2）| 42203 | tv 65942 | 1 | 38 | E39 起 |
  | 163134（S3）| 54857 | tv 65942 | 1 | 50 | E51 起 |
  | 189046（S4）| 61316 | tv 65942 | 1 | 66 | E67 起 |
  | 100049（OVA/Memory Snow）| — | tv 65942 | **0** | — | 對到 Specials，而不是 TMDB movie 532321 |

  **沒有任何 Fribb 條目指向 TMDB movie 532321 / 566451**。所以 Fribb 解不了 Re:Zero 的兩部劇場版，要用 TMDB collection / search 補。
- **Anime-Lists（ScudLee）** `anime-list.xml`：AniDB id → TVDB / TMDB（`tmdbid`、`tmdbseason`、`tmdboffset`）。Fribb 的 README 說自己是它的精簡衍生並用 TMDB API 補缺 id；本次未直接比對兩份。
- 授權與使用：Fribb 倉庫的授權條款本次沒有查；若要打包進 Berth 要先確認（`LICENSE`）。作為「執行時從 raw.githubusercontent.com 抓、快取、每週更新」的做法則沒有這個問題，但依賴第三方倉庫存活。

### 2.5 比較

| | AniList | Bangumi | Jikan / MAL | Fribb | TMDB |
| --- | --- | --- | --- | --- | --- |
| 新番季表 | **最好**（篩季 + 排序）| 好（`/calendar`，中文名）| 可（`/seasons`）| — | 勉強（需 keyword 組合）|
| 評分 | 0–100，可 null | 1–10 + 票數 + 分布 | MAL 分數 | — | 0–10 + 票數，新番不穩 |
| 系列關聯 | **最好**（型別化 relations）| 噪音大，需過濾 | `/relations` | 只有 anidb 集合檔 | 只有 movie collection，無 TV 關聯 |
| 與 TMDB 對應 | 無 | 無 | 無 | **有（21.6% 覆蓋，含 offset）** | — |
| 中文名 | 無（romaji / native / english）| **有** | 無 | — | 有（zh-TW / zh-CN 翻譯）|
| 帳號 / key | 免 | 免（要 UA）| 免 | 免 | 需 key（Berth 已要求）|
| 速率 | 30–90 / min | 未公開 | 60 / min | 靜態檔 | ~40 / s |
| 風險 | 目前降級 30/min、禁 hoarding | 單一社群站 | 單點、爬蟲式 | 第三方倉庫 | 季劃分常被改 |

**建議**：系列清單 = AniList（走圖）→ Fribb（對 TMDB）→ TMDB（驗證存在 + 取劇場版）；新番推薦 = AniList 季表為主，Bangumi `/calendar` 補中文名與社群分，TMDB 補海報/簡介（Berth 已有）。Jikan 不納入。

---

## 3. 一般劇集的推薦與評價來源

### 3.1 Trakt

- 端點：`/shows/trending`、`/shows/anticipated`、`/shows/popular`、`/recommendations/shows`（個人化，需 OAuth）。免登入的公開端點只要 `trakt-api-key`（Client ID）標頭。
- **速率**（[Rate Limits](https://developer.trakt.tv/docs/rate-limiting)，2026-10-27）：未登入 GET 每 Client ID + 公網 IP **500 次 / 5 分鐘**；登入 GET 500 / 5 分鐘；POST/PUT/DELETE 1 次/秒。
- **取得 Client ID 的門檻在 2026 年變了，而且文件與論壇不一致**：
  - 開發者文件〈Create an App〉現在要求「**已驗證的 GitHub 帳號**」，且「不得為了繞過速率限制而建多個 app」；資料不得用於助長盜版的 app（[Create an App](https://developer.trakt.tv/docs/create-an-app)）。
  - 論壇有用戶回報「建立 API 應用程式目前是 VIP 功能，免費帳號僅有的 app 被移除」，客服答覆「下個月會有其他選項」（[Failure to register an API](https://forums.trakt.tv/t/failure-to-register-an-api/116157)，貼文日期未取得）；官方公告也把「免費帳號同時只能連一個 Community App」（2026-07 左右，[公告](https://forums.trakt.tv/t/an-update-to-community-app-connections/117898)）。
  - 條款本身最後更新 2026-09-25（[Terms](https://app.trakt.tv/terms)）：個人、非商業。
- 判定：**對自託管用戶「每人一把自己的 Trakt key」摩擦太高且政策不穩**。Berth 若內建一把共用 key，違反 Trakt「不要為繞過限制建多個 app」的精神，也綁到 Berth 專案帳號的 VIP 狀態。不建議作為預設，最多當選配。

### 3.2 IMDb

- 無免費官方 API。官方路徑是 AWS Data Exchange 的付費 IMDb API / Bulk Data（需聯絡授權，[文件](https://developer.imdb.com/documentation/)）。
- **非商業 dataset**（[說明](https://developer.imdb.com/non-commercial-datasets/)）：個人與非商業可下載，TSV gz，**每日更新**，有 `title.ratings.tsv.gz`（`tconst`、`averageRating`、`numVotes`）與 `title.basics`、`title.akas`。可以本地持有副本，受條款約束。
- 用法：TMDB 的 `external_ids` 給 `imdb_id` → 對 dataset 查 IMDb 評分與票數。要自己下載、解壓、建索引（數百 MB 級，具體大小未查），對 Berth 是額外的維運面。
- 判定：不納入預設；可當「網搜找評價」時的間接來源（搜尋結果頁會帶 IMDb 分數）。

### 3.3 豆瓣

- 公開 API 已於 2019 前後關閉（[討論串](https://m.douban.com/group/topic/140630769)為使用者詢問，無官方公告；第三方整理 [豆瓣开发者不完全指南](https://feizhaojun.com?p=3813) 說明圖書、電影 API 已關閉，只剩抓 App / 小程式接口的非官方做法）。
- 判定：**不可作為資料來源**。非官方抓取接口用的是外流的 apiKey，法律與穩定性風險都不該由 Berth 承擔。中文社群評價改用 Bangumi（動漫）或網搜結果摘要。

### 3.4 TMDB 以外的建議

- 一般劇集推薦：TMDB（trending / discover / recommendations，已有 key）就夠；評價補充走網搜（§4），讓 AI 讀媒體評論頁，**不是**當作結構化資料。
- 串流平台可用性：TMDB `watch/providers`（JustWatch，必須標示來源）。Berth 使用者「要下載」，這資訊用途是告訴使用者「這部其實有正版平台」，屬可選。

---

## 4. 網路搜尋工具（自託管用戶視角）

| | Anthropic `web_search` / `web_fetch` | Tavily | Brave Search API | Exa | SearXNG（自架）|
| --- | --- | --- | --- | --- | --- |
| 額外帳號 | **不用**（同一把 Anthropic key）| 要（Tavily key）| 要 + **綁信用卡** | 要 | 不用（要自己跑一個容器）|
| 費用 | **$10 / 1,000 次搜尋** + 搜尋結果算輸入 token（web fetch 另文件說明，本次未查價格）| 免費 1,000 credit/月；basic 搜尋 1 credit、advanced 2 credit；PAYG $0.008/credit；Project $30/月 4,000 credit | **$5 / 1,000 次**，含每月 $5 免費額度（頁首另寫 "Up to $20 in free calls every month"，兩處說法不一致）；Answers $4/1,000 + token | 每月 $10 免費額度；Instant $4 / Fast-Auto $7 / Deep $12 每 1,000 次 | 免費（+ 主機）|
| 限制網域 | `allowed_domains` / `blocked_domains`（二選一）| `include_domains` / `exclude_domains` | Goggles（重排 / 過濾規則）、`site:` | `includeDomains`（API）| `site:` 語法 / 設定引擎 |
| 時間 / 主題 | 由模型自己決定查詢 | `topic: general\|news`、`time_range`、`start_date/end_date`、`country` | `freshness` | 日期過濾 | `time_range` |
| 結果品質 | 單一供應商內部搜尋（來源引用）| 專為 LLM 設計，可帶 raw content | 獨立索引（官方稱不回退 Google / Bing）| 語意搜尋強 | 取決於上游引擎；**上游常 CAPTCHA / 封鎖**，JSON 輸出不穩（[You.com 整理](https://you.com/resources/searxng-alternatives)為競品文章，僅供參考）|
| 繁中 / 日文 | 模型端處理，無特別限制 | 有 `country` 加權（含 japan / taiwan / china）| 有 `search_lang`、`country` 參數 | 英文最強，CJK 未驗證 | 取決於引擎 |
| 與 provider 無關？ | **否**（綁 Anthropic）| 是 | 是 | 是 | 是 |
| MCP | — | 有官方 MCP server（npx `tavily-mcp`，也有遠端 MCP）| 有 MCP server | 有 | 社群 MCP |

來源：
- Anthropic：[Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)（$10/1,000、三個版本 `web_search_20250305` / `20260209`（動態過濾）/ `20260318`、`allowed_domains` 與 `blocked_domains` 擇一）、[Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)（可用於 Claude API、AWS 上的 Claude Platform、Google Cloud 上 Anthropic 託管的 Claude、Foundry；web fetch 只能抓對話裡已出現的 URL）。哪些模型支援哪個版本：動態過濾版需要 Opus 4.6 以上與 Sonnet 4.6 以上；**Vertex AI 上只有基本版 `web_search_20250305`、沒有 web fetch**（claude-api skill 的 Server Tools 表，2026-10-27）。Haiku 5.5 是否支援我沒有逐項確認。
- Tavily：[Credits & Pricing](https://docs.tavily.com/documentation/api-credits)、[MCP](https://docs.tavily.com/documentation/mcp)。
- Brave：[brave.com/search/api](https://brave.com/search/api/)（Search $5/1,000、50 QPS；Answers 2 QPS；免費額度需信用卡，頁面 FAQ 有「為何要信用卡」一項）。
- Exa：[exa.ai/pricing](https://exa.ai/pricing)（Starter 每月 $10 免費、10 QPS）。
- SearXNG：[Limiter 文件](https://docs.searxng.org/admin/searx.limiter.html)；JSON 格式預設未啟用，要在 `settings.yml` 的 `search.formats` 加 `json`（[Discussion #3542](https://github.com/searxng/searxng/discussions/3542)、[LiteLLM 文件](https://docs.litellm.ai/docs/search/searxng)）。

**對 Berth 的建議**：
1. 預設用 Anthropic `web_search`（Berth M5 的 provider 就是 Anthropic，零額外設定）。查詢意圖固定（「X 的評價」「X 全系列順序」），用 `allowed_domains` 限制在 `anilist.co`、`myanimelist.net`、`bgm.tv`、`wikipedia.org`、`themoviedb.org`、`reddit.com` 這類來源，降低 prompt injection 與垃圾農場風險。注意：**網頁內容是不可信資料**，搜尋結果餵給 agent 後仍不得驅動寫入類命令（確認卡才是閘門）。
2. 介面保留 `WebSearch` 工具抽象，之後可換 Tavily（key 設定）或 SearXNG（URL 設定）。不要把 Anthropic server tool 的型別寫死在 services 層（`adapters/ai` 內處理）。
3. 預算：一次「推薦」對話大約 3–6 次搜尋 = $0.03–0.06 + token；一次「全系列」2–4 次。需要把 `web_search_requests`（回應 `usage.server_tool_use`）記進 Event，與 M5 既有的費用記帳同一處。
4. 用戶用 ZDR / Vertex 時 web fetch / 動態過濾版不一定可用，要有降級（只回 TMDB / AniList 資料）。

---

## 5. 情境 1 / 2 的問題點

### 5.0 Berth 現有能力盤點（相關部分）

- TMDB adapter（`berth/adapters/tmdb/client.py`）：`/configuration`、`/trending/{tv,movie}/week`、`/search/multi`、tv detail、`/tv/{id}/season/{n}`、`/tv/episode_group/{id}`；`services/discover.py` 有 `read_trending`、`read_popular`、`search_media`。**沒有** discover、on_the_air、recommendations、keywords、collection、watch providers、find、external_ids。
- 搜索：`search.search_torrents`（Prowlarr 索引站，帶 verdict 與季集估計）、`indexer.search_indexers`；`bangumi.search_bangumi` / `read_bangumi`（Mikan 番組與字幕組，標 READ）。
- 寫入：`rss.subscribe_mikan`、`rss.subscribe_search`（Nyaa / acg.rip）、`jobs.add_download`（`downloading.add_manual_download` 標 REVERSIBLE）、`rss.bind_series`。
- 檢查：`inventory.read_holdings`（每集持有與缺號，`aired_episodes`）、`media.read_snapshot`、`rss.list_series`（有 `finished`）。
- 命令登錄表現況見同目錄 `05-human-touchpoints.md`：`jobs.py`、`discover.py`、`search.search_torrents`、`issues.resolve_issue` 等在 `BEFORE_M3` 豁免表，**沒有 `@command` 標記**，AI 工具要用就得先補標。

### 5.1 資料來源可靠度

- **TMDB 的動漫季劃分正被社群改**：brief §20.3 已記合併；本次補一個現況證據——Re:Zero 4 季併成 1 季至今沒被拆回（Absolute group `season4` 存在但是空的，有人建了沒填）。**不能假設「TMDB 說第 2 季」等於使用者/字幕組說的第 2 季**；系列清單用 AniList 的輪次當顯示單位，用 Fribb 的 `episode_offset` 換算到 TMDB。
- **TMDB 評分偏差**：新番低票數（§1.2）；非英語作品的 TMDB 使用者群偏西方。
- **Fribb 覆蓋率 21.6%**（§2.4）：沒對應時退回標題搜尋（TMDB `search/tv` 加 AniList 的 `title.native`），這一步必須由使用者在確認卡確認。
- **AniList 的 `averageScore` 可為 null**，新番的 `popularity` 是累積列表數，剛開播的作品天然低。
- **網搜內容**可能過時或錯（例如本次 Re:Zero 的 TMDB 末集日期被工具疑為錯誤，實為正確）；agent 引用時必須帶來源 URL，確認卡上顯示。

### 5.2 TMDB 季劃分 vs 字幕組發佈名的落差

- 已有（brief §20.3、§6.4、`profile-effect.md`）：分割 cour、絕對編號、虛擬季、篇章名。Berth 的 parser 已處理，對話層**不重做**。
- 對話層新增的風險是**「訂閱時對哪個輪次」**：使用者說「Re:Zero 第三季」，AniList 是 163134（16 集），TMDB 是 `S01E51–66`，Mikan 的番組頁是另一個 bangumiId，字幕組寫 `3rd Season` 或 `S3` 或總集數 51 起。確認卡要同時顯示三個名字 + 集數範圍，讓使用者看到「這就是我要的」。
- Mikan 的 Re:Zero 第四季發佈名帶 `第四季 夺还篇`，與 TMDB 季名（只有 Season 1）對不上，這靠 parser 的篇章名比對與虛擬季；對話層只需要把選定的 bangumi 綁到對的 TMDB media（`bind_series`，已有）。

### 5.3 torrent 搜尋結果品質

- 一季多字幕組 × 多解析度 × 簡繁 × 內嵌/內封（brief §20.4 樣本）；Nyaa / acg.rip 搜尋 feed 夾合集（brief §20.12：8/30、14/75）。
- **已完結作品 RSS 沒有用**：Mikan 單一 feed 有整季（brief §20.12），所以 Mikan 路徑對完結作品可用（`subscribe_mikan` 一律補整季）；但 Nyaa / acg.rip 的搜尋 feed 是滾動窗口，且 Re:Zero 這種多輪次作品會混合不同輪次。→ 對已完結作品優先 **Mikan（若有）→ 否則搜尋後逐 torrent 下載**，不要建搜尋 feed 訂閱。
- **BD 與 WEB**：Beatrice-Raws 的 BD 單獨是一個 torrent（Frozen Bond 1/1；Director's Cut 13/13）；VCB-Studio / DBD-Raws 的 BD 包含 SP / PV / NCOP / menu / Fonts（brief §20.4）；Nyaa 有「Season 1-2 + Movies + Specials」跨作品合集。→ 搜尋回的每個結果要標 `release_kind`（Berth 已有 single / range / batch / collection）與涵蓋的 TMDB 季集範圍，AI 才能判斷是否「涵蓋全部」。
- **冷門劇**：做種數少，qBittorrent 可能卡住——這是 Job 層的問題（`stalled`），agent 要在確認卡上顯示做種數與大小，並說明風險。（做種數是否已在 `search.SearchResult`，我沒逐欄確認。）

### 5.4 劇場版 / OVA：兩種入庫路徑

- TMDB 的歸屬：**Memory Snow / Frozen Bond = movie（各自 id）**；Break Time 等短篇 = TV Season 0；Fribb 把 OVA 對到 Season 0 而不是 movie；AniList 格式 OVA / MOVIE / ONA 並存。→ **同一個「OVA」在不同來源會落到不同入庫路徑**。
- Berth 側：電影走 movie Route（Jellyfin 電影庫），specials 走 TV 的 `Season 00`（`season_number: 0`，brief §20.3）。這是兩個不同的 Route 種類，確認卡必須明示「入庫成：電影」或「入庫成：Specials」。
- 建議規則：以 **TMDB 的歸屬為準**（因為最終命名由 TMDB 決定，Jellyfin 也吃 TMDB）；當 AniList / Fribb 與 TMDB 不一致，卡片上列出不一致並預設 TMDB。Re:Zero 的兩部要建為兩個 movie media（各一張卡），Break Time 系列預設不勾選（使用者要才加）。

### 5.5 情境 1：推薦新番 / 新劇

**流程**
1. 使用者：「最近有什麼新番推薦」。agent 先確認偏好（類型、語言、要不要只看有字幕組在做的）——可以不問，直接給一份。
2. 讀取：AniList 當季季表（`popularity` 前 N）+ Bangumi `/calendar`（中文名、社群分）；一般劇集走 TMDB `discover/tv`（`first_air_date.gte`、`vote_count.gte`、`sort_by=popularity.desc`）或 `trending`（Berth 已有）。
3. 評價：每部取 AniList / Bangumi / TMDB 的分數 + 票數；必要時 1–2 次網搜（「X 評價」，限定網域）。
4. 給清單（5–10 部）：標題（中 / 日 / 英）、集數 / 播出狀態、分數 + 票數、一句理由、**Berth 內是否已追蹤**（`tracking.is_tracked`）、**是否有字幕組在做**（Mikan 搜尋命中）。
5. 使用者選 → agent 找對應 TMDB media（`search_media`；AniList→TMDB 用 Fribb，沒有就標題搜尋）→ 找來源：連載中的作品優先 Mikan（`bangumi.search_bangumi` → `read_bangumi` 列字幕組 → `rss.subscribe_mikan`），次選 `rss.subscribe_search`（Nyaa / acg.rip）；已播完的走情境 2。
6. 確認卡 → 執行 → 進既有流程（RSS Series 自動綁定、第一批 audit、入庫）。

**需要的資料與工具**
- 新工具（READ）：`anilist.season`、`bangumi.calendar`、`tmdb.discover`、`tmdb.external_ids`／`fribb.lookup`、`web.search`。
- 現有：`discover.search_media`、`bangumi.search_bangumi/read_bangumi`、`tracking.is_tracked`。
- 寫入：`rss.subscribe_mikan`（REVERSIBLE，無單一反向命令，brief 與 plan 已記）、`rss.subscribe_search`（inverse `rss.delete_feed`）。

**問題點**
- 新番評分票數少（§1.2）；agent 不應該說「評價很高」，只能說「目前 N 票平均 X」。
- 清單中的作品可能 Mikan 還沒有字幕組發佈（剛開播第 1 集前），訂閱不會有東西——要先 `read_bangumi` 看有幾個字幕組、`releases` 數。
- 訂閱要選字幕組與繁簡（brief §20.4：一部作品只訂一個字幕組較佳）。agent 可建議預設（使用者先前常用的組、`bound_to` 已有的組），但**選字幕組是使用者偏好**，確認卡上列出候選。
- Route 選擇（TV / movie 可有多條，brief §15）：若只有一條自動帶，多條要問。
- 版權：agent 推薦與訂閱的是使用者的決定，卡片上不要出現促進盜版的措辭；Trakt 條款明文禁止用於助長盜版（§3.1），所以資料來源也不用 Trakt。

**建議**
- 確認卡顆粒度：**一張卡一部作品**（作品 + 輪次 + 來源 + 字幕組 + Route + 會發生什麼：「訂閱後現有 N 集會一併補上並送下載」，Mikan 路徑 `series.submitted` 含整季，這個數字要事先估給使用者看）。
- 推薦清單本身不是確認卡（只讀），每部旁邊有「訂閱」按鈕，按了才生成確認卡；一次選多部就依序一部一卡，卡片可批次「全部確認」但每張內容仍可展開。
- 副作用等級：`subscribe_*` 是 REVERSIBLE，依 M5 規則（使用者在場時自己要求的可逆動作直接執行並給撤銷）可以不經 Proposal；**但「訂閱後自動補整季」會立刻送出幾十集下載**，使用者感受上不是小事。建議這條路徑在對話中仍出確認卡（卡片本身就是輕量確認），不要走靜默執行。

### 5.6 情境 2：全季 / 全系列 / 冷門劇

**流程（以 Re:Zero 為例）**
1. 辨識作品：`search_media("Re:Zero")` → TMDB 65942；Fribb 反查 → AniList 21355。
2. 組清單：AniList 走圖（12 次呼叫，快取）→ 每個節點用 Fribb 對到 TMDB（tv 65942 + 季 + offset），沒對到的標「未對應」；再用 TMDB collection（`GET /collection/689287`）補劇場版，並把 AniList/Fribb 的 OVA 與 collection 的 movie 比對去重。
3. 呈現「完整清單」：
   - 正篇：第 1 季（25）、第 2 季 part 1（13）、part 2（12）、第 3 季（16）、第 4 季（19）= TMDB `S01E01–85`。
   - 電影：Memory Snow（movie 532321）、Frozen Bond（movie 566451）。
   - 其他：總集篇／導演版 `新編集版`（AniList/Bangumi 有，TMDB 為 episode group `Director's Cut Seasons` 且 0 集）、Break Time 系列（TMDB Season 0）、Petit、Isekai Quartet（聯動，過濾掉）。
   - 預設勾選：正篇 + 電影；不勾：Break Time / 導演版 / 聯動。
4. 逐項找來源：
   - 完結 → Mikan 單一 feed 有整季（`subscribe_mikan`）或 `search_torrents` 找 BD/合集；
   - 合集 torrent 若涵蓋多部（如 Nyaa 的 Season 1-2+Movies+Specials），是否採用是使用者決定（一個 torrent 進一個 Job，Plan 會把檔案分配到各集）。
5. 確認 → 分批執行。

**需要的資料與工具**
- 新工具（READ）：`anilist.relations_walk(id)`（內部做走圖與快取）、`fribb.lookup(anilist_id)`、`tmdb.collection(id)`、`web.search`（補導演版、冷門劇的集數）。
- 現有：`search.search_torrents`、`bangumi.*`、`media.read_snapshot`（取 TMDB 季集）、`inventory.read_holdings`（已持有哪些，避免重複）。

**問題點**
1. **規模**：Re:Zero 全做是 3 個 RSS 訂閱/搜尋 + 2 部電影，**約 110+ 集**，磁碟與頻寬不是小事；`jobs.check_disk` 已有保護，但 agent 要在確認卡上估算總大小（搜尋結果有 size）。
2. **同一輪次多個 torrent**：同一季有 WEB 單集（每集一個 torrent）與 BD 合集；選哪個影響字幕（BD 通常外掛 / 內封，WEB 多是內嵌）與品質。使用者通常想要「最好的版本」，agent 能做的是列出候選（來源、解析度、字幕、做種）並推薦，不能替使用者決定。
3. **偏好必須先問**：BD 還是 WEB、字幕語言、解析度——否則每個輪次問一次太煩。建議對話開頭一次問清楚，存為這次對話的偏好（不是全域設定）。
4. **TMDB 單季 vs 多個 torrent**：BD 合集的集號通常是各輪從 01 起，Berth 的 parser/Plan 要把 `[S3 01-16]` 對到 `S01E51–66`；這已是 parser 的工作（M1–M4），但**對話層不能假設一定成功**——Plan 可能進 review，agent 要告訴使用者「這幾個要到審核頁看」。
5. **冷門劇**：TMDB 資料常缺（季集不全、無翻譯），索引站結果零星；agent 必須誠實說「找不到完整來源」，不要硬湊。這類沒有 AniList 可走圖，只能靠 TMDB 季 + 網搜。
6. **走圖的速率**：AniList 目前 30 req/min，走圖 12 次要 24 秒；要把結果快取（例如 24 小時）並避免對同一系列重複走。
7. **去重**：使用者資料庫裡可能已經有其中幾季（`tracking.is_tracked`、`inventory.read_holdings`）；清單要標示「已有 / 部分 / 沒有」，已有的預設不勾。

**建議**
- **確認卡顆粒度：一張卡一個「作品 × 輪次」，不要一張卡一個 torrent，也不要一張卡整個系列。**
  - 一張卡一個 torrent 會有 110 張（單集 WEB）——不可行。
  - 整個系列一張卡無法表達「每個輪次選不同來源 / Route / 可能進 review」。
  - 折衷：**系列層有一張「總覽卡」**（只讀：清單、預設勾選、預估總集數與大小），使用者在這張卡上勾選要哪些；**勾選結果展開成 N 張子卡**（每個輪次或每部電影一張），每張子卡才是會觸發寫入的確認卡。
- **分批**：預設一次一個輪次（先第 1 季；進入 Plan/audit 流程後再問要不要繼續下一個），或使用者明確說「全部」時，每批最多 2–3 個輪次，批與批之間等第一批入庫結果（Berth 的「第一批審核」本來就是這個設計邏輯，brief §15）。理由：parser 對第一批的判斷會影響後面（例如 Route 選錯，後面全錯）。
- **劇場版與 specials 分開卡**，卡上明示入庫成 movie 或 Season 0（§5.4）。
- agent 不宣稱「完整」：回覆用「依 AniList / TMDB / Fribb 整理，未對應的有 N 項」，並列出沒對應的。

---

## 6. 其他對話 / 背景情境與可行性

事實基礎：命令登錄表現況（`05-human-touchpoints.md`）、`berth/services/` 的命令（本次 grep：標了 `@command` 的 READ / REVERSIBLE / IRREVERSIBLE 清單；`jobs.py`、`issues.py` 的大半、`plan_review.py`、`duplicates.py`、`rematch.py`、`deletion.py`、`reimport.py` 未標）。

### 6.1 診斷「為什麼這集沒入庫」

- **流程**：使用者說「Re:Zero 第 85 集怎麼還沒有」。agent 讀：媒體庫持有（`inventory.read_holdings` 的缺集）→ 該集的 Job（`jobs.list_jobs` 依 media 過濾）→ `jobs.read_job_events`（時間線）→ `plan_view.read_plan`（review 原因）→ `issues.list_issues`（相關 Issue）→ RSS Series／Feed 狀態（`rss.list_series`、`list_series_items` 的 `skip` 理由與 `release_blocked`）。輸出一段因果說明 + 建議動作。
- **資料與工具**：全部是現有 READ 函式；**唯一缺口是沒標 `@command`**（`jobs.*`、`plan_view.*`、`issues.list_issues` 未標），登錄表前要補標。
- **問題點**：資料散在 5 個表，agent 需要的是「一次拉完」的聚合讀取（否則 5–8 次工具往返，每次都耗 token）。建議做一個 `diagnose.media_episode(media_id, season, episode)` 的 READ 命令，回結構化結果（`Job` 狀態鏈、最近事件、Plan 理由碼、相關 Issue、RSS Item 的 `skip`）。理由碼是封閉列舉（`ReviewReason`、`SkipCode`、`IssueType`），agent 的說明可以直接引用，不易 hallucinate。
- **風險**：低（唯讀）。要避免的是 agent「推測原因」——回覆必須只引用讀到的事實，查不到就說查不到。
- **建議**：優先做這個情境，價值最高、風險最低，也最能驗證命令登錄表。

### 6.2 補缺集

- **流程**：「Frieren 第 2 季少了第 5 集」。`inventory.read_holdings` 算缺號（`aired_episodes` 只算已播出）→ 看有沒有 Job 在途 → `search.search_torrents`（帶 `QueryScope` 指定季集）找單集或合集 → 確認卡（選 torrent）→ `jobs.add_download`。
- **資料與工具**：現有齊全。
- **問題點**：(a) 單集 torrent 常常已被合集取代；(b) 缺的集在 RSS 被排除條件擋下（`SkipCode`）時，正解是 `rss.release_item`（放行），而不是另找 torrent——agent 要先查 `skip`；(c) 缺口原因若是 `unmatched` / `review`，補下載會變成重複。
- **風險**：中——下載是 IRREVERSIBLE 的前一步（`queue_downloading` 標 IRREVERSIBLE）。`add_manual_download` 標 REVERSIBLE，可直接走，但仍建議確認卡，因為選錯 torrent 的代價是頻寬與磁碟。
- **建議**：確認卡一張卡一個 torrent（這裡 torrent 是粒度，因為使用者要補的就是一集）；順序是「先診斷（6.1）→ 再補」。

### 6.3 整理 Issue

- **流程**：「幫我看一下待處理」。`issues.list_issues` → 分類 → 對每種提建議；可逆的（`relink`、`adopt`、`claim_*`、`replan`）使用者同意後執行，不可逆的（`delete_complete`、`delete_orphan`、`replace_with_link`）做 Proposal。
- **資料與工具**：`issues.list_issues`、`issues.resolve_issue(session, factory, issue_id, action, ...)`、`ignore_issue`。
- **問題點**：`resolve_issue` 一個函式涵蓋可逆與不可逆動作，**標記要逐動作**（`05` 已指出：`ISSUE_ACTIONS` 與 `ACTION_DELETES` 決定可逆性），登錄表必須把它拆成 per-action 的命令或讓 `Effect` 依 action 變動，否則 AI 無法正確決定自動/Proposal。
- **風險**：高（刪除）。AI 預設只讀 + 建議，只有可逆動作且使用者在場時才執行。
- **建議**：與 plan §11.6「Issue 各型別變成 AI 任務」一致；對話層只做「說明 + 一鍵批次套用可逆的」。

### 6.4 換更好的版本（BD 出了替換 WEB）

- **流程**：使用者：「Frieren 第 1 季 BD 出了，換掉 WEB」。agent 查：帳本版本群組（`inventory._versions`、`VersionGroupView`）→ 搜尋 BD 合集（`search_torrents`，`Source.BD` 標籤）→ 確認卡 → 下載 → 新 Plan 與舊版產生 duplicate → `duplicates.decide_duplicate(..., replace)`。
- **資料與工具**：`decide_duplicate` 有「取代 / 保留兩者 / 跳過」；版本群組讀取已有。
- **問題點**：(a) **「取代」不可逆**（`05` A.1 #6：舊硬鏈接被換掉，來源在 complete 的檔案是否保留取決於刪除旗標）；(b) BD 的集號與 WEB 不一定一致（OVA / SP 夾在其中，brief §20.4 的 VCB `01-28+SPx11`），替換前要比對集數與片長（片長驗證 `check_runtime` 已有）；(c) 字幕：WEB 內嵌繁中 vs BD 外掛 ass，使用者可能偏好前者；(d) Jellyfin 播放進度與觀看狀態（`watch.py` 有 `WatchState`）——換檔案是否影響「已看」，我沒查證。
- **風險**：高。
- **建議**：Proposal 卡（IRREVERSIBLE），卡上並列新舊的解析度、大小、字幕、片長；預設「保留兩者」（Jellyfin 支援同集多版本，`VersionGroupView` 已有此概念），由使用者再決定刪舊。不自動化。

### 6.5 「這部完結了，訂閱可以停了嗎」

- **流程**：背景或對話皆可。檢查：TMDB `status`（`Ended` / `Canceled` → `MediaSnapshot.ended`，brief §20.3）+ 全集已入庫（`read_holdings`）+ RSS Series 的 `finished`（`rss.list_series` 已算）→ 建議停：`rss.delete_feed` 或不動（Feed 若是 Mikan 聚合 feed，同一個 Feed 會有多部，不能刪）。
- **資料與工具**：現有齊全，且 brief §15 已經把「完結的自動收進『已完結』」做在 RSS 頁。
- **問題點**：(a) 完結的判定有 TMDB 與 Berth 自算兩種（`parser.series_finished`），可能不同；Re:Zero 的例子——TMDB 狀態 Ended 但 S4 若再宣布第五季會改回（TMDB 資料更新有延遲）；(b) 「停」的物件不明：Feed（Mikan 聚合 feed 是多部共用）、RSS Series（只能解除綁定 / 排除）、搜尋 feed（可刪）；(c) 刪 Feed 會連 Feed Item 一起刪（`DELETE /rss/feeds/{id}` 回 `{items}`）。
- **風險**：低到中。實際上 Berth 對完結的 Series 已經自動收起來、不再輪詢多餘資料，**「停訂閱」的真實需求可能很小**。
- **建議**：不做成獨立情境，併進 6.1／週報（巡檢把「已完結且全持有」列為資訊，不要求動作）。

### 6.6 補充：「這部在 Jellyfin 的標題 / 季對不對」（rematch / 季修正）

- AI 最強的一類：把使用者說的「第三季」翻成 RSS Series 的 offset 修正（`series_review.correct_series`，REVERSIBLE）。plan §11.6 已經把「RSS Series 的季號與 offset 修正」列為第一批 AI 任務；對話層只是同一個命令的另一個入口。

### 6.7 排序建議

| 順位 | 情境 | 理由 |
| --- | --- | --- |
| 1 | 6.1 診斷 | 唯讀、價值高、驗證登錄表與聚合讀取 |
| 2 | 6.3 整理 Issue、6.6 季修正 | plan §11.6 已列，命令已有，補標記即可 |
| 3 | 情境 1 推薦 + 訂閱（連載中） | 讀取工具新增（AniList / Bangumi / TMDB discover），寫入走現有 `subscribe_mikan` |
| 4 | 6.2 補缺集 | 依賴 6.1 |
| 5 | 情境 2 全系列 | 規模與 UX 最複雜，需要總覽卡 + 子卡 + 分批 |
| 6 | 6.4 換版本 | 不可逆 + 資料缺口多，延後 |
| — | 6.5 | 併入巡檢 |

---

## 7. 開放問題（本次沒查證）

1. TMDB `discover/tv` 的 `sort_by=popularity.desc` 與 `with_keywords=210024` 在「當季日本動畫」上的實際召回與雜訊（沒有 key，未實打）。
2. Jikan 的現況可用性（本機連線失敗）。
3. Fribb 倉庫授權條款，以及與 Anime-Lists（ScudLee）的實際差異。
4. Brave 免費額度的真實數字（官網兩處說法不同：$5 / 月 vs "up to $20"）。
5. Anthropic `web_fetch` 的計費（文件說除 token 外是否另計，本次沒抓到）。
6. Trakt 建 app 的現行規則（開發者文件說 GitHub 驗證，論壇說 VIP）。
7. `search.SearchResult` 是否已帶做種數（5.3）。

---

## 來源

TMDB
- Discover TV：https://developer.themoviedb.org/reference/discover-tv（OpenAPI：`/reference/discover-tv.md`），2026-10-27
- Recommendations / Similar / Trending / Keywords / Collection details / Details：`https://developer.themoviedb.org/reference/{tv-series-recommendations,tv-series-similar,trending-tv,tv-series-keywords,collection-details,tv-series-details}.md`，2026-10-27
- On the Air：https://developer.themoviedb.org/reference/tv-series-on-the-air-list，2026-10-27
- Watch providers（JustWatch 標示要求）：https://developer.themoviedb.org/reference/tv-series-watch-providers，2026-10-27
- Rate limiting：https://developer.themoviedb.org/docs/rate-limiting，2026-10-27
- Re:Zero TV：https://www.themoviedb.org/tv/65942-re-zero-starting-life-in-another-world（含 `/seasons`、`/episode_groups`），2026-10-27
- Re:Zero Collection：https://www.themoviedb.org/collection/689287-re ；Memory Snow https://www.themoviedb.org/movie/532321-re-memory-snow ；Frozen Bond https://www.themoviedb.org/movie/566451-re ，2026-10-27
- Anime keyword：https://www.themoviedb.org/keyword/210024-anime ；論壇 https://www.themoviedb.org/talk/628b76ac5cea184d122c137e ，2026-10-27
- repo 快照：`tests/fixtures/tmdb/tv-65942.json`

動漫來源
- AniList 速率：https://docs.anilist.co/guide/rate-limiting ；條款：https://docs.anilist.co/guide/terms-of-use ；GraphQL 文件（context7 `/anilist/docs`）；實打 `https://graphql.anilist.co`，2026-10-27
- Bangumi：實打 `https://api.bgm.tv/calendar`、`/v0/subjects/140001`、`/v0/subjects/140001/subjects`、`/v0/subjects/261805`、`/v0/subjects/225462`、`/search/subject/…`；User-Agent 規範 https://raw.githubusercontent.com/bangumi/api/master/docs-raw/user%20agent.md ；授權 https://github.com/bangumi/api/blob/master/docs-raw/How-to-Auth.md ，2026-10-27
- Jikan：https://docs.api.jikan.moe/ ；https://github.com/jikan-me/jikan-rest/issues/221 ；https://jikanpy.readthedocs.io ，2026-10-27（限流數字各處不一致）
- Fribb/anime-lists：https://github.com/Fribb/anime-lists ；`anime-list-full.json` 2026-10-27 下載分析，倉庫最後提交 2026-10-20
- Wikipedia Re:Zero season 4：https://en.wikipedia.org/wiki/Re:Zero_season_4 ；Radio Times：https://www.radiotimes.com/tv/fantasy/anime/rezero-starting-life-in-another-world-season-4-part-2-release-schedule
- Beatrice-Raws：https://beatrice-raws.org/release/beatrice-raws-re-zero-kara-hajimeru-isekai-seikatsu-hyouketsu-no-kizuna-the-frozen-bond-bdrip-1920x1080-hevc-flac-1080p ；https://beatrice-raws.org/release/beatrice-raws-re-zero-kara-hajimeru-isekai-seikatsu-shin-henshuu-ban-directors-cut-bdrip-1920x1080-hevc-flac-1080p ，2026-10-27
- Nyaa 搜尋：https://nyaa.si?f=0&c=0_0&q=re%3Azero ，2026-10-27（僅搜尋摘要）

一般劇集
- Trakt：https://developer.trakt.tv/docs/rate-limiting ；https://developer.trakt.tv/docs/create-an-app ；https://app.trakt.tv/terms ；https://forums.trakt.tv/t/failure-to-register-an-api/116157 ；https://forums.trakt.tv/t/an-update-to-community-app-connections/117898 ，2026-10-27
- IMDb：https://developer.imdb.com/documentation/ ；https://developer.imdb.com/non-commercial-datasets/ ，2026-10-27
- 豆瓣：https://m.douban.com/group/topic/140630769 ；https://feizhaojun.com?p=3813 ，2026-10-27

搜尋工具
- Anthropic web search：https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool ；web fetch：https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool ；模型與平台可用性：claude-api skill 的 Server Tools 表，2026-10-27
- Tavily：https://docs.tavily.com/documentation/api-credits ；https://docs.tavily.com/documentation/mcp ，2026-10-27
- Brave：https://brave.com/search/api/ ，2026-10-27
- Exa：https://exa.ai/pricing ，2026-10-27
- SearXNG：https://docs.searxng.org/admin/searx.limiter.html ；https://github.com/searxng/searxng/discussions/3542 ；https://docs.litellm.ai/docs/search/searxng ；https://you.com/resources/searxng-alternatives ，2026-10-27

repo 內
- `docs/design-brief.md` §20.3、§20.4、§20.12、§20.21；`docs/plan.md` §11.6；`docs/research/anime-episode-source.md`、`rss-sources.md`；`docs/research/m5-ai-direction-2026-10-27/05-human-touchpoints.md`；`berth/adapters/tmdb/client.py`；`berth/services/{discover,search,bangumi,rss,inventory,duplicates,issues,jobs}.py`
