# 10 — 「為什麼沒入庫」的聚合讀取命令

**Status:** done

**Blocked by:** 01

**讀:** plan §11.6〈分段〉第 4 段；`docs/research/m5-ai-direction-2026-10-27.md` C6 情境 3；`docs/research/m5-prototype-2026-10-27.md` 的 S4 逐字稿（`docs/research/m5-prototype-2026-10-27/anthropic-S4.md`）；`berth/services/jobs.py`、`events.py`、`issues.py`、`rss.py`、`inventory.py`（`read_holdings` 的 `missing`）

## 為什麼

「為什麼這集沒入庫」的答案散在五張表：Job 時間線、事件、Issue、RSS Item（被排除？沒綁定？）、作品的缺集。prototype 裡模型要叫四到八次工具才拼得出來。一支聚合的唯讀命令讓 agent 一次拿到，人也用得到。它不需要 AI，是 M5 第一個 tracer 情境的資料來源。

## 做什麼

1. 讀取命令（`READ`）：給一部作品，或一部作品加一集。回傳：
   - 季表上的狀態（播了沒、入庫沒）。
   - 相關的 Job 和它們的狀態與最後幾筆事件。
   - 開著的 Issue。
   - RSS 那一側：有沒有綁 Series、Item 是不是被排除、在不在待綁定。
   - 一個**結論分類**：沒有來源、還在下載、等審核、入庫失敗、Jellyfin 還沒掃到、被排除。
2. 結論分類的規則只寫一份，前端與 agent 都讀它。
3. 一般使用者看得到的範圍照 brief §19「M5 的方向」⑦。
4. 這張不做 UI；Media 詳情頁要不要露出，等票 22 收尾時再看。

## 驗收

- [x] 每一種結論分類各有一個情境測試（用現有的 fixture 與 Fake 情境）
- [x] 一般使用者看不到別人的 Job（測試）
- [x] plan §6 補 API；`pnpm gen:api`；全部檢查與 pytest 綠；progress.md 已更新

## Comments

- 2026-10-27 實作：`domain/why_not.py`（`WhyNot` 十種與 `conclude`）、`services/why_not.explain`、`GET /media/{id}/why-not`。結論從票上的六種擴成十種（使用者同意）：多 `download_failed`（S4 的 `client_removed` 就是這種）、`unbound`、`unaired`、`imported`。測試在 service（`test_why_not.py`，每種結論一個情境）與 API（`test_why_not_api.py`）兩層。
- code-review 已改：已入庫的電影問整部時說成還沒播；一筆送單被拒會蓋掉同一集另一筆還在排隊的；發佈名或計劃的季 TMDB 沒有時那一筆 Job 從回答裡消失（改成退到整部作品，第 0 季除外）；已刪除、已入庫的 Job 不列；Feed 層的 Issue 沒收；`Any` 沒寫原因；`CLAIMING_ACTIONS` 兩份；事件模型重複一份；`user_id` 可以是 `None`；猜測在計劃已經說得出集時照樣跑解析器。
- code-review 未處理：
  - `DOWNLOAD_FAILED_STATES`（domain）與 `inventory.FAILED_STATES` 只差 `import_failed` 與 `client_removed`，兩組各管各的畫面，沒合併。
  - 每一筆 Job 各讀一次整條時間線再取最後 5 筆（最多 50 次查詢）；量到慢再改成一次查詢。
  - 磁碟不足、TVDB 這種整台 Berth 的 Issue 不在回答裡（健康頁說它們）；agent 要用時再看要不要帶。
  - 問季表上沒有的集（`episode=999`）回 `unaired`（TMDB 沒有播出日），不拒絕。
  - 一般使用者看得到 RSS 推出的結論類別（待綁定、被排除），看不到是哪個 Feed、哪一條規則；季表上那一格只是「缺」。
  - plan §11.6 第 4 段的「搜尋紀錄」沒做：Berth 不存搜尋紀錄（`SourceCache` 在記憶體、兩小時）。
