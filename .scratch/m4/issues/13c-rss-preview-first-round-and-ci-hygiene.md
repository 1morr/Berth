# 13c — main CI 紅：`rss-preview` 第一輪「新 0 筆」、pre-commit hygiene

**Status:** done

**Blocked by:** None — can start immediately（M4 01–17 推上 main 後的第一個 CI 就紅，先修綠）

**讀:** 票 12、13、13b 的 `## Comments`（`rss-preview` / `rss-subscribe` 那幾條）；plan §3.2（背景迴圈）、§6 rss；
progress.md 2026-09-27 票 11 那一條「同一個 Feed 一次只輪一輪」（`1513db5`）

## 為什麼

main `6a90fc8` 的 CI（run 36614179332）兩個 job 紅：

1. **web-e2e**：33 條中 `rss-preview`（1280）紅，`rss-preview-390` 同一輪是綠的：

   ```
   Locator: getByRole('region', { name: /^Feed/ }).getByRole('article', { name: 'acg.rip' }).getByRole('status')
   Expected substring: "新 30 筆"
   Received string:    "這一輪：新 0 筆、長出 0 個 RSS Series（自動綁定 0 個）、送出 0 筆。"
   ```

   票 12 收尾時 `rss-preview-390` 已經紅過一次（單獨重跑綠），這是第二次。第一輪看到 0 筆新 Item，像是背景
   poller 與「立即輪詢」搶同一個 Feed：背景那一輪先把 30 筆記成已見，畫面上那一輪就是 0（票 11 的 `1513db5`
   讓同一個 Feed 一次只輪一輪，但沒有說畫面上顯示的是哪一輪）。**還沒 repro，第一步就是做出來。**

2. **hygiene**：`pre-commit run --all-files` 的 `trailing-whitespace` 與 `end-of-file-fixer` 改了檔：
   `.impeccable/critique/2026-09-28T13-52-10Z__web-src-setup-ownerstep-tsx.md`、
   `.impeccable/critique/2026-09-29T06-57-20Z__web-src-pages-setuppage-tsx.md`、
   `.scratch/m4/issues/06-wizard-jellyfin-first.md`、`09-indexer-berth-test-first.md`、`13-rss-series-by-work.md`。

要先分清楚 1 是**產品的問題**（使用者按「立即輪詢」或新加 Feed 時，畫面說「新 0 筆」但其實 30 筆被背景那一輪收走，
等於說錯話）還是**spec 的問題**（等待條件或測試資料的時序）。前者修產品，後者修 spec；只拉長逾時而說不出原因的不收。

## 驗收條件

- [x] 找出 1 的原因並寫進票的 Comments，附證據（log、trace 或計時）
- [x] 產品的問題：一條會紅的後端或前端測試，修好轉綠；spec 的問題：說明原本的等待條件為什麼不對，改 spec
- [x] `rss-preview` 與 `rss-preview-390` 在整套前端 e2e 裡連跑三次都綠
- [x] `pre-commit run --all-files` 乾淨；想一下為什麼本機的 pre-commit 沒擋下這些檔（`.impeccable/` 與 `.scratch/`
      是不是被排除、或 session 繞過了 hook），有需要就補上，並在 Comments 說明
