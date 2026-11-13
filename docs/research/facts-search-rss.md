# 事實：搜尋、索引站與 RSS

查證過的外部事實。編號沿用 brief 原本的節號（`§20.x`），程式碼與文件用它引用，編號不重用。索引在 [brief §20](../design-brief.md)。

## 事實

### 20.10 Sonarr 怎麼替一集組查詢（2026-09-19 查證）

缺集一鍵搜（M1.5 票 10）要決定「缺一集時拿什麼字去問」，採用的是 Sonarr 的慣例：

- Sonarr 的 Newznab / Torznab 請求把季集放在**結構化參數**上（`&season=<n>&ep=<n>`），標題只放 `q=`。
- **只有動漫的絕對編號是接在關鍵字後面的**：`&q={NewsnabifyTitle(queryTitle)}+{searchCriteria.AbsoluteEpisodeNumber:00}`
  ——絕對編號補零到兩位，與標題之間一個空白。
  【來源：`Sonarr/src/NzbDrone.Core/Indexers/Newznab/NewznabRequestGenerator.cs`，develop 分支，2026-09-19 讀】
- Berth 的搜尋 adapter（Prowlarr 的 REST；M4 票 37 前另有 Torznab 的 `t=search`）只送 `q=`，plan §8.4「分類碼不送」同一個理由：
  各站對結構化參數的支援與映射不一致，而 Berth 打的是公開站），所以季集一律進關鍵字：整季 `S03`、
  單集 `S03E05`、有絕對編號的 `26`。

### 20.11 發佈時間：索引站與 RSS（2026-09-24 查證）

播出日比對（M3 票 14）與之後可能的「發佈離播出多近」都要一個發佈時間。試跑環境（Prowlarr 預設公開站）實測：

- **Prowlarr 搜尋結果每一筆都有 `publishDate`**（ISO 8601、UTC），缺值 0（搜「Kamiina Botan」534 筆，五個站的筆數見研究檔）。Berth 的 adapter 解析成 `published_at`（`adapters/indexer/prowlarr.py`；M4 票 37 前另有 `torznab.py`，Torznab 的 `pubDate` 是 RFC 822）。**M3 票 14 起接上**：搜尋結果帶 `published_at`、送單存進 `jobs.published_at`，規劃時做播出日比對（plan §4.4）。【實測；原文在 [`publish-time-indexers-and-rss.md`](publish-time-indexers-and-rss.md)】
- **ACG.RIP 的 RSS** 是標準的 `<item><pubDate>`，RFC 822 帶時區（`Thu, 24 Sep 2026 06:01:00 -0700`）。【實測 `https://acg.rip/.xml`】
- **Mikan 的 RSS 沒有標準的 `<item><pubDate>`**：日期在 `https://mikanani.me/0.1/` 命名空間的 `<torrent><pubDate>`，ISO 8601 **不帶時區**（`2026-09-24T21:01:00.760219`）。同一個發佈在 ACG.RIP 是 13:01 UTC，所以 Mikan 的值是 **UTC+8**；當成 UTC 讀會差 8 小時。【實測 `https://mikanani.me/RSS/Classic`，與 ACG.RIP 同一筆對照】
- Nyaa 的 RSS 從試跑機器連不上（連線失敗），沒有量到。**2026-09-25 補量**（§20.12）：`<pubDate>` 是 RFC 822 的 `-0000`，即 UTC。
- **發佈時間是「這一筆條目」貼出的時間，不是這一集的首發**：重新上傳、合集、聚合站晚收錄都會讓它偏晚。它只保證那一集在某處已經播出，不一定是 TMDB 記的電視台：平台先行時發佈比 TMDB 的播出日早一週（§20.27），所以規則一對照字面的讀法容忍九天、有換算的兩天（plan §4.4）。它適合當下限，不適合量「多新」（SubsPlease《上伊那牡丹》01–12 合集在 Anime Tosho 是 2026-08-15，TMDB 第一季末集 2026-06-27）。【實測】

