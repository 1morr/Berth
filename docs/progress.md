# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、session 紀錄、偏差與決定。

## 里程碑與閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| M0 | `.scratch/m0/issues/` | plan §1、§2、§9、§11.1；brief §16、§20.6、§20.7 | 已拆成 11 張票（2026-09-07）。§20.6 的實驗是票 04，排在 compose（票 03）之後；票 05 是第一張 UI 票，開頭跑 `/impeccable hooks on` 與 `init` |
| M1 | `.scratch/m1/issues/` | plan §3、§4、§5、§8、§11.2；brief §5、§6、§7、§20.1–§20.4 | 已拆成 15 張票（2026-09-08），票 01 做完後插入 02b（2026-09-09），共 16 張。票 01 是 brief §10 的 TVDB 【研究】，它決定 `media` 的欄位所以排最前；票 02 是 openapi 型別產生器的 prefactor；票 02b 拿掉內建 TMDB 憑證，排在 03 之前因為之後每張票都要有憑證才跑得動。解析器（票 05–07）先寫 fixture 與 harness 再逐階段實作，與 UI 那條線（票 03–04）並行，在票 08 匯流 |
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
| 2026-09-07 | 06 精靈第 3 步 Jellyfin | 套件內一鍵跑完 plan §9.4 的九步（建管理員、三個媒體庫、API key、裝 MergeVersions、重啟、記下兩個任務 `Id`），每一步冪等、失敗可重試；既有路徑登入取 key、列媒體庫與路徑、TVDB 警告、兩顆需二次確認的按鈕。**對真的 `jellyfin:10.11.11` 跑完全序列 69 秒，第二次 0.2 秒全 `skipped`**；fixture 從那一輪錄下。175 個後端測試 + 38 個前端測試綠燈；playwright 實跑三個情境，深淺兩主題所有文字對比 ≥ 4.5:1 | `/implement .scratch/m0/issues/07-auth.md` |
| 2026-09-08 | 07 認證 | Jellyfin 帳密登入換 Berth session（httpOnly + `SameSite=Strict`，30 天不續期）；門禁是 middleware，`/api` 預設拒絕；`setup/*` 完成後只放行 admin。登入頁走 `/impeccable shape`（單一登船口窗格，不畫泊位板）。229 個後端測試 + 54 個前端測試綠燈；playwright 對 `--scenario signed-out` 實跑登入 / 登出 / 非 admin 阻擋三條路徑，深淺兩主題文字對比最低 5.71:1 | `/implement .scratch/m0/issues/08-wizard-services.md` |
| 2026-09-08 | 08 精靈第 4–6 步 | 泊位 2（qBittorrent 逐鍵差異與套用、版本閘門、密碼）與泊位 3（十個預設索引站逐站成敗、既有 Prowlarr / 任意 Torznab、TMDB 內建憑證可覆寫、兩步可跳過）完成。**對真服務錄了 14 份新 fixture**：qBittorrent 4.4.5 與 5.2.3 各一組、Prowlarr 的 schema 與三種新增結果、Torznab caps、TMDB configuration。十個站在本機五成五敗，逐站結果就是 UI 要撐住的東西。297 個後端測試 + 70 個前端測試綠燈；playwright 實跑 `bundled` 與 `outdated` 兩個情境，深淺兩主題文字對比最低 5.22:1 | `/implement .scratch/m0/issues/09-wizard-routes.md` |
| 2026-09-08 | 10 健康檢查 | `health_checker` 由 lifespan 啟動（每 30 秒醒、上一輪滿 5 分鐘才跑、精靈跑完前不跑、關閉時不留 pending task）；四項檢查——Jellyfin、qBittorrent（含建議設定漂移）、索引站、每條 Route 的五條纜繩（與精靈第 7 步同一組、寫回同一個欄位並記下最後成功時間）。`GET /api/health` 的 `status` 改由紀錄導出，新增 `GET /api/health/detail`、`POST /api/health/check` 與 `/api/settings/*`（只有 admin）。健康頁 `/health` 與服務設定頁 `/settings/services` 走 `/impeccable shape`（`.scratch/m0/health-shape.md`），與精靈**同一塊泊位板**。416 個後端測試 + 103 個前端測試綠燈；三個新情境（`healthy` / `degraded` / `drifted`）實跑驗證，深淺兩主題最低對比 5.71:1 | `/implement .scratch/m0/issues/11-m0-acceptance.md` |
| 2026-09-08 | 09 精靈第 7–8 步 | 泊位 4（媒體庫 → Library Route）與完成頁做完：套件內自動建三條 Route、既有由使用者勾選媒體庫與寫入目標（可就地加 Berth 路徑、劇集可挑 profile），每條 Route 建 `berth-*` category 並跑五項跨服務檢查（含**真的 `link()` 再比 inode**）；`POST /api/setup/complete` 全綠才寫 `settings.setup.completed`。fs adapter 帶進來（`link`、`stat`、`same_inode`、`link_test`、`probe_file`、`free_space`、`is_within`，寫入一律要允許的根）。356 個後端測試 + 84 個前端測試綠燈；playwright 對 `--scenario bundled` 走完八步（Windows NTFS 上真的建了硬鏈接：`dev=11550084160259632778 · inode=17451448556763814`），對新的 `--scenario unmounted` 看失敗樣子 | `/implement .scratch/m0/issues/10-health.md` |
| 2026-09-08 | 11 M0 收尾 | 三輪驗收全過：乾淨 Linux（Docker Desktop VM 的 ext4）、乾淨 Windows（NTFS 9p bind mount）、以及「既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr」，每一輪都是`docker compose up` → **只操作 Berth** → 四項綠燈；既有媒體庫是加路徑，項目 ID 與觀看紀錄五項全未變。**驗收本身抓到三個真缺陷並修掉**：入口腳本從來沒接手過 `/data`（乾淨 Linux 上精靈第 3 步必死）、qBittorrent 5.x 的登入被判成失敗（每一套預設部署健康檢查永遠紅）、Prowlarr 冷啟動`indexer/schema` 超過 5 秒逾時（實測 9.42 秒）。`/impeccable critique` 22/40、檢測器 0 findings，polish 修掉對比 3.56:1、英文大寫掉 API 端點、索引站跳過零回饋、`<summary>` 焦點環、觸控目標、窄版 carousel、精靈沒有出口；`DESIGN.md` 產生。README 與 CHANGELOG 定稿，票 01–10 的遺留逐條過完（延後的寫進 plan §11）。425 後端 + 104 前端測試綠燈 | M0 完成。`/to-tickets docs/plan.md` 拆 M1 |
| 2026-09-08 | 拆票 | M1 拆成 15 張票寫入 `.scratch/m1/issues/`（使用者拍板四個顆粒度問題），四條偏差記於下方 | `/implement .scratch/m1/issues/01-anime-episode-source.md` |
| 2026-09-09 | 01 動漫季集來源 | brief §10 的 TVDB【研究】結案：**維持 TMDB**。10 部動漫、7,833 筆真實字幕組釋出，TMDB 8.0% / TVDB aired 7.6% / TVDB absolute 7.6% —— 差 0.4 個百分點，而 TVDB 要付授權（ToS 禁止內建 key 轉讓）、Jellyfin 沒有絕對編號概念（要逐劇寫 `DisplayOrder`）、Skyhook 不能寫進產品三個代價。**真正的失敗主因與來源無關**：九成的失敗是檔名只有篇章名沒有季號（柱訓練篇、最終季、死滅迴游），已寫成 plan §4.4 的解析器需求並記進票 06。方法上換過三次錨點才穩：最後用 Mikan 的發佈時間把檔名數字釘到實際播出，再逐（輪次, 字幕組）校準偏移量。腳本 `scripts/experiments/anime_episode_source.py` 可重跑，研究文件 `docs/research/anime-episode-source.md` | `/implement .scratch/m1/issues/02-openapi-types.md` |
| 2026-09-09 | 02 openapi 型別 | `berth openapi`（不跑起服務、不碰資料庫）+ `pnpm -C web gen:api`（openapi-typescript 7.13）產出 `web/src/api/schema.d.ts`；前端的 API 模組與三個元件的 prop 不再有任何手寫的 API 形狀，連七個 request body literal 都加了 `satisfies`。CI 多一個 `api-types` job，型別檔過期時 `git diff --exit-code` 紅。型別檔進版控、中間產物 `openapi.json` 不進（理由在票上）。**換過來當天就抓到一個真漂移**：`ServiceDetection` 少了後端早就在回的 `configured`。以一次真的後端改動實證（`failures` → `failure_count`、`drift` 變選填）：不重跑產生器時 typecheck 仍是綠的——那正是過期檢查存在的理由；重產後 CI 的檢查 exit=1，`tsc` 在 `ServiceCard` / `signals` / `fixtures` 三處紅。431 後端測試 + 104 前端測試綠燈；playwright 對 `healthy` 與 `bundled` 兩個情境實跑健康頁、服務設定頁與精靈第 1 步 | `/implement .scratch/m1/issues/02b-tmdb-user-key.md` |
| 2026-09-09 | 02b TMDB 使用者自備 key | **Berth 不再內建任何 provider 的 API key**。`PROJECT_CREDENTIAL` 從 repo 消失，`credential()` 只讀 `settings.services.tmdb.api_key`；精靈第 6 步從「可跳過的覆寫」變成必填閘門——`POST /api/setup/tmdb/skip` 刪除，`_current_step` 要 `configuration` 綠燈才過得去，`POST /api/setup/complete` 缺憑證時回 422。`GET /api/setup/tmdb` 的形狀換成 `api_key_present` + `verified`（閘門判定由後端導出，前端不再自己導一次），`SetupTmdb.skipped` 移除（`extra="ignore"`，不需要 migration）。空白送出不打網路，直接是一條說「必填」的紅線。實驗腳本改讀 `TMDB_API_KEY`。`/impeccable critique` 23 / 40（M0 是 22），檢測器 0 findings，據此修掉六條——其中兩條是回歸：空欄時停用主要按鈕（票 11 抓過的「按不動讀起來像壞掉」，改成按鈕永遠按得下去、說不行的是欄位）與結果列缺 `aria-live`；另補上外部連結（整頁原本一個 `a` 都沒有）、手機的 `STICKY_ACTION` 與一條跑得動的連線探測。432 後端 + 105 前端測試綠燈；playwright 實跑「沒填 key 走不完精靈」：泊位板停在 BTH 3、`complete` 回 422，貼上 key 測過才放行。深色最低 7.74:1、亮色 6.44:1 | `/implement .scratch/m1/issues/03-tmdb-discover.md` |
| 2026-09-09 | 03 TMDB 探索頁 | `media` 與 `tmdb_cache` 兩張表與 migration（升得上去也降得回來，且降完再升是同一份 schema）；TMDB adapter 補 `trending/{tv,movie}/week`、`{tv,movie}/popular`、`search/multi`，**11 份 fixture 對真 API 錄**；全域 40 req/s 令牌桶（時鐘與 sleep 注入，量的是「它決定等多久」）；`services/discover.py` 的三個 feed、一小時快取與三種失敗理由；`/` 從轉址變成真的探索頁，走 `/impeccable shape`。477 個後端測試 + 122 個前端測試綠燈；**對真的 `api.themoviedb.org` 實跑**：快取第一次 1075 ms / 第二次 11 ms，深淺兩主題最低對比 5.71:1 與 6.53:1，390px 無橫向捲動。實跑當場抓到三個缺陷（灰板子、海報上的色塊、滿版按鈕）並修掉 | `/implement .scratch/m1/issues/04-media-detail.md` |

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
- 2026-09-07 票 06：**精靈第 2 步的完成條件從「有結論」改成「每個服務都連得上」**。判定多一個
  `resolved` 旗標（`not_deployed` / `unreachable` / `auth_required` / `protocol_mismatch` /
  `api_key_missing` 都算未解決），全部解決才離得開第 2 步。推翻 plan §9.3 第 2 步原本的措辭，已回寫。
  理由：接上第 3 步之後才看見的破口——從 `COMPOSE_PROFILES` 拿掉的 Jellyfin 立刻就有結論（既有），
  精靈於是跳到第 3 步，而使用者唯一能填位址的表單在第 2 步。前端的信號色改讀同一個旗標，不再自己
  維護一份「哪些理由算沒解決」。
