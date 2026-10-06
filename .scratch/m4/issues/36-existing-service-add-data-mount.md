# 36 — 既有服務的接入說明：只多掛一條 `/data`，並停掉套件內那一台

**Status:** done

**Blocked by:** 34（實跑要用 34 的隔離做法，不能動 berth-trial / berth-audit）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S2 第一點、S3「qBittorrent 沒掛 `/data`」那列、§C1、§C2 全部、「文件與實作不符」的 README:33、`choice.existing.*`、`routes.fix.existing.qbittorrentMount`、plan §9.5 四列；改進清單 P1-6、P1-7）；brief §16.4、§20.14；plan §9.5；README〈選「既有」的條件〉

## 為什麼（2026-10-06 審計）

- 卡片寫「同一個容器路徑（例如都是 /data）」。「例如」暗示可以是別的路徑，實際上**只能是 `/data`**：Berth 的三層路徑是固定的。
- 掛錯時的補法要求使用者「下載目錄也移到它底下…不要分開掛 /downloads」，比 Berth 需要的多。照做的話，使用者的舊 torrent 可能找不到檔案。
  Berth 只在自己的目錄讀寫，最小改法是**多加一條 `/data` 掛載、原本的全部留著**（報告 §C2 的 compose 與 `docker run` 範例）。
- 實測：README 的混用指示「把它從 `COMPOSE_PROFILES` 拿掉再 `docker compose up -d`」不會停掉已經在跑的套件內容器。Compose 對不在啟用 profile 裡的服務，不會動既有容器。
- plan §9.5 的 NAS 範例（三個容器都掛 `/volume1/media:/volume1/media`、在 qBittorrent 頁設根目錄）與實作不符。

## 做什麼

1. 精靈「既有」卡片與 README 的條件寫明：容器路徑必須是 `/data`，`DATA_ROOT` 要是能硬鏈接的檔案系統，既有 Jellyfin 要先有對應類型的媒體庫。
2. 掛載補法（頁 3 與設定頁）改成「在原本的 compose 或 `docker run` 上多加一條 `${DATA_ROOT}:/data`」，原本的掛載不用動。附報告 §C2 那種片段。
3. README 混用指示補上停掉套件內那一台的指令（`docker compose stop <服務>`，或 `up -d --remove-orphans` 之類，以實跑結果為準）。
   `.env.example` 的 `COMPOSE_PROFILES` 註解與精靈「選了既有」那一段同步改。
4. plan §9.5 的 NAS 範例照 §C2 改寫。

## 驗收

- [x] vitest：卡片不再出現「例如」；補法片段只有加 `/data` 那一條，沒有「移到它底下」（zh-Hant 與 en 並列）
- [x] 實跑（隔離環境，指令與結果貼在 Comments）：既有 qBittorrent 保留 `/downloads`、既有 Jellyfin 保留 `/tv`，各只多掛一條 `/data`，頁 3 6/6
- [x] 實跑：照 README 的混用指示做完，`docker ps` 裡套件內那一台確實停掉
- [x] README、`.env.example`、plan §9.5 已改；brief §20.14 補上 Compose 不停既有容器的實測（附來源或腳本）
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-07 實作紀錄**

- 卡片：`choice.existing.sameHost` 改說只能是 `/data`、原本的掛載不動、`DATA_ROOT` 要建得了硬鏈接；新 key
  `choice.existing.library`（只在 Jellyfin 卡片）說要先有對應類型的媒體庫。「選了既有」那一段在 `COMPOSE_PROFILES`
  那一行之後多一行 `docker compose stop <服務>`。
- 補法：既有那一台的三個掛載補法（`download_visible`、`library_path`、`probe_visible`）與頁 3 加不上 Berth 路徑那一句，
  改成「在原本那一份 compose（或 docker run 指令）多加一條，原本的掛載不用動」；片段是 compose 一段加
  `routeChecks.runMount` 的 `-v ${DATA_ROOT}:/data`。`existing.qbittorrent`、`existing.split` 拿掉「例如」與「改成同一個父目錄」。
- 「設定頁」解讀成 Route 設定頁：它讀 `GET /setup/status`，給既有那一台的版本（健康頁照舊給套件內那一份）。
- vitest：`routeChecks.test.ts`（既有三條 compose + docker run、套件內與 berth 只有 compose）、`i18n/existingMount.test.ts`
  （zh-Hant 與 en 並列；三個樣式在檔內雙向：原本的寫法會紅、無關的說法不紅；改前的文案跑過是 9 紅）、
  `SetupPage.*`、`RouteSettingsPage.test.tsx`（既有／讀不到來源兩邊）。

