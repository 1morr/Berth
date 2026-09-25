# 09 — RSS Series 自動綁定

**Status:** done

**Blocked by:** 08

**讀:** plan §4.3（`candidates`）、§8.3、§11.4；brief §6.4 第 2 點（標題比對）、§6.5、§15（「綁定」）；`docs/research/rss-sources.md`（Mikan 番組頁的欄位）

## 做什麼

使用者 2026-09-24 拍板：有把握就自動綁定，沒把握的進待綁定清單。

**候選從哪來**：第一次見到的 RSS Series，用 Mikan 番組頁的中文標題、開播日期、bgm.tv 連結，加上 Feed Item 標題解析出的標題骨幹，去 TMDB 搜。這正是 plan §4.3 說的 `candidates`，目前一直沒有呼叫端去搜（2026-09-24 審查點出的落差）。

**什麼叫有把握**：規則要寫成封閉集合的理由碼，形狀照解析器的 `reasons`。起點是 brief §6.5「標題 + 年份精確命中」：中文或原文標題正規化後相等，**而且**開播日期落在 TMDB 那一季的首播附近。只命中一個候選才算；兩個以上或沒有就留在待綁定，畫面列出候選讓人一鍵選。規則門檻先寫、再用票 07 的 fixture 與 `MyBangumi` 裡的真實作品量一次。

**自動綁定走票 08 的同一個綁定命令**，actor 是 `system`（`bound_by = system`），所以之後改綁、解除綁定都是同一條路。

Route 怎麼選：TMDB 類型推得出電影或劇集，同類型只有一條啟用的 Route 時才自動選；否則留在待綁定並預填作品。

## 驗收

- [x] 用 fixture 裡的作品：命中唯一候選的自動綁定並送單，`bound_by = system`，時間線說得出依據（整合測試）
- [x] 同名不同年、兩個候選、沒有候選，三種情況都留在待綁定，理由碼不同（單元測試）
- [x] 待綁定清單列出候選，一鍵選定就走綁定命令（前端測試 + playwright 實跑）
- [x] 同類型有兩條 Route 時不自動綁定
- [x] 規則門檻的量測結果記在 `docs/research/rss-sources.md` 或本票 Comments（自動綁了幾部、錯了幾部）
- [x] lint、type、test 綠燈

## Comments

**2026-09-25 實作**（`/implement`）。

- 驗收對照：
  - 第 1 條：`tests/integration/test_rss_auto_bind.py::TestConfident`。Mikan 聚合 feed → 番組頁 4009 → 替身 TMDB → `bound_by = system` → 兩集送單 → 入庫；`created` 事件的 `grounds` 是 `title_equal`、`premiere_near`、`only_route`，而且帶參數。
  - 第 2 條：`tests/unit/test_rss_binding.py`。三種情況的理由碼是 `premiere_far`、`several_candidates`、`no_candidate`，另有一條斷言三者互不相同。
  - 第 3 條：前端 `RssPage.test.tsx`（候選一鍵選定 → Route → 確認 → `PUT binding`）；playwright `web/e2e/rss.spec.ts` 1280 / 390 兩條都綠，390 寬沒有橫向捲動。
  - 第 4 條：`TestPending::test_two_routes_of_that_kind_keep_it_pending_with_the_work_prefilled`，停用的 Route 不算。
  - 第 5 條：`docs/research/rss-sources.md` §2.8。
- **量測**（`scripts/experiments/rss_auto_bind.py`，真的 Mikan 與 TMDB）：`MyBangumi` 的 11 個 RSS Series 裡，**規則有把握的 10 部，錯 0 部**。開播日期差 0–1 天。留在待綁定的 1 部是 Re:Zero 第四季（番組名帶季數，`no_candidate`），應該留。
- **Route 那一步在真實環境一部都綁不上**：試跑環境是 Anime、Movies、TV 三條，Anime 與 TV 都收劇集。照這張票的規則，上面 10 部全部會留在待綁定（`route_ambiguous`），作品已經預填、一鍵選定。這是照票面做的，要不要改規則（例如「作品上次送單用的 Route」或「同一個 Mikan 番組已綁的 Route」）**等使用者拍板**。
- **「一鍵選定」之後仍要按一次確認**：資料夾名在綁定那一刻定死（brief §4.5、shape §3），確認區塊要重述它。
- 規則門檻 14 天是起點，實測差 0–1 天。留寬是為了對岸平台晚開播、Mikan 寫它的日期的那種情況；同名重拍差的是年。

**code-review（Standards / Spec 兩軸）**，已處理：
- 實驗腳本的環境變數改用 `.env.example` 的 `TMDB_API_KEY`（原本多了一個 `BERTH_TMDB_KEY`，09-09 已經合併過一次）。
- 測試裡沒有寫原因的 `# type: ignore` 拿掉。
- 年份預篩搬進 `parser.binding.could_be`，補了電影與跨年的單元測試（先紅再綠）。
- `bind_series` 被拒時收回 `only_route` 那一句，不再把綁上用的依據當成沒綁的理由。
- `PREMIERE_WINDOW` 的註解改指研究檔。
- plan §4.3 寫明 RSS 沒走 `ParseContext.candidates`；brief §15 補上「只在長出來的那一輪認」與「選定後仍要確認」。

未處理（刻意不做或留給後面的票）：
- 名字：後端叫 reasons（`BindReason`、`reasons_json`），時間線與 i18n 叫 grounds（`rss.grounds.*`、`created.grounds`）。兩者不全等：時間線只帶綁上時的依據，所以沒統一。元件檔 `GroundsList.tsx` 匯出 `Grounds`：Windows 上 `grounds.ts` 與 `Grounds.tsx` 會被當成同一個檔。
- 實驗腳本 import `services.rss` 的私有 `_clues`、`_candidates`：量的就是那一條路。公開它們就要在 service 模組加 `@command` 標記，而它們不是命令。
- `SYSTEM = actor_of(None)` 是 services 裡第四份 `system`，既有慣例。
- `_auto_bind` 回 `int | None`（送出幾筆 / 沒綁）。
- 對到第 2 季以後時沒有把季號寫回 `RssSeries.season`：票 13 的範圍（季號與 offset 的改正）。解析器照樣看發佈名。
- 查不到（`lookup_failed`）不重試：理由寫在 brief §15。一個壞掉的番組頁不該每 15 分鐘打一次。
- bgm.tv 連結沒用上：TMDB 不收 bgm 的 id。
