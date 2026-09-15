# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、session 紀錄、偏差與決定。

## 里程碑與閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| M0 | `.scratch/m0/issues/` | plan §1、§2、§9、§11.1；brief §16、§20.6、§20.7 | 已拆成 11 張票（2026-09-07）。§20.6 的實驗是票 04，排在 compose（票 03）之後；票 05 是第一張 UI 票，開頭跑 `/impeccable hooks on` 與 `init` |
| M1 | `.scratch/m1/issues/` | plan §3、§4、§5、§8、§11.2；brief §5、§6、§7、§20.1–§20.4 | 已拆成 15 張票（2026-09-08），票 01 做完後插入 02b（2026-09-09），共 16 張；票 13 之後插入 14b（2026-09-15，Jellyfin 12），共 17 張。票 01 是 brief §10 的 TVDB 【研究】，它決定 `media` 的欄位所以排最前；票 02 是 openapi 型別產生器的 prefactor；票 02b 拿掉內建 TMDB 憑證，排在 03 之前因為之後每張票都要有憑證才跑得動。解析器（票 05–07）先寫 fixture 與 harness 再逐階段實作，與 UI 那條線（票 03–04）並行，在票 08 匯流 |
| M1.5 | `.scratch/m1.5/issues/` | plan §11.2b；brief §12、§13、§19、§20.8；`docs/research/library-browsing.md` | 2026-09-15 使用者在票 13 之後拍板加入，排在 M1 驗收後、M2 前。brief §19 的四條待決已於 2026-09-15 定案；CONTEXT.md 的 **Inventory** 要跟著改定義 |
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
| 2026-09-09 | 04 Media 詳情 | `GET /api/media/{id}` + `track` + `refresh`：TMDB 詳情與各季各集快照（24 小時，過期自動重抓）、追蹤、預設 Route。**`folder_name` 在追蹤那一刻凍結**，之後 TMDB 改標題也不動它（兩個方向各有測試；拿掉守衛時凍結那條會紅）。TMDB adapter 補詳情四支端點，**7 份 fixture 對真 API 錄**；`NotFoundError` 讓「這個 id 不存在」與「TMDB 壞了」分得開。`/media/:id` 走 `/impeccable shape`（`.scratch/m1/media-detail-shape.md`，使用者拍板三個問題），探索牆的每一格終於是連結。順手收掉兩處共用：`DiscoverProblem` → `TmdbProblem` + `TmdbNotice`、`Cutaway` 移進 `components/`。520 個後端測試 + 138 個前端測試綠燈；**對真的 `api.themoviedb.org` 實跑**：SPY×FAMILY 4 季 53 集、S02E01 的絕對編號是 #26，深淺兩主題 336 個文字元素最低 5.71:1，390px 無橫向捲動。實跑當場抓到兩個缺陷（集表撐寬整頁、資料夾名那一列的 term 用錯變體）並修掉 | `/implement .scratch/m1/issues/05-parser-skeleton.md` |
| 2026-09-09 | 04b 追蹤語意 | **「追蹤」不再是一個動作**：`media.tracked` 欄位（含 migration `5225422c03ef`，升得上去也降得回來）、`POST /api/media/{id}/track`、`DiscoverItem.tracked` 與 `TrackAction` 全部移除；`folder_name` 改成一律跟著 TMDB 的標題走（票 04 釘住「refresh 不改它」的那條測試反過來），凍結移到票 09 的送單成功那一刻——那是它第一次真的通向磁碟，而且有人在場。Route 下拉原地留下、語意換成「入庫到哪裡」的偏好：不落地、不新增端點，只有一條相符時自動選它。plan §2.2 / §6 / T1.1、brief §9 / §13、CHANGELOG、shape brief 與票 04 / 08 / 09 同輪改完。520 個後端測試 + 144 個前端測試綠燈；playwright 對 `--scenario discover`（真 TMDB）實跑詳情頁：劇集兩條相符的 Route 不預選、電影只有一條時自動選 Movies、資料夾名那一列說得出它什麼時候定下來 | `/implement .scratch/m1/issues/05-parser-skeleton.md` |
| 2026-09-10 | 05 解析器骨架 | `berth bench` 跑得起來：**20 筆真實 torrent 的檔案清單**（動漫 8 / 非動漫劇集 8 / 電影 4，共 321 個檔案，逐筆附 `source_url`）與 **18 份凍結的 TMDB 快照**（`scripts/record_tmdb_snapshots.py` 走產品自己的路徑錄）就位；分類、CJK 正規化、發佈名解析與 `Tags.render()` 完成。**分類 321/321、語料寫下的 tag 128/128、`auto_wrong` = 0**，其餘 268 筆落在 review（季集對應是票 06，目標路徑是票 07，這是預期的）。票 01 量到的兩個羅馬數字寫法都有真實語料與單元測試釘住。import-linter 多一條「parser / naming 不得 import 會做 IO 的模組」，並實測拿掉守衛會紅。680 個後端測試綠燈 | `/implement .scratch/m1/issues/06-parser-mapping.md` |
| 2026-09-10 | 06 季集對應 | `map_episode` / `structure_hints` / `match_media` / `score` 完成：**benchmark 的季集第一次真的動起來**——`auto_correct` 0 → **140**（語料寫下的 128 個 import 全對），`auto_wrong` **0**、`missed` **0**、信心達標 140/140。票 01 量到的三條槓桿都做進去了：**篇章名 → 季號**（佔失敗九成；為此 `SeasonSnapshot` 多一個 `names`，季名改取 `en-US` / `zh-TW` / `zh-CN` 三輪——真實發佈寫的是「柱训练篇」而英文季名是 `Hashira Training Arc`，只留一套字這條規則一次都不會命中）、**`第二部分` / `Part.2` 的 cour 偏移**（與虛擬季同一條 180 天規則；加上偏移超出該季就回頭照字面讀，於是「季內連號」與「每 cour 重數」兩種寫法用同一條規則都對）、**180 天虛擬季**。語料補三筆真實發佈（鬼滅柱訓練篇、進擊的巨人 S3 Part 2、單檔多集的 `Mizuiro Jidai - 01-02`），共 23 筆 333 個檔案。過程中抓到兩個票 05 的解析器缺口：`[01-13TV全集+SP]` 讓整包 13 集正片被當成特典（`merge_release` 不再補 `special_kind`）、`The_Final_Season[28]` 的 28 被 guessit 讀成季號。812 個後端測試綠燈 | `/implement .scratch/m1/issues/07-naming-plan.md` |

