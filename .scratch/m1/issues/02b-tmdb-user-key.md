# 02b — 拿掉內建 TMDB 憑證，改成使用者自備 key

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工（排在票 02 之後、票 03 之前，因為票 03 起每一張都要有憑證才跑得動）

**讀:** brief §16.3（服務來源表的 TMDB 那一列）、§20.7（TMDB 那一段）；plan §8.3、§9.3 第 6 步；
`.scratch/m0/issues/08-wizard-services.md`（第 6 步原本的形狀）

## 做什麼

**決定（2026-09-09，使用者拍板）：Berth 不內建任何 provider 的 API key。** TMDB 的憑證改由使用者
自己申請並填入，精靈第 6 步從「可跳過的覆寫」變成**必填的閘門**：沒有一把測得過的 TMDB 憑證就
不能完成設定。

這推翻 M0 票 08 已經做完的東西（`adapters/tmdb.PROJECT_CREDENTIAL`，Seerr 的做法），也削掉
brief §16 的「開箱即用」一角 —— 使用者現在必須先去 themoviedb.org 註冊、建 API key、貼回來。
這個代價是知情且接受的：不替所有使用者背一把共用憑證。

**內部程式碼直接刪，不留 fallback。** 憑證只有一個來源就是設定，`credential()` 不再有 `or`。

### 範圍

| 層 | 要改的東西 |
| --- | --- |
| 後端 | `adapters/tmdb/__init__.py` 的 `PROJECT_CREDENTIAL` 與 `__all__`；`services/tmdb.py` 的 docstring、import、`credential()` 的 fallback、`TmdbSetupStatus.using_project_credential` |
| 精靈 | 第 6 步變必填閘門：沒測過或測失敗就不能前進；`POST /api/setup/complete` 也要擋 |
| 前端 | `setup/SourceStep.tsx` 的第 6 步形態、`i18n/resources.ts` 的文案（zh-Hant 與 en 各一份，現在寫的是「內建一把專案級憑證，什麼都不填也用得了」）、`test/fixtures.ts` 的預設 |
| 測試 | `tests/integration/test_adapter_contracts.py`（3 處）、`test_setup_api.py`、`test_setup_source.py` |
| 文件 | brief §16.3 表格那一列與 §20.7；plan §8.3、§9.3 第 6 步；README 的部署前提（要先申請 key，附取得步驟）；CHANGELOG |
| 實驗腳本 | `scripts/experiments/anime_episode_source.py` 的 `tmdb_token()` 現在是用 regex 刮 adapter 原始碼，改成讀環境變數（`TMDB_API_KEY`），並在 README 的實驗腳本段寫明 |

`credential_auth()` 的「v3 key 與 v4 token 兩種形狀都收」**保留**：TMDB 的帳號頁同時發兩種，
使用者貼哪一種都該成立（plan §8.3，2026-09-08 實測）。

### UI

第 6 步是既有頁面的形狀改變，不是新頁面，所以走 `/impeccable` 的 `critique` 而不是 `shape`。
文案要告訴使用者**去哪裡拿 key**（themoviedb.org → 設定 → API），別只說「必填」。

## 驗收

- [ ] `PROJECT_CREDENTIAL` 從 repo 中完全消失（`grep -r PROJECT_CREDENTIAL` 零命中，含測試與腳本）
- [ ] `services/tmdb.credential()` 沒有 fallback；`settings.services.tmdb.api_key` 是唯一來源
- [ ] 精靈第 6 步沒有通過測試就不能前進，`POST /api/setup/complete` 在缺憑證時回錯而不是放行；
      兩者各有一個測試
- [ ] v3 key 與 v4 token 兩種形狀仍然都收，測試涵蓋兩種
- [ ] 前端第 6 步文案（zh-Hant + en）寫明必填與取得 key 的位置；`/impeccable critique` 跑過，
      文字對比仍 ≥ 4.5:1
- [ ] `scripts/experiments/anime_episode_source.py` 改讀 `TMDB_API_KEY`，`--self-test` 仍綠，
      README 的實驗腳本段同輪更新
- [ ] brief §16.3 / §20.7、plan §8.3 / §9.3、README、CHANGELOG 全部同一個 commit 改完
- [ ] lint / type / test 全綠；playwright 實跑一次「沒填 key 走不完精靈」
- [ ] `docs/progress.md` 記一行 session 紀錄與一行偏差（推翻 M0 票 08 與 brief §16 的開箱即用）

## Comments

- 這張票是 M1 票 01 的連帶結果。票 01 原本把「TVDB 授權」當成不採用 TVDB 的主要理由之一，
  2026-09-09 更正為**錯的**：TVDB 的 v4 key 免費自助申請，ToS 擋的只是「內建一把發給所有人」。
  既然兩個 provider 在「使用者自備 key」這件事上對稱，內建 TMDB 憑證這條路就一併不走。
  維持 TMDB 的決定不變，撐住它的是 0.4 個百分點、Jellyfin 同源、第二個 provider 的成本。
- 精靈的索引站那一步（第 5 步）**維持可跳過**：沒有索引站只是不能搜尋，Berth 其餘功能還在；
  沒有 TMDB 則探索、季集快照、命名全部停擺，兩者不同級。
