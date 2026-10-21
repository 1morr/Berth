# 131 — 週報：每週存一筆、週報頁、推摘要

**Status:** ready-for-agent

**Blocked by:** 129、130

**讀:** plan §11.5〈巡檢〉（週報每週存一筆的理由）；brief §14；`berth/models/event.py` 與事件型別（入庫、核准、rematch、Issue 收掉）；`berth/services/deletion.py` 的 `_purge`（會刪事件）；票 123 的通知寫入、票 124 的連結；DESIGN.md

## 為什麼

週報回答三件事：這週入庫了什麼、修了什麼、還有什麼等人。purge 會連事件一起刪，所以當下算好存下來，之後回頭看的舊週報不會跟著變。

## 做什麼

1. **開頭先 `/impeccable shape` 週報頁**（`.scratch/m4/weekly-report-shape.md`）。
2. 每週一次（週一早上，照容器時區）產生一筆週報存起來：入庫了什麼（依作品，季集範圍）、修了什麼（核准、rematch、Issue 被收掉或解決）、還有什麼等人（等你處理的總數與種類、巡檢開出的 Issue）。
3. 週報頁：最新一週與歷史；只有管理員看得到（M4 範圍）。
4. 給訂閱週報的管理員推一則摘要，附週報頁的連結（票 124）。
5. 同一週不重複產生（重啟、補跑都不會多一筆）。

## 驗收

- [ ] 一週的假資料 → 週報的三段內容正確（pytest）
- [ ] 產生之後 purge 一筆 Job，存下的週報不變（pytest）
- [ ] 同一週重跑不多一筆（pytest）
- [ ] 摘要推給訂閱的管理員、附連結（pytest）
- [ ] 週報頁與歷史（vitest；playwright 實跑 1280 與 390 附截圖）
- [ ] 全部檢查、pytest、vitest 綠；CONTEXT.md「週報」；CHANGELOG、progress.md 已更新