| 2026-09-10 | 07 命名與 Plan | `naming/` 的六種凍結模板、`match_subtitle`、目標路徑與衝突偵測完成：**Plan 第一次說得出「這個檔案會被寫到哪裡」**。benchmark 連目標路徑一起比對，`auto_wrong` 仍是 **0**、`auto_correct` **140** 不變，外掛字幕 37 筆全部掛對（新的 `subtitle_correct` 桶），review 從 98 掉到 61（剩下的全是 `your-name-bdmv` 的 61 個光碟檔）。`naming` 移到 `parser` 之下（衝突偵測比的就是目標路徑）；「兩個檔案同一集」不再一律進 review，改比檔名——简繁分軌與 1080p / 720p 同包本來就該並存（brief §7.7）。`AiPlanner` 介面與 `NullAiPlanner` 一併定好（plan §4.5）。869 個後端測試綠燈 | `/implement .scratch/m1/issues/08-indexer-search.md` |
| 2026-09-10 | 08 索引站搜尋 | `IndexerSearch` 介面加 `ProwlarrSearch` / `TorznabSearch` 兩個實作、`services/search.py`、`GET /api/search` 與 `GET /api/search/queries`、Media 詳情頁的搜尋區塊與結果表。fixture 對真的 Prowlarr 2.5.2.5491 + 五個公開站錄製。實跑（`--scenario search`，TMDB 與索引站都是真的）驗過動漫 / 美劇 / 電影三種類型：SPY×FAMILY 1726 筆去重後逐站各取 25 筆，98/100 筆有正確的季集預估與 Tags；深淺兩主題各 894 個文字節點對比全過（最差 5.71:1），390px 無頁面層級橫向捲動。920 個後端測試 + 162 個前端測試綠燈 | `/implement .scratch/m1/issues/09-add-download.md` |
| 2026-09-10 | 09 送單與下載列表 | `jobs` / `job_files` 兩張表、`add_download`、`POST /api/jobs` 與 jobs 的三支讀取端點、下載列表頁 `/jobs`（`.scratch/m1/jobs-shape.md`，使用者拍板三件事：時間線就地展開、進度欄現在就畫、純粹最新在前）。**送單前 Berth 自己把 torrent 抓下來**（新的 `adapters/torrent.py`：磁力連結就地解析，`.torrent` 逐位元組取 `info` 再 SHA-1）——`jobs.hash` 是主鍵而索引站不一定報 hash，而且交網址給 qBittorrent 是背景抓取、失敗永遠沒有下文。資料夾名在**送單成功那一刻凍結**（`media.folder_frozen`），`tracked` 改由 `EXISTS(jobs)` 推導（`services/tracking.py`，詳情頁與探索牆同一份）。plan T1.9 的結構化日誌一併做掉：一行一筆 JSON、job id 由 `ContextVar` 在 record 建立那一刻蓋上，「每一行都帶」有測試守著。**對真的 qBittorrent 5.2.3 與 4.4.5 各驗一輪，當場抓到一個實跑才看得見的缺陷**：5.2.3 的 `torrents/add` 成功回的是 JSON 摘要不是 `Ok.`，只認 `Ok.` 的話 5.x 上每一次成功送單都會被判成失敗（brief §20.2 / §20.7 與研究文件已更正，五份 fixture 已錄）；兩台上 category、save path、`berth` tag 與版本對的開始參數都落對了。1006 個後端測試 + 180 個前端測試綠燈，`berth bench` 的 `auto_wrong` 仍是 0 / `auto_correct` 140。playwright 對 `--scenario submit` 與 `submit-failing` 實跑：真 TMDB 的詳情頁 → 搜尋 → 送單確認印出資料夾名 → 送出 → 下載列表看得到 → 展開時間線 → 重試；深淺兩主題 × 桌機與 390px 四輪對比全過（最差 5.71:1），390px 無頁面層級橫向捲動 | `/implement .scratch/m1/issues/10-qbit-poller.md` |
| 2026-09-10 | 10 poller | `qbit_poller`（maindata 增量、plan §3.1 由客戶端狀態觸發的七個轉換、進度事件每跨 25% 一筆）、`GET /api/events/stream`（SSE）讓下載列表不重整就自己動、`job_files`、時間線五種新事件、健康頁的「下載迴圈」區塊與無主 torrent、`IpBannedError`（解掉 T1.9 第四條）。對真的 4.4.5 與 5.2.3 各錄一輪 fixture（maindata 全量 / 增量 / 移除、`torrents/files`、封鎖的 403）。實跑：真的 qBittorrent + 真的 poller，送單 7 秒內走到「下載完成」且全程 0 次頁面載入；重啟 Berth 後狀態與時間線都在。1062 個後端測試 + 198 個前端測試綠燈 | `/implement .scratch/m1/issues/11-planner-runner.md` |
| 2026-09-11 | 11 planner_runner | `plans` / `plan_items` 兩張表、`planner_runner`（事件驅動 + 每 60s 掃 `completed` **與 `planning`**）、mediainfo adapter、pre-plan、`GET /api/plans/{id}`、`POST /jobs/{hash}/replan`，以及下載列表展開區裡的「匯入計劃」——**Plan 第一次真的落地**：逐檔的處置、信心、季集、目標路徑與理由都存得下來也看得見。**沒有人在場的那一段接上了**：下載完成 → 讀 mediainfo → 解析 → 建 Plan → 全 high/medium 就自己走向 `importing`，否則停在 `review` 並說得出三種理由中的哪一種。mediainfo 對**真的檔案**驗（`tests/fixtures/mediainfo/two-second-episode.mkv`，ffmpeg 造的 17 KB Matroska），並當場記下 libmediainfo 的兩個坑：`duration` 在 General 上是 int、在 Video 上是 str，而讀得完但沒有影像軌的檔案不丟例外——所以「有沒有影像軌」才是「這是不是影片」的判準（brief §20.4）。`--scenario plan` 讓這一整段實跑得起來（qBittorrent 是替身但**真的把檔案寫進 save path** 並報成 100%）：三集的批次自動入庫、OST 那一包停在待審核、按「重新規劃」後 plan id 與 item 數都不變。1145 個後端測試 + 213 個前端測試綠燈，`berth bench` 的 `auto_wrong` 仍是 0 / `auto_correct` 140；四輪無障礙實測（1280px 與 390px × 深淺）最差 5.71:1、390px 無橫向捲動。順帶把 plan T1.9 的四條技術債逐條過完：三條已完成，剩下的「一個媒體庫多條 Route」留在票 14 | `/implement .scratch/m1/issues/12-importer-ledger.md` |
| 2026-09-15 | 12 importer、帳本與 Jellyfin 反查 | `ledger` 表與 migration、`importer`（逐檔建目錄 → `link()` → 帳本 → 事件、一個檔案 commit 一次；目標已存在比 inode：同一個補帳本、不同就 `target_unmanaged` 進 review；正片鏈接不成是 `import_failed`、「再試一次入庫」從沒做完的接著做）、`jellyfin_resolver`（兩段查詢都以媒體庫為 parent、也比 `MediaSources`；30s → 2m → 10m → 1h 共 6 次，排程存在帳本上；找到之後觸發 MergeVersions）、事件一分鐘內去重（使用者按下的重試是界線）、時間線六種新事件。**對真的一套做 M1 驗收**（berth image 由工作目錄 build、qBittorrent 5.2.3、Jellyfin **12.0.0**、真的 TMDB，`/data` 是 Docker Desktop VM 的 ext4 named volume）：The Bear S03、Frieren S01（28 集 + 11 集 Specials）、Oppenheimer 三包由 Berth 自己抓 torrent、送單，資料到位之後 **10 秒內不經人工走到 `imported`**；50 個正片硬鏈接在容器內 `stat` 同一個 inode、link count 2；Jellyfin 顯示正確的季集、標題與海報（API 與 playwright 截圖兩邊都有）；Berth 反查到全部 50 個 item 並觸發 MergeVersions。**實跑抓到一個真缺陷**：Jellyfin 的路徑通知對從沒掃到過內容的媒體庫無效（204 但什麼都不做，查核原始碼確認），套件內的第一次入庫一定踩到——resolver 改成第二次沒找到就跑 `RefreshLibrary` 排程任務（brief §20.1）。code-review 兩軸的發現大多修掉（`target_unmanaged` 改名、「再試一次入庫」不撞 Reimport、`link_failed` 只有阻擋才紅、resolver 重送通知與逐筆略過、去重以重試為界、EXDEV 訊息分得出 mergerfs）。`/Items` 對 12.0.0 錄了三份 fixture。1199 個後端測試 + 222 個前端測試綠燈；11 條 `deploy/` shell 腳本測試在這台機器上紅（`bash` 解析到 WSL，其中 2 條在乾淨 HEAD 上同樣紅），記在票的 Comments | `/implement .scratch/m1/issues/13-library-page.md` |
| 2026-09-15 | 13 媒體庫頁與 Jellyfin 深連結 | `/library/:routeSlug`（程式碼叫 inventory）：Route 切換列、卡片牆（六種狀態依序取、`N / M 集入庫`、Jellyfin 找到了沒）、「待審」「Unmatched」篩選；Media 詳情補上「檔案與版本」（季集、Tags、目標路徑、帳本與反查狀態、對不到的檔案、多版本並存）與集表的入庫欄。`/impeccable shape` 使用者拍板四題（牆上放全部有 Job 的作品、選填對外網址 + 推導、各集五種狀態、卡片本體連詳情）。深連結 `{主機}/web/#/details?id=…` **不帶 `serverId`**（12.0.0 實測），帳本多 `jellyfin_series_id` 讓劇集連到作品。code-review 兩軸修掉十處（前端 `library` 命名、多版本跨 Route 誤併、季列分母在前端算…）；**測試抓到一個自己的缺陷**：migration 用 batch 重建 ledger，外鍵順序不固定讓「降版再升版」的 schema 比對偶發紅，改用原生 `ADD COLUMN`。playwright 對真環境（Jellyfin 12.0.0）點卡片的深連結開到「奧本海默」，對 `inventory` 演練情境看到真的 resolver 寫下 Series id 與待審篩選；深淺兩主題 × 1280 / 390 最低 6.53:1 / 5.71:1、無橫向捲動。1266 個後端 + 257 個前端測試綠燈 | `/implement .scratch/m1/issues/14-route-settings.md` |
| 2026-09-15 | （規劃，無票） | 票 13 收尾後使用者拍板：媒體庫改成像 Jellyfin 那樣瀏覽，播放仍跳 Jellyfin，排成 M1.5（M1 驗收後、M2 前）。brief §1.1、§1.2、§12、§13、§17、§18、§19 與 plan §11.2b 已改，Jellyfin API 的可行性查證寫在 `docs/research/library-browsing.md`、摘進 brief §20.8。另查 Jellyfin 12（`docs/research/jellyfin-12.md`，brief §20.9），使用者拍板支援版本、釘 image、多集衝突送審核，插入 M1 票 14b | `/implement .scratch/m1/issues/14-route-settings.md`（新 session），之後 14b、15；M1.5 的待決已定，M1 驗收後直接 `/to-tickets docs/plan.md` 拆 M1.5 |
| 2026-09-15 | 14 Route 設定頁 | `/settings/routes`（只有 admin）：同一個 Jellyfin 媒體庫的第二條 Route（新增時向 Jellyfin 現查，已經有 Route 的路徑選不了）、改名稱 / profile / 啟用（每次重跑五條纜繩，紅燈不給啟用）、重新檢查、明確刪除（被 Job 或帳本引用就不給刪除鍵、說出路：停用）；`GET|POST /api/routes`、`PUT|DELETE /api/routes/{id}`、`POST /api/routes/{id}/check`、`GET /api/jellyfin/libraries`。使用者拍板三題（精靈只新增不改不刪、紅燈建立但停用、PUT 只改三個欄位），shape 三題（兩頁共用子分頁列、綠燈收起紅燈展開、新增在清單下方就地展開）。**精靈第 7 步重跑不再隱式刪 Route**：已經有 Route 的媒體庫鎖住、每條 Route 底下有同一個刪除；停用的 Route 不算進健康總結與完成條件。code-review 兩軸抓到兩個真缺陷並修掉——精靈跑完之後重跑會建出啟用中的紅燈 Route、檢查以名稱認媒體庫（一庫多條之後改名或同名會驗到別的）——另補三條測試、電影不收 anime、門禁前綴收窄。chrome-devtools 對 `--scenario routes` 實跑（playwright 的瀏覽器被另一個程序佔用）：建出 `berth-tv-2` 全綠、紅燈建立維持停用、啟用被拒、刪除、刪不得的說明、EN；深淺兩主題 × 1280 / 390 最低 5.22:1、無橫向捲動。1306 個後端 + 278 個前端測試綠燈。**一條待使用者確認**：停用不算進完成條件，加上 `/api/routes` 在精靈跑完之前匿名開放，代表那一刻可以匿名停用紅燈 Route 再完成 | `/implement .scratch/m1/issues/14b-jellyfin-12.md`（新 session） |

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
- 2026-09-09 票 03 收尾：演練情境的 TMDB 憑證環境變數從 `BERTH_TMDB_KEY` 改名 `TMDB_API_KEY`，與票 02b 給實驗腳本定的名字合併——同一把 key 兩個名字是本票引入的不一致。根目錄 `.env.example` 補上該欄位並寫明**產品不讀它**（Berth 的唯一來源仍是精靈寫進資料庫的 `settings.services.tmdb.api_key`），跑法沿用專案既有的 `uv run --env-file .env`。
- 2026-09-09 票 04：**`media.tracked` 是欄位，不是「有沒有這一列」**。點進詳情頁就會寫下一列——快照要有地方放，而 `tmdb_cache` 是探索牆的一小時快取、規則完全不同（plan §8.3）。連帶把 `folder_name` 的凍結點定死在**追蹤那一刻**：還沒追蹤時它跟著 TMDB 的標題走（畫面上是「將會是」的預覽，PRODUCT.md 原則 2「動手前先給看」），`tracked` 一旦是 true 就再也不動。plan §2.2 已補；兩個方向各有一條測試，拿掉那個 `if not row.tracked:` 守衛時凍結那條會紅。
- 2026-09-09 票 04：**季集只取英文那一輪**，詳情才打兩輪。理由是集名會進檔名（plan §5 的 `{episode_title}`），中文集名放進去等於讓磁碟上的檔名跟著 UI 的語言跑。所以一部四季的作品是 2（詳情兩種語言）+ 4（每季一次）+ 1（absolute group）= 7 個請求，24 小時一次。plan §8.3 已補。
- 2026-09-09 票 04：**TMDB 詳情的 append 拿掉 `external_ids` 與 `release_dates`**，推翻 plan §8.3 原本列的兩個。理由是快照裡沒有任何欄位讀它們，而 `release_dates` 每部電影是一百多筆各國上映日（2026-09-09 實測 138 筆）。要用時再加回來，plan §8.3 已同步。
- 2026-09-09 票 04：**絕對編號要從 0-based 的 `order` 推**，不是 episode group 裡的 `episode_number`——後者保留播出序原值，所以 SPY×FAMILY 的 S02E01 在 group 裡仍然是 `episode_number: 1`，而它是絕對第 26 集（對真 API 實測並錄成 fixture）。同一部作品有五個 episode group，只有 `type: 2` 是絕對編號。brief §20.3、plan §8.3 已補。
- 2026-09-09 票 04：`DiscoverProblem` 更名 `TmdbProblem` 並新增 `not_found`，訊息塊收成共用的 `TmdbNotice`（`discover/DiscoverNotice.tsx` → `components/TmdbNotice.tsx`，i18n 鍵 `discover.problem.*` → `tmdb.problem.*`）。理由是兩頁問的是同一台服務、四種理由的下一步也一樣；`not_found` 不給重試（那個 id 上面就是沒有作品）。`Cutaway` 也從 `setup/` 移到 `components/`——DESIGN.md 早就把它列為設計系統的元件，只是一直住在精靈底下。
- 2026-09-09 票 04：`GET /media/{id}` 順手回**相符的 Route 清單**，不要前端另外打 `GET /routes` 再自己過濾。「劇集只進得了 tvshows 媒體庫」是領域規則（`domain.collection_type_for`），放前端會變成第二份實作；型別不符擋在 track 那一支回 422，而不是等送單才發現。
- 2026-09-09 票 04 實跑：**展開的集表把整頁撐寬**（390px 實測 560px）。`<details>` 是 grid 項目而 grid 項目的 `min-width` 預設是 `auto`，所以它不肯縮到比 `min-w-[32rem]` 的表格窄，`overflow-x-auto` 那一層因此永遠沒事做。補 `min-w-0` 之後整頁 375 = 375、表格自己捲（327 / 512）。shape brief §7 本來就寫「該捲的是集表自己」，這是實跑才看得到的違反。
- 2026-09-09 票 04 實跑：`CutawayRow` 的 `code` 變體是給 **term 本身就是機器字串**的那種列（`tmdb_id`），資料夾名那一列的機器字串在 dd（dd 本來就是 `.value`），所以 term 要走 `.label`。一度兩者都給了 `code`，畫面上「Folder (frozen)」與旁邊四個大寫模板字對不齊。
- 2026-09-09 票 04 code-review：**`sanitize()` 只做 `strip()` 是這一票的缺陷，不是票 07 的欠債**。理由是 `folder_name` 在**這一票**就凍結進資料庫——`Mission: Impossible` 現在被寫成非法路徑的話，票 07 補規則時那幾列已經改不掉了。plan §5 的完整規則（移除 `/ \ : * ? " < > |` 與控制字元、連續空白合一、去尾端 `.` 與空白、≤ 200 UTF-8 位元組且不切半個字）連同八條邊界測試補在本票；票 07 接手其餘五種模板，共用同一支。
- 2026-09-09 票 04 code-review：**絕對編號一度是「這一筆排第幾」而不是 `order + 1`**，與 plan §8.3、brief §20.3 自己寫的規則相反。單一連續的 group 兩種算法一樣，所以 fixture 測不出來；group 缺號時位置會編出一個 TMDB 沒說過的號碼。已改成直接用 `order + 1`，並補一條刻意給缺號、亂序 group 的測試。
- 2026-09-09 票 04 code-review：**季數與集數把 Specials 算進去了**（顯示「4 季 53 集」，而 TMDB 自己的 `number_of_seasons` / `number_of_episodes` 是 3 / 50）。總數改成只算 `season_number > 0`；季集**清單**仍然列出 S00——那一季是真的存在，只是不進總數。
- 2026-09-09 票 04 code-review：**「快照是舊的」不可以用 `blocked`**（The One Meaning Rule：紅色只代表「在你動手之前走不下去」，而這一格的前提正是頁面照樣畫得出來）。改用 `assigned`，順帶讓掉 `blocked` 會帶的 `role="alert"`——舊快照不該打斷螢幕閱讀器。
- 2026-09-09 票 04 code-review：**快照新鮮度那一塊一度自己一個區塊，正好佔住票 08 搜尋結果表的位置**，而 shape brief §3 自己寫著「後兩票往中間插，不重排前面」。收進身分帶。同一輪把「立即重抓」的 `disabled={pending}` 拿掉（票 02b：按鈕永遠按得下去）。
- 2026-09-09 票 04 code-review：三處逐字複製的 ghost 連結類名收成 `GHOST_LINK`，兩處「admin 給連結／否則叫管理員」收成 `SetupHint`——後者正是這一輪自己說「各寫一份遲早會走樣」卻又抄了一次的那條規則。保序去重也寫了兩份（adapter 與 services），收成 `adapters.tmdb.unique_titles`。
- 2026-09-09 票 04 code-review：Route 下拉用 `useState(media.default_route_id)` 只取初值，追蹤成功或 refresh 之後會停在舊值。改成「使用者這一輪動過就用他的選擇，沒動過就跟著資料走」。
- 2026-09-09 票 04 code-review：識別欄位的標籤說「首播 / 上映」而值只有年份。`first_air_date` 早就在快照裡，補進 `MediaOut` 並顯示整個日期。
- 2026-09-09 票 04b：**推翻票 04 的「追蹤」**。`CONTEXT.md` 早就寫著 Tracked Media 是「Berth 曾為其下載、訂閱或入庫過的 Media」——一個推導出來的結果，不是一顆按鈕；而畫面上那顆按鈕讀起來像訂閱（使用者回報：「似乎訂閱了這個媒體，新集出來時會自動下載」），M3 真的訂閱（Rule）進來時這一頁會有兩個東西都自稱「追蹤」。`tracked` 是**刪掉**而不是改成推導：`jobs` / `ledger` / `rss_rules` 三張表都還不存在，留著只會是一個永遠是 false 的死欄位（票 09 起以 `EXISTS(jobs)` 推導回來）。plan §2.2 的「`tracked` 是一個欄位而不是有沒有這一列」整段刪除。
- 2026-09-09 票 04b：**凍結 `folder_name` 的時機從「追蹤」移到「送單成功」**（票 09；M3 的 Rule 建立時同理）。理由是那一刻才是第一次真的通向磁碟，而且與追蹤一樣有人在場、有一次明確確認。**不拖到入庫才凍**——importer 是背景迴圈，那時候沒有人看著，而這是整個系統唯一一個定了就改不掉的字串（brief §4.5）。`sanitize()` 仍然每次都跑：票 04 的理由（現在寫進去的非法路徑之後改不掉）在凍結點移走之後依然成立。
- 2026-09-09 票 04b：**動作列這一票不黏底**（偏離票上的「版面不動」）。`RoutePicker` 留在動作列的位置上，但拿掉 `STICKY_ACTION`——390×844 實跑量到那條 bar 永遠佔著 ~80px，而裡面沒有任何東西按得下去。票 08 的搜尋鍵回到這一行時它跟著回來（已寫進元件 docstring 與票的 Comments）。
- 2026-09-09 票 04b：**`default_route_id` 一併退出 `MediaOut`**（欄位留在資料表，票 09 要寫）。這一票之後沒有任何東西寫得了它，回應裡它會永遠是 `null`——與刪掉 `tracked` 同一個判斷。下拉的初值改由「只有一條 `collection_type` 相符的 Route 就選它」決定，多數人身上這件事根本不存在。
- 2026-09-09 票 04b：`web/src/pages/MediaDetailPage.tsx` 在票 04 交出去時**沒有通過 `prettier --check`**（`pnpm -C web format:check` 會紅，CI 的前端 job 因此在 main 上是壞的）。本票的 `pnpm format` 順手修好，沒有另開票——它是票 04 的收尾漏掉的一步。
- 2026-09-09 票 04b code-review：**migration 的 `downgrade` 留下了一個當初沒有的 `server_default`**。SQLite 補一個 NOT NULL 欄位得先給預設值填舊列，填完要 `alter_column(server_default=None)` 拿掉。既有的兩條 migration 測試都測不到它——一條降到 base（整張表沒了）、一條降完再升回 head（差異被下一次升版蓋掉）。補的 `test_downgrading_the_last_revision_lands_on_the_previous_schema` 比的是 `PRAGMA table_info` 而不是 `sqlite_master.sql` 原文：batch migration 是「建新表再搬」，回來的 DDL 會多一組引號、欄位順序也會變，那兩件事不是差異，而預設值是。
- 2026-09-09 票 04b code-review：探索頁「防抖」那條測試是**偽陰性**——它等的 `Moana` 在熱門那面牆上本來就有，所以搜尋還沒送出就綠了，機器一忙就翻成紅（實測 3/6）。結果那一筆的標題不能與牆上任何一格相同。這是票 03 留下的，本輪順手修掉。
- 2026-09-10 票 05：**語料的 `files[].path` 是相對於 torrent 內容根**（不含最外層資料夾），`torrent_name` 則是**索引站上的發佈標題**而不是 torrent 內部的根資料夾名。兩者各知道一半：CJK 的字幕語言與季號幾乎只寫在標題上（`简繁外挂`），集號只寫在檔名上，所以 `parse_release` 兩邊都跑再 `merge_release`。已寫進 plan §4.6。
- 2026-09-10 票 05：語料的 `expected` 多一個 **`kind`** 欄位（plan §4.6 的範例原本只有 action / 季集 / tags）。分類是第一層，錯在這裡後面每一層都白算，而它是這一票唯一量得到的東西。plan §4.6 已同步。
- 2026-09-10 票 05：benchmark 的桶從 plan §4.6 的五個加到**七個**（多 `missed`：該入庫的被丟成 unmatched / skip；`skipped`：雙方都同意可忽略）。理由是五個桶加起來不等於檔案數，那種報表會讓沒被數到的檔案看起來不存在。另加分類正確率與 tag 正確率兩欄——沒有它們，這一票做的三件事在報表上完全不會動。plan §4.6 已同步。
- 2026-09-10 票 05：`min_confidence` **不參與比對**。信心低於期望不是「做錯事」，只是少自動化了一點，那件事由 `review` 與 high / medium 誤判率各自回答；把它算進誤判會讓「保守」與「入錯」混成同一個數字。plan §4.6 已同步。
- 2026-09-10 票 05：`sample` 的大小比較**同目錄沒有別的影片時退回整包最大的那一個**（plan §4.1 原文只寫「同目錄最大影片 10%」）。真實發佈幾乎都把 sample 放在自己的 `Sample/` 資料夾裡，照字面只比同目錄的話這條規則永遠不成立。plan §4.1 已同步。
- 2026-09-10 票 05：**v0 語料裡沒有 sample 檔**——抓的 20 個真實 torrent 一個都沒有，現在的發佈幾乎不再附 sample（apibay 與 dmhy 各掃過數十筆）。規則改由 `tests/unit/test_parser_classify.py` 釘住，並記在 `tests/fixtures/parser/README.md`。多集檔（`S01E01E02`）同理，語料留給票 06 補。
- 2026-09-10 票 05：`extra` 的資料夾清單改為引用 brief §20.1 那一串 **Jellyfin 認得的 extras 資料夾名**（`Featurettes/`、`Behind the Scenes/`…），不只 brief §6.2 原本寫的 `SPs/` `Extras/` `Bonus/`。真實語料（`movie/psycho-featurettes`）的 17 個特典就放在 `Featurettes/`，而其中 5 個的檔名沒有任何關鍵字。brief §6.2 已同步。
- 2026-09-10 票 05：`disc` 是**整包**的判定而不是逐檔——`BDMV/` 與 `CERTIFICATE/` 是同一張碟的兩半，只標其中一半沒有意義。plan §4.1 已同步。
- 2026-09-10 票 05：`CjkHints.special` 用 `SpecialKind` enum 而不是 plan §4.2 原本寫的 `str`（`SP` 可能對得到 TMDB season 0，`NC` 一律進 extras，下一步不同）；`CjkHints` 另加 `matched`（認出來的原文，往上併進 `ReleaseInfo.matched_tokens`）。`ReleaseInfo` 不含 `season_hint_from_folder`——資料夾提示是 `structure_hints` 的輸出（票 06），兩個階段的產物不混進同一個型別。plan §4.2 已同步。
- 2026-09-10 票 05 查證：brief §20.4 標「未證實」的 **VCB-Studio 類 BD 包資料夾名**已用兩份真實 torrent metadata 確認，社群轉述的 `SPs/ CDs/ Scans/ Fonts/ Menu/` 只對了一半：VCB-Studio 有 `SPs/` `CDs/` `Scans/` 但**沒有** `Fonts/` 與 `Menu/`；DBD-Raws 是 `SP/` `PV/` `NCOP&NCED/` `menu/`（小寫）`Fonts/Fonts.zip`。兩份都成了語料。brief §20.4 已同步。
- 2026-09-10 票 06：**`SeasonSnapshot` 多一個 `names`（各季在 `en-US` / `zh-TW` / `zh-CN` 三輪的名字）**，
  `services/media.py` 對劇集多打一輪 `zh-CN` 詳情（只取季名，電影不打）。plan §4.3 / §4.4 / §8.3 已補，
  實測記在 brief §20.3。理由：plan §4.4 的「篇章名 → 季號」是 M1 票 01 量到的最大槓桿（佔失敗九成），
  而真實發佈寫的是簡體篇章名（`鬼灭之刃 柱训练篇`），TMDB 的英文季名是 `Hashira Training Arc`——
  只留英文的話那條規則對它一個都不會命中。18 份凍結快照因此重錄。
