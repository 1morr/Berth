# 07 — 【研究】RSS fixture 與欄位事實

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §8.5、§11.4；brief §15、§20.6（Mikan / Nyaa 那一條）、§19（「RSS 的形狀」）；progress.md 2026-09-24「RSS 重新設計」那一條偏差（還沒寫進 brief 的實測事實）

## 做什麼

`mattpocock-skills:research`：先把欄位弄清楚，adapter 才寫得出來（plan §11.4「先抓 fixture 定欄位」）。輸出放 `docs/research/rss-sources.md`，結論摘進 brief §20 並附來源；§20.6 那一條劃掉。

要錄的 fixture（放測試 fixture 目錄，**去掉個人 token**）：

- **Mikan**：`/RSS/MyBangumi?token=` 聚合 feed、`/RSS/Bangumi?bangumiId=&subgroupid=` 單一 feed、一個單集頁（上面有單一 feed 的連結，是反查番組 id 與字幕組 id 的來源）、一個番組頁（中文標題、開播日期、bgm.tv 連結，票 09 的自動綁定靠它）。
- **Nyaa**：搜尋 feed 與使用者 feed，`nyaa:` 命名空間的實際欄位名。**從開發機連不上**，改走瀏覽器（claude-in-chrome 或 playwright）或 tavily-extract 取原文。
- **acg.rip**：搜尋 feed，要有夾著合集的那種。

每種來源要回答的問題：guid 的形狀與穩定性、有沒有 info hash（沒有的話 torrent URL 能不能先抓來算）、大小、發佈時間的時區、enclosure 的 type、做種數。

同時寫進 brief §20 的 2026-09-24 實測事實：聚合 feed 只有最近的集數、單集頁反查得到番組 id 與字幕組 id、單一 feed 有整季、acg.rip 搜尋 feed 夾合集、Nyaa 從開發機連不上。

`feedparser` 的版本與命名空間處理用 context7 查過再寫進研究檔。

## 驗收

- [ ] `docs/research/rss-sources.md`：三個來源各自的欄位表與範例，每條事實附來源（網址 + 取得日期）
- [ ] fixture 已入庫、不含 token 或帳號資訊（貼 grep 結果）
- [ ] brief §20 有一節 RSS 來源事實（含上面五條實測）；§20.6 那一條劃掉並連到新節
- [ ] plan §8.5 的「實際欄位名以 M3 抓的 fixture 為準」改成真的欄位，「跨 feed 以 info_hash 去重，M3 決定是否做」有結論
