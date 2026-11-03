# 04 — 播出日比對認得地上波先行

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「播出日比對認得地上波先行」；brief §20.27、§20.11（規則一）、§15；plan §4.4；`docs/research/review-queue-2026-11-01.md`

## 為什麼

正式環境審核佇列 33 件裡有 16 件是地上波先行：字幕組從 ABEMA 這類平台先拿到片，發佈比 TMDB 的電視台日期早 4–8 天，被規則一「早於播出日超過兩天一定算錯」擋下。這條規則不成立（brief §20.27），被誤擋的集數進不了 Jellyfin。

## 做什麼

1. **「照字面」抽成一支共用的定義**，04 的播出日比對與第一批（`first_batch`）都用它：`written_episode` 等於對到的集號、沒有換算類的理由、季號寫明或對到第一季。人在 Series 上設了季號或 offset 就不算照字面。`check_airing` 因此要多收發佈名。
2. **照字面的列**容忍 `RELEASE_TOLERANCE` 加 `SIMULCAST_LEAD`（7 天，共 9 天），放行時記一條新理由 `released_ahead_of_airing`（帶兩個日期，zh-Hant、en）。超過 9 天照舊擋。
3. **有換算的列維持兩天**：換算差一集也剛好早一週，只看日期分不開。
4. **第一批認這個窗口**：`released_ahead_of_airing` 進 `VOUCHED`，照字面的「剛播」上緣跟著放寬。`mapping._just_aired`（推測虛擬季）不動，所以 `publishing.just_aired` 要拆成兩個窗口。
5. `released_before_airing` 與 `air_date_conflict` 的文案補一句「平台先行的核准就好」（zh-Hant、en）。
6. 文件：plan §4.4 的規則一、brief §15、`parser/airing.py` 與 `parser/first_batch.py` 開頭的條件說明。

## 驗收

- [ ] 照字面早 8 天放行並記 `released_ahead_of_airing`，早 10 天仍擋；有換算的早 7 天仍擋（測試）
- [ ] 正式環境那 16 列做成 fixture，全部放行
- [ ] 哥布林、裝備仔、野生的大魔王那種照字面先行的 Series 由第一批的系統確認（測試）
- [ ] `berth bench` 的 `auto_wrong` 不升（貼前後數字）
- [ ] 全部檢查、pytest 綠；progress.md「偏差與決定」記規則一的改法；progress.md 已更新
