# 57 — README 改成英文為主、中文另一份；安裝頁只留必讀

**Status:** done

**Blocked by:** 55（Unraid 一節照實跑結果寫）、56（安裝步驟的第一步是下載 zip）

**讀:** `docs/research/usability-audit-2026-10-07.md` §2 E7、§6.3、§7、§8 P1-8、P2-13、P2-16、§9 第 5 點；`notes/r2-docs-and-research.md` §1（全節）；票 55 的研究檔；brief §19「第四輪可用性審計的八項」E7；專案 `CLAUDE.md`〈指令〉

## 為什麼

- 使用者要公開發佈、寫進 CV：r/selfhosted、Unraid 論壇與看 CV 的人讀英文。
- 使用者拍板（2026-10-08）：**README 改成英文為主、中文另一份**。
- 審計 E7：安裝頁現在的必讀約 2,000 字、35 個名詞，四個對照產品都是「拿檔案 → 改 2–4 個值 → `up -d` → 連到下一頁」。

## 做什麼

1. **`README.md` 改寫成英文**，給第一次來的自架使用者，依序是：
   - 一句話介紹＋截圖 3–4 張：精靈、作品頁搜尋、媒體庫、健康頁。可從審計截圖挑，或重拍英文介面。
   - 前置需求：Docker Engine 或 Docker Desktop，加 Compose v2。
   - 先申請 TMDB key（約 5 分鐘）。
   - 下載 zip（56）→ 改 `.env` 的幾個值 → `docker compose up -d` → 開精靈。
     - 要改的值：`DATA_ROOT`、PUID / PGID、`TZ`；已經在跑 Jellyfin / qBittorrent / Prowlarr 的人先改 `COMPOSE_PROFILES` 或 port。
   - 精靈每頁一句話。
   - 一節「**Status & known limitations**」，照實寫：
     - 公開 beta；只支援 Jellyfin 12+ 與 Prowlarr；沒有通知。
     - 實測過 Windows Docker Desktop 與 Unraid，其他 Linux 發行版還沒實測。
     - 換服務、重裝後要手動處理的已知問題，連到 59–65 那幾件。
     - 不要直接開到公網。
   - 連結到各份 guide、CHANGELOG、授權與 TMDB 歸屬。
2. **`README.zh-Hant.md`**：同一份內容的繁中版；兩份開頭互相連結。
3. **長段落搬到 `docs/` 的使用者 guide**（英文）：
   - 精靈逐頁細節、接既有服務（含 Unraid 的「Add another Path」寫法）、前置與版本下限、硬鏈接前提、升級、疑難排解、秘密與備份。
   - 每份 guide 開頭一句話說這頁給誰看。
4. **開發者內容搬走**：開發指令、目錄結構、實驗腳本搬到 `CONTRIBUTING.md`（或 `docs/development.md`，擇一）。
   - **專案 `CLAUDE.md`〈指令〉「README 是指令的單一來源」要同一個 commit 改成新的位置**；全域規則要求改目錄結構時同輪更新 CLAUDE.md。
5. **同時修掉文件小錯**：
   - 「四個容器掛同一個媒體根」→ 三個；
   - 「Berth 不存密碼」→ 存加鹽雜湊；
   - 套件內媒體庫不即時監看：手動丟進去的檔案不會自動出現（P2-13）；
   - 「唯一要離開 Berth 的一步是 TMDB」限定成套件內＋公開站。
6. `.env.example` 的註解與 README 對齊：`DATA_ROOT` 試跑可以不改、正式用要改到哪裡；`TZ` 要改成自己的時區。

## 驗收

- [x] `README.md`（英文）的安裝必讀部分（從開頭到「精靈每頁一句話」）不超過約 700 英文字；照它在乾淨目錄實跑一次到精靈頁 1，附指令輸出
- [x] `README.zh-Hant.md` 與英文版段落一一對應，兩份互相連結
- [x] 原 README 每一段都有去處（保留、搬走或刪除），在票的 Comments 列對照表
- [x] 專案 `CLAUDE.md` 的指令來源、README 內部連結、`docs/` 裡指向 README 段落的連結全部更新（用腳本掃斷鏈，結果貼在 Comments）
- [x] 全部檢查綠燈；progress.md 記一行

