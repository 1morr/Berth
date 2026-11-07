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

## 7. 基準：改動前（2026-11-07，票 01）

票：[`.scratch/m5.6/issues/01-baseline.md`](../../.scratch/m5.6/issues/01-baseline.md)。在任何會影響模型行為的改動之前量一次，之後每一項都和這裡比。
驅動：`scripts/experiments/m5_acceptance_scenarios.py`；演練情境：`scripts/fake_setup_server.py --scenario agent-live`。
逐字稿：[`m5-acceptance/baseline-core/`](m5-acceptance/baseline-core/)、[`baseline-s7s8/`](m5-acceptance/baseline-s7s8/)、[`baseline-retry-s1/`](m5-acceptance/baseline-retry-s1/)、[`baseline-retry-s2a/`](m5-acceptance/baseline-retry-s2a/)、[`baseline-retry-s7route/`](m5-acceptance/baseline-retry-s7route/)（`.local/` 不進版控）。

### 環境

- **模型**：`.env` 的兩組都接 DeepSeek `deepseek-flash`（和 M5 驗收同一個模型）。
  - anthropic：`https://api.deepseek.com/anthropic`；openai：`https://api.deepseek.com`。
- **版本**：pydantic-ai-slim 2.62.0、anthropic SDK 2.3.0、openai SDK 3.39.0（`uv.lock`）。
- **Berth**：`agent-live`（真 TMDB、真索引站、真模型與動漫資料，qBittorrent 是 `KeepingQbittorrent`）。每種接口一台全新的 Berth。
- **時間**：2026-11-07 UTC 02:12–02:55（DeepSeek 尖峰）。
- **情境**：S1–S6、S2 的三個變體、`S7-route`（M5 票 23b 的舊情境，這次改名），加上新的 S7（非人少女）與 S8（同一段對話的模糊開頭）。S8 排在 S7 前面：S7 會下載同一部作品，先跑 S8 才量得準「還沒說要下載就搜」。
- **驅動這次的改動**：舊的 Route 情境從 `S7` 改名 `S7-route`（新的 S7／S8 用掉這兩個編號）；summary 加種子搜尋次數、skill 載入次數（Route 列數原本就有）；確認卡的字幕組照模型預選的那一個送（M5 票 26 之後商品會要人選，舊驅動沒送，S1 的卡會停在 `pending`）。
- **重跑**：第一輪 S1（驅動沒送字幕組）與 S2 anthropic（模型端 `max_tokens` 4096 的暫時錯誤）無效，修好驅動後各重跑；S4 anthropic 跟著 S2 重跑。`S7-route` 在第一輪被前一個 S3 的下載污染（S3 已把宝石の国整季送進 qBittorrent，模型正確地不再重複下載），另外用全新的 server 重跑。表格只放有效的那些列。
- **費用**：表中 22 列合計 **$0.256**（anthropic $0.133、openai $0.122）；被丟掉的那幾輪（S1、S2 anthropic、S4 anthropic、S7-route）約 **$0.091**，這次總共花約 **$0.35**。

### 數字

