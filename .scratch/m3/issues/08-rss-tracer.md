# 08 — Tracer：Mikan 聚合 feed → 待綁定 → 手動綁定 → 入庫

**Status:** ready-for-agent

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

- [ ] 用票 07 的 Mikan fixture 當替身：加 feed → 輪詢一輪 → 長出 RSS Series，而且在待綁定清單 → 綁定作品與 Route → item 送單 → Fake qBittorrent 做完 → 規劃 → 入庫，帳本有那幾集（整合測試走完整條）
- [ ] 同一個 feed 輪詢兩次，不會多出 item 或 Job（GUID 去重）
- [ ] Mikan item 的發佈時間讀 `<torrent><pubDate>`（`https://mikanani.me/0.1/` 命名空間），不帶時區的值當 UTC+8，存成 UTC（單元測試，用票 07 能對照時區的那一筆；brief §20.11）
- [ ] 綁定當下凍結 `folder_name`；綁定之前的 item 不送單
- [ ] RSS Series 帶季號與 offset 時，規劃結果用的是它（單元或整合測試，雙向）
- [ ] `rss/*` 全部 admin；`test_auth_api` 的整張表同步
- [ ] 新命令都有副作用標記（票 05 的閘門是綠的）
- [ ] 新增一個演練情境（`--scenario rss`），playwright 實跑加 feed → 綁定 → 看到 Job，1280 與 390，附結果
- [ ] plan §2.4、§6、§7、brief §13 同步；CONTEXT.md 若有新詞一併補
- [ ] lint、type、test 綠燈
