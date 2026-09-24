# 06i — 設定頁接手精靈跑完之後的修改；精靈只管第一次

**Status:** ready-for-agent

**Blocked by:** 06d（同一輪 `/impeccable onboard` shape 一起定設定頁的五頁；導覽的元件先定）、06e（索引站與 TMDB 的元件在這裡重用）

**讀:** plan §6（`settings` 那一列）、§7（路由、守衛、`/settings/*`）、§9.3；brief §13；`web/src/api/settings.ts` 的 docstring；`web/src/pages/ServiceSettingsPage.tsx`、`SetupPage.tsx`（`revisited`）、`SetupRoute.tsx`、`routes.tsx`（`?berth=`）；`web/src/components/berths.ts`、`TmdbNotice.tsx`、`web/src/media/IndexerNotice.tsx`、`RoutePicker.tsx`；README〈先申請一把 TMDB API key〉、〈外部服務的前提〉

## 做什麼

現在的設計（`api/settings.ts`：「位址與憑證仍然在精靈裡改，精靈跑完之後它就是設定入口」）：設定頁只做維運動作（重測連線、Jellyfin 對外網址、磁碟門檻、還原建議設定），每個服務一顆「改位址或憑證」帶 `?berth=N` 跳回精靈的那個泊位。使用者 2026-09-25 想調整索引站時覺得怪：

- **字不對**：調整索引站、換 TMDB key 都不是「改位址或憑證」，入口卻只有這一顆。
- **流程不對**：精靈是從頭靠泊一次的循序流程（泊位板、「第 5 步，共 8 步」），只想加一個站卻被丟回靠泊的中間；06d 還得為「走完之後又回來」多處理一種覆寫。
- **README 寫錯**：說 TMDB 的 key 可以在「設定 → 來源」重貼（README 兩處），但設定頁只有「服務」「媒體庫路徑」兩個分頁。

**決定**（使用者拍板，brief §19）：**設定頁接手，精靈只管第一次**。慣例：Jellyseerr 的設定頁分頁與精靈對應、兩邊用同一批表單元件；Sonarr / Radarr / Prowlarr 的設定頁按領域分頁，每頁可新增、編輯、測試、刪除；Home Assistant onboarding 之後一律在設定裡管理。

- **設定頁五頁，對應五個泊位**：Jellyfin、qBittorrent、索引站、TMDB、媒體庫路徑（`/settings/routes` 已經有）。每一頁重用精靈那一格的元件，不寫第二份：
  - Jellyfin、qBittorrent：換位址或帳密（精靈既有服務的那張表單）與測試連線；現在服務頁上的對外網址歸 Jellyfin 頁、建議設定的差異與還原歸 qBittorrent 頁。
  - 索引站：加站、移除、試搜（06e 的元件）；既有 Torznab 換網址或 key。
  - TMDB：重貼 key 並測試。
  - 磁碟空間門檻：它不屬於任何一個服務，shape 決定住在哪一頁（qBittorrent 頁或一個「一般」頁）。
- **精靈跑完之後 `/setup` 導向設定頁**；`?berth=` 與 `SetupPage` 的 `revisited` 分支刪掉（消費點歸零，連同它們的測試）。
- **所有帶人回精靈的地方改指設定頁的那一頁**：`ServiceSettingsPage` 的「改位址或憑證」、`TmdbNotice`、`IndexerNotice`、`RoutePicker`，健康頁的「到設定精靈」（`health.toSetup`）在精靈跑完之後也改成到設定。「改位址或憑證」這個字不再出現。
- **後端**：現在沒有給精靈跑完之後用的修改端點（`api/settings.ts`：「所以這裡沒有 `PUT`」），而 `setup/*` 在精靈完成後只放行 admin。shape 時決定是讓設定頁呼叫同一批 `setup/*` 命令（命令本來就冪等），還是在 `settings/*` 底下開同一批命令的端點；**services 命令只有一份**，API 層不重寫邏輯（專案架構規則）。決定寫進 plan §6。
- **README**：拿掉「設定 → 來源」，照新的設定頁寫；〈頁面〉表格的設定那一列同步。

## 驗收

- [ ] 設定頁五頁，各頁的動作與精靈那一格用同一個元件（程式碼上是同一個 import，不是複製）；zh-Hant 與 en
- [ ] 精靈跑完之後打開 `/setup` 導向設定頁；`?berth=` 與 `revisited` 已刪，沒有殘留的呼叫點
- [ ] `TmdbNotice`、`IndexerNotice`、`RoutePicker`、健康頁、服務頁的連結都到設定頁的對應頁（前端測試逐一）
- [ ] 設定頁可以：加一個索引站並試搜、移除一站、換 TMDB key、換既有 qBittorrent 的帳密（整合測試 + 前端測試）
- [ ] `user` 角色看不到也打不到這些頁與端點（`test_auth_api` 的整張表同步）
- [ ] README 沒有「設定 → 來源」，設定頁的描述與畫面一致；plan §6、§7 同步
- [ ] playwright：走完精靈之後從設定頁加一個站、試搜、換 TMDB key，1280 與 390，附結果
- [ ] lint、type、test 綠燈
