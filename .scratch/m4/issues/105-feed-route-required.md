# 105 — Feed 的 Route 必填（劇集、電影各一條），待綁定的手動綁定沿用它

**Status:** done

**Blocked by:** None — can start immediately

**讀:** brief §15「綁定」、§19「RSS 自動綁定送進哪一條 Route（2026-09-26）」；plan §2.4 `rss_feeds`、§6 rss；`berth/services/rss.py` 的 `_auto_bind`（`_chosen_route`、`_route_reason`）；`web/src/rss/FeedSection.tsx`、`SeriesBinder.tsx`、`preselect.ts`；`CONTEXT.md` 的 RSS Series、Feed

## 為什麼

使用者 2026-10-16 用兩台 `rss` 演練情境對照之後提的：

1. 加 Feed 時「自動綁定送進」可以選「不指定」。不指定時，同類型有兩條以上 Route 收得下的作品停在待綁定（`route_ambiguous`），使用者只是多按一次一鍵候選再選 Route，結果跟自動綁定一樣。這條路只增加摩擦。Sonarr 的 Import List 本來就把 Root Folder 列為必填；票 21 抄它的時候多留了一個「不指定」。
2. Feed 有指定 Route 時，因為**作品**沒認出來而停在待綁定的那幾列，手動綁定的「入庫到」還是「尚未指定」。`preselect` 只看這部作品上次用的 Route 和「只有一條」，不讀 Feed 的設定：RSS Series 不屬於任何一個 Feed，綁定框拿不到它。

推翻 brief §19 2026-09-26 那一列的「沒選的留給人」與「兩條以上啟用中才問」。

## 使用者拍板（2026-10-16）

- **劇集、電影各一條**：Route 分類型（`collection_type`），一條 Route 只收一種。Feed 上兩格都要填，Mikan 的劇場版不會因為有兩條電影 Route 而停住。
- **舊資料能推就推，不能就提示**：migration 裡，某一種類型的啟用中 Route 只有一條時就填它；否則留 `NULL`，Feed 列標出「要選 Route」，並給一個「改 Route」。選之前照現在的行為走（Route 不只一條的留在待綁定）。
- **選了或改了 Feed 的 Route 之後當場綁上**：只處理理由裡有 `route_ambiguous` 的待綁定列，用它存著的候選（`candidates_json[0]`，判出來的那一部）加上新的 Route 走 `bind_series`（`bound_by = system`），不重新上網查。

## 做什麼

1. **資料**：`rss_feeds.route_id` 改名為 `tv_route_id`，加 `movie_route_id`（同樣是 `ForeignKey("routes.id", ondelete="SET NULL")`）。migration 照上面的「能推就推」補值。從 Media 頁訂閱建的 Feed（`media_id` 有值）把它那一條 Route 寫在作品類型對應的那一欄。
2. **API**：`POST /rss/feeds` 的 `route` 換成 `tv_route`、`movie_route`。某一種類型有啟用中的 Route 卻沒給，422 `route_required`（新的 `RssRefusal`，照 development.md〈API 型別〉的四件事）；給的 Route 不是那一種，422 `route_kind_mismatch`。某一種類型一條啟用中的 Route 都沒有時，那一格不收、存 `NULL`。新增 `PUT /rss/feeds/{id}/routes`（`{tv_route, movie_route}`，同樣的驗證），回那一列，連同當場綁上的數量。`FeedOut` 的 `route_id` 換成兩欄。這是對外介面的破壞性變更，目前只有 Berth 自己的畫面在用，CHANGELOG 照票 83b 的寫法交代。
3. **自動綁定**：`_chosen_route` 依作品類型讀那一欄；Feed 的那一欄是 `NULL`、或那條 Route 停用了，才退回「只有一條」的規則，再不行才是 `route_ambiguous`（僅限舊資料或 Route 被刪的情況）。
4. **當場綁上**：`PUT /rss/feeds/{id}/routes` 成功之後，找出「長出它的 Feed」是這一個、而且理由含 `route_ambiguous` 的待綁定 RSS Series，候選的類型有 Route 就綁。「長出它的 Feed」的定義：這個 Series 最早那一筆 Feed Item 的 `feed_id`。命令要標 `@command`（`tests/unit/test_command_marks.py`）。
5. **手動綁定的預選**：`SeriesOut` 帶長出它的 Feed 的兩條 Route（例如 `feed_routes: {tv, movie}`，名字照 OpenAPI 慣例定）。`preselect` 的順序改成：Feed 那一種類型的 Route（必須在 `detail.routes` 裡）→ 作品的 `default_route_id` → 只有一條。下拉照樣顯示，可以改；確認區照舊重述資料夾名。
6. **畫面**：`FeedSection` 的新增表單在有一條以上啟用中的 Route 時就出現那一種類型的格子；只有一條時預填它，零條時不出現。沒有「不指定」。Feed 列說出兩條 Route；某一格是 `NULL` 而那一種類型有 Route 時，用 `assigned` 塗漆標「要選 Route」。另加一個就地展開的「改 Route」（不是 dialog，同 `SeriesBinder` 的確認區），文案說明會當場綁上幾部。i18n 的 zh-Hant、en 並列。
7. **文件**：brief §15「綁定」與 §19 那一列（新的一列寫今天的決定與理由）、plan §2.4 `rss_feeds`、§6 rss、CONTEXT.md 有必要才改（Feed 的定義要不要提 Route）、docs/development.md 的 `rss` 情境說明、CHANGELOG。progress.md「偏差與決定」記一行。

