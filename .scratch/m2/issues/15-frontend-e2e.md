# 15 — 前端 e2e 閘門

**Status:** done

**Blocked by:** 13、14（前端改動收完才不會一直重寫腳本）

**讀:** plan §10（測試策略）、§9.3（精靈流程）、§11.3 的票 14 那一列；README（演練情境那一節）

## 做什麼

plan §10 現在寫的是實話：**「沒有腳本化的 playwright e2e」**（2026-09-22 改的，它從 M0 起就與
repo 不符）。這一票把它變成不實話——把 playwright 對演練情境跑精靈與送單腳本化進 CI。

範圍以**現有的演練情境**為底（README 已記：`inventory`、`long-lists` 等，`scripts/fake_setup_server.py`
起得來）：精靈走完 → 送單 → 等入庫。M2 新增的審核與修正流程至少各有一條（`/review` 確認一筆
audit、`/issues` 修一條 `library_link_missing`）——它們是 M2 最該有閘門的一批。

**排在 13 / 14 之後**：那兩票會動到媒體庫、詳情頁與清單元件，先寫腳本就是先寫一份要重寫的腳本。

**與後端 e2e 的關係**：`tests/e2e/` 那一套（compose + 真服務）是後端的，nightly 跑。這一票是
瀏覽器那一層，兩者不合併——共用 compose 環境但斷言的東西不同。

不做的話就維持 §10 現在的實話，那句話不准改。

## 驗收

- [x] playwright 腳本在 CI 上跑得起來（貼 workflow run 連結與輸出）
- [x] 至少四條：精靈走完、送單到入庫、`/review` 確認一筆 audit、`/issues` 修一條
      `library_link_missing`
- [x] 腳本用的是演練情境（`scripts/fake_setup_server.py`），不打真的索引站與 TMDB
- [x] 失敗時留得下證據（截圖或 trace），CI 上撿得到
- [x] plan §10 那句話改成腳本化之後的實話，README 的演練情境那一節跟著更新
- [x] 跑一次故意的失敗（改壞一個選擇器）確認它真的會紅
- [x] lint、type、test 綠燈

## Comments

**2026-09-24 做完**（`7f1e1a6`…`271a0eb`）。

- **CI**：`web-e2e` job（`.github/workflows/ci.yml`，每個 push 與 `workflow_dispatch`）。main 上全綠：
  https://github.com/1morr/Berth/actions/runs/35920060310（`4 passed (19.4s)`）。第一次推上去
  （https://github.com/1morr/Berth/actions/runs/35917352134）`web-e2e` 就綠了，紅的是 backend 與 hygiene，
  兩者都是這一票之前就在的：`test_issues_api.py` 讀背景對帳沒等它跑完（本機剛好來得及），以及票 06 / 09c
  的票檔結尾多一行空白——`main` 自 2026-09-21 起沒推過，這兩件一直沒被 CI 看到。都修了（`6c16094`、`271a0eb`）。
- **四條**：`web/e2e/{wizard,submit,review,issues}.spec.ts`，一條流程一台 `fake_setup_server.py`
  （`bundled` / 新的 `import` / `review` / `issues`，port 8491–8494），本機約 16 秒、連跑三次都綠。
  斷言的是結果不是點擊：送單等到「已入庫」再看「檔案與版本」5 個檔案、帳本對得上；audit 確認後重新整理
  那一列不回來；重新鏈接後再對一次帳不再開。
- **不出網**：新情境 `import` 是 `plan` 那一包對得上的批次 + 替身 TMDB（與 `issues` 同一部 SPY×FAMILY）；
  下載連結指回 server 自己。
- **故意的失敗**：`issues.spec.ts` 的「重新鏈接」改成「重新連結」。本機紅、留下截圖 / trace / error-context；
  CI 上也跑了一次（一次性分支 `e2e-red-check` + `workflow_dispatch`，跑完刪掉分支）：
  https://github.com/1morr/Berth/actions/runs/35920075513——`web-e2e` 1 failed 3 passed、其餘 job 全綠，
  artifact `playwright-evidence` 下載得到 `test-results/<那一條>/{test-failed-1.png,trace.zip,error-context.md}`
  與 `playwright-report/`。
- **寫腳本時抓到的 bug（使用者拍板這一票修）**：精靈第 5 步加站還在跑時按「測試 TMDB」，加站那支命令最後把
  它開頭讀到的整份 `settings.setup` 寫回去，TMDB 的結果被蓋掉、精靈卡在第 6 步。反過來則是逐站結果消失。
  新的 `services/settings.update_settings`（寫鎖裡重讀、只改自己那一半），`test_setup_source.py` 兩條雙向
  重現（`7f1e1a6`）。精靈那條 e2e 照使用者真的會做的順序按（不等加站跑完），所以它同時守著這個修正。
- **驗證**：ruff / ruff format / mypy strict（271 files）/ lint-imports（6 kept）綠；`pytest` 2233 passed；
  前端 tsc / eslint / prettier 綠、vitest 641 passed；`pnpm gen:api` 零差異；`pnpm e2e` 4 passed。

code-review（`5c7688a`，Standards / Spec 兩軸）未處理的發現：

- Standards（判斷層級）：「0 列 UPDATE 拿 SQLite 寫鎖 + commit / rollback 骨架」現在 `services/settings.py`
  與 `services/routes.py` 各一份。第三處出現時抽成一個共用 helper。
- Standards（判斷層級）：`update_settings` 進門的 `commit()` 會連帶提交呼叫端還沒 commit 的寫入（加站命令的
  `IndexerSettings`、TMDB 的 `TmdbSettings`），之後失敗會留下「憑證存了、步驟沒記」的半態。與
  `routes._write_lock` 同一個取捨，docstring 有交代；鎖內重讀不會同步呼叫端手上的舊 pydantic 副本，目前只
  在網路之前用到它。
- Spec：`wizard.spec.ts` 沒有直接斷言纜繩狀態——已改註解說明「看得到完成設定就是全綠」（後端 `_current_step`
  要 Route 全綠才推到 8）。
- Spec 提醒：精靈那條不等加站跑完就測 TMDB，對時序敏感；CI 若偶紅先看這裡。
