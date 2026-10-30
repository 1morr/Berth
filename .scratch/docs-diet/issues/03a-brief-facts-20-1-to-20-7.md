# 03a — brief §20 壓縮（上）：§20.1–§20.7

**Status:** done

**Blocked by:** 01

**讀:** `.scratch/docs-diet/spec.md`；brief §20 開頭與 §20.1–§20.7（約 660 行 115 KB，交給子代理逐節處理）；各節提到的 `docs/research/` 檔

## 為什麼

brief §20 有 1,107 行，是 brief 最大的一章。13 節已經連到 `docs/research/`，內容卻又在 brief 寫了一遍；另外 11 節的細節只在 brief。brief 該只留「是什麼、從哪來」，細節的唯一來源是 research。§20 太大，一個 session 做不完，拆成兩張票。

## 做什麼

1. **細節先搬**：這批還沒有研究檔的是 §20.2（qBittorrent Web API 與硬鏈接 / Docker，210 行）、§20.5（名稱衝突檢查，21 行）。原文搬到新的 `docs/research/<slug>.md`，不改字，開頭一行說從 brief §20.x 搬來。已有研究檔的節：brief 有、研究檔沒有的段落，原文補進研究檔的〈從 brief 搬來〉段。
2. **brief 留**：每個事實一到兩行加來源（研究檔加錨點，或外部 URL）。保留版本號與查證日期，它們是版本行為的前提。
3. **plan、brief 其他章節或 `CLAUDE.md` 直接依賴的事實**（例：qBittorrent 發佈 port 必須是 8080）照樣在 brief 留一行。開工前 `grep -n '§20\.[1-7]\b'` 列出引用點，確認每個引用在壓縮後還找得到對應的那一行。
4. **章節號與小節標題不變**（`berth/`、`web/` 引用 §20.x 共 298 處）。
5. §20 開頭寫一句：細節在 `docs/research/`，本章只留結論與來源。

## 驗收

- [x] `scripts/docs_moved_lines.py` 對 `docs/design-brief.md` → `docs/research/*.md` 跑出「遺失 0」，輸出貼 Comments
- [x] §20.1–§20.7 每節前後行數表貼 Comments
- [x] 第 3 步的引用點清單與檢查結果貼 Comments
- [x] brief 到 research 的連結都指得到檔與錨點（跑一次檢查，貼輸出）
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

- `docs_moved_lines.py 6fb74108 docs/design-brief.md -- docs/research/*.md`：`removed 497 lines, found 497, missing 0`（placeholder 行「本節由查證子任務填入」留在 §20 開頭）。
- 前後行數／位元組（brief 節；前 → 後）：

| 節 | 行 | 位元組 | 研究檔 |
| --- | --- | --- | --- |
| 20.1 | 47 → 46 | 13,768 → 11,050 | jellyfin-12.md（補〈從 brief 搬來〉） |
| 20.2 | 210 → 80 | 29,698 → 19,669 | 新 qbittorrent-web-api.md |
| 20.3 | 72 → 62 | 20,762 → 14,250 | anime-episode-source.md（補） |
| 20.4 | 86 → 53 | 12,726 → 9,553 | profile-effect.md（補） |
| 20.5 | 21 → 6 | 1,367 → 859 | 新 name-conflict-check.md |
| 20.6 | 25 → 11 | 2,956 → 2,536 | m0-experiments.md（補） |
| 20.7 | 201 → 135 | 38,166 → 34,056 | 新 setup-api-facts.md（改用新檔，避免與 20.6 搶 m0-experiments.md） |

brief 整檔 1,875 → 1,615 行。
- 引用點：子代理逐節 grep `§20.x`（plan、PRODUCT.md、ADR、development、CONTEXT.md、berth/ web/ 註解），每條對到壓縮版一行；清單在各子代理報告，未逐條貼入。qBittorrent「發佈 port 必須 8080」實際在 §20.7（不在 §20.2），已保留。
- 連結檢查：brief → research 的檔與錨點全部存在；研究檔內原文的 `](research/…)` 改成 `](../research/…)`（行尾 normalize 後仍算「搬到」）。
- 未解／留意：(1) §20.7 只縮 11%，約 120 個引用點都咬具體數字，再縮要砍 Prowlarr 實測段；(2) 程式碼註解 `berth/services/jobs.py:241`、`tests/unit/test_torrent_source.py:4` 引 §20.7「ACG.RIP 不報 info hash」，`test_adapter_contracts.py:465` 引 §20.7 的 `temp_path_enabled`，§20.7 原文本來就沒有（後者在 m0-experiments），屬舊問題；(3) §20.4 樣本清單 brief 只留各類代表，完整清單在 profile-effect.md；(4) `docs/development/experiments.md:50` 仍寫「見 brief §20.1」，細節現在在研究檔。
- **沒跑 `/code-review`**（用子代理各自自驗代替），請使用者決定要不要補。
