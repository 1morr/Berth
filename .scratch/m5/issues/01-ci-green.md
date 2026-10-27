# 01 — 讓 CI 與本機測試回到綠燈

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/m5-ai-direction-2026-10-27.md` A4、A5 的 B1；`docs/development.md`〈全部檢查〉〈前端〉；三個被撤銷的修正：`git show 69291d2d 70423b2f 952dc733 a55078ae`（在 `backup/m5-attempt-1-20261024`）

## 為什麼

`main` 的 CI 從 2026-10-24 起是紅的，本機另有 5 條只在 macOS 紅的測試。每張票的完成標準是全部綠燈，所以這張排第一。三個修正在被撤銷的上一輪 M5 裡做過，連同 M5 的程式一起被退掉了。

## 做什麼

1. **RSS 時間炸彈**：`tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs`。fixture 的第二 cour 已經播完，Series 被判成完結。參考 `952dc733`、`a55078ae`，把測試時鐘釘住。
2. **本機 fake-ip DNS**：`tests/integration/test_compose_hosts.py:103`。參考 `69291d2d`，偵測到解析器把無效名稱也解得到時 skip，並說明原因。
3. **knip 閘門**：`web/gates/knip.test.ts` 的 4 條。參考 `70423b2f`，探測目錄要解 symlink（macOS 的 `/tmp`）。
4. 從那幾個 commit **只取測試與 `docs/development.md` 的部分**，不帶 M5 的票檔與產品程式碼。照提交前的規則先重現紅燈，再修。

## 驗收

- [x] 三類失敗各自在修之前重現過（貼紅燈的輸出）
- [x] `uv run pytest -m 'not e2e'` 與 `pnpm -C web test` 本機全綠（貼輸出）
- [x] 全部檢查綠；progress.md 已更新
- [x] 提醒使用者：push 之後確認 `main` 的 CI 轉綠（push 要使用者同意）

## Comments

- 2026-10-27 修前重現（本機）：
  - `test_rss_api.py:202` `assert (2, 12, True) == (2, 12, False)`
  - `test_compose_hosts.py:103` `assert True is False`
  - `web/gates/knip.test.ts` 4 failed，各報 `files:src/health.ts`、`files:src/api/schema.d.ts`、`files:src/api/schemas.ts`
  - CI 的 web-e2e（run 40114628104）也紅：`rss`、`rss-auto-bind`、`rss-exclusions`、`rss-backfill` 兩種寬度共 8 條；本機 `pnpm -C web e2e --project rss ...` 重現 4 failed
- 修後：`uv run pytest -m 'not e2e'` 4340 passed、1 skipped（fake-IP 那條）、28 deselected；`pnpm -C web test` 115 files / 2183 passed；`pnpm -C web e2e` 44 passed；`uv run pre-commit run --all-files` 13 項 Passed
- **超出票文字的一處**：`a55078ae` 對 `scripts/fake_setup_server.py` 的 `Scenario.clock` 也帶進來。票說只取測試與 `development.md`，但 web-e2e 的 rss 情境紅在同一個時間炸彈，沒有它 CI 不會綠；它是演練伺服器，不是 `berth/` 的產品程式碼。由 web-e2e 的 rss 系列 project 守著
- 被撤銷那一輪的「M5 票 10b」引用改成「M5 票 01」；time-machine 裝 3.6.0（上一輪是 3.5.1），實測 `travel(tick=True)` 不動 `time.monotonic`
- code-review 未處理：
  - `uv.lock` 的 `revision` 3 → 5 是本機 uv 0.13.5 改寫的；repo 沒釘 uv 版本，CI 的 setup-uv 裝最新版。push 後留意 `uv sync --locked`
  - `test_rss.py` 的 `NOW` 註解列出了使用它的地方（`time_machine`、`Scenario.clock`），與 `development.md` 重複，判斷題，保留
