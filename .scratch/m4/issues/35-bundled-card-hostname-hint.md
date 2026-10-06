# 35 — 「套件內」卡片的主機名提示要準、會更新

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S3 第一列、§C3 第 2 條、改進清單 P1-3）；票 30（第 3 點與它的 Comments）；brief §16.3「不偵測、不判定，但選完要測試」；plan §9.3

## 為什麼（2026-10-06 審計，實測）

- 套件內 qBittorrent 容器停掉時，卡片說「這套 compose 沒有起 qBittorrent」。實際上它在 compose 裡，只是停了。截圖 s3-02。
- 重啟它、重新測試轉綠之後，卡片仍寫「沒有起」。截圖 s1-04。
- 票 30 的做法是只查 DNS。停掉的容器與不在 `COMPOSE_PROFILES` 裡的容器，DNS 一樣解不到，所以 Berth 分不出這兩種，文案要同時涵蓋兩種情況。

## 做什麼

1. 文案改成「沒在跑」，補法同時列出兩種：加回 `COMPOSE_PROFILES` 再 `up -d`，或容器停了就 `docker compose start <服務>`。不另外加 Docker socket。
2. 那一頁的連線測試成功後，卡片的主機名狀態跟著更新。主機名查詢的結果不再停留在進頁那一刻。

## 驗收

- [ ] vitest（雙向）：主機名解不到時卡片寫「沒在跑」並列兩種補法；同一頁連線測試成功後加註消失
- [ ] zh-Hant 與 en 並列，「沒有起」不再出現
- [ ] playwright 實跑：停掉套件內 qBittorrent → 卡片加註 → 啟動 → 重新測試轉綠、加註消失；附截圖
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
