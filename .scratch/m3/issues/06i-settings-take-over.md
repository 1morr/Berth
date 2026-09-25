# 06i — 設定頁接手精靈跑完之後的修改；精靈只管第一次

**Status:** done

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

- [x] 設定頁五頁，各頁的動作與精靈那一格用同一個元件（程式碼上是同一個 import，不是複製）；zh-Hant 與 en
- [x] 精靈跑完之後打開 `/setup` 導向設定頁；`?berth=` 與 `revisited` 已刪，沒有殘留的呼叫點
- [x] `TmdbNotice`、`IndexerNotice`、`RoutePicker`、健康頁、服務頁的連結都到設定頁的對應頁（前端測試逐一）
- [x] 設定頁可以：加一個索引站並試搜、移除一站、換 TMDB key、換既有 qBittorrent 的帳密（整合測試 + 前端測試）
- [x] `user` 角色看不到也打不到這些頁與端點（`test_auth_api` 的整張表同步）
- [x] README 沒有「設定 → 來源」，設定頁的描述與畫面一致；plan §6、§7 同步
- [x] playwright：走完精靈之後從設定頁加一個站、試搜、換 TMDB key，1280 與 390，附結果
- [x] lint、type、test 綠燈

## Comments

**Shape（2026-09-25，`.scratch/m3/settings-shape.md`，使用者確認）**：後端沿用 `setup/*`（不開 `settings/*` 的同一批端點，plan §6 已寫）；單欄區塊、重用精靈的內層元件（精靈的剖面、泊位板、「之後再說」、上一個 / 下一個不帶過來）；磁碟門檻住 qBittorrent 頁。分頁照泊位板的順序；套件內的服務沒有位址表單；套件內 Jellyfin 的媒體庫清單與既有 Jellyfin 的「加入 Berth 路徑」不搬過來。

**重用的是哪幾個元件**：`MooringLine`（連線表單，經 `settings/ServiceConnection.tsx`）、`JellyfinSignIn`（從 `JellyfinExisting` 抽出來）、`IndexerActions`（從 `IndexerStep` 抽出來，包著 `DefaultIndexers` / `ExistingIndexer` / `TrialSearch`）、`TmdbKey`。`onSkip` 變選填，設定頁不給。

**驗收的證據**：
- 前端：`JellyfinSettingsPage` / `QbittorrentSettingsPage` / `IndexerSettingsPage` / `TmdbSettingsPage` 四個測試檔；連結的 `href` 在 `DiscoverPage`、`MediaDetailPage`（TMDB 與 RoutePicker）、`SearchPanel`（IndexerNotice）、`HealthPage`（紅燈與漂移）逐一斷言；`router.test` 的 `/setup` 導向與五個設定分頁對 `user` 的導向。
- 後端：`tests/integration/test_settings_take_over.py`（精靈跑完之後 admin 加站、試搜、移除、換 TMDB key、換既有 qBittorrent 帳密，移除最後一站不會把精靈拉回未完成；`user` 對五支都是 403）。沒有新端點，`test_auth_api` 的表不必改（`setup/*` 本來就在表上，對 `user` 一律 403）。
- playwright（`--scenario healthy`，`.local/screens/m3-06i/`）：登入時 `redirect=/setup` 落在 `/settings/jellyfin`；1280 勾 dmhy → 「加入這 2 個站」→ 試搜 Nyaa.si 7 筆、dmhy 14 筆，健康卡跟著變「索引站 2」；TMDB 換 key 綠燈。390 重新整理後勾選從現有的兩站起、再加 ACG.RIP 並以 `Frieren` 試搜三站都有筆數、換 TMDB key 綠燈；五個分頁 `scrollWidth - clientWidth` 都是 0。
- 變異：`DefaultIndexers` 的勾選起點改回一律全勾，索引站設定頁三條轉紅；`verify_tmdb` 拿掉「已驗過」的判斷，新的整合測試轉紅。

**票面沒寫、這一輪加的**：
- `DefaultIndexers` 的勾選起點改成 Prowlarr 現在有的那幾站（一站都沒有時照舊全勾）：「加入」只加不刪，起點全勾的話移除的站會在下一次加站時被默默加回來。精靈也受影響（回頭看時同樣是對的），精靈那邊沒有另寫測試，由設定頁的測試守著同一個元件。
- **已經有一把驗過的 TMDB key 時，新的測不過就不換**（code review Spec 提出，使用者拍板）：`verify_tmdb` 回這一次的紅燈但不存，`verified` 仍是 true；設定頁說「沒有換掉」。`test_completing_needs_a_tmdb_credential_first` 原本靠「回頭貼空白 key」走到未驗證，改成直接清掉狀態。
- 健康卡的鍵叫「重新檢查」（原本「測試連線」）：同一頁的連線表單送出也叫「測試連線」，兩顆同名的鍵螢幕閱讀器分不出來。
- 「去補上」的連結字由泊位導出（「前往設定：TMDB」），`tmdb.problem.toSetup`、`search.problem.toSetup`、`media.route.toSetup`、`health.toSetup`、`health.toSettings` 收成 `settings.go`；一般使用者在健康頁紅燈看到「請管理員來看」（原本給一條進不去的連結）。

**code review 未處理的發現**：
- `routes.tsx` 仍逐條寫五個設定路徑（TanStack Router 的型別要字面值）；`components/berths.ts` 的 `settings` 欄與它是兩份，改一邊要記得另一邊（`router.test` 的五條導向與分頁測試的 href 會抓到不一致）。
- `IndexerActions` 與 `TmdbKey` 自帶 `mt-6`，設定頁用 `[&>:first-child]:mt-0` 壓掉；外距交給呼叫端要動精靈那幾個區塊的間距，這一輪不做。
- 「讀取中 / 讀不到 / 資料」的三態在 `HealthSection`、`ServiceConnection`、索引站頁、TMDB 頁各寫一份；四處的讀不到說法各不相同，暫不收。
- `settings.jellyfin.*`（對外網址）與 `settings.jellyfinPage.*`（整頁）兩組鍵名不易分辨；改名會動到既有的鍵，留著。
- 「加入這 N 個站」的 N 含已經在的站（它們會重驗一次、標「已經是這樣」），在設定頁上字面偏大；要改得動按鈕語意，留給 06h 的精靈收尾一起看。
