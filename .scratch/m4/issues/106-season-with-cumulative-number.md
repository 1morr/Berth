# 106 — 季號明寫、集號跨季累計時換算成那一季的集；設定頁顯示版本；「拒絕」改叫「重新規劃」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §4.4；`berth/parser/mapping.py` 的 `_from_hint`、`_cumulative`；`tests/fixtures/parser/README.md`〈v5 補的兩筆〉；`berth/api/health.py`；`web/src/api/health.ts`、`web/src/settings/SettingsFrame.tsx`

## 為什麼

使用者 2026-10-16 在 0.2.7 的審核頁看到 7 件看不懂要做什麼的計劃。例子是 ANi 的 `黑色五葉草 Season 2 - 171`、`重生者的魔法一定要特別 第二季 - 13`：

- TMDB 上 Black Clover（73223）第 1 季 170 集、第 2 季 26 集；A Returner's Magic（230050）第 1 季 12 集、第 2 季 12 集（2026-10-16 查 themoviedb.org 的 seasons 頁）。
- 字幕組明寫季號，集號卻從第一季一路數下來：171 是 S02E01，13 也是 S02E01。
- `_from_hint` 照字面讀成 S02E171、S02E13，TMDB 查不到就降成 low、停在審核，而「核准後寫到」印的是錯的路徑。畫面上看起來沒有錯，使用者不知道該改什麼；直接核准會寫出 Jellyfin 對不上的孤兒集。

`tests/fixtures/parser/README.md` 記過同一類（SPY×FAMILY `Season 3 - 50`），當時寫的是「季號明說時要不要改走絕對編號，現在沒有規則回答」。這張票補上那條規則。

另外，使用者無法從畫面上得知自己跑的是哪一版（只能打 `/api/health`），設定頁要能看到。

## 使用者拍板（2026-10-16）

- 一張票，最簡實現。不做「由哪一版計算」的標示、不做審核頁的「建議 + 一鍵套用」UI：換算對了，「核准後寫到」那一行本身就是對的。

## 做什麼

1. **解析器**：`_from_hint` 裡，提示的那一季存在、但字面集號不在那一季時，拿同一個 span 走 `_cumulative(_regular(media), span)`。換算結果**落在提示的那一季**才採用：季集用換算後的，信心 medium（與其他 `absolute_cumulative` 一致），理由是提示原本那一條加上 `absolute_cumulative`。落在別季或換算不出來時照舊（字面、low、`episode_not_on_tmdb`）。不新增 `ReasonCode`。
2. **測試先行**（`mattpocock-skills:tdd`）：unit 測試用手建的快照涵蓋三種：
   - 換得進提示的那一季（170 + 26 集，`Season 2 - 171` → S02E01）
   - 換到別季時不採用
   - 字面就存在時不動（`Season 2 - 05` 仍是 S02E05）
3. **bench**：跑 `berth bench` 貼改動前後的輸出。`auto_wrong` 不得上升；SPY×FAMILY 那兩筆應該讀成 S03E13 / S03E10。fixture README 那一段「現在沒有規則回答」改成現在的規則。
4. **版本**：`SettingsFrame` 底部加一行 `Berth 0.2.7`，資料讀前端已經在用的 `/health` query（`web/src/api/health.ts`），不加新端點。i18n 的 zh-Hant、en 並列。
5. **審核頁的「拒絕」改叫「重新規劃」**（使用者 2026-10-16 拍板）：它做的事與下載詳情頁的「重新規劃」相同（`replan_job` 註解寫明走的是「使用者拒絕」那一條），叫「拒絕」會被讀成「不要這筆」。只改 i18n 文案，zh-Hant 與 en 並列：
   - `review.plan` 的 `reject`、`confirmReject`、`confirmRejectAction`、`rejected`。確認句要說清楚三件事：會用目前的 TMDB 資料與設定重算、改過的列會丟掉、檔案不動。
   - 時間線的 `reviewRejected`、Plan 狀態的 `rejected` 跟著改成同一個說法。
   - 端點 `POST /review/.../reject`、`PlanStatus.REJECTED`、事件名稱都不動：使用者看不到，改了反而是對外介面的破壞性變更。
6. **註解對齊**：`berth/api/health.py` 開頭說匿名那一支「只回一個字」、不該讓人知道版本，實際上它回版本。改註解，不改行為。
7. **文件**：plan §4.4 補這條規則；CHANGELOG `[Unreleased]`；progress.md「偏差與決定」記一行。

## 不做

- 已經停在審核的計劃不自動重算：拒絕之後重新規劃就會套到新規則。CHANGELOG 寫一句。
- 審核頁的理由排序、「0 個檔案要入庫」的說法不在這張票。

## 驗收

- [ ] `Season 2 - 171`（第 1 季 170 集、第 2 季 26 集）計劃成 S02E01、medium，理由含 `absolute_cumulative`；換到別季時照舊 low；字面存在時不動（pytest，做變異驗證）
- [ ] `berth bench` 前後輸出貼在票裡，`auto_wrong` 沒有上升
- [ ] 設定頁每一個分頁看得到 Berth 版本（vitest，zh-Hant 與 en；playwright 實跑截圖）
- [ ] 審核頁、時間線、Plan 狀態不再出現「拒絕 / Reject」，改說「重新規劃」；確認句說得出重算、丟掉改動、檔案不動（vitest，zh-Hant 與 en）
- [ ] `health.py` 註解與行為一致
- [ ] 全部檢查、pytest、vitest 綠；progress.md、CHANGELOG、plan §4.4 已更新
