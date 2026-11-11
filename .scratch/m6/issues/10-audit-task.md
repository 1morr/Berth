# 10 — AI 任務：audit 與第一批，加 Jellyfin 回驗抓到的不符

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** spec〈第一批任務型別〉、〈AI 評估〉、〈共同規則〉；brief §6.10（程式檢查抓到的那一段）、§15〈季號、offset 與第一批確認〉；`CONTEXT.md`〈Audit〉〈First Batch〉、`jellyfin_item_mismatch`；C1 表「Audit」「第一批確認」兩列；`services/review.py`、`services/first_batch.py`、`services/rematch.py`；第 05、06 張的 Comments

## 為什麼

第一批就是以 RSS Series 分組的 audit：同一個佇列、同一組確認與撤銷的命令。Jellyfin 回驗抓到的不符也是「已經入庫、可能不對」，處理同樣是撤銷、rematch、必要時寫回 offset。三者併成一型（2026-11-11 拆票時定）。

## 做什麼

1. 決定的形狀：
   - 單一 audit：確認，或撤銷後 rematch 到正確的集。
   - 第一批：證據夠就確認整批；季號或 offset 錯就改正一集、套用到這個 RSS Series（寫回季號與 offset，重算未確認的集數：已入庫的 rematch、停在 review 的重新規劃）。
   - `jellyfin_item_mismatch`：撤銷、rematch，或交給人（Jellyfin 那邊的問題，例如兩份正片被併成一集，Berth 修不了）。
2. 套用都走現有的人工命令，經執行器；驗證同第 05 張，加播出日比對。
3. 案例集：從真實資料取樣，三種都有，只動可撤銷的東西，至少 20 件，連同標準答案凍進 repo。
4. 跑評估（兩種接口），達標才在設定頁放開關（三種一個開關或分開，在票內定並寫進 Comments）。
5. 文件：brief §6.10、§15、`CONTEXT.md`。

## 驗收

- [ ] 假模型下：audit 確認、撤銷後 rematch；第一批整批確認、改正一集後寫回 offset 並重算未確認的集數；`jellyfin_item_mismatch` 撤銷後 rematch（整合測試）
- [ ] 真模型評估 ≥ 20 件：套用的錯 0 件、交回人的比例 < 5%，數字在 Comments 與研究紀錄
- [ ] AI 關著或開關在人時行為不變（整合測試）；設定頁有開關
- [ ] 全部檢查、pytest、vitest 綠

## Comments
