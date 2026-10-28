# 24 — 同一步並行的工具呼叫搶建同一筆作品資料

**Status:** done

**Blocked by:** 23d

**讀:** plan §2.6（AI 對話）、§11.6 的工具與執行器；`berth/services/agent.py` 怎麼跑一步裡的多個工具呼叫；`berth/services/media.py` 的 `read_snapshot` / `read_media`；`berth/services/search.py` 的 `search_torrents`；`berth/services/executor.py`（或執行命令的那一層）的 session 用法

## 為什麼

使用者 2026-10-28 在試用機（Docker 全套、真模型 DeepSeek）上請助理訂閱「鐵旅！meet with 鐵道少女」（`tv:302020`）。模型在同一步並行叫了 `media_read_media` 與 `search_search_torrents`，前者回：

```
IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed: media.id
[SQL: INSERT INTO media (id, tmdb_id, kind, title_en, ...)]
```

兩支都在「這部作品還沒有快照」時要建 `media` 列，同時插入。模型這次自己繞過去，但工具結果是一串 SQL 錯誤，而且任何兩支會先建作品資料的工具並行時都會撞（`why_not.explain`、`media.route_choices` 等）。

## 做什麼

1. 先寫**會紅的 repro**：同一步兩個工具呼叫並行、同一個還沒有快照的 media_id，重現 `UNIQUE constraint failed`。
2. 找根因再修，修在根上（例如「取得或建立」改成能承受並行的寫法、或同一步的工具呼叫怎麼分 session），不是在工具外面包 try/except 吞錯。寫明為什麼選這個修法。
3. 查一遍其他「沒有就建」的路徑（作品快照之外，如 Series、Feed 綁定）在並行工具呼叫下會不會同樣撞；撞的一起修並補測試，不撞的在票 Comments 寫一句查過哪些。

## 驗收

- [x] repro 測試先紅後綠；把修法拿掉會紅（變異）
- [x] 其他「沒有就建」的路徑查過並記在 Comments
- [x] 全部檢查、pytest、vitest 綠；改到 API 時 `gen:api` 無 diff；progress.md 已更新
- [x] 不發版、不 push

## Comments

### 2026-10-28 實作（票 24 session）

**根因**：`media._store` 是「抓 TMDB 之前 `session.get` 看有沒有 → 抓幾百毫秒 → 沒有就 `session.add`」。側面板每個工具呼叫各開一個 session（`Turn.run_tool`），同一步的兩支都在抓的途中看到「沒有」，後 commit 的撞 `media.id`。

**修法**：建列改成 `INSERT … ON CONFLICT(id) DO NOTHING`，再讀回那一列套更新（`folder_frozen` 照讀回的那一列算）。不選「agent 把同一步的工具排隊」：作品頁、自動綁定、規劃器也各開 session 走 `_store`，排隊只擋得住一種；不選 `_write_lock`（routes 那種先鎖再讀）：鎖要包住抓 TMDB 的那段，別的寫入全都得等。

**repro**：`tests/integration/test_agent_parallel_tools.py`，一則回應裡並行 `media_read_media` + `search_search_torrents`，修前紅在跟試用機一模一樣的 `UNIQUE constraint failed: media.id`。假 TMDB 不讓出事件迴圈，兩支不一定交錯，所以用 `tests/integration/arrange.Meeting` 讓兩支都問到 TMDB 才往下走（等滿 2 秒自己走，改成排隊時測試不會卡住，但也就測不到「真的並行」）。

**其他「沒有就建」的路徑**（側面板不出卡、直接跑的工具走得到的）：

- 撞，一起修並補測試：
  - `rss._series`：RSS Series 的鍵跨 Feed 共用（nyaa / acg.rip 是標題骨幹），兩條搜尋訂閱並行輪詢時搶建同一個 → 同樣 `ON CONFLICT DO NOTHING` + `RETURNING`，搶輸的不算這一輪長出來的（`test_two_searches_growing_the_same_series_at_once_both_succeed`）。背景輪詢與「立即輪詢」不同 Feed 時也會撞，同一支修好。
  - `rss.subscribe_search`：先查網址、再 commit；同一組參數並行兩次時兩支都過了檢查，後到的丟原始 IntegrityError → commit 撞 `rss_feeds.url` 時確認網址已在就回 `feed_duplicate`（`test_the_same_search_twice_at_once_is_one_feed_and_a_duplicate`；檢查與 commit 之間沒有網路，碰面點只好放在私有的 `_subscribed_routes`）。
  - `discover._write_cache`：`session.merge` 是先查再插，兩個正規化相同的查詢（或側面板讀趨勢時有人開探索頁）都寫同一格 → sqlite upsert（`test_the_same_query_twice_at_once_shares_one_row`）。
- 查過、不撞：`why_not.explain`、`media.route_choices` / `route_offer`（只讀；票面猜 `why_not` 會建快照，實際不會，沒快照時回 `media_missing`）；`discover.image_base`（有 TMDB key 就有 settings 那一列，只 UPDATE）；`ai_runs` 的計數（拿到寫鎖之後才讀 `Turn.tool_calls`，後 commit 的值一定比較大）；`proposals`（uuid 主鍵）；`SourceCache`（記憶體）；`RssItem`（`(feed_id, guid)`，同一條 Feed 由 `_rounds` 排隊）。
- 同一種寫法、但不是並行工具呼叫走得到的（經確認卡由人按）：`rss._subscribe`（Mikan 的 `if series is None: RssSeries(...)`）、`rss.add_feed`。沒改。

**變異**：四個修法各自拿掉，都只紅它自己那一條（code-review 的 Spec 代理在副本上另外跑過一次，結果相同）。

**code-review 沒處理的發現**：

- Standards：`add_feed` 把 commit 時的任何 IntegrityError 都當 `feed_duplicate`，`subscribe_search` 先確認網址真的在才算，同一個拒絕兩種判法。曾經抽成共用的一支，但 `add_feed` 不在這張票的範圍、收窄它要另補「Route 在檢查與 commit 之間被刪」的測試，所以還原，留作後續題目。
- Standards：`media._store` 與 `rss._series` 是同一種「insert or ignore 再讀回」；只有兩處、`_series` 多了 `RETURNING`，先不抽。
- Spec：舊資料庫（沒存 `image_base_url`）第一次讀作品時 `image_base` 先寫 settings，這個寫交易一路開到 `_store` commit，中間跨抓 TMDB；並行的另一支等寫鎖，TMDB 超過 5 秒（`busy_timeout`）就是 `database is locked`。精靈跑過的資料庫都有圖片基底，不擋。
