# 69 — 搜尋結果：「片名＋年份」搜得到、筆數對得上、同名雜訊收起來

**Status:** done

**Blocked by:** 79（同樣改搜尋與結果表；79 先拿掉 `download_url`）

**讀:** `docs/research/usability-audit-2026-10-07.md` §3 S3〈下載〉、§8 P2-18、P2-19；brief §6、§20.16（Radarr / Sonarr 怎麼用年份與類型篩）；plan §8.4；M4 票 49（收起來、`parser.fits`）；CONTEXT.md 的 Set Aside

## 為什麼（審計 S3）

- 探索頁搜「Nosferatu 1922」是 0 筆：TMDB 的搜尋不吃年份。
- 作品頁搜尋寫「共 262 筆 · 逐站取了 100 筆」、「103 筆已略過」、「164 筆已經收起來」，彼此對不上。
- 主表還混進同名動畫《Tsuki to Laika to Nosferatu》的各集與成人內容。
- 2026-10-09 使用者本機試用（票 77 實跑時查到）：作品頁搜《Law & Order》，The Pirate Bay 0 筆；改搜 `Law and Order` 有 100 筆。片名含 `&` 的作品幾乎搜不到。

## 做什麼

1. 探索搜尋：查詢字串結尾是四位數年份時，拆成「片名＋年份」交給 TMDB 的年份參數。查證 TMDB 的搜尋參數（context7 或官方文件），寫進 brief §20。沒有結果時退回原字串。
2. 作品頁的筆數：定義清楚每個數字數的是什麼（Prowlarr 回幾筆、名字對不上略過幾筆、收起來幾筆、主表幾筆），讓它們加得起來；畫面上照同一個定義說。
3. 電影搜尋時，讀得出集數的發佈（同名劇集或動畫的各集）收進「收起來」。這要延伸票 49 的 `fits`，紅燈先寫在 fixture。
   - 成人內容：查 Prowlarr 回傳的分類欄位能不能判斷，能就收起來，不能就記在票的 Comments、不硬做。
4. **片名含 `&`**：作品頁的搜尋多送一組把 `&` 換成 `and` 的查詢（語言照作品的原文名或英文名，中文名不換），結果合併、照 info hash 去重。
   - 這會多佔請求預算：先看現在一次搜尋送幾組查詢、怎麼佔額度（票 77），再決定是多一組，還是取代原本那一組。理由寫在 Comments。
   - 先查 Sonarr / Radarr 怎麼處理片名裡的 `&`（它們的 clean title 規則），說明採用了誰的慣例。
5. 解析器有改動就跑 `berth bench`，`auto_wrong` 不得上升。

## 驗收

- [x] 單元或整合測試：年份拆分；筆數加得起來；同名劇集的各集在電影搜尋被收起來（fixture 先紅後綠）
- [x] 片名含 `&` 會多一組（或改成）`and` 的查詢；整合測試守著，並驗過不含 `&` 的片名不受影響
- [x] 實跑：《Law & Order》作品頁搜尋有結果，附截圖
- [x] `berth bench` 前後的 `auto_wrong` 貼在 Comments
- [x] 實跑：《Nosferatu》(1922) 的探索與作品頁搜尋截圖
- [x] 全部檢查、test 綠燈；brief §20、plan §8.4 同步；progress.md 記一行

## Comments

### 決定

- **`&`：多一組，不取代**（推翻開工時照 Sonarr / Radarr 的「取代」）。現況（票 77）：一次搜尋最多五個查詢（`MAX_QUERIES`），每個查詢在每一站佔一格請求預算。實測兩種站各認一種寫法：The Pirate Bay（經 Prowlarr）`Law & Order` 0 筆、`Law and Order` 100 筆；Mikan RSS 搜尋 `TIGER & BUNNY` 81 筆、`TIGER and BUNNY` 0 筆。Sonarr / Radarr 的 `GetCleanSceneTitle` 只送寫開的那一個（brief §20.19），照抄會丟掉字幕組那一邊。所以有 `&` 的名字原樣問一次、緊接著問寫成 `and` 的一次；**仍在五個之內**，擠掉的是排最後的別名，每一站佔的格數上限不變。`Season N` 變體用寫開的（scene 的寫法），`第N季` 照原樣。只換沒有 CJK 字的名字（「中文名不換」做成「有 CJK 字的不換」：拉丁字的別名也會多一個寫開的）。比對那一邊只替帶 `&` 的名字多認一種寫開的，不學 Sonarr 刪掉每一個 `and`。
- **筆數的定義**：`returned`（每個查詢回的筆數加總）＝`merged`（不同查詢或站回了同一個發佈、合併掉的）＋`discarded`（名字對不上）＋`set_aside_total`（收起來）＋`total`（結果表）。畫面一行說完，是 0 的那幾份不說；標頭從「共 N 筆」改成「結果表 N 筆」（「共」被讀成全部）；`onlyOthers` 不再報數字。欄位叫 `merged` 不叫 `duplicates`：CONTEXT.md 的 **Duplicate** 是帳本裡的重複版本（code-review）。
- **成人內容：能判斷，做了**。Prowlarr 的 `categories` 帶 Newznab 標準碼，XXX 是 6000–6090；實跑 The Pirate Bay 搜「Nosferatu」100 筆裡 19 筆帶 6000 / 6040 / 6045（加 `1005xx` 自訂碼）。落在 6000–6999 的收起來。**電影與劇集都收**（票面寫在電影那一條下面）：成人分類與作品類型無關。
- **探索的年份**：TMDB `search/multi` 沒有年份參數（實測「nosferatu 1922」0 筆）。結尾是 1800–2099 的四位數（括號要成對）而前面還有片名時，`search/movie?primary_release_year=` 與 `search/tv?first_air_date_year=` 各問一次、交錯（參數照 Jellyseerr）；那一年沒有東西才照原字串問 `search/multi`。
- **同名劇集的各集**：`parser.fits` 的電影季集記號加上字幕組的集號 `- 05`、`- 07v2`、`- 01 ~ 12`、`[05]`、`[01-12]`、`【12 END】`、`[01-12合集]`、`第01-12话`；只認兩到三位數（四位是年份、一位多半是光碟數或續集，code-review 抓到 `- 2 Disc`、`[3]`）。