## Comments

### 實跑：乾淨目錄照 README 到精靈頁 1（2026-10-09，Windows Docker Desktop 29.6.2）

本機產生的 zip、本機 build 的 image（main `fe47457` 加本票工作樹，`berth:t57`；GHCR 的 `:latest` 還是 0.1.0，
`latest/download/` 要到票 58 發版才有東西），repo 外的 scratchpad：

```
$ uv run python scripts/deploy_bundle.py v0.2.0-t57 --out t57/dist
t57/dist/berth-deploy-0.2.0-t57.zip                 # 另有同內容的 berth-deploy.zip
$ cd t57/run && unzip berth-deploy.zip && cd berth && cp .env.example .env
  inflating: berth/.env.example
  inflating: berth/docker-compose.yml
  inflating: berth/preseed/qbittorrent/10-berth.sh
$ # README 第 2 步：DATA_ROOT 留 ./data（試跑）、PUID / PGID 不動（Windows）、TZ=Europe/London
$ docker compose up -d && docker compose ps
berth-t57              Up 13 seconds (healthy)
berth-t57-jellyfin     Up 13 seconds (healthy)
berth-t57-prowlarr     Up 13 seconds (health: starting)
berth-t57-qbittorrent  Up 13 seconds (healthy)
$ docker compose logs qbittorrent | grep berth
[custom-init] 10-berth.sh: executing...
[berth-preseed] added to /config/qBittorrent/qBittorrent.conf: WebUI\AuthSubnetWhitelistEnabled=true WebUI\AuthSubnetWhitelist=10.233.0.2/32
[custom-init] 10-berth.sh: exited 0
$ docker exec berth-t57 date
Thu Oct  8 20:11:02 BST 2026                         # TZ 生效
```

playwright 開 `http://localhost:58383` → 轉到 `/setup?step=1`，精靈頁 1「先選 Jellyfin 是哪一台」、套件內 / 既有兩張卡
（截圖 `.playwright-mcp/t57-page1.png`，不進版控；瀏覽器存著 zh 的語系設定所以是中文介面）。結束後 `docker compose down`、
刪 image 與資料目錄；其他容器沒動。

**為了與本機其他 stack 並存而偏離「照抄」的地方**（zip 的檔案一字未改，同票 56 的做法）：`.env` 的五個 port 改成 5xxxx、
加 `COMPOSE_PROJECT_NAME=berth-t57`；旁邊一份 `docker-compose.override.yml` 換容器名、網路名、子網（`10.233.0.0/16`，
berth 固定 IP 跟著換）與 image。第一次的 override 只寫 `subnet` 沒寫 `ip_range`，整段 `ipam.config` 被蓋掉，
動態配發領走了 berth 的固定 IP（`Address already in use`）；補上 `ip_range` 就好——是 override 寫錯，不是套件的問題。

### 原 README 每一段的去處

