# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、session 紀錄、偏差與決定。

## 里程碑與閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| M0 | `.scratch/m0/issues/` | plan §1、§2、§9、§11.1；brief §16、§20.6、§20.7 | 已拆成 11 張票（2026-09-07）。§20.6 的實驗是票 04，排在 compose（票 03）之後；票 05 是第一張 UI 票，開頭跑 `/impeccable hooks on` 與 `init` |
| M1 | `.scratch/m1/issues/` | plan §3、§4、§5、§8、§11.2；brief §5、§6、§7、§20.1–§20.4 | 解析器先寫 fixture 與 harness 再逐階段實作 |
| M2 | `.scratch/m2/issues/` | plan §11.3；brief §9 | |
| M3 | `.scratch/m3/issues/` | plan §11.4；brief §15 | 先抓 Mikan 與 Nyaa 的 RSS fixture |
| M4 | `.scratch/m4/issues/` | plan §11.5；brief §6.10 | |

拆票：每個里程碑開頭跑 `/to-tickets docs/plan.md` 並指定里程碑；每張票要寫「讀：plan §x、brief §y」與驗收條件。plan §11 是拆票的輸入與驗收來源，拆票後以票為準。

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-09-07 | 文件 | brief、plan、CLAUDE.md、CONTEXT.md、matt pocock skills 設定完成並 commit | `/to-tickets docs/plan.md` 拆 M0 |
| 2026-09-07 | 拆票 | M0 拆成 11 張票寫入 `.scratch/m0/issues/`，三條偏差記於下方 | `/implement .scratch/m0/issues/01-repo-skeleton.md` |
| 2026-09-07 | 01 骨架 | uv 後端 + `berth --version`、pnpm/Vite/React 前端、ruff / mypy / pytest / import-linter / eslint / prettier / vitest、pre-commit、CI、LICENSE / CHANGELOG / README 完成。票留在 `ready-for-human`：唯一未過的驗收是「CI 在 PR 上綠燈」，repo 還沒有 GitHub remote | 建 remote 並開 PR 勾掉票 01 最後一條；之後 `/implement .scratch/m0/issues/02-app-skeleton.md` |
| 2026-09-07 | 02 應用骨架 | `berth serve` 起 FastAPI，lifespan 自動套 Alembic migration、SQLite 開 WAL、建 M0 五張表；`GET /api/health` 匿名 200；六個 settings 分組可讀可寫；前端 shell（Tailwind 深色主題、`zh-Hant`、TanStack Router / Query、健康佔位頁）由後端同一程序提供。51 個後端測試 + 5 個前端測試綠燈，playwright 實跑深淺兩種主題確認 | `/implement .scratch/m0/issues/03-deploy-compose.md` |
| 2026-09-07 | 03 部署套件 | `deploy/` 完成：多階段 image（281 MB / gzip 62.8 MB）、四服務 compose（profiles、固定子網、健康檢查）、qBittorrent preseed、`.env.example`、GHCR 發佈 workflow 與 CI 的 image build job；README 補上部署段與 brief §16.1 / §16.2 要求的前提。實跑驗證：四個容器健康、四個 port 可達、拿掉 jellyfin profile 只起三個、berth 免密進 qBittorrent 而宿主被擋、preseed 重建兩次不改設定檔、PID 1 非 root。票留在 `ready-for-human`：唯一未過的驗收仍是要 remote 才驗得了的 GHCR workflow | 建 remote 後回頭勾掉票 01 與票 03 的最後一條；之後 `/implement .scratch/m0/issues/04-experiments.md` |
| 2026-09-07 | 01 / 03 收尾 | GitHub remote 建好（`1morr/Berth`，public，預設分支 `main`）。CI 原本一次都沒跑過：`ci.yml` 觸發條件寫 `main` 但分支是 `master`，且 `astral-sh/setup-uv` 沒有 `v10` major tag。兩者修好後 push 與 PR（#1）皆四個 job 全綠；`v0.1.0-rc1` 觸發 release workflow，image 推上 GHCR 且未動 `:latest`。票 01 與 03 皆為 done | `/implement .scratch/m0/issues/04-experiments.md` |
| 2026-09-07 | 04 實驗 | `scripts/experiments/` 完成並全部實跑：Jellyfin 10.10.7 / 10.11.11 命名實測、qBittorrent 4.4.5 / 5.2.3 參數矩陣、Prowlarr `config/host`、硬鏈接三情境。結果寫進 `docs/research/m0-experiments.md`，摘要回 brief §20.6 / §20.7，plan §5 命名模板凍結，§8.1 / §8.2 / §9.2 / §9.4 依實測修正，brief §7.2 / §7.7 / §20.1 更正。lint / type / test 全綠 | `/implement .scratch/m0/issues/05-*.md`（第一張 UI 票，開頭跑 `/impeccable hooks on` 與 `init`） |
| 2026-09-07 | 05 精靈第 1–2 步 | `/setup` 精靈骨架完成：`GET /api/setup/status`、`POST /api/setup/admin`、`POST /api/setup/detect`、`POST /api/setup/services/{kind}`；Jellyfin / qBittorrent / Prowlarr 三個 adapter 各有 `Protocol`、HTTP 實作與 `Fake`，契約測試跑對真服務錄下來的 `tests/fixtures/http/`。UI 依 direction contract「泊位調度板」重寫視覺系統（票 02 的佔位 token 全換），zh-Hant 與 en 並列。125 個後端測試 + 24 個前端測試綠燈；playwright 對 `scripts/fake_setup_server.py` 的三種情境實跑前兩步，深淺兩主題所有文字對比 ≥ 4.5:1 | `/implement .scratch/m0/issues/06-wizard-jellyfin.md` |

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-09-07 拆票：M0 只建 `users`、`sessions`、`settings`、`routes`、`events` 五張表，plan §2 其餘的表在需要它們的里程碑用 Alembic 增量加。推翻 plan §11.1 T0.2 的「schema 完整」驗收。理由是不為未來需求預先建表，Alembic 隨時可加。
- 2026-09-07 拆票：M0 不設「adapters 第一版」的獨立任務，改成按精靈步驟垂直切票（票 05–09），每張票帶進自己需要的 adapter 能力、Fake 與契約測試。推翻 plan §11.1 的 T0.4 / T0.6 分法。理由是 T0.6 一票塞不進一個 session，而單獨的 adapter 票沒有可示範的成果。
- 2026-09-07 拆票：brief §20.6 的實驗排在 compose 之後（票 04，而非 M0 第一張）。推翻 brief §17「實驗最先」的順序。理由是實驗需要真的 Jellyfin 與兩個版本的 qBittorrent，compose（票 03）已經提供；命名模組要到 M1 才寫，模板在那之前凍結即可。
- 2026-09-07 事實更正：brief §20.3 的「TVDB v4 要每位使用者自付訂閱並輸入 PIN」過度。重查為：申請 key 免費、`/login` 的 `pin` 選填、無 PIN 實測可讀，Jellyfin 官方 TVDB 插件同形狀（內建 project key + 選填 PIN）；但授權條款仍要求終端使用者訂閱，內建 key 靠執行寬鬆。已改 §20.3、§10 的理由與 §20.6 的實驗項。§10「第一階段只用 TMDB」的決定不變，但新增【研究】：TVDB 作為 anime profile 的季集來源，以 §20.6 的動漫編號實驗定案，須在 M1 拆票前決定。
- 2026-09-07 票 01：前端裝 React 19（現行 stable，`create vite` 的預設），推翻 plan §1.4 的「React 18」，已回寫 plan。
- 2026-09-07 票 01：plan 沒寫的四件事補進 plan §1.2 / §1.3 / §1.4 —— Python 3.13 與 Node 24 為執行環境、CLI 用 stdlib argparse、`db` 在 import-linter 契約中位於 `models` 之下 `domain` 之上、Alembic 的 `env.py` 從 `db/` 移到 `migrations/`（它要 import `models`，留在 `db/` 會違反契約）。
- 2026-09-07 票 01：CI workflow 已寫但未實跑，repo 還沒有 GitHub remote。建 remote 後第一個 PR 要回票 01 勾掉該條驗收，票在那之前維持 `ready-for-human`。
- 2026-09-07 票 01：brief §16.1 / §16.2 要求 README 寫的部署前提（硬鏈接限制、qBittorrent 版本下限、MergeVersions、TMDB 歸屬、秘密不加密）延到票 03，已記在該票的 Comments。
- 2026-09-07 票 02：新增環境變數 `WEB_ROOT`（預設 `<repo>/web/dist`），plan 只寫了 `/config` 與 `/data`。理由是 wheel 安裝後 repo 佈局不存在，容器要能指到 image 內的複製位置；票 03 的 Dockerfile 會設它。已補進 plan §1.1 與 README。
- 2026-09-07 票 02：`settings.services.*` 這一輪只放連線資訊，plan §2.1 另外要求的「最後健康狀態」延到票 10 一起定形狀。理由是 M0 票 02–09 沒有任何地方讀寫它，先猜欄位形狀會猜錯。
- 2026-09-07 票 02：時間欄位用自寫的 `UtcDateTime` TypeDecorator 存 UTC ISO 8601 TEXT，不用 SQLAlchemy 的 `DateTime`。理由是後者在 SQLite 上回 naive datetime，跨時區比較必錯；plan §2 本來就要求 ISO 8601。
- 2026-09-07 票 02：本票寫了前端但沒跑 `/impeccable`，推翻 CLAUDE.md「所有前端頁面走 /impeccable」的字面要求。理由是拆票時已把票 05 定為第一張 UI 票（`hooks on` 與 `init` 在那裡跑），本票只做證明前後端串起來的佔位頁。`web/src/index.css` 的七個色彩 token 與亮色覆寫是 plan §7「深色為預設、亮色跟隨系統」的最小實作，票 05 的 `/impeccable init` 定案時以它為準重寫。
- 2026-09-07 票 02：TanStack Router 裝 1.170.32 而非最新的 1.170.33。理由是 1.170.33 發佈未滿 pnpm 的 `minimumReleaseAge` 供應鏈門檻，不為了小版號在 lockfile 開例外。
- 2026-09-07 票 03：qBittorrent 的免密白名單改成只放行 berth 容器固定 IP 的 `/32`，不是 plan 原本的整個網段。理由是 Docker Desktop 把發佈 port 進來的流量 SNAT 成閘道位址（`172.28.0.1`，也在網段內），整段開放實測讓宿主與 LAN 免密打得到 qBittorrent API。已回寫 plan §9.1、§9.2 與 brief §16.3、§20.7；compose 用 `ip_range` 把動態配發隔開，固定 IP 才不會被別的容器領走。
- 2026-09-07 票 03：preseed 改成「缺鍵才補、已有值不動」，推翻 plan §9.2 的「檔案不存在才寫」。理由是 linuxserver 的 `init-qbittorrent-config` 先跑並已從 `/defaults` 複製設定檔，原條件永遠不成立；整份覆蓋會掉 `LegalNotice\Accepted=true`。已回寫 plan §9.2 與 brief §20.7。
- 2026-09-07 票 03：`WebUI\ServerDomains` 不預置，推翻 plan §9.2。理由是 image 預設值是 `*`，Host 檢查本來就過得了，寫死成 `qbittorrent` 反而讓使用者從 `localhost:8080` 進不了 WebUI。
- 2026-09-07 票 03：入口腳本只在 `/data` 還是空目錄時接手擁有者。理由是媒體根可能是別的帳號擁有的共用目錄；但 Docker 替 bind mount 新建的目錄是 `root:root`，不接手的話乾淨環境第一次啟動就寫不進去。已補進 plan §9.1。
- 2026-09-07 票 03：image 不裝 curl，所以票的驗收指令改用容器內的 python urllib（adapter 之後真正走的路徑）加同網段的一次性 curl 容器驗證，兩者都免密回 `v5.2.3`。README 的部署疑難排解記了 python 那條指令。
- 2026-09-07 票 03：plan §11.1 T0.7 的「compose 範本（Linux 與 Windows 兩個 override）」改成一份共用的 compose，與 §9.1 本來就寫的一致。另外 CI 加了只 build 不推的 image job，plan §10 本來就列了 image build。
- 2026-09-07 票 03：GHCR image 名稱假設 GitHub owner 是 `1morr`（compose 寫死 `ghcr.io/1morr/berth:latest`，workflow 用 `github.repository_owner` 組同一個名字）。repo 還沒有 remote，workflow 與這個名字都要等建了 remote 才驗得了。
- 2026-09-07 收尾：分支從 `master` 改名為 `main`，與 plan §0 的措辭一致；GitHub 預設分支同步改掉，舊的 `master` 已刪除。
- 2026-09-07 收尾：workflow 的 action 一律 pin 到「實際存在的 tag」而非推測的 major tag。`astral-sh/setup-uv` 只發 `v10.0.1` / `v10.0.0`，沒有 `v10`，用 major tag 會讓 job 連起都起不來。
- 2026-09-07 收尾：repo 轉 public（MIT，brief §16.2）。轉之前掃過全歷史，沒有秘密、沒有真 `.env`、沒有本機路徑外洩。GHCR package 隨之公開可匿名拉取。
- 2026-09-07 票 04：brief §7.2 的電影檔名範例更正 —— 檔名在 ` - ` 之前必須與資料夾名一字不差，**含 `[tmdbid-<id>]`**。實測少了它就不是多版本而是兩部獨立的電影。plan §5 的模板本來就是對的，凍結不動。
- 2026-09-07 票 04：brief §7.7 的「版本標籤即 tags 字串」只對電影成立。劇集經 MergeVersions 合併後，版本選單顯示的是**整個檔名主幹**，而且順序不保證（10.10 與 10.11 相反）。
- 2026-09-07 票 04：plan §8.2 的 `find_episodes(series_id)` 改成 `find_episodes(series_folder_path)`，用「媒體庫 recursive + `Path` 前綴」而不是 `parentId=<seriesId>`。理由是 10.11 第一次掃描後，對已比對到 provider 的 Series，`parentId=<seriesId>` 與 `/Shows/{id}/Episodes` 都回 0，要再掃一次才正常；10.10 沒有這個問題。
- 2026-09-07 票 04：plan §9.4 第 3 步補上「先 `GET /Startup/User`」。直接 POST 在兩個版本都回 500（`Sequence contains no elements`），GET 那一支才會建立預設使用者。
- 2026-09-07 票 04：plan §9.4 第 4 步的 body 要包成 `{"LibraryOptions": {...}}`（`AddVirtualFolderDto`）。直接送 `LibraryOptions` 一樣回 204，但整份設定被靜默丟掉。
- 2026-09-07 票 04：plan §9.2 補上「qBittorrent 的發佈 port 不可以改號碼」。Host 檢查除了網域還比對 port，`ServerDomains=*` 也不放過 port 不符；README 的部署疑難排解已記。原本「不預置 `ServerDomains`」的決定維持，也不需要 `HostHeaderValidation=false`。
- 2026-09-07 票 04：plan §8.1 的 `torrents/files.name` 從「兩種基準都試」收斂成「相對 `save_path`」，四種 `contentLayout` 組合實測都成立；另外要正規化 `save_path` 的尾斜線（4.4 有、5.x 沒有）。
- 2026-09-07 票 04：brief §20.1 的 `zh-Hant` / `zh-Hans` 有答案了 —— 只有 10.11 認得，10.10 顯示「未定義」，所以字幕沿用 `<stem>.CHT.zh.ass`，plan §5 不動。
- 2026-09-07 票 04：brief §20.6 的「Linux 宿主硬鏈接」用 Docker Desktop 的 Linux VM（ext4）完成 —— daemon 端的檔案系統，不是另一台實體 Linux。原生 Linux 宿主與 NAS 兩條都仍未做，已在 brief §20.6 / §20.7 與票的 Comments 標明。
- 2026-09-07 票 04：另起 `scripts/experiments/compose.yml`，沒有用票寫的「03 的 compose 環境」。理由是 `deploy/` 只有單一版本的 Jellyfin 與 qBittorrent，而本票的核心是兩個版本各跑一次；而且實驗會改壞 qBittorrent 的偏好、砍掉 Jellyfin 的 `/config`，不該碰使用者照 README 起的那一套。port 與子網都錯開，兩套可並存。
- 2026-09-07 票 04：版本標籤**含中文**沒測到（實驗的 tag 全是 ASCII），但 brief §6.8 的 group token 保留字幕組原文。brief §20.1「多版本」保留「未證實」，不當成已驗證。
- 2026-09-07 票 04：plan §9.4 第 8 步的「輪詢 `/System/Info/Public` 直到恢復」改成「輪詢真正要用的管理員端點回 200」。`/System/Info/Public` 在伺服器還在載入時就回 200，這時 `/ScheduledTasks` 回 503，實驗腳本重跑時踩到了。
- 2026-09-07 票 04：`scripts/` 納入 mypy 的 `files`（`pyproject.toml`），實驗腳本的型別註記才不是裝飾。強制之後抓到 `lib.py` 的 `multipart()` 有一個變數同時被當 str 與 bytes 用。
- 2026-09-07 票 05 `/impeccable init`：UI 語言從「zh-Hant 唯一、不做英文版直到有需求」改成 **zh-Hant 與 en 並列**。推翻 brief §16.2 與 plan §7，兩處已改。理由是使用者確認 Berth 是開源給自架者、且要面向英語使用者。`web/src/i18n/` 目前寫死 `lng: 'zh-Hant'` 且只有一個語言檔，票 05 實作時補上 en 與語言偵測。
- 2026-09-07 票 05 `/impeccable init`：裝置假設定為「桌機為主，但每頁都要有真正可用的窄版」。brief 與 plan 原本完全沒有裝置或螢幕尺寸的敘述，已補進 plan §7 與 `PRODUCT.md`。
- 2026-09-07 票 05 `/impeccable init`：無障礙目標定為 **WCAG 2.2 AA**，是驗收條件不是加分項。brief 與 plan 原本沒有任何無障礙要求，已補進 plan §7 與 `PRODUCT.md`；之後每頁的 `/impeccable audit` 以它為準。
- 2026-09-07 票 05 `/impeccable init`：新增根目錄 `PRODUCT.md`（impeccable 的產品脈絡，CLAUDE.md 已列為文件之一）與 `.impeccable/`（設計偵測 hook 設定，`config.local.json` 已加進 `.gitignore`）。`DESIGN.md` 還沒建立——它在第一個頁面 `shape` 之後才由 impeccable 依實際做出來的東西產生。
- 2026-09-07 票 05 `/impeccable shape 設定精靈`：精靈可**續行**（狀態在 `settings.setup`），第 5 步索引站與第 6 步 TMDB **可跳過**，其餘不可跳。plan §9.3 原本沒寫這兩件，已補。同時把八步歸成四個泊位（Jellyfin / qBittorrent / 來源 / 媒體庫路徑），與 M0 驗收的「四項綠燈」對齊。
- 2026-09-07 票 05 `/impeccable shape 設定精靈`：視覺世界定案為「泊位調度板」（concept-seed `b84bd503`，card `assigned`，使用者於決策頁鎖定）。執行契約 **code-led**（此 harness 無圖像生成）。shape brief 寫在 `.scratch/m0/wizard-shape.md`；direction contract 由票 05 的 build session 寫，DESIGN.md 由票 11 產生。
- 2026-09-07 票 05：`settings.setup` 存的是**明文密碼**，不是票的驗收寫的「密碼雜湊」。理由是雜湊沒有消費者也做不到該做的事——第 3 步要拿這組帳密去建 Jellyfin 管理員（plan §9.4 第 3 步），第 4 步要拿它設 qBittorrent 的 WebUI 密碼，兩者都需要明文；Berth 自己從不驗證這組密碼（登入走 Jellyfin，brief §11）。與其他 `settings.services.*` 的 key 與密碼一致，只靠檔案權限保護（brief §16.2）。票的驗收行已改。
- 2026-09-07 票 05：`settings.setup` 移除票 02 建的 `current_step` 欄位，步驟改成由狀態導出（管理員未建立 → 1；有服務還在探測或逾時 → 2；否則 3）。理由是精靈可續行也可重跑，存游標會在偵測結果變回等待時說謊。已補進 plan §9.3 第 2 步。
- 2026-09-07 票 05：「探不到服務」拆成兩種判定——主機名解不到（`socket.gaierror`）→ 不在 compose 裡，立刻判既有；解得到但連不上 → 容器啟動中，續探到 2 分鐘上限後判逾時。plan §9.3 原本只寫「探不到或已設定過 → 既有」。**實測發現**：這條鏈在 httpx 是 `ConnectError → httpcore.ConnectError → socket.gaierror`，而第二層是 `__context__` 不是 `__cause__`，只走 `__cause__` 會把「服務不在」誤判成「還在啟動」，害使用者白等兩分鐘。在 compose 網路內對 Docker 內建 DNS 實測確認。另外本機開發用的 DNS 會劫持 NXDOMAIN（`.invalid` 也解得到位址），所以逾時的 UI 也給連線表單，兩種 DNS 環境都走得下去。
- 2026-09-07 票 05：新增 `POST /api/setup/services/{kind}`（plan §6 已補）。票只寫「顯示連線表單」，但「Prowlarr 讀不到 API key 時退回手動貼上」要成立，貼上的值就必須真的存得下來並生效，否則表單只是擺設。同時帶進 qBittorrent 的 `auth/login`（既有服務的「測試連線」要真的驗得了帳密）。測不過也照樣存，使用者才能改一個欄位再按一次。
- 2026-09-07 票 05：adapter 的例外名一律以 `Error` 結尾（`ServiceUnavailableError`…），推翻 plan §8.1 原本寫的 `ServiceUnavailable` / `AuthFailed` / `CategoryMissing`。理由是 ruff 的 N818 擋下來，而為了三個名字在專案全域關掉一條 lint 規則不划算。plan §8.1 已改。
- 2026-09-07 票 05：import-linter 的「api and pipeline call services only」契約加上 `allow_indirect_imports`。理由是 `api → services → models` 正是 plan §1.3 要的方向，沒有這個旗標時任何經由 services 的間接依賴都算違規，票 02 沒踩到只是因為當時 api 還沒呼叫過 services。
- 2026-09-07 票 05：**不引入 shadcn/ui**，推翻 plan §7 / §1.4 的「shadcn/ui 為元件基礎」（僅就第 1–2 步而言）。理由是這兩步沒有任何需要行為基礎的元件（無 dropdown / dialog / popover / tabs），原生 `input` / `checkbox` / `button` 的無障礙比 Radix 重寫的更好；真的需要行為原語的那一步再引入。plan §7 未改，等票 06–09 確認是否真的需要。
- 2026-09-07 票 05：**不引入 webfont**。方向要求「模板噴字 + 貨櫃編號等寬」，但自架應用不該對 Google Fonts 發請求、離線也要成立，所以改用等寬系統堆疊加重字距、橫線與塗裝色塊承載那個語彙。shape brief 標為「最大實作風險」的字體問題就此定案，已寫進 direction contract 的 Resolved 段。
- 2026-09-07 票 05：`.label` 的中文分岔用**塗上去的刻度**（空 `content` + `inline-block` 背景）而不是 `▸` 字元。實測 `content: '▸ '` 會被算進無障礙名稱，螢幕閱讀器把「帳號」念成「三角形 帳號」。
- 2026-09-07 票 05：四個信號色與 `on-signal` **兩個主題共用**，只有中性色與「當字用」的兩個信號色（`blocked-ink`、`secured-ink`）隨主題換。理由是亮色主題原本把信號色壓深配白字，實測只有 3.60:1，過不了 AA；改成「同一罐漆配黑字」之後兩個主題所有文字配對都 ≥ 4.5:1（實測值記在票的 Comments）。
- 2026-09-07 票 05 code-review：**重探會清掉使用者剛接好的服務**。`detect_services` 整份覆寫 `settings.setup.services`，而前端只要有服務還在啟動就每 3 秒自動探一次——「Jellyfin 被拿掉 profile + qBittorrent 還在啟動」正好是票上寫的組合，填完表單三秒後就被判回「探不到」。`ServiceProbe` 因此多一個 `configured` 旗標，重探跳過它；要重測就用那個服務自己的「測試連線」。
- 2026-09-07 票 05 code-review：**「測試連線」的判定改用與探測相同的規則**，不再一律判「既有」。原本的寫法會讓一台讀不到 API key 的**套件內** Prowlarr 在使用者貼上 key 之後永遠是既有，票 08 的十個預設索引站對它就不會跑。判定看的是服務自己報出來的事實，不是位址是誰填的。唯一的差別是「連不上」：探 compose 主機名時代表容器還在啟動（該等），使用者自己填的位址連不上就是連不上（不給倒數）。
- 2026-09-07 票 05 code-review：信號色的規則收斂成「探測成功與否」而不是單一 reason。既有服務連得上是 `secured`（這一步的事做完了），連不上才是 `assigned`。同時把 `SIGNAL_FILL` 與 `Signal` 從 `setup/` 移到 `components/signal.ts`、控制項移到 `components/controls.tsx`——健康頁已經在用它們，共用元件不該住在精靈專屬資料夾。
- 2026-09-07 票 05 code-review：`SetupStatus` 不再帶 `admin_password`。它只有測試讀得到，API 本來就刻意剝掉，票 06 / 08 直接讀 `settings.setup`。
