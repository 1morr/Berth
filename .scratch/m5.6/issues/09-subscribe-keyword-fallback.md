# 09 — `rss.subscribe` 退回關鍵字來源，拿掉舊的四支工具

**Status:** done

**Blocked by:** 07、08

**讀:** spec〈範圍〉C3、〈驗收〉；研究文檔 §4 C3 與 `subscribe` 草稿；plan §7〈確認卡〉「訂閱的字幕組由人選」；票 08 的 Comments

## 為什麼

把 C3 收尾：Mikan 找不到時伺服器自己改走 nyaa / acg.rip 關鍵字，模型就不用再懂兩條路。改完之後，給模型的工具從 22 支減到 18 支。

## 做什麼

1. `rss.subscribe` 在 Mikan 找不到番組、或番組上沒有模型給的那個字幕組時，改走關鍵字來源（沿用 `subscribe_search` 的搜尋、字幕組與第一批）。
2. 卡片列出找到的字幕組**與來源**（Mikan / 關鍵字站），由人選一個；兩條路都有那個字幕組時怎麼排、預選哪一個，在這張票定並寫進 Comments。讀不到來源時照舊不出卡（`feed_unreachable`）。
3. 給模型的工具清單拿掉 `bangumi.search_bangumi`、`bangumi.read_bangumi`、`rss.subscribe_mikan`、`rss.subscribe_search`。命令本身留著，RSS 頁還在用。
4. 照研究文檔的草稿改寫 `subscribe` skill（≤ 20 行），讓 skill 總行數 ≤ 80。
5. 確認卡的訂閱列顯示來源，文案走 i18n。
6. 文件：brief §14、plan §6〈rss〉〈agent〉、§7〈確認卡〉。

## 驗收

- [x] Mikan 沒有番組時走關鍵字來源，卡片寫出來源；Mikan 有番組但沒有那個字幕組時也是（整合測試）
- [x] 給模型的工具 18 支，由測試斷言清單
- [x] RSS 頁的 Mikan 訂閱與關鍵字訂閱行為不變（既有測試綠）
- [x] `subscribe` skill ≤ 20 行，skill 總行數閘門綠
- [x] 卡片的來源顯示有 vitest；brief §14、plan §6、§7 已改
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

### 2026-11-07 設計（`codebase-design`）：退回關鍵字來源的邊界

- **找與挑在 services**：新 internal 讀命令 `rss.subscription_offers(media_id, subgroup)`。先用
  `services.bangumi.match_bangumi` 找番組；找到而且番組頁上有模型給的那個字幕組時只回它那一頁的
  選項，否則再讀兩個關鍵字站的搜尋（`rss.search_subgroups`）。卡片預覽（`agent._subscribe_preview`）
  與核准（`rss.subscribe`）共用同一支；選項的參數帶著 `kind`、`term`、`subgroup`，核准時蓋過
  存下的那幾格（`kind` 是 `FeedKind`：與 `subscribe_search` 的同一格同名，卡片上的標籤仍是「來源」）。
- **關鍵字站拿哪個名字**：`rss.keyword_terms`，各站最多試 `MAX_KEYWORD_TERMS = 2` 個名字，第一個有
  字幕組的就夠。acg.rip 中文優先（`parser.bangumi.names` 的順序），nyaa 原文與英文優先（同一個
  集合把 CJK 的排後面）。兩個站都問：nyaa 的發佈名多半是原文或英文、acg.rip 是中文，只問一邊會
  漏掉半個站。
- **讀不到不換來源**：Mikan 讀不到是 `feed_unreachable`，不退回關鍵字（分不出「站上沒有」與
  「暫時讀不到」）。兩個關鍵字站都讀不到才是 `feed_unreachable`；讀得到而一個字幕組都沒有是新的
  拒絕 `subgroups_not_found`（`detail` 是作品名）。一次搜尋讀不到不擋另一個站（與 `match_bangumi`
  同一個取捨）。
