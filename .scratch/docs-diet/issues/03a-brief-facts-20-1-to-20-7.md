# 03a — brief §20 壓縮（上）：§20.1–§20.7

**Status:** ready-for-agent

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

- [ ] `scripts/docs_moved_lines.py` 對 `docs/design-brief.md` → `docs/research/*.md` 跑出「遺失 0」，輸出貼 Comments
- [ ] §20.1–§20.7 每節前後行數表貼 Comments
- [ ] 第 3 步的引用點清單與檢查結果貼 Comments
- [ ] brief 到 research 的連結都指得到檔與錨點（跑一次檢查，貼輸出）
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