- 2026-09-10 票 06：**絕對編號的三種換算不在同一個分支**，推翻 plan §4.1「三法各產一個 Candidate」
  的字面讀法（plan §4.4 已補）。`absolute_group` 與 `absolute_cumulative` 是「只有集號」時的兩條路；
  虛擬季換算要有一個季號才索引得到那一輪播出。brief §6.4 另外提的「以**發佈時間**推測」需要索引站給的
  發佈時間，M1 的解析器拿不到（票 08 起才有 `published_at`），沒有它就只是換一種猜法，**刻意沒做**。
- 2026-09-10 票 06：**特典不靠集名或片長比對**（票 05 留下的決定）。檔名裡沒有集名、片長要 mediainfo，
  加了只是換一種猜法。規則維持：明說 `S00Exx` 照它走但信心至多 medium（字幕組的特典編號與 TMDB 的
  S0 編號不保證一致），只寫 `[SP][01]` 這種自己的序號則是 `unmatched`。寫進 `tests/fixtures/parser/README.md`。
- 2026-09-10 票 06：`ParseContext` 多一個 `candidates`（`media` 缺席時可以比對的作品）。plan §4.3 已補。
  理由是票的驗收要求「上下文缺 Media 時做標題比對」，而解析器沒有 IO——候選只能由呼叫端遞進來。
  M1 沒有人填它（Job 一律帶 Media），真正的使用者是 M3 的 RSS。
- 2026-09-10 票 06：`merge_release` **不再從 torrent 名補 `special_kind`**。`[01-13TV全集+SP]` 說的是
  「這一包裡有特典」而不是「這個檔案是特典」，原本會讓整包 13 集正片被判成 unmatched（語料實測）。