- 2026-09-07 票 06：判定一出來伺服器就把步驟推到 3，但**畫面停在第 2 步**等使用者按「前往泊位 1」。
  否則他看不到自己剛按下的那一輪靠泊序列——那是票 05 的署名互動。這是前端覆寫，不是後端游標。plan §9.3 已補。
- 2026-09-07 票 06：`POST /Auth/Keys?app=` **回 204、不回傳 key、也不檢查重複**（按兩次就有兩把同名的）。
  所以要先 `GET /Auth/Keys` 找、沒有才建、建完再列一次讀回來。plan §9.4 第 7 步與 brief §20.7 已改。
- 2026-09-07 票 06：`POST /Library/VirtualFolders` **同名不會被拒**，會建出 `Movies2` 指向同一路徑。
  冪等只能靠呼叫端先列。plan §9.4 第 4 步已補。
- 2026-09-07 票 06：`LibraryOptions.TypeOptions[]` 只給 `MetadataFetchers` 而省略 `ImageFetchers`，
  後者被存成**空陣列**，該類型從此不抓圖。所以只有 metadata fetcher 是設定值，image fetcher 取自
  `GET /Libraries/AvailableOptions`（政策 `FirstTimeSetupOrDefault`，精靈期間匿名可讀）。
  plan §9.4 第 4 步與 brief §20.7 已補。
- 2026-09-07 票 06：`POST /Library/VirtualFolders/Paths` 目錄不存在回 **404**、同一條路徑送兩次會出現
  重複的 location。所以先建目錄（新增 `adapters/fs.py` 與 `PathSettings.library_root`）、先看 `Locations`。
  plan §9.5 已補。
- 2026-09-07 票 06：初始精靈跑完之後 `/Library/VirtualFolders` 就要管理員憑證，所以**重按 bootstrap 時
  要先登入再列媒體庫**。plan §9.4 第 4 步已補。
- 2026-09-07 票 06：新增 `ServiceBusyError`（503）。Jellyfin 重啟後每一支端點都會有一段時間回 503，
  「還在載入」與「壞了」必須分得開；重啟當下連線還會直接被切，兩種都要當成「繼續等」。plan §8.1 已補。
- 2026-09-07 票 06：bootstrap 是一個可能跑好幾分鐘的請求。**進度不另開通道**：每一步在做之前把自己
  寫成 `running` 並 commit，前端輪詢 `GET /api/setup/jellyfin`。plan §2.1、§6 已補。
- 2026-09-07 票 06：plan §6 原本寫的 `POST /setup/jellyfin/install-mergeversions` 與
  `/add-library-path` 改成 `/plugin` 與 `/libraries/paths`，另加 `POST /setup/jellyfin/connect` 與
  `GET /setup/jellyfin`。已回寫 plan §6。
- 2026-09-07 票 06：brief §20.7 原本寫「`POST /Startup/RemoteAccess` 只有 `EnableRemoteAccess`，
  沒有 `EnableAutomaticPortMapping`」。10.11.11 的 schema 其實有後者（Berth 仍只送前者）。已更正。
- 2026-09-07 票 06：CONTEXT.md 補上 **Jellyfin Library**、**Library root**、**Berth path**、
  **Step status** 四條，並把 Library Route 的 `_Avoid_: library（程式碼中）` 說清楚——那條規則說的是
  「不要用 `library` 指 Route」，而 `library` 正是 Jellyfin 那一端媒體庫的名字。
