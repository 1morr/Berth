# 08 — AI 任務：Unmatched 檔案

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** spec〈第一批任務型別〉、〈AI 評估〉、〈共同規則〉；brief §7.4、§6.10；plan §4.5（「猜作品」是另一種任務那一點）；C1 表「Unmatched 檔案」那一列；`services/rematch.py`、`services/review.py` 的 Unmatched 部分；第 05、06 張的 Comments（地基與評估的介面）

## 為什麼

Unmatched 是規則層連作品或集都對不上的檔案，現在全部等人指派。

## 做什麼

1. 決定的形狀：指派到某部作品的某一集、標 Extra，或交給人。**先定「猜作品」在不在這張**：spec〈第一批任務型別〉與 plan §4.5 說猜作品是另一種任務，這一步的寫法卻把它放進來；定案寫進 Comments，同一 commit 改 spec（2026-11-12 M5.6 回顧）。若在這張：猜作品時 `PlanItem` 沒有 `media_id`，資料包要帶候選作品（程式先用 TMDB 搜好）。「忽略」會藏起問題，做成 Proposal（`needs_person`）。
2. 套用走現有的人工命令（rematch 一類），經執行器；驗證同第 05 張。
3. 案例集：benchmark 語料裡 Unmatched 的 42 個檔案，標準答案重標成正確的集、Extra 或「交給人」（語料原本的答案是「對不到」，照用的話 AI 指派任何一集都算錯）；只動可撤銷的東西，至少 20 件。
4. 跑評估（兩種接口），達標才在設定頁放這個決定點的開關。
5. 文件：plan §4.5、`CONTEXT.md`（有新名詞時）。

## 驗收

- [ ] 假模型下：Unmatched 檔案被指派到集或標 Extra、入庫可撤銷；「忽略」停在 Proposal（整合測試）
- [ ] 真模型評估：套用的錯 0 件、交回人的比例 ≤ 5%，數字在 Comments 與研究紀錄
- [ ] AI 關著或開關在人時行為不變（整合測試）
- [ ] 設定頁有開關（vitest）
- [ ] 全部檢查、pytest、vitest 綠

## Comments
