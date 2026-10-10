# 82 — 自動綁定：同一輪裡同一個 Mikan 番組頁只讀一次

**Status:** ready-for-agent

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

- [ ] 同一輪有兩個 Series 指向同一個 `bangumi_id`：番組頁只抓一次，預算只佔一格，兩個 Series 都拿到正確的線索與字幕組名；pytest 守，做變異驗證
- [ ] 番組頁讀失敗（暫時性失敗、預算擋下）時，兩個 Series 都記成同一種結果，不多打一次；pytest
- [ ] 不同輪照舊各讀一次（快取不跨輪）；pytest
- [ ] 全部檢查、pytest 綠；CHANGELOG、progress.md 已更新

## Comments
