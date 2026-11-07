---
target: web/src/agent/ConfirmCard.tsx
total_score: 25
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
target_identity: "file:/Users/roxy/orca/workspaces/Berth/t10/web/src/agent/ConfirmCard.tsx"
target_fingerprint: "sha256:c8608a21927ba8f86b82e373f6ecacd4733850b39d68ec51788e25e6ef6bc889"
target_path: /Users/roxy/orca/workspaces/Berth/t10/web/src/agent/ConfirmCard.tsx
timestamp: 2026-11-07T09-15-44Z
slug: web-src-agent-confirmcard-tsx
---
Method: dual-agent (A: design review, opus · B: detector + overlay, sonnet)

# 確認卡 critique（M5.6 票 10）

目標：`web/src/agent/ConfirmCard.tsx`（送單卡與訂閱卡）。證據：替身伺服器實跑 1280×900 與 390×844，三種卡（13 列同一部作品、兩部作品可全部套用、以作品訂閱）。

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 效果、期限、逐列結果都有；缺勾選數與「會送幾個」的即時摘要 |
| 2 | Match System / Real World | 3 | `routeLead` 在訂閱卡說「送單」、單一作品卡說「兩部以上作品」 |
| 3 | User Control and Freedom | 3 | 可逐列取消、可拒絕；無全選／全不選，送出後沒有撤銷入口 |
| 4 | Consistency and Standards | 3 | 選中語彙有兩種（勾選框 vs 邊框變重的選項鍵）；「第一批」標籤出現兩次 |
| 5 | Error Prevention | 2 | 擋住未選齊、標了已有的集；同集的重複列沒有標 |
| 6 | Recognition Rather Than Recall | 2 | 件數在隱藏按鈕、字幕組後果在上方、第一輪後果在中間 |
| 7 | Flexibility and Efficiency | 2 | 13 列要一列一列點；沒有全選、沒有按作品收合 |
| 8 | Aesthetic and Minimalist Design | 2 | 作品與「Route —」重印 13 次；資料夾說明重複 2 次 |
| 9 | Error Recovery | 3 | 逐列結果、拒絕句、過期與被別人按走都說得清楚 |
| 10 | Help and Documentation | 2 | 卡上常駐長篇說明，需要時反而沒有入口 |
| **Total** | | **25/40** | **Acceptable（需要明顯改善）** |

十項都適用，沒有 n/a。

## Design Specificity Verdict

**LLM**：為 Berth 長的卡，換一個產品就活不了。Route 由伺服器挑、模型不給；字幕組的來源、筆數、最近更新是提出那一刻讀的；「含已有的第 1 季第 4 集」是照帳本／Jellyfin 算的；資料夾凍結與「出自外部來源」都是 Berth 的入庫承諾與 AI 防線。骨幹（標題、效果、列、確認／拒絕）通用，血肉完全屬於這個產品。
**Deterministic scan**：`impeccable detect --json web/src/agent/ConfirmCard.tsx` → 0 條（加 `--no-config` 仍 0；入口用故意違規的替身檔驗過會回 8 條）。
**Overlay**：三張卡 × 兩個寬度都注入成功。只有訂閱卡一條 `repeated-container-text`（「ACG.RIP」出現在 4 個位置）——**誤報**：一個是「來源」欄位的值，三個是選項上的來源標記，是刻意的設計。

## Overall Impression

可信、誠實、先選再確認做得徹底；但把「規模」與「主要動作」藏起來了。在被 Route 擋住的狀態（證據拍到的狀態），整張 13 列的卡沒有一處說得出「這次會送 13 個、共多少」，唯一的數字在還不存在的確認鍵上。最大的機會是把摘要與動作固定在卡頭與卡尾，讓 13 列只是細節。

## What's Working

1. 長相由伺服器決定、證據先於模型：效果、期限、已有的集、資料夾、來源出處都是提出那一刻算的。
2. 「先選再確認」是認真的：按下去必被拒的鍵不畫，按過之後整排鍵收掉、焦點交給標題。
3. 訂閱卡對後果誠實：字幕組的來源、筆數、最近更新、第一批發佈名都印在卡上。

## Priority Issues

