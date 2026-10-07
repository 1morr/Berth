# 49 — 作品頁搜尋結果用年份與類型篩

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S6 作品頁搜尋那列、§3.2 搜尋那列、改進清單 P2-7）；brief §6.3、§6.4、§20.10；plan §8.4

## 為什麼（2026-10-06 審計，實測）

- 搜《活死人之夜》（1968，電影）時，結果混進 1990、2006 的重拍版，以及《Below Deck Down Under S04E02 Night of the Living Dead》。年份與「這是電影」都沒用來篩。截圖 s6-02。

## 做什麼

1. 作品是電影時，發佈名讀得出季集的結果篩掉或排到最後；作品是劇集時同理反過來。
2. 發佈名讀得出年份、而且與作品年份差超過容許範圍的，篩掉或排後。容許範圍參考 Radarr 的做法，查證後寫進 brief §20（附來源）。
3. 被篩掉的數量照現在「名字對不上已略過」的方式說出來，使用者可以展開。

## 驗收

- [x] 整合測試（雙向）：電影搜尋不列出讀得出季集的結果、劇集搜尋照常；年份差太多的被篩，同年與沒寫年份的保留
- [x] 用《活死人之夜》1968 的 fixture：1990 版與劇集不在主清單
- [x] vitest：略過數量與展開
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

- 2026-10-07 code-review（兩軸 opus）處理掉的：篩選推導式重複、季集記號改用 `seasons` 的寫法（補 `2nd Season`、`S01E01E02`、`S01E05v2`、`1x05`、`EP05`）、主清單為 0 時略過筆數被吞、「差一年以上」措辭、`_aired` / `named` 改名、CONTEXT.md 補 **Set Aside**。
- 未處理（判斷題，留著）：
  - `[S1] Movie 2019`、`Movie 2019 S1 Remux` 這種把 `S1` 當片源記號的會被收起來；沒有實例，展開救得回來。
  - 只寫修復年份、不寫原始年份的發佈（`Movie.2018.4K.Restoration`）會被收起來；同上。
  - 收起來的那一份也跑 `parse_release`（至多再一百筆，約 1.4 秒）；實測的審計那一次只有十幾筆，plan §8.4 已寫明。
  - `set_aside` / `set_aside_total` 與 `rows` / `total` 是同一種「前 N 筆加總數」；只有兩組，不收成型別。
  - 展開後照樣能送單（票面只說可展開）：判斷只看發佈名，可能看錯，展開了卻送不出等於還是丟了。
  - `schema.d.ts` 重新產生時帶進票 47 的端點說明漂移，拆成前一個 commit。
- 全套 pytest 時 `test_rss.py::TestTwoRoundsAtOnce::test_only_one_round_runs_and_neither_fails` 失敗一次（`(12, 0) != (12, 1)`：背景那一輪晚到，Feed 已輪過），單獨跑 3/3 綠。與本票無關，沒有 repro 不修。
