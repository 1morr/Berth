# AI 對話精簡方案（2026-11-06，已審）

起因：試用機上一段真實對話（「幫我找想吃掉你的那個什麼動漫」，conversation `b0e4f028`）。
使用者要的方向：**skills 與工具簡潔、generic**，確認卡不要逐列重複問同一件事。
項目由使用者在 2026-11-06 的對話裡勾選（A1、A2、A4、B1–B4、C1–C4；A3 與 A4 衝突，放棄 A3）。
2026-11-06 審過，開工為 M5.6：規格與票在 `.scratch/m5.6/`，票序以 spec 為準（基準移到最前面，C3 拆兩張）。

## 1. 這段對話發生了什麼

5 分鐘、30 次工具呼叫，其中 18 次是 `search_search_torrents`。

| 時間 (UTC) | AI 做的事 | 工具 |
|---|---|---|
| 14:53:26 | 猜成《我想吃掉你的胰臟》，搜 TMDB | `discover_search_media` ×2 |
| 14:53:30 | 讀作品、查 Route、查 Jellyfin | `media_read_media`、`media_route_choices`、`inventory_find_in_library` |
| 14:53:33 | 使用者只說「找」，仍搜了種子 | `search_search_torrents` ×1 |
| 14:54:02 | 使用者更正後找到 `tv:274810`，讀作品、查 Jellyfin（沒有） | `discover_search_media` ×2、`media_read_media`、`inventory_find_in_library` |
| 14:54:09 | 載入 `missing-episodes`，診斷：13 集 `no_source` | `skills_load_skill`、`why_not_explain` |
| 14:54:13–43 | `scope` 搜一次，再用 7 種名字或關鍵字搜，列候選表，問字幕 | `search_search_torrents` ×8 |
| 14:55:29–58 | 使用者選「喵萌奶茶屋繁中單集」，01–09 每集各搜一次 | `search_search_torrents` ×9 |
| 14:55:58 | 13 列送單卡，每列 `route_id: 3` | `downloading_add_manual_download` |
| 14:56:02–57:44 | 使用者在卡上逐列選 Route（13 個下拉都選 Anime，無預選） | — |

看到的問題：

1. **卡片逐列問 Route**：13 列同一部作品，`preview.routes` 13 個 `RouteAsk`（TV / Anime），
   `preselected` 全是 `null`（這部作品沒送過單）。模型給的 `route_id` 依票 23b 不算數。
2. **`scope` 搜尋沒問到動畫站**（C2，已確認原因）：整季缺時查詢是「名字 × 季記號」，CJK 名字的
   季記號是「第1季」（`parser/title.py` `season_tokens`）。這次兩個查詢是
   `私を喰べたい、ひとでなし 第1季`、`想吃掉我的非人少女 第1季`，只有一季的番發佈名不寫
   「第1季」，動畫站零筆；回來的 216 列全是 TPB / YTS 的 `unrelated`。作品頁「搜缺的集」
   走同一段（`search_queries.missing_batches`），不只 AI 受影響。
3. **同一字幕組的單集要逐集搜**：給模型的結果只有前 10 列，加上之後「符合」而帶來新集數的列
   （`agent_tools._rows_to_show`）。`query` 搜的單集多半不算「符合」，被截掉，模型只好一集搜一次。
4. **還沒說要下載就搜種子**：猜錯作品那一輪白搜一次。

## 2. 現況盤點

- 系統指示 `services/agent.py` `INSTRUCTIONS`：約 1.7 KB，短，保留。
- skills 5 個、351 行、24 KB。重複段落：

  | 段落 | 出現次數 |
  |---|---|
  | 搜尋語言決定字幕語言、用原名 / 英文 / 中文（含簡體）搜 | 4 |
  | Route 取 `default_route_id`、不在對話問、卡片會讓人選 | 4 |
  | 卡片按下前不說做了、之後逐列回報 | 4 |
  | 「從媒體庫重建帳本」按鈕指引 | 3 |
  | `in_jellyfin` / `jellyfin_maybe` 的意思（工具說明也寫了） | 3 |

