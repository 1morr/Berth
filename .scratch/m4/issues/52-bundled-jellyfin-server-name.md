# 52 — 套件內 Jellyfin 的伺服器名稱設成「Berth」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S4 Jellyfin 第一點、改進清單 P2-11）；brief §20.7、§20.9；plan §9.4

## 為什麼（2026-10-06 審計，實測）

- 精靈沒設 ServerName，套件內 Jellyfin 的伺服器名稱是空的，用戶端顯示成容器 ID（例如 `d6c8b33ddada`）。
- **2026-10-06 使用者決定**名稱用「Berth」。

## 做什麼

1. Jellyfin 初始化序列（plan §9.4）在套件內那一台寫 ServerName = `Berth`。端點與欄位先查 Jellyfin 12 的 OpenAPI，寫進 brief §20.9（附來源）。
2. 只在 Berth 跑初始化的那一次寫。已初始化的套件內 Jellyfin 與既有 Jellyfin 都不改（33 的定義：伺服器名稱是全域設定）。

## 驗收

- [ ] 整合測試（雙向）：套件內未初始化 → 寫 ServerName；已初始化或既有 → 不寫
- [ ] 33 的寫入白名單閘門同步更新，仍綠
- [ ] 實跑一次全新套件內 Jellyfin，`/System/Info/Public` 的 `ServerName` 是 `Berth`（輸出貼在 Comments）
- [ ] plan §9.4、brief §20.9 已改
- [ ] 全部檢查（`pre-commit run --all-files`）、test、真服務 e2e 綠燈
