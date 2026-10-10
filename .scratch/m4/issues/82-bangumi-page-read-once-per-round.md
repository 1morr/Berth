# 82 — 自動綁定：同一輪裡同一個 Mikan 番組頁只讀一次

**Status:** done

**Blocked by:** None — can start immediately

**讀:** M4 票 77 的 Comments〈MyBangumi 的請求量與預算計法〉；`berth/services/rss.py` 的自動綁定（`_clues`、`_due_lookups`、呼叫它的那一輪）；`berth/services/bangumi.py`（也讀番組頁）；`berth/adapters/budget.py`；brief §20.13

## 為什麼

自動綁定要讀 Mikan 的番組頁，才知道這部是什麼作品。`_clues` 是以 RSS Series 為單位讀 `bangumi_url(mikan_bangumi_id)` 的；同一部動畫的不同字幕組是不同的 Series，所以同一輪會把同一頁讀好幾次。這些請求都算在 Mikan 每小時 60 次的請求預算裡。額度用完時，被擋下的 `lookup_deferred` 下一輪會再讀一次，浪費跟著放大。

## 做什麼

- 一輪裡同一個 `bangumi_id` 的番組頁只抓一次，同一輪裡其他 Series 共用那一份。快取只活在那一輪，不跨輪，也不寫進資料庫。
- 讀失敗（暫時性失敗、被預算擋下）時，同一輪共用這個番組頁的 Series 都照同一個結果處理，不再各自重試一次。
- `bangumi.py` 若也在同一輪讀同一頁，一併納入；不在同一輪的不動。
- 字幕組名字是從同一頁取出的（`subgroups`），每個 Series 照舊取自己的那一個。

## 驗收

- [x] 同一輪有兩個 Series 指向同一個 `bangumi_id`：番組頁只抓一次，預算只佔一格，兩個 Series 都拿到正確的線索與字幕組名；pytest 守，做變異驗證
- [x] 番組頁讀失敗（暫時性失敗、預算擋下）時，兩個 Series 都記成同一種結果，不多打一次；pytest
- [x] 不同輪照舊各讀一次（快取不跨輪）；pytest
- [x] 全部檢查、pytest 綠；CHANGELOG、progress.md 已更新

## Comments

### 做法

- `services/rss.py` 新的 `_ShowPages`：一個 Feed 的一輪（`_poll_feed`）建一份，`bangumi_id` → 原文或失敗（`_LookupError`、`BudgetExhaustedError`）。剛長出來的與到期重認的兩段迴圈共用同一份；`_clues` 只拿原文、各 Series 照自己的 `mikan_subgroup_id` 挑字幕組名。只是一個區域物件，不跨輪、不落地。
- **「一輪」是一個 Feed 的一輪**，不是 `poll_due` 整批：票 77 的情境（MyBangumi 聚合 feed）都在同一個 Feed 裡。用好幾個單一番組 feed 追同一部的不同字幕組時，同一次 `poll_due` 仍會各讀一次——沒有資料說有人這樣用，沒做。
- `bangumi.py` 沒動：它只由人按的 API 呼叫（`BudgetUse.MANUAL`），不在輪詢那一輪裡。
- 兩支實驗腳本（`rss_auto_bind.py`、`air_date_lag.py`）呼叫 `_clues` 的地方跟著包一層 `_ShowPages`。

### 測試與變異

`tests/integration/test_rss_show_page_per_round.py` 五條：兩組一次讀到並綁上（預算 poll 4 格、字幕組名各自的）、連不上時兩組都是 `lookup_retry` 且只問一次、預算放不下時兩組都是 `lookup_deferred` 且延後只記 1、下一輪再讀一次、同一輪一組新長的與一組到期重認共用一次。變異：未實作前前四條紅（讀 2 次、延後記 2）；拿掉「失敗也記下來」→ 3 條紅；快取改成模組層（跨輪）→ 跨輪那條紅；重認迴圈另開一份 `_ShowPages` → 混合那條紅。

### code-review（兩軸 opus）

- 已處理：讀失敗轉 `_LookupError` 搬進 `_ShowPages`（網址只在一處組）、`_read` 改名 `_outcomes`、快取的例外再丟時 `with_traceback(None)` 不疊 traceback、補混合情境的測試、「一輪」的解讀寫進 docstring 與這裡。
- 沒處理：實驗腳本要知道 `_ShowPages` 才能呼叫 `_clues`（Standards 判斷題）；腳本本來就 import 私有函式，為它另開公開介面沒有其他消費者。