- 2026-09-10 票 06 code-review：信心的順序與封頂散在四個模組（`mapping` / `score` / `planner` /
  `bench`），其中 `bench` 那一份的順序還是反的。收進 `domain`（`CONFIDENCE_ORDER`、`AUTO_APPLIED`、
  `at_most`、`at_least`），四處各一份的狀況結束。
- 2026-09-10 票 06 code-review：**區間的尾巴算不出來時降到 low**。原本 cour / 虛擬季 / 絕對編號三條路
  在「檔名說 01-02 但換算後的 02 落在別季」時會靜默把多集檔變成單集檔——少入一集與入錯一集一樣看不見。
- 2026-09-10 票 06 code-review：補上 brief §6.5 的「影片數量與 TMDB 集數明顯不符 → low」。一季十二集卻
  對出二十個檔案時，是哪一個檔案讀錯了看不出來，所以整季一起進 review。
- 2026-09-10 票 07：**`naming` 移到 `parser` 之下**（plan §1.3 原本把兩者並排，import-linter 因此
  禁止 `parser -> naming`）。理由是 plan §4.1 的 `plan` 階段本來就要產出目標路徑，而**衝突偵測比的
  就是那條路徑**——那個判斷跑在 `score` 之後、離不開命名。反向不成立，另加一條契約守著。
- 2026-09-10 票 07：**「兩個檔案對應到同一集」不再一律進 review**（票 06 的 `score._duplicated` 刪掉）。
  brief §6.4 第 5 點說的是同一（季, 集, **tags**），而 §7.7 說同一集不同 tags 本來就該並存——简繁分軌
  與 1080p / 720p 同包都是常態。改比**目標路徑**：那正是「會不會蓋掉對方」的定義，而 tags 已經在檔名裡。
  brief §6.4 第 5 點已同步。
- 2026-09-10 票 07：**字幕的第二條規則接受語言資料夾**（`繁體/`），不只 brief §6.7 寫的 `Subs/` `字幕/`；
  語言後綴另外收 ISO 639-2 式的 `.Cht` `.Chs` `.Jpn` `.Eng`（真實語料 `tv/gto-2026-magicstar` 寫的就是
  這一種）。同一集對到兩個以上的影片時**不選**——多版本並存時這一份字幕是誰旁邊的那一個，路徑沒有說。
  brief §6.7 已同步。
- 2026-09-10 票 07：**字幕的語言不看 torrent 名**。`附官方日英简繁中字幕` 說的是這一包有四種字幕，
  不是這一個檔案有四種——照 `merge_release` 的結果命名的話，四個 `.srt` 會全部變成 `.CHS+CHT+JP+EN.zh`。
  影片的 tags 仍然照舊用 torrent 名補（那一欄問的正是「這個發佈帶了哪幾種字幕」）。
- 2026-09-10 票 07：**`.default` 旗標在語言碼之前，而且 M1 不產生它**。plan §5 原本寫
  `{SUBTOKEN}.{lang}[.default]`，但 M0 票 04 實測的是 `.CHT.default.zh.ass`，brief §20.1 抄的官方格式
  也是 `<flags>.<language>`——原文的順序是抄錯的。至於產不產生：M1 沒有任何東西決定得了哪一軌是預設
  （沒有字幕語言偏好設定），寫死一個只是猜。plan §5 已同步。
- 2026-09-10 票 07：**標題自己帶著同一個年份時不再接一次**。TMDB 上真的有 `GTO (2026)` 這種標題
  （語料 `tv/gto-2026-magicstar`），照字面套模板會產出 `GTO (2026) (2026) [tmdbid-325022]`。只有**同一個**
  年份才算重複——`Show (1999)` 的 2020 重製版那兩個數字說的是兩件事。plan §5 已同步。
- 2026-09-10 票 07：benchmark 多一個 **`subtitle_correct`** 桶（七格 → 八格），baseline 多守
  `extra_correct` 與 `subtitle_correct` 兩格。理由是**字幕或 extras 整批掉出來時 `auto_wrong` 一格都
  不會動**，只守兩個數字的話那種退步在 CI 上看不見。plan §4.6 已同步。
- 2026-09-10 票 07：語料的 `expected` 多一個 **`target`** 欄位，`import` / `extra` / `subtitle` 必填、
  其餘必空，兩種都比。它是拿語料**自己寫的期望**（action / 季集 / tags）套凍結模板算出來的，
  不是抄解析器的輸出——抄輸出的話語料只會證明解析器與自己一致。plan §4.6 與語料 README 已同步。
- 2026-09-10 票 07：brief §7.8 的「與帳本既有版本同 tags → `duplicate`」**沒有做**，也做不了：帳本
  在票 12 才存在，而解析器沒有 IO。這一票做完的是同一包裡的衝突（brief §6.4 第 5 點）。記在票的 Comments。
- 2026-09-10 票 07 code-review：**長集名會把 tags 從尾巴截掉**。200 位元組上限原本只保護副檔名，
  於是同一集的兩個版本（只差 group）被截成**同一個檔名**——而 tags 正是它們唯一的差別（brief §7.7），
  結果兩個都被判衝突、一個都進不去。改成三段式：`SxxExx` 與 tags 一個字都不能少，可以捨的只有集名。
- 2026-09-10 票 07 code-review：**長標題的電影檔名不再以資料夾名開頭**。`folder_name` 與檔名各自
  截在不同的位置（一個扣副檔名一個不扣），於是 ` - ` 之前差了幾個字——那正是 Jellyfin 判「同一部片
  的多版本」的依據（brief §7.2）。電影檔名改成**不截**：前綴少一個字就不是同一部片，寧可超出上限
  （與側掛字幕同一個例外，兩者都仍低於 ext4 的 255）。
- 2026-09-10 票 07 code-review：**`sanitize` 的「去尾端 `.`」不該套在後面還要接東西的片段上**。
  `It Didn't Have to Be Magic...` 是 TMDB 的集名原文（語料 `anime/frieren-7acg-bd-batch`），
  而 `Foo..mkv` 的結尾是 `v`——Windows 擋的是**檔名**以 `.` 結尾，不是名字中間有點。
  清理與去尾端因此拆成兩支，資料夾名走去尾端那一支。
- 2026-09-10 票 07 code-review：側掛字幕**刻意超出 200 位元組**的例外寫進 plan §5；
  brief §6.7 補上 `.default` 的位置與「M1 先不產生」；plan §4.1 補上「brief §7.8 的帳本重複不在
  解析器」的理由——原本只是把「重複」兩個字刪掉，那是把決定藏起來。
