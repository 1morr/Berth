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

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-09-07 拆票：M0 只建 `users`、`sessions`、`settings`、`routes`、`events` 五張表，plan §2 其餘的表在需要它們的里程碑用 Alembic 增量加。推翻 plan §11.1 T0.2 的「schema 完整」驗收。理由是不為未來需求預先建表，Alembic 隨時可加。
- 2026-09-07 拆票：M0 不設「adapters 第一版」的獨立任務，改成按精靈步驟垂直切票（票 05–09），每張票帶進自己需要的 adapter 能力、Fake 與契約測試。推翻 plan §11.1 的 T0.4 / T0.6 分法。理由是 T0.6 一票塞不進一個 session，而單獨的 adapter 票沒有可示範的成果。
- 2026-09-07 拆票：brief §20.6 的實驗排在 compose 之後（票 04，而非 M0 第一張）。推翻 brief §17「實驗最先」的順序。理由是實驗需要真的 Jellyfin 與兩個版本的 qBittorrent，compose（票 03）已經提供；命名模組要到 M1 才寫，模板在那之前凍結即可。
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
