# 98 — 解析器讀標題遇到括號就停：「尼古喵喵 (邪竜解放版) / … / Chainsmoker Cat」只讀到前半

**Status:** done

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

- [x] 上面那個發佈名讀得出 `Chainsmoker Cat`（也就是 `search_terms` 裡有它）；pytest 守，做變異驗證
- [x] `berth bench` 前後對照貼輸出，`auto_wrong` 不得上升
- [x] 既有 Series 不會因為這次改動分裂：有測試守，或有 migration 並以帶資料的舊庫實跑升級（隔離環境，**不准碰使用者的 `berth-local`**）
- [x] brief / plan 的解析規則同步；全部檢查、pytest 綠；progress.md 已更新

## Comments

- **規則**：括號註記（`(…)`，全形經 `undecorate` 轉半形）後面緊接 ` / ` 時整格丟掉，後面的名字照讀
  （`binding._NOTE`）；後面沒有 ` / ` 的括號照舊是標題結尾。依據是 `tests/fixtures/http/**/*.xml` 約 256 筆真實
  發佈名：改動前後只有兩筆讀法變了——尼古喵喵（讀出 `ヤニねこ`、`Yani Neko`、`Chainsmoker Cat`）與
  `令和妖神斑小姐（放送版） / Reiwa no Dara-san (On-air version) - 13`（讀出 `Reiwa no Dara-san`，最後那格註記照舊截斷）。
  兩筆都進 `TestTheSkeleton`。`search_terms` 與 `_equal_title` 都讀 `skeleton`，所以搜尋詞與自動綁定的相等比對一起受益。
- **`title_key` 不受影響，沒有 migration**：它改呼叫 `_skeleton(drop_notes=False)`，骨幹讀到第一個括號為止。
  `title_key` 只在 `services/rss._series_key` 一處用；fixture 裡受影響的兩筆鍵都與改動前相同。
  `TestTheTitleKey::test_a_note_in_the_middle_of_the_title_leaves_the_key_as_it_was` 釘住 `title:尼古喵喵:lolihouse`。
  選這條而不是 migration：鍵只有 `title_raw`（第一筆）可重算；同組简繁兩種中文名在新讀法下會併成同一個羅馬字鍵，
  migration 要合併 Series（連帶 Feed Item、Job），代價遠大於「鍵少讀幾個名字」——舊讀法下它們本來就是兩個 Series。
- **`berth bench` 前後相同**（`parser.binding` 不在 bench 的路徑上）：
  `overall 904 904/904 270/270 247/247 253 0 86 0 42 123 37 363`，`high: 0/112 wrong  medium: 0/141 wrong`，`auto_wrong` 0 → 0。
- **變異驗證**（`tests/unit/test_rss_binding.py`）：拿掉 `_NOTE.sub` → 尼古喵喵、令和兩個 skeleton 例子與 search_term
  例子紅；`_NOTE` 拿掉 `(?=\s+/\s)` → `Some Movie (2019) BDRip 1080p` 紅；`title_key` 改 `drop_notes=True` → 鍵的 pin 測試紅；
  一致改名（`drop_notes`、`_NOTE`）→ 綠；改回 → 綠。
- **不處理**：組名之後以方括號開頭的寫法（`★07月新番★[名 (註) / 名][12]`），括號留在名字裡——舊有行為，fixture 沒有這種例子。
  千夏那一例（底線）照票面不在這張票。
- **code-review**：Standards 指出 `_skeleton` 的 docstring 寫成「票 98 之前的讀法」像相容層、`past_notes` 易誤讀，
  改成正面定義與 `drop_notes`；「別名」在 `CONTEXT.md` 是 Search Name 的一種，改回「名字」。Spec 指出 plan §4（非 Mikan 鍵那段）
  沒同步、令和那筆真實標題該進測試，都已改。未處理：無。