- 2026-09-07 票 06 code-review：**`pnpm exec tsc --noEmit` 其實什麼都沒檢查**。根 `tsconfig.json` 是
  `files: []` + project references，不帶 `-b` 就是空的 program。正確指令是 `pnpm typecheck`
  （`tsc -b --noEmit`）。換成它之後立刻抓到一個真的型別錯誤（動態組出來的 i18n key）。
- 2026-09-07 票 06 code-review：`i18next.d.ts` 補上 `strictKeyChecks: true`。沒有它，認不得的 key
  只會在畫面上原樣印出來而編譯不吭聲——這一票就踩到（`en` 有而 `zh-Hant` 沒有的 key 一路過關）。
  動態組 key 的地方改成 `satisfies Record<JellyfinStep, string>` 的查表。
- 2026-09-07 票 06 code-review：**「加入 Berth 路徑」失敗變成一條 `failed` 的步驟，不是 HTTP 500**。
  原本只 catch `StepFailedError`，`ensure_directory` 的 `OSError` 與 client 的 `ServiceError` 會冒成
  500，畫面什麼都看不到——而「目錄建得出來但 Jellyfin 看不到」正是 brief §16.4 那句「哪個容器少了
  哪個掛載」最典型的失敗。
- 2026-09-07 票 06 code-review：`POST /System/Restart` 有時在回應送出去之前就把連線切了，那是重啟
  開始了的樣子而不是失敗；`Fake` 補上這個行為並加測試。
- 2026-09-07 票 06 code-review：套件內媒體庫的路徑與既有媒體庫的「Berth 路徑」原本是兩套算法，
  只因 `Movies`→`movies` 巧合一致。改成同一支函式，並加測試釘住三個套件內媒體庫的 `has_berth_path`。
- 2026-09-07 票 06 code-review：`_ACTIONS` 加上 import 時的完整性斷言——漏一步原本是使用者按下去
  才炸的 `KeyError`。
- 2026-09-08 票 07：**`setup_completed` 這個位元搬到 `GET /health`**。精靈跑完之後 `setup/*` 只有
  管理員讀得到，而「該畫精靈還是登入頁」必須在**還沒有人登入得了**的時候就決定得出來；不搬的話
  匿名開任何一頁都得先吃兩個 401 再靠錯誤路徑猜答案（playwright 實跑時看到的）。精靈未完成時
  `setup/*` 本來就整組匿名開放，所以這一個位元不多洩漏任何東西。plan §6、§7 已補。
- 2026-09-08 票 07：門禁做成 **middleware**（`api/gate.py`）而不是逐 router 的相依，理由是預設拒絕——
  新增端點什麼都不做就已經在門後。代價是**未知 `/api` 路徑匿名時回 401 而不是 404**，推翻票 02 的
  `test_unknown_api_paths_stay_json_404`（該測試已改；登入後仍是 404）。回應碼因此也不能拿來列舉端點。
- 2026-09-08 票 07：`setup/*` 在精靈完成後從「一律 401」改成「未登入 401、非 admin 403」。plan §6 已改。
- 2026-09-08 票 07：`ServiceClientFactory` 與 `SetupProbes` 從 `services/setup.py` 移到
  `services/clients.py`。理由是 `services/auth.py` 只為了一個 Protocol 去 import 精靈模組是錯的耦合；
  `clients.py` 本來就是「要連哪一台、用什麼憑證」的家。沒有留相容匯出。
- 2026-09-08 票 07：`JellyfinAuth` 新增 `name`（`User.Name`）。顯示名取自 Jellyfin 而不是使用者打進
  表單的字串——大小寫以伺服器那一端為準。plan §8.2 未提及此欄位，屬新增而非推翻。
- 2026-09-08 票 07：session 壽命 30 天、**絕對到期不滑動續期**，token 存 SHA-256 雜湊（token 本身是
  256 bit 亂數，沒有字典可查，用慢雜湊只會讓每個請求變慢），過期的列在下一次被用到時就地刪掉，
  不等背景工作。brief 與 plan 原本都沒寫壽命，已補進 plan §2.1。
- 2026-09-08 票 07：cookie **刻意不設 `Secure`**。自架幾乎都是區網的純 HTTP 位址，設了 cookie 根本
  存不下來；防線是 httpOnly + `SameSite=Strict` + CSRF 標頭，HTTPS 交給前置代理。plan §6 已寫。
- 2026-09-08 票 07：**TanStack Router 的 `validateSearch` 刪不掉父路由沒宣告的 search 參數**
  （實測 1.171）——根路由沒有宣告任何 search，所以原始的 `?redirect=https://evil.example` 會越過子
  路由的驗證直接到達頁面。open redirect 的清洗因此做在**用它的地方**（`LoginPage.destination()`），
  不是 `validateSearch`。這是前端測試抓到的，不是推理出來的。
- 2026-09-08 票 07 `/impeccable shape 登入頁`：**不畫泊位板**——泊位板講的是精靈那四個泊位，登入時
  一個都還沒開始，搬過來只是把同一組色塊當壁紙。改成單一「登船口」窗格（`BTH 0`），
  `my-auto` 置中而不是 `items-center`（矮螢幕上 flex 置中會把上緣切掉且捲不回去）。
  shape brief 在 `.scratch/m0/login-shape.md`。
- 2026-09-08 票 07 `/impeccable shape 登入頁`：**不顯示 Jellyfin 的位址與版本**（使用者決定）。
  這一頁匿名可達，內部主機名不該送給沒登入的人；畫面上只留一句「Berth 沒有自己的密碼」，
  它一次解釋了帳密從哪裡來、為什麼沒有註冊、以及為什麼 Jellyfin 掛掉時誰都進不來。
- 2026-09-08 票 07：頁首的角色用**中性色塊**（`bg-deck`）而不是四個信號色之一。角色不是狀態，
  借用信號色會讓「每個顏色只有一個意思」這條規則破掉。角色要看得見，`user` 才知道自己為什麼
  沒有「設定」那顆按鈕，而不是以為壞了。
- 2026-09-08 票 07：「工作階段已過期」只在**這一輪之前畫面上就有人**時才說（前端快取裡有 `me`）。
  一個 401 分不出「過期」與「從來沒登入過」，對第一次來的人說「已過期」是騙他。
- 2026-09-08 票 07 code-review：**TanStack Query 的 `ensureQueryData` 只要快取裡有值就直接回，
  不會重抓**（實測 query-core 5.102，`staleTime: 0` 也不管用）。門禁用它的話，session 在使用中
  失效之後每一次前端導航都拿舊的 `me` 放行，永遠導不到 `/login`。改用 `fetchQuery`；回歸測試
  先驗過在舊寫法下是紅的。
- 2026-09-08 票 07 code-review：**FastAPI 的 422 會把收到的值原樣回傳**——`POST /auth/login`
  少一個欄位時，pydantic 的 `input` 放的是**整份 body**，密碼就這樣回到回應裡。新增
  `api/errors.py` 把 `input` / `ctx` 從 422 剝掉（掛在 app 上，下一個收密碼或 API key 的端點
  不必記得這件事），`LoginIn` 的欄位改成有預設值，缺欄位走 401 而不是 422。
- 2026-09-08 票 07 code-review：`setup/*` 的規則原本一半在門禁的白名單、一半在 router 的相依，
  於是 `/api/setup` 底下**新掛的 router 預設是匿名的**。整條規則搬進門禁，`require_setup_open`
  刪除。plan §6 的措辭已經是搬完之後的樣子。
- 2026-09-08 票 07 code-review：門禁從 `BaseHTTPMiddleware` 改寫成**純 ASGI middleware**。
  前者會把回應整個收進記憶體再送出去，plan §6 的 `GET /events/stream`（SSE，M1）在它底下就
  不是串流了。純 ASGI 沒有這個問題，程式碼也沒有比較長。
