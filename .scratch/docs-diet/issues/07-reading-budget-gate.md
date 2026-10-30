# 07 — 閱讀預算閘門：CLAUDE.md 與 progress.md 的大小上限

**Status:** ready-for-agent

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

- [ ] 上限值與理由在 Comments
- [ ] 測試兩條綠；雙向變異紅 / 不紅都跑過，記在 Comments
- [ ] 〈寫法與封存〉與 CLAUDE.md 的宣稱對得上測試
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
