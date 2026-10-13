# 100 — 修穩 `TestTwoRoundsAtOnce::test_only_one_round_runs_and_neither_fails`

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `tests/integration/test_rss.py` 的 `TestTwoRoundsAtOnce`（同一個 class 裡第二條用 `_GatedFetcher` 的寫法）；M4 票 13c（這組測試的由來）；票 49 的 Comments（第一次記到失敗）；`berth/services/rss.py` 的 `poll_feed`、`poll_due` 與 Feed 鎖

## 為什麼

這條測試在全套 pytest 時偶爾紅，單獨跑都綠。2026-10-07（票 49）記過一次，2026-10-13 合併票 94、98 時又各紅一次。每次都得重跑，久了大家會習慣「紅了就重跑」，哪天真的錯誤就混過去了。使用者（2026-10-14）同意開票修。

票 49 記下的失敗是 `(12, 0) != (12, 1)`：背景那一輪晚到，Feed 已經被「立即輪詢」輪過、不再到期，`poll_due` 就輪 0 個。

初步看法（**未證實**，開工時先證實）：
- 這條用 `asyncio.gather` 同時起兩邊，但沒有任何東西保證兩邊真的重疊。
- 「立即輪詢」整輪跑完之後背景那一輪才進來，是合法的排程。這時產品行為是對的（Feed 不再到期），是測試的斷言假設了重疊。
- 同一個 class 的第二條用 `_GatedFetcher` 把 Feed 卡住，確保重疊，所以穩定。

## 做什麼

1. **先重現**：用固定的排程（例如讓背景那一輪晚一點進來）穩定重現 `(12, 0)`，確認上面的看法。如果根因不是這個，停下來在票的 Comments 寫清楚實際原因，不要硬修。
2. **確認是測試的問題之後**：用 `_GatedFetcher`（或同等的閘）讓兩邊確實重疊，斷言的意思不變——人先到、背景後到時，只輪一輪、兩邊都不報錯。
3. 如果查出來是產品的競態（例如鎖沒有涵蓋到某一段），就修產品並補一條會穩定紅的測試。
4. 不要用重試、放寬斷言或 `flaky` 標記掩蓋。

## 驗收

- [x] 根因寫在票的 Comments，附重現方法
- [x] 修好之後，這條測試連跑 50 次（例如 `pytest --count` 或迴圈）全綠，貼輸出；全套 pytest 連跑 3 次都綠
- [x] 改測試的話，變異驗證：把閘拿掉，能穩定重現原本的失敗
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

**根因（已證實，是測試的問題，產品行為正確）**：`asyncio.gather` 一起起兩邊，沒有東西保證背景那一輪在「立即輪詢」寫下 `last_polled_at` 之前看 Feed 到期沒。窗口比票面猜的大：不必等「立即輪詢」整輪跑完，`_poll_feed` 在寫完 Item 之後、綁定與送單之前就 commit `last_polled_at`，背景那一輪的 `select` 只要晚於這一次 commit，Feed 就不到期、`poll_due` 回 0。平常背景那一輪只要一次 `select`、「立即輪詢」要五六次查詢加抓 Feed，前者多半先到，所以只在全套 pytest 偶爾紅。

**重現**（臨時測試，已刪）：兩種固定排程各跑 5 次，5/5 都是 `(12, 0)`，Feed 都只抓 1 次、`last_error` 空：
- 背景那一輪等「立即輪詢」整輪結束才進來；
- 把 `rss._prebind` 換成先停住的版本，背景那一輪等「立即輪詢」commit 了 `last_polled_at`、還在綁定時才進來。

**修法**：照同 class 第二條，用 `_GatedFetcher` 把「立即輪詢」卡在抓 Feed（commit 之前）；背景那一輪判定到期、走進 `poll_feed` 才放行（`rss.poll_feed` 換成先 set 一個 event 的包裝，monkeypatch；包裝之後不經 await 就停在等正在跑的那一輪）。兩處等待都用 `_until(event, task)`：該停的那一邊沒停（閘沒擋住、背景判定不到期）時等那個 task 結束，測試走到斷言而不是卡住；閘沒擋住時背景那一輪因此必定晚到，變異驗證才穩定。斷言不變。

**驗證**：
- 修好之後單跑這條 50 次：50/50 綠（迴圈逐次起 pytest；repo 沒有 pytest-repeat）。
- 變異：閘拿掉（`hold` 指向不會抓的網址）：20/20 紅，`assert (12, 0) == (12, 1)`。
- 對照：閘一開始就放行（抓 Feed 時照樣 set `entered`）：20/20 綠，背景那一輪多半照樣搶先判定到期，這也是原本只偶爾紅的原因。

**code-review 提到、查過不改**：同 class 第二條用 `await asyncio.sleep(0.05)` 等「立即輪詢」走到等待，Standards 軸疑為同類競態。不是：`by_hand` 開 session 不碰資料庫、`poll_feed` 到 `asyncio.shield` 之前沒有 await，`create_task` 排進的第一步在下一圈事件迴圈就跑完，一定早於 50ms 的計時器。

**順帶看到、沒修**：`poll_due` 用一次 `select` 讀到期狀態，判斷與真的走進 `poll_feed` 之間「立即輪詢」若整輪跑完、離開 `_rounds`，背景那一輪仍拿舊的判斷再輪一次：多一個請求預算，讀到的全是看過的 Item（`_unseen` 濾掉），沒有錯誤也不重複長東西。窗口在多個 Feed 時明顯（前面的 Feed 輪很久），單一 Feed 只剩 `select` 回來那一下。沒有 repro 也沒有使用者遇到，不在本票。