- 2026-09-10 票 08：`IndexerSearch` 改成**一次呼叫一個查詢**（`search(query)` + `capabilities()`），推翻 plan §8.4 的 `search(queries, categories)`。多標題展開、併發、合併去重與逐查詢逾時要看 `MediaSnapshot` 與 Route 的 profile 才決定得了，留在 adapter 等於兩個實作各抄一份。已改 plan §8.4。使用者拍板。
- 2026-09-10 票 08：**分類碼不送給索引站**（plan §8.4 原本寫 `search(queries, categories)`）。實測 dmhy 對 `cat=5000`、`cat=5070` 與不帶 `cat` 都回同樣 80 筆，而它一筆帶 5070 / 100002 / 2020 卻沒有 5000——分類在這一層不是可靠的篩子。分類仍然收進 `SearchResult` 當顯示資料。已改 plan §8.4、brief §20.7。
- 2026-09-10 票 08：結果表只送**前 100 筆**（`RESULT_LIMIT`），而且是**逐站輪流取**不是取做種前 100 筆。plan / brief 都沒寫上限。理由是實測一次搜尋去重後 1726–1854 筆（1–2 MB JSON），而純做種排序會讓 100 筆全部來自 The Pirate Bay——公開中文站的做種數是個位數，TPB 的 scene 發佈是 28–86。使用者拍板 100 筆。已改 plan §8.4、brief §20.7。
- 2026-09-10 票 08：搜尋結果**先用標題粗篩**，名字對不上這部作品的丟掉並回報 `discarded`。plan / brief 都沒寫這一步。理由是實跑發現 **The Pirate Bay 對搜不到的關鍵字會回它自己的熱門清單**（搜 SPY×FAMILY 時前六筆是 Spider-Man、Ted Lasso、Reacher，做種四千到六千）。使用者自己打關鍵字時不篩——那時他要的是那一串字，不是這部作品。粗篩用新的 `parser.title.mentions`（純字串），因為 `parse_release` 實測每筆 14 毫秒，一兩千筆會把事件迴圈卡住半分鐘。已改 plan §6、§8.4、brief §20.7。
- 2026-09-10 票 08：新增 `GET /api/search/queries?media=&route=`，plan §6 的 search 群組原本只有一支。理由是「按下搜尋之前先給看會問哪幾個名字」（PRODUCT 原則 2）需要 `search_titles` 的答案，而那條規則要看快照與 Route profile——前端重算一份遲早會與後端分岔。順帶讓 `route` 這個參數看得見自己做了什麼。已改 plan §6。
- 2026-09-10 票 08：`search_titles` 把**顯示用標題明確排第三**（英文、原文之後），不跟著 `snapshot.titles` 走。實跑發現 TMDB 的 `alternative_titles` 沒有順序可言，它把 `Agent x Ailə`（亞塞拜然語，實搜 0 筆）排到中文標題前面，而中文標題是使用者索引站上最值錢的那一個。已改 plan §8.4。
- 2026-09-10 票 08：Route 下拉從身分帶**搬進搜尋區塊**，推翻 `.scratch/m1/media-detail-shape.md` §3 的「後兩票不動身分帶」。理由是它到票 08 才真的驅動一件事（anime profile 的查詢變體），留在身分帶等於一個按了沒反應的控制項。區塊序列不變。已改該 shape brief。使用者拍板。
- 2026-09-10 票 08：修了票 05 的解析器缺陷 `[01-13Fin]` 被讀成「第 1 集」（`_BRACKET_EPISODE` 不認得黏在集號後的 `Fin` / `END`）。跨票修是因為它讓這一票交付的結果表對一整類中文季包顯示錯的預估，而修法是一個正則 token；`berth bench` 的 `auto_wrong` 仍是 0。
- 2026-09-10 票 08：`TorznabCaps.search_available: bool` 換成 `search: TorznabSearchMode`，並多了 `tv` / `movie` 兩個同型別欄位。理由是 `t=caps` 的 `supportedParams` 決定得了能不能用 tmdbid 搜，而精靈與搜尋讀的是同一份 XML——解析寫兩份其中一份會先過期。內部型別，直接改掉舊形狀不留相容層。
- 2026-09-10 票 08 code-review：`_season_variants` 只對**季數 ≥2 的最新一季**產生 `第N季` / `Season N`，plan §8.4 只寫「anime profile 另加變體」。單季動漫零變體是刻意的——第一季的發佈幾乎不寫季號，而每多一個變體就是每個追蹤站再被問一次。已補進 plan §8.4。
- 2026-09-10 票 08 code-review：`SearchResult` 這個名字原本給了 adapter 那一層的原始列，但 `CONTEXT.md` 的 Search Result 指的是「**附解析出的 Tags 與預估季集**」那一筆。已對調：adapter 那一層改叫 `IndexerResult`（新詞，已進 CONTEXT.md），services / API / 前端的那一筆才是 `SearchResult`。
- 2026-09-10 票 08 code-review：`SearchResult` 拿掉畫面不畫的四欄（`leechers`、`published_at`、`confidence`、`release_kind`）。它們是替票 09 先鋪的，違反「不為想像中的未來需求加東西」。索引站真的回的那兩個（`leechers`、`published_at`）留在 adapter 的 `IndexerResult` 上——那一層的職責是忠實翻譯協定，而契約測試釘的就是它們。
- 2026-09-10 票 08 code-review：發佈名**不截斷**，推翻自己的 shape brief §6「最多兩行後省略」。它是這一列的證據——解析器讀的就是同一串字，截掉之後使用者看不出「為什麼判成 S03E13」。已記進 `.scratch/m1/search-results-shape.md` §8。
- 2026-09-10 票 09：**送單前 Berth 自己把 torrent 抓下來**（新的 `adapters/torrent.py`），plan §8.1 原本只寫「把參數送給 `torrents/add`」。兩個理由：`jobs.hash` 是主鍵而索引站不一定報 info hash（實測 ACG.RIP 不報，brief §20.7），沒有 hash 就沒有 Job；以及交一條**網址**給 `torrents/add` 是背景抓取——實測 5.2.3 回 `202` + `pending_count: 1`，抓失敗之後永遠沒有下文，那樣 plan §3.1 的 `submit_failed` 這個狀態永遠觸發不到。代價是一個 bencode 掃描器（不解碼，只取 `info` 的位元組範圍再 SHA-1——解出來再編回去只在鍵剛好照字典序時才等價）。plan §8.1 已補。
- 2026-09-10 票 09：**`torrents/add` 的成功形狀依版本判定**，推翻 brief §20.2 / §20.7 與 `docs/research/m0-experiments.md` §2.1 記的「一律回 200 `Ok.`」。2026-09-10 對真的 `lscr.io/linuxserver/qbittorrent:5.2.3` 與 `:4.4.5` 各錄一輪：4.4.5 成功回 `200` + `Ok.`，**5.2.3 成功回 `200` 加一份 JSON 摘要**（`failure_count` / `success_count` / `added_torrent_ids`）。只認 `Ok.` 的話 5.x 上每一次成功的送單都會被判成失敗——這個缺陷是實跑當場抓到的，單元測試與替身都看不見它。另外量到 `409 Conflict`（同一個 hash 已經在，或 category 的 save path 用不了）與 `415`（那份 `.torrent` 無效）。五份 fixture 已錄，brief §20.2 / §20.7、plan §8.1 與研究文件都已更正。
- 2026-09-10 票 09：`torrents/add` 送的那個開始參數**值是 `false`**（只送版本對的那一個鍵），plan §8.1 原本沒說值。理由是 qBittorrent 有一個「加入後不自動開始」的全域偏好，而 plan §3.1 的狀態機假設送出去的 torrent 會自己走到 `metadata_ready`；不明講的話，開著那個偏好的使用者身上每一筆 Job 都會永遠停在 `submitted`。實測 5.2.3 送出去之後是 `queuedDL` / `metaDL`，不是 `stoppedDL`。plan §8.1 已補。
- 2026-09-10 票 09：`jobs` 多一欄 **`source_url`**，plan §2.3 的欄位表沒有它。理由是「送單失敗可手動重試」要重送得出去，而畫面上那一輪搜尋早就不在了、Prowlarr 的代理連結每次搜尋都不一樣（brief §20.7）——重新搜一次不會給出同一條。
- 2026-09-10 票 09：`media` 多一欄 **`folder_frozen`**，plan §2.2 只描述了「第一次真的通向磁碟那一刻凍結」而沒有給它一個開關。**推導不出來**：送單失敗的 Job 也是一列 `jobs`，而那一刻磁碟上什麼都沒發生；刪掉那筆 Job 也不該讓資料夾名重新開始跟著 TMDB 跑。`services/media._store` 因此多一個守衛，拿掉它時新的那條測試會紅。
- 2026-09-10 票 09：**索引站給不出那份 torrent 時不建 Job**（HTTP 502 + `source_unavailable`），而 qBittorrent 收不下時**建**（200 + `submit_failed`）。票上只寫了後者。理由是 `jobs.hash` 是主鍵而 Job 記的正是「一個 torrent 的生命週期」（`CONTEXT.md`）——連是哪一個 torrent 都還不知道時，沒有東西可以記。
- 2026-09-10 票 09：**紅的 Route 擋下送單只認 `failed`，`unknown` 放行**。brief §4.4 說的是「紅的 Route 送單一定失敗」，而 `HealthStatus` 有三個值。`unknown` 是「還沒檢查」不是「壞了」，而健康迴圈五分鐘才跑一輪（plan §3.2）——拿它擋人等於精靈剛跑完的那五分鐘裡誰都送不了單。
- 2026-09-10 票 09：**送單前若快照超過六小時就先刷新一次**（plan §8.3 本來就這樣寫，這一票落地）。失敗不擋送單——TMDB 連不上時存下來的標題仍然是真的標題。順帶修掉 `services/media._view` 的一個潛在崩潰：沒有快照的 `media` 列會讓 `MediaSnapshot.model_validate({})` 炸掉，現在退回那一列自己知道的那幾欄。
- 2026-09-10 票 09：`services/routes` 送給 qBittorrent 的 category save path 改成**計劃裡那一串字**，不是 `str(Path(...))` 走一趟回來的樣子。容器路徑一律 POSIX，而 Windows 上那一趟會換成反斜線——送單比對的是同一支 `save_path_of` 的輸出，兩邊差一種分隔符就會判成衝突。兩條既有測試跟著改。
- 2026-09-10 票 09：`_sign_in` 從 `services/routes` 搬到 `services/qbittorrent` 並改名 `sign_in`。它問的是 qBittorrent 的事，而 Route 檢查與送單只是兩個呼叫端。
- 2026-09-10 票 09：**下載列表頁不另建 `/jobs/:hash`**（使用者拍板）：點一列就地展開時間線、info hash 與重試（The Failure Expands In Place Rule）。plan §7 的 `/jobs/:hash` 留給 T1.7 的完整 Job 詳情（檔案清單、Plan、刪除範圍）。排序**純粹最新在前**，不把失敗置頂——同一筆 Job 會在重試成功之後跳位置，而使用者剛剛才在那個位置按過按鈕。進度欄現在就畫、沒有值就說 `大小 —` / `進度 —`。
- 2026-09-10 票 09：`ApiError` 多帶一個 `detail`。拒絕的理由是封閉集合，而畫面要照理由說出下一步（PRODUCT 原則 4）——只有狀態碼的話「這條 Route 是紅的」與「這條 Route 停用了」在畫面上是同一句話。
- 2026-09-10 票 09：`CopyLine` 補 `min-w-0`。它常常是 grid 項目，而底下的 `<code>` 是 `whitespace-pre`，所以那一整串不斷行的字會變成整欄的 min-content、`overflow-x-auto` 永遠沒事做（票 04 的集表踩過同一個坑）。390px 實跑量到的。
- 2026-09-10 票 09 code-review：**打 qBittorrent 之前就要 commit 那一列 Job**。原本一路到送完才 commit，於是 `_submit` 期間任何一個沒接住的例外或斷線都會 rollback——而 torrent 可能已經進了下載器，那就成了一個沒有 Job 的孤兒（plan §3.2 的 `unknown_torrent`）。改成建完 job + `created` 事件就 commit，與精靈每一步「做之前先寫 `running` 並 commit」同一個道理（plan §2.1）。順帶接住主鍵撞車：兩個分頁同時送同一筆時回既有那一列，不是 500（plan §3.3）。
- 2026-09-10 票 09 code-review：**`→ submitted` 與 `→ submit_failed` 也走 compare-and-set**。plan §3.1 寫的是「轉換**一律** compare-and-set」，而原本只有重試那一條走了。`error` 與狀態同一句 UPDATE——分兩次寫的話中間那一瞬間的狀態與理由對不起來。票 10 起的迴圈會寫同一列，這一條在那時候才真的擋得住東西。
- 2026-09-10 票 09 code-review：**重試與第一次送單走同一組前提**（`_check_route`）。原本重試只檢查健康，於是一條被停用、或被改成收別種作品的 Route 上「第一次送不出去、重試卻送得出去」——同一個決定兩種答案。
- 2026-09-10 票 09 code-review：**送單這一步不刷新 TMDB 快照**，推翻本輪自己先做的「plan §8.3 的六小時」。理由是送單會**凍結** `folder_name`，而刷新會在使用者按下確認與那串字落地之間把它換掉——凍下去的必須就是他剛剛在確認畫面上看到的那一串（brief §4.5「有人在場、有一次明確確認」、PRODUCT 原則 2）。六小時那條規則留給票 11 的 planning，它的理由（新播集數會變）本來就是為 planning 寫的。plan §8.3 已改。
- 2026-09-10 票 09 code-review：`SearchResult` 多一格 **`info_hash`**。`key` 的定義是「info hash **或** guid」，而送單原本把它當 hash 送——不報 hash 的站（實測 ACG.RIP）那一格是一條網址，拿去當 hash 是在說謊（重複檢查也永遠不命中）。
- 2026-09-10 票 09 code-review：`adapters/torrent.py` 三處收緊——大小上限改成**邊讀邊擋**（原本整份進記憶體之後才判，那個上限只保護了 bencode 掃描器）、bencode 掃描器加深度上限（`RecursionError` 不是 `_MalformedError`，會穿過 `except` 冒成 500）、hash 的十六進位／base32 轉換只留 `adapters.indexer.normalise_info_hash` 一份實作（這裡只多一層「認不得就回空字串」的嚴格檢查——猜一個 hash 會讓兩個不同的 torrent 變成同一列）。
- 2026-09-10 票 09 code-review：`TorrentRejectedError` 的 docstring 原本寫「實測 `415` + body `Fails.`」，那是**抄錯的**——`Fails.` 是 4.x 登入失敗的 body。改成這一輪真的量到的兩種（`409 Conflict` 與 `415` + 檔名與原因）。
- 2026-09-10 票 09 code-review：沒選 Route 時**前端不打 API**。原本送 `route: 0` 出去，換回一句「那條 Route 不在了」——而使用者根本還沒選過（PRODUCT 原則 4）。
- 2026-09-10 票 09 code-review：`Dot` 收成 `components/Dot.tsx`（票 08 的結果表與這一票的下載列表各寫了一份）。它是一個字元，而 DESIGN.md 的 Don't 寫著「不用字元當裝飾標記」——那條規則說的是會進無障礙名稱的那種，而 `Dot` 掛 `aria-hidden`；CSS 畫的刻度跟不上一行會換行、寬度由內容決定的值列表。已寫進 DESIGN.md 的 Known contradictions。
- 2026-09-10 票 10：**無主 torrent 在 M1 的載體是一筆 `issue_detected` 事件加健康頁的一份清單**，
  不是 plan §3.2 字面的 `issue`（`issues` 表在 M2，票上已預告）。事件**一個 hash 只寫一次**——
  迴圈每 5 秒跑一輪，每輪一筆的話一天一萬七千筆；「現在還在不在」由 `settings.poller` 那份
  每輪重寫的清單回答。`IssueType` 四個值先定下來，M2 建表時它就是那張表的同一欄。
- 2026-09-10 票 10：**`settings.poller` 自己一列**，plan §3.2 原文寫的是「連續失敗次數與最後錯誤
  寫入 `settings.health`」。理由與當初把健康結果從 `settings.services.*` 分出來時一樣：`write_settings`
  是整組覆寫，而兩個迴圈一個 5 分鐘一個 5 秒，共用一列會互相蓋掉。plan §3.2 已同步。
- 2026-09-10 票 10：**輪詢間隔每次醒來重算**（迴圈每 5 秒醒一次，滿了間隔才真的問），
  與 `health_checker`「醒得比檢查頻繁」同一個形狀。沿用上一輪算出來的 30 秒的話，使用者按下送單
  那一刻多半落在間隔中間，他要對著那一列等最多半分鐘才看到第一個變化——而那正是這一票要拿掉的
  體驗。代價是一次帶索引的 `SELECT ... LIMIT 1`。plan §3.2 已補。
- 2026-09-10 票 10：**一輪可以走好幾步**。已經做完種的 torrent 加進來時，同一輪裡它走完
  `submitted → metadata_ready → downloading → completed`。plan §3.1 的表是逐狀態寫的，照字面
  一輪一步的話輪詢間隔會決定使用者看到幾個階段，而時間線仍然說得出它經過了哪些站。plan §3.1 已補。
- 2026-09-10 票 10：**`metadata_ready` 只做前半**（建 `job_files` + `metadata_received`），
  plan §3.1 的另一半 pre-plan 留給票 11——`plans` 表到那一票才建。plan §3.1 已註明。
- 2026-09-10 票 10：**完成判定的第四條（`stat` 每個檔案）只在 Berth 解析得了那條路徑、而且真的
  看得到它的時候才算數**。看不到就視為通過：那不是這一筆 torrent 的問題，而是掛載對不上，
  而那件事有專門的檢查在報（Route 的 `download_path` 纜繩）；在這裡翻成 `missing_files` 會讓每一筆
  Job 都紅著，而紅的理由指向錯的地方（PRODUCT 原則 4）。看得到卻少檔案才是 `missing_files`。
  「解析得了」是 `Path(save_path).is_absolute()` ——**Windows 上實跑當場踩到**：qBittorrent 報的
  `/downloads/complete/anime` 在那裡是「目前磁碟機的根目錄底下」，而那台機器上剛好有一個同名目錄，
  於是完成的 torrent 被判成 `missing_files`。plan §8.1 已補。