**實測 1：Compose 停不停（`python scripts/experiments/compose_profile_removal.py --berth-image berth:e2e`；
Docker 29.6.2、Compose v5.3.1；隔離 project `berth-exp-profiles`，跑完全清掉）**

| 步驟 | 結果 |
| --- | --- |
| 三個 profile `up -d` | 四個都 running |
| `COMPOSE_PROFILES=prowlarr` 再 `up -d` | exit 0，jellyfin、qbittorrent **仍 running** |
| `up -d --remove-orphans` | 同上，仍 running |
| `docker compose stop jellyfin qbittorrent` | exit 0，兩台 exited |
| 再 `up -d` | 兩台留在 exited |
| 不帶 profile 的 `down` | 只收 berth、prowlarr 與網路，exited 的兩台留著 |

**實測 2：精靈（工作樹 build 的 `berth:qa-t36`；repo 外 `C:/Users/Roxy/berth-qa-t36`，compose 從 `deploy/` 改名成
`t36` / `t36-*`、子網 `10.233.0.0/16`、port 3xxxx；「使用者原本的」`t36-mine-jellyfin`（12.1，已初始化，媒體庫 Shows 在
`/tv`）與 `t36-mine-qbittorrent`（5.2.3，全域 save_path `/downloads`）；用完 `down -v`、刪目錄與 image；沒碰 berth-trial、
berth-audit）**

- 頁 1 選既有：卡片條件、媒體庫那一條、`COMPOSE_PROFILES=qbittorrent,prowlarr` 與 `docker compose stop jellyfin` 都在
  （`.playwright-mcp/t36-01-p1-existing-card.png`，不進版控）。填 `http://host.docker.internal:37096`、以既有管理員登入。
- 頁 2 選既有 qBittorrent（此時只掛 `/downloads`）：連上、按「確認，不改任何設定」。
- 照 README 混用指示：`.env` 改 `COMPOSE_PROFILES=prowlarr`，`docker compose up -d` 之後 `docker ps` 仍有
  `t36-berth-jellyfin`、`t36-berth-qbittorrent`（Up）；`docker compose stop jellyfin qbittorrent` 之後 `docker ps` 只剩
  `t36-berth`、`t36-berth-prowlarr`，`ps -a` 兩台 `Exited (0)`；再 `up -d` 仍 Exited。
- 頁 3 勾 Shows、寫入目標 `/data/library/shows`、建立並檢查：2 / 6，紅在「qBittorrent 讀得到 Berth 寫的檔案」，補法是新文案、
  compose 片段與 `-v ${DATA_ROOT}:/data`（`t36-02-p3-qbit-no-data.png`）。
- 照補法只在 mine 的 qBittorrent 多加 `../data:/data`、`docker compose up -d`（Recreate）：掛載變成 `/downloads`、`/data`、
  `/config`；Jellyfin 是 `/config`、`/tv`、`/data`。按「重新檢查 1 條 Route」：**6 / 6 通過**（`t36-03-p3-six-of-six.png`）。
- 測後：Jellyfin 的 Shows 是 `['/data/library/shows', '/tv']`；qBittorrent 全域 `save_path=/downloads`、autoTMM false 沒變，
  多一個分類 `berth-shows`（`/data/torrent/complete/shows`、未完成 `/data/torrent/incomplete/shows`），探測 torrent 已清（0 個）。

**檢查**：`uv run pre-commit run --all-files` 全過（新檔另以 `--files` 跑過）；pytest 3517 passed（審查後再跑 unit 1399）；
vitest 83 檔 1302；`pnpm -C web e2e` 35 passed。

**code-review 未處理的發現**

- Standards：Route 設定頁的 `useExisting` 與 `SetupPage` 各組一份 `ExistingServices`，root 一個用 `SHARED_ROOT`、一個用
  `commonRoot(...)`，等價只靠 `PathSettings` 固定。留著：統一要動精靈的 `routes` 契約，不在本票。
- Standards：實驗腳本的 `docker()`、`substitute()`、`leftovers()` 與 `compose_collisions.py` 幾乎相同。實驗腳本照慣例各自獨立，留著。
- Standards：NAS compose 範例在 README 與 plan §9.5 各一份（票面兩處都要求）。
- Standards：`routes.fix.existing.split` 的 key 名留著（講的仍是「分開掛」的處境）；advice 兩句寫死 `/data`，其他補法用
  `{{root}}`（advice 不帶插值）。
- Spec：健康頁仍給套件內那一份補法（票面只點名頁 3 與設定頁）。
