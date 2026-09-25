# 08 — Tracer：Mikan 聚合 feed → 待綁定 → 手動綁定 → 入庫

**Status:** done

**Blocked by:** 01、02、04（RSS 無人值守的前提修補），07（fixture 與欄位）

**讀:** plan §2.4（`rss_*` 三張表）、§3.2（`rss_poller`）、§4.3（`ParseContext` 的季號與 offset）、§6（`rss` 那一列）、§7、§8.5、§11.4；brief §15、§19（「RSS 的形狀」）；`CONTEXT.md` 的 RSS 一節

## 做什麼

M3 的端到端最小版。**一條 Mikan 聚合 feed 走到 Jellyfin**，中間每一層都用最窄的做法：

1. **資料**：`rss_feeds`、`rss_series`、`rss_items` 三張表與 migration（plan §2.4 的欄位；用不到的欄位先不建，等到用它的那一票再加）。
2. **Mikan adapter**：照票 07 的 fixture 把聚合 feed 解析成統一的 Feed Item；從單集頁反查（番組 id, 字幕組 id），組成 RSS Series 的鍵。
3. **`rss_poller`**：一個 feed 一個 `interval_sec`（預設 15 分鐘），跟其他迴圈同一個形狀（lifespan 啟動、例外只記 log、失敗寫進自己那一列）。抓 → 解析 → 找到或長出 RSS Series → 寫 Feed Item。這一票只做同 Feed 的 GUID 去重，其餘去重在票 10。
4. **待綁定**：新長出的 RSS Series 一律 `media_id = NULL`，它的 item 狀態是 `unbound`、留著不送。自動綁定在票 09，這一票的綁定是**人工版本**，也就是之後 AI 與自動綁定都要走的那一個命令。
5. **綁定命令**：管理員選作品與 Route → RSS Series 綁定。第一次通向磁碟，所以照 plan §2.2 凍結 `folder_name`，然後把那個 Series 底下 `unbound` 的 item 送單（`trigger = rss`、`trigger_ref` = Series id）。
6. **規劃時讀 Series 的季號與 offset**：接上 `PlanContext` 已有的欄位。這一票只要讀得到；改正與重算在票 13。
7. **`/rss` 頁**：新頁面，先 `/impeccable shape`。最小範圍是 Feed 清單（新增、刪除、立即輪詢）、RSS Series 清單（待綁定排前面、綁定動作）、最近的 Feed Item。只有 admin。

新命令照票 05 立的規矩標副作用等級：新增 Feed、綁定 RSS Series 是 `reversible`（反向命令是刪除 Feed、解除綁定）。刪除 Feed 自己是否可逆，shape 時一起決定。

`plan §6` 的 `rss/rules` 那一組端點改成 series；brief §13 的 RSS 頁那一列（「規則清單」「規則試跑」）同步改詞。

## 驗收

- [x] 用票 07 的 Mikan fixture 當替身：加 feed → 輪詢一輪 → 長出 RSS Series，而且在待綁定清單 → 綁定作品與 Route → item 送單 → Fake qBittorrent 做完 → 規劃 → 入庫，帳本有那幾集（整合測試走完整條）
- [x] 同一個 feed 輪詢兩次，不會多出 item 或 Job（GUID 去重）
- [x] Mikan item 的發佈時間讀 `<torrent><pubDate>`（`https://mikanani.me/0.1/` 命名空間），不帶時區的值當 UTC+8，存成 UTC（單元測試，用票 07 能對照時區的那一筆；brief §20.11）
- [x] 綁定當下凍結 `folder_name`；綁定之前的 item 不送單
- [x] RSS Series 帶季號與 offset 時，規劃結果用的是它（單元或整合測試，雙向）
- [x] `rss/*` 全部 admin；`test_auth_api` 的整張表同步
- [x] 新命令都有副作用標記（票 05 的閘門是綠的）
- [x] 新增一個演練情境（`--scenario rss`），playwright 實跑加 feed → 綁定 → 看到 Job，1280 與 390，附結果
- [x] plan §2.4、§6、§7、brief §13 同步；CONTEXT.md 若有新詞一併補
- [x] lint、type、test 綠燈

## Comments

**2026-09-25 實作**（`/implement`）。

