# 08 — `rss.subscribe` 走 Mikan

**Status:** ready-for-agent

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

- [ ] 名字有幾種寫法、Mikan 回好幾個番組時，用開播日挑對（fixture 測試，包括同名不同年的作品）
- [ ] 找到番組時出卡，字幕組選項、第一批、現有訂閱與數量閘照舊；核准後建的 Feed 與 `subscribe_mikan` 建的一樣（整合測試）
- [ ] 找不到番組時提出被拒，理由交給模型
- [ ] `test_command_marks.py`、`test_command_registry.py`、`test_agent_tools.py` 綠
- [ ] 全部檢查、pytest 綠；progress.md 已更新

## Comments
