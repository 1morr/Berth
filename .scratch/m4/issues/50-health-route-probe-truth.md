# 50 — 健康頁 Route 的 5/6 講真話

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S5 第 2 點最後、「Berth 精靈哪裡不統一」第 11 條、§3.2 健康頁那列、改進清單 P2-8）；progress.md「偏差與決定」M4 票 19「qBittorrent 探針不在 5 分鐘的健康迴圈裡跑」；brief §16.2；plan §3.2

## 為什麼

- qBittorrent 探針不在 5 分鐘的健康迴圈裡跑（票 19：校驗會觸發「完成時執行外部程式」，每 5 分鐘一次會變成通知洪水），所以健康頁的 Route 永遠是 5/6。
  那一條寫「尚未執行」，Route 卻顯示「已繫上」。
- **2026-10-06 使用者確認**票 19 的那條偏差：探針維持不進迴圈，畫面改成講真話。

## 做什麼

1. 健康迴圈裡沒跑的探針，顯示「沿用上一次結論」與那一次的時間；從來沒跑過的才是「尚未執行」。
2. 上一次的結論要存下來，才能沿用。若現在沒存，就補上。
3. progress.md 票 19 那條的「待使用者確認」改成「已確認（2026-10-06）」。

## 驗收

- [x] 整合測試（雙向）：精靈或「重新檢查」跑過探針之後，健康迴圈那一輪顯示沿用與時間；從沒跑過的顯示尚未執行
- [x] vitest：Route 卡片的文案（zh-Hant 與 en）
- [x] playwright 實跑健康頁，附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

- 2026-10-07 實跑（`healthy` 演練情境、playwright）：健康頁 Movies「6 / 6 通過」，「qBittorrent 讀得到 Berth 寫的檔案」那一條是「已完成」加「沿用上一次的結論 · 52 秒前」與為什麼、去哪裡重問；Route 設定對 Movies 按「重新檢查」後，那一條不再說沿用（三條剩兩條）；390 寬英文版沒有溢出。截圖 `.playwright-mcp/t50-health-carried-1280.png`、`t50-health-carried-390-en.png`（gitignored）。
- code-review（兩軸 opus）處理掉的：探到之後被打斷的「重新檢查」會退回上一次的結論、進行中誤標沿用（`_progress` 當下存結論、有 `running` 不說沿用）；重新檢查後再進迴圈與舊資料列的整合測試補上；`_progress` 改 `model_copy`；`_row` 改名 `_check_row`；時間相等的契約寫明；按鈕名改插值；文案「才會」改成「要再問一次」。
- 未處理（判斷題，留著）：`probe` / `probed_at` 收成一個型別（Data Clumps）——兩個欄位，收起來要動持久化 JSON 的形狀；`probe_carried` 靠兩個時間相等認出「這一輪問的」而不另存旗標——由 `_run_checks` 寫同一個 `moment` 保證，註解寫明；新測試裡 `RouteCheck.DOWNLOAD_VISIBLE.value` 與 `"download_visible"` 並用，沿用既有測試的寫法。
