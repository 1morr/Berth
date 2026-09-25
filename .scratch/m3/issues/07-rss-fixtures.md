# 07 — 【研究】RSS fixture 與欄位事實

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §8.5、§11.4；brief §15、§20.6（Mikan / Nyaa 那一條）、§19（「RSS 的形狀」）；progress.md 2026-09-24「RSS 重新設計」那一條偏差（還沒寫進 brief 的實測事實）

## 做什麼

`mattpocock-skills:research`：先把欄位弄清楚，adapter 才寫得出來（plan §11.4「先抓 fixture 定欄位」）。輸出放 `docs/research/rss-sources.md`，結論摘進 brief §20 並附來源；§20.6 那一條劃掉。

**已知的地雷**（brief §20.11，2026-09-24 試跑時量到）：Mikan 的發佈時間不在標準的 `<item><pubDate>`，在 `https://mikanani.me/0.1/` 命名空間的 `<torrent><pubDate>`，而且不帶時區、實際是 UTC+8。fixture 要各站留一筆能對照時區的（同一個發佈在 ACG.RIP 帶 `-0700`），票 14 的播出日比對靠它。

要錄的 fixture（放測試 fixture 目錄，**去掉個人 token**）：

- **Mikan**：`/RSS/MyBangumi?token=` 聚合 feed、`/RSS/Bangumi?bangumiId=&subgroupid=` 單一 feed、一個單集頁（上面有單一 feed 的連結，是反查番組 id 與字幕組 id 的來源）、一個番組頁（中文標題、開播日期、bgm.tv 連結，票 09 的自動綁定靠它）。
- **Nyaa**：搜尋 feed 與使用者 feed，`nyaa:` 命名空間的實際欄位名。**從開發機連不上**，改走瀏覽器（claude-in-chrome 或 playwright）或 tavily-extract 取原文。
- **acg.rip**：搜尋 feed，要有夾著合集的那種。

每種來源要回答的問題：guid 的形狀與穩定性、有沒有 info hash（沒有的話 torrent URL 能不能先抓來算）、大小、發佈時間的時區、enclosure 的 type、做種數。

同時寫進 brief §20 的 2026-09-24 實測事實：聚合 feed 只有最近的集數、單集頁反查得到番組 id 與字幕組 id、單一 feed 有整季、acg.rip 搜尋 feed 夾合集、Nyaa 從開發機連不上。

`feedparser` 的版本與命名空間處理用 context7 查過再寫進研究檔。

## 驗收

- [x] `docs/research/rss-sources.md`：三個來源各自的欄位表與範例，每條事實附來源（網址 + 取得日期）
- [x] fixture 已入庫、不含 token 或帳號資訊（貼 grep 結果）
- [x] brief §20 有一節 RSS 來源事實（含上面五條實測）；§20.6 那一條劃掉並連到新節
- [x] plan §8.5 的「實際欄位名以 M3 抓的 fixture 為準」改成真的欄位，「跨 feed 以 info_hash 去重，M3 決定是否做」有結論

## Comments

2026-09-25 收尾。fixture 在 `tests/fixtures/http/{mikan,nyaa,acgrip}/`（來源表在同目錄 README）；token 檢查：

```text
$ grep -rno 'token=[^&<"]*' tests/fixtures/http/mikan tests/fixtures/http/nyaa tests/fixtures/http/acgrip
tests/fixtures/http/mikan/rss-mybangumi.xml:1:token=REDACTED
$ grep -rc 'RequestVerificationToken" type="hidden" value="CfDJ8x' tests/fixtures/http/mikan/*.html
home-bangumi.4009.html:2
home-episode.85c93c23.html:2
```

- 聚合 feed 的 token 不經過 agent（權限機制擋下讀取），由使用者自己下載；channel `<link>` 的 token 換成 `REDACTED`。
- Nyaa 從開發機的 curl / Python / Node 都連不上，claude-in-chrome 也拒絕這個站；playwright 瀏覽器連得上，在頁內 `fetch()` 取原文。
- 多錄了 `mikan/rss-classic.xml`（票面沒列）：聚合 feed 到手之前它是「三種 Mikan feed 同格式」的第三個樣本，也說明 Classic 夾合集。
- 分析腳本入庫成 `scripts/experiments/rss_sources.py`（code-review Standards 軸：plan §10「一次性但保留腳本」），`uv run --no-project --python 3.13 --with feedparser python scripts/experiments/rss_sources.py`；feedparser 不進專案依賴，票 08 加依賴時再決定腳本要不要改用專案環境。
- 沒解、留給之後的票（研究檔 §11）：同一個發佈在 Mikan 與 acg.rip 是不是同一個 info hash（要下載 acg.rip 的 `.torrent`，票 10 的去重會用到）；MyBangumi 的上限是筆數還是時間窗；Mikan GB 級大小的單位；acg.rip 搜尋 feed 的 30 筆上限與分頁。
- 判斷題、沒改：三站欄位表在 brief §20.12（事實）、plan §8.5（取法）、研究檔 §9（理由）三處重疊，改一處要同步。
