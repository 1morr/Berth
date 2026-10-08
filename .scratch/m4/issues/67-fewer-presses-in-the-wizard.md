# 67 — 精靈再省幾按：連線＋登入合一、既有 Prowlarr 一鍵加站、TMDB 下一步先測

**Status:** ready-for-agent

**Blocked by:** 63（頁 1 加了 `/data` 探測之後再合併表單）、64（頁 3 改完再算按鍵）

**讀:** `docs/research/usability-audit-2026-10-07.md` §4（全節，C1、C3、C4）、§8 P2-10；`notes/r2-docs-and-research.md` §2.2（Sonarr 的 Save 會再測）、§2.3（Seerr 位址與管理員帳密同一頁）；plan §9.3；M4 票 38、39、44、45

## 為什麼

審計 §4.1 量到的必按數：套件內 12、既有 17。多出來的主要是：

- 既有 Jellyfin 先「測試連線」，通過後才長出登入表單，再按「登入」（Seerr 是同一頁、一顆 Sign In）。
- 既有 Prowlarr 加推薦站要「測試全部 → 勾 → 加入」，套件內一顆鍵（票 44）。
- TMDB 要「測試 TMDB」再「前往下一個泊位」（Sonarr 的 Save 自己會再測）。

## 做什麼

1. 既有 Jellyfin：位址＋管理員帳密同一個表單，一顆「連線並登入」。
   - 錯誤照票 45 標在欄位上：位址類標位址，帳密類標帳密，版本、非管理員在表單層級。
   - 還沒初始化的那一台照現在的分支（建管理員）。
2. 既有 Prowlarr 也有「測試推薦站，加入通過的」主鍵，條件與套件內相同（Prowlarr 已有站時放進「進階」）。
3. TMDB 頁按「前往下一個泊位」時，若 key 還沒驗過就先測，測過才走；保留單獨的「測試 TMDB」。
4. 重算 §4.1 的表：S1、S2 兩條路徑的輸入與必按數，寫進票的 Comments。

## 驗收

- [ ] 整合測試：Jellyfin 一次呼叫完成連線與登入，錯誤分類到欄位；既有 Prowlarr 一鍵加站
- [ ] vitest：三處的新流程（zh-Hant 與 en）
- [ ] playwright 實跑 S2（全既有）：必按數比審計時少，附截圖與計數
- [ ] 全部檢查、test、前端 e2e 綠燈；plan §9.3、README guide 同步；progress.md 記一行
