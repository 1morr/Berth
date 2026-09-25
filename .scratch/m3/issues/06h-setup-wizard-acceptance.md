# 06h — 精靈驗收：冷啟動閘門、兩條完整路徑、impeccable 收尾

**Status:** done

**Blocked by:** 06b、06c、06d、06e、06f、06g、06i（全部做完才驗）

**讀:** plan §9.1–§9.5、§10（e2e）；`.scratch/m0/wizard-shape.md`；06b–06g 六張票的驗收與 Comments；`tests/e2e/conftest.py`（`configured`）、`.github/workflows/e2e.yml`、`web/e2e/wizard.spec.ts`、`scripts/fake_setup_server.py`（`starting` 等情境）；README〈快速開始〉的泊位表與〈前端 e2e〉

## 做什麼

06b–06g 與 06i 由七個 session 各改精靈（與接手它的設定頁）的一塊：port 進 `.env`、第 1 步剖面與帳密、導覽（停在結果上、上一個 / 下一個泊位、泊位板可點、Route 自動跑）、泊位板 4 格變 5 格與索引站試搜、自訂媒體庫、偵測時服務還在啟動。每張票只驗自己那一塊，**這一張驗整條路還走得通**，並把使用者 2026-09-24/25 試跑時靠手動才發現的事變成常駐的閘門（全域規則：手動驗證過但沒編碼進去的等於沒驗證）。

**為什麼現有的測試沒擋下 06g**（使用者 2026-09-25 問「要不要寫一個精靈的驗收票」時查到）：

- `tests/e2e` 用 `docker compose up --detach --build --wait`（`.github/workflows/e2e.yml`），**四個容器都健康了才開始精靈**，永遠碰不到 Jellyfin 還在啟動的那幾秒；`conftest.configured` 的 `detected` 在逾時時自己按 `restart`，又補掉一層。
- `web/e2e/wizard.spec.ts` 只有一條，對替身 `bundled` 走套件內的路；替身的 `starting` 只演 qBittorrent 連不上與 Prowlarr 讀不到 key，沒有 Jellyfin 的 503 與半啟動；既有服務（`mixed`）沒有端到端的一條。

要做的：

1. **冷啟動 e2e**：真的 compose 起來之後，**不等外部服務健康就開始精靈**（`--wait` 只等 `berth`，或 workflow 拆成先起 berth），`configured` 拿掉逾時就 `restart` 的補救，照常輪詢到判定完成。四個容器同時啟動、全程不按重新探測就走完。這是 06g 的常駐閘門。
2. **替身補情境**：`starting` 加上 Jellyfin 回 503 「still loading」與回應不像 Jellyfin 的半啟動（06g 量到的兩種），本機 playwright 就重現得出來。
3. **playwright 兩條完整路徑**（1280 與 390，zh-Hant）：
   - 套件內：5 格泊位、每一格做完停在結果上、按「上一個泊位」回去再往前、從泊位板點回走過的泊位、自訂一個媒體庫（改名、加一列、刪一列）、試搜索引站並移除一站、Route 自動跑、完成後以同一組帳密登入。
   - 既有服務（`mixed`）：Jellyfin 勾選媒體庫與選寫入目標、既有 qBittorrent 的帳密、既有 Prowlarr。
   - 另外一條冷啟動（替身 `starting`）：不按重新探測就判定完成。
   - 走完之後的修改（06i）：`/setup` 導向設定頁；從設定頁加一個索引站並試搜、換 TMDB key。
