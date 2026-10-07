# 45 — 只存驗過的憑證、錯誤標在欄位上

**Status:** done

**Blocked by:** 39（頁 4 用上共用表單之後，欄位錯誤一次改三頁）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S1 頁 5「錯的 key 也被存下」、§E 共同慣例 2 與 5、「Berth 精靈哪裡不統一」第 6、7 條、簡化方案 E-6、改進清單 P2-3）；票 21、25、31；brief §16.3；plan §9.3

## 為什麼（2026-10-06 審計）

- 錯的 TMDB key 照樣存下，右欄寫「已存下，沒通過驗證」。Home Assistant 是驗過才 `create_entry`。
- 錯誤都是頁面層級的橫幅加手動步驟，不標在欄位上（只有頁 1 的帳號規則例外）。Sonarr 與 Home Assistant 都會把錯誤標到欄位：位址錯標位址，帳密錯標帳密。

## 做什麼

1. TMDB 與既有服務的憑證改成測過才存。`GET /setup/tmdb` 的回應語意會變，欄位可以保留，但「已存下，沒通過驗證」這個狀態要消失。記進 CHANGELOG。
2. 連線錯誤分兩類，標在各自的欄位旁：
   - 位址類：`unreachable`、`scheme_*`、`protocol_mismatch`、localhost
   - 憑證類：`auth_required`、`ip_banned`、API key 錯

   其餘的留在頁面層級。人話、手動步驟、技術細節的分層照票 21 / 25 保留。

## 驗收

- [x] 整合測試（雙向）：錯的 TMDB key 不存、對的才存；既有服務的憑證同一條
- [x] vitest：位址錯時錯誤標在位址欄、帳密錯時標在帳密欄（頁 1、2、4 三頁同一個元件）；`aria-describedby` 指到錯誤
- [x] playwright 實跑三種錯誤，附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**做了什麼**

- 後端：既有服務先拿表單那一組測（`setup._candidate` + `_test_connection` 改收連線），測過才存；測不過是 `ConnectionFailedError` → 400 `connection_failed`，`ChoiceRefusalOut.attempt` 帶那一次的結論，選擇、連線、頁的結果、Route 檢查都不動。TMDB `verify_tmdb` 測不過一律不存（06i 那一條併進來），`api_key_present` 只在驗過時為真。
- qBittorrent 連錯次數改記在 `SetupQbittorrent.auth_failures`（以位址為鍵），`ServiceTest.auth_failures` 拿掉：沒存下的那一次也要數。
- 前端：`signals.connectionField`（每種理由一格的 `Record`，後端多一種理由 tsc 逼人歸類）；`ExistingForm` 位址類標位址欄、憑證類標憑證欄（qBittorrent 兩格都標、那一句寫一次、兩格的 `aria-describedby` 指到它，`Field` 多 `invalid` / `describedBy`）、其餘在表單裡；下面說「這一組沒有存下」與技術細節。補法那一句由 `fixOf` 與連線卡共用。剖面拿掉「已存下，沒通過驗證」。
- 演練伺服器 `mixed` 的既有 qBittorrent 只收 e2e 那一組帳密，主機名帶 `typo` 連不上、帶 `old` 是 4.3.9；`existing.spec` 頁 2 先各錯一次。

**實跑**：`pnpm -C web e2e` 的 `existing` / `existing-390` 截圖 `2-qbittorrent-wrong-address`（位址欄紅、那一句在欄下）、`2-qbittorrent-wrong-login`（帳號與密碼兩格紅、一句）、`2-qbittorrent-outdated`（欄位都不紅、表單裡「至少要 qBittorrent 4.4，這一台是 v4.3.9」）、`4-indexers-wrong-key`（API key 欄）；右欄仍是「尚未取得」。

**code-review**

- 已修（Standards）：`_candidate` 非 Jellyfin 直接回傳入的那一組；理由 → 欄位改成 `Record<ConnectionReason, …>`。
- 已修（Spec）：補 vitest「填 localhost 而連不上，位址欄說那一句」。
- 未處理：TMDB key 被拒仍在 `StepLine`、不標到 key 欄（驗收只點名頁 1、2、4）；0.1.0 測不過時存下的那一條紅燈纜繩留著，剖面說「還沒填」、下面仍是那一次的失敗（不寫 migration，下一次測過就換掉）；`setup.py` 照服務分三支的讀寫有四處（`_candidate`、`_stored_connection`、`_remember_connection`、`_test_connection`），沒有收成一組；「Jellyfin 的 `auth_required` 不算表單的錯」前後端各寫一次；`auth_failures` 打錯又放棄的位址會留一列（量很小）。