- 2026-09-08 票 08：**`POST /api/v1/indexer` 在存之前會先連一次那個站**，連不上回 400 加逐條理由
  而且什麼都不建立（`?forceSave=true` 也一樣）。所以「逐站驗證」不是 plan §9.3 原本寫的
  「新增之後再 `indexer/test`」，而是新增那一支本身；`indexer/test` 留給已經存在的站（重按時用）。
  plan §8.4、§9.3 第 5 步與 brief §20.7 已改。實測十個站五成五敗。
- 2026-09-08 票 08：Prowlarr 的介面登入（brief §16.3）一起做了——票面沒有這一條，使用者決定納入。
  它是自己一條纜繩 `prowlarr_login`，**不與既有路徑的 `prowlarr` 同名**：同名會讓「第 5 步做完了沒」
  把一條永遠存在的憑證步驟當成「至少接上了一個站」，十站全失敗也放行。
- 2026-09-08 票 08：**套件內 Prowlarr 的 API key 在第 2 步探測時就寫進 `settings.services.indexer`**。
  它只有唯讀掛載讀得到，不存的話第 5 步會拿空字串去打真的 Prowlarr。使用者貼過的值優先。plan §9.3 已補。
- 2026-09-08 票 08：qBittorrent 設過密碼、Prowlarr 加過索引站之後，那個服務的判定釘住不再重探
  （`ServiceProbe.configured`）。判定規則是「免密可進 / 一個索引站都沒有 → 套件內」，而這兩件事
  正是 Berth 自己剛做掉的。`configured` 的意思因此從「使用者填的」擴成「重探會說謊的」。
- 2026-09-08 票 08：TMDB 的內建憑證用 v4 的 read access token（走標頭，不進網址也就不落在 log 裡），
  但覆寫欄位**兩種形狀都收**——TMDB 的帳號頁同時發 v3 key 與 v4 token，認形狀比多一個設定項好。
  plan §8.3 已改。
- 2026-09-08 票 08：`app/setPreferences` 收的是表單裡一個叫 `json` 的欄位，不是 JSON body；
  `web_ui_password` 只寫不讀，所以「密碼設過了沒」只能比對 Berth 自己上一次寫下去的值。plan §8.1 已補。
- 2026-09-08 票 08 code-review：**路徑鍵的差異比對要正規化尾斜線**。4.4.5 把設進去的 `/data/x`
  讀回來寫成 `/data/x/`，照字面比的話那兩個鍵在 4.4 上永遠「不同」，每次重按都重寫一次同樣的值，
  「重按結果一致」就破了。
- 2026-09-08 票 08 code-review：qBittorrent 的密碼與 Prowlarr 的登入都改成**就地攔下例外**。
  原本它們的失敗會冒到整個命令的 except，把前面五個鍵 / 十個站的結果一起丟掉——而那些事已經做完了。
- 2026-09-08 票 08 code-review：`POST /setup/indexers/apply` 對既有索引站回 422。UI 在那個狀態下
  不給按鈕，但端點本身也要擋——brief §16.4 的紅線是「既有服務只做檢查」。
- 2026-09-08 票 08 code-review：四個泊位各自複製一份 `StepView` 與 `_message`，收斂成
  `services/steps.py`。形狀本來就是同一個：`SetupStep` 是它存下來的樣子，`StepView` 是讀出來的樣子。
- 2026-09-08 票 09：`POST /setup/routes/from-libraries` 改成 `GET /setup/routes` + `POST /setup/routes` + `POST /setup/complete`。plan §6 已改。理由是這一步要先讓使用者看到媒體庫清單與上一輪的檢查結果，與其他泊位「GET 看現況、POST 做事」的形狀一致。
- 2026-09-08 票 09：plan §9.5 的「檢查三」拆成兩條纜繩——`probe_visible`（Jellyfin `Environment/ValidatePath` 看得到探測檔）與 `hardlink`（`link()` + 同 inode），連同 `category`、`download_path`、`library_path` 共五條，前一條失敗就不跑下一條。理由是這兩件事的修正片段不同（jellyfin 少掛載 vs 兩個目錄是不同掛載），混成一條就說不出是哪一種。plan §9.5 已改寫成五項，`RouteCheck` 是它的封閉值集合。
- 2026-09-08 票 09：**硬鏈接的方向照 brief §4.4**（在 `complete/<slug>` 建暫存檔 → `link()` 到 Route 目標），不是 plan §9.5 原本寫的「在 Route 目標寫探測檔再從 complete 鏈接」。理由是這個方向與 M1 入庫時真正要做的操作一模一樣，連 fs adapter 的路徑逃逸防線都一起測到了。
- 2026-09-08 票 09：第 7 步要**每一條 Route 都綠燈**才走得到第 8 步（不是「至少一條」）。紅的那條 Route 送單一定失敗（brief §4.4），放行等於讓使用者帶著一個已知壞掉的目的地開始用。plan §9.3 第 7 步已補。
- 2026-09-08 票 09：既有 Jellyfin 的劇集媒體庫可以挑 `standard` / `anime` profile（plan 只寫了套件內的 anime）。理由是 profile 決定 M1 的命名與解析，預設全部 standard 會讓動漫媒體庫一開始就是錯的；電影類型不問。
- 2026-09-08 票 09：重跑第 7 步時**沒被勾到的 Route 會刪掉**——精靈裡的勾選就是「我要哪幾條 Route」。M0 沒有任何東西引用 route_id，M1 有了 Job 之後這條要改成軟處理，屆時在設定頁逐條管理。
- 2026-09-08 票 09：`SetupLibrary` 新增 `item_id`（Jellyfin virtual folder 的 `ItemId`），Route 記它而不是只記名字。舊資料沒有這個欄位所以是選填。
- 2026-09-08 票 09：fs adapter 的每個寫入函式都要 `roots` 參數，不在其中就丟 `PathEscapeError`——「寫進 library 的東西一定在某個 Route 的 target_path 底下」因此是型別上的事實而不是紀律。plan §8.6 已改。
- 2026-09-08 票 09：`POST /Environment/ValidatePath` 看得到回 204、看不到回 **404**，所以 adapter 把 404 翻成 `False` 而不是例外（查核 Jellyfin master 的 `EnvironmentController.cs`）。`ValidateWritable` 不送真——那會讓 Jellyfin 自己在媒體庫目錄裡建暫存檔。已補進 brief §20.7。
- 2026-09-08 票 09：`torrents/createCategory` 的表單鍵是 `category` / `savePath`，同名已存在時回 409（查核 qBittorrent master 的 `torrentscontroller.cpp`）。冪等靠呼叫端先讀 `torrents/categories`；已存在但 save path 不同時**回報衝突不覆寫**（改 category 路徑會搬走該分類所有 torrent）。已補進 brief §20.2。
- 2026-09-08 票 09：檢查一同時 `stat` qBittorrent 的**全域** save path。那條路徑在第 4 步就被設成 Berth 的 complete 根目錄，所以它看不到等於掛載真的少了。
- 2026-09-08 票 09：精靈完成後前端**就地改掉 `GET /health` 快取裡的 `setup_completed`** 再導航。守衛走的是 `ensureQueryData`（快取裡有值就不重抓，票 07 已記過一次），只作廢的話下一次導航仍拿到 `false`，人會被彈回一個已經回 401 的精靈頁。
- 2026-09-08 票 09：`scripts/fake_setup_server.py` 把 `settings.paths` 指到該次的暫存 `DATA_ROOT`。第 7 步會真的建目錄、寫探測檔、呼叫 `link()`，指著容器裡的 `/data` 在本機跑不起來。另加 `--scenario unmounted` 演「Jellyfin 少了掛載」。
- 2026-09-08 票 09 自審：qBittorrent 登入失敗改成落在每個 Route 的 `category` 纜繩上（原本會讓整支端點回 500，還漏掉一個沒關的 client）。帳密不對要看得出是哪個 Route 卡住、原文是什麼。
- 2026-09-08 票 09 code-review：**檢查一原本等於沒檢查**——`category` 那一步先 `ensure_directory` 建好目錄，`download_path` 再 `stat` 同一個 Berth 自己算出來的字串，必過。改成 `stat` **qBittorrent 回報的**那條 category save path 與全域 `save_path`；後者讀不到（`app/preferences` 失敗或空值）也改成這一條紅燈，原本被吞掉之後這一步照樣變綠。
- 2026-09-08 票 09 code-review：**檢查二改成向 Jellyfin 現查**媒體庫，不吃第 3 步存進 `settings.setup.jellyfin` 的快照。第 3 步與第 7 步之間使用者可能在 Jellyfin 那邊改了路徑或刪了媒體庫，而這一步要證明的正是「現在這台 Jellyfin 說的路徑，Berth 看得到」。plan §9.5 的措辭一併改回「向 Jellyfin 讀」（先前為了配合實作弱化過）。
- 2026-09-08 票 09 code-review：plan §8.6 原本寫「每個會寫東西的函式都要 `roots`……是型別上的事實」——`ensure_directory` 就沒有，這句話對不上它文件的程式碼。改成「凡是把**檔案**放進去的函式都要」，並寫明 `ensure_directory` 建的是 Berth 自己的根目錄。
- 2026-09-08 票 09 code-review：完成頁的 Route 狀態改讀 `route.health`，不再寫死綠色——那一頁目前只在全綠時出現，寫死等於把「這個假設哪天不成立」變成畫面說謊。健康 → 信號的對照表 `ROUTE_SIGNAL` 兩個元件共用。
- 2026-09-08 票 09 code-review：profile 的 radio `name` 從 profile 值改成媒體庫名。原生 radio 群組靠 `name` 分組，兩個劇集媒體庫共用一個名字會讓方向鍵在它們之間跳，螢幕閱讀器也把兩組唸成同一組。
- 2026-09-08 票 09 code-review：`_berth_path` 從 `services/jellyfin` 匯出成 `berth_path`，`services/routes` 不再自己算一次同樣的字串——這一票本來就是為了不讓 slug 算法分岔才把它抽出來的。前端的 `RouteHealth` 型別改名 `RouteHealthStatus`（與後端存檢查結果的 `RouteHealth` 撞名），`Pick` 改名 `LibraryPick`（撞 TS 內建型別）。
- 2026-09-08 票 09 code-review：`PathFacts.is_dir` 拿掉（只有測試在讀）；`free=` 用 key=value 形狀而不是英文散文 `GB free`；`routes.build.bundled` 與 `.selected` 兩個一字不差的 key 收成一個；套件內剖面與按鈕的數字只算建得了 Route 的媒體庫（`supported`），不再把音樂之類的媒體庫算進去。
- 2026-09-08 票 09 code-review：既有 Jellyfin 的勾選只送得出「目標真的是那個媒體庫的路徑之一」的選擇。伺服器本來就用同一條規則擋（422），但那時候畫面只說得出「請求沒走完」；最典型的觸發是「加入 Berth 路徑」失敗之後選了那條不存在的路徑。
- 2026-09-08 票 10：健康狀態存進**新的 `settings.health` 分組**，不是 plan §3.2 原本寫的
  `settings.services.*`。理由是那幾組是使用者設定的連線資訊、整組覆寫是它們的常態
  （`write_settings`），把迴圈每 5 分鐘改一次的狀態混進去，兩邊會互相蓋掉。這同時結掉票 02
  留下的「`services.*` 的最後健康狀態延到票 10 定形狀」。plan §2.1、§3.2 已改。
