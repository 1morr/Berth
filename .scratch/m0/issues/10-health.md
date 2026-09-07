# 10 — 健康檢查迴圈、健康頁與服務設定頁

**Status:** ready-for-agent

**Blocked by:** 07、09

**讀:** plan §3.2（health_checker）、§6（health、settings、routes 群組）、§9.5、§11.1（T0.8）；brief §16.2

## 做什麼

背景迴圈定期跑四項健康檢查（Jellyfin、qBittorrent、索引站、Route 硬鏈接與跨服務可見性），健康頁顯示每個服務與每個 Route 的狀態、最後成功時間、失敗原因與修正建議；服務設定頁可重測連線、重新套用建議設定。

迴圈以 asyncio task 在 lifespan 啟動，各服務獨立 try/except 與退避，一個服務掛掉不拖垮其他檢查。

## 驗收

- [ ] `health_checker` 在 lifespan 啟動與關閉，關閉時不留 pending task
- [ ] `GET /api/health` 匿名回 ok / degraded；`GET /api/health/detail` 需登入，回逐服務與逐 Route 的明細與最後成功時間
- [ ] 健康頁四項綠燈
- [ ] 停掉任一服務後 5 分鐘內該項變紅，顯示原因與修正建議；其餘三項不受影響
- [ ] 服務重新啟動後自動恢復綠燈，不需重啟 Berth
- [ ] 設定頁可對每個服務「測試連線」，結果即時顯示
- [ ] qBittorrent 關鍵設定漂移時顯示差異與「還原建議設定」按鈕
- [ ] Route 的健康結果寫回 `routes.health_status` 與 `health_detail_json`
- [ ] 健康頁走 impeccable `shape`
- [ ] playwright 跑通全綠與其中一項紅燈兩種狀態並附結果

## Comments