**[P1] 規模與主要動作都不在該在的地方**
- Why：13 列卡沒有任何一處說「13 個 torrent、共多少」；確認鍵在選了 Route 之前不存在，選了之後又在 13 列最底下（390 上約兩個視窗）。
- Fix：卡頭一行摘要（幾個發佈、總大小、送進哪條 Route／待選、已勾幾列）；`CONFIRM_ACTIONS` 在長卡上貼底；被藏起來的按鈕位置留一句「選好 Route 才能送出」。
- Command：`/impeccable layout`

**[P2] 13 個黃勾是卡上最響的東西**
- Why：全勾是常態卻被塗成滿片 `assigned`，與「要你確認」和主要動作搶同一個意思（The Usual Stays Unpainted）。
- Fix：批次列（≥3 列）的勾選框改中性（`ink` 勾），黃留給「要你確認」與確認鍵；同步改 DESIGN.md 的 Checkbox 規則。
- Command：`/impeccable quieter`

**[P2] 一列印四格、同一件事講 13 次，同集的重複列也沒標**
- Why：「作品」「Route —」各 13 次；兩部作品時資料夾說明原句重複；列沒有照季集排序（04、05、06、01…），同集的兩個來源隔得最遠而預設都勾。
- Fix：依作品分組（作品名、Route、資料夾、總大小一次），列只留發佈名、大小、已有的集；列照季集排序；同集的列標出來。
- Command：`/impeccable distill`

**[P2] 訂閱卡一次問三件事，還把同一段話說兩次**
- Why：Route、字幕組（6 選 1）、第一輪（2 選 1）同時出現；第三個的後果顯示在卡片前段；`routeLead` 在訂閱卡說「送單」、在單一作品卡說「兩部以上作品」；`firstBatchAfter` 與 `round.allHint` 是同一句話的兩個版本；「第一批」當標籤出現兩次。
- Fix：引導句照命令與組數給；兩段第一批說明只留一段；第二個「第一批」改名；第一輪在字幕組選定之後才展開。
- Command：`/impeccable clarify`

**[P2] 選中態、來源與錯誤位置對輔助技術不友善**
- Why：字幕組的選中只有邊框與底色；「勾幾項」「還有 N 部作品沒選 Route」「確認鍵出現／消失」不在 live region；「含已有的…」沒有 `aria-describedby`；Route 的下拉沒有 `aria-invalid`，錯誤句在卡片最底；字幕組用 `aria-pressed` 的 toggle 按鈕群。
- Fix：選中態加非顏色訊號；摘要與阻擋句放進常駐 `role="status"`；held 綁到那一列；Route 的阻擋句搬到下拉旁並設 `aria-invalid`；字幕組改 `role="radiogroup"`。
- Command：`/impeccable harden`

## Persona Red Flags

**Alex（進階使用者）**：13 列要挑掉同集重複與已經有的集，沒有全選／全不選；改 Route 在頂端、確認在底端，來回兩個畫面；Tab 要穿過 13 個勾選框才到確認鍵；卡上沒有總大小，比不出划不划算。
**Sam（輔助技術）**：卡片出現時沒有即時提示（只是把工具那一行換成一張卡）；勾掉一列、確認鍵變數字、勾到零時整顆消失，都不會被念；字幕組六顆按鈕只有邊框粗細的差別；「含已有的…」是視覺相鄰不是程式關聯。
**Casey（手機）**：390 的面板蓋滿全螢幕，捲到中段時卡頭、作品名、Route 全在畫面外，眼前只剩四列一樣的發佈名與一顆「拒絕」；要拒絕得滑過 13 列，要選 Route 得滑回頂端。

## Minor Observations

- 還沒選 Route 時每一列顯示「—」，讀起來像「沒有 Route／壞了」而不是「還沒選」。
- 「期限：24 小時後」是相對時間，卡片留在歷史裡之後會一直相對下去。
- 按過的卡仍保留全部 13 列永遠展開；歷史卡可以收成摘要。
- 同一段對話兩張「送出下載」時 region 名稱重複。
- 證據限制：截圖是 Route 未選的狀態，確認鍵存在的樣子是推論；實作後補拍。

## Questions to Consider

- 13 列真的需要 13 個勾選框嗎？例外只有兩種（同集重複、已經有了），要不要把「批次」做成一個決策、逐列留給例外？
- 送出前能不能給一點「入庫」的樣子（這 12 個會變成哪 12 個檔案、放在哪）？
- 磁碟空間要不要一起看？13 個 torrent 是最能事前給保證的地方。