- 2026-09-08 票 10：`health_checker` **沒有逐服務的間隔退避**，推翻票面「各服務獨立 try/except
  與退避」的後半。理由是退避的目的是不要打爆服務，而 5 分鐘一次的檢查本來就打不爆任何東西；
  退避只會延後「服務回來之後自動變綠」這條驗收。隔離靠的是逐項 try/except 加 adapter 的 5 秒
  逾時，連續失敗次數仍然記錄並顯示。plan §3.2 已改。
- 2026-09-08 票 10：迴圈**每 30 秒醒一次、上一輪滿 5 分鐘才真的跑**，而且精靈跑完之前什麼都
  不做。兩層的理由是精靈剛按完「完成」的那一刻——如果醒來的間隔就是檢查的間隔，使用者會對著
  一個空的健康頁等五分鐘。plan §3.2 已補。
- 2026-09-08 票 10：plan §6 的 settings 群組改成 `GET /settings/services`、
  `POST /settings/services/{kind}/test`、`GET|POST /settings/qbittorrent/diff|apply`，
  **不做 `PUT /settings/{group}`**。理由是位址與憑證仍然在精靈裡改（精靈跑完之後它就是設定
  入口，plan §6 本來就這麼寫），複製四份連線表單只會讓兩份規則分岔。plan §6 已改。
- 2026-09-08 票 10：`/api/settings/*` 的 admin 門禁放在**門禁 middleware**（`ADMIN_PREFIXES`）
  而不是 router 的相依，與票 07 把 `setup/*` 搬進門禁同一個理由：底下新掛的端點什麼都不做
  就已經在同一道門後面。
- 2026-09-08 票 10：新增 `/health` 路由（plan §7 的清單原本沒有它，只有 brief §13 的「健康與
  問題」頁），`/` 在 M1 的探索頁之前先導向它。plan §7 已補。
- 2026-09-08 票 10：`create_app(clients=...)` 與 `get_client_factory` 改從 `app.state` 取。
  理由是背景迴圈不經過 FastAPI 的相依，`dependency_overrides` 換不掉它要用的 client——
  演練用的 `scripts/fake_setup_server.py` 必須換得掉，否則那台假 Berth 的迴圈會去打真的主機名。
- 2026-09-08 票 10：**Route 那一項與服務不獨立**。它的檢查要問 qBittorrent 與 Jellyfin，
  所以那兩台掛掉時 Route 一起紅——那是事實不是連坐。票面「其餘三項不受影響」字面上只對索引站
  成立（沒有人依賴它），所以 playwright 的紅燈情境用的就是索引站。
- 2026-09-08 票 10：索引站沒接上時是 `unknown` 而不是紅燈——第 5 步可以跳過（plan §9.3），
  跳過的人不該永遠看到一盞紅燈。`ServiceHealth.configured` 就是這件事。
- 2026-09-08 票 10：qBittorrent 的**設定漂移用 `assigned`（需要你）而不是紅色**。那台服務
  還在動，紅色只代表阻擋（direction contract 的法定色規則）。CONTEXT.md 新增 **Drift** 詞條。
- 2026-09-08 票 10：前端共用件從 `setup/` 移到 `components/`（`StepLine`、`steps`、
  `routeChecks`、泊位板的版面與 `BERTHS`），跨頁的 API 型別移到 `api/schemas.ts`（後端對應
  新增 `api/schemas.py`）。理由是精靈、健康頁與設定頁講的是同一批東西；`RouteView` 從
  `api/setup.ts` 匯出會讓「Route 是精靈的東西」這個誤解留在型別上。測試的共用安排同樣從
  `test_setup_routes.py` 抽到 `tests/integration/arrange.py` 與 `conftest.py`，
  `web/src/test/setupStatus.ts` 改名 `fixtures.ts`。
- 2026-09-08 票 10：**開頁不自動重測**（使用者決定）。那一輪檢查會在 qBittorrent 建 category、
  在媒體庫寫探測檔再刪掉，不該是「重整頁面」的副作用；要現在的答案就按「立即重測」。
- 2026-09-08 票 10：`display: flex` 會吃掉 `<summary>` 的三角形，所以 Route 那一列的展開狀態
  用模板字自己說（`展開檢查` / `收起`）。實測沒有這一句時收起來的列看不出它按得開。
- 2026-09-08 票 10 code-review：**逐 Route 也要有最後成功時間**。票面寫的是「每個服務與每個
  Route 的狀態、最後成功時間」，而 `RouteHealth` 原本只有逐項檢查結果。已補
  `checked_at` / `last_ok_at`（失敗時留住上一次成功的時間），畫面在展開的 Route 裡顯示。
