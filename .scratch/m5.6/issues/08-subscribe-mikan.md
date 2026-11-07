# 08 — `rss.subscribe` 走 Mikan

**Status:** done

**Blocked by:** 04

**讀:** spec〈範圍〉C3、〈共同規則〉；研究文檔 §4 C3；brief §15、§20.12；plan §6〈rss〉、§7〈確認卡〉「訂閱的字幕組由人選」、§8.5

## 為什麼

訂閱現在有兩條路：`bangumi.search/read` 加 `rss.subscribe_mikan`，或 `rss.subscribe_search`。由模型自己選走哪一條，而在 Mikan 找番組的判斷寫在 skill 裡。這張票把 Mikan 這條路搬進程式：模型只說要訂哪部作品、要哪個字幕組。

## 做什麼

1. **設計先行**（`mattpocock-skills:codebase-design`）：「用作品的名字找 Mikan 番組、用開播日挑」放在哪一層（adapter、services，還是可以獨立測試的純函式），邊界寫進 Comments。
2. 新命令 `rss.subscribe`：輸入 `media_id` 與 `subgroup`（模型推薦的那一個）。伺服器用作品的中文、原名、羅馬拼音、英文名搜 Mikan，用 TMDB 的開播日挑番組；番組頁讀得到字幕組就出 Mikan 訂閱卡（沿用現有的 `SubgroupAsk`、第一批、`existing` 與數量閘的預覽）。
3. 找不到番組，或番組上沒有任何字幕組時，這張票先拒絕並說出原因（退回關鍵字來源是票 09）。
4. `@command`、登錄表、Route 照票 04 的規則（模型不給 `route_id`）。加進給模型的工具清單；舊的四支工具這張票先留著。
5. 文件：plan §6〈rss〉、§7〈確認卡〉；brief §15 有變動的話一起改。

## 驗收

- [x] 名字有幾種寫法、Mikan 回好幾個番組時，用開播日挑對（fixture 測試，包括同名不同年的作品）
- [x] 找到番組時出卡，字幕組選項、第一批、現有訂閱與數量閘照舊；核准後建的 Feed 與 `subscribe_mikan` 建的一樣（整合測試）
- [x] 找不到番組時提出被拒，理由交給模型
- [x] `test_command_marks.py`、`test_command_registry.py`、`test_agent_tools.py` 綠
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

### 2026-11-07 設計（`codebase-design`）：Mikan 的「找與挑」放在哪

- **挑選是純函式**：新模組 `parser/bangumi.py`，介面兩支：`same_work(snapshot, title)` 與
  `choose(snapshot, candidates) -> BangumiCandidate | None`（`BangumiCandidate(id, title, premiere)`）。
  規則與 `parser.binding.judge` 的「有把握」同一套：標題正規化、拆掉季名後與作品的某個名字相等，
  而且番組頁的開播日落在作品 `first_air_date` 前後 `PREMIERE_WINDOW` 內；命中兩個以上取最近的一個，
  沒有開播日時只在標題命中恰好一個時給它。同名不同年由開播日分開。
- **IO 在 adapter**：`adapters/rss/mikan.py` 已有 `search_page`（番組 id + 標題）與 `bangumi_page`
  （中文名 + 放送开始），不加新介面。
- **協調在 services**：`services/bangumi.py` 新增 internal 讀命令 `match_bangumi(session, factory,
  media_id)`：拿作品的名字逐個搜 Mikan（去重、最多四個詞，CJK 優先）、只讀標題命中的番組頁，
  `choose` 挑一個；找不到丟 `bangumi_not_found`、番組頁沒有字幕組丟 `bangumi_without_subgroups`，
  回既有的 `BangumiView`。
- **命令**：`services/rss.py` 新增 `rss.subscribe`，輸入只有 `media_id`、`subgroup`（名字）與 Route；
  解析出番組與字幕組後直接呼叫既有的 `_subscribe`（`subscribe_mikan` 的同一支），所以建的 Feed、
  Series 與補舊集完全一樣。`subgroup` 找不到是 `subgroup_not_found`（卡片之外的路徑才走得到）。
  卡片預覽（`agent._subscribe_preview`）呼叫同一支 `match_bangumi`，選項沿用 `SubgroupAsk`；
  人選的字幕組只蓋掉 `subgroup` 這一格，不新增隱藏參數。

### 2026-11-07 收尾

- **`berth bench`**（動了 `parser/`）：`overall` 904 檔，`auto_wrong` **0**（anime 0、tv 0、movie 0），
  與基準相同；`auto_correct` 255。
- **code-review 的取捨**（未改掉的兩條）：
  - 核准時重新解析番組與字幕組（卡片帶回的是字幕組名），所以按下確認會再打幾頁 Mikan；預覽與核准之間
    站上若變動，可能綁到與卡片顯示不同的番組。改成把 id 藏在卡片參數裡要多兩個模型看不到的欄位，
    與票上「輸入只有 `media_id` 與 `subgroup`」相衝，因此照現在的寫法。
  - 三個拒絕理由（`bangumi_not_found`、`bangumi_without_subgroups`、`subgroup_not_found`）
    只有助理那條路會產生，但 `RssRefusal` 是共用的封閉集合：REST 對照表（`api/rss.py` 的 `_STATUS`）、
    `schema.d.ts` 與 i18n 兩份都要有，網頁上不會看到它們。
- plan §6〈rss〉（端點）沒有改：`rss.subscribe` 沒有 HTTP 端點，給模型的工具清單在 §6〈agent〉，
  已同輪更新。
