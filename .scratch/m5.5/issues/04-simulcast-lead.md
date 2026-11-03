# 04 — 播出日比對認得地上波先行

**Status:** done

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

- [x] 照字面早 8 天放行並記 `released_ahead_of_airing`，早 10 天仍擋；有換算的早 7 天仍擋（測試）
- [x] 正式環境那 16 列做成 fixture，全部放行
- [x] 哥布林、裝備仔、野生的大魔王那種照字面先行的 Series 由第一批的系統確認（測試）
- [x] `berth bench` 的 `auto_wrong` 不升（貼前後數字）
- [x] 全部檢查、pytest 綠；progress.md「偏差與決定」記規則一的改法；progress.md 已更新

## Comments

- **fixture 的來歷**：研究檔只記了日期，發佈名是 2026-11-04 從 ACG.RIP（裝備仔從 Mikan）查回的同一筆發佈，發佈日（UTC）16 列都與正式環境相同；檔名取自 `.torrent`。轉生就是劍同一天還有黒ネズミたち、ToonsHub 兩組，選了標題寫 `S02` 的 ANi（正式環境那 4 列的理由是 `season_from_release`，對得上）。大聖女選 LoliHouse：ANi 的 06 發佈日差一天。
- **TMDB 的播出日會移動**：快照用 `scripts/record_tmdb_snapshots.py`（多讀 `tests/fixtures/airing/`）錄真的 API。野生的大魔王（tv-280042）的日期已被 TMDB 改成 ABEMA 的日期、早一週，所以 fixture 帶 `tmdb_aired`（正式環境當時的日期），測試以它為準；其餘 14 列兩者相同。這也可能是研究檔查不出 E17 當時為什麼沒被擋的原因。
- **「照字面」的定義**放在新的 `parser/literal.py`（`is_literal` 與白名單 `VOUCHED`），播出日比對與第一批都 import 它。Series 的季號由白名單擋（`season_from_job`），offset 由「對到的集號是檔名寫的」擋；offset 設成 0 時算照字面，那等於人說了檔名就是 TMDB 的集號。所以 `check_airing` 只多收發佈名、不收 Series。第一批另外要求 Series 兩個值都沒設，沒動。
- **放行的列不再看規則二**：播出日在發佈之後，發佈當時「最近播出的一集」不會比它晚。
- **前後數字**：`berth bench` 前後完全相同（40 份、904 檔、`auto_wrong` 0 → 0；bench 只跑解析器、不跑播出日比對）。`scripts/experiments/first_batch_rule.py` 前後輸出逐字相同（擔保錯 0）。前一版是把 HEAD 抽到暫存目錄、用 `PYTHONPATH` 跑的。
- **變異驗證**：`SIMULCAST_LEAD` 改成 0 時三個測試檔 36 個測試紅。
- **code-review 未處理的發現**：`released_before_airing` 與 `air_date_conflict` 的「平台先行的核准就好」也會出現在有換算的列上，而換算差一集同樣早一週，那一句可能把算錯的列引去核准；這是票面要求的文案，照做、留給使用者決定。（票 04b 處理：只對照字面的列說。）`VOUCHED` 留著原名（票面用這個名字），沒改成 `LITERAL_REASONS`；`publishing.tolerance(literal=...)` 的布林參數沒改成兩個常數。