- 2026-09-08 票 10 code-review：**迴圈跑第一輪之前，三個已接好的服務被說成「尚未接上」**。
  `ServiceHealth.configured` 預設是 `False`，而前端先判它——精靈按完完成到第一個 tick 之間
  （最長 30 秒）畫面會叫使用者「到設定精靈接它」。判定順序改成「沒有 `checked_at` → 尚未檢查」
  優先。
- 2026-09-08 票 10 code-review：**漂移的「到服務設定」連結對一般使用者是死路**（守衛會把他
  彈回健康頁）。改成只給 `admin`，與頁首的設定入口同一條規則。
- 2026-09-08 票 10 code-review：差異表的「這一鍵被改過」原本只靠紅字，違反 plan §7 與
  PRODUCT.md 的「狀態不只靠顏色」。補上「已改」色塊。
- 2026-09-08 票 10 code-review：`ROUTE_SIGNAL` 與 `ROUTES_SIGNAL` 逐字相同、`COMPOSE_SERVICE`
  是恆等映射（CONTEXT.md 已定「服務名字串同時是 compose 服務名」）、四個泊位的號碼與名字兩份，
  全部收成一份；動態組出來的 `routes.health.*` key 改成查表（與票 06 的決定一致）。
  前端型別 `RouteHealthStatus` 改名 `HealthStatus`（與後端 enum 同名，它現在同時給服務用），
  匿名端點那個 ok/degraded 改名 `OverallStatus`。
- 2026-09-08 票 10 code-review：`Timestamp` 沒有值時說「沒有紀錄」而不是「尚未檢查」——後者
  與那一項的狀態標籤同字，紅著的服務也可能從來沒成功過，兩件事不該共用一句話。
- 2026-09-08 票 11 驗收：**`deploy/entrypoint.sh` 的 `take_ownership` 參數順序寫反**，`/data` 那一次
  展開成 `chown /data berth:berth berth:berth`，所以「空的媒體根接手擁有者」（plan §9.1、票 03 的決定）
  從來沒有真的執行過。Windows 上量不到——那裡 `chown` 本來就會失敗且不影響寫入；乾淨的 Linux 宿主上
  Docker 新建的 `/data` 是 `root:root`，Berth 連 `/data/library` 都建不出來。同一輪讓腳本改讀
  `CONFIG_ROOT` / `DATA_ROOT`（它本來寫死，與 Berth 自己讀的變數對不上），回歸測試
  `tests/unit/test_entrypoint.py` 用替身 `chown` 記錄參數。
- 2026-09-08 票 11 驗收：**qBittorrent `auth/login` 的成敗形狀跨大版本不同**，brief §20.2 原本只寫了
  4.x 的那一種。實測 4.4.5 成功 `200` + `Ok.` / 失敗 `200` + `Fails.`；5.2.3 成功 `204` 空 body /
  失敗 `401`。原本「不是 `Ok.` 就是失敗」的判定讓**每一套用預設 image 的部署**，qBittorrent 那一項
  健康檢查永遠紅著——而且只有在精靈第 4 步設過密碼之後才看得到（在那之前健康檢查不呼叫 `login`）。
  判定改成只認 `Fails.`；免密白名單上的來源在 5.x 一律回 204，那是成功。brief §20.2、plan §8.1 已改，
  兩個版本的回應錄成 fixture。
- 2026-09-08 票 11 驗收：**Prowlarr 的 `indexer/schema` 不能用探測的 5 秒逾時**。容器剛起來的第一次
  呼叫要讀進 627 份 Cardigann 定義再組出 5.6 MB 回應，Windows 的 9p bind mount 上實測 **9.42 秒**
  （第二次 0.34 秒），精靈第 5 步因此在乾淨部署上直接失敗、退回「接入你自己的索引站」表單。
  這一支改用自己的 `SCHEMA_TIMEOUT_SECONDS = 60`。brief §20.7 已補。慢的儲存（NAS）只會更久。
- 2026-09-08 票 11：**「乾淨 Linux 宿主」用的是 Docker Desktop Linux VM 上的 ext4 持久磁碟**
  （`/mnt/docker-desktop-disk`），不是另一台實體 Linux，也不是 NAS。與票 04 同一個限制，brief §20.6
  的兩條仍然保留。WSL 的 Ubuntu 沒有開 Docker Desktop 整合，開它要動使用者的 Docker Desktop 設定，
  沒有為了這件事去改。
- 2026-09-08 票 11：票 01 延後的「型別感知 eslint 規則」只開 `no-floating-promises` 與
  `no-misused-promises` 兩條，不開整包 `recommendedTypeChecked`。整包在這個 repo 上抓到 36 條，
  全部是 TanStack Router 的 `throw redirect(...)`（框架慣用法）與測試裡 `RequestInit.body` /
  `JSON.parse` 的型別噪音，沒有一條是真的缺陷；而那兩條正是票 01 寫下的延後理由，開了之後抓到兩個
  真的漏 await（兩個健康頁的 `invalidateQueries`，已標成刻意的 `void`）。
- 2026-09-08 票 11：票 01–10 的 Comments 裡剩下的「留給後續」逐條過完，該延後的寫進 plan §11 而不是
  另開票——plan §11 本來就是 `/to-tickets` 的輸入，M1 開頭拆票時自然會被拆到。新增 T1.9（openapi
  型別產生器與 CI 過期檢查、帶 job id 的結構化日誌、Route 設定頁的「一個媒體庫多條 Route」與明確刪除），
  §11.3 補兩條（TVDB 插件警告成為 Issue、磁碟空間門檻）。
- 2026-09-08 票 11 `/impeccable critique`：兩個隔離的子代理（設計審查 + 檢測器與瀏覽器實測）。
  機械檢測器 31 個元件 0 findings；Nielsen 十項 22/40，最強是「診斷與復原」4 分（紅燈頁給的是
  排查順序而不只是錯誤），最弱是「使用者控制與自由」1 分（精靈沒有出口）。設計專屬性判定為
  「為這個產品寫的」。報告存在 `.impeccable/critique/2026-09-08-m0-ui.md`。
- 2026-09-08 票 11 polish：**`.label` 不可以套在機器字串上**。它對拉丁文 `uppercase`，套在 API
  端點上會印出 `POST /LIBRARY/VIRTUALFOLDERS`——而同一畫面右欄印的是正確的那一個。中文版
  `text-transform: none` 所以看不到，這是「英文是一等公民」在實作上第一次被證偽。`CutawayRow`
  新增 `code` 變體，DESIGN.md 記下這條規則。
- 2026-09-08 票 11 polish：泊位板窄版從 carousel 改回 shape brief 寫的 **2×2**。carousel 讓
  BTH 3 與 BTH 4 完全在畫面外，而這塊板的用途就是「一眼看出哪一格紅了」；捲動容器同時是一個
  沒有名字的 Tab 停留點。目前泊位另加 `aria-current="step"` 與 inset 底線（用 currentColor，
  不引入第五個顏色）。
- 2026-09-08 票 11 polish：**精靈跑完之後它就是設定入口**（plan §6 本來就這麼寫），所以它需要
  出口。新增 `?berth=1..4` 深連結（設定頁三張卡片各連自己那一格，原本三條都連裸 `/setup`）、
  頁首的返回鍵、以及一句「不會重跑一次靠泊」。`berth` 由 `routes.tsx` 讀了再當 prop 傳給
  `SetupPage`——那個元件的測試刻意不掛 router。
- 2026-09-08 票 11 polish：`status.skipped`（「已經是這樣」）是**冪等步驟**的字，被借去當「你選擇
  之後再做」的徽章會說謊。新增 `source.deferred`。索引站那一節原本連徽章都沒有，按下「之後再說」
  畫面毫無變化——兩個審查代理與驗收本人都以為按鈕壞了。原本的測試只驗「請求送出去了」，
  已改成同時驗畫面。
- 2026-09-08 票 11：M0 UI 的 `critique` / `audit` / `polish` 收尾之後由 impeccable 產生 `DESIGN.md`
  （票 05 就記過它要在這一票才寫，因為它依實際做出來的東西寫，不是依打算做的東西）。
