# 87 — 簡化：四件已經分岔的小修（服務狀態一支端點、Route 歸屬一種量法、兩個逐字複本）

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S1、S3、S5、S6（位置、建議、要改的測試都在裡面）；`CLAUDE.md`（架構規則）

## 為什麼

票 86 的審計找到這四條：同一件事有兩份，而且兩份已經給出不同答案，或者有一份沒人讀卻讓人以為有作用。使用者（2026-10-13）照協調者建議全部要改，S1 刪一支對外 GET 也已同意。

## 做什麼

1. **S1**：留 `GET /health/detail`，刪 `GET /settings/services` 與前端的 `servicesQueryOptions`；設定頁改讀健康頁那一份快取。之後在健康頁按「重新檢查」，設定頁也看得到。`POST /settings/services/{kind}/test` 不動。
2. **S3**：`routes.owning_route` 改用路徑段數量「最深」；`claims._route_of` 改成呼叫它，找不到時照舊 raise。
3. **S5**：刪 `reconcile._categories`，改用 `qbittorrent.route_categories`。
4. **S6**：刪 `ParseContext.route_collection_type` 與所有寫入點（含 scripts），以及只為它存在的 import。

## 驗收

- [ ] S1：設定頁與健康頁共用一份查詢；有 vitest 守「健康頁重新檢查之後，設定頁讀到新的狀態」；`GET /settings/services` 已刪，門禁表與測試同步；`gen:api` 重跑
- [ ] S3：補一條測試，守「不正規但較淺的 Route 對上較深的 Route 時選較深的」，做變異驗證（改回字串長度要紅）
- [ ] S5、S6：沒有殘留的呼叫端
- [ ] plan（`plan.md:391`、`plan.md:285`）、CHANGELOG（刪端點記在 Removed）同步
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