### 20.12 RSS 來源的欄位（2026-09-25 查證，M3 票 07）

完整的欄位表、範例原文與逐條來源在 [`docs/research/rss-sources.md`](rss-sources.md)；
fixture 在 `tests/fixtures/http/{mikan,nyaa,acgrip}/`（來源網址與去掉 token 的方式見同目錄 README）。以下只留結論。

**2026-09-24 試跑時的五條實測**（2026-09-25 的 fixture 都重現了，[§10](rss-sources.md)）：

- **Mikan 聚合 feed（`/RSS/MyBangumi?token=`）只有最近的集數**：12 筆、跨 6.6 天，同一部作品 × 字幕組只剩最近兩集。
- **單集頁反查得到番組 id 與字幕組 id**：`/Home/Episode/<hash>` 頁上的 `a.mikan-rss` 就是 `/RSS/Bangumi?bangumiId=…&subgroupid=…`；feed 本身不帶，所以聚合 feed 的每一筆第一次出現都要多抓一次單集頁（[§2.7](rss-sources.md)）。
- **單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`）有整季**：4009 × 370 的 01–12 都在。
- **三站都沒有標示合集的欄位**，只能看標題；acg.rip 搜尋 feed 30 筆裡 8 筆是合集，Nyaa 75 筆裡 14 筆（[§6](rss-sources.md)）。
- **Nyaa 從開發機連不上**（TLS 握手失敗；Mikan、acg.rip 同時 200），瀏覽器連得上；部署環境連不連得上取決於使用者的網路（[§3.5](rss-sources.md)）。

**三站的欄位**（逐欄對照在研究檔 §9）：

- **guid**：Mikan 的 `<guid isPermaLink="false">` **就是標題**，改標題會跟著變，不能拿來去重；Nyaa 是 `https://nyaa.si/view/<id>`，acg.rip 是 `https://acg.rip/t/<id>`。
- **info hash**：Mikan 的 `link`（`/Home/Episode/<40 hex>`）與 enclosure 檔名末段就是（124/124 筆一致，§2.3）；Nyaa 有 `nyaa:infoHash`；acg.rip **沒有**，只能下載 `.torrent` 算。
- **torrent / magnet**：Mikan、acg.rip 是 `<enclosure type="application/x-bittorrent">`、都沒有 magnet；Nyaa 沒有 enclosure，`<link>` 是 `.torrent`（`&m` 時換成 magnet）。
- **大小**：Mikan 的 `contentLength` 與 enclosure `length` **不是位元組**（多出約 5%），描述後綴 `[518.65 MB]` 比較準；Nyaa 是人類可讀字串（`240.5 MiB`）；acg.rip 的 `torrent:contentLength` 是位元組。三站都只當顯示用的近似值（§2.4）。
- **發佈時間**：Mikan 的 `https://mikanani.me/0.1/` 命名空間 `<torrent><pubDate>` 是 ISO 8601 **不帶時區、實際是 UTC+8**（同一筆在 acg.rip 對照差 +7:59:59），小數秒 0、3、6 位都有；Nyaa 是 RFC 822 `-0000`（UTC）；acg.rip 是 RFC 822 `-0700`（§5）。
- **做種數**：只有 Nyaa 有（`nyaa:seeders` / `leechers` / `downloads`）。

**feedparser 6.0.14**（2026-07-30，PyPI 最新）三站都讀得動、不丟欄位，但 Mikan 有兩處會安靜地讀錯：`published_parsed` 把不帶時區的 `<torrent><pubDate>` 當 UTC（差 8 小時，要讀 `published` 字串自己補 UTC+8）；`<torrent>` 的命名空間被抹掉（`pubDate` → `published`、`link` 變成第二個 `links`），哪天 Mikan 加上標準的 `<item><pubDate>` 會撞名（[§7](rss-sources.md)）。【實測 fixture；context7 `/kurtmckee/feedparser`】

