# 08 — 時間表資料源實驗

**Status:** done

**Blocked by:** None (can start immediately；可與 07 平行)

**讀:** spec〈範圍〉「時間表」的資料那一條；brief §20.3〈放送時間表的來源〉、§10；`docs/development.md`（`TMDB_API_KEY`）；skill `mattpocock-skills:prototype`

## 為什麼

時間表預定以 TMDB 為主幹（有作品 id、海報、zh-TW），但 discover 的條件與它對當季新番的覆蓋率還沒實測（brief §20.3）。09 用哪個來源當主幹要看這個結果。

## 做什麼

1. 寫 `scripts/experiments/schedule_sources.py`（保留，下次換季重量；plan §10）：
   - 用 TMDB discover（或 `tv/on_the_air`）列當季動畫，條件可調。
   - 抓 Bangumi 的放送表，當作「當季新番」的對照。
   - 比對兩邊（標題、Bangumi 與 TMDB 的對應），算 TMDB 列得出的比例，並列出漏掉的作品。
2. **判定**：覆蓋率九成以上，09 照 TMDB 為主幹；**低於九成就改以 Bangumi 為主幹**、再對 TMDB，並同輪改 spec〈範圍〉與 09 的「做什麼」。
3. 結論、discover 參數、覆蓋率數字與來源寫回 brief §20.3。

## 驗收

- [x] 實驗腳本在 `scripts/experiments/`，跑得起來，輸出貼在 Comments
- [x] brief §20.3 有覆蓋率、漏掉的作品、discover 參數與主幹的決定（附來源）
- [x] 主幹改成 Bangumi 時，spec 與票 09 已跟著改（不適用：主幹照 TMDB；spec 與 09 仍補上條件）
- [x] 全部檢查綠；progress.md 已更新

## Comments

- 2026-11-04 結論：主幹照 TMDB。分母「只算日本作品、Bangumi 說這週有集」是使用者定的（不分產地是 88.4% / 84.1%，會改成 Bangumi）。條件、數字、漏掉的作品在 brief §20.3 與 `docs/research/schedule-sources-2026-11-04.md`。
- 取捨：每部 Bangumi 作品先找 TMDB id 再比 id，標題只拿來找；第一輪用開頭比對把迷你動畫對到本篇，所以加了衍生作記號那條；114 筆對應都人工看過。`tv/on_the_air` 不分類型（1703 筆），沒有拿來比。
- 腳本只用標準庫、不 import berth；key 讀 `TMDB_API_KEY`，快取鍵不含 key，回應與結果 JSON 在 `.local/experiments/`（gitignore）。量測日之後重跑會重抓清單與放送表（快取鍵帶日期）。
- 輸出摘錄（`uv run --env-file <主目錄>/.env python scripts/experiments/schedule_sources.py`，2026-11-04；完整的含每部的對應，在 `.local/experiments/results/schedule_sources/2026-11-04_week-2026-11-02.json`）。**篩過**：兩個「漏掉」段只留日本且 Bangumi 這週有集的列（腳本原樣不分產地，箭頭那句是加註），上一週只留兩行覆蓋率：

