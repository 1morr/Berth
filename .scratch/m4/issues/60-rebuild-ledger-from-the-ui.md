# 60 — 重裝之後在畫面上把帳本找回來

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E6、§3 S4（重裝那兩列）、§8 P1-5、P2-8；截圖 s4-31～s4-36；README〈帳本重建（`berth rebuild-ledger`）〉；plan 中 Reconciler 與 `rebuild-ledger` 的章節；CONTEXT.md 的 Ledger Entry、Unmanaged、Claim

## 為什麼（審計實跑）

- 搬走 Berth 的 DB 再跑精靈（或 DB 遺失）之後：
  - 作品頁同時寫「在 Jellyfin 看」和「還沒有任何檔案入庫」，下載頁全空；使用者很可能重複下載同一部。
  - 唯一的提示是待處理裡一件「無主 torrent」，按鈕「認領並建立下載」沒說會做什麼。
  - 完成頁寫「跳過：沒有」，沒有任何地方提 `rebuild-ledger`。
- 精靈完成後打開 `/setup` 會靜默導向設定頁；「怎麼重跑精靈」沒有任何文件寫。
- 使用者拍板 E6：偵測到媒體庫裡有 Berth 不認得的檔案時，在畫面上給「從媒體庫重建帳本」。它就是 `rebuild-ledger`：只加不刪、可以重跑。

## 做什麼

1. **先 `/impeccable shape`**：決定提示出現在哪裡。候選位置是完成頁、待處理、作品頁。要寫出「為什麼會這樣」：重裝或 DB 遺失。
2. 偵測：Route 的寫入目標底下有 Berth 帳本不認得的媒體檔時，給出提示與一顆「從媒體庫重建帳本」。
   - 按下去跑與 CLI 同一個命令（`@command`，標成可重跑、不刪任何東西），完成後說找回了幾個、有幾個變成 Unmanaged。
3. 作品頁的「檔案與版本」在帳本空、但 Jellyfin 有這部時，說「Jellyfin 有，Berth 的紀錄裡沒有」，並連到重建。不要寫「還沒有任何檔案入庫」。
4. 「無主 torrent」的按鈕說清楚會做什麼（認領成一筆下載、之後照常入庫或對帳）。
5. 精靈完成後打開 `/setup`：導向設定頁時說一句「精靈已經完成，之後的修改在這裡」；README 寫明重跑精靈的方法與後果（要重貼 TMDB key、帳本靠重建）。

## 驗收

- [ ] 整合測試：帳本空、媒體庫有 Berth 命名的檔案時偵測得到；重建之後作品頁的檔案列回來；再按一次不重複（冪等）
- [ ] vitest：提示、作品頁的新文案、無主 torrent 的說明（zh-Hant 與 en）
- [ ] 實跑：入庫一部 → 搬走 DB → 重跑精靈 → 按重建 → 作品頁與下載頁的樣子，附截圖
- [ ] 全部檢查、test、前端 e2e 綠燈；README、plan、CHANGELOG 同步；progress.md 記一行
