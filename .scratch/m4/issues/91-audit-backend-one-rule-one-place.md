# 91 — 簡化（後端）：同一個判斷收成一份

**Status:** ready-for-agent

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

- [ ] 每一條做完後，審計列出的重複位置只剩一份；沒有殘留的呼叫端
- [ ] 行為不變：既有測試照舊綠。S8 的 API 回應形狀改了，要重跑 `gen:api`、改 `src/test/fixtures.ts`
- [ ] 解析器有改動（S15、S16），跑 `berth bench`，`auto_wrong` 不得上升，貼輸出
- [ ] import-linter 綠（依賴方向沒破）
- [ ] brief §6.3、plan、CHANGELOG（S8 刪欄位）同步；全部檢查、pytest、vitest 綠；progress.md 已更新
