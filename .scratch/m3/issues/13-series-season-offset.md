# 13 — 季號與 offset：第一批審核、套用到整個 RSS Series、確認後不再 audit

**Status:** done

**Blocked by:** 05（批次確認的分組形狀）、08（RSS Series 與規劃讀季號 offset）

**讀:** plan §2.3（`plans`、`plan_items`）、§3.1（`review` 的核准 / 拒絕）、§4.4、§11.4；brief §6.4、§6.5、§15（「季號與 offset」）、§19（「沒有 AI 時把人工降到最少」）

## 做什麼

brief §15，使用者 2026-09-24 拍板。

- **每份計劃記下它用到的季號與 offset**：RSS Series 的值在規劃時讀，所以同一個 Series 前後兩份計劃可能用了不同的值，要看得出來。
- **新 RSS Series 的第一批進審核**：已經入庫、只是等人看一眼，走 audit 的形狀（`confirmed = false` 期間 high 也標 audit）。審核頁以 RSS Series 分組，一組一顆「全部確認」（沿用票 05 的形狀）；確認之後 `confirmed = true`。
- **改正並套用到這個 RSS Series**：在審核裡改一集的季集時，可以選「套用到這個 RSS Series」。套用後寫回 Series 的季號與 offset，**重算它底下還沒確認的集數**（補舊集一次十幾集，第一集錯就全錯，改一次要全修好）。重算走既有的重新規劃與 rematch 路徑，不另寫一條入庫路。
- **確認過之後，medium 入庫不再進 audit 清單**：之後改由播出日比對（票 14）、片長驗證（票 15）、Jellyfin 回驗（票 17）與 M4 的每日檢查守著。

新命令（套用到 Series、確認 Series）照票 05 標副作用等級與反向命令。

## 驗收

- [x] Plan 上看得到它用的季號與 offset（API 與 `/jobs/:hash`）
- [x] 新 Series 的第一批出現在 `/review`，以 Series 分組；按一次全部確認之後 `confirmed = true`（整合測試）
- [x] split-cour：第二 cour 從 01 重數、TMDB 併成一季，第一批換算錯 → 在審核裡改一集並套用到 Series → 其餘未確認的集數跟著對，已入庫的鏈接搬到正確路徑（整合測試，對應 M3 驗收第五條）
- [x] 已確認的 Series，新進的 medium 集數不出現在 audit 清單；未確認的照舊出現（雙向，對應 M3 驗收最後一條）
- [x] 新命令都有副作用標記
- [x] playwright 對演練情境實跑改正並套用，附結果
- [x] lint、type、test 綠燈

## Comments

2026-09-26 收尾。實作的取捨（progress.md「偏差與決定」同日也記了）：

- 改正走 `POST /files/rematch` 加 `apply_to_series`，不另開端點：改一集本來就是 rematch，套用只是多一個旗標；新命令是 `series_review.correct_series` 與 `confirm_series`，兩支都標 `reversible`、`inverse=None`（理由寫在各自的 docstring）。
- 第一批是 Series `confirmed = false` 期間**所有寫進媒體庫的列**（字幕、特典也掛），與 medium 的 audit 同一個形狀；確認過的 Series 什麼都不掛。
- 跟著重算的集數**仍在第一批裡**（還沒有人看過），人親手改的那一集清掉旗標；已確認的集數、管理員逐列改過的待審核 Plan 都不動。
- 人要的那一格被同一批也要搬的另一集佔著時等它先搬（offset 小於這一批的集數時必然發生，自己複查時抓到、紅燈先行）；被不會搬的檔案佔著時 409 `target_taken`、什麼都不動。
- 既有的 RSS Series migration 成 `confirmed = false`（下一批照第一批問一次）；既有的 Plan 不回填季號與 offset。
- 前端：還沒確認的 Series 只有一列也畫成一組（組的「全部確認」才確認 Series）；**audit 段整段的「全部確認」也把範圍內還沒確認的 Series 一起確認**（前端依 Series 拆請求、件數加總，就地確認時說出幾個 Series）——票面沒寫，不這樣做的話從整段確認之後 Series 永遠停在未確認。

playwright（`--scenario rss-split-cour`，`web/e2e/series-offset.spec.ts`，1280 與 390）：綁定並補舊集 → 12 集以「TMDB 一季」落在 S01E01–E12、在 `/review` 是一組第一批 → 第 1 集改成 S01E13 並套用到 Series → 畫面說「已修正，這個 RSS Series 改成第 1 季、集號偏移 +12。其餘 11 集跟著搬過去了」、其餘 11 集在 S01E14–E24 → 全部確認之後整組消失、重新整理也不回來。截圖 `.local/screens/m3-13/{1280,390}-{1-first-batch,2-correcting,3-corrected,4-confirmed}.png`。

code-review 已處理：Spec 軸的「重新規劃洗掉管理員逐列改過的待審核 Plan」、「送來的列全被跳過時仍把 Series 標成確認」（各一條紅 → 綠）；Standards 軸的 plan.md 四處落差（`RematchRefusal` 種數、`plan_id` 可空、`plan_items.audit` 的定義、§6 命令欄）、`correct_series` 的反向命令指向自己（改成 `None`）、前端第一批判斷的兩個真相來源（改成只讀 `reason.code`）。

未處理的發現：

- **跟著重算的集數由 rematch 另建單列 Plan，那幾份沒有記 `rss_series_id` / `season_hint` / `episode_offset`**；Job 自己那一份仍說它當時用的舊值，列上已經是新集數。新值只在那一列的 `series_corrected` 理由裡。要不要讓 rematch 的單列 Plan 也記，等有人在 `/jobs/:hash` 真的被它搞混再說。
- 逐列按「確認」不會把 Series 標成確認過，只有組與整段的「全部確認」會；第一批確認完之前，同一個 Series 新進的集數仍是第一批。
- `QUEUE_LIMIT`（200 列）截斷時，組上的「全部確認」只確認畫面上那幾列，Series 卻整個標成確認過；沒上畫面的那幾列留在 audit（理由變回 medium）。
- offset 以檔名寫的集號算（`parser.written_episode`），而規劃器帶季號提示時仍會對 `Part N` 標記套 cour 換算；三 cour 以上、或檔名帶 `Part N` 的 Series 可能多算一截。沒有語料，沒寫測試。
- Standards 的判斷題、沒改：「`trigger_ref` 就是 Series id」有三份寫法（`plan.series_of`、`review._fetch_audits` 的 `cast`、`series_review._hashes_of`）；`Landing.because/audit` 是 `Assignment` 的複本；`Plan.season_hint` 對上 `RssSeries.season` 兩個名字（沿用 `ParseContext` 的詞）；`AuditSeries.name` 裝的是 `title_raw`；整段確認「Series 的列打哪一支」由前端拆（可以改成 `/audit/confirm` 自己標 Series，但那會改掉票 05「逐列按確認」的語意）；`web/src/rss/seriesValues.ts` 的消費者都不在 rss 頁。
