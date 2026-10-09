# 80 — 精靈：點下去馬上有反應；「也用這組」在頁 1 就擋好、頁 2 不再重問

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（只動精靈前端，與 79、69 不重疊）

**讀:** M4 票 15（沿用 Jellyfin 帳密）、40（頁 1「也用這組」）、07（介面登入）；`web/src/setup/ServiceChoice.tsx`（`pick`、`TestLine`）、`web/src/setup/interfaceLogin.ts`（`LOGIN_RULES`、自動帶入）、`web/src/setup/QbittorrentStep.tsx`、`web/src/setup/IndexerStep.tsx`、`web/src/setup/InterfaceLoginFields.tsx`、頁 1 的「也用這組」；brief §16.3

## 為什麼（2026-10-09 使用者本機試用）

1. **點「套件內」之後整頁沒有反應**：
   - 第一次用滑鼠點「套件內」，`pick` 會直接送出 `onChoose({ origin: 'bundled' })`。
   - 但「測試中」那一條（`TestLine`）要等 `service` 已經有結果才畫得出來。第一次還沒有結果，所以請求在路上那幾秒，畫面什麼都沒有，使用者以為壞了。
   - 用鍵盤選才有確認框和忙碌中的鍵；滑鼠那條路沒有。
2. **頁 1 勾了「也用這組」，到頁 2 又問一次「沿用」，而且用不了**：
   - 使用者在頁 1 用了 4 個字的 Jellyfin 密碼，照樣勾得起「也用這組」。頁 1 沒有檢查 qBittorrent 的規則：帳號至少 3 個字、不能有冒號，密碼至少 6 個字（`LOGIN_RULES`）。
   - 到頁 2，自動帶入被擋下，上面寫「不能沿用」。下面的表單卻照預設勾著「沿用 Jellyfin 帳密」，密碼框還標紅：同一件事說了兩次，那個勾選根本用不了。

## 做什麼

1. **點下去當下就有回饋**（Jellyfin、qBittorrent、Prowlarr 三頁共用 `ServiceChoice`）：
   - 送出的那一刻，被點的那一格就是選中的樣子；下面馬上出現「正在設定套件內 qBittorrent，連線測試中…」這類忙碌中的狀態，並且有讀屏宣告。
   - 回來之後換成結果。請求失敗時照舊顯示 `RequestFailed`。
   - 請求在路上時，不能再點另一格送出第二個請求。
2. **頁 1 就擋好「也用這組」**：
   - 照套件內服務的登入規則，即時檢查頁 1 的帳號與密碼：
     - 建立管理員時，邊打邊檢查；
     - 登入既有帳號時，送出前檢查。
   - 不合的話，「也用這組」停用並說出原因（例如「密碼少於 6 個字，qBittorrent 不收；到頁 2 另設一組」），zh-Hant 與 en 並列。
   - Prowlarr 目前沒有規則（`LOGIN_RULES.prowlarr = null`）。只有 qBittorrent 不合、Prowlarr 合的情況，怎麼說由實作決定，理由寫在 Comments。
3. **頁 2、頁 4 不重問**：
   - 頁 1 帶過來、而且設好了：只顯示「已沿用 Jellyfin 帳密（Admin）」，加一顆「改用另一組」。
   - 頁 1 沒勾，或帶了但不合規則：表單直接是自設的三格，不再預設勾「沿用」。
   - 「不能沿用」那則提示只說一次。
   - 頁 1 沒勾、使用者在頁 2 自己想沿用：照舊可以勾，規則不合時勾選停用並說原因，不是勾了才紅。
4. **UI 走 `/impeccable`**：先 `shape`，收尾 `critique` / `polish`。

## 驗收

- [ ] 三頁第一次點「套件內」，當下就看得到選中與忙碌中的狀態；請求在路上時不能送第二次；vitest 守著
- [ ] 頁 1 的帳密不合 qBittorrent 規則時，「也用這組」停用並說原因；合的時候照舊能勾；vitest 守兩個方向
- [ ] 頁 2／頁 4：帶過來而且設好了只顯示摘要與「改用另一組」；沒帶或不合規則時不預設勾「沿用」；「不能沿用」只說一次；vitest
- [ ] Playwright 實跑：精靈從頭走一次，用 4 個字的密碼與 8 個字的密碼各一輪，附截圖。用隔離環境（專案名 `berth-t80`、另一組 port）；**不准碰使用者的 `berth-local`**
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新
