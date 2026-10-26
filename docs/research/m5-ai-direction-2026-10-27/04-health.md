# 04 健康度實測（v0.3.0，main @ 5fc0bbc8）

日期：2026-10-27。實測環境：macOS、Docker 在跑、無 `.env`、shell 沒有 `TMDB_API_KEY`。

## 1. 結論摘要

- 全部檢查（`uv run pre-commit run --all-files`）**全綠**（13 項，約 15 秒）。
- 後端 `pytest -m 'not e2e'`：**4339 通過、2 失敗**、28 deselected（5 分 42 秒）。前端 vitest：**2179 通過、4 失敗**（皆在 `gates/knip.test.ts`）。失敗皆已記錄、未修。
- 真實服務 e2e **沒跑**：`tests/e2e/stack` 要 `TMDB_API_KEY`（精靈 TMDB 頁是閘門），本機沒有；且單次約 50 分鐘。改用 Fake 後端。
- 主流程（Fake 後端 `rss` + `import` 兩個情境）：加 Feed → 輪詢 → 12 集自動入庫、搜尋 → 送單（要點兩次）→ 約 2 分鐘內入庫 → 媒體庫「還沒進 Jellyfin」都走得通；沒有 console error（除登入頁的 401 噪音）。
- 主流程卡點：入庫完成後「等 Jellyfin 收錄」永遠不消失（Fake 的限制，非產品缺陷）；季表的「N / M 集入庫」數字與檔案區、媒體庫頁互相對不上（見問題 2）；Fake 下完整主流程要換兩個情境（`rss` 沒索引站結果、`import` 沒 RSS Feed 替身）。

## 2. 指令與輸出

### 2.1 全部檢查

```
$ uv run pre-commit run --all-files
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check for merge conflicts................................................Passed
check yaml...............................................................Passed
check toml...............................................................Passed
mixed line ending........................................................Passed
ruff check...............................................................Passed
ruff format..............................................................Passed
mypy.....................................................................Passed
import-linter............................................................Passed
prettier (web)...........................................................Passed
eslint (web).............................................................Passed
knip (web)...............................................................Passed
```

`pnpm -C web exec knip` 單獨跑也是 0 條（exit 0）。

### 2.2 後端 test

```
$ uv run pytest -m 'not e2e' -q --no-header -p no:cacheprovider
FAILED tests/integration/test_compose_hosts.py::TestSystemHostResolver::test_a_reserved_invalid_name_does_not
FAILED tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs
2 failed, 4339 passed, 28 deselected in 342.06s (0:05:42)
```

失敗 1，`test_compose_hosts.py:103`：

```
>       assert await SystemHostResolver().resolves("berth not a host") is False
E       assert True is False
```

`SystemHostResolver` 對一個含空白的保留無效名稱回「解得到」。推測是本機 DNS（macOS / 網路環境會把無效名稱劫持成可解析）造成，測試依賴本機解析器行為；單獨重跑仍紅。未驗證根因。

失敗 2，`test_rss_api.py:202`：

```
>       assert (listed["active"], listed["latest_episode"], listed["finished"]) == (2, 12, False)
E       assert (2, 12, True) == (2, 12, False)
E         At index 2 diff: True != False
```

單獨重跑仍紅。推測與日期有關：fixture 的 split-cour 第二 cour 2026-07-02 起播，12 集在今天（2026-10-27）已播完，`finished` 變 True；測試寫死「未完結」。這是時間炸彈型測試，未驗證根因。

### 2.3 前端 test

```
$ pnpm -C web test
 Test Files  1 failed | 114 passed (115)
      Tests  4 failed | 2179 passed (2183)
   Duration  22.56s
```

四個失敗都在 `web/gates/knip.test.ts`（knip 閘門的雙向驗證）：

```
FAIL |gates| gates/knip.test.ts > knip 閘門 > 沒有人 import 的 export 會報
AssertionError: expected [ 'files:src/health.ts', …(2) ] to deeply equal [ 'exports:HEALTH_LABEL' ]
- Expected  + Received
-   "exports:HEALTH_LABEL",
+   "files:src/health.ts",
+   "files:src/api/schema.d.ts",
+   "files:src/api/schemas.ts",

FAIL ... > 只在同一個檔裡用到的 export 也報：export 面保持最小
AssertionError: expected [ 'files:src/health.ts', …(2) ] to deeply equal [ 'exports:UNKNOWN' ]
FAIL ... > 合規的樹不報：外部的 uv、產生出來的型別檔不算
AssertionError: expected { status: 1, reported: [ …(3) ] } to deeply equal { status: +0, reported: [] }
FAIL ... > 改名字、改排版不會讓它紅
AssertionError: expected { status: 1, reported: [ …(3) ] } to deeply equal { status: +0, reported: [] }
```

在暫存小專案裡，knip 把 `src/health.ts`、`src/api/schema.d.ts`、`src/api/schemas.ts` 報成「未使用檔案」，也就是這份測試造的暫存專案沒有被 knip 認出入口。真專案的 knip 是綠的，所以是閘門測試本身在本機環境失敗（可能與暫存目錄位置或 knip 版本有關，未驗證）。這代表這個閘門的「會紅」「不會誤紅」兩個方向現在都不可信。

