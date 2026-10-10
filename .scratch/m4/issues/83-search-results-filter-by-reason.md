# 83 — 搜尋結果：每一筆說得出為什麼被收起來或略過，使用者用篩選按鈕自己看

**Status:** done

**Blocked by:** None — can start immediately

**讀:** M4 票 69 的 Comments（筆數的定義、已知限制）、票 49（`fits`）、票 08（自己打關鍵字不篩）；`berth/services/search.py`（模組說明、`search_torrents`、`_about`、`_fits`、`_take`、`SearchView`）；`berth/parser` 的 `mentions` 與 `fits`；`web/src/media/SearchPanel.tsx`、`SearchResults.tsx`、`searchResult.ts`；brief §13、plan §8.4

## 為什麼（2026-10-10 使用者）

目前結果分四類：合併、名字對不上、收起來（年份或類型不符、同名動畫的集號、成人分類）、結果表。畫面只說了「100 筆名字對不上（已略過）」，那 100 筆後端根本沒送到前端；「收起來」的也只能整批展開，每一筆沒寫是因為哪一條被收起來。使用者不知道被略過的是什麼，也就沒辦法判斷 Berth 是不是判斷錯了。

票 69 留下的《Law & Order》混進衍生劇《Law & Order: SVU》也在這張處理：不再硬擋或硬放，改成單獨一類。

## 做什麼

照 Sonarr 手動搜尋的慣例（被拒絕的發佈照樣列出，每一筆標上理由，使用者自己決定抓不抓）。動手前先查證 Sonarr 的做法，結論寫進 brief §20 並附來源。

1. **後端每一筆帶理由**：
   - 每一筆歸到一類：符合、年份不符、類型不符（電影搜到季集）、同名作品的集號、成人分類、**只對上部分名字（可能是衍生劇）**、名字對不上。理由要細到什麼程度，在 shape 時定。
   - 「名字對不上」的也送出來，每類照舊各站輪流取、有上限（The Pirate Bay 對查不到的關鍵字會回熱門清單，全送會讓回應變很大）。
   - 筆數照樣加得起來（`returned = merged + 各類筆數`）。
   - 「只對上部分名字」：照 Sonarr 解析季集記號前面那一段片名，再跟作品的名字比對；不是比對整串是否包含。規則先查證。
2. **前端用篩選按鈕**：
   - 結果表上方一排按鈕，一類一顆，按鈕上帶筆數。預設只開「符合」，其他類按了才一起列出。
   - 每一列標出它屬於哪一類；不是「符合」的那幾類，用一句話說出原因。
   - 可以只看某個站。
   - 解析度、字幕語言這類篩選不在這張。
   - 現在「收起來」的展開區由這組按鈕取代，不要兩種都留著。
3. **自己打關鍵字**：照票 08 不篩，全部列出。要不要標出類別，在 shape 時定。
4. **UI 走 `/impeccable`**：先 `shape`，把稿子給使用者確認後才實作；收尾做 `critique` / `polish`。

## 驗收

- [x] shape 稿使用者確認過，路徑寫在 Comments
- [x] 每一類各有一筆例子，後端分得對；「只對上部分名字」以 `Law.and.Order.SVU.S28E01` 搜《Law & Order》為例；pytest 守，做變異驗證
- [x] 回應的大小有上限；筆數加得起來；pytest
- [x] 篩選按鈕的開與關、筆數、每一列的理由（兩種語言）、只看某個站；vitest
- [x] `berth bench` 的 `auto_wrong` 不上升（若有動到解析器）
- [x] Playwright 實跑：《Nosferatu》(1922) 與《Law & Order》各搜一次，每一類都點開看，1280 與 390 寬各一張截圖。用隔離環境（專案名 `berth-t83`、另一組 port）；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`pnpm gen:api` 沒有差異；CHANGELOG、progress.md 已更新

## Comments

### 決定

