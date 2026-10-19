# 110 — 新增 Feed 時就能設排除條件

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §3.2（`rss_poller`）、§6 rss；brief §15「全部接受，只排除」；`berth/services/rss.py` 的 `add_feed`、`set_feed_exclusions`、`_screen`、`_rescreen`；`berth/api/rss.py` 的 `FeedIn`；`web/src/rss/FeedSection.tsx` 的 `AddFeed`、`web/src/rss/RulesEditor.tsx`

## 為什麼

使用者 2026-10-19 問 Feed 的排除條件怎麼作用、能不能在新增時就設。查下來，**現在的流程有時間差**，不只是方便與否的問題：

- `add_feed` 不當場輪詢，但 `rss_poller` 每 30 秒醒一次，`last_polled_at` 是空的 Feed 下一次醒來就輪到。
- Mikan 在 `_NO_PREVIEW` 裡，新增的那一刻就寫 `primed_at`：第一輪就自動綁定、補整季、直接送單。
- 使用者新增完再展開 Feed 卡片加規則時，通常已過了 30 秒。`_rescreen` 只重看還沒送出的（`unbound` / `matched`），已經送進 qBittorrent 的擋不住。

Nyaa / acg.rip 第一輪停在預覽，選擇之前加的規則都來得及，所以影響主要在 Mikan。但新增表單不分來源，一起做。

## 做什麼

1. **後端**（`mattpocock-skills:tdd`）：`FeedIn` 收選填的 `exclusions: list[str]`，預設空；`add_feed` 先走 `_normalized_rules` 驗證，寫壞的回 422 `rule_invalid`（與 `PUT` Feed 排除條件同一種拒絕），再與 Feed 一起寫進 `exclude_json`。驗證在寫入之前做，被拒時不留下 Feed。
2. **前端**：`AddFeed` 表單加「排除條件」，沿用 `RulesEditor` 那一套，包括建議按鈕（720p、简体、简日…）與規則格式說明。規則先記在表單裡，按「加入」時跟著 `POST /rss/feeds` 一起送；送出前不另打 API。i18n 的 zh-Hant、en 並列。
3. **說明**：表單上那一格的說明要讓人知道「Mikan 加入之後很快就會開始下載，要排除的現在就加」，用詞與 Feed 卡片的 `rss.rules.feedLede` 一致。
4. **文件**：plan §6 rss（`POST /rss/feeds` 的欄位）；CHANGELOG；progress.md session 紀錄。

## 不做

- 新增 Mikan Feed 時改成先預覽：那是推翻 brief §15 的決定，沒有被要求。
- 從作品頁訂閱建出的 Mikan 單一 Feed 不加這一格：它只有一個番組 × 字幕組，要排除的用 Series 那一層。

## 驗收

- [x] `POST /rss/feeds` 帶 `exclusions` 時寫進 Feed；第一輪寫下的 Item 照它擋下、不送出（pytest）
- [x] 規則寫壞時回 422 `rule_invalid`，而且沒有長出 Feed（pytest，做變異驗證）
- [x] 新增表單可以加、刪規則，按建議按鈕加規則；送出後 Feed 卡片顯示同一組（vitest，zh-Hant 與 en）
- [x] playwright 實跑新增帶規則的 Feed，附截圖（1280 與 390）
- [x] 全部檢查、pytest、vitest 綠；plan、CHANGELOG、progress.md 已更新

## Comments

- 變異驗證（第二條驗收）：把 `_normalized_rules` 挪到 `commit` 之後再寫一次，`test_a_broken_rule_leaves_no_feed` 紅（`assert 1 == 0`，留下了 Feed），還原後綠。沒有編進測試檔：它驗的是行為測試本身會不會抓到，不是靜態規則。
- 截圖：`110-feed-exclusions-on-add/add-form-1280.png`、`add-form-390.png`（裁自 `web/e2e/rss-exclusions.spec.ts` 的 `3-rules-on-add` 整頁截圖）。
- code-review Spec 軸：規則欄打了字、沒按「加入規則」就按「加入」時那一條原本會被丟掉——Mikan 正是這張票要防的情境。已改：加入欄的草稿由表單持有，送出時一起帶上（vitest 一條，做過變異）；送出中規則欄鎖住。
- 未處理（code-review，判斷題）：`OneshotSection` 仍有自己的「拒絕 → 句子」串接（多一個 `feed_unreachable` 特例），沒併進 `rssProblem`；`addFeed` 四個位置參數沒改成物件；`addLede` 前半句與 `feedLede` 逐字相同、沒有閘門守同步；e2e `rss-exclusions` 改了既有情境（12 集由「重複」改成被 Feed 規則擋下，「重複」從 2 筆剩 1 筆，路徑仍在）。