- 工具 22 支（`agent_tools.TOOLS`）。重疊：`media.route_choices` 與 `media.read_media` 的
  `routes`；兩條訂閱路徑（`bangumi.search/read` + `rss.subscribe_mikan`，或 `rss.subscribe_search`）
  要模型自己選。

## 3. 分層原則（這次精簡照它切）

| 放哪裡 | 放什麼 |
|---|---|
| 伺服器（命令、卡片） | 政策：Route 怎麼定、去重複、哪些要人選。模型不必知道就不給它 |
| 工具說明與輸出 | 怎麼解讀結果：結論的意思、狀態欄位 |
| 系統指示 | 跨任務的共同規則（只寫一次） |
| skill | 這類任務的決策順序。不重述上面三層，不點名特定作品，每個約 20–30 行 |

## 4. 改動

### A. 確認卡的 Route

**A1 同一部作品只問一次**：`ConfirmCard` 依 `media_id` 分組，每組一個 Route 選擇，套到那組勾著的
每一列。`decide` 的 `routes` 照舊逐列送（前端展開），API 不變。

**A2 卡片頂部「全部套用」**：一張卡有兩部以上作品、而且它們的可選 Route 有交集時，頂部多一個
選擇，選了就填進每一組（之後仍可逐組改）。

慣例：Sonarr / Radarr 的 Manual Import 對勾選的列提供整批設定（Series、Season、Quality），
不逐列重選。實作票開工時再對一次現行版本的畫面。

**A4 模型不再給 `route_id`**：
- `SubmitRow`、訂閱卡的列拿掉 `route_id`。伺服器在提出時定：可選的只有一條就用它，不只一條就
  `RouteAsk`（預選照舊 `default_route_id`），零條就拒絕（沿用現有的拒絕理由，票裡查定）。
- 刪 `media.route_choices` 工具。`media.read_media` 給模型的那一份拿掉 `routes`、
  `default_route_id`，說明跟著縮短。
- 四個 skill 的 Route 段落刪掉。
- 不動 `rss.add_feed` 的 `tv_route_id` / `movie_route_id`：那是 Feed 層的設定，不是一部作品的。
- 要注意：Proposal 存下的參數與雜湊（`proposals` 模組 docstring 第 3 點）在 Route 未定時怎麼存。

**放棄 A3**（預選 AI 給的或按類型預選）：做了 A1、A2 之後，每張卡最多選一次，下載過的作品還有
「上次用的」預選。預選 AI 給的，會回到票 23 實測的問題（模型不問就挑）；按類型預選要加 Route 的
「動畫預設」設定與 TMDB anime 判斷，範圍變大。之後真的要做，參考 Jellyseerr 的「Anime Root
Folder」（未查證）。

### B. 系統指示與 skills

**B1 共同規則進系統指示**（加在 `INSTRUCTIONS`，英文，草稿）：

```text
- Releases: the language of a search decides which subtitles come back (Chinese titles find
  mostly Chinese subtitles; English and original titles every language). Search under the
  original, English and the user's-language titles (for Chinese also the Simplified title most
  subgroups write); try romaji or one subgroup's spelling when results are thin. Rows from a
  `query` search are judged only against the words you typed: check their season and episodes.
- Search releases only when the user wants to download or asks what is available.
- What the user already has: `imported` and `in_jellyfin` from media_read_media. Do not
  download those again unless the user asks for another version.
- Downloads, subscriptions and feeds are confirmation cards. Put one request on one card. Do
  not say anything was done before the user decides; afterwards report what happened per row.
```

第二條就是 **B4**。

**B2 5 個 skill 併成 3 個**：

| 新 skill | 取代 | 草稿行數目標 |
|---|---|---|
| `download` | `missing-episodes`、`series-mapping`、`new-season-picks` 第 8 步 | ≤ 30 |
| `subscribe` | `subscribe` | ≤ 20 |
| `recommend` | `new-season-picks` | ≤ 20 |