- **shape**：`.scratch/m4/search-filter-shape.md`，2026-10-10 使用者確認（依類別分組、只標不是「符合」的列、自己打關鍵字不分類、上限符合 100 其他每類 50）。
- **七類變六類**（使用者 2026-10-10 追加）：`episode`（類型不符）與 `namesake_episode`（同名作品的集號）合成 `not_movie`（不是電影 / Not a movie），
  那一句話照樣帶出觸發的那段字（`S04E02`、`- 05`、`[01-12]`）。
- **篩選按鈕是可重用元件**（使用者追加）：`web/src/components/ToggleChips.tsx`（`aria-pressed` 的一組切換鍵，可帶筆數）與 `toggled.ts`，票 84 的名字與季選擇用同一個。
- **判定順序與 shape 原稿不同（請使用者確認）**：原稿表格的先後是名字對不上 → 成人 → 只對上部分名字 → 類型 → 集號 → 年份；
  實作是名字對不上 → 成人 → 不是電影 → 年份不符 → 只對上部分名字 → 符合。理由：`Tsuki to Laika to Nosferatu - 05` 的片名也包住《Nosferatu》，
  部分名字排在前面的話同名動畫的各集全會被歸成「名字多一段」，而更硬的證據是 `- 05`；年份同理（`Nosferatu.The.Vampyre.1979` 說年份比說名字明確）。
  按鈕與分組的順序照 shape。brief §20.20、plan §8.4、`SearchVerdict` 的說明照新順序寫。
- **「只對上部分名字」的規則**（brief §20.20，Sonarr `ParsingService.FindSeries` 的 clean title 完全相等）：取第一個記號（季集、字幕組集號、
  片名以外的年份）前面那一段，照 `/`、`|`、括號與文字系統（CJK／非 CJK）切成一個一個名字；有一個相等就是這一部，沒有相等但有一個包住
  作品的名字才算部分。讀不出記號時不判。比 Sonarr 多「切成名字」那一步：字幕組把中文名與拉丁字名寫在一起，整段比的話每一筆都像衍生劇。
- **理由句**：「只對上部分名字」原稿寫「可能是衍生劇」，實跑時《Nosferatu》的 `Nosferatu A Symphony of Horror 1922` 是這部片多寫了副標，
  改成「可能是衍生作品，也可能只是多寫了副標」。
- **API**（`GET /api/search`，SPA 是唯一消費者，CHANGELOG 已寫）：每一列多 `verdict`、`evidence`；`total`、`discarded`、`set_aside`、`set_aside_total`
  換成每類每站的 `counts`；`returned = merged + Σ counts.total`。CONTEXT.md 的 Set Aside 換成 Search Verdict。
- **標頭只說「結果表 N 筆」**：原本的「逐站列出前 N 筆」與那一組底下的上限說明重複（code-review），拿掉標頭那一份。

### 變異驗證（手動跑過、測試裡守著）

- parser（`test_parser_title.py`）：拿掉「有一個名字相等就不算」→ 15 紅；不照文字系統切 → 1 紅；電影不看字幕組集號 → 9 紅；片名那一段不以年份收尾 → 2 紅；
  只改區域變數名 → 全綠。
- services（`test_search.py`）：部分名字排到 `misfit` 之前 → 2 紅；每類同一個上限 → 1 紅；拿掉成人分類 → 4 紅；`counts` 不分站 → 1 紅；改常數名 → 全綠。
- 前端（`SearchPanel.test.tsx` 的票 83 那一組）：預設全開 → 7 紅；按鈕數字不跟站別 → 1 紅；電影年份那一句不出 → 1 紅；分組不照順序 → 1 紅；改區域變數名 → 全綠。

### berth bench

改動前（`3dc9f52`，`git archive` 到 scratchpad 跑）與改動後相同：`overall 904 files · auto_correct 253 · auto_wrong 0 · review 86`；high 0/112、medium 0/141 wrong。