| 接口 | 情境 | 秒 | 輪 | 模型呼叫 | 工具 | input | 快取 | output | 網搜 | 種子搜尋 | skill | Route 列數 | 卡片（命令，狀態，列數） | 費用 USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic | S1 | 102 | 4 | 12 | 19 | 247,172 | 92% | 10,783 | 2 | 3 | 2 | 1 | rss.subscribe_mikan executed 1 | 0.02029 |
| openai | S1 | 107 | 4 | 13 | 18 | 267,842 | 92% | 10,736 | 1 | 3 | 2 | 1 | rss.subscribe_mikan executed 1 | 0.02083 |
| anthropic | S2 | 151 | 4 | 13 | 17 | 269,338 | 83% | 14,099 | 2 | 6 | 1 | 2 | downloading.add_manual_download executed 4 | 0.03186 |
| openai | S2 | 105 | 4 | 11 | 18 | 209,347 | 78% | 9,444 | 1 | 7 | 1 | 4 | downloading.add_manual_download executed 6 | 0.02623 |
| anthropic | S2-mushoku | 38 | 1 | 6 | 7 | 63,494 | 70% | 4,613 | 2 | 0 | 1 | 0 | — | 0.01145 |
| openai | S2-mushoku | 32 | 1 | 6 | 8 | 53,296 | 90% | 3,714 | 1 | 0 | 1 | 0 | — | 0.00641 |
| anthropic | S2-hxh | 32 | 1 | 6 | 9 | 73,691 | 78% | 3,430 | 2 | 0 | 1 | 0 | — | 0.00944 |
| openai | S2-hxh | 37 | 1 | 5 | 8 | 55,020 | 83% | 4,228 | 2 | 0 | 1 | 0 | — | 0.00814 |
| anthropic | S3 | 49 | 3 | 9 | 14 | 113,277 | 89% | 3,962 | 0 | 6 | 1 | 1 | downloading.add_manual_download executed 1 | 0.00897 |
| openai | S3 | 37 | 3 | 8 | 12 | 90,765 | 89% | 3,173 | 0 | 4 | 1 | 1 | downloading.add_manual_download executed 1 | 0.00718 |
| anthropic | S4 | 25 | 1 | 4 | 6 | 131,287 | 95% | 2,939 | 0 | 0 | 1 | 2 | downloading.add_manual_download executed 4 | 0.00615 |
| openai | S4 | 13 | 1 | 3 | 4 | 95,978 | 93% | 1,567 | 0 | 0 | 1 | 4 | downloading.add_manual_download executed 6 | 0.00433 |
| anthropic | S5 | 8 | 2 | 5 | 6 | 38,976 | 92% | 833 | 0 | 0 | 0 | 0 | rss.add_feed executed 1 | 0.00216 |
| openai | S5 | 11 | 2 | 4 | 5 | 31,379 | 91% | 1,177 | 0 | 0 | 0 | 0 | rss.add_feed executed 1 | 0.00247 |
| anthropic | S6 | 58 | 1 | 4 | 13 | 56,969 | 70% | 7,191 | 1 | 4 | 1 | 0 | — | 0.01402 |
| openai | S6 | 46 | 1 | 4 | 8 | 38,113 | 78% | 5,830 | 0 | 2 | 1 | 0 | — | 0.0097 |
| anthropic | S7-route | 40 | 2 | 7 | 11 | 74,215 | 89% | 3,148 | 0 | 3 | 1 | 1 | downloading.add_manual_download executed 1 | 0.00662 |
| openai | S7-route | 60 | 2 | 7 | 15 | 92,207 | 83% | 3,914 | 0 | 8 | 1 | 1 | downloading.add_manual_download executed 1 | 0.00985 |
| anthropic | S7 | 100 | 3 | 10 | 18 | 189,633 | 86% | 7,747 | 0 | 11 | 1 | 13 | downloading.add_manual_download executed 13 | 0.01828 |
| openai | S7 | 67 | 3 | 9 | 16 | 167,581 | 85% | 6,389 | 0 | 10 | 1 | 13 | downloading.add_manual_download executed 13 | 0.01594 |
| anthropic | S8 | 27 | 2 | 6 | 8 | 44,600 | 92% | 2,368 | 0 | 0 | 0 | 0 | — | 0.00422 |
| openai | S8 | 56 | 2 | 8 | 15 | 91,498 | 84% | 5,216 | 0 | 6 | 1 | 0 | — | 0.01113 |

- 合計：anthropic 128 次工具、input 1.30M、$0.133；openai 127 次工具、input 1.19M、$0.122。
- 種子搜尋（兩個接口合計）：S7 **21 次**（11 + 10）、S8 **6 次**（0 + 6）、S3 10 次、S2 13 次、`S7-route` 11 次。S8 的 6 次全是 openai 在兩句都沒說要下載時搜的。
- 送單卡 Route 列數：S7 **13**（兩個接口都逐列問），`S7-route` 1，S1 1，S3 1。
- 所有 run 的停止原因都是 `completed` 或 `awaiting_confirmation`；表中列出的 run `errors` 全空。

### 品質（照 M5 驗收逐項檢查）

**S1 新番推薦 → 訂閱**

- 兩個接口都列 5 部、AniList 與 Bangumi 的分數與人數並列，樣本小的有標（黑色五葉草 Bangumi 175 票、青之芦苇 204 票）。第一部都選《藥屋少女的呢喃 第三季》，對到 `tv:220542`，判斷還在播，走 Mikan 訂閱。
- 出卡 1 列，字幕組選模型推薦的喵萌奶茶屋（預選）、路線在卡上選 Anime，按確認後 `executed`。**品質和 M5 的 `-answered` 重跑同水準**。
- 腳本修好字幕組選擇之前，兩個接口的 S1 卡都停在 `pending`（`subgroup_required` 422）——那是驅動的問題，不是產品。

**S2 Re:Zero 全系列**

- 兩個接口都講清楚 TMDB 把第 2–4 季併進 S01（85 集）、兩部 OVA 是獨立電影、短篇排除。
- anthropic：4 列卡（S01E01–E66 一個合集、E67–E85 一個合集、兩部 OVA），全部 `done`；`/compact` 後追問答對，E01–E85 不重疊、不空號。**但七段全部標「沒有網頁核對，請確認」**（它說找不到完整季集數的網頁，雖然這一輪有 2 次網搜）。這是比 M5 更保守的標法，不是範圍算錯。
- openai：6 列卡（4 個 TV 批次 + 2 部 OVA），範圍 E01–E85 正確，全部 `done`；`/compact` 後追問答對。**沒有標任何「未經核對」**（`phrase_seen` False），和 M5 的「部分標記」不同，但範圍本身正確。
- 兩邊的卡片粒度都比 M5 的 7 列粗（anthropic 4 列、openai 6 列），但涵蓋範圍一致。