### berth bench

改動前（`444f330`，`git archive` 到 scratchpad 跑）與改動後（含 code-review 之後）完全相同：`overall 904 files · auto_correct 253 · auto_wrong 0 · review 86`；high 0/112、medium 0/141 wrong。`auto_wrong` 0 → 0。

### 實跑（隔離環境）

compose 專案 `berth-t69`：只有一台 Prowlarr（`berth-t69-prowlarr`、port 19769、named volume、網路 `berth-t69` 10.69.0.0/16、`restart: "no"`），加了 The Pirate Bay 與 Mikan（YTS、Nyaa 當時從容器連不上）。Berth 是這個分支的 `scripts/fake_setup_server.py --scenario search --port 8469`（真的 API、資料庫、前端 build；索引站打那台 Prowlarr、TMDB 打真的 API，key 讀主 checkout 的 `.env`；Jellyfin、qBittorrent 是替身，搜尋不碰它們）。所以沒有 build Berth 的 image；Prowlarr image 與 `berth-local` 共用，沒刪。跑完 `down -v`、刪 config root；`berth-local` 四個容器全程 Exited、沒碰。截圖在 `.playwright-mcp/t69/`：

- 探索搜「Nosferatu 1922」：1 部作品，《不死殭屍—恐慄交響曲》MOVIE · 1922（`discover-nosferatu-1922.png`）。
- 《Nosferatu》(1922) 作品頁：「索引站回了 389 筆：19 筆列在結果表、270 筆年份或類型對不上（收在下面）、100 筆名字對不上（已略過）。」（`media-nosferatu-1922-search.png`）。第一輪實跑時主表還有 27 筆，其中 8 筆是《Tsuki to Laika to Nosferatu》的 `[第01-12话]`、`【01-12 END】`、`【12 END】`、`[01-12合集]`，補進 regex（紅燈先寫在單元測試）後剩 1 筆（見下面的限制）。
- 《Law & Order》作品頁：查詢 `Law & Order · Law and Order · 法網遊龍 · Law and Order Season 26 · 法網遊龍 第26季`，「索引站回了 300 筆：100 筆列在結果表、200 筆名字對不上（已略過）。」（`media-law-and-order-search.png`）。直接問 Prowlarr（只 The Pirate Bay）：`Law & Order` 0 筆、`Law and Order` 100 筆。

### 已知限制（判斷題，留著）

- 沒有任何集號的動畫合集擋不到：`[喵萌奶茶屋&VCB-Studio] … Tsuki to Laika to Nosferatu … 10-bit 1080p HEVC BDRip [Fin]` 仍在《Nosferatu》的主表。只看發佈名分不出它是劇集；`[Fin]` 不是集號，沒拿來判。
- 《Law & Order》的主表混進《Law & Order: SVU》（`Law.and.Order.SVU.S28E01`）：名字包含就算對上（`mentions`），衍生劇分不開。與本票無關，沒有 repro 票不修。
- 字幕組集號的 regex 仍可能誤判兩位數的光碟或部數（`Movie (2020) [01]`）；收錯的展開救得回來。
- 探索的年份拆分只在帶年份的那兩支**完全沒有結果**時退回原字串：`the 1975` 會拆成片名 `the`、1975 年，那一年有東西就不退回。
- 成人分類只在站的定義有映射時擋得到；多數動漫站（Mikan 全部映射成 5070）沒有這一格。

### code-review（兩軸 opus）處理掉的

`duplicates` 改名 `merged`；`Season N` 變體以外的 `&` 改成「多一組」（見上）；一位數的 `- 2`、`[3]` 不算集號；年份拆分要成對的括號；CHANGELOG 說成人內容只在電影收起來的錯；`_with_year` docstring 錯字。

### 未處理

- `HttpTmdbClient.search_year` 兩個分支只差路徑與參數名：改成查表會讓 mypy 把 `**dict` 對到 `_get` 的 `missing` 參數，兩個分支比較清楚。
- `discover.fetch` 兩條路都是「listing → display 查表 → 卡片」：只有兩處，不抽。
- 前端的 `type SearchResults as SearchOutcome` 別名：避開同名元件 `SearchResults`，只用在 `tally` 一處。
- 「一個 commit 包四件事、`fix` 帶新欄位」：第一個 commit 已經在本地，沒有改寫歷史；code-review 之後的修正另一個 commit。
