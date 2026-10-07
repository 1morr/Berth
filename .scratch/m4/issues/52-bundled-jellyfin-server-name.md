# 52 — 套件內 Jellyfin 的伺服器名稱設成「Berth」

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S4 Jellyfin 第一點、改進清單 P2-11）；brief §20.7、§20.9；plan §9.4

## 為什麼（2026-10-06 審計，實測）

- 精靈沒設 ServerName，套件內 Jellyfin 的伺服器名稱是空的，用戶端顯示成容器 ID（例如 `d6c8b33ddada`）。
- **2026-10-06 使用者決定**名稱用「Berth」。

## 做什麼

1. Jellyfin 初始化序列（plan §9.4）在套件內那一台寫 ServerName = `Berth`。端點與欄位先查 Jellyfin 12 的 OpenAPI，寫進 brief §20.9（附來源）。
2. 只在 Berth 跑初始化的那一次寫。已初始化的套件內 Jellyfin 與既有 Jellyfin 都不改（33 的定義：伺服器名稱是全域設定）。

## 驗收

- [x] 整合測試（雙向）：套件內未初始化 → 寫 ServerName；已初始化或既有 → 不寫
- [x] 33 的寫入白名單閘門同步更新，仍綠
- [x] 實跑一次全新套件內 Jellyfin，`/System/Info/Public` 的 `ServerName` 是 `Berth`（輸出貼在 Comments）
- [x] plan §9.4、brief §20.9 已改
- [x] 全部檢查（`pre-commit run --all-files`）、test、真服務 e2e 綠燈

## Comments

2026-10-07 實跑：`uv run --env-file .env python -m tests.e2e.stack` 起的全新套件內 Jellyfin（`lscr.io/linuxserver/jellyfin:version-12.1ubu2604`，容器 hostname `82c2326baf4b`），精靈跑完後：

```
$ curl -s http://localhost:28096/System/Info/Public
{"LocalAddress":"http://[::1]:8096","ServerName":"Berth","Version":"12.1.0","ProductName":"Jellyfin Server","OperatingSystem":"","Id":"1013b29dcd9c41cc8a3167b022b936c4","StartupWizardCompleted":true}
```

e2e 24 passed（含新的 `test_the_bundled_jellyfin_is_named_berth`）。那一輪的 image 是 code-review 修正前 build 的；修正只改了 `_Runner` 收參數的方式與替身，送給 Jellyfin 的請求不變，整合測試（3620 passed）守著。

2026-10-07 code-review（Standards 與 Spec 兩軸）沒有處理的發現：

- `test_a_bundled_jellyfin_is_named_berth` 斷言寫字面值 `"Berth"` 而不是 `BUNDLED_SERVER_NAME`：刻意釘住使用者拍板的那個名字，常數改了這條要紅。
- 既有而還沒初始化的 Jellyfin，`system.xml` 事先放的名字仍會被第 2 步清空（票 52 之前就是如此）。要保住得先讀 `GET /Startup/Configuration`，不在本票；記在 plan §9.4 與 progress.md「偏差與決定」。
