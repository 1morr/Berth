# 104 — 精靈：既有分支的說明去重、跨頁一致性收尾

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 103 的 Comments（critique 那一段）；`.impeccable/critique/2026-10-14T05-22-48Z__web-src-pages-setuppage-tsx.md`；`PRODUCT.md`、`DESIGN.md`（Values Sit On Their Line Rule、塗漆規則）；`CONTEXT.md`

## 為什麼

票 103 收尾的 `/impeccable critique`（27/40）提了五個問題。使用者（2026-10-14）選了收 P1 與 P2 的一致性那一條成一張票；其餘三條（頁 4 孤立的「之後再說」、頁 2／4 位址沿用頁 1 的主機、指向句與完成頁的峰終）這一輪不做，指向句維持頁 1、2、4 各說一次。

## 做什麼

1. **既有分支說明去重（P1）**：頁 2 選既有、完成之後，「不改偏好」在 lede、這裡能做、卡片、剖面、完成提示說了 5 次；探測 torrent 說了 3 次。每件事只在一處說，唯一要使用者動手的那件（「設了『torrent 加入時執行外部程式』會觸發一次」）獨立成一行、放在測試鍵附近。頁 1、頁 4 照同一個原則檢查。先 `/impeccable distill`，390 寬的版面再 `/impeccable layout`。
2. **一致性收尾（P2）**，`/impeccable polish`：
   - 頁 4 還沒選時的標題與頁 1、頁 2 同一個形狀（「先選 X 是哪一台」）。
   - 頁 3 Route 列「已繫上」與頁 6 同一列的塗漆一致；頁 2 套件內完成時不疊三顆綠章。
   - 介面登入在同一個狀態下，重新整理前後說同一句（現在是「已沿用 Jellyfin 帳密（skipper）＋改用另一組」與「Prowlarr 介面的帳號：skipper＋更換登入」）。
   - 頁 2 剖面有「介面登入」一列、頁 4 沒有：兩頁同一套列。
   - 頁 1 勾了「套件內 qBittorrent 與 Prowlarr 的介面也用這組」並送出之後，剖面不再說「不存下：你的密碼（只交給 Jellyfin）」。
   - 頁 1 套件內鎖定說明「同一台換了位址可以改」與「這裡能做」說套件內位址由 compose 決定，兩句對齊。

## 驗收

- [ ] 第 1 點：頁 2 既有完成狀態下，「不改偏好」與探測 torrent 各只出現在一處，有 vitest 守著（zh-Hant 與 en）；外部程式那一句獨立可見
- [ ] 第 2 點每一小項有 vitest（zh-Hant 與 en）
- [ ] playwright 實跑頁 1、2、4（套件內與既有）1280 與 390 寬截圖；不碰使用者的 `berth-local`
- [ ] `/impeccable critique` 前後分數記在 Comments（前一輪 27/40）
- [ ] 全部檢查、vitest、前端 e2e 綠；progress.md 已更新
