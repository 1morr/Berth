# 98 — 解析器讀標題遇到括號就停：「尼古喵喵 (邪竜解放版) / … / Chainsmoker Cat」只讀到前半

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 88 的 Comments（「退步一例」「千夏那一例」）；`berth/parser/binding.py`（`skeleton`、`_TITLE_END`、`search_terms`）；`title_key` 的持久化用法（非 Mikan 的 RSS Series）；`CLAUDE.md`（解析器改動必跑 `berth bench`）

## 為什麼

`[LoliHouse] 尼古喵喵 (邪竜解放版) / ヤニねこ / Yani Neko / Chainsmoker Cat - 11` 這種發佈名，`_TITLE_END` 把 `(` 當成標題結尾，只讀出 `尼古喵喵`。後面以 ` / ` 隔開的別名（包括最好搜的英文名 `Chainsmoker Cat`）全丟了。

影響兩處：
- 綁定框的預填（票 88 之後由後端給）。
- 自動綁定拿去搜 TMDB 的字。

舊前端讀得到 `Chainsmoker Cat`，所以票 88 之後這一例是退步。使用者（2026-10-13）同意開票修。

## 做什麼

- 讓標題中間的括號註記（版本、特別篇之類）不再截斷整個標題：括號那一段當註記丟掉，後面的 ` / ` 別名照讀。實際規則開工時用 bench 的 fixture 與真實發佈名決定，寫進票的 Comments。
- **`skeleton` 也是非 Mikan RSS Series 的持久化鍵 `title_key`**：改了它，既有的 Series 可能分裂成兩個。開工時先查清影響範圍，再選一種做法：
  - 寫 migration 重算既有的 `title_key`；或
  - 讓 `title_key` 不受這次改動影響。

  選了哪一種、為什麼，寫進 progress.md「偏差與決定」。沒查清楚之前不要改 `skeleton`。
- 千夏那一例（中文名與 Romaji 用底線連在一起）**不在這張票**：要不要切底線是另一條新規則。

## 驗收

- [ ] 上面那個發佈名讀得出 `Chainsmoker Cat`（也就是 `search_terms` 裡有它）；pytest 守，做變異驗證
- [ ] `berth bench` 前後對照貼輸出，`auto_wrong` 不得上升
- [ ] 既有 Series 不會因為這次改動分裂：有測試守，或有 migration 並以帶資料的舊庫實跑升級（隔離環境，**不准碰使用者的 `berth-local`**）
- [ ] brief / plan 的解析規則同步；全部檢查、pytest 綠；progress.md 已更新