**Mikan 的番組搜尋**（2026-09-26 查證，M3 票 19）：`/Home/Search?searchstr=<詞>` 回整頁 HTML（1–4 MB、約 1.5 秒），結果在 `ul.an-ul` 連到 `/Home/Bangumi/<id>` 的 `<a>`。**英文、羅馬字、日文、繁中都搜得到**：`Frieren`、`Sousou no Frieren`、`葬送のフリーレン`、`葬送的芙莉蓮` 四種寫法都回同樣兩個番組（3141、3821）。番組頁左欄 `a.subgroup-name.subgroup-<字幕組 id>` 是字幕組名、緊接的 `span.date` 是最近一次發佈（M/D/YYYY）。【[原文](rss-sources.md#從-brief-搬來2012)；fixture `home-search.frieren.html`、`home-bangumi.4009.html`】

**Mikan 的番組頁**（`/Home/Bangumi/<id>`）有中文標題、「放送开始」（`M/D/YYYY`）與 bgm.tv 連結，選擇器在研究檔 §2.7。字幕組 id（`subgroupid=370`）與單集頁上的發佈組 id 不是同一套編號。

**Mikan 的番組是 cour，TMDB 的季可能是好幾輪播出併成的**（2026-09-26 查證，M4 票 14）：Re:Zero 第四季的第二個 cour 在 Mikan 是另一個番組（4052，放送开始 8/12/2026），而 TMDB 65942 把四季 85 集全放第 1 季（第四季是第 67–77 集與停播 56 天後的第 78–85 集）；發佈名只寫「第四季」、不寫篇名。所以自動綁定的季號線索要比那一季**播出的期間**，不能只比首播（§15「綁定」）。【[原文與量測](rss-sources.md#從-brief-搬來2012)、§2.8】

**跨 feed 以 info hash 去重：做，不多發請求**（plan §8.5）。Mikan 與 Nyaa 在輪詢時就有 hash；acg.rip 不預抓 `.torrent`，送單時 `TorrentFetcher` 本來就要下載並算 hash，`jobs.hash` 是主鍵。**未證實**：同一個發佈在 Mikan 與 acg.rip 是不是同一個 info hash；不同的話由帳本「同 Media / 季 / 集 / Tags」那一層擋。

**排除條件的格式照 Sonarr 的 release profile**（2026-09-25 查證，M3 票 10）：每一條是字詞、不分大小寫；要正則寫成 `/regex/`（預設分大小寫，`/regex/i` 不分）。【[Servarr Wiki：Sonarr Settings › Release Profiles](https://wiki.servarr.com/sonarr/settings)】Berth 照搬（`parser.exclusion`），比對整個標題。

### 20.13 公開站的請求限制：Prowlarr、Sonarr、AutoBangumi 的慣例（2026-09-26 查證，M3 票 20）

研究檔 [`docs/research/request-budget.md`](request-budget.md)，逐條附原始碼或文件連結。M3 票 20 照這幾條定了一個站一份的請求預算（已拿掉，[ADR-0014](../adr/0014-no-site-request-budget.md)）；**M4 票 107 整個拿掉**（[ADR-0014](../adr/0014-no-site-request-budget.md)、plan §3.2），最後一條是拿掉的主要理由：

- **Prowlarr 的 Query Limit 是滾動窗**（[§1](request-budget.md)）：數「過去 N 小時」的歷史（`Limits Unit` 只有 `Hour` 與預設的 `Day`），**RSS 與查詢算在同一份**，打滿時那一站那一次跳過；Grab Limit 是另一份。預設不限，要使用者自己填。
- **Cardigann 定義的請求間隔**（[§2](request-budget.md)）：只有 `nyaasi.yml` 有 `requestDelay: 2`；`mikan.yml`、`dmhy.yml`、`acgrip.yml` 都沒有。
- **輪詢間隔**（[§3、§4](request-budget.md)）：Sonarr 的 RSS Sync Interval 10–120 分鐘（預設值查不到，社群慣用 15 分鐘）；AutoBangumi 的 `rss_time` 預設 900 秒，輪 Mikan 聚合 feed。FreshRSS 每個 Feed 各自設間隔、下限 15 分鐘（[Refreshing feeds](https://freshrss.github.io/FreshRSS/en/users/09_refreshing_feeds.html)）；Berth 照它每個 Feed 各自設、只收固定檔位（M4 票 109）。
- **出錯退避是另一回事**：Sonarr 的 `EscalationBackOff` 0 秒 → 1 分 → … → 24 小時逐級加重，與配額分開計時。
- **Berth 的搜尋曾照「那一站那一次跳過」**（M4 票 77）；票 107 之後搜尋問全部的站，各站的配額交給 Prowlarr 自己的 Query Limit（使用者看得到、調得了）。
- **三站都沒有公開的限速或封鎖事故紀錄**（[§5](request-budget.md)；Nyaa 只有 2 秒間隔的間接證據）。票 20 的「每站每小時 60 個」因此不是量出來的，是照 Berth 的用量推的；實際擋到人的只有 Berth 自己的計數（票 77），所以票 107 拿掉。

### 20.16 搜尋結果怎麼用年份與類型篩：Radarr 與 Sonarr（2026-10-07 查證，M4 票 49）

來源：[Radarr develop](https://github.com/Radarr/Radarr/tree/develop/src/NzbDrone.Core)、[Sonarr develop](https://github.com/Sonarr/Sonarr/tree/develop/src/NzbDrone.Core)（`Movies/QueryExtensions.cs`、`Parser/ParsingService.cs`）；原文在 [`docs/research/search-results.md`](search-results.md)。

- **Radarr 年份要完全相同，但認 `Year` 與 `SecondaryYear` 兩個**；發佈名沒有年份照收（`Year < 1800` 放行，只比標題）。
- **Radarr 沒有「這是劇集的一集」那一道**：`Show.S01E02` 被拒是因為標題對不上。Berth 的粗篩只看 `mentions`，所以電影要另外擋季集記號。
- **Sonarr 不以年份拒絕**（只在純標題找不到時用年份分同名劇），也沒有「這是電影」那一道。
- **Berth 的做法**（`parser.title.fits`）：年份容許差一年，代替沒有的「第二年份」；劇集年份範圍是首播年到最後一季首播年（各放寬一年）；片名自帶的數字（`Blade Runner 2049`）不算年份。劇集**不**擋沒有季集記號的（`Title - 05`、`[01-12]` 是動漫常態，`Movie` 又可能是 S00，§6.3 `special_kind`）。篩掉的收著不丟，畫面說數量、可展開。

### 20.19 搜尋的年份、片名裡的 `&` 與成人分類（2026-10-10 查證，M4 票 69）

來源與完整原文：[`docs/research/search-results.md`](search-results.md)。外部：[TMDB search-multi](https://developer.themoviedb.org/reference/search-multi)、[search-movie](https://developer.themoviedb.org/reference/search-movie)、[search-tv](https://developer.themoviedb.org/reference/search-tv)；[Sonarr develop](https://github.com/Sonarr/Sonarr/tree/develop/src/NzbDrone.Core) `SearchCriteriaBase.GetCleanSceneTitle`；[Prowlarr develop](https://github.com/Prowlarr/Prowlarr/tree/develop/src/NzbDrone.Core/Indexers)。

- **TMDB `search/multi` 沒有年份參數**：「Nosferatu 1922」整串當片名比，0 筆（2026-10-10 實測兩次，M4 票 69、85）。帶年份的是 `search/movie`（`year`、`primary_release_year`）與 `search/tv`（`year`、`first_air_date_year`）。Jellyseerr 的一般搜尋也不拆年份，直接 `searchMulti`。
- **Berth 的做法：不用帶年份的那兩支**（M4 票 85，使用者拍板，推翻票 69 的年份拆分）。打的字整串原樣問 `search/multi`，結尾數字不拆成年份。理由：使用者搜尋不加年份，同名作品看卡片年份認；拆開問會擠掉片名以數字結尾的作品（「Space 1999」拆成 1999 年後回 24 部別的 Space 片、沒有它，兩種都問合併也只排第 25 筆，2026-10-10 實測）。代價是「Nosferatu 1922」0 筆；搜「Nosferatu」列得出各年份。要做年份篩選時從這裡起。
- **Sonarr / Radarr 送查詢前把 `&` 換成 `and`**（取代，不多問一組；兩邊逐行相同）：`Law & Order` 送出 `Law+and+Order`。比對用的 clean title 把 `and` 等與非字元刪掉，`Law & Order` 與 `Law and Order` 同為 `laworder`（2026-10-10 讀）。
- **兩種站各認一種寫法**（2026-10-10 實測）：The Pirate Bay（經 Prowlarr）`Law & Order` 0 筆、`Law and Order` 100 筆；Mikan RSS `TIGER & BUNNY` 81 筆、`TIGER and BUNNY` 0 筆。字幕組照官方拉丁字片名寫 `&`，scene 寫 `and`。
- **Berth 的做法**（`parser.title.spell_ampersand`、`services/search_queries.py` 的 `_spellings`）：**不照 Sonarr 只送寫開的**；有 `&` 的名字原樣問一次、再問寫成 `and` 的一次，各配開了的季（列在預覽裡，算進上限 `MAX_QUERIES`）。有 CJK 字的名字不換。比對不學 Sonarr 刪每個 `and`（`Pride and Prejudice` 照舊要寫 `and`）。
- **Newznab 成人分類是 6000–6090**（`XXX = 6000`，子分類 `XXX/DVD` 6010 到 `XXX/WEB-DL` 6090）；結果的 `categories` 帶標準碼加 `100000 + 站碼` 的自訂碼，不自動補父分類。The Pirate Bay 把 Porn 各類映射到 `XXX*`（`definitions/v11/thepiratebay.yml`）。2026-10-10 讀；回應形狀沒實呼叫驗證，錄製的 `search.*.json` 沒有成人類。
- **Berth 的做法**（`services/search.py` 的 `ADULT_CATEGORIES`）：分類碼落在 6000–6999 歸成「成人分類」（M4 票 83 起是 Search Verdict 的一類），不丟。分類碼不拿來查（plan §8.4：各站映射自訂），只拿來歸類（歸錯了按一下就看得到，畫面預設只列「符合」，其他類照樣送）；沒映射成人類的站（多數動漫站）擋不到，只剩發佈名。

### 20.20 搜尋結果怎麼說出「為什麼不像這部作品」：Sonarr 的互動搜尋（2026-10-10 查證，M4 票 83）

來源：[Sonarr v4.0.20.3014](https://github.com/Sonarr/Sonarr/tree/v4.0.20.3014)（`ReleaseController.cs`、`InteractiveSearchRow.tsx`、`releaseActions.js`、`ParsingService.cs`、`SeriesSpecification.cs`）、[Radarr develop](https://github.com/Radarr/Radarr/tree/develop/src/NzbDrone.Core)、[Prowlarr releaseActions.js](https://github.com/Prowlarr/Prowlarr/blob/develop/frontend/src/Store/Actions/releaseActions.js)；原文在 [`docs/research/search-results.md`](search-results.md)。

- **被拒的發佈照樣列出**：每個 decision 都回傳，被拒的一列紅圖示、Popover 逐條列 `rejections`；後端與畫面**沒有筆數上限**（只有 Newznab 分頁 `PageSize = 100`）。預設篩選是「全部」（`all`、`season-pack`、`not-season-pack`）。
- **片名比對是「季集記號前面那一段」清過之後完全相等**（不是包含）：`searchCriteria.Series.CleanTitle == SeriesTitle.CleanSeriesTitle()`，再退到 tvdbId / imdbId。找到別部是 `Wrong series`，整庫都找不到是 `Unknown Series`；`Law.and.Order.SVU.S28E01` 清成 `laworder svu`，與 `laworder` 不等而被拒（讀程式推得，沒實跑）。Radarr 對應 `Wrong movie` 與 `Unknown Movie. …`，年份不符沒有獨立拒絕字串。
- **Berth 的做法**（`services/search.py` 的 `_judge`、`parser.title.misfit` / `partial_title`，`.scratch/m4/search-filter-shape.md`）：照 Sonarr 每一筆都送、都說得出理由；不同的是**一筆一類、一句話**（粗篩先後：名字對不上 → 成人分類 → 不是電影 → 年份不符 → 只對上部分名字 → 符合），**畫面預設只開「符合」**（The Pirate Bay 對查不到的字回熱門清單），每類各有上限（符合 100、其餘 50，逐站輪流取）。「只對上部分名字」取第一個記號（季集、字幕組集號、年份）前面那一段，但先照 `/`、`|`、括號與文字系統（CJK／非 CJK）切成一個個名字再比；有一個名字相等就算這一部，沒有相等但有一個包住這部作品的名字才算「部分」；讀不出記號時不判。
- **自己打關鍵字的搜尋**（2026-10-14 補查，M4 票 83b）：Prowlarr 手動搜尋頁預設篩選只有 `all`，自訂篩選欄位有 `title`、`indexerId`、`seeders` 等，**沒有拿發佈名比對查詢的判斷**（The Pirate Bay 熱門清單照樣全列）。Berth 推翻票 83 的「自己打的關鍵字一律 `unjudged`」：只分**對得上**（`typed_match`：正規化後發佈名含打的字串，或含這部作品的某個名字，後者補繁簡）與**對不上**（`typed_miss`），預設只開對得上；仍不判是不是這部作品（票 08 的理由）。有 CJK 的字串不設長度下限，不到四個字的拉丁字要整詞相等（`parser.typed_fits`，`.scratch/m4/search-typed-filter-shape.md`）。`unjudged` 拿掉。

### 20.21 季的搜尋記號：`Season N` 與 `SNN` 實跑比較（2026-10-13 實測，M4 票 84）

腳本 `scripts/experiments/season_token_compare.py`，隔離的 Prowlarr（The Pirate Bay、Mikan、dmhy；Nyaa 與 YTS 當天連不上）；逐站數「總筆數 / 發佈名含作品名字的筆數」。完整比較表在 [`docs/research/search-results.md`](search-results.md)。

- **美劇 `SNN` 比較準**：`The Bear Season 3` 在 The Pirate Bay 名字對得上的 11 筆裡只有 3 筆寫 `S03`；`The Bear S03` 的 6 筆全是第三季。
- **動畫站的 `SNN` 少一個數量級**：Mikan、dmhy 對 `Season 2` 是寬鬆比對；`SPY x FAMILY Season 2` 在 Mikan 對得上的 162 筆裡 90 筆真寫 `Season 2`（1 筆寫 `S02`），`S02` 只回 2 筆。字幕組寫 `Season 2`、`第2季`，不是 `S02`。
- **Berth 的做法**（`parser.title.season_tokens`）：`SNN` 比較少就兩種都留——**拉丁字名字一季問 `S03` 與 `Season 3` 兩個**，有 CJK 字的名字問 `第3季`；按搜尋與搜缺的集共用這一個函式。一次搜尋上限因此從 5 改成 10（使用者 2026-10-13 拍板）：動畫的英文名、原名配「不指定季」與最新一季是 6 個，再開兩種中文名是 10 個。CJK 那一對兩邊都只有 0–1 筆，樣本太小，只當參考。