| 原段落（`fe47457:README.md`） | 去處 |
| --- | --- |
| 開頭一句簡介 | `README.md` 開頭，英文改寫 |
| 里程碑長段（M1–M3 已完成） | 刪。各版內容在 CHANGELOG；README 改成截圖＋〈Status & known limitations〉 |
| 〈部署〉zip、四行指令、只抓 compose 不夠 | README〈Install〉1–4 |
| 一台主機只跑一套 | `docs/guide/requirements.md`〈Docker〉（`.env.example` 開頭也有） |
| 「唯一要離開 Berth 的一步是 TMDB」 | 改寫成 `setup-wizard.md`〈How the wizard works〉的例外：私站在 Prowlarr 加、既有服務缺掛載要改它的 compose |
| 精靈表（六頁 × 套件內 / 既有） | `setup-wizard.md` 的表；README〈The setup wizard〉每頁一句 |
| Berth 只建自己擁有的東西 | `setup-wizard.md`〈What Berth changes in your services〉，另列已知例外（62、66） |
| 選「既有」的條件、NAS 範例、`docker run` | `existing-services.md`〈What an existing service needs〉，另加 Unraid 模板「Add another Path」 |
| 選了既有之後停掉套件內那一台、沒在跑時的提示、再點一次套件內 | `existing-services.md`〈Stopping a bundled service you no longer use〉 |
| 精靈的頁在網址上、上一頁 / 下一個泊位 | `setup-wizard.md`〈How the wizard works〉 |
| 換一台 | `existing-services.md`〈Switching to another server later〉（補上換台後自動重查 Route，票 59） |
| 索引站可「之後再說」、TMDB 不行；Route 建立時的硬鏈接檢查 | `setup-wizard.md`〈How the wizard works〉 |
| Berth 沒有自己的帳號、介面登入、「不存密碼」 | `setup-wizard.md`〈Accounts and passwords〉，改正成存加鹽 scrypt 雜湊 |
| 設定完成後 `/health` 每 5 分鐘 | `setup-wizard.md`〈After the wizard〉 |
| 〈頁面〉表 | `setup-wizard.md`〈After the wizard〉，補 Review / Issues、RSS 兩列 |
| port 表與「改 `.env` 不改 compose」、`QBITTORRENT_WEBUI_PORT` 要先定 | `troubleshooting.md`〈Ports〉 |
| 已有服務就從 `COMPOSE_PROFILES` 拿掉 | README〈Install〉2、`existing-services.md`〈Before docker compose up -d〉 |
| 〈先申請一把 TMDB API key〉 | README〈What you need〉；要連得到 `api.themoviedb.org` 在 `requirements.md`〈Docker〉與 `troubleshooting.md`；換 key 在 `requirements.md`〈Service versions〉 |
| 〈硬鏈接前提〉 | `requirements.md`〈Hardlinks〉；README 一句「一顆支援硬鏈接的本機磁碟」 |
| 〈支援的宿主平台〉（Linux / Windows / Unraid、實測過的環境） | `requirements.md`〈Host platforms〉；README〈Status〉一句 |
| 〈外部服務的前提〉（版本下限、Jellyfin 10.x 升級、釘版） | `requirements.md`〈Service versions〉；釘版的升級在 `upgrading.md`〈Bundled Jellyfin〉；Prowlarr 的 key 位置在 `existing-services.md`〈Prowlarr〉 |
| 〈秘密與備份〉 | `backup-and-reinstall.md`；README 一句「備份 `${CONFIG_ROOT}/berth`」 |
| 〈重跑設定精靈〉 | `backup-and-reinstall.md`〈Rerunning the wizard〉 |
| 〈版本與升級〉 | `upgrading.md`；`deploy_bundle.py` 的本機指令搬到 `development.md`〈部署套件〉 |
| 〈自己 build image（進階）〉 | `upgrading.md`〈Building your own image〉 |
| 〈部署疑難排解〉（沒有 curl、`Unauthorized`、`port is already allocated`、`host.docker.internal`） | `troubleshooting.md`；`host.docker.internal` 也在 `existing-services.md` |
| 〈環境需求〉〈開發指令〉（安裝、啟動、環境變數、後端、解析基準測試、前端、API 型別、全部檢查、e2e、前端 e2e、UI 的 Fake 後端、實驗腳本）〈目錄結構〉〈疑難排解〉 | `docs/development.md`，原文（中文）搬過去，只改相對連結；目錄結構補 `docs/guide/` |
| 〈帳本重建（`berth rebuild-ledger`）〉 | `development.md` 原文；使用者那一面（何時用、按鈕、容器裡的指令）在 `backup-and-reinstall.md`〈What a ledger rebuild does〉 |
| `PROWLARR__AUTH__APIKEY`（開發環境變數表） | `development.md` 原表；部署面在 `existing-services.md`〈Prowlarr〉 |
| 〈授權與歸屬〉 | README 結尾（兩份） |

刻意沒帶過去的細節：「`.env.example` 裡沒有任何秘密欄位」（`.env.example` 開頭自己說了）、「標為未看先確認」與
「v4 token 走標頭不進 log」（畫面與行為細節，使用者不必先知道）。

文件小錯（做什麼 §5）：三個容器（README、`requirements.md`、`deploy/.env.example`、brief §16 的範例那一行）；
加鹽雜湊（`setup-wizard.md`）；不即時監看（`troubleshooting.md` 最後一節）；「唯一離開 Berth」（見上表）。