```text
量測日 2026-11-04；Bangumi 放送表 114 部
產地/平台：中国/TV 1、中国/WEB 11、其他/TV 5、其他/WEB 11、日本/TV 77、日本/WEB 9

## 窗口 this：2026-11-02 – 2026-11-08
discover 筆數：animation 193、animation+ja 92、animation+ja|zh 162、animation+JP 93、animation+ja±1 94、animation+ja|zh±1 164
覆蓋率（全部）：animation 79/114 = 69.3%；animation+ja 72/114 = 63.2%；animation+ja|zh 77/114 = 67.5%；animation+JP 72/114 = 63.2%；animation+ja±1 74/114 = 64.9%；animation+ja|zh±1 79/114 = 69.3%
覆蓋率（日本）：animation 72/86 = 83.7%；animation+ja 72/86 = 83.7%；animation+ja|zh 72/86 = 83.7%；animation+JP 72/86 = 83.7%；animation+ja±1 74/86 = 86.0%；animation+ja|zh±1 74/86 = 86.0%
覆蓋率（日本/TV）：animation 70/77 = 90.9%；animation+ja 70/77 = 90.9%；animation+ja|zh 70/77 = 90.9%；animation+JP 70/77 = 90.9%；animation+ja±1 72/77 = 93.5%；animation+ja|zh±1 72/77 = 93.5%
覆蓋率（Bangumi 這週有集）：animation 76/86 = 88.4%；animation+ja 70/86 = 81.4%；animation+ja|zh 75/86 = 87.2%；animation+JP 70/86 = 81.4%；animation+ja±1 71/86 = 82.6%；animation+ja|zh±1 76/86 = 88.4%
覆蓋率（日本且 Bangumi 這週有集）：animation 70/76 = 92.1%；animation+ja 70/76 = 92.1%；animation+ja|zh 70/76 = 92.1%；animation+JP 70/76 = 92.1%；animation+ja±1 71/76 = 93.4%；animation+ja|zh±1 71/76 = 93.4%
漏掉（animation+ja|zh±1）：  ← 只留日本且 Bangumi 這週有集的列
  - [日本/WEB；Bangumi 這週有集] 猫猫のひとりごと 第3期（猫猫的呢喃 第三季，bgm 707667，開播 2026-10-05）→ tmdb —：TMDB 查不到
  - [日本/WEB；Bangumi 這週有集] ミニアニメ「ホタルの嫁入り」ちょいたし（萤火虫的出嫁 迷你动画，bgm 713219，開播 2026-10-12）→ tmdb —：TMDB 查不到這部衍生作（本篇不算同一部）
  - [日本/TV；Bangumi 這週有集] シルバニアファミリー フレアのカラフル・エブリデイ（—，bgm 704737，開播 2026-10-01）→ tmdb —：TMDB 查不到
  - [日本/TV；Bangumi 這週有集] ぷにるんず ぷに４（—，bgm 646586，開播 2026-10-04）→ tmdb 209198：這一週沒有播出日的集（最近一集與下一集：2025-12-27）
  - [日本/WEB；Bangumi 這週有集] ダークサモナーとデキている  ミニアニメ劇場（黑暗召唤师在地下恋爱中 迷你动画剧场，bgm 708612，開播 2026-10-04）→ tmdb —：TMDB 查不到這部衍生作（本篇不算同一部）
## 窗口 last：2026-10-26 – 2026-11-01
覆蓋率（Bangumi 這週有集）：animation 75/88 = 85.2%；animation+ja 68/88 = 77.3%；animation+ja|zh 73/88 = 83.0%；animation+JP 68/88 = 77.3%；animation+ja±1 69/88 = 78.4%；animation+ja|zh±1 74/88 = 84.1%
覆蓋率（日本且 Bangumi 這週有集）：animation 68/76 = 89.5%；animation+ja 68/76 = 89.5%；animation+ja|zh 68/76 = 89.5%；animation+JP 68/76 = 89.5%；animation+ja±1 69/76 = 90.8%；animation+ja|zh±1 69/76 = 90.8%
漏掉（animation+ja|zh±1）：  ← 只留日本且 Bangumi 這週有集的列
  - [日本/WEB；Bangumi 這週有集] 猫猫のひとりごと 第3期（猫猫的呢喃 第三季，bgm 707667，開播 2026-10-05）→ tmdb —：TMDB 查不到
  - [日本/WEB；Bangumi 這週有集] ミニアニメ「ホタルの嫁入り」ちょいたし（萤火虫的出嫁 迷你动画，bgm 713219，開播 2026-10-12）→ tmdb —：TMDB 查不到這部衍生作（本篇不算同一部）
  - [日本/WEB；Bangumi 這週有集] 歯ならび～ズ（—，bgm 716367，開播 2026-10-26）→ tmdb —：TMDB 查不到
  - [日本/TV；Bangumi 這週有集] シルバニアファミリー フレアのカラフル・エブリデイ（—，bgm 704737，開播 2026-10-01）→ tmdb —：TMDB 查不到
  - [日本/WEB；Bangumi 這週有集] 凶乱令嬢 ニア・リストンミニ（乱世千金倪亚‧利斯顿 迷你动画，bgm 716967，開播 2026-10-15）→ tmdb —：TMDB 查不到這部衍生作（本篇不算同一部）
  - [日本/TV；Bangumi 這週有集] ぷにるんず ぷに４（—，bgm 646586，開播 2026-10-04）→ tmdb 209198：這一週沒有播出日的集（最近一集與下一集：2025-12-27）
  - [日本/WEB；Bangumi 這週有集] ダークサモナーとデキている  ミニアニメ劇場（黑暗召唤师在地下恋爱中 迷你动画剧场，bgm 708612，開播 2026-10-04）→ tmdb —：TMDB 查不到這部衍生作（本篇不算同一部）
## animation+ja|zh±1 列了、Bangumi 放送表沒有（this）：85 部，{'ja': 20, 'zh': 65}
## animation+ja|zh±1 列了、Bangumi 放送表沒有（last）：107 部，{'ja': 28, 'zh': 79}
```
- code-review（Standards、Spec 兩軸）已處理：`tv/{id}` 與搜尋的快取改成帶日期（原本換季重跑會讀到舊的集）、`first_air_date` 為空不再炸排序、結果檔名帶週、docstring 與程式對齊、衍生作查不到另寫原因、brief 註明 `zh-CN` 只是實驗用、上一週靠放寬一天才過線。沒改：`PAD` 混在參數 dict 裡（Primitive Obsession，判斷題，實驗腳本不值得多一個型別）；`SCOPES` 鍵與原因字串用中文（實驗輸出，照其他實驗腳本）。