- 驗收對照：整條 tracer `tests/integration/test_rss.py::TestTheTracer`（帳本有 S01E11、S01E12，硬鏈接真的在）；
  GUID 去重 `TestGuidDedup`（第二輪只抓 feed 本身、不再抓單集頁）；UTC+8 `tests/unit/test_rss_mikan.py::TestPublishedAt`
  （與 acg.rip 同一個發佈差不到一秒）；凍結與不送 `TestBinding`；季號 offset 雙向 `TestSeasonAndOffset`（拿掉
  `plan._series_of` 那一行時 season=2 那一條轉紅，已驗）；權限 `test_auth_api.py` 的 `ACCESS` 多八條；命令標記
  `test_command_marks.py` 綠（`services/rss` 是新模組，不在豁免表）。
- **playwright 實跑**（`--scenario rss`，fake server）：1280 加 Feed → 立即輪詢「新 12 筆、長出 11 個 RSS Series、送出 0 筆」→
  《与你相恋到生命尽头》那一列綁定（搜尋框預填 `Kimi ga Shinu made Koi wo Shitai`、兩條 tvshows Route 不預選、選 Anime、
  確認區塊印 `Kimi ga Shinu made Koi wo Shitai (2026) [tmdbid-262000]` 與「綁定並送出 2 集」）→ `aria-live`「綁好了，送出 2 集。」
  → `/jobs` 兩筆 RSS、約 20 秒後都已入庫（各 1 個待確認：單季推論是 medium）。390 同一條：無橫向捲動（`scrollWidth - clientWidth = 0`），
  綁完焦點落在接替的那一列。同一條寫成 `web/e2e/rss.spec.ts`（`rss` / `rss-390` 兩個 project，每一步留整頁截圖在
  `web/test-results/`），兩條都綠。
- **shape**：`.scratch/m3/rss-shape.md`，三題照建議拍板（單頁堆疊待綁定在最上、在那一列就地綁定、刪 Feed 連 Item 一起刪而 Series 留著）。

**code-review（Standards / Spec 兩軸）**，已處理：區塊計數 `aria-hidden` + `sr-only` 帶單位；Feed 的空狀態照 DESIGN.md
（`well` 框、`ink` 散文、「打開 Mikan」）；沒有 Feed 時不畫 Item 段（shape §5）；送不出去的 Item 與 Feed 的上一輪問題改塗
`assigned`（卡住、下一輪再試，不是失敗）、Feed 那一塊的標籤從「輪詢失敗」改「上一輪有問題」（部分 Item 跳過不是整輪失敗）；
拿掉 `mikanime.tv`（shape 只認 mikanani.me）；`SeriesBinder` 的類型字改用自己的 i18n key；`actor_of` 的 docstring 不再宣稱
組 `rss:<series>`；plan §2.3 的 `trigger_ref` 改詞；`list_items` 的 `limit` 參數拿掉；`test_models` 的表清單加三張；
token 遮罩、待綁定列的展開區、「這一輪…」那一句補記進 shape。

未處理（留給後面的票或刻意不做）：

- `SeriesBinder` 的搜尋與結果清單與 `issues/WorkPicker.tsx` 幾乎同形、`preselect` 與 `media/SearchPanel` 的預選同一個邏輯：
  兩個真實案例了，第三個出現時（票 19 從 Media 頁訂閱）抽成共用元件。
- `services/rss._parse` 與 `_series_key` 各自 `match kind`、鍵是 `mikan:<a>:<b>` 字串再 `split` 回來：票 11 加 Nyaa 時
  改成依 `FeedKind` 查的一個 mapper（鍵的形狀那時才有第二種）。
- 命名 `RssItem` / `ItemView` 與 adapter 的 `FeedItem`、enum 的 `FeedItemStatus` 不一致（CONTEXT 的詞是 Feed Item）：
  ORM 與表名 `rss_items` 對齊，沒改。
- `SeriesOut.submitted` 只有綁定回的那一份有值：與其另開一個回應型別，先留著並在欄位註解說明。
- `delete_feed` 標 `reversible`：Item 的 `error` 與 Feed 的 `interval_sec` 回不來，但會送出的東西與綁定都回得來（shape §4 的根據）。
- 綁完待綁定段最後一列時焦點落在 Feed 段第一列而不是段落標題（整段消失了）；`Loading` 用 `well` 框而不是 `deck` 色條，
  與 `/issues` 同一個樣子。
- `pipeline/rss.py` 又一份 `Sleeper` / `Clock` 型別別名（第五個迴圈，既有慣例）。
