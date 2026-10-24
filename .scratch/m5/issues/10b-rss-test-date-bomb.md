# 10b — RSS 頁面流程測試隨日期變紅

**Status:** done

**Blocked by:** None — can start immediately（排在票 11 之前）

**讀:** `tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs` 與它用的 RSS fixture；`berth/parser/finished.py`（`QUIET_AFTER = timedelta(days=30)`）與呼叫它的地方；`docs/development.md`〈測試〉

## 為什麼

2026-10-24 起這條測試在 main 上穩定紅（票 10 開工時的 commit 一樣紅；協調者在 main `38e48bb` 上重現）。初步判斷：它用真實時間判斷「最近一筆發佈後 30 天沒有新的就算完結」，fixture 的發佈日期寫死，今天剛好跨過 30 天。CI 在 `38e48bb` 還是綠的，只是因為當時還沒跨過那一天；下一次 push 起 CI 會紅，擋住後面每一張票。

## 做什麼

1. **先分清是產品的問題還是測試的問題**：讀 `finished.py` 與它的呼叫端，確認「現在時間」從哪來（`datetime.now()`、注入的 clock、或 DB 的時間）。產品端若在不該用牆上時間的地方用了它（例如應該以 poll 的時間為準），那是產品 bug，要修產品；若產品行為正確、只是測試沒固定時間，修測試。結論寫進 Comments。
2. **要有會紅的 repro**：現在的紅燈就是 repro；修好之後再加一個能證明「不再依賴今天日期」的手段（例如把時鐘固定在 fixture 日期附近、或把 fixture 日期改成相對現在），並實際把時間往後推（例如固定成 fixture 之後 40 天）證明不會再紅、或該紅時會紅。
3. **只拉長時間或改死另一個日期、說不出原因的不收**（下一個 30 天又會炸）。
4. 全套 pytest 掃一次有沒有其他用牆上時間又寫死日期的測試；有的話一起修或列在 Comments。

## 驗收

- [x] 原因寫在 Comments：產品還是測試、時間從哪裡來
- [x] 這條測試綠，而且不再依賴執行當天的日期（附上把時間往後推的證明）
- [x] 全部檢查、`pnpm -C web build`、pytest、vitest 綠；progress.md 已更新（含回頭註記票 10 回報的這條紅燈已修）

## Comments

### 原因（2026-10-24）

**測試的問題，產品沒錯。** 「現在」是讀清單那一刻的牆上時間：`GET /api/rss/series` → `services.rss.list_series(now=None)` 取 `now or utcnow()`，經 `_series_view` → `_finished` 傳給 `parser.series_finished`。`finished.py` 的 docstring 寫明完結不存下來、每次讀清單照現況算，Berth 停機一個月後打開 RSS 頁，安靜了 30 天的 Series 本來就該收進「已完結」，改用輪詢時間反而錯。錄下的 Feed 裡《与你相恋》最新一筆是 2026-09-24 08:08:01 UTC，加 `QUIET_AFTER` 30 天就是 2026-10-24 08:08，那之後跑的都紅（`assert (2, 12, True) == (2, 12, False)`）。

### 修法

- 這條測試開頭用 time-machine 的 `time_machine` fixture 把時鐘固定在 `KIMI_NEXT_DAY`（錄下的最新一筆的隔天，從 fixture 算出來，不是另一個寫死的日期）。整條流程（登入、輪詢、綁定、讀清單）用同一個時鐘。
- 結尾跳到 `KIMI_NEXT_DAY + QUIET_AFTER`，斷言同一列變成 `finished: true`：證明前面的 `False` 是時鐘給的。登入也照同一個時鐘過期，所以跳過去之後重新登入。
- 新 dev 依賴 `time-machine>=3.5.1`（3.x 不再假造 `monotonic`，asyncio 不受影響）。`docs/development.md`〈後端〉補一段「測試裡的『現在』」。

### 不再依賴執行當天的證明

用暫時的 pytest plugin 在整個 session 開頭 `time_machine.travel(timedelta(days=N), tick=True)`（沒進 repo）：

```
travel     0 days: 2 passed   # TestThePageFlow
travel   -60 days: 2 passed
travel    40 days: 2 passed
travel   400 days: 2 passed
travel  3650 days: 2 passed
```

修好之後全套：正常時鐘 `4620 passed, 1 skipped`；時鐘 +400 天（session 內讀回 2027-11-28）同樣 `4620 passed, 1 skipped`。變異：把跳過 `QUIET_AFTER` 那一行換成 `pass`，最後一條斷言紅（`assert False is True`）。

### 全套掃描（第 4 點）