### 斷鏈掃描

新閘門 `tests/unit/test_readme_docs.py`：兩份 README 的標題層級序列與對外連結一致；README 兩份、`docs/guide/*`、
`docs/development.md` 的相對連結與錨點（GitHub 的算法）都指得到。測試檔內雙向變異：少一節、多一個 `###`、少一條連結、
檔案不存在、標題不存在會紅；改措辭與標題、程式碼區塊裡的 `##` 與連結、絕對網址不紅。

同一套判定一次性掃整個 repo 的 256 份 Markdown（腳本在 scratchpad，不進版控）：第一輪 2 條斷鏈——
`scripts/experiments/README.md` 指向舊 README〈實驗腳本〉（本票造成，改指 `docs/development.md#實驗腳本`），以及
brief 指向 `m0-experiments.md#1-jellyfin-命名10107-與101111`（舊的錨點少一個 `-`，順手修）。修完：

```
scanned 256 markdown files, 0 broken relative links
links pointing at a README:
README.md -> README.zh-Hant.md
README.zh-Hant.md -> README.md
```

程式註解與 workflow 裡指向 README 段落的文字（不是 Markdown 連結）逐一改指 `docs/development.md` 或 `docs/guide/`：
`.env.example`、`ci.yml`、`e2e.yml`、`release.yml`、`pyproject.toml`、`tests/e2e/*`、`test_e2e_stack.py`、`test_rss.py`、
`fake_setup_server.py`、`jellyfin_naming.py`、`compose_profile_removal.py`、`prowlarr/config_file.py`、`TmdbStep.tsx`、
`deploy/docker-compose.yml`；brief 4 處、plan 5 處。CHANGELOG 已發佈的版本段照舊（歷史）。

### 截圖

`docs/assets/screenshots/` 四張，演練伺服器（`scripts/fake_setup_server.py`）的英文介面、1280×800：精靈頁 3（`bundled`）、
SPY×FAMILY 作品頁搜尋（`submit`）、媒體庫海報牆（`library`）、健康頁（`healthy`）。媒體庫的海報是替身的色塊，不是真海報。

### code-review（fe47457 ... 工作樹）已處理

- Standards：閘門原本只比 `##` 節數，CLAUDE.md 卻寫「段落一一對應」——測試改比標題層級序列（含 `###`），CLAUDE.md
  改寫成「標題層級與連結一致，`test_readme_docs.py` 守」；拿掉 CLAUDE.md 裡的歷史註記；plan §0「文件繁體中文」補上
  README 與 guide 的例外；測試抽出 `_prose`、程式碼區塊裡的 `##` 不算節、兩元素 list 改具名變數。
- Spec：brief §16 範例的「四者掛 `/data`」改三者；繁中版多出的「指南目前只有英文」拿掉；README 頁 3 那一句原本只對套件內
  成立，改成兩種都講；`setup-wizard.md` 的密碼句改通順、已知例外改連到票 62、66；`hardlink.sh` 那句改成「有 clone 才有」。

### 未處理（判斷後留著）

- 註解裡的路徑有的加反引號、有的沒有（Standards）：照各檔原本引用 README 的寫法換字，沒有閘門管，不統一。
- 頁面表多了 Review / Issues、RSS 兩列（Spec 說是範圍外）：內容對、使用者會用到，留著。
- **`deploy/.env.example` 與 compose 的註解仍是中文**：英文 README 叫人改 `.env`，打開卻是中文註解。票沒要求翻，
  建議在票 58 發版前一起翻成英文（`tests/unit/test_deploy_*.py` 只比值，不比註解）。
- **精靈頁 1 右欄「不存下：你的密碼（只交給 Jellyfin）」**：與 P2-16 同一類——勾了沿用時存的是擁有者密碼的雜湊。
  文案歸票 68。
- 實跑中途電腦斷電：工作區兩支 `.py`（`prowlarr/config_file.py`、`test_rss.py`）整檔變成 null bytes，從 git 還原後重套
  那一行註解改動；其餘檔案逐一檢查完整，`git fsck` 無誤。
