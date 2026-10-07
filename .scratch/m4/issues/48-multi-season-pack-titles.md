# 48 — 「S01 + S02」「S1-S2」讀成季包，不是 S01E02

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S6 RSS 那列、§3.2 RSS 那列、改進清單 P2-6）；brief §6.3、§6.6、§6.9；plan §4.1、§4.6

## 為什麼（2026-10-06 審計，實測）

- 用一次性 RSS 連結讀 `acg.rip/.xml?term=Frieren`，「S01 + S02」與「S1-S2」兩包被標成 `S01E02`。截圖 s6-08。
- 沒有送單，所以不知道會不會影響自動綁定；要先查清楚。

## 做什麼

1. 先把那兩個標題（與同類的變體）加進 benchmark fixture，確認是紅燈。
2. 走 tdd 修發佈名解析，讀成多季合集（brief §6.6）。
3. 查清楚它對 RSS 自動綁定與送單的影響，結論寫在 Comments。

## 驗收

- [x] fixture 先紅後綠；兩個標題讀成 S01–S02 的季包（紅燈在發佈名的單元測試，bench 語料修之前就是綠的，見 Comments）
- [x] `berth bench` 的 `auto_wrong` 不上升（前後數字貼在 Comments）
- [x] 對 RSS 自動綁定的影響有結論
- [x] 全部檢查（`pre-commit run --all-files`）、test 綠燈

## Comments

**根因**：guessit 對 `S01 + S02`、`S1-S2` 回 `season: [1, 2]`，`_numbers` 裡為 `Season 3 [04]` 寫的那一條把清單的第二個數字當成集號。修法：`ReleaseInfo.season_end`；`_SEASON_SPAN` 要兩邊都有季的前綴（`S01 + S02`、`S1-S2`、`S01 S02`、`S01~S03`、`Season 1 + Season 2`）→ `season`–`season_end`、`release_kind = batch`；明寫的集號照讀；`merge_release` 不從多季包名補季號；一次性連結沒選作品時不聲稱季號。刻意不認：`Season 1-2`、`S01-03`（第二個數字沒有季的前綴，與 `Season 3 - 50` 分不開，維持原讀法）。

**語料**：`anime/frieren-s1-s2-xspitfire911`（acg.rip 361401，38 檔）、`anime/frieren-s1-s2-reinforce`（acg.rip 360101，475 檔）。兩筆在 bench 上**修之前就不紅**——檔名都帶得出答案（Xspitfire911 明寫 `S02E01`；ReinForce 的 `29` 靠誤讀出的 `season: 1` 補進去，在這份把第二季併進第 1 季的快照上碰巧對）。紅燈落在 `tests/unit/test_parser_release.py`（多季 7 種寫法、merge 不補季號）、`test_rss_exclusion.py`（合集預設排除）與 `tests/integration/test_rss_api.py`（一次性連結）。

**`berth bench`**（40 筆語料、904 檔）：修之前 auto_correct 253、auto_wrong 0、review 86、high 0/150 wrong、medium 0/103 wrong；修之後 auto_correct 253、auto_wrong 0、review 86、high 0/112、medium 0/141。差別只有 ReinForce 38 集從 high（誤讀的「明說季號」）變成 medium（「TMDB 只有一季、只有集號」，理由對了）。baseline 不動。

**對 RSS 自動綁定與送單的影響（結論）**：
- **綁定不受影響**：acg.rip / Nyaa 的 RSS Series 鍵是 `title_key`（骨幹 + 字幕組），只用 `parse_release(...).group`；非 Mikan 來源沒有番組頁，`judge` 一律留給人，不會自動綁定。
- **送單受影響（已修）**：「不自動下載合集」（`exclude_not_single`，預設開）看 `release_kind is not SINGLE`。修之前這兩包是 `single`，所以不會被排除——人把它們那個 RSS Series 綁到芙莉蓮之後，50 GB / 113 GB 的整包會被當成一集自動送單（送單後的規劃是逐檔的，入庫本身不會錯，錯的是不該自動下載）。修之後是 `batch`，預設排除。
- 已經寫進資料庫的舊 Item：待綁定的那幾筆在 `bind_series` 綁上時會跑 `_rescreen`，照新判讀排除；已經綁好、已送出的不回溯。
- 預覽：有作品時 `estimate` 對多季一包回「判斷不出來」（與單季包 `S01` 現在一樣）；沒有 API 欄位說得出 `S01–S02`，畫面靠 `batch` 標記。要顯示季的範圍另開票。

**code-review（兩軸 opus）**：已修——明寫的集號被一起丟掉（`S01-S02 [01-24]`、`S1+S2 - 05`、`第13集`）、`S01 S02` / `S01.S02` 沒認、`第二季` 同時出現時 guessit 的 `[1, 2]` 仍被讀成第 2 集、`Season 1-2 S01-S02` 落進 `_LOOSE_RANGE`、`_season_span` 的分支沒測試、brief 用「季包」與 CONTEXT 的「季包」（單季整包）撞名。未處理：
- 「有 `season_end` 時 `season` 不算數」寫在 `merge_release` 與 `oneshot._item` 兩處（Duplicated Code，判斷題）：兩處語意不同（一個是不補、一個是不顯示），目前只有兩個消費點，不先抽屬性。
- 合併後的檔案從 torrent 名補到 `release_kind = batch`（`_empty` 把 SINGLE 當空值）：`(Batch)` 本來就這樣，不是這次引入，也沒有消費點讀檔案的 `release_kind`。
- `matched_tokens` 沒記多季的判讀：這個欄位只收詞典認出的片段，guessit 與其他後處理一律不記，不在這票改。
