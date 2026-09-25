# 11 — Nyaa 與 acg.rip adapter + 新 Feed 第一輪預覽

**Status:** done

**Blocked by:** 10（預覽要畫得出排除與重複）

**讀:** plan §2.4（`primed_at`、`rss_series.key`）、§8.5、§11.4；brief §15（「Feed」「RSS Series」「補舊集」最後一句）；`docs/research/rss-sources.md`

## 做什麼

**兩個 adapter**：照票 07 的 fixture，Nyaa（搜尋 feed、使用者 feed）與 acg.rip（搜尋 feed）各一個 mapper，輸出同一種 Feed Item。

**非 Mikan 的 RSS Series 鍵**：標題骨幹 + 字幕組（AutoBangumi 的做法，brief §15）。骨幹 = 去掉字幕組、集號、tags 之後的標題；正規化規則沿用解析器現有的，不另寫一份。同一部作品的兩個字幕組是兩個 RSS Series。自動綁定走票 09 的同一條路；這些來源沒有番組頁，所以候選只從標題來。

**新 Feed 的第一輪預覽**（brief §15）：搜尋類 feed 第一輪就帶著歷史，所以第一輪不直接下載，而是列成預覽，使用者選「全部下載」或「只追之後的」。選完之後寫 `primed_at`。預覽裡要看得到排除與重複（票 10）。Mikan 聚合 feed 沒有這個問題（只有最近的集數），是否也要預覽在 shape 時決定並寫進 plan。

## 驗收

- [x] 兩個 adapter 各有契約測試（fixture → Feed Item 欄位）
- [x] 標題骨幹：同一部作品不同集數得到同一個鍵、不同字幕組得到不同鍵（單元測試，含 fixture 裡的真實標題）
- [x] 新增搜尋 feed → 第一輪不送單、出現預覽 → 「只追之後的」之後舊的不送、新的送；「全部下載」之後全送（整合測試，雙向）
- [x] acg.rip 搜尋 feed 裡的合集在預覽裡顯示為被排除（對應 M3 驗收「合集被排除」）
- [x] playwright 實跑預覽，1280 與 390，附結果
- [x] lint、type、test 綠燈

## Comments

- 2026-09-25 實作（`/implement`）。shape 在 `.scratch/m3/preview-shape.md`（三題照建議拍板：頁首獨立一段、摘要 + 依結果分組、Mikan 不走預覽）。
- playwright `rss-preview` / `rss-preview-390` 通過：新 acg.rip feed（《上伊那牡丹》30 筆）→ 立即輪詢 → 頁首「會送出 0 · 綁定之後送 22 · 排除 8 · 重複 0」→ 打開「排除」看到 8 筆合集（`[01-12 合集]`、`[第01-12話]`、`[Vol.1]` 等，每筆「不是單集…」）→「只追之後的」→ 那一塊消失、Feed Item 清單 22 筆「略過」、8 筆「已排除」。截圖在 `web/test-results/rss-preview-*/{1-preview,2-excluded,3-passed}.png`。實跑改了一處：兩顆動作鍵原本在 22 筆清單之後，390 寬要捲好幾屏，搬到摘要下面（shape §3 已補）。
- 實跑抓到解析器漏認三種季包（`[Vol.1]`、`(Season 01) … (Batch)`、`S01 (Batch)`，研究檔 §6 列為要認得的寫法）：`release_kind` 對自己一格括號的 `(Batch)` / `[Vol.N]` 回 `batch`，紅 → 綠；`berth bench` 172 / 0 不變。
- code-review 修了：`prime_feed` 條件式寫 `primed_at`（兩個分頁同時選時後到的是 409，紅 → 綠）、還沒讀過的 Feed 不收「全部下載」（409 `feed_unread`，紅 → 綠）、`prime_feed` 改標 `irreversible`、`skeleton` 在組名後還有一格 tag 時退化（`[Group] [Other] Title - 01`，紅 → 綠）、`enclosure` 抽到 `feed.py`、`Group` 的 prop 改名 `folds`、`approx_bytes` 的測試搬到 `test_rss_feed.py`。
- 沒處理、記下：
  - **`prime_feed(later)` 裡的輪詢與背景 poller 同時寫同一批 guid** 會撞 `(feed_id, guid)` unique，冒成 500（「立即輪詢」本來就有同一個窗口）；重按一次就好。要修的話是 `_record` 用 `INSERT … ON CONFLICT DO NOTHING`。
  - **預覽沒有叫 `_sent_before`**：刪掉 Feed 再加回來時，同一個 RSS Series 自己送過的在預覽裡是「重複：同一個 torrent 已經送過」，真的送單時認回成已送單——兩者都不會重下，只是說法不同。acg.rip 不報 hash，那時已送過的會列在「會送出」，送單時由 `add_download` 認出是同一個 Job。
  - **「全部下載」不重讀 feed**：預覽到按下確認之間 poller 新寫入的幾筆也會一起送；確認區的數字可能少算。方向（多送近期的集數）可以接受。
  - **讀不出組名的發佈鍵尾是空的**：兩個都沒有組名的上傳者、同一部作品會併進同一個 Series。實測 fixture 裡沒有這種（guessit 讀得出結尾的 `-VARYG`、`-Tsundere-Raws`）。
  - **切集號的 `_TITLE_END` 是新寫的一份**：解析器既有的規則回的是集號的值，這裡要的是標題在哪裡結束；組名、播出檔期與正規化（`undecorate`、`normalize_cjk`、`normalize_title`）都重用解析器的。
  - **來源分支散在五處**（`_parse`、`_series_key`、`_NO_PREVIEW`、`_series` 的 `mikan:` 前綴、`_clues` 的番組 id）：加第四站（dmhy、generic）時一起收成一張表。
  - **`rss_items.torrent_url` 有時存 magnet**（Nyaa 的 `&m`）：`add_download` 兩種都收，欄位名沒改。
  - **「只追之後的」之後，只有擋下與略過的 Item 的 RSS Series 仍在待綁定、寫「留著 0 集」**（票 10 起的行為，搜尋 feed 讓它更常見）：它們之後的新集數仍要綁定才送，所以留著；要不要收起來留給 M3 收尾的 critique。
  - 前端 `Group` 的每一列與「最近的 Feed Item」那一列形狀相近，沒有抽共用元件。