**S2 變體（範圍標記，之後要比）**

- **無職轉生**：兩個接口都把第 2 季**前半與後半兩列**標「未經核對，請確認」，並說明第 0 集在 Specials S00E02、官方 25 集對 TMDB 24 集；第 1、3 季沒有誤標。**比 M5 基準好**（M5 兩個接口都只標後半）。
- **HUNTER×HUNTER 2011**：兩個接口都選對 `tv:46298`（不是 1999 年版），兩部劇場版列成獨立電影；S02 從 E63 起、貪婪之島跨 S01/S02 都講了。anthropic 三季都標；openai 用篇章列（6 列）並全部標「未經核對，請確認」。**兩邊都沒有漏標**（M5 的 openai 漏了 S1）。

**S3 冷門作品（宝石の国）**

- 兩個接口都先用日文名搜、再換中文找到 `tv:74091`，Jellyfin 0 集、沒有在途下載；都列出整季包與做種數，固定回答後各送 1 列 `add_manual_download`（都是 Lilith-Raws Baha 繁中 1080p 10.8 GB），`done`。沒有重複搜同一個詞到被當成迴圈。

**S4 為什麼沒入庫**

- openai（接在自己送單的 S2 之後）：答「6 項都已送出、全部 `stalledDL` 0%」，分得出 TV／電影，指出 Berth 紀錄只有 `created` → `submitted`，卡在 qBittorrent 端。
- anthropic（接在重跑的 S2 之後）：4 筆同樣 `stalledDL`；另外指出 64 GB 合集在搜尋結果只綁到 S01E02，其餘 64 集目前是 `no_source`，並說明要等匯入才會依檔名認集。只讀、沒有出卡。
- `stalledDL` 讓兩邊都推測 tracker／peer 問題，和 M5 一樣是替身回報 0% 的副作用，不是產品。

**S5 使用者貼的 RSS**

- 兩個接口網址逐字照抄、劇集送 Anime、電影落到唯一的 Movies，卡片 `executed`；都說明電影路線是預設、feed 還沒第一次輪詢。

**S6 要 AI 自己找 RSS 網址**

- 兩個接口都不把搜到的網址塞進 `rss_add_feed`，明說「只接受你自己貼的網址」，改推薦 Mikan 訂閱；**都停在「要哪個字幕組？」**，這一輪腳本不回答，所以沒有出卡。`address_not_from_user` 這次沒被撞到（模型自己繞開），和 M5 一樣。

**S7-route（M5 票 23b，額外驗）**

- 全新 server 上兩個接口都直接出 1 列卡，不再在對話裡問 Route；卡片那一列要人選、沒有預選，腳本選 Anime 後 `done`。

**S7 非人少女（新）**

- 兩個接口都對到 `tv:274810`、13 集全缺。第一句「先找來源給我看」之後都先問字幕組（沒有出卡）；第二句指定喵萌奶茶屋繁中單集後，各出一張 **13 列**的送單卡，全部 `done`。
- **種子搜尋 11（anthropic）／10（openai）次**，**Route 要選 13 次**——這就是要修的問題（票 03、05、07 的目標分別是 Route 1 次、種子 ≤ 6 次）。
- 原對話的 18 次包含「還沒說要下載就搜」的那一次，S7 從「我要下載」開始，所以**之後和 S7 的 10–11 次比，不用 18 次比**。

**S8 模糊開頭（新）**

- 第一句都先猜（anthropic 直接猜到非人少女；openai 列出「我想吃掉你的胰臟」與非人少女兩個候選），第二句更正後都對到 `tv:274810`。
- **anthropic 0 次種子搜尋**；**openai 6 次**，在兩句都沒說要下載時就列了候選表。後者就是票 07 的 B4 要修的行為。

### 這次量測的限制

- 驅動只在每個情境送固定的句子，**不回答模型臨場的問題**；S1、S3、S7 的「要哪個字幕組」所以靠第三句固定回答，S6 停在問題上。品質結論要看逐字稿，不看 summary 的「出現標記字樣」欄。
- S7 的種子搜尋次數受索引站當下結果影響；之後重跑時要同一時間窗、同一個索引站，數字才直接可比。
- 舊的 `S7-route` 和 S3 都用《宝石の国》：同一個 server 先跑 S3 會讓 `S7-route` 看到已經在下載。要一起跑時把 `S7-route` 放前面，或另外開一台。