`why-not-imported` 不再是 skill：結論的意思與「唯讀、先說結論、最後給下一步」寫進
`why_not.explain` 的說明。

**B3**：不點名作品（Re:Zero、無職轉生、HUNTER×HUNTER 只留在驗收情境，不留在 skill），只留通則。
例如「第 0 集、.5 集、總集篇、被 TMDB 移到特典的集會讓之後的範圍全部位移」。

`download` 草稿：

```markdown
---
name: download
description: >-
  Download a movie, a season, the episodes a series is missing, or every part of a franchise.
  Use when the user asks to download, get, complete or fill in something, or wants all seasons.
tools: [discover.search_media, media.read_media, why_not.explain,
        inventory.find_in_library, search.search_torrents, downloading.add_manual_download]
---
1. Identify the work with discover_search_media; when several could be it, ask (year, kind).
   Not on TMDB: inventory_find_in_library tells whether the user has it under another name.
2. media_read_media for what the user has; why_not_explain for the whole work. Only
   `no_source` and `download_failed` need a download; for the rest say what is happening.
   If `jellyfin` is unknown, say Berth could not check Jellyfin.
3. Franchise or "all seasons" only: list the parts in airing order with their TMDB entry and
   SxxEyy range. TMDB may fold several cours into one season, continue numbering across
   seasons, or move an episode 0, a .5 or a recap to specials, which shifts every later range.
   Check against a web page when web search is available and cite it; otherwise cut seasons
   at the breaks in `aired_blocks`. Mark every season you could not check, or whose counts do
   not add up, "unchecked". Show the table and ask which parts.
4. Say which episodes you will look for, then search: once per season with
   `scope: {missing: true, season: n}`, then with `query` for names not in `attempts`.
   Use `contains` to list one subgroup's releases instead of searching episode by episode.
5. Reply with a candidates table grouped by subtitle language (subgroup, episodes,
   resolution, seeders, size) and your pick: what the user asked for; then `verdict: fits`;
   a season pack over single episodes; more seeders; smaller size. If the user has not said
   which subtitles and there is more than one language, ask and stop.
6. One downloading_add_manual_download card, one row per torrent, saying the episodes it
   covers.
```

`subscribe` 草稿（配 C3 的 `rss.subscribe`）：

```markdown
1. Identify the work, media_read_media (`aired_blocks`), rss_list_subscriptions for it.
2. search_search_torrents under the names. Table per subgroup: subtitle language, resolution,
   latest episode and its date, usual delay after airing (estimate from `published_at`; "—"
   when you cannot tell), seeders.
3. Recommend one and ask which, unless the user already picked. If the work already has a
   subscription, say so and ask whether to delete it (rss_delete_feed).
4. rss_subscribe with media_id and the subgroup. The card shows where it subscribes, the
   subgroups found and the first batch.
5. A site that cannot be reached: say which; do not switch sources on your own.
```

`recommend` 草稿：

```markdown
1. Candidates: anilist_read_season (+ bgm_read_calendar for Chinese titles and Bangumi
   scores) for anime, discover_read_trending for the rest.
2. One inventory_find_in_library call with every name, one rss_list_subscriptions call:
   mark "have" (only `exact` matches) and "subscribed"; do not recommend those again.
3. Per candidate: titles, format and episodes, scores with their rater counts (under 20 is
   "too few ratings", not ranked), one line of genre; say when sources disagree.
4. Reviews only when asked: at most two web searches, cite URLs.
5. When the user picks: still airing → load `subscribe`; finished → load `download`.
```

「從媒體庫重建帳本」的指引只留一處：`media.read_media` 的輸出在 `in_jellyfin` 佔一整季以上時
帶一句 `hint`（票裡定格式），skill 與系統指示都不寫。

### C. 工具