- 2026-09-08 票 11 code-review：**`entrypoint.sh` 不可以讀 `CONFIG_ROOT` / `DATA_ROOT`**。
  同名兩義——那兩個名字在 `deploy/.env.example` 裡是**宿主**路徑（`./config`、`./data`），在
  image 的 ENV 裡才是容器路徑。compose 目前不注入它們所以安全，但誰用 `--env-file .env` 起容器，
  接手就會靜默指到錯的目錄。改成只有測試會覆寫的 `BERTH_CONFIG_DIR` / `BERTH_DATA_DIR`
  （同票 03 `BERTH_QBITTORRENT_CONF` 的先例）。
- 2026-09-08 票 11 code-review：`login()` 改成只認 `Fails.` 之後，順帶失去了「連到的不是
  qBittorrent」那道防線——位址填錯打到反向代理時它很可能回 `200` 加一頁 HTML。成功只有兩種
  形狀（空 body 或 `Ok.`），其餘 2xx 判 `ProtocolMismatchError`，補了測試。
- 2026-09-08 票 11 code-review：泊位順序一度散在四個檔案（`BERTHS`、`BERTH_CODE`、`BERTH_STEP`、
  `SERVICE_BERTH`），而 `berths.ts` 的檔頭正好寫著「各寫一份遲早會分岔」。「哪一格是哪個服務」
  收回 `BERTHS.slot`，`SLOT_SERVICE` 與 `SERVICE_BERTH` 刪除，改由 `berthNumberOf()` 導出；
  步驟號是精靈才有的事，留在 `SetupPage`。
- 2026-09-08 票 11 code-review：plan 補三處與實作對不上的敘述——§8.4 沒寫 Prowlarr 的兩個逾時、
  §8.1 寫「403 記錄並退避」但實作沒有退避（4.4.x 封 IP 也回 403，會被顯示成「帳密不對」，
  已列進 T1.9）、§10 的測試層表沒有 `deploy/` 的 shell 腳本那一層（票 03 起就有兩支）。
- 2026-09-08 拆票：brief §10 的【研究】「TVDB 作為 anime profile 的季集來源」**改在 M1 票 01 做，不是拆票前**。
  推翻 brief §10 與 §20.6 的「必須在 M1 拆票前定案」。理由是那條實驗要打兩家 API、抽 10 部動漫量化
  換算失敗率，是一個完整的 session，而它的結論只影響三張票（03 `media` 欄位、05 fixture 形狀、
  06 `map_episode`）；把它排成有 blocking 邊的票 01，決定仍然在任何程式碼碰 `media` 之前落地。
  代價是票 03 / 05 / 06 可能要依結論修訂一次，已寫進票 01 的驗收。
- 2026-09-08 拆票：plan §11.2 的 T1.9（M0 帶過來的技術債）**拆散到四張票**而不是一張——openapi 型別
  產生器成為票 02（prefactor，排在所有新端點之前，「make the change easy, then make the easy change」）、
  結構化日誌帶 job id 進票 09（Job 在那裡誕生）、qBittorrent 的 403 分辨進票 10（poller 是會連續登入
  的那一個）、Route 設定頁成為票 14。理由是那四條的前提各不相同，綁成一張票會讓三條等第四條。
- 2026-09-08 拆票：T1.1 拆成票 03（探索頁）與票 04（Media 詳情），T1.5 拆成票 05–07（harness 與發佈名
  解析 / 季集對應與信心 / 命名與 Plan），T1.6 拆成票 11（planner_runner）與票 12（importer + ledger），
  T1.7 的 UI 拆散到票 04、08、10、13 各自的頁面。理由是 M0 的經驗——一張票碰兩個新頁面或兩個新模組
  就會超出一個 session；每一段都有自己的驗收數字（benchmark 的 `auto_correct`、頁面的 playwright 實跑）。
- 2026-09-08 拆票：`issues` 表與問題頁**留在 M2**，所以 M1 的「無主 torrent」（plan §3.2）與
  「Jellyfin 反查耗盡」（plan §3.2 `jellyfin_resolver`）先寫 event。推翻那兩處 plan 的字面。理由是
  Issue 這個載體要連同 Reconciler 與問題頁一起才有用（M0 票 10 已為「TVDB 插件警告」與「磁碟空間門檻」
  下過同樣的判斷），只為了兩個生產者先建表會讓 M2 再改一次形狀。