4. **`/impeccable critique`、`audit`、`polish` 各一輪只對精靈**：P0 / P1 當場修，其餘記進這張票的 Comments（專案 CLAUDE.md：UI 收尾前）。
5. **文件一致**：README 的泊位表（現在是四個泊位）、plan §9.3 的步驟與前端覆寫規則、`.scratch/m0/wizard-shape.md`、CONTEXT.md 的名詞、`.env.example`，都對得上做出來的畫面。
6. **使用者實走一次**：試跑環境（`C:\Users\Roxy\berth-trial\`，非預設 port）改用 06b 之後的 compose 與 `.env`，重置後從第 1 步走完；**不靠 `WebUI\HostHeaderValidation=false`**——試跑目錄的 preseed 副本裡那一行要一起拿掉（06b 的 Comments）。走完之後媒體庫的「在 Jellyfin 開啟」開到對外 port。

## 驗收

- [x] 冷啟動 e2e 在 CI 綠燈：精靈在外部服務還沒健康時就開始，`configured` 不再按 `restart`（貼 CI run 連結與輸出）；把 06g 的修正拿掉時這一條會紅（在 PR 描述或票的 Comments 記下實跑結果）
- [x] 替身 `starting` 有 Jellyfin 的 503 與半啟動，README 的情境表同步
- [x] playwright：套件內、既有、冷啟動、走完之後從設定頁修改四條，1280 與 390 截圖附在票上
- [x] `/impeccable critique`、`audit`、`polish` 各一輪，分數與處理結果記在票上
- [x] README、plan §9.3、`wizard-shape.md`、CONTEXT.md、`.env.example` 與畫面一致
- [x] 使用者在試跑環境重置後走完一次，沒有用到 `HostHeaderValidation=false`，也沒有按重新探測；結果記在 Comments
- [x] lint、type、test、e2e 全綠（貼指令輸出）

## Comments

**冷啟動閘門（後端 docker e2e）**：`.github/workflows/e2e.yml` 先 `build` 與拉 image，再 `docker compose up --detach`（不加 `--wait`）；`tests/e2e/compose.yml` 的 `torrents` 拿掉 `depends_on: berth: service_healthy`（它會讓 `up -d` 卡到 Berth 第一次健康檢查的 30 秒，那時外部服務早就起來了），改由 `payload.py` 自己等 Berth 回應再寫 `/data`；`submitted` 等 `torrents` 健康才送單。`conftest.configured` 拿掉逾時就 `restart` 的補救，每 2 秒輪詢、印出時間線；**第一輪就全部判定完成算失敗**（那一輪沒碰到啟動中的那幾秒，閘門等於沒守）。

- 綠燈：<https://github.com/1morr/Berth/actions/runs/36095639574>（分支 `m3-06h-cold-start`，15 passed in 898 s）。時間線（從建完管理員起算）：`+1.8s jellyfin=pending/protocol_mismatch` → `+3.8s jellyfin=pending/starting` → `+5.9s jellyfin=bundled/setup_pending`（qBittorrent、Prowlarr 第一輪就是套件內）。06g 量到的兩種啟動中樣子都出現了，沒有按重新探測。
- 拿掉 06g 的修正（`git show 63b87a8 -- berth/services/setup.py | git apply -R`，分支 `m3-06h-without-06g`）時紅：<https://github.com/1morr/Berth/actions/runs/36095657612>。第一輪 `jellyfin=existing/protocol_mismatch`（06g 的缺陷 2），下一輪 `POST /setup/detect: 500`（缺陷 1，Jellyfin 的 503 冒成 500）。

**替身 `starting`**：改成照探測次數演 06g 量到的時間線（`StartingJellyfin` / `StartingQbittorrent` / `StartingProwlarr`）：Jellyfin 先丟 `ProtocolMismatchError`（回的東西不像 Jellyfin）、再丟兩次 `ServiceBusyError`（503 still loading），第 4 次探測起是套件內；qBittorrent 第一次連不上；Prowlarr 連不上五次。原本的「Prowlarr 讀不到 API key」搬到新情境 `key-missing`（它不是啟動中的暫時狀態，冷啟動時等不好）。`mixed` 的 NAS 媒體庫舊路徑改成暫存目錄底下真的存在的 `nas/movies`、`nas/anime`（原本 `/volume1/...` 在這台機器上 `stat()` 不到，第 5 步永遠紅，既有服務那條路走不完）。README 的情境表同步。

**playwright 四條 × 兩種寬度**（`web/playwright.config.ts` 的 `NARROW`，每條一台替身）：`wizard`（bundled：改名 Movies → 電影並補資料夾、加「紀錄片」、刪 Anime、每一格停在結果上、泊位板點回 BTH 1、「回到目前這一步」、上一個泊位再往前、試搜並移除 YTS、Route 自動跑出 3 條含 `berth-紀錄片`、完成後同一組帳密登入）、`existing`（mixed：qBittorrent 帳密、既有 Jellyfin 登入並就地確認加 Berth 路徑、第 5 步勾「電影」選 Berth 路徑、貼 Prowlarr key 並試搜、以 `owner` 登入）、`cold-start`（starting：先看到「探測中」與「還在啟動」，不送任何 `restart: true` 就三個套件內）、`settings`（healthy：`/setup` → `/settings/*`、加 YTS 並試搜、換 TMDB key）。`pnpm -C web e2e` 11 條：一次全開時 `cold-start-390` 撞到 Chromium 180 秒啟動逾時（本機預設 worker 數讓十一條同時開瀏覽器），`playwright.config.ts` 把本機 worker 限成 4（CI 照預設）之後 11 passed（52.1 s）。每一格的整頁截圖在 `.local/screens/m3-06h/e2e/<那一條>/`（1280 與 390 共 38 張，不進版控；`web/test-results/` 每次都會重產）。

**實走時抓到、當場修的（紅燈先行）**：
- 完成頁寫「四個泊位都繫上了」→「五個泊位都走過了」；既有 Jellyfin 也說「用剛才建立的 Jellyfin 管理員帳號登入」→ 既有時說「你那台 Jellyfin 的帳號」（`CompleteStep` 的 `bundledJellyfin`）。
- 前置列「N 個服務已判定」把探測中也算進去（冷啟動時寫 3 個、清單上還有兩個在等）→ 只算套件內與既有。
- 第 2 步寫死 `qbittorrent:8080`（06b 的遺留）→ `GET /setup/status` 多 `probe_targets`（`services.clients.bundled_targets`，與 `build_setup_probes` 同一個來源），前端 `probeEndpoint` 照它寫；連線表單的範例位址三個服務都寫 `:8096` → 各自的 port。
- 設定頁的 TMDB 說明還寫「精靈的進度已經存下來了」→ `tmdbStep.where` / `whereWizard` 兩個 key。

**impeccable**（`.impeccable/critique/2026-09-25T05-30-59Z__web-src-pages-setuppage-tsx.md`，polish 之後已 close）：
- critique（雙代理）**24/40**，P0 0、P1 3：既有服務的安全感、焦點管理、窄版第一屏只有剖面。偵測器 CLI 0 條；瀏覽器注入的 `skipped-heading`、第 2 步剖面溢出屬實，`em-dash`、`dark-glow` 誤報。
- audit **13/20**（A11y 2、Performance 3、Responsive 2、Theming 3、Integrity 3），P1 4：焦點掉回 body、窄版固定列蓋住焦點（390 時 qBittorrent 位址 44/44px 被蓋）、live region 與內容同一次掛上、淺色主題未塗漆的泊位格 3.73:1。
- polish（使用者拍板「DOM 改成工作面在前」「P1 全修，P2 記下」）：`web/src/setup/StepFrame.tsx`——DOM 工作面在前、桌機 grid 放回左欄（390 寬第 2 步標題 790 → 508 px、泊位 1 1550 → 508 px，標題順序 h2 → h3），套件內 Jellyfin 的媒體庫清單從剖面搬進工作面（它是輸入，Tab 順序才對）；換步時焦點給新一步的 h2，按下的鍵被換掉時接回「前往下一個泊位 / 前往泊位 1」，只在「最後有焦點的元素被拿掉」時動手（與 `useFocusAfterRemoval` 同一條規則，排在它之後）；TMDB 結果與偵測清單的 live region 常駐；窄版 `scroll-padding-bottom: 6rem`（實測 Tab 走過 390 寬第 2 步每一欄，0 個被蓋）；泊位格只有塗漆的才 `opacity-80`（淺色 3.73 → 5.71:1）；泊位 3「加入 Berth 路徑」改成與泊位 1 同一顆就地確認；既有媒體庫有 Berth 路徑時預選它（`routes._default_target`；只有一條時照 brief §4.3 預選那一條）；第 5 步 lede 改成「Berth 只往你選的那一條寫……不想讓它寫進你既有的資料夾，先加一條 Berth 路徑再選它」；剖面的端點 `wrap-anywhere`。

**code-review（`/code-review 15a2cd4`）**：
- Standards 硬性一條：CHANGELOG 沒寫 → 補（Added / Changed / Fixed 各一條）。判斷題裡照改的：`StepFrame` 的焦點接回原本靠「StepFrame 自己重繪時檢查」，換鍵只發生在子步驟自己的 state 裡時接不回來——`StepFrame.test.tsx` 先重現（兩個分支要不同 `key`，同一位置同一種元素 React 會重用節點、焦點根本沒掉），改成與 `useFocusAfterRemoval` 同一種 MutationObserver 做法；`where` / `whereWizard` 逐字重複 → `whereWizard` 用 `{{where}}` 插值，`resumable` 改名 `inWizard`。沒改、記在這裡的：`api/setup.py` 為了 `probe_targets` 六個 handler 各多一個 `ConfigDep`（放進 `SetupStatus` 要讓 `read_status` 等五個 service 函式都吃 config，更散）；替身的三個 `Starting*` 同形（各覆寫的是不同的探測方法，抽 helper 省不了幾行）；`bundledJellyfin` 在頁面層算成布林往下傳；`BerthBoard` 的 `filled === false` 判兩次。
- Spec：README 與 plan §10 還寫「四條流程」→ 改成七條；`_default_target` 預選 Berth 路徑補進 brief §4.3 與 plan §9.3 第 5 步、`probe_targets` 補進 plan §9.3 第 2 步；第 6 項待使用者實走（預期中）。它提的兩個弱點照記：「每一格停在結果上」只由「前往下一個泊位」出現間接驗證（06d 的前端測試直接驗）；冷啟動那條的 `restart` 監聽掛在第一次探測之後（第一次是「開始探測」本身，之後任何一次按「重新探測」都會被記到）。

**P2 與小觀察（這一輪不修，使用者拍板「P2 記下」）**：
- 既有 Jellyfin 帳密錯只顯示「失敗 POST /Users/AuthenticateByName: 401」，該對成「帳號或密碼不對」（產品原則 4）。
- 選填的索引站連不上塗成阻擋紅、每一站一個 `role=alert`（4 條同時念）；加完之後主要鍵仍是「加入這 N 個站」。
- 同名控制項：索引站「移除」×5、「複製」×4；既有服務第 2 步「位址」「測試連線」各 ×3、「顯示」×2 且沒有 `aria-pressed`（`BundledLibraries` 已經用 `removeNamed` 帶名字）。
- 標題跳號：纜繩列的手動步驟用 h5（`MooringLine`、`QbittorrentStep`、`StepLine`），跳過 h4。
- 淺色主題錯誤狀態的輸入框邊框 `blocked` 對 `hull` 2.58:1（WCAG 1.4.11），比正常邊框還淡。
- 精靈沒有路由切分（入口 800 KB / gzip 229 KB，M3 票 06 量過、決定不做）。
- 觸控目標：ZH/EN 44×24、「顯示」39×24、Ghost 按鈕 35 px 高——過 2.5.8 的 24 px，沒到 44。
- 移除媒體庫列之後焦點掉回 body（`BundledLibraries` 沒用 `useFocusAfterRemoval`；`StepFrame` 現在會接回 h2，不是下一列）。
- `SetupPage.tsx` 的輪詢 effect 依賴每次 render 都是新物件的 `detect`，重繪會重設 3 秒計時器。
- 泊位 1 套件內的剖面「將會做什麼」與右欄序列同 7 列（plan §11.3 D 組已經記過，可再延）；泊位板一格寫來源（套件內 / 既有）不寫狀態。
- 「套用這 5 個鍵」下面列 6 列；qBittorrent 套用後「建議值」欄變「已經是這樣」看不到原值；Route 建好之後剖面「這一輪要建的 Route 0」；Prowlarr key 的位置兩處寫法不同（設定 → 一般 → 安全性 / 設定 → 一般）；第 2 步的「上一個泊位」回到的是管理員；既有 Jellyfin 做完「重新登入」仍是黃色主要鍵；qBittorrent 分類 `berth-電影` 中文進了機器 token；冷啟動第一秒寫「連得上，但回的東西不是這個服務」會嚇人；管理員欄位留空時錯誤念兩次；設定頁 Jellyfin 健康卡的「3 libraries」是英文（後端 detail 字串）。
- 術語：「開始靠泊」「冪等」「complete 根目錄」「dev= / inode=」對第一次架設的人是黑話。

**最後的程式碼再跑一次（分支 `m3-06h-cold-start`）**：
- 後端 docker e2e 綠：<https://github.com/1morr/Berth/actions/runs/36101293785>，15 passed in 891 s，時間線 `+1.8s jellyfin=pending/protocol_mismatch` → `+3.8s pending/starting` → `+5.8s bundled/setup_pending`。
- CI 綠：<https://github.com/1morr/Berth/actions/runs/36101576757>（backend、web、web-e2e、api-types、image、hygiene 全 success；前一輪 hygiene 紅在 critique 存檔的行尾空白，已修）。
- 本機：`ruff check` / `ruff format --check` / `mypy`（284 files）/ `lint-imports`（6 kept）綠，`pytest` 2462 passed；`tsc -b` / `eslint` / `prettier --check` 綠，`pnpm test` 52 files 831 passed，`pnpm e2e` 11 passed（52.1 s）。

**第 6 條的準備**：`C:\Users\Roxy\berth-trial` 先整份備份到 `C:\Users\Roxy\berth-trial-backup-20260925`（舊 compose、config、data、preseed），再清掉 `config/`、`data/`，換成 repo 的 `deploy/docker-compose.yml`、`deploy/preseed/`（沒有 `WebUI\HostHeaderValidation=false`）、由 `deploy/.env.example` 抄的 `.env`（五個 port 換成 18383 / 18096 / 18080 / 16881 / 19696），以及只換 image 的 `docker-compose.override.yml`（`berth:trial-06h`，這一票的程式碼 build）。三個外部 image 已經拉好，容器還沒起：由使用者 `docker compose up -d` 冷啟動、馬上開 <http://localhost:18383> 從第 1 步走完。

**第 6 條實走（2026-09-25 14:33，由 agent 代走，使用者授權）**：試跑環境照上一段準備好之後，`cd C:\Users\Roxy\berth-trial` 同一刻起 `docker compose up -d`（6.6 s 回來）與一支 playwright 腳本（真 Chromium、1280 × 900、`zh-TW`；腳本在 session 的 scratchpad，不進 repo）。腳本等到 Berth 回應才開瀏覽器，之後照畫面按：第 1 步建管理員 **`skipper` / `Harbour-06h-trial`**（也是精靈第 3 步替 Jellyfin 建的管理員），第 2 步只按「開始探測」，之後預設清單靠泊、套用 qBittorrent、Route 自動建、加入九個預設站並試搜、貼 repo `.env` 的 TMDB key、完成、以同一組帳密登入。每一次 `POST /setup/detect` 都記下判定與有沒有帶 `restart`。時間從 `up -d` 起算：

| 時間 | 事件 |
| --- | --- |
| 8.4 s | Berth `/api/health` 200，開瀏覽器 |
| 9.5 s | 第 1 步送出；按「開始探測」 |
| 12.1 s | detect #1：Jellyfin `pending/starting`、qBittorrent `bundled/anonymous_ok`、Prowlarr `pending/unreachable` |
| 15.1 s | detect #2：Jellyfin `pending/protocol_mismatch` |
| 18.2 s | detect #3：Jellyfin `pending/starting` |
| 21.2 s | detect #4：Jellyfin `bundled/setup_pending`（Prowlarr 仍 `unreachable`，#5、#6 同） |
| 30.5 s | detect #7：Prowlarr `bundled/no_indexers`，三個都判定完成 |
| 30.9 s | 「前往泊位 1」出現；**7 次探測，`restart: true` 0 次**，沒有按重新探測 |
| 38.0 s | 泊位 1 Jellyfin 靠泊完成（3 個媒體庫、API key） |
| 38.4 s | 泊位 2 qBittorrent 套用完成 |
| 39.3 s | 泊位 3 三條 Route 自動建好、五條纜繩全綠 |
| 60.0 s | 泊位 4 加入預設站有結論（板上「Prowlarr · 6 個索引站」），63.4 s 試搜有結果 |
| 64.5 s | 泊位 5 TMDB 驗過 |
| 64.6 s | 完成設定 → 登入頁；66.4 s 以 `skipper` 登入，落在 `/library` |
| 67.5 s | playwright 開 `http://localhost:18080/`：HTTP 200、title「qBittorrent WebUI」 |

- 06g 量到的兩種啟動中樣子（503 `starting` 與 `protocol_mismatch`）在真環境又各出現一次，畫面都是「探測中」；第 2 步的剖面與纜繩寫的是 `qbittorrent:18080/api/v2/app/version`（`probe_targets`，06b 的遺留在真環境也修掉了）。
- **qBittorrent 從宿主開得到，不靠 `HostHeaderValidation=false`**：curl `http://localhost:18080/` 200，未登入打 `/api/v2/app/version` 是 403（免密白名單只有 Berth 的固定 IP，`WebUI\AuthSubnetWhitelist=172.28.0.2/32`）；`config/qbittorrent` 與 `preseed/` 裡都搜不到 `HostHeaderValidation`。
- **「在 Jellyfin 開啟」指向 18096**：新建的媒體庫是空的，所以放一支測試影片（`tests/fixtures/e2e/seed.mkv` → `data/library/movies/Big Buck Bunny (2008)/`），以 `skipper` 登入 Jellyfin 的 API 叫 `POST /Library/Refresh`，Jellyfin 掃到之後 Berth 的 Movies 媒體庫頁那一格的連結是 `http://localhost:18096/web/#/details?id=56f1a2a0…`；點下去開新分頁到 `http://localhost:18096/web/#/login?…&url=/details?id=…`（那個瀏覽器還沒登入過 Jellyfin）。
- 截圖 `.local/screens/m3-06h/trial/`（`1-admin` … `9-signed-in`、`10-qbittorrent`、`11-library-deeplink`、`12-jellyfin-opened`，不進版控）。試跑環境留著在跑（`berth:trial-06h`），舊的那一份在 `C:\Users\Roxy\berth-trial-backup-20260925`。