- 2026-09-10 票 10：**`stalled` 的門檻量 qBittorrent 自己的 `last_activity`（10 分鐘）**，不是 Berth
  另存一個「什麼時候變成 `stalledDL` 的」——客戶端本來就在量同一件事，少一個欄位就少一個會與它
  不一致的東西。10 分鐘偏長是刻意的：門檻太短會讓一列在 `downloading` 與 `stalled` 之間跳來跳去。
- 2026-09-10 票 10：**無主 torrent 的篩子是「category 或 `berth` tag」的聯集**，plan §3.2 只寫了
  category。只認 category 的話，Route 被刪掉之後它送出去的那些 torrent 就再也沒有人認領。plan §3.2 已改。
- 2026-09-10 票 10：**SSE 只推 job，不推健康變化**（plan §6 的 events 群組寫的是「job 狀態、進度、
  健康變化」）。健康檢查五分鐘一輪，值不到一條長連線；那一頁本來就有一顆「立即重測」。plan §6 已註明。
- 2026-09-10 票 10：**推播在 commit 之後**（實跑抓到的缺陷）。原本 `_advance` 走完就 publish，而那時
  `poll_downloads` 的交易還沒 commit——前端收到「這一筆完成了」立刻重問一次，讀到的是舊狀態，
  於是每一筆事件都把畫面推到**上一個**狀態，永遠慢一步。改成把訊號收進一份清單，commit 之後才發。
- 2026-09-10 票 10：**`/api` 底下的每一個回應都帶 `Cache-Control: no-store`**（門禁補的）。這不是
  最佳化：Berth 原本一個快取 header 都不送，瀏覽器就對 `200` 套用它自己的啟發式快取——實跑抓到
  SSE 推來的重問拿回一份幾秒前的快取，畫面停在錯的狀態。plan §6 已補。
- 2026-09-10 票 10：**SSE 連上的那一刻先重問一次**。這條連線沒有補送，而「訂閱之前」包含那一頁
  自己載入的那幾百毫秒——實跑踩到：送單後那一筆在頁面還在連線時就完成了，畫面因此停在
  「已取得檔案清單」再也不動。同一行也涵蓋每一次重連。
- 2026-09-10 票 10：**SSE 端點不自己查斷線**。原本每秒 `request.is_disconnected()` 一次，而
  `EventSourceResponse` 已經有一個 task 在讀同一條 ASGI `receive` 通道——兩個讀者會互相把訊息搶走。
  等待也從「每秒醒一次」改成「佇列或關機，誰先來」：取消一個正在被喚醒的 `asyncio.Queue` getter
  是最細的那一段語意，而一條開著幾小時的連線會做上萬次那個動作。
- 2026-09-10 票 10：**IP 封鎖與帳密不對分得開了**（解掉 plan T1.9 的第四條）。2026-09-10 對 4.4.5 與
  5.2.3 各實測一輪：連續 5 次帳密錯之後第 6 次回 `403` + `Your IP address has been banned...`，
  **兩版一字不差**；而帳密錯本身在兩版都不是 403（4.4.5 是 `200` + `Fails.`、5.2.3 是 `401`）。
  所以登入端點上的 403 只有一個意思。被封之後其他端點回的是 `403 Forbidden`，與「沒有登入」同形，
  所以這個判定只放在登入那一支。brief §20.2 與 plan §8.1、T1.9 已同步。
- 2026-09-10 票 10：**`sync/maindata` 的 `rid` 掛在 session（SID cookie）上**（實測：不帶 cookie 每一輪
  都回 `full_update`）。所以 `Downloader` 把 HTTP client 握著不放，失敗那一輪才丟掉重造——重造就是
  重新開始，而重新開始本來就會拿到一次全量，兩邊自然對齊。增量那一輪的 `torrents[hash]` 只帶變動
  欄位（實測有的只剩 `{num_leechs, time_active}`），合併因此在 adapter 的 `MaindataCursor` 裡。
  brief §20.2 已同步。
- 2026-09-10 票 10：**未完成時的 `completion_on` 4.4.5 是 `0`、5.2.3 是 `-1`**。完成判定寫 `> 0`
  對兩版都成立，寫 `!= 0` 會讓 5.x 上每一個剛加入的 torrent 都被當成已完成。brief §20.2 已補。
- 2026-09-10 票 10：**下載列表不做「即時」指示器**，無主 torrent 畫在**健康頁**的「下載迴圈」區塊
  而不是下載列表（兩件都是使用者拍板）。DESIGN.md 的這塊板沒有動畫也沒有 spinner，值自己換就是
  訊號本身；而下載列表的每一列都該是使用者自己送的，無主 torrent 問的是「整條線還動得了嗎」。
  記在 `.scratch/m1/live-jobs-shape.md`。
