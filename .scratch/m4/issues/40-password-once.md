# 40 — 密碼只問一次

**Status:** done

**Blocked by:** 38（頁 2 套件內收成一顆「設定介面登入」之後，自動帶入才有地方落）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S1 全程、S5 第 3 點的完成頁、§B1、簡化方案 E-3、「文件與實作不符」的完成頁那列、改進清單 P1-5）；brief §19「精靈審計後的八項」D4、§16.3「沿用 Jellyfin 帳密」；plan §9.3；票 07、26

## 為什麼（2026-10-06 審計）

- 全套件內的流程中，密碼要打 4 次：建擁有者 2 次、qBittorrent 1 次、Prowlarr 1 次。Jellyfin 自己的啟動精靈只問一組。
- **D4 拍板**：頁 1 建擁有者時多一個勾選，預設勾起「套件內 qBittorrent 與 Prowlarr 也用這組」。
  密碼只在精靈這一個分頁的前端記憶體裡，不寫 storage、不送給 Berth 存。到頁 2、頁 4 自動帶入，照舊先向 Jellyfin 驗過再寫。重新整理之後才再問。
- 重裝時完成頁寫 Prowlarr「密碼是精靈裡設的那一組」，但這一輪精靈並沒有設，那是上一個 Berth 設的。

## 做什麼

1. 頁 1 套件內建擁有者：加勾選，預設勾。只有選了套件內的服務才提。
2. 頁 2、頁 4 套件內需要設介面登入時，記憶體裡有密碼就自動帶入並套用；沒有（重新整理、頁 1 沒勾、頁 1 是登入而不是建立）就照現在的表單問一次。
   票 26 的密碼規則照舊先擋：Jellyfin 密碼不合 qBittorrent 規則時，說明不能沿用，再問。
3. 完成頁的登入說明照實際情況寫：這一輪設的、已經存在的、或沒設。
4. 後端不變；若需要改，停下來回報。

## 驗收

- [x] vitest：勾選時頁 2、頁 4 不再出現密碼欄而是自動套用；重新整理後才再問；密碼不出現在 `localStorage` / `sessionStorage`（測試斷言）
- [x] vitest：Jellyfin 密碼不合 qBittorrent 規則時退回手動表單並說明
- [x] vitest：重裝時完成頁不寫「精靈裡設的那一組」
- [x] playwright 實跑 S1：全程只在建擁有者時輸入兩次密碼；附截圖
- [x] brief §16.3 的「沿用 Jellyfin 帳密」段落與 plan §9.3 已改
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e、真服務 e2e 綠燈

## Comments

**做了什麼**

- 頁 1：建**套件內** Jellyfin 的管理員時多一格「套件內 qBittorrent 與 Prowlarr 的介面也用這組」，預設勾；登入既有的管理員、選既有 Jellyfin 都不提（「只有選了套件內的服務才提」照審計 E-3「頁 1 套件內建擁有者時」解讀）。剖面的「不存下」照勾選說密碼會交給誰。
- 密碼留在 `SetupPage` 的 React state（不寫 storage、不送給 Berth 存）。頁 2、頁 4 那一台還沒有介面帳號時 `interfaceLogin.useCarriedLogin` 自動送一次 `reuse_owner`，欄位與主鍵換成「設定中」；請求還在飛（走開又回來）不重送。頁 2 照 qBittorrent 規則不合（`carriedUnfit`）就不送、說明、欄位一開始是自設的三格；Prowlarr 沒有規則。Jellyfin 回 `owner_password` 時丟掉那一組，頁 4 不再自動送。
- 完成頁照 `web_ui_login_by_berth` 說：精靈設的、它原本就有的、還沒設（套件內沒設時不再說「用你原本的登入」）。

**偏離票面：後端改了**（使用者 2026-10-07 拍板「回應多一個布林」）。code-review spec 軸抓到：Prowlarr 的「加入」每次以不帶登入重算登入那一條（`apply_indexers` → `_apply_password(None)` → `skipped`），S1 走完完成頁會把頁 4 剛設的登入說成「原本就有的」。纜繩分不出來，所以 `QbittorrentOut`、`IndexerSetupOut` 加 `web_ui_login_by_berth`（Berth 記著密碼雜湊）；加法性、舊欄位不動。後端測試 `test_setup_interface_login.py` 四條（加站後仍是 Berth 的、同一組再送仍是、那一台自己設過的與沒設的不是）。

**實跑 S1**（工作樹 build 的 `berth:qa-t40`；repo 外 `C:/Users/Roxy/berth-qa-t40`，compose 改名 `t40` / `t40-*`、子網 `10.240.0.0/16`、port 40xxx；用完 `down -v`、刪目錄與 image；沒碰其他環境）。截圖在 `.playwright-mcp/t40/`（gitignore，不進版控）。

| 頁 | 結果 |
| --- | --- |
| 1 | 套件內 → 建立表單，勾選預設勾著；填帳號與兩次密碼（`t40-01-owner`） |
| 2 | 選套件內 → 直接「qBittorrent WebUI 的帳號：skipper」，畫面上 0 個密碼欄（`t40-02-qbittorrent`）；`curl` 以 skipper／頁 1 那組登入 qBittorrent 回 204，錯的回 Unauthorized |
| 3 | 建立並檢查 → 3 條 Route |
| 4 | 選套件內 → 直接「Prowlarr 介面的帳號：skipper」、「替 Prowlarr 介面設登入」已完成，0 個密碼欄（`t40-03-prowlarr`）；Prowlarr `/login` 以那一組 302 到 `/`，錯的到 `loginFailed=true` |

頁面上掛的 `change` 監聽記到的密碼輸入只有頁 1 的「密碼」「再輸入一次密碼」兩次。頁 5 要貼真的 TMDB key，沒有在瀏覽器裡填，所以實跑停在頁 4；完成頁的三種說法由 vitest 覆蓋（`SetupPage.routes.test.tsx`），之後的密碼提示只在頁 2、頁 4。

**code-review 未處理的發現**

- Spec：頁 4 自動登入時 Prowlarr 會自行重啟，這段時間裡「測試」仍按得下去，會暫時連不上（可重測）。只停用了「加入」與「之後再說」——加站的結果整列寫回會蓋掉登入那一條。
- Spec：帳號與密碼都不合 qBittorrent 規則時只說帳號那一條（取消沿用之後密碼本來就重設）。
- Spec：前端 e2e `wizard` 改成 S1 流程後，「頁 2 打錯密碼被拒」與「頁 4 自設 Prowlarr 登入」只剩 vitest 守著（`SetupPage.services.test.tsx`）。
- Standards：`bodiesOf` 在 `SetupPage.test.tsx` 與新的 `SetupPage.password.test.tsx` 各一份；頁 2、頁 4 「送出那一刻」的寫法（`setSentAt` 再送）各兩處，兩頁失敗的處理本來就不同，沒有收。
- 已處理：`useEffectEvent` 取代 latest-ref（對齊 `useLibraryDraft`）、`CarriedUnfit` 只收 qBittorrent、`carried` → `carriedPassword`、`ServiceDoors` 改讀布林後拿掉 step key 表、重掛載重送、送出中停用加站。
