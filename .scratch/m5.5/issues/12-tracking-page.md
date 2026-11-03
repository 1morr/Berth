# 12 — 追更頁

**Status:** ready-for-agent

**Blocked by:** 09, 11

**讀:** spec〈範圍〉「追更頁」「新番區塊」；brief §13；plan §7；ADR-0015；`domain.WhyNot`；`GET /me/notifications`；`.scratch/m5.5/schedule-shape.md`

## 為什麼

管理員要一眼看出訂閱的作品哪些按時、哪些晚了、卡在哪。沒接 Discord 的管理員只能從這一頁知道有遲到。

## 做什麼

1. **先 `/impeccable shape`**：輸出 `.scratch/m5.5/tracking-shape.md`。
2. **`/schedule/tracking`**（admin，新番區塊的「追更」分頁，排在時間表與訂閱之間）：依作品一列，欄位為字幕組、已播到、已入庫到、狀態。
   - 狀態是 `domain.WhyNot` 的結論，加「晚 N 天」與「可能是下一輪」（11 的 `next_run`）。
   - **下載停滯要說出來**：`WhyNot` 把 `stalled` 算成 `DOWNLOADING`，這一頁另外顯示「下載停滯」。
   - 排序：要人動手的在前，準時的在後，「斷更很久」（11 的 60 天視窗）收起。
   - 讀取命令 `Effect.READ`，端點進 `ADMIN_PREFIXES`，`TestWhoEachEndpointIsFor` 補一列。
3. **收不到通知時頁首說一句**：這位管理員沒有 bot、沒填 Discord ID、沒訂閱「等你處理」或 Discord 到不了時，提示遲到只會顯示在這裡、不會通知，連到 `/settings/notifications`。讀 `GET /me/notifications` 就夠，不加端點，不另做其他通知管道（ADR-0015）。
4. **時間表卡片**多「晚 N 天」狀態（只有 admin 看得到字幕組相關的部分，比照 09）。
5. 文件：brief §13、plan §7 路由表、`CONTEXT.md`（追更）。

## 驗收

- [ ] 追更頁把停滯顯示成「下載停滯」，不是「下載中」；「斷更很久」預設收起（e2e，桌機與 390px）
- [ ] 沒接 Discord 時追更頁頁首有提示；收得到通知的管理員看不到提示（e2e 或 vitest）
- [ ] `/schedule/tracking` 對一般使用者 403 或導向（`TestWhoEachEndpointIsFor`＋e2e）
- [ ] 時間表上晚了的卡片顯示「晚 N 天」
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新