### 實跑（隔離環境）

compose 專案 `berth-t83`：只有一台 Prowlarr（`berth-t83-prowlarr`、port 19783、named volume、網路 10.83.0.0/16、`restart: "no"`），
加了 The Pirate Bay 與 Mikan（YTS、Nyaa 從容器連不上，與票 69 相同）。Berth 是這個分支的 `fake_setup_server.py --scenario search --port 8483`
（真的 API、資料庫、前端 build；TMDB 打真的，key 讀主 checkout 的 `.env`）。跑完 `down -v`；`berth-local` 四個容器全程照舊、沒碰。
截圖在 `.playwright-mcp/t83/`（每一類一張 1280 的表格、兩部各一張 1280 與 390）：

- 《Nosferatu》(1922)：符合 13 · 年份不符 64 · 不是電影 187 · 成人分類 19 · 只對上部分名字 6 · 名字對不上 100 = 索引站回的 389。
  不是電影裡有 `Dragula Titans S02E04 …`（「S02E04」）與 `Tsuki to Laika to Nosferatu - 01`（「- 01」）；成人分類帶 6000 / 6040 / 6045。
- 《Law & Order》：符合 40 · 只對上部分名字 60（`Law.and.Order.SVU.S28E01` →「Law and Order SVU」、`Law.and.Order.Special.Victims.Unit…`）·
  名字對不上 201，加 99 筆重複 = 400。只有 The Pirate Bay 回結果，所以沒有站別下拉；站別在 Nosferatu（兩站）看得到，行為由 vitest 守。

### critique / polish

以實跑的兩種寬度截圖逐項看：空狀態（沒選類、這一站沒有、沒有符合）、鍵盤（每一顆是 `aria-pressed` 按鈕、整組有名字）、390 寬按鈕折行、
「符合」列不塗漆、類別色塊是中性。改了一處：中文筆數那一行兩句之間多一個半形空白（「400 筆。 其中…」），空白改寫在英文字串裡。

### 已知限制

- 片名帶國別的 scene 寫法（`The.Office.US.S01E01`）歸成「只對上部分名字」：Sonarr 的 TVDB 片名有 `(US)`，TMDB 沒有；拿掉國別的話 `Law.and.Order.UK` 會算符合（Spec 審查）。
- 「只對上部分名字」讀不出記號時不判：`Law and Order SVU 1080p` 算符合。
- 「只看某個站」時標頭與 `aria-live` 仍說全部站的「符合」數。
- 《Nosferatu》的部分名字 6 筆裡有 4 筆其實就是這部片（英文副標 `A Symphony of Horror` 不在 TMDB 給的名字裡），預設看不到、按一下看得到。

### code-review（Standards、Spec 兩軸 opus）處理掉的

`ASIDE_LIMIT` 改名 `OTHERS_LIMIT`（`set aside` 是 CONTEXT.md 的 _Avoid_）；「預設列出的那一份」前端收成一個 `isListed`；前端型別 `Judged` 改名 `FilterVerdict`、
元件 `Verdict` 改名 `VerdictNote`、色塊的 key 由 `reasonOf` 一起給；標頭不再重複上限說明；`SearchResult.verdict` / `evidence` 不給預設值；
brief §20.19 那一行改掉「收起來」；`_` 不再當名字分隔（`Law_and_Order_SVU_S28E01` 原本漏判，紅燈先寫）；英文「不是電影」那一句補回 anime；
`SearchPanel.test.tsx` 一行過時的註解。

### 未處理

- 前端 `isJudged`（這一次搜尋有沒有分類）與後端 `Judged`（一筆與它的類別）名字相近：意思不同但都準確，沒改。
- 理由句裡的證據沒有走 `.value`：句子是一般字體、不轉大寫，The Machine String Rule 防的是 `.label` 的大寫，這裡沒有那個問題；要嵌樣式得換成 `<Trans>`，專案還沒用過。