- [x] lint、type、test、前端 e2e 綠燈；push 後 main 的 CI 全綠（附 run 連結）——[run 36620909540](https://github.com/1morr/Berth/actions/runs/36620909540)（`627294f`）：backend、web、web-e2e、hygiene、api-types、image 全綠

## Comments

- **1 的原因：產品的問題**。背景 `rss_poller`（`pipeline/rss.py`，`TICK` 30 秒、先睡再跑）與「立即輪詢」同時輪同一個剛加的
  Feed（`last_polled_at` 是 `NULL`，醒來就到期）。票 11 的 `1513db5` 讓後到的那一輪**排在後面再輪一次**，讀到的全是前一輪剛
  收下的 Item，於是畫面說「新 0 筆」——那 30 筆其實在，只是被背景那一輪收走（還多花一格請求預算）。證據（CI run 36614179332）：
  - `rss-preview` 的 server 在 18:45:57.72 印出 `scenario=rss`，背景迴圈約在 18:46:28、18:46:58、**18:47:28** 醒；這條 spec
    跑在 18:47:26.9–33.1（6.2 s）。trace：`POST /rss/feeds` 18:47:27.673、`POST /rss/feeds/1/poll` 18:47:27.823、花 434 ms、
    回「新 0 筆」——正好罩住那一次醒來。
  - 同一輪的 `rss-preview-390`：server 18:46:03.4 起，醒在 18:47:33.5、18:48:03.5；spec 跑在 18:47:35.4–39.5，錯過 → 綠。
  - 為什麼整套才紅、單獨跑綠：`webServer` 一開始就起全部 33 台，spec 排隊等 worker；單獨跑時 spec 在開機後幾秒就跑完，
    碰不到第一次醒來。票 12 那一次 `rss-preview-390` 紅是同一型。
- **修法**：`services/rss.poll_feed` 改成 Go `singleflight` 的做法（`_rounds`）：同一個 Feed 已經有一輪在跑時，後到的不另輪，
  等它做完拿它的 `PollOutcome`；前一輪沒做完就結束（例外、cancel）時後到的自己再輪。一次只輪一輪照舊（`_feed_locks` 拿掉，
  `KeyedLocks` 只剩 Job 用）。紅燈測試 `tests/integration/test_rss.py::TestTwoRoundsAtOnce::
  test_the_later_one_reports_the_round_it_waited_for`：背景那一輪卡在抓 feed（`_GatedFetcher`）時按「立即輪詢」，修前
  `(1, 0, 0) != (1, 12, 11)`；也斷言 feed 只抓一次。原本那一條（人先到）改名 `test_only_one_round_runs_and_neither_fails`，
  同樣多斷言只抓一次。spec 沒改：它等的就是產品該說的話。
- **殘餘的窗口**（沒修，說明為什麼）：背景那一輪若在按下去**之前就整輪做完**，按下去的那一輪照舊說「新 0 筆」——這時它
  說的是實話（那幾筆已經在清單上）。要碰到得兩件事同時成立：醒來落在「加入」到「按下」之間，而且整輪比這段間隔短。CI 裡
  這段間隔約 150 ms、一輪 434 ms，所以醒在間隔裡的那一次一定還在跑、會被併進去；spec 的「第一輪還沒輪到」斷言也在同一段
  間隔裡，同理。不為這個再改 spec 或關掉演練的背景迴圈（那等於不測真實的時序）。
- **後到的拿前一輪的 `now`**：前一輪開始時讀的是當時的 Feed 設定；剛改完網址就按輪詢、又撞上背景那一輪時，第一次看到的是
  舊網址那一輪。影響小，不處理。
- **hygiene**：五個檔不是被排除（`.pre-commit-config.yaml` 只排 `^tests/fixtures/`），是**這個 clone 從沒裝過 hook**
  （`.git/hooks` 只有 `*.sample`；README 寫「選用但建議」），而 CLAUDE.md 的 session 流程第 3 步寫的是「lint、type、test」，
  每個 session 各自跑 ruff / mypy / eslint，沒有人跑 whitespace 那一組。處理：`uv run pre-commit install`（只在這個 clone，
  worktree 共用 `.git/hooks`）；**接手的閘門是 CLAUDE.md 第 3 步改成跑 README「全部檢查」（`pre-commit run --all-files`）與
  完成標準跟著改，加上 CI 的 hygiene job**——本機 hook 不在版控裡，換一個 clone 就沒有。
  - 順帶看到：工作目錄裡幾十個檔是 CRLF 混 LF（Windows 上的編輯寫出來的），`mixed-line-ending` 會回報「fixed」；它們進版控時
    被 `.gitattributes` 的 `eol=lf` 正規化，CI 看不到，`git diff --ignore-cr-at-eol` 是空的。
- **整套前端 e2e 連跑三次**（本機，`npx playwright test`）：`rss-preview` 4.0 / 4.6 / 4.8 s、`rss-preview-390` 3.5 / 4.2 / 3.5 s，
  三次都綠。三次各有一條別的紅：
  - 第 1、3 次的 `existing`、`issues`：`browserType.launch: Timeout 180000ms exceeded`，測試本體 2 ms、chromium 三分鐘沒起來
    （那兩次整套因此多 2 分鐘）。同一台機器上使用者的試跑環境正在啟動，是本機環境，不是產品或 spec；CI 上沒有出現過。
  - 第 2 次的 `settings-390`：**spec 的問題**（票 09 的 spec）。它按完「加入 1 個站」立刻按「搜尋全部」，而「搜尋全部」搜的是
    按下去那一刻已加入的站；加站還沒回來時 YTS 不在裡面，那一列停在「還沒搜」、等不到「N 筆」。重現：把
    `POST /api/setup/indexers/apply` 用 `page.route` 延後 1.5 s，`settings` 每次都紅，畫面上 YTS「還沒搜」。修法：先等 YTS
    出現在已加入清單再按；同樣延後 1.5 s 時兩種寬度都綠，之後拿掉延遲。產品的行為是對的（使用者看得到那一列還沒加進來）。
- 驗證：`pre-commit run --all-files` 全綠（ruff、ruff format、mypy、import-linter、prettier、eslint、檔案衛生）；pytest 3335 passed；前端 e2e 見上；CI 見驗收條件。