- 2026-09-09 票 01：brief §10 的【研究】結案為**維持 TMDB**，`media` 不加 `tvdb_id` / `episode_source`，不做 TVDB adapter。這條研究改在 M1 票 01 做，而不是 brief §20.6 原本要求的「M1 拆票前」—— 拆票時就已把它排成 M1 第一張票並讓票 03 / 05 / 06 等它，效果相同而不必在拆票流程外再開一輪。
- 2026-09-09 票 01：brief §10 的弱點對策改寫。原本寫「靠絕對編號換算 + review」，實測顯示絕對編號換算只影響 16% 的釋出、TMDB 在那一段只錯 4.4%；主要弱點是**檔名只有篇章名沒有季號**（佔失敗的九成）。plan §4.1 / §4.4 補上「篇章名 → 季號」與「最終季 → 最後一季」，plan §2.2 / §4.3 的快照補上各季 `name`。
- 2026-09-09 票 01：brief §20.3 兩處更正。（一）TMDB 的合併政策比原記載激進得多 —— 不只 split-cour，**獨立的連續季也在併**（咒術 3 季→1 季 59 集、Re:Zero 4 季→1 季 85 集、芙莉蓮 2 季→1 季 38 集、柯南 34 季→1 季 1213 集）。（二）**TVDB 的 absolute 會把 OVA 與劇場版也編號**（SPY×FAMILY 的劇場版 CODE: White 佔掉 absolute 38），所以 absolute ≠ 正篇第幾集，而字幕組數的是正篇。
- 2026-09-09 票 01：plan §4.4 的 180 天虛擬季門檻從「移植 AutoBangumi 的常數」升級為**有量測支持的決定**（180 天 8.0% vs 60 天 9.7%），並註明不要調小。
- 2026-09-09 票 01：實驗用 Sonarr 的 Skyhook 當 TVDB 資料來源（免 key），並對 thetvdb.com 網頁逐部驗過 10/10 一致。**但它不能寫進產品**（封閉自營、無 SLA、servarr 官方不支援第三方直打），已記在 brief §20.3。
- 2026-09-09 決定（使用者拍板）：**Berth 不內建任何 provider 的 API key**。TMDB 憑證改由使用者自己申請並填入，精靈第 6 步從「可跳過的覆寫」變成必填閘門。推翻 M0 票 08 的 `PROJECT_CREDENTIAL`（Seerr 的做法）與 brief §16 的「開箱即用」一角 —— 代價知情且接受。觸發點是票 01 更正「TVDB 授權」那條理由之後，發現兩個 provider 在「使用者自備 key」上本來就對稱。**程式碼與文件由新票 `02b-tmdb-user-key.md` 一起改**，在它落地之前 repo 維持現狀（不讓文件先跑到 repo 前面）。
- 2026-09-09 票 01 修正：研究文件 §5 把「TVDB 授權」寫成主要代價是**錯的**，已改。brief §20.3 早在 2026-09-07 就查證過 v4 key 免費自助、不帶 PIN 可讀，ToS 擋的只是「內建一把 key 發給所有使用者」，不擋「使用者自己申請一把填進 Berth」；後者與 TMDB 的做法對稱，在兩個 provider 之間不構成差異。決定不變（撐住它的是 0.4 個百分點、Jellyfin 同源、第二個 provider 的成本），但 §10 的理由與「回頭重看」第 4 條已據此改寫 / 撤銷。
- 2026-09-09 票 01：推翻票 01 自己的驗收條件「若維持 TMDB：票 03、05、06 不動」。實際改了三張票：03 與 05 解除 blocked-by（機械操作）；05 補「季號的全形羅馬數字」；06 補「篇章名 → 季號」「最終季 → 最後一季」「第二部分 / Part.2 當 cour 偏移」。理由是量測指出這三條合計佔失敗的九成，是比換 provider 大得多的槓桿，不寫進票就會連同這份研究一起被忘掉。票上保留原條文並註明偏離。
- 2026-09-09 票 02b：**「不內建 provider key」這個決定落地了**（票 01 那天記的「在它落地之前 repo 維持現狀」到此為止）。推翻 M0 票 08 的 `adapters/tmdb.PROJECT_CREDENTIAL` 與 brief §16.3 的「TMDB 那一列使用者不必自己做」，brief §16.3 現在明寫「唯一要離開 Berth 的一步是 TMDB 憑證」、§20.7 那一段從「沿用 Seerr 的專案級 key」改成「查證過那條路走得通，但本系統不走」。plan §9.3 的「第 5、6 步可跳過」縮成「可跳過的只有第 5 步」。README 多一節〈先申請一把 TMDB API key〉。代價是知情且接受的：**開箱即用缺了這一角**，而且 `api.themoviedb.org` 連不到的使用者現在走不完精靈。
- 2026-09-09 票 02b critique：**「停用主要按鈕」在同一個檔案裡第二次成為缺陷**。票 11 修過索引站的「之後再說」按下去畫面毫無變化；這一輪一度讓必填的「測試 TMDB」在欄位空白時停用，亮色主題下那顆按鈕對底色只有 1.03:1，而同一屏上方**可跳過**的那顆是滿版黃漆——閘門的動作比可跳過的動作安靜。規則寫進票：**按鈕永遠按得下去，說不行的是欄位自己**（`Field` 的 `error` prop 已經接好 `role="alert"` 與 `aria-describedby`）。
- 2026-09-09 票 03：**票 08 把一把真的 TMDB v3 key 當成「同形狀的假值」寫進 `test_adapter_contracts.py`**（`4660154`、`ddf6c26` 兩個 commit）。查證後那兩個 commit **從未推送**（`origin/main` 在 `ae1ad35`，本地 `main` 超前 18 個），所以它沒有公開過；先前一度判斷成「已對外可讀」是錯的，看 `git log --all` 把本地 commit 當成已推送。使用者決定**換 key、不重寫歷史**。`d91e839` 把字串換成 `0000…0003`，並把「秘密的假值照一張號碼表挑」寫進 `tests/fixtures/http/README.md`——那條規則現在管的不只是 fixture 檔，也管任何寫得出憑證形狀的測試。
- 2026-09-09 票 03：**`language` 換掉的不只是文字**。`trending/tv/week` 的 `en-US` 與 `zh-TW` 兩輪各 20 筆只有 17 筆相同（2026-09-09 實測）。所以清單一律以 `en-US` 那一輪為準，`zh-TW` 只當「這一部叫什麼、海報是哪張」的查表；反過來做會讓作品憑空消失。plan §8.3、brief §20.3 已補。
- 2026-09-09 票 03：**回應裡的 `popularity` 不是清單的排序依據**（`tv/popular` 首五筆是 583 / 440 / 692 / 417 / 398）。所以劇集與電影兩份清單合成一面牆時用**交錯**而不是照 `popularity` 重排——重排會得到第三種順序。plan §8.3、brief §20.3 已補。
- 2026-09-09 票 03：`{tv,movie}/popular` 的每一筆**沒有 `media_type`**（`trending` 與 `search/multi` 有），所以型別由端點決定、由呼叫端傳進解析器。brief §20.3 已補。
- 2026-09-09 票 03：`TmdbSettings` 新增 `image_base_url`，精靈第 6 步驗憑證時順手寫下。理由是 `configuration` 對同一把憑證是常數，每次探索都問一次是白花一個請求；欄位是空的時候（在這個欄位存在之前就跑完精靈的資料庫）才現查一次並補寫。plan §8.3 已補。
- 2026-09-09 票 03：探索的三支端點**失敗也回 200**，理由放在 `problem`（`credential_missing` / `credential_rejected` / `unreachable`）。推翻「錯誤走 HTTP 狀態碼」的直覺做法：一頁上有三個 feed，一個垮掉時另外兩個要照樣畫得出來，而前端只拿得到一個狀態碼就分不出「還沒填憑證」與「TMDB 連不上」——那兩件事的修法完全不同。plan §6 已補。
- 2026-09-09 票 03：`/` 不再導向 `/health`（票 10 的暫時安排到此為止），plan §7 的措辭已改。連帶把「登入後落到哪一頁」「非 admin 打 `/setup` 被送回哪裡」從 `/health` 改成 `/`，三個既有測試跟著改。
- 2026-09-09 票 03 實跑：**卡片牆不可以用「塗底 + `gap-px` 透出格線」畫線**。泊位板可以，因為它永遠是四格滿的；這面牆的格數由 TMDB 決定，只搜到一部作品時整排空欄會變成一塊灰色的板子。改成線由每一格自己的 `border-2` 畫。DESIGN.md 的 Don't 已補。
- 2026-09-09 票 03 實跑：**色塊不疊在圖像上**。「已追蹤」原本壓在海報左下角，實測發現讀不讀得出來取決於那張海報那一角剛好是什麼顏色——`deck` 在亮色主題是近白（壓深色海報很清楚），深色主題是中灰（壓深色海報幾乎消失）。改貼在卡片下方的標識帶（底是 `well`，實測 11.95:1）。DESIGN.md 新增 The Paint Needs A Painted Ground Rule。
- 2026-09-09 票 03：卡片**這一票不是連結**。`/media/:id` 要到票 04 才存在，點下去沒反應的格子比不能點的格子更糟。shape brief §6 原本寫「每一格是一個連結」，已在票的 Comments 記下由票 04 接手。
- 2026-09-09 票 03 code-review：**英文的 `{{count}} titles` 在一筆時說「1 titles」**。i18next 傳 `count` 時查的是 `_one` / `_other`，兩個都沒有就退回原鍵。本票的鍵改成兩個語言各自定義 `count_one` / `count_other`（中文兩個同字，`Translations<>` 要求鍵樹一致），傳固定值的 `tooShort` 改用 `{{min}}` 完全繞開複數。**其他頁面既有的同類鍵**（`health.routes.count`、`setup.detect.done`、`routes.build`）有同一個缺陷，不在本票範圍，記在票上留給 M1 UI 收尾的 `/impeccable audit`。
- 2026-09-09 票 03 code-review：**搜尋每停一次就把整面牆換成 12 格空位**，違反 shape brief §6 自己寫的「搜尋中不換掉上一輪結果」。改用 `keepPreviousData`，而且**回應帶著它自己的查詢字串**——留在畫面上的是上一輪的卡片，標題就必須跟著說上一輪的詞，否則那面牆會掛著新標題演舊結果。
- 2026-09-09 票 03 code-review：**憑證缺失時同一段話與同一條精靈連結出現兩次**（趨勢一次、熱門一次）。後端維持逐 feed 各回自己的 `problem`（「一個垮掉不影響另一個」要的就是這個），去重放在頁面那一層：兩個 feed 的理由相同時整頁只說一次。
- 2026-09-09 票 03 code-review：**令牌桶「全域」那一半沒被測到**——原本只測 `TokenBucket` 自己。補了「四支端點各真的呼叫一次 `acquire()`」與「兩個 client 拿到同一個 `_BUCKET`」兩條契約測試。
- 2026-09-09 票 03 code-review：`services/tmdb.py::_test` 原本偷偷改 `settings.image_base_url`，逼得 `verify_tmdb` 寫兩次設定；改成回 `(step, image_base_url)` 由呼叫端寫回。另外 `_decorate` 的逐欄手抄收成 `DiscoverItem.from_card()`、假憑證字串收進 `tests/conftest.TMDB_API_KEY`、前端測試改用共用的 `discoverWall()`。
