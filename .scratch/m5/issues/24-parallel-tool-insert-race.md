# 24 — 同一步並行的工具呼叫搶建同一筆作品資料

**Status:** ready-for-agent

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

- [ ] repro 測試先紅後綠；把修法拿掉會紅（變異）
- [ ] 其他「沒有就建」的路徑查過並記在 Comments
- [ ] 全部檢查、pytest、vitest 綠；改到 API 時 `gen:api` 無 diff；progress.md 已更新
- [ ] 不發版、不 push

## Comments
