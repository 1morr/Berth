# 34 — 真服務 e2e 恢復，能與試跑環境並存

**Status:** ready-for-agent

**Blocked by:** 32（e2e 對頁 2 的斷言要照不寫全域鍵之後的行為寫）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（§A3「真服務 e2e 從票 16 之後沒跑過」、「還原與清理」、改進清單 P1-8）；票 15、26、31 的 `## Comments`（撞名與 `CONFIG_ROOT` / `DATA_ROOT` 外洩）；plan §10；README 的 e2e 段落

## 為什麼

- 真服務 e2e 從票 16 之後沒在本機跑過。票 26、31 都記了同一個原因：撞名，不准動使用者的試跑環境。所以票 26 之後的行為（密碼規則、完成時照頁序再驗）只有單元測試與 Fake 後端在守。
- 撞名的來源：`deploy/docker-compose.yml` 寫死了專案名 `berth`、四個 `container_name`（`berth`、`berth-*`）、網路名 `berth`，host port 則讀 `.env`。
  `C:\Users\Roxy\berth-trial` 與 `C:\Users\Roxy\berth-audit` 用的也是這一份，兩者彼此都會撞。
- 票 15 記過另一個陷阱：e2e 匯出的 `CONFIG_ROOT` / `DATA_ROOT` 被之後的 `docker compose up` 繼承，試跑環境的 Berth 因此掛到 e2e 的資料庫。

## 做什麼

1. 讓 e2e 的整套服務有自己的專案名、容器名、網路名與 host port，只在 e2e 這邊覆寫。產品 compose 的容器名不改（票 16 的決定：使用者看到的是 `berth-*`）。
   如果有一個名字非得改產品 compose 才能覆寫，停下來回報。
2. e2e 的環境變數不外洩到呼叫它的 shell：只在 e2e 的程序或 compose 呼叫裡生效。
3. 補上票 26 之後的行為：qBittorrent 介面密碼規則、完成時照頁序再驗，以及 32 的「全域偏好不影響 Route」。
4. README 的 e2e 段落寫明：試跑環境開著也能跑，跑完不留容器。

## 驗收

- [ ] berth-trial 或 berth-audit 其中一套開著時，本機跑 `tests/e2e` 全綠；跑之前與之後 `docker ps` 比對，那一套的容器 ID 與狀態不變（指令與輸出貼在 Comments）
- [ ] CI 的 nightly e2e 綠燈（手動觸發一次，貼連結）
- [ ] 新增的 e2e 涵蓋票 26 的密碼規則、完成時照頁序再驗、32 的全域 `save_path` 改掉後送單仍成功
- [ ] 跑完之後呼叫端 shell 的 `CONFIG_ROOT` / `DATA_ROOT` 沒有被改（e2e 自己的測試或腳本守著）
- [ ] README 已改；全部檢查（`pre-commit run --all-files`）、test 綠燈