### 2.4 e2e（真實服務）

未執行。原因：

- `docs/development.md〈e2e〉`：`uv run --env-file .env python -m tests.e2e.stack` 需要 `.env` 內的 `TMDB_API_KEY`；本機沒有 `.env`、shell 也沒設。
- Docker 有在跑（`docker info` 成功，沒有任何 `berth-e2e-*` 容器）。
- 紀錄佐證：票 133（`.scratch/m4/issues/133-m4-acceptance.md`，Status: done）與 progress.md 有 CI e2e 紀錄，單次約 50 分鐘（pytest 45 分鐘）。本次沒有重跑，也沒有新的 e2e 證據。

### 2.5 Fake 後端

```
$ uv run python scripts/fake_setup_server.py --scenario rss    --port 8484 --config-root /private/tmp/claude-501/health/cfg
$ uv run python scripts/fake_setup_server.py --scenario import --port 8484 --config-root /private/tmp/claude-501/health/cfg2
```

前端 build 用現成的 `web/dist`（沒有重 build；未確認它與 main 的 HEAD 一致）。登入帳號 `skipper` / `harbour`。

## 3. 主流程逐步紀錄

全程是 **Fake 後端**：qBittorrent、Jellyfin、Prowlarr、TMDB、Mikan 都是替身。真正的產品程式碼（API、DB、poller、planner、naming、ledger、前端）是真的。Fake 看不出真實服務的行為。精靈沒走（兩個情境都是精靈已完成）。

| # | 情境 | 操作 | 結果 | 問題 |
| --- | --- | --- | --- | --- |
| 1 | rss | 開 `/` | 轉到 `/login`，登入 skipper 後進探索頁 | 登入頁 `/api/auth/me` 401 進 console error（2 筆，預期的噪音但會污染 console 檢查） |
| 2 | rss | 探索頁 | 兩條 feed 都顯示「TMDB 這一輪什麼都沒回」 | `rss` 情境無 TMDB 憑證；文案說「過一小時快取到期後會再問一次」，但沒說是憑證問題或怎麼辦（真實部署精靈有 TMDB 閘門，可能不會遇到） |
| 3 | rss | `/rss` 加 Feed：貼 Mikan 網址、劇集送進選 Anime、輪詢間隔選 1 小時、按「加入」 | Feed 列出現：「每 1 小時 · 上次輪詢 沒有紀錄 · 0 筆 · 劇集送進 Anime · 電影送進 Movies」，表單清空 | 「劇集送進」預設是 disabled 的「選一條 Route」，必選，OK。加入一次就成（無確認步驟） |
| 4 | rss | 按「立即輪詢」，等約 5 秒 | 12 筆 Feed Item；頁首出現 10 張待綁定 RSS Series 卡，每張帶「抓不到番組頁」錯誤（`connection refused`）；《与你相恋》自動綁定 | 輪詢按下去沒有進行中指示，只能等；待綁定卡片把整頁拉到約 7300px 高（截圖 01），Feed 列與表單被擠到頁面中段，新手要捲很久才找得到自己剛加的 Feed |
| 5 | rss | `/jobs` | 12 筆都已「已入庫」，「在路上 0」，預設分頁「在路上」空，要再按「看已入庫的」 | 預設落在空的「在路上」，要多點一下才看得到結果（空狀態有給捷徑按鈕，算可接受） |
| 6 | rss | `/media/tv:262000` | 詳情頁正常：12/12 入庫、RSS 訂閱區顯示 LoliHouse 第一批已確認 | 「等 Jellyfin 收錄 12」一直不消失（Fake Jellyfin 的限制） |
| 7 | rss | 同頁按「搜尋」 | 「2 個關鍵字都有回應」，「找到 0 筆」 | `rss` 情境的索引站替身沒有結果，所以搜尋 → 送單改在 `import` 情境走 |
| 8 | import | 換伺服器，開 `/media/tv:120089` | 被導到 `/login?redirect=…`，登入後回到原頁 | 重啟後 session 失效，符合預期；redirect 正常 |
| 9 | import | 「入庫到」選 Anime，按「搜尋」 | 「6 個關鍵字都有回應 … 索引站回了 6 筆，其中 5 筆重複、已合併」，1 筆結果 `[Berth-Demo] SPY×FAMILY S01 [01-03][1080p][CHT]`，預估 S01E01–E03，約 4 秒 | 結果表上方有「要列出哪幾類 符合 1」，意思不直觀；「入庫到」預設是「尚未指定」，沒選就不能搜（要自己選） |
| 10 | import | 按結果列的「送單」 | 該列展開確認區：「入庫到「Anime」…資料夾會是 SPY x FAMILY (2022) [tmdbid-120089]」，有「確認送單」「取消」 | 送單要點兩次（送單 → 確認送單） |
| 11 | import | 按「確認送單」 | 該列變「已送出」，下方「下載」段出現一筆「已送出」，qBittorrent 替身、hash `a783877b79bd`、進度 `—` | 進度欄是 `—`，沒有任何預期時間；時間欄只寫「現在」 |
| 12 | import | 停在頁面等（約 2.5 分鐘內） | 「下載」段自動消失（還沒了結 0），「檔案與版本」出現 5 個檔案（字幕 E01、正片 E01–E03 3 檔、特典 1 檔），皆「帳本對得上」 | 沒有看到中間狀態的轉場（腳本沒抓到），頁面不重整自己更新 |
| 13 | import | `/jobs` | 「已入庫 1」，預設分頁仍是空的「在路上」 | 同 5 |
| 14 | import | `/library` | 先落在「Movies」（「還沒有任何作品」）；切到 Anime 看到「還沒進 Jellyfin 1：SPY×FAMILY，部分，1 / 3 集入庫，等 Jellyfin 收錄」 | `/library` 預設落在最左邊的 Movies（空），入庫的東西在另一個分頁；數字不一致，見問題 2 |
| 15 | 全程 | console | 沒有 warning；error 只有 `/api/auth/me` 401、`/api/auth/login` 401 與換伺服器時的 `ERR_CONNECTION_REFUSED` | 無實質 error |

