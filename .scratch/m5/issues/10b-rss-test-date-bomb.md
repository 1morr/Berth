# 10b — RSS 頁面流程測試隨日期變紅

**Status:** ready-for-agent

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

- [ ] 原因寫在 Comments：產品還是測試、時間從哪裡來
- [ ] 這條測試綠，而且不再依賴執行當天的日期（附上把時間往後推的證明）
- [ ] 全部檢查、`pnpm -C web build`、pytest、vitest 綠；progress.md 已更新（含回頭註記票 10 回報的這條紅燈已修）

## Comments