- **排序**：Mikan 在前（番組頁順序），再 nyaa、再 acg.rip（各站照筆數多的在前）。
- **同一個字幕組兩條路都有時**：兩個都列（訂起來是兩條不一樣的 Feed：Mikan 單一 feed 對關鍵字
  搜尋 feed），**預選卡片順序上的第一個**。實務上模型給的那一組在 Mikan 就不會退，所以重疊只會在
  別的字幕組上（人自己改選），預選不受影響；退到關鍵字時 nyaa 在前，所以兩站都有時預選 nyaa。
- **命令輸入多了三格**：`kind`、`term`、`first_batch`。模型看不到它們（卡片列是新的
  `agent.WorkSubscriptionRow`，只有 `media_id` 與 `subgroup`），由卡片上的選項帶回來；關鍵字那一條
  沿用 `subscribe_search` 的第一批與第一輪選擇（「下載這些並追之後的」／「只追之後的」）。
- **舊的兩張訂閱卡沒有人提出了**：拿掉四支工具之後 `rss.subscribe_mikan`／`rss.subscribe_search`
  的卡片預覽（`_mikan_preview`、`_search_preview`、`SearchSubscriptionRow`、`_bangumi_options`）
  沒有任何呼叫端，連同守它們的測試一起刪；`subscribe_mikan`／`subscribe_search` 的命令與 REST
  端點留著（RSS 頁與作品頁）。新的卡走 `rss.subscribe`，原本那幾條測試的場景改寫到它上面。
- 判準的一致性：預選與核准都用 `rss.offer_named`（`normalize_title` 後相等），與 `subgroup_named`
  同一套。
- 名字排序的判斷只有一份：`parser.bangumi.names(..., latin_first=True)`，`rss.keyword_terms` 只是
  兩次呼叫與截斷。

### 2026-11-07 收尾

- 工具 22 → 18（`tests/unit/test_agent_tools.py::test_the_model_has_eighteen_tools`）。
- `subscribe` skill 20 行（`tests/unit/test_skills.py` 的 `FILE_LIMITS`），三份合計 66 行。
- `rss.subscribe` 沒有 HTTP 端點；`subgroups_not_found` 仍在 `RssRefusal` 的封閉集合裡（REST 對照表、
  `schema.d.ts`、i18n 兩份都要有），只有卡片之外的路徑（人提出的、MCP）走得到。
- **code-review 的取捨**（兩軸，已處理的三條）：
  - `source` 改名 `kind`：與 `subscribe_search` 同一格同名，也不再讓 CONTEXT 的「來源」多一種意思。
  - 名字排序收進 `parser.bangumi.names`，`rss` 不再自己複製一份 CJK 判斷。
  - `rss.subscribe` 的輸入有 `first_batch`（關鍵字那一條要有第一輪的選擇），但 Mikan 的列在卡上
    看不到它：`agent._first_batch_rows` 只替選了關鍵字那一條的列回報 `first_batch_chosen_on_card`，
    不再跟模型說「人選了第一輪」。
  - 前端兩種訂閱卡的列合成一支 `SubscribeRowBody`（以 `look` 描述來源、搜尋詞、字幕組與要不要標
    來源），舊的 `rss.subscribe_mikan`／`rss.subscribe_search` 卡照舊畫得出來。
- **UI 實跑**：`pnpm -C web e2e --project=agent agent.spec.ts`（1280）與 `--project=agent-390`（390）
  都綠；新增的一條走「訂閱 SPY×FAMILY」→ 兩條路的字幕組與來源（MIKAN ×3、ACG.RIP ×4）→ 選
  LoliHouse 送整季、再訂一次選 ToonsHub 送第一批。截圖在
  `web/test-results/agent-以作品訂閱…/subscribe-work*.png`。假模型的台詞與頁面同輪改
  （`scripts/fake_setup_server.py`、`docs/development/fake-backend.md`）。