截圖在 `docs/research/m5-ai-direction-2026-10-27/health-screens/`：`01-rss-after-poll.png`（整頁約 7300px）、`03-media-detail.png`、`04-search-results.png`、`05-after-submit.png`（確認區）、`06-confirmed.png`、`07-job-imported.png`、`08-jobs-imported.png`、`09-library-anime.png`。

## 4. 發現的問題（依嚴重度）

1. **前端 knip 閘門測試在本機全紅（4 個）。** 重現：`pnpm -C web test`。真專案 `knip` 綠，所以是測試造的暫存專案報出 `files:src/health.ts` 等三個未使用檔。「全部檢查」綠、vitest 紅：CLAUDE.md 的完成標準要求 test 綠燈，現在 main 上做不到。需要查是環境（暫存目錄、knip 版本）還是測試本身壞了。
2. **同一部作品的入庫集數在三處對不上。** 重現：`import` 情境送單後開 `/media/tv:120089`。檔案區寫「S01 E01–E03 · 3 個檔案」，季表寫「S01 1 / 2 集入庫」，媒體庫 Anime 卡寫「1 / 3 集入庫」。分母（2 與 3）、分子（1）都不同。可能與 demo 資料（TMDB 替身只有部分集數在 aired）有關，需要對照真實資料再判斷是 Fake 偽影還是計算口徑不一致。未驗證。
3. **兩個後端 test 不穩或過時。**
   - `test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs`：疑為時間炸彈（fixture 中第二 cour 2026-07-02 起播，今天已全播完，`finished` 變 True）。重現：`uv run pytest tests/integration/test_rss_api.py::TestThePageFlow`。
   - `test_compose_hosts.py::TestSystemHostResolver::test_a_reserved_invalid_name_does_not`：疑為依賴本機 DNS。重現：`uv run pytest tests/integration/test_compose_hosts.py`。
   兩個都沒有確認根因。CI 是否也紅，沒有查。
4. **真實服務 e2e 沒有本機可跑的證據。** 沒有 `TMDB_API_KEY` 就跑不了；M5 在動前要自己決定 e2e 的 key 從哪來。CI 的 nightly 與票 133 紀錄是唯一證據，本次沒有驗證。
5. **`/rss` 頁在有待綁定 RSS Series 時變得非常長。** 重現：`rss` 情境，加 Feed、按「立即輪詢」。10 張待綁定卡片排在 Feed 列與加 Feed 表單**上面**，頁面約 7300px。剛加的 Feed 要捲到中段才看得到。
6. **送單要點兩次、`/jobs` 預設落在空分頁、`/library` 預設落在空的 Movies。** 都是小摩擦，單看沒有錯，但連在一起，主流程「搜尋 → 送單 → 看到入庫結果」中間每一步都多一次點擊或切分頁。
7. **「入庫到」預設「尚未指定」，沒選就搜不了。** 對只有一條可用 Route 的作品類型（例如只有 Anime）也是如此，需要使用者自己選。
8. **登入頁 `/api/auth/me` 的 401 進 console。** 無害，但會讓「console 無 error」的自動檢查要寫例外。

## 5. 清理紀錄

- 起的程序：兩個 `scripts/fake_setup_server.py`（`rss`、`import` 情境，port 8484），全部 `pkill` 掉，`pgrep` 無殘留，8484 已空。
- 臨時資料：`/private/tmp/claude-501/health/`（兩個臨時 `CONFIG_ROOT`、log）保留在 /private/tmp 下，沒有刪；不在 repo 內。
- 瀏覽器：playwright 已關閉；`/Users/roxy/orca/projects/Berth/.playwright-mcp/`（工具產生的 snapshot 與 console log）已刪除。
- Docker：沒有起任何容器（沒跑 e2e）；`docker ps -a` 中無 `berth-e2e-*`。沒有碰使用者既有的 Berth / Jellyfin / qBittorrent 部署。
- repo 變更：只有 `docs/research/m5-ai-direction-2026-10-27/`（本檔與 `health-screens/` 八張截圖），未 commit；`git status` 無其他變動。
