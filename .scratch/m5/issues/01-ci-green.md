# 01 — 讓 CI 與本機測試回到綠燈

**Status:** ready-for-agent

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

- [ ] 三類失敗各自在修之前重現過（貼紅燈的輸出）
- [ ] `uv run pytest -m 'not e2e'` 與 `pnpm -C web test` 本機全綠（貼輸出）
- [ ] 全部檢查綠；progress.md 已更新
- [ ] 提醒使用者：push 之後確認 `main` 的 CI 轉綠（push 要使用者同意）

## Comments
