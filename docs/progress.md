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

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-09-07 拆票：M0 只建 `users`、`sessions`、`settings`、`routes`、`events` 五張表，plan §2 其餘的表在需要它們的里程碑用 Alembic 增量加。推翻 plan §11.1 T0.2 的「schema 完整」驗收。理由是不為未來需求預先建表，Alembic 隨時可加。
- 2026-09-07 拆票：M0 不設「adapters 第一版」的獨立任務，改成按精靈步驟垂直切票（票 05–09），每張票帶進自己需要的 adapter 能力、Fake 與契約測試。推翻 plan §11.1 的 T0.4 / T0.6 分法。理由是 T0.6 一票塞不進一個 session，而單獨的 adapter 票沒有可示範的成果。
- 2026-09-07 拆票：brief §20.6 的實驗排在 compose 之後（票 04，而非 M0 第一張）。推翻 brief §17「實驗最先」的順序。理由是實驗需要真的 Jellyfin 與兩個版本的 qBittorrent，compose（票 03）已經提供；命名模組要到 M1 才寫，模板在那之前凍結即可。
- 2026-09-07 票 01：前端裝 React 19（現行 stable，`create vite` 的預設），推翻 plan §1.4 的「React 18」，已回寫 plan。
- 2026-09-07 票 01：plan 沒寫的四件事補進 plan §1.2 / §1.3 / §1.4 —— Python 3.13 與 Node 24 為執行環境、CLI 用 stdlib argparse、`db` 在 import-linter 契約中位於 `models` 之下 `domain` 之上、Alembic 的 `env.py` 從 `db/` 移到 `migrations/`（它要 import `models`，留在 `db/` 會違反契約）。
- 2026-09-07 票 01：CI workflow 已寫但未實跑，repo 還沒有 GitHub remote。建 remote 後第一個 PR 要回票 01 勾掉該條驗收，票在那之前維持 `ready-for-human`。
- 2026-09-07 票 01：brief §16.1 / §16.2 要求 README 寫的部署前提（硬鏈接限制、qBittorrent 版本下限、MergeVersions、TMDB 歸屬、秘密不加密）延到票 03，已記在該票的 Comments。
