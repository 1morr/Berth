# 35 — 「套件內」卡片的主機名提示要準、會更新

**Status:** done

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

- [x] vitest（雙向）：主機名解不到時卡片寫「沒在跑」並列兩種補法；同一頁連線測試成功後加註消失
- [x] zh-Hant 與 en 並列，「沒有起」不再出現
- [x] playwright 實跑：停掉套件內 qBittorrent → 卡片加註 → 啟動 → 重新測試轉綠、加註消失；附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-06 實作紀錄**

- 文案：卡片「這套 compose 的 X 沒在跑。」（停掉的與不在 profile 裡的服務都還在 compose 檔裡，兩種都說得通）；
  `signals.bringBack` 改回兩組 `{stopped, missing}`，卡片下與測試那一條的 `not_deployed` 共用 `BringBack`：
  「容器停了：`docker compose start X`」、「X 不在 COMPOSE_PROFILES 裡：加回那一行＋`docker compose up -d`」。
- 更新：選擇與使用者按的「重新測試」做完都 invalidate `GET /setup/compose`（`SetupPage.reaskHosts`）；啟動中的輪詢不問。
- vitest：`SetupPage.services.test.tsx`「只有 Berth 時的套件內卡片」——轉綠後加註消失、仍解不到時留著（兩邊都數
  compose 問了兩次）；`SetupPage.test.tsx` 的啟動輪詢斷言只問一次。兩個方向都做過變異（拿掉 invalidate、拿掉
  `restart` 判斷）確認會紅。

**實測（工作樹 build 的 image `berth:qa-t35`，repo 外 `C:\Users\Roxy\berth-qa-t35` 照 repo 的 compose、override 換
image；用完 down、刪目錄與 image；沒碰 berth-trial、berth-audit）**

選套件內 Jellyfin、建擁有者 → 頁 2 選套件內 qBittorrent 連上 → `docker compose stop qbittorrent`、重新整理：卡片
「這套 compose 的 qBittorrent 沒在跑。」、測試那一條「找不到這個名字的主機」＋兩種補法（`.playwright-mcp/t35-01-qbit-stopped.png`）
→ `docker compose start qbittorrent`、按「重新測試」：連上了、加註消失（`t35-02-qbit-restarted-green.png`；不進版控）。
檢查：`pre-commit run --all-files` 12 項通過；vitest 82 檔 1288；pytest 3517 passed；`pnpm -C web e2e` 35 passed。

**code-review 未處理的發現**

- Standards：`35042a0` 的 subject 76 字元，超過 72（已提交，不改寫歷史）。
- Standards：純函式 `bringBack` 與元件 `BringBack` 同檔只差大小寫；`connection.fix` 底下的補法引用 `choice.bringBack.*`
  的 i18n key（兩處共用同一組，放在先出現的卡片那邊）。判斷題，留著。
- Spec：重問不分測試成功或失敗（票面只說成功後）——失敗時也重問，容器測到一半被停掉時加註才會出現；有雙向測試守著。
