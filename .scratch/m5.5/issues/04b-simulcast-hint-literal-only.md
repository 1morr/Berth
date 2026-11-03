# 04b — 「平台先行的核准就好」只給照字面的列

**Status:** ready-for-agent

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

- [ ] 照字面而早超過 9 天被擋的列，文案有「平台先行的核准就好」；有換算的列沒有，改提醒查季號／offset（測試）
- [ ] 審核頁實跑看得到兩種文案（playwright，桌機與 390px）
- [ ] `berth bench` 的 `auto_wrong` 不升（貼數字）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
