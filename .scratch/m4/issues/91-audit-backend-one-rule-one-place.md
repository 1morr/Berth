# 91 — 簡化（後端）：同一個判斷收成一份

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S8–S13、S15–S17；票 84 的 Comments〈code-review 未處理〉；`CLAUDE.md`（架構規則、依賴方向）；brief §6.3（S16 要改）

## 為什麼

票 86 審計的第二級：同一個判斷寫了兩三份。現在答案還一致，但改一處就會分岔。使用者（2026-10-13）照協調者建議要改。票 84 收尾時留下的「搜尋內部函式收 8 個參數」也是同一類，一起處理。

## 做什麼

照審計各條的「建議」做，不另外擴大範圍：

1. **S8**：拿掉前端沒讀的 `JellyfinSetupOut.libraries`、`LibraryOut` 與 services 端的來源；「有沒有 TVDB」收成一個 `uses_tvdb`。資料庫快照不動。
2. **S9**：「Route 的 Jellyfin 媒體庫先比 id、沒有才比名字」收成一支函式，三處共用。
3. **S10**：刪三個 `_utcnow`，八處改用 `models.types.utcnow`；pipeline 的注入時鐘與 `reconciling.py` 的本地時間不動。
4. **S11**：`IN_CLIENT_STATES` 與 `IN_FLIGHT` 留一份。
5. **S12**：qBittorrent 改用 `adapters/versions.parse_version`。
6. **S13**：「沒登入算 system」收成 `api/gate.py` 的一支函式。
7. **S15、S16**：刪 `CjkHints.hardsub`；刪 `ReleaseInfo` 的 `video_codec`、`bit_depth`、`audio`。同一個 commit 改 brief §6.3 與 plan，progress.md「偏差與決定」記一行。
8. **S17**：TMDB 的三種共同錯誤收成 `tmdb_problem(exc)`。`NotFoundError` 那一支留在 `media.py` 原處，探索頁 404 的說法不變。審計把「要不要一起改」列給使用者決定，協調者選維持現狀，這張不改行為。
9. **票 84 留下的**：`services/search` 的 `_texts` 收 8 個參數（`missing`、`season`、`from_season` 與 `choice` 一起走），收成一個型別。「別名不記」在 models、service、API 三層各有理由（見票 84 Comments），留著。前端那一份如果能改讀後端給的資訊就收掉，不能就在票的 Comments 寫明理由。

## 驗收

- [x] 每一條做完後，審計列出的重複位置只剩一份；沒有殘留的呼叫端
- [x] 行為不變：既有測試照舊綠。S8 的 API 回應形狀改了，要重跑 `gen:api`、改 `src/test/fixtures.ts`
- [x] 解析器有改動（S15、S16），跑 `berth bench`，`auto_wrong` 不得上升，貼輸出
- [x] import-linter 綠（依賴方向沒破）
- [x] brief §6.3、plan、CHANGELOG（S8 刪欄位）同步；全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

**做法**（開工 `4d809cd`）：

- S8：`LibraryOut`、`JellyfinSetupOut.libraries`、`LibraryView`、`_library_view` 刪掉；**沒有另加 `uses_tvdb(names)`**——
  `tvdb_fetchers` 改收 `JellyfinLibrary | SetupLibrary`（快照已經攤平），是唯一比對 `TVDB_MARKER` 的地方，要布林的地方寫
  `bool(tvdb_fetchers(x))`。另加一支 `uses_tvdb` 只是包一層 `bool`，而 `tvdb_fetchers` 本身仍得自己比一次。測試改讀
  `GET /api/setup/routes` / `read_route_status`（`test_setup_jellyfin.py` 加 `choices` helper）。
- S9：`routes.route_library_matches(library, library_id, library_name)`，`_library_key` 的兩處（勾選表的 `has_route`、
  規劃的 `routed` 去重）、重跑檢查、健康檢查的 TVDB 都改呼叫它。**連帶行為**：沒有 `ItemId` 的舊 Route，遇到快照上有 id
  的同一個媒體庫，現在以名字認得（`_library_key` 拿名字比 id，認不得）。新測試
  `test_a_route_without_an_item_id_is_known_by_its_library_name` 守著，還原成舊比對時紅。
- S13：`api/gate.current_actor(request)`。
- S17：`services/tmdb.tmdb_problem(exc | None)`，`None` 是沒有憑證；`NotFoundError` 那一支留在 `media.py`。
- 票 84：`services/search.QueryScope`（`choice`、`missing`、`season`、`from_season`），`plan_queries` / `search_torrents`
  收 `scope=`（預設 `DEFAULT_SCOPE`，ruff B008 不收預設值裡的呼叫）；`api/search._scope` 組它，原本的
  `_refuse_bare_scope` 併進去。

**前端「別名不記」那一份留著**：`SearchPanel.rememberKinds` 濾掉 `alias` 才送 `PUT /search/names`。後端沒有告訴前端哪些種類
記得住（`SearchQueriesOut` 只有 chip 與它的種類），要收掉得加一個回應欄位（或讓 API 默默丟掉別名，與 service「拒絕、不默默
丟掉」相反），超出這張票「不另外擴大範圍」。

**bench**（S15、S16 改前改後同一份）：

```
overall   904    904/904   270/270  247/247     253           0           86      0       42                 123            37                363
high: 0/112 wrong (0.0%)  medium: 0/141 wrong (0.0%)
```

**code-review（兩軸 opus）**：Spec——S8 介面與票面不同、S9 行為有變而沒測試沒記，已補測試、記在上面與 progress.md。
**未處理**（Standards，判斷題）：三處 `next(... route_library_matches ...)` 形狀相同（`read_route_status` 是反方向找 Route，
收成一支 find 也只省兩處）；規劃的 `routed` 用 `(id, name)` tuple；`tmdb_problem(None)` 以 `None` 表示沒有憑證、回 tuple
展開成位置參數；`chosen = scope.choice or await _default(...)` 在預覽與搜尋各寫一次（票 84 之前就是這樣）；`api/gate.py`
的模組 docstring 沒提 `current_user` / `current_actor`。
