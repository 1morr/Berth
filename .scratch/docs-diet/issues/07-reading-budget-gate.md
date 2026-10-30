# 07 — 閱讀預算閘門：CLAUDE.md 與 progress.md 的大小上限

**Status:** done

**Blocked by:** 01

**讀:** `.scratch/docs-diet/spec.md`；`docs/progress.md`〈寫法與封存〉（票 01 寫的）；`tests/unit/test_progress_merge.py`；`CLAUDE.md`

## 為什麼

票 01 把 progress.md 縮回讀得完的大小，但沒有東西擋它再長回去：上一次從幾 KB 長到 893 KB 沒人發現。CLAUDE.md 是每個 session 第一份讀的，也要有上限。

排在 01 之後馬上做：02–06 的 session 都會往 progress.md 寫，越早有閘門越好。

## 做什麼

1. **定上限**（單位：字元，Python `len`；中文與英文混排時比 bytes 準）。建議值，開工時重量再定，理由寫進 Comments：
   - `CLAUDE.md` ≤ 6,000 字（現在 3,596；票 01 改完再量）。
   - `docs/progress.md` ≤ 20,000 字：一次 Read、不帶 offset 就讀得完。一個里程碑 100 張票、每列 200 字已經到這個量，所以超過時的做法是把進行中里程碑的舊列也先封存。
2. **測試** `tests/unit/test_reading_budget.py`：兩個檔各一條，訊息寫超過多少、超過時怎麼做（progress → 封存舊列；CLAUDE.md → 先刪打開程式碼就查得到的段落）。
   - 雙向變異：在檔尾補到上限 + 1 → 紅；同樣內容換行與空行重排、總字數不變 → 不紅。記在 Comments。
3. progress.md〈寫法與封存〉寫上限與超過時的做法；CLAUDE.md 若提到「由測試強制」，逐條對得上這支測試。

## 不做

plan / brief 的章節大小不設閘門：要等 04、05 改寫完才有基線，08 收尾時再評估要不要加。

## 驗收

- [x] 上限值與理由在 Comments
- [x] 測試兩條綠；雙向變異紅 / 不紅都跑過，記在 Comments
- [x] 〈寫法與封存〉與 CLAUDE.md 的宣稱對得上測試
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

- 上限：`CLAUDE.md` ≤ 6,000 字（量到 3,875，留約 55% 餘裕給後續票）；`docs/progress.md` ≤ 20,000 字（量到 2,965；一次 Read 不帶 offset 讀得完）。採用建議值，沒有調整。
- 雙向變異（手動，各檔各一次，跑完還原）：補 `x` 到上限 + 1 → 該檔那條紅、另一條綠；換行與空行重排、總字數不變 → 兩條綠。
- CLAUDE.md 沒有「由測試強制」的宣稱涉及此上限，不改；上限與超過時的做法寫在 progress.md〈寫法與封存〉，測試失敗訊息同一說法。
- code-review（`/code-review medium d515c733`）：本票只改 3 檔（`test_reading_budget.py`、`progress.md`、本票），8 條發現沒有一條落在這些檔上，也沒有碰到本票的 Spec。它們講的是票 06 的 development.md 拆分，審查範圍似乎被帶到票 06 的內容。全部未處理，原樣留給票 06 的後續或 08 收尾判斷：
  1. `scripts/docs_moved_lines.py:21` 連結正規化忽略 `./`、`../` 深度，「遺失 0」可能掩蓋指向不同檔的連結。
  2. `docs/development/commands.md:24,99`、`e2e.md:79`：〈UI 的 Fake 後端〉、〈前端 e2e〉跨檔引用沒有連結。
  3. `docs/research/m5-ai-direction-2026-10-27.md:155`、`04-health.md:98`、`.scratch/m5` 票：仍指 `docs/development.md` 已不存在的章節。
  4. `docs/development.md:82`：「證明沒丟」那條沒寫連結深度正規化。
  5. 五個子檔 `# 標題` 後直接 `###`，跳過 `##`。
  6. `docs/development.md:3`：CLAUDE.md 流程沒指到 `commands.md`。
  7. `tests/unit/test_readme_docs.py:130`：連結檢查只 glob `docs/development/*.md`，不含更深的子目錄。
  8. `scripts/experiments/README.md:3`：「單一來源之一」與 CLAUDE.md 的「單一來源」措辭不一致，連結失去錨點。
- 驗證（commit `866f1ed7`，審查後無程式碼改動）：`uv run pytest tests` 5280 passed, 1 skipped, 28 deselected（347.79s，含 integration）；`pre-commit run --all-files` 13 項全 Passed。