- 2026-09-11 票 11：**一個 Job 只有一列 `plans`**（`job_hash` 上是 unique index），plan §2.3 的欄位表沒說。重跑 planning 把它整份改寫而不是再長一列：不然 `GET /api/plans/{id}` 要先回答「哪一個 id 才是現在那一份」，而 `plan_items` 會在每次重跑之後多一份重複的決定（票上的重入驗收）。上一份留在時間線；`created_at` 因此是**算出這一份的時間**。已回寫 plan §2.3。
- 2026-09-11 票 11：**`unmatched` 不擋自動入庫**。plan §3.1 寫的是「全 high/medium 才 `importing`」，而 unmatched 一律是 low——但那不是低信心，是一個**已經做完的決定**（brief §7.6：這是一個節目，但它不是 TMDB 上的任何一集，檔案留在 complete 原位）。動漫批次幾乎每一包都夾著一兩個發佈方自己編號的 SP，擋下去等於 §11.2 T1.6 的「三種類型各一部不經人工入庫」永遠達不到。它仍然數進 `summary.low`，畫面上看得見。已回寫 plan §3.1，並有一條釘住的測試。
- 2026-09-11 票 11：**pre-plan 不在 poller 那一輪做**，由 `planner_runner` 下一輪補（plan §3.1 把它寫成 `metadata_ready` 的副作用）。理由是那一輪的失敗理由不該綁在一起：poller 一輪要為幾十筆 job 做事，而 pre-plan 要讀快照、跑解析器；poller 的一輪失敗會退避到 5 分鐘，而那與「這一包對不對」無關。已回寫 plan §3.1。
- 2026-09-11 票 11：**掃描包含 `planning`，不只 `completed`**（plan §3.2）。Berth 在算到一半時被關掉的話那一列會停在 `planning`，只掃 `completed` 就再也沒有人會碰它。同理 `POST /replan` 收 `completed` / `planning` / `review` 三種，**`importing` 不收**——那一份計劃已經被採信，而 importer 正照著它動檔案（票 12）。
- 2026-09-11 票 11：**迴圈之間的提示是一個沒有內容的喚醒訊號**（`services/hints.py`），不是 plan §3.2 寫的 `asyncio.Queue`。同一段的下半句是「DB 狀態才是真相；程序重啟後由定時掃描補上」——而掃描本來就找得到同一批 job，佇列裡那個 hash 因此不帶任何資訊，只留下三個要回答的問題（重複的 hash 去不去重、滿了丟哪一筆、重啟之後裡面那幾筆誰來補）。已回寫 plan §3.2。
- 2026-09-11 票 11：**一筆 Job 算計劃時爆掉不拖累同一輪的其他人**（code-review 前自己抓到）。迴圈那一層本來就接了例外，但那個接法會讓這一輪剩下的 job 全部跳過——而掃描照 `added_at` 排，所以一筆解析不了的 torrent 會停在 `planning` 並在每一輪都排最前面，後面那幾筆永遠等不到自己的計劃。
- 2026-09-11 票 11：**mediainfo 是模組層函式（形狀同 `adapters/fs.py`），不是 `ServiceClientFactory` 的一員**。它沒有位址、沒有憑證、沒有連線可以握——它讀的是這台機器上的一個檔案。`probe()` 同步，由 `services/plan.py` 以 `asyncio.to_thread` 呼叫（libmediainfo 是 C 函式庫，呼叫的那一刻整條執行緒都在等，而同一個迴圈也是 SSE 的來源）。
- 2026-09-11 票 11：`FileEntry` 多一欄 **`duration_s`**（plan §4.2 的欄位表沒有），**`None` 是「還沒量」不是 0**：pre-plan 那一輪檔案還在下載，而分類器拿它把短的正片降為 extra——分不開的話下載中的每一個檔案都會在預估裡變成 extra。解析器仍然沒有 IO。已回寫 plan §4.2。
- 2026-09-11 票 11：**`PlanSummary` 住在 `domain/`** 而不是 `models/`（plan §2 說 `*_json` 的 model 集中在 `models/`）。理由與 `MediaSnapshot` 完全一樣：`api` 依契約不 import `models`（§1.3），而這一格 API 直接送出去。import-linter 當場抓到。已回寫 plan §4.2。
- 2026-09-11 票 11：**被 Route 政策擋下的 medium 保留 `target_path`**，推翻 plan §4.2 的「review 沒有目標路徑」。那一格回答的是「它會去哪裡」，而這條政策說的是「先問一句」不是「不知道」——季集是算得出來的，只差一次點頭。
- 2026-09-11 票 11：**`review` 那一條轉換不另外寫 `plan_generated`**（plan §3.1 的表把它放在 auto 那一條）。一個轉換一筆事件；`review_required` 自己帶同樣的計數加一個說得出下一步的理由。
- 2026-09-11 票 11：**`job_files.release_info_json` 這一票不填**（plan §3.1 說 planning「更新 `job_files`」），只填 `kind` 與 `mediainfo_json`。逐檔的 `ReleaseInfo` 是 `planner._decide` 的中間值，服務層自己再算一次會與解析器分岔，而 M1 沒有東西讀它。記在票的 Comments。
- 2026-09-11 票 11：**Plan 畫在 `/jobs` 的就地展開區**，不是 `/jobs/:hash`（`jobs-shape.md` §4 把 Plan 列在「不做」，因為票 09 拍板不另建那一頁）。M1 沒有第二個地方放它，而 plan §7 的 `/jobs/:hash` 仍然留給 T1.7 的完整 Job 詳情。已回寫 plan §7。
- 2026-09-11 票 11：**Plan item 的理由不走 i18n**，原樣顯示英文並標 `lang="en"`。它們是解析器產生的句子，帶著檔名片段與數字（`the release name says season 1`）；要翻譯得先把理由變成封閉集合的 code + 參數，而那是 M2 Review Queue 的形狀。推翻 CLAUDE.md「UI 文案一律走 i18n key」的字面，與「服務回的原文不翻譯」同一個道理。
- 2026-09-11 票 11：**這一塊 UI 不用信號色**（DESIGN.md 的 The One Meaning Rule）。處置與信心是分類不是狀態（The Role Is Not A State Rule），而那一列的狀態格已經塗過一次漆了；要人看的那幾列改用**線變重**（`rule-strong`），與失敗那一列同一種語彙。
- 2026-09-11 票 11：`JobOut` 多兩格 **`plan_id`** 與 **`replannable`**。前者讓畫面決定要不要去要那一份逐檔的決定（不必先打一次 404），後者與 `retryable` 同一個規矩——「這一筆現在按得了什麼」在後端算，前端不重算一份。
- 2026-09-11 票 11：**`JobHints` 在 lifespan 裡建，不是 `create_app`**（實測抓到）。它裡面是一個 `asyncio.Event`，而 Event 認第一次 await 它的那個事件迴圈——同一個 app 起兩次（`test_app.py` 就是這樣跑的）會拿到「bound to a different event loop」。迴圈與它同生同滅，所以它本來就屬於那一段。
- 2026-09-11 票 11 code-review：**`Contents` 型別**（檔案清單 + 內容根那一層）。原本三個呼叫端各算一次 prefix，而其中兩個是從整包算、一個是從「要下載的那些」算——使用者在 qBittorrent 上取消勾選了根目錄外的檔案時兩者會不一樣，後果是靜靜地查不到那一列 `job_files`（mediainfo 跳過、`job_file_id` 變 `None`）。
- 2026-09-11 票 11 code-review：時間線那三筆事件與展開區的計劃**共用同一組 i18n 鍵**（原本兩份字面相同的翻譯）；下載列表的「重試」與「重新規劃」收成同一個 `Action` 元件；三把沒有人用的 key 刪掉。
- 2026-09-15 票 12：**`ledger` 比 plan §2.3 多三欄**——`action`（review 之後重新規劃會把 `plan_items` 整份換掉，帳本要自己記得當時鏈接的是什麼，`plan_item_id` 因此是 `SET NULL`）、`resolve_attempts` / `resolve_after`（`jellyfin_resolver` 的排程要活過重啟）。**inode 與 device 存 TEXT**：Windows 的 `st_dev` 實測 `11550084160259632778`（票 09），超過 SQLite INTEGER 的有號上限。plan §2.3 已回寫。
- 2026-09-15 票 12：**`importing` → `review`** 是 plan §3.1 表上原本沒有的轉換（§3.3 只寫了「進 review」）：目標上有別人的檔案時，其餘不衝突的檔案照樣鏈接，整筆停下來並寫 `review_required(target_exists)`。`ReviewReason` 多一種。plan §3.1 已補。
- 2026-09-15 票 12：**「不可跳過」定義為正片**（票面只寫「不可跳過」）。字幕與特典鏈接不成只記在那一列上、不擋 `imported`——那一集仍然看得了，整季擋下來換不到任何東西。plan §3.1 已補。
- 2026-09-15 票 12：**Jellyfin adapter 只加 `items(library_id, item_types)`**，推翻 plan §8.2 的 `find_series` / `find_episodes`。兩段查詢的比對要看 Route 與帳本，adapter 不認得它們（與票 08 把多標題展開搬出 `IndexerSearch` 同一個理由）。plan §8.2 已改。
- 2026-09-15 票 12：**MergeVersions 以存下的任務 Id 觸發**（票面寫法），推翻 plan §8.2 原本的「每次 `GET /ScheduledTasks` 找名稱含 Merge 的任務」；而且**放在反查成功之後**而不是入庫當下：合併要 Jellyfin 已經看得到那些檔案，入庫那一刻它多半還沒掃完。plan §8.2、§3.2 已改。
- 2026-09-15 票 12：**反查也比 `MediaSources[].Path`**（brief §20.1 只寫比 `Path`）：多版本合併之後第二個版本的檔案不是 item 自己的 `Path`（brief §7.7）。代價是 `/Items` 帶整份 MediaSources，媒體庫大的時候那一支很重——記在票的 Comments，M2 對帳時再看要不要分段取。
- 2026-09-15 票 12：**`jellyfin_resolver` 不是事件驅動**，每 15 秒醒一次看有沒有到時間的帳本，推翻 plan §3.2 的「事件驅動」。第一次反查本來就排在入庫 30 秒後，importer 那一刻叫醒它也只會看到「還沒到」。plan §3.2 已改。
- 2026-09-15 票 12：**迴圈之間的提示一個接收者一份**（poller → planner；planner 與入庫重試 → importer）。`JobHints` 裡是 `asyncio.Event`，而它是所有等待者一起清的——共用一份時，正在忙的那一個醒來清掉訊號，另一個就漏了。
- 2026-09-15 票 12：**事件去重在 `record_event` 裡查最近一分鐘**（比鍵排序後的 payload），沒有加一欄 payload hash。**使用者按下的重試是界線**：重試之後發生的事就算與之前一模一樣也照寫（code-review 抓到：不設界線的話，重試之後又同樣失敗的那一筆會被吞掉，時間線停在「重試」而狀態是入庫失敗）。
- 2026-09-15 票 12：`guarded`（一筆 Job 的一輪爆掉不拖累同一輪的其他人）從 `services/plan.py` 搬到 `services/jobs.py`，planner 與 importer 共用；`_counts` 改名 `plan_counts`（importer 停下來時寫的 `review_required` 帶同一組計數）。
- 2026-09-15 票 12：fs adapter 的 **`link()` 會建目標那幾層資料夾**（守衛之後才建），**`EXDEV` 的訊息多說兩邊各在哪個掛載上**（仍是同一個 `errno` 的 `OSError`）。目標已存在時照樣丟 `FileExistsError`，由 importer 比 inode——不先 `exists()` 再鏈接，否則守衛會被繞過。plan §8.6 已補。
- 2026-09-15 票 12：`tests/unit/test_entrypoint.py` 與 `test_qbittorrent_preseed.py` **在這台機器的 PowerShell 裡紅**，與這一票無關：`bash` 先解析到 WSL 的 `System32\bash.exe`，它不認 `C:/…` 形式的腳本路徑（exit 127）。把 Git Bash 放到 PATH 最前面之後 9 條綠、剩 `test_entrypoint.py` 的兩條（chown 替身沒有記錄到呼叫）——**在乾淨的 HEAD worktree 上同樣是這兩條紅**。記在票的 Comments，留給票 15 的收尾。
- 2026-09-15 票 12 code-review：**`target_exists_foreign` 改名 `target_unmanaged`**（plan §3.3、票上驗收的原文）。`foreign` 在 CONTEXT.md 的 **Unmanaged** 的 _Avoid_ 裡，而「媒體庫裡不是 Berth 建立的檔案」正是 Unmanaged 的定義。同一輪：入庫失敗的重試按鈕叫「再試一次入庫」而不是「重新入庫」——後者是 CONTEXT.md 的 **Reimport**（M2）；`link_failed` 只有擋住入庫時才是紅字，擋不擋由後端寫進 payload 的 `blocking`（DESIGN.md 的 The One Meaning Rule）。
- 2026-09-15 票 12 code-review：**resolver 每一輪把還沒找到的路徑再通知 Jellyfin 一次**。plan §3.3 寫「Jellyfin 通知失敗只記 event……resolver 之後會再嘗試」，而原本的 resolver 只重試查詢、從不重送通知——入庫當下那一次沒送到，或 Berth 在狀態落地與通知之間被關掉，Jellyfin 就根本不知道要去掃，6 次查詢只是在等它自己的排程掃描。路徑級通知是冪等的。plan §3.2 已補。
- 2026-09-15 票 12 code-review：**`jellyfin_item_resolved` 一筆 Job 一行、只帶 `count`**，推翻 brief §5.2 的 `jellyfin_item_resolved(item_id)`：一季 24 集的時間線不該被 24 行「找到了」淹沒，item id 在帳本上。
- 2026-09-15 票 12 code-review：resolver 一輪只 commit 一次，所以 `ServiceError` 以外的例外會把整輪回滾、`resolve_attempts` 不長，那一批每 15 秒重問一次永遠用不完 6 次。唯一會在比對時丟例外的 `relative_to` 改成逐筆略過。`EXDEV` 的訊息在兩邊掛載點相同時改說「掛載底下的檔案系統把它們分開了」（mergerfs、btrfs 子卷、ZFS dataset），不再叫已經只掛一個父目錄的人去掛同一個父目錄。入庫完成的推播移到通知 Jellyfin 之前。
- 2026-09-15 票 12：下載列表時間線的六種新事件、兩個理由與「再試一次入庫」是這一票做的前端（票面沒寫 UI）。不做的話後端一寫這些事件，時間線就只剩原樣的型別字串。沒有新頁面、沒有新元件，所以沒有走 `/impeccable shape`；實跑時以 playwright 對真的那一套看過時間線。
- 2026-09-15 票 12 實跑：**Jellyfin 的路徑通知對從沒掃到過內容的媒體庫無效**（`lscr.io/linuxserver/jellyfin:latest` 已經是 **12.0.0**；實測加查核原始碼，brief §20.1）。套件內的三個媒體庫一開始一定是空的，所以第一次入庫一定踩到，而原本的 resolver 會把 6 次反查白白用完、寫出一筆假的 `jellyfin_item_unresolved`。resolver 改成**沒找到兩次以上就跑 Jellyfin 的 `RefreshLibrary` 排程任務，之後最晚 10 分鐘再看**——推翻 plan §3.2 字面的「1h ×3」，只在請了掃描之後。不用 `POST /Library/Refresh`（在請求裡等整次掃描做完），也不用 `POST /Items/{id}/Refresh`（master 沒有 `Recursive`）。plan §3.2、§8.2 已補。
- 2026-09-15 票 12 實跑：診斷時**手動對 TV 媒體庫打過一次 `POST /Items/{id}/Refresh`**（204、沒有任何效果：兩分鐘後仍是 0 個 item、log 沒有一行），它不是入庫流程的一部分。修好 resolver 之後停掉 berth、換 image 再起來，讓已經過期的反查由新程式碼接手——沒有手動改帳本、沒有手動觸發掃描。
- 2026-09-15 票 13：**媒體庫的程式碼叫 `inventory`**（`services/inventory.py`、`GET /api/inventory`、`web/src/inventory/`、`InventoryPage`），前端網址維持 plan §7 的 `/library/:routeSlug`。理由是 CONTEXT.md 規定程式碼的 `library` 一律指 Jellyfin Library；新增名詞 **Inventory**。code-review 抓到前端一度仍用 `Library*`（`LibraryRoute` 還撞上名詞表的 Library Route），同一輪全部改掉。plan §6、§7 與 CONTEXT.md 已改。
- 2026-09-15 票 13（使用者拍板）：**牆上是這條 Route 上有 Job 的全部作品**，加上帳本裡目標落在它底下的，不只票面的「已入庫作品」。理由是「有待審」篩選要找得到一個檔案都還沒入庫的作品。卡片狀態六種、依序取第一個成立的（失敗 → 待審 → 下載中 → 已入庫 / 部分 / 沒有檔案），只有需要人的那幾格塗漆。
- 2026-09-15 票 13（使用者拍板）：**各集入庫狀態五種**（已入庫 / 卡住 / 下載中 / 缺 / 未播出），推翻票面的三種：停在待審的那一集說成下載中是騙人，還沒播的集說成缺也是。季列的 `N / M 集入庫` 由後端算、與卡片同一個分母（code-review 抓到前端自己算時分母不一致）。
- 2026-09-15 票 13（使用者拍板）：**深連結的主機 = 選填的 `settings.services.jellyfin.public_url` + 推導**（Seerr 的 `externalHostname`）：既有服務用 `base_url`，套件內用瀏覽器的主機名加 `base_url` 的 port——後者只能在前端補完。新增 `GET|POST /api/settings/jellyfin`，放在服務設定頁自己一個區塊（不塞進 `ServiceCard`，健康頁共用那個元件）。plan §2.1、§6 已改。
- 2026-09-15 票 13：**深連結是 `{主機}/web/#/details?id=…`，不帶 `serverId`**，推翻 brief §12 沿用 Seerr 的 `#!/details?id=…&serverId=…`。2026-09-15 對 12.0.0 以 playwright 實測不帶照樣開到 Series 與 Movie 的詳細頁；10.10 / 10.11 沒有測過不帶的形式，已在 brief §20.1 註明。brief §12、§20.1 已改。
- 2026-09-15 票 13：**帳本多一欄 `jellyfin_series_id`**（migration `7c3e5a9b2d41`）：劇集卡片要連作品而不是某一集，而 `/Items` 的 Episode 自己帶 `SeriesId`（同日實測），反查時一起寫下。**既有的列不回填**（沒有 Jellyfin 回填不了），那些劇集卡片照實說「Jellyfin 還在掃描」——M2 的對帳重新反查時補上。plan §2.3、§8.2、brief §20.1 已改。
- 2026-09-15 票 13：**這一支 migration 升版不用 `batch_alter_table`**。ledger 有兩個外鍵，batch 重建表時它們的順序是反射出來的、不固定，「降版再升版是同一份 schema」那條測試因此偶發紅（這個分支上四次紅兩次，乾淨的 HEAD worktree 五次全綠，抓到差異就是兩個外鍵換了位置）。改用 SQLite 原生的 `ADD COLUMN`，model 那一欄帶同一個 `server_default`；修好之後連跑十次全綠。
- 2026-09-15 票 13：`GET /media/{id}` 多帶 `files` / `unmatched` / `versions` 與各集、各季的入庫狀態（plan §6 的 media 列本來就寫著「檔案 + Unmatched + 版本」）。判定住在 `services/inventory.py` 的 `read_holdings`——code-review 指出它原本塞在 `services/media.py` 讓那一支因兩個不相干的理由改動。多版本以**所在資料夾**分組（code-review：同一部作品入庫到兩條 Route 時會被誤列成版本）。
- 2026-09-15 票 13：電影卡片只有一個版本時寫「1 個版本」，推翻 shape brief 原本的「已入庫」——那一格的色塊已經寫著「已入庫」，計數行再說一次是重複。shape brief 已改。
- 2026-09-15 票 13：`JobTimeline.tsx` 的 `ReturnType<typeof useTranslation>['t']` 在媒體庫的 i18n 鍵加進來之後觸發 TS2589（型別展開太深），改用 `TFunction`。同一個檔案在 HEAD 上就過不了 `prettier --check`（票 12 的驗證沒跑 `format:check`），本票的 `pnpm format` 順手修好。
- 2026-09-15 票 13：季集代號與 `formatEpisode` 收成 `components/episodes.ts`（原本 `jobState.ts` 與 `SeasonList.tsx` 各一份，後者匯出非元件還違反 fast refresh 的 lint）；探索牆與媒體庫共用 `WALL_GRID`，頁首導覽與媒體庫的切換列共用 `NAV_BOX`（不含內距——`px-4` 與 `px-3` 疊在同一個元素上誰贏看的是 CSS 先後）。
- 2026-09-15 票 13 實跑：真環境（票 12 的驗收那一套）的 berth 換上本票 image 之前，先把資料庫以 sqlite backup API 備份成 `/config/berth.before-ticket13.db`（另存一份在 session scratchpad）。沒有手動改帳本。
- 2026-09-15 票 13 之後（使用者拍板，無票）：**媒體庫改成像 Jellyfin 那樣瀏覽**，推翻 brief §12 的「媒體庫頁的價值在『狀態與修正』，不在『取代 Jellyfin 播放』」。範圍：整個 Jellyfin 媒體庫疊上 Berth 狀態（不只 Berth 經手的）、繼續觀看、下一集、已看 / 未看可切換並寫回 Jellyfin、類型與年份排序、Jellyfin 的圖、選季選集；播放仍跳 Jellyfin，內嵌播放器仍延後（電視與手機上的 Jellyfin app 本來就取代不了）。探索與媒體庫共用 `/media/:id`，作品在 Jellyfin 裡時觀看區放最上，不採 Sonarr 那種另建一頁。排成新的 **M1.5**（M1 驗收後、M2 前），M1 的票 14、15 不變。brief §1.1、§1.2、§12、§13、§17、§18、§19 與 plan §11.2b 已改；查證見 `docs/research/library-browsing.md`（brief §20.8）。
- 2026-09-15 M1.5 查證（無票）：瀏覽要用的 Jellyfin API 都做得到，但**伺服器 API key 代讀時 Jellyfin 只套用一部分媒體庫權限**（帶 `parentId` / `ids` / `seriesId` 的查詢與 Genres / Years / Filters 不套），權限要由 Berth 自己擋——plan §11.2b 的前置已寫明，這一條只讀原始碼，拆票時要用受限使用者實測。另兩個事實：brief §20.1 的「10.11 第一次掃描後回 0」在 12.0.0 沒有重現（另起一次性容器、跑完即刪）；`/Items` 靜默忽略不存在的參數。對真環境的 Jellyfin 只寫過已看 / 未看切換，已還原（大熊餐廳 S03E01，讀回與開始時相同）。brief §19 多兩條待決（帳號狀態、圖片載入）；brief §20.1、§20.7 與 plan §8.2 的那一條都補上「12.0.0 沒有重現」。
- 2026-09-15 Jellyfin 12 查證與決定（使用者拍板，無票）：**12.0 起劇集原生合併多版本**，推翻 brief §1.2、§7.7、§20.1 與 PRODUCT.md 的「劇集多版本必須靠 MergeVersions」（對 10.10 / 10.11 仍成立）。決定：兩條版本線都支援，12 以上不裝也不觸發插件，**10.x 的支援在 Jellyfin 13.0 正式發佈時拿掉**；套件內 image 釘 `version-12.1ubu2604`；多集檔與同起始集的單集送審核（12.x 會把它們併成一集、藏掉後面的集）。查證同時找到兩個現行 bug：媒體詳情的劇集版本名照 10.x 算、精靈第 3 步重試在 12.x 回 403。以上全部排進插入的 M1 票 14b（15 之前）。brief §1.2、§7.7、§7.8、§16.2、§16.3、§18、§19、§20.1、§20.7 已改並新增 §20.9；PRODUCT.md、plan §9.1、§11.2 已改；`m0-experiments.md` 的「linuxserver 釘不了版本」已更正。查證另起兩個一次性容器（12.0.0 / 12.1.0）跑完即刪，對真環境只讀。
- 2026-09-15 M1.5 拆票前的四條待決（使用者拍板，全數照推薦，無票）：**媒體庫頁一個 Jellyfin 媒體庫一頁**，推翻票 13 的一條 Route 一頁（Route 退成入庫狀態的來源；一個媒體庫多條 Route 或有舊路徑時，同一批作品才不會出現在兩頁）；首頁上方放繼續觀看與下一集、下面維持探索；瀏覽時一併讀 Jellyfin 帳號 `Policy`，停用就結束 Berth 的 session，不縮短 session；Jellyfin 圖片由 Berth 代理。brief §13、§19 與 plan §11.2b 已改。
- 2026-09-15（使用者改決定，無票）：**只支援 Jellyfin 12 以上**，推翻同日稍早的「12.x 與 10.10 / 10.11 都支援、13.0 發佈時才拿掉 10.x」。使用者看過升級阻力（`jellyfin-12.md` §4：遷移失敗的 open issue、舊客戶端要升級、binhex 與 QNAP 社群套件還沒有 12）之後，仍選擇降低複雜度。MergeVersions 整段移除，既有 Jellyfin 低於 12 時精靈與健康檢查紅燈並說明升級注意，都在票 14b。brief §1.2、§7.7、§16.2、§16.3、§16.4、§18、§19、§20.7，PRODUCT.md，plan §11.2 與票 14b 已改。
- 2026-09-15 票 14（使用者拍板）：**精靈第 7 步只新增、不改不刪**，推翻 plan §9.3 第 7 步的「重跑覆寫同一組列，沒被勾到的 Route 刪掉」。已經有 Route 的媒體庫的選擇略過、勾選表上鎖住；slug 與整張表比（設定頁建的 `tv-2` 也佔名字）。選錯了的出路是每條 Route 底下同一個明確的刪除。只把刪除拿掉還不夠：舊寫法以 slug 認 Route，重跑時換一個目標會覆寫已經被帳本認著的 `target_path`，而 `by_library` 一庫只認一條，會把設定頁建的第二條當成精靈那一條改掉。plan §9.3 已改。
- 2026-09-15 票 14（使用者拍板）：**新建的 Route 檢查紅燈時照樣建立、維持停用**；**從停用到啟用要那一輪全綠**，否則 409 `route_unhealthy`，名稱與 profile 照樣存下。已啟用的 Route 這一輪變紅不會被停掉——它的紅燈本來就擋送單，默默替人停用是另一種隱式改動。精靈跑完之前由第 7 步建的 Route 仍然直接啟用（它紅著就擋完成，與票 09 的決定一致）；**跑完之後重跑新建的，照這一條紅燈就停用**——code-review 抓到原本兩個時期都直接啟用，精靈跑完之後就沒有完成條件擋著了。
- 2026-09-15 票 14（使用者拍板）：**PUT 只改名稱、profile、啟用**；slug 與寫入目標建立後不可改（category 與 complete 子目錄由 slug 導出、帳本以目標路徑認 Route）。修改一律重跑五條纜繩，連只改名稱也是——票面「新建或修改的 Route 跑一次檢查」照字面做。plan §2.2、brief §4.3 已補。
- 2026-09-15 票 14：**刪除被 Job 或帳本引用時拒絕**（409 `route_in_use`）；帳本不記 Route，以 `owning_route`（最深的那一條）算。刪除不動 qBittorrent 的分類與 complete 子目錄。`GET /routes` 帶引用數，設定頁在按之前就不給刪除鍵、直接說出路（停用）；競態時靠同一個 409。
- 2026-09-15 票 14：**停用的 Route 不算進健康總結與精靈第 7 步的完成條件**（`routes_health`、`routes_ready`）。票面沒寫，是「停用是刪不得時的出路」之後的直接後果：一條沒有人會送單過去的 Route 紅著，不該讓整台 Berth 永遠 degraded。停用的 Route 照樣檢查、照樣逐條顯示。
- 2026-09-15 票 14：**`/api/routes` 與 `/api/jellyfin/libraries` 跟著 `setup/*` 的門禁規則**（精靈跑完之前匿名開放、之後只有 admin），不是 `settings/*` 的「永遠只有 admin」。精靈第 7 步的刪除打的就是 `DELETE /routes/{id}`，而精靈跑完之前還沒有人登入得了。規則仍在門禁（`OPEN_UNTIL_SETUP_PREFIXES`），沒有 router 相依；`/jellyfin` 只開到媒體庫清單那一支（code-review：整個前綴會讓之後掛上的端點也匿名開放）。plan §6 已改。
- 2026-09-15 票 14：**新增 Route 的媒體庫與路徑向 Jellyfin 現查**（`GET /jellyfin/libraries`，建立時再查一次），不讀第 3 步的快照——一庫多條的第二條路徑多半是之後才在 Jellyfin 加的；認媒體庫用 `ItemId`。同一個目標兩條 Route 拒絕（`target_taken`），slug 仍由媒體庫名導出（`tv-2`），名稱是另一個欄位。
- 2026-09-15 票 14：`RouteOut` 多 `id`；精靈的 `Profiles` 抽成 `components/ProfilePicker.tsx`，刪除做成 `components/RouteDelete.tsx`，設定頁與泊位 4 共用；`Checkbox` 多 `disabled`；API client 多 `apiPut` / `apiDelete`。`/settings/routes` 走 `/impeccable shape`（`.scratch/m1/route-settings-shape.md`，使用者拍板三題：兩頁共用子分頁列、綠燈收起紅燈或停用展開、新增 Route 在清單下方就地展開）。
- 2026-09-15 票 14 code-review：**Route 檢查與精靈認 Jellyfin 媒體庫改用 `ItemId`**（沒有 id 的舊資料才用名字），推翻票 09 起 `library_path` 纜繩與精靈索引的「以名字認」。一庫多條成為正式功能之後，媒體庫在 Jellyfin 改名、或有兩個同名的，第二條 Route 就會驗到別的媒體庫。
- 2026-09-15 票 14 code-review：**電影媒體庫的 Route 不收 anime profile**（422 `profile_unsupported`）。票面寫的是「劇集可挑不同 profile」，原本只有前端把選項藏起來。
- 2026-09-15 票 14 code-review：`LibraryChoice.selected` 改名 `has_route`（語意早已是「已經有 Route、鎖住」）；`ManagedRouteOut` 多 `in_use`，前端不再重算「刪不得」；健康頁與設定頁的 Route 身分帶收成 `components/RouteIdentity.tsx`；`SettingsTabs` 改成一份清單；兩處 Jellyfin collection type 從 `.label` 改 `.value`（DESIGN.md 的 Machine String Rule，`RouteStep` 那一處是既有的債）；刪除警告不再把 category 插進散文。
- 2026-09-15 票 14 code-review 留著沒改的（理由記在票的 Comments）：`create_route` 與精靈 `_plan` 的驗證沒合併、API 五個端點的 `try/except`、`routeRefusalOf` 與 `refusalOf` 沒泛型化、「已是哪一條」的名字在前端反查、拒絕理由在 Python 端是字串。
- 2026-09-15 票 14 待使用者確認：**停用的 Route 不算進完成條件**，加上 `/api/routes` 在精靈跑完之前匿名開放，合起來代表「精靈跑完之前，匿名呼叫者可以把紅燈 Route 停用再按完成」（spec 軸 code-review 指出）。畫面沒有這個入口，而那一刻本來就沒有任何帳號，與 `setup/*` 在同一時期整組匿名開放的暴露面相同；記下來而不是再加一條規則。
