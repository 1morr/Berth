# 04b — 「平台先行的核准就好」只給照字面的列

**Status:** done

**Blocked by:** 05（同一塊：`parser/airing.py`、`parser/first_batch.py`、審核理由的文案）

**讀:** 票 04 的 Comments（code-review 未處理的發現）；spec〈範圍〉「播出日比對認得地上波先行」；plan §4.4；brief §15、§20.27；`berth/parser/literal.py`；`web/src/i18n/resources.ts` 裡 `released_before_airing` 與 `air_date_conflict` 的文案

## 為什麼

協調者插的追加票（使用者 2026-11-04 定）。票 04 照票面在 `released_before_airing` 與 `air_date_conflict` 的文案補了「平台先行的核准就好」，但這兩個理由也會出現在**有換算**的列上。換算差一集剛好也早一週，那一句會把算錯的列引去核准。使用者定：這句只在**照字面**的列上顯示。

照字面的列早 2–9 天已經被放行（`released_ahead_of_airing`），所以還會帶這兩個理由的照字面列，是早超過 9 天的那種；它們仍可能是平台先行（spec：「還被擋的列可能仍是對的」），那句提示對它們有用。

## 做什麼

1. 審核理由要分得出這一列是不是照字面（用 `parser/literal.py` 那一份定義，不另寫一套），讓文案能選：
   - 照字面：保留「平台先行的核准就好」那一句。
   - 有換算：拿掉那一句，改成提醒先查季號、offset 或絕對編號（說法照現有的 `air_date_conflict` 長說明）。
   - 怎麼帶這個區分（理由的參數、分成兩個理由、或其他）照 `codebase-design` 判斷，記在 Comments；改了理由的形狀就同輪改 plan §4.4、brief §15 的說明與 `gen:api`。
2. 長說明（`air_date_conflict` 那段 explanation 類的文案）也照同一規則分開，或改寫成只對照字面的情況說「平台先行」。
3. zh-Hant 與 en 並列。

## 驗收

- [x] 照字面而早超過 9 天被擋的列，文案有「平台先行的核准就好」；有換算的列沒有，改提醒查季號／offset（測試）
- [x] 照字面早 10 天有提示、早兩個月沒有，改提醒查作品與 TMDB 的日期（協調者 2026-11-04 追加，上限 14 天；測試）
- [x] 審核頁實跑看得到兩種文案（playwright，桌機與 390px）
- [x] `berth bench` 的 `auto_wrong` 不升（貼數字）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- **分成兩個理由，不加參數**：照字面而早超過九天被擋的列記新的 `released_far_ahead_of_airing`（同樣三個日期參數），有換算的留在 `released_before_airing`。理由的句子由前端照 code 挑，參數是不翻譯的事實（`domain/parser.py` 的 `REASON_PARAMS` 說明）；拿一個布林參數切句子會違反這條，`reasonText` 也得多一層分支。兩個 code 都在 `HELD_BY_AIRING`，所以整份計劃仍是 `air_date_conflict`。`check_airing` 改成先問 `is_literal`（同一份定義），再看有沒有超過九天。
- **舊名沒改**：審查提到三個名字靠天數區分、真正的分界是照字面與否。`released_before_airing` 已存在資料庫的 `reasons_json` 裡，改名要 migration，不值得；語意寫在 `domain/parser.py` 的註解與 plan §4.4。已存的舊列（04b 前算的照字面列）仍是舊碼、顯示查季號的句子，06 升級後自動重算會把它們換成新碼。
- **平台先行的上限 14 天**（協調者 2026-11-04 追加：沒有上限時早兩個月的照字面列也會被叫去核准）：照字面早 10–14 天記 `released_far_ahead_of_airing`、說平台先行；更早的記 `released_too_early_for_simulcast`，叫人先查作品認對沒、TMDB 的日期。常數 `publishing.PLAUSIBLE_SIMULCAST_LEAD`。依據：正式環境量到的先行 4–8 天（brief §20.27）；`air_date_lag.py` 的 198 筆最早只比播出早 1 天（M3 票 14），沒有更長的先行樣本，所以取 8 天加約一週餘裕的 14 天。上限只決定文案，兩種都照擋。
- **整份計劃的兩句**（審核頁短句 `review.plan.reason`、下載頁長說明 `jobs.plan.reason`）不知道是哪一種列，改寫成「有換算的先查季號與 offset；照字面讀而早得像平台先行的才核准」；長說明另說照字面卻早太多的先查作品與 TMDB 的日期。
- **手動送單的整合測試**（`TestManual`）那一筆只寫集號、單季，是照字面列，早兩個月，斷言改成 `released_too_early_for_simulcast`。RSS 那一筆帶 Series 的季號，不算照字面，仍是舊碼。
- **實跑**：新演練情境 `rss-simulcast`（`docs/development/fake-backend.md`，TMDB 晚三週，發佈早 7–15 天）。綁定後早 7–9 天的三集照先行放行；早 13–14 天的七份說「平台先行的核准就好」；早 15 天的 E01、E05 說「不像平台先行：先查作品有沒有認錯、TMDB 的日期對不對」（zh-Hant、en，桌機與 390px，無水平捲動）。把 E02 改成第 3 集並套用到 RSS Series（offset +1）後，其餘 8 份停著的都換成「先查季號、offset 或絕對編號」，兩種照字面的句子都沒了。截圖在 `.playwright-mcp/04b-r2-*.png`（gitignore）。
- **前後數字**：`berth bench` 前後相同（40 份、904 檔、`auto_wrong` 0 → 0；前一版是把 HEAD 抽到暫存目錄跑的。bench 不跑播出日比對）。
- **變異驗證**：`simulcastCopy.test.ts` 兩輪改文案前各 8 個紅，parser 的上限測試改碼前 2 個紅；樣式本身另有雙向檢查。
- **`released_far_ahead_of_airing` 沒改名**：第二輪審查說它只管 10–14 天、更早的反而叫 `too_early`。這兩個名字照它們的句子讀：far ahead＝早得多但仍是先行，too early for simulcast＝早到不像先行，留著。
- **code-review 未處理的發現**：CHANGELOG `[Unreleased]` 沒加條目（M5.5 的票都沒寫，發版時一起寫）；`airing.py` 開頭也講了一次兩種理由的文案方向，與 plan §4.4 重複，留著方便讀程式的人。第二輪：14 天散在常數之外的文案（「兩週」）沒有測試綁住，常數註解寫明要一起改；`REASON_PARAMS` 裡三個日期參數那一組重複了五次，延續既有寫法沒抽。
