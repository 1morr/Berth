# 搜尋結果的篩選、查詢寫法與季記號

從 design-brief §20.16、§20.19、§20.20、§20.21 搬來（原文不改字）。

### 20.16 搜尋結果怎麼用年份與類型篩：Radarr 與 Sonarr（2026-10-07 查證，M4 票 49）

- **Radarr 要年份完全相同，但認兩個年份**：`movie.Year == year || movie.MovieMetadata.Value.SecondaryYear == year`（`AllWithYear`），標題的每一種比對（clean、原文、別名、翻譯）都套這一條；互動搜尋的 `TryGetMovieBySearchCriteria` 同一個判準：`parsedMovieInfo.Year < 1800 || …Year == … || …SecondaryYear == …`。**發佈名沒有年份照收**（`Year < 1800` 那一條放行，只比標題）。【`src/NzbDrone.Core/Movies/QueryExtensions.cs`、`Parser/ParsingService.cs`，[Radarr develop](https://github.com/Radarr/Radarr/tree/develop/src/NzbDrone.Core)，2026-10-07 讀】
- **Radarr 沒有「這是劇集的一集」那一道**：`Parser.ParseMovieTitle` 不看季集，`Show.S01E02` 被拒是因為標題對不上（`UnknownMovie`），不是因為 `S01E02`。Berth 的粗篩只看「名字出現在發佈名裡」（`mentions`），《Below Deck Down Under S04E02 Night of the Living Dead》過得了那一道，所以電影要另外擋季集記號。
- **Sonarr 不以年份拒絕**：`FindByTitle(TitleWithoutYear, Year)` 只在純標題找不到時才拿年份來分同名劇（`Parser/ParsingService.cs`，[Sonarr develop](https://github.com/Sonarr/Sonarr/tree/develop/src/NzbDrone.Core)）。也沒有「這是電影」那一道。
- **Berth 的做法**（`parser.title.fits`）：年份容許差一年，代替 Berth 快照沒有的「第二年份」（影展與各國上映跨年）；劇集的年份範圍是首播年到最後一季的首播年（各放寬一年），只擋播出期間之外的（《Doctor Who》1963 與 2005 是兩部）；片名自己帶的數字（`Blade Runner 2049`）不算年份。劇集**不**擋沒有季集記號的：`Title - 05`、`[01-12]` 是動漫的常態，`Movie` 又可能是 S00（§6.3 `special_kind`）。篩掉的收著不丟，畫面說數量、可展開（判斷只看發佈名，可能看錯）。

### 20.19 搜尋的年份、片名裡的 `&` 與成人分類（2026-10-10 查證，M4 票 69）

- **TMDB 的 `search/multi` 沒有年份參數**：只收 `query`、`include_adult`、`language`、`page`；搜「Nosferatu 1922」是把整串字當片名比，0 筆（2026-10-10 實測兩次，M4 票 69、85）。帶年份的是分開的兩支：`search/movie` 有 `year` 與 `primary_release_year`，`search/tv` 有 `year`（「Search the first air date and all episode air dates」）與 `first_air_date_year`（「Search only the first air date」）。【[search-movie](https://developer.themoviedb.org/reference/search-movie)、[search-tv](https://developer.themoviedb.org/reference/search-tv)、[search-multi](https://developer.themoviedb.org/reference/search-multi)，2026-10-10 讀】
- **Jellyseerr 帶年份時用 `primary_release_year` 與 `first_air_date_year`**（`server/api/themoviedb/index.ts` 的 `searchMovies` / `searchTvShows`），但它的一般搜尋（`server/routes/search.ts`）不從字串拆年份，直接 `searchMulti`。【[jellyseerr develop](https://github.com/fallenbagel/jellyseerr/tree/develop/server)】
- **Berth 的做法：不用帶年份的那兩支**（M4 票 85，使用者拍板，推翻票 69 的年份拆分）。探索搜尋與 Jellyseerr 的一般搜尋一樣，打的字整串原樣問 `search/multi`，結尾的數字不拆成年份。理由：使用者搜尋時不加年份，同名不同年的作品看卡片上的年份就認得出來；而拆開問會把片名本身以數字結尾的作品擠掉——票 69 的做法下「Space 1999」拆成 `space` 與 1999 年，帶 1999 年的那兩支回 24 部別的 Space 片、沒有它（它 1975 年首播），票 69 只在那兩支沒有東西時才問原字串，所以找不到它；兩種都問、合併的版本把它排到第 25 筆（2026-10-10 實測）。代價是「Nosferatu 1922」0 筆；搜「Nosferatu」列得出 1922、1979、2024 各年的那幾部。上面兩條事實留著，要做年份篩選時從這裡起。
- **Sonarr / Radarr 送查詢前把 `&` 換成 `and`**：`SearchCriteriaBase.GetCleanSceneTitle` 是 `cleanTitle.Replace("&", "and")`，再把非字元換成 `+`，所以《Law & Order》送出去是 `Law+and+Order`；**取代**，不另外多問一組。兩邊的這一支逐行相同。比對用的 clean title（`Parser.CleanSeriesTitle` / `CleanTitle`）用 `NormalizeRegex` 把 `a`、`an`、`the`、`and`、`or`、`of`（不在頭尾時）與所有非字元一起刪掉，所以 `Law & Order` 與 `Law and Order` 清成同一串 `laworder`。【`src/NzbDrone.Core/IndexerSearch/Definitions/SearchCriteriaBase.cs`、`Parser/Parser.cs`，[Sonarr develop](https://github.com/Sonarr/Sonarr/tree/develop/src/NzbDrone.Core)、[Radarr develop](https://github.com/Radarr/Radarr/tree/develop/src/NzbDrone.Core)，2026-10-10 讀】
- **兩種站各認一種寫法**（2026-10-10 實測）：The Pirate Bay（經 Prowlarr）對 `Law & Order` 回 0 筆、對 `Law and Order` 回 100 筆；Mikan 的 RSS 搜尋對 `TIGER & BUNNY` 回 81 筆、對 `TIGER and BUNNY` 回 0 筆（`Spice & Wolf` 與 `Spice and Wolf` 都是 100 筆）。字幕組照官方的拉丁字片名寫 `&`，scene 寫 `and`。
- **Berth 的做法**（`parser.title.spell_ampersand`、`services/search_queries.py` 的 `_spellings`）：**不照 Sonarr 只送寫開的**——那會丟掉 Mikan 那一邊。有 `&` 的名字原樣問一次、再問寫成 `and` 的一次，兩者各配開了的季（M4 票 84 起名字與季由人開關，`&` 這一個照舊自動多一個、列在預覽裡，算進一次搜尋的上限 `MAX_QUERIES`）。有 CJK 字的名字不換。比對不學 Sonarr 刪掉每一個 `and`（`Pride and Prejudice` 的發佈名照舊要寫出 `and`），只替帶 `&` 的名字多認一種寫開的寫法。
- **Newznab 的成人分類是 6000–6090**：Prowlarr `NewznabStandardCategory` 的 `XXX = 6000` 與子分類 `XXX/DVD` 6010 到 `XXX/WEB-DL` 6090。搜尋結果的 `categories` 帶站定義映射到的標準碼加 `100000 + 站碼` 的自訂碼（`IndexerCapabilitiesCategories.MapTrackerCatToNewznab`），標準碼是定義檔寫的那一個、不自動補父分類。The Pirate Bay 的定義把 Porn 各類映射到 `XXX`、`XXX/x264`、`XXX/Other` 等（`definitions/v11/thepiratebay.yml`）。【[Prowlarr develop](https://github.com/Prowlarr/Prowlarr/tree/develop/src/NzbDrone.Core/Indexers)、[Prowlarr/Indexers](https://github.com/Prowlarr/Indexers/blob/master/definitions/v11/thepiratebay.yml)，2026-10-10 讀；回應的形狀沒有實際呼叫驗證，錄製的 `search.*.json` 裡沒有成人類】
- **Berth 的做法**（`services/search.py` 的 `ADULT_CATEGORIES`）：分類碼落在 6000–6999 的歸成「成人分類」（M4 票 83 起是 Search Verdict 的一類），不丟。分類碼不拿來查（plan §8.4：各站映射自訂），拿來歸類是因為歸錯了按一下就看得到（畫面預設只列「符合」，其他類照樣送）；沒有映射成人類的站（多數動漫站）擋不到，那時只剩發佈名。

### 20.20 搜尋結果怎麼說出「為什麼不像這部作品」：Sonarr 的互動搜尋（2026-10-10 查證，M4 票 83）

- **被拒的發佈照樣列出**：`ReleaseController.GetEpisodeReleases` 把 `EpisodeSearch` 的每一個 decision 都 `MapDecisions` 回傳，
  不濾掉被拒的；被拒的那一列在 rejected 欄一個紅色圖示，`Popover`（標題 `ReleaseRejected`）逐條列出 `rejections` 字串。後端與
  畫面都**沒有筆數上限**，上限只在索引站的分頁（Newznab `PageSize = 100`）。
  【`src/Sonarr.Api.V3/Indexers/ReleaseController.cs`、`frontend/src/InteractiveSearch/InteractiveSearchRow.tsx`、
  `src/NzbDrone.Core/Indexers/Newznab/NewznabRequestGenerator.cs`，[Sonarr v4.0.20.3014](https://github.com/Sonarr/Sonarr/tree/v4.0.20.3014)，2026-10-10 讀】
- **預設篩選是「全部」**：預先定義的篩選只有 `all`、`season-pack`、`not-season-pack`（`selectedFilterKey: 'all'`）；要藏起被拒的
  得自建 `rejectionCount EQUAL 0`。自訂篩選的欄位有 `indexerId`（只看某個站）、`rejectionCount`、`quality`、`seeders` 等。
  【`frontend/src/Store/Actions/releaseActions.js`，同上】
- **片名比對是「季集記號前面那一段」清過之後完全相等**：`ParsingService.FindSeries` 在有 `searchCriteria` 時比
  `searchCriteria.Series.CleanTitle == parsedEpisodeInfo.SeriesTitle.CleanSeriesTitle()`（不是包含），再退到 tvdbId / imdbId；
  `SeriesTitle` 是 `Parser.ParseTitle` 取季集記號前面那一段。找到的是別部是 `Wrong series`
  （`DecisionEngine/Specifications/Search/SeriesSpecification.cs`），整庫都找不到是 `Unknown Series`
  （`DecisionEngine/DownloadDecisionMaker.cs`）。所以搜《Law & Order》回來的 `Law.and.Order.SVU.S28E01` 片名清成
  `laworder svu` 一類，與 `laworder` 不等而被拒（讀程式推得，沒有實跑）。Radarr 的對應是 `Wrong movie` 與
  `Unknown Movie. Unable to match to correct movie using release title.`，年份不符沒有獨立的拒絕字串。
  【`src/NzbDrone.Core/Parser/ParsingService.cs`，同上；[Radarr develop](https://github.com/Radarr/Radarr/tree/develop/src/NzbDrone.Core)】
- **Berth 的做法**（`services/search.py` 的 `_judge`、`parser.title.misfit` / `partial_title`，`.scratch/m4/search-filter-shape.md`）：
  照 Sonarr 每一筆都送、每一筆說得出理由；不同的是**一筆一類、一句話**（判斷是排了先後的粗篩：名字對不上 → 成人分類 → 不是電影
  → 年份不符 → 只對上部分名字 → 符合），**畫面預設只開「符合」**（The Pirate Bay 對查不到的字回熱門清單，全開等於沒篩），
  每類各有上限（符合 100、其餘 50，逐站輪流取）。「只對上部分名字」照 Sonarr 取第一個記號（季集、字幕組集號、年份）前面那一段，
  但先照 `/`、`|`、括號與文字系統（CJK／非 CJK）切成一個一個名字再比——字幕組把中文名與拉丁字名寫在一起（`SPY×FAMILY 間諜家家酒 - 05`），
  整段比的話每一筆都像衍生劇。有一個名字相等就算這一部，沒有相等但有一個包住這部作品的名字才算「部分」；讀不出記號時不判。
- **自己打關鍵字的搜尋**（2026-10-14 補查，M4 票 83b）：Prowlarr 的手動搜尋頁就是打字搜，預先定義的篩選只有 `all`
  （`selectedFilterKey: 'all'`），自訂篩選的欄位有 `title`（使用者自己填的字串比較）、`indexerId`、`seeders` 等，**沒有拿發佈名比對
  查詢的判斷**——The Pirate Bay 的熱門清單在它那裡一樣全列。【`frontend/src/Store/Actions/releaseActions.js`，
  [Prowlarr develop](https://github.com/Prowlarr/Prowlarr/blob/develop/frontend/src/Store/Actions/releaseActions.js)，2026-10-14 讀】
  Berth 推翻票 83 的「自己打的關鍵字一律 `unjudged`、不分類」：只分**對得上**（`typed_match`：正規化後發佈名含打的那串字，或含這部作品的
  某個名字——後者補繁簡，專案沒有轉換）與**對不上**（`typed_miss`），預設只開對得上；仍不判是不是這部作品（票 08 的理由）。有 CJK 的字串
  不設長度下限，不到四個字的拉丁字要整詞相等（`parser.typed_fits`，`.scratch/m4/search-typed-filter-shape.md`）。`unjudged` 拿掉：
  沒有快照時只看打的字，照作品名搜沒有快照時根本沒有查詢。

### 20.21 季的搜尋記號：`Season N` 與 `SNN` 實跑比較（2026-10-13 實測，M4 票 84）

腳本 `scripts/experiments/season_token_compare.py`，隔離的 Prowlarr（The Pirate Bay、Mikan、dmhy；Nyaa 與 YTS 那天從容器連不上），
每一對查詢逐站數「總筆數 / 發佈名真的含那部作品名字的筆數」（The Pirate Bay 對查不到的字回熱門清單，純筆數會騙人）：

| 查詢 | The Pirate Bay | Mikan | dmhy |
| --- | --- | --- | --- |
| `The Bear Season 3` | 23 / 11 | — | — |
| `The Bear S03` | 6 / 6 | — | — |
| `Severance Season 2` | 4 / 4 | — | — |
| `Severance S02` | 11 / 11 | — | — |
| `SPY x FAMILY Season 2` | 21 / 21 | 189 / 162 | 80 / 56 |
| `SPY x FAMILY S02` | — | 2 / 2 | 2 / 2 |
| `Frieren Season 2` | 1 / 1 | 114 / 114 | 75 / 75 |
| `Frieren S02` | — | 11 / 11 | 11 / 11 |
| `Oshi no Ko Season 2` | 1 / 1 | 47 / 47 | — |
| `Oshi no Ko S02` | — | 8 / 7 | — |
| `间谍过家家 第2季` | 100 / 0 | — | — |
| `间谍过家家 S02` | — | 1 / 1 | — |

- **美劇 `SNN` 比較準**：The Pirate Bay 對 `The Bear Season 3` 回的名字對得上的 11 筆裡只有 3 筆寫 `S03`，其餘是別季；
  `The Bear S03` 的 6 筆全是第三季。`Severance S02` 11 筆、`Season 2` 4 筆。
- **動畫站的 `SNN` 少一個數量級**：Mikan、dmhy 對 `Season 2` 是寬鬆比對，`SPY x FAMILY Season 2` 在 Mikan 回的 162 筆名字對得上
  的裡有 90 筆發佈名真的寫 `Season 2`（只有 1 筆寫 `S02`），`S02` 只回 2 筆。字幕組寫的是 `Season 2`、`第2季`，不是 scene 的 `S02`。
- **Berth 的做法**（`parser.title.season_tokens`）：照票面「`SNN` 比較少就兩種都留」，**拉丁字名字一季問 `S03` 與 `Season 3`
  兩個**，有 CJK 字的名字問 `第3季`；按搜尋與搜缺的集共用這一個函式。一次搜尋的上限因此從 5 個改成 10 個（使用者 2026-10-13
  拍板）：動畫的英文名、原名配「不指定季」與最新一季是 6 個，再開兩種中文名是 10 個。CJK 那一對兩邊都只有 0–1 筆，樣本太小，只當參考。
