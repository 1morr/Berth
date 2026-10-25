# 02 — 通知的兩個缺口與連結閘門

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §11.5〈M5 開工前的審查補記〉「排進 M5 開頭」、§7；M4 票 124、126 的 Comments；`services/downloading` 的 docstring（`download_round`、`presser`）；後端 `deeplink.MEDIA_PAGE` 與前端的路由表

## 為什麼

M4 收尾審查留下三條沒人接手的：

- 放行、全部下載、改 Route 時傳下去的 `presser`（「誰按的」，那個人不收自己按的「正在下載」）沒有測試：API 那一層拿掉 `user_id=` 也不會紅（票 126）。
- 關機時被取消的那一輪，已經送出的 Job 沒有「正在下載」那一則（票 126）。
- 通知連結的作品頁路徑（後端 `/media/{media_id}`）與前端路由 `/media/$mediaId` 只靠註解綁著，前端改路由時連結靜靜變成 404（票 124）。M5 的結果卡與 M7 的 Discord embed 會連回更多頁面，先補這道門。

## 做什麼

1. **`presser`**：放行、全部下載、改 Route 三條路各一條測試，按的人收不到、其他訂閱者收得到；拿掉 API 那一層的 `user_id=` 會紅。
2. **被取消的那一輪**：先寫出 repro（一輪送出兩筆之後被 `CancelledError` 打斷，看不到「正在下載」），再讓已送出的照樣排進待送表。取消時的寫入不能拖住關機——照 `test_loop_shutdown` 的取向，排不進去只記 log。
3. **連結閘門**：讓前後端讀同一份事實，或讓一邊的測試讀另一邊的定義（例如前端測試從後端匯出的路徑模板對照路由表）。挑最不需要新機制的做法，理由寫進票。後端其他組前端網址的地方（Job、Issue、清單頁的錨點）一起納入。

## 驗收

- [x] 三條路的 `presser` 各有測試，拿掉傳遞會紅（pytest）
- [x] 被取消的一輪：改之前 repro 紅、改之後已送出的有「正在下載」（pytest）
- [x] 前端路由與後端連結模板不一致時紅、改無關路由不紅（雙向變異）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

### 做法與理由（2026-10-25）

**`presser`**：`tests/integration/test_rss_api.py::TestWhoPressed` 三條經過 HTTP：放行（`POST /rss/items/{id}/release`）、全部下載（`POST /rss/feeds/{id}/prime`，`mode: all`，acg.rip feed）、改 Route（`PUT /rss/feeds/{id}/routes`）。登入的 skipper 與另一位管理員 bosun 都訂「正在下載」，斷言待送表裡每位收件人的則數（`== {"bosun": N}`，按的人不在裡面）。變異：三個端點各自把 `user_id=_user_id(request)` 換成 `None`，每次只紅對應那一條。

**被取消的那一輪**：repro `TestCancelledRound::test_what_was_sent_before_the_cancel_is_still_told`（第三筆 `.torrent` 時 `CancelledError`）改之前紅（`ValueError: not enough values to unpack (expected 1, got 0)`，沒有「正在下載」）。`download_round` 多接 `asyncio.CancelledError`：寫的那一段包在 shield 裡、寫完才把 cancel 往上傳；寫不成只記 log（`test_a_write_that_fails_only_logs_and_the_cancel_goes_on`）。寫的時候再被 cancel 也等它寫完（`TestCancelledTwice`，真的 `task.cancel()` 兩次）：放手的話它在背景用著呼叫端要關掉的同一個 session，task 也沒人持有參照（code-review 抓到，第一版是放手）。寫入只碰本機資料庫，所以等得起；背景迴圈的輪本來就被 `whole_tick` shield 住，cancel 只會從 API 請求進來。

**連結閘門：Python 測試讀前端原文**（`tests/unit/test_berth_links.py`），照 `tests/unit/test_job_filters.py` 的前例，不新增機制。沒選「後端匯出、前端測試讀」：vite 不讓前端測試讀 `web/` 以外的檔（`test_library_slug.py` 的註解），要匯出就得多一份簽進版控的產出檔與它的同步檢查。後端組前端網址的地方收進 `services/deeplink`：`*_PAGE`（路徑模板）照名字自動收，每一條的形狀要等於 `routes.tsx` 的一條路由；`waiting` 原本自己用 f-string 組的三種錨點改成 `REVIEW_ROW`、`ISSUE_ROW`、`SERIES_ROW`，每一個要是那一頁某個元素 `id={`…`}` 的樣板字串，新加一個 `*_ROW` 不登記頁面就紅。雙向變異在測試檔裡，也對真檔手跑過：`/media/$mediaId` 改名、`issue-` 改 `issues-`、`RSS_PAGE` 改值都紅；`/health` 改名與 `/jobs/$hash` 改參數名不紅。**Job**：後端目前沒有組 `/jobs/…` 網址的地方，所以沒有可守的；M5 結果卡要連 Job 時在 `deeplink` 加 `JOB_PAGE` 就被守。

### code-review 沒處理的

- `waiting` 三處 `f"{PAGE}#{ROW.format(...)}"` 重複（可在 `deeplink` 給一個組 `page#row` 的函式）：三行、一個呼叫端，先不抽。
- `*_PAGE` 靠名字字尾收；有人用別的字尾（`JOB_URL`）加常數會漏過閘門。`deeplink` 的段落註解寫明了命名，不另外掃整個 `berth/`。
- `TestCancelledRound` 兩條的前四行準備相同、`test_rss_api.py` 的 `DOWNLOADING` 別名：判斷題，不改。