修之前用同一個 plugin 跑全套 N = 0、−60、400、3650：

- 往後推（0、400、3650）只有這一條紅。
- 往回推 60 天多紅一條 `tests/integration/test_reimport.py::TestRebuildingADeletedLibrary::test_jellyfin_finds_every_episode_again`：入庫用寫死的 `arrange.NOW`（2026-09-08），反查掃描用 `utcnow() + 1 分鐘`，時鐘早於 2026-09-08 才紅，往後永遠綠，**不是定時炸彈，不修**。兩個時鐘混用，下次動這條時可以順手改成都從 `NOW` 算。
- 四種 N 都有的 9 個 ERROR 是掃描時加了 `-p no:logging`（`caplog` 不在了），與日期無關；不加這個旗標的全套是綠的。

掃描的極限：抓得到「過了某一天就翻面」的測試，抓不到只在某段時間窗內才紅的（跨年、月底、夏令時間）。

### code-review（基準 `c8c15646`）

Standards 沒有硬性違規；已改：`development.md` 那段的「fixture」同時指 pytest fixture 與錄下的資料，後者改成「錄下來的資料」。未處理（判斷題）：同檔第三份 `next(row for row in client.get("/api/rss/series").json() if row["key"] == KIMI_KEY)`，三份不抽；`KIMI_NEXT_DAY` 說的是怎麼算而不是用途，有註解，保留。Spec 沒有缺漏或範圍外的改動。

### 後續：e2e 的那一半（2026-10-24，合進 main `583de588` 之後）

協調者回報 CI 的 web-e2e 紅 8 條（run 40079562312）：`rss`、`rss-auto-bind`、`rss-exclusions`、`rss-backfill` 各 1280 與 390。同一個原因：演練伺服器（`scripts/fake_setup_server.py`）是真的 Berth、用真的時鐘，`rss` 系列情境讀的是同一份錄下的 Feed，過了 2026-09-24 08:08 UTC + 30 天，《与你相恋》一長出來就收進「已完結」，`region 'RSS Series'` 裡找不到它。上一次 CI 綠是在 08:08 UTC 前跑完。本機重現：`pnpm -C web e2e` 同樣 8 failed / 44 passed。

**修法：固定演練伺服器的時鐘，不改錄下的日期。** 改日期的話，`rss-split-cour-airing` 靠的「發佈日 vs TMDB 播出日」（第二 cour 2026-07-02 起播）也得跟著搬，錄下的 Feed、單一 feed、兩份 acg.rip、合集 feed 與 TMDB 替身的日期要一起平移，牽動的地方太多。

- `Scenario.clock`：設了的話，`main` 在建 app 與種資料之前 `time_machine.travel(clock, tick=True).start()`。時鐘照常往前走，背景迴圈的排程照跑。
- `rss_scenario` 設成 `tests/integration/test_rss.NOW`（2026-09-25 12:00 UTC）。這是 services 層測試對這份錄下的資料本來就用的「今天」，在每一份錄下的 Feed 之後（最新是聚合 feed 的 09-24 08:08 與 acg.rip 的 09-24 12:31）。`rss-legacy-feed`、`rss-split-cour`、`rss-split-cour-airing`、`rss-runtime` 都從 `rss_scenario` 長出來，一起固定。
- pytest 那條的 `KIMI_NEXT_DAY` 換成同一個 `NOW`：API 測試、services 測試、演練伺服器對同一個「今天」。
- 只固定伺服器，瀏覽器照真的時間。前端只有顯示用到瀏覽器時鐘（`relativeTime` 的「幾天前」、`FilesPanel` 的反查「即將」），所以這幾個情境的畫面上「幾天前」會多算一段，沒有判斷會因此翻面。cookie 用 `Max-Age`，登入不受影響。

**往後推的證明**：一個暫時的 `sitecustomize.py`（沒進 repo）讓每台演練伺服器起來就 `time_machine.travel(+N 天)`；`rss` 情境自己的固定是絕對時刻，會蓋過它。日誌讀回：`rss` 那幾台都是 2026-09-25，`weekly` 分別在 2026-12-03、2027-11-28。

```
正常時鐘：52 passed (1.6m)
+40 天：  52 passed (1.6m)
+400 天： 52 passed (1.6m)
修之前（正常時鐘）：8 failed, 44 passed
```

**其他 e2e 的掃描**：+40 與 +400 天時，其他情境的伺服器跟著往後推，也全綠，沒有同類依賴。掃描的極限：瀏覽器沒有一起推，只在瀏覽器那一側比日期的依賴掃不到。不過前端沒有這種判斷（見上一段）。
