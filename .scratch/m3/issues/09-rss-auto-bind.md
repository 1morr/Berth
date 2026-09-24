# 09 — RSS Series 自動綁定

**Status:** ready-for-agent

**Blocked by:** 08

**讀:** plan §4.3（`candidates`）、§8.3、§11.4；brief §6.4 第 2 點（標題比對）、§6.5、§15（「綁定」）；`docs/research/rss-sources.md`（Mikan 番組頁的欄位）

## 做什麼

使用者 2026-09-24 拍板：有把握就自動綁定，沒把握的進待綁定清單。

**候選從哪來**：第一次見到的 RSS Series，用 Mikan 番組頁的中文標題、開播日期、bgm.tv 連結，加上 Feed Item 標題解析出的標題骨幹，去 TMDB 搜。這正是 plan §4.3 說的 `candidates`，目前一直沒有呼叫端去搜（2026-09-24 審查點出的落差）。

**什麼叫有把握**：規則要寫成封閉集合的理由碼，形狀照解析器的 `reasons`。起點是 brief §6.5「標題 + 年份精確命中」：中文或原文標題正規化後相等，**而且**開播日期落在 TMDB 那一季的首播附近。只命中一個候選才算；兩個以上或沒有就留在待綁定，畫面列出候選讓人一鍵選。規則門檻先寫、再用票 07 的 fixture 與 `MyBangumi` 裡的真實作品量一次。

**自動綁定走票 08 的同一個綁定命令**，actor 是 `system`（`bound_by = system`），所以之後改綁、解除綁定都是同一條路。

Route 怎麼選：TMDB 類型推得出電影或劇集，同類型只有一條啟用的 Route 時才自動選；否則留在待綁定並預填作品。

## 驗收

- [ ] 用 fixture 裡的作品：命中唯一候選的自動綁定並送單，`bound_by = system`，時間線說得出依據（整合測試）
- [ ] 同名不同年、兩個候選、沒有候選，三種情況都留在待綁定，理由碼不同（單元測試）
- [ ] 待綁定清單列出候選，一鍵選定就走綁定命令（前端測試 + playwright 實跑）
- [ ] 同類型有兩條 Route 時不自動綁定
- [ ] 規則門檻的量測結果記在 `docs/research/rss-sources.md` 或本票 Comments（自動綁了幾部、錯了幾部）
- [ ] lint、type、test 綠燈