**C1 `search_torrents` 加 `contains`**：`contains: list[str]`，每個詞都要出現在發佈名裡
（NFKC、casefold，同 `parser.title` 的正規化），先篩再截斷。有 `contains` 時，給模型的上限放寬
（數字票裡用 token 量定）。這次的情況是一次
`query: 非人少女, contains: [喵萌奶茶屋, 繁日]` 拿到 13 集。
比起只篩字幕組更 generic：字幕組、語言版本、解析度都用同一格。

**C2 整季缺時的季記號**（bug，先寫會紅的測試）：失效條件是只有一季的作品第 1 季整季缺時，
`missing_batches` 只送「名字 第1季」。候選修法：
- 第 1 季另送不帶記號的名字；
- 或作品只有一季時不加記號。

哪一種要先實測索引站的回應（結果寫進 brief §20）。TPB / YTS 對查不到的查詢回一整頁無關結果，
另記一條、不在這張票修。

**C3 兩支訂閱工具合成 `rss.subscribe`**：
- 輸入 `media_id`、`subgroup`（推薦的那一個）。
- 伺服器找 Mikan 番組：用作品的中文、原名、羅馬拼音、英文名搜，用開播日挑。找到又有那個字幕組
  就走 Mikan，否則走 nyaa / acg.rip 關鍵字。
- 卡片列出找到的字幕組與來源，人選一個，第一批照舊。
- 模型的工具少掉 `bangumi.search_bangumi`、`bangumi.read_bangumi`、`rss.subscribe_mikan`、
  `rss.subscribe_search`。命令本身留著，RSS 頁還在用。
- 這是最大的一項：Mikan 找番組的判斷從 skill 搬進程式，要 `codebase-design` 先定邊界，可能拆兩張票。

**C4 `find_in_library` 給集數**：劇集的命中多一格 `episodes`，用 Jellyfin 的季集號、以範圍表示
（`S01E01–E12`），註明不是 TMDB 編號。用在 Jellyfin 沒刮到 TMDB id、`read_media` 找不到作品時。

### 改後的工具清單（22 → 18）

- 刪：`media.route_choices`、`bangumi.search_bangumi`、`bangumi.read_bangumi`、`rss.subscribe_mikan`、
  `rss.subscribe_search`。
- 加：`rss.subscribe`。
- 改：`downloading.add_manual_download`（列不帶 `route_id`）、`search.search_torrents`（`contains`）、
  `inventory.find_in_library`（`episodes`）、`why_not.explain`（說明含結論的意思）、
  `media.read_media`（拿掉 Route 欄位、加 `hint`）。

## 5. 驗收與量測

- **基準**：改之前先跑一次 `scripts/experiments/m5_acceptance_scenarios.py`（S1–S6 加 S2 三個變體，
  兩種接口；上次約 $0.20），再加一個 S7：這段對話（找「非人少女」、選喵萌奶茶屋繁中單集）。
- **改完重跑同一組**，比工具呼叫數、input token、費用。品質照 M5 驗收的逐項檢查，S2 三個變體的
  範圍標記不能變差。
- **目標**：
  - S7 的種子搜尋從 18 次降到 ≤ 6 次；
  - 卡片 Route 點擊從 13 次降到 1 次；
  - skills 總行數 ≤ 80。

## 6. 票序草案

每一步 repo 都可運作：

1. C2 季記號 bug（tdd，先紅）。
2. A1 + A2 卡片分組與全部套用（前端，API 不變；playwright 截圖）。
3. A4 模型不給 `route_id`，刪 `route_choices`，刪 skill 的 Route 段落。
4. C1 `contains`。
5. C4 `find_in_library` 的 `episodes`。
6. 跑基準（真模型，S1–S7）。
7. B1–B4 系統指示與三個 skill 改寫，`why_not.explain` 說明。
8. C3 `rss.subscribe` 與 `subscribe` skill（可能拆兩張）。
9. 驗收：重跑 S1–S7、比數字、封存。

要同輪改的文件：
- brief §14（skills 與確認卡）、plan §11.6〈確認卡範圍〉、plan §6（工具與 API）；
- `tests/unit/test_skills.py`、`test_agent_tools.py`、`test_command_registry.py` 的對應斷言。