## 不做

- 不給 RSS Series 加 `feed_id` 欄位：「長出它的 Feed」從 Feed Item 推得出來，`CONTEXT.md`「不屬於任何一個 Feed」不變。
- 已綁定的 RSS Series 不因為 Feed 改了 Route 而搬家。

## 驗收

- [x] migration：兩種類型各只有一條啟用中的 Route 時兩欄都補上；某一種有兩條時那一欄留 `NULL`；`alembic upgrade`／`downgrade` 都跑得過（測試）
- [x] `POST /rss/feeds`：缺必填的那一格是 422 `route_required`，類型不符是 422 `route_kind_mismatch`，某一種類型零條 Route 時不要求（integration 測試）
- [x] 自動綁定：劇集照 `tv_route_id`、劇場版照 `movie_route_id`，依據各是 `feed_route`（services 測試，含兩條電影 Route 的情況）
- [x] `PUT /rss/feeds/{id}/routes`：舊 Feed 選了 Route 之後，原本 `route_ambiguous` 的待綁定列當場綁上並送單，其他理由的列不動（integration 測試）
- [x] 手動綁定：Feed 指定 Anime 時，作品沒認出來的那一列選好作品，「入庫到」預選 Anime；選了電影作品就照電影那一格（vitest）
- [x] 前端：新增表單沒有「不指定」，只有一條時預填；Feed 列的「要選 Route」與「改 Route」（vitest，zh-Hant 與 en）
- [x] e2e：`rss.spec.ts` 那一條改成「加 Feed 選 Route → 輪詢 → 那一部自動綁定」不再有一鍵候選這一步；另加一條「舊 Feed 沒有 Route → 改 Route → 當場綁上」，或改既有的；playwright 實跑截圖 1280 與 390 寬
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`pnpm -C web gen:api` 的產出一起提交；progress.md 已更新

## Comments

- 2026-10-17 code-review 沒處理的發現：
  - **Spec 軸——已處理（2026-10-17 使用者拍板排除）**：從 Media 頁訂閱建的搜尋 Feed 一律以 `_prebind` 綁到它那一部，另一種的那一格用不到。後端 `_route_kinds` 判斷它只用得到作品那一種，`FeedOut.route_kinds` 帶給畫面：另一格不標「要選 Route」、`PUT /rss/feeds/{id}/routes` 不要求（給了也存 `NULL`）、自動綁定不讀、`awaiting_route` 不算它；建 Feed 時那一格留空。測試：`test_rss_subscribe.py::test_only_the_works_kind_needs_a_route`、`test_rss_api.py::test_a_search_feed_of_a_series_asks_for_no_movie_route`、`RssPage.test.tsx`「從作品頁訂閱一部劇集的 Feed」。
  - **Standards 軸（判斷題，沒改）**：`FeedSection` 的 `AddFeed` 與 `FeedRoutes` 各有一份「動過的格子 ?? 預填」的合併，兩處只差 `FeedRoutes` 多一層 Feed 現值；tv/movie 的分支在 `_check_routes`、`_subscribed_routes` 各寫一次。
  - 真服務 e2e `tests/e2e/test_4_m3_rss.py` 改了加 Feed 的請求形狀（`tv_route`、`movie_route`），沒有跑（要整套服務，約 20 分鐘）。
