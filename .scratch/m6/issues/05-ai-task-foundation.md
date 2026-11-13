# 05 — AI 任務地基：先只接審核中的 Plan

**Status:** ready-for-agent

**Blocked by:** 04

**讀:** spec〈範圍〉〈決定點的開關〉〈AI 任務與 `ai_worker`〉〈驗證〉、〈共同規則〉；plan §4.5、§2.6、§3.2〈所有迴圈〉、§6〈命令執行器〉；brief §6.10、§14；ADR 0008、ADR 0016；`docs/research/m5-ai-direction-2026-10-27.md` C1、C3；`services/commands.py`、`services/executor.py` 的模組 docstring

## 為什麼

tracer bullet：一種任務型別從頭到尾跑通（規則層停在審核 → 開任務 → 模型決定 → 程式驗證 → 執行器套用或交給人），後面每一種型別只是換資料包、schema 與套用的命令。

## 做什麼

1. **設計先行**（`mattpocock-skills:codebase-design`）：`ai_tasks` 的欄位（型別、對象、狀態、結論、理由、快取鍵、嘗試次數）、`ai_worker` 與任務型別的介面（組資料包、schema、驗證、套用各是哪一層）、決定點開關存在哪（`SettingsGroup`）、AI 的 `actor`。這個介面要讓第 06 張的第二段網搜與第 08–10 張的新型別不必改地基。結論寫進 Comments 與模組 docstring。
2. **任務型別「審核中的 Plan」**：規則層停在 review 的 Plan，理由為 `low_confidence`、`medium_not_allowed`、`air_date_conflict`、`runtime_conflict`（程式檢查擋下的兩種，spec 合併進這一型；`target_exists` 要取代既有檔時照 C1 表留給人）。其餘理由要不要接，查定後寫進 Comments。spec〈第一批任務型別〉只列 low 加兩種程式檢查，沒提 `medium_not_allowed`；這張定案後同一 commit 寫回 spec（2026-11-12 M5.6 回顧）。模型改寫 Plan 的季集與分類後核准，或交給人。
3. **資料包**：plan §4.5 的內容，包括片長（`FileEntry.duration_s`、大小、TMDB `runtime`；片長偏離同組的不壓進樣本）。快取鍵 `torrent hash + 解析器版本 + prompt 版本`。
4. **只做第一段**（不給工具）：固定 schema 的輸出，理由為 `ReasonCode` 加一欄自由文字；schema 留一種「資料不夠」的結論，這張先當成交給人。
5. **驗證**：集在 TMDB 存在、不撞目標路徑、季集範圍、副檔名與分類一致、播出日、片長；不通過的不套用、交給人並附理由。
6. **防護**：每次呼叫 2048 output、每輪 4 次模型呼叫、100K / 8K token、並發 2、同一對象 24 小時最多 2 次、「交給人」的結論也快取、沿用 M5 的 provider 斷路器。用量記進 `ai_runs` / `ai_calls`。
7. **開關**：決定點開關預設「人」；這張**不放上設定頁**（第 06 張評估達標後才放）。AI 關著或開關在人時行為與現在一致。
8. 交給人的照舊進審核頁與「等你處理」。
9. 文件：plan §2（新表）、§3.2（新迴圈）、§4.5；`GLOSSARY.md`（新名詞）。

## 驗收

- [ ] 假模型下：一份 low 的 Plan 開任務、模型給出改寫、驗證通過、經執行器核准入庫，事件的 actor 認得出是 AI（整合測試）
- [ ] 模型的改寫沒通過驗證時不套用，Plan 留在審核並附理由（整合測試）
- [ ] 防護各有一條測試：超過上限停下並交給人、24 小時第三次不開、「交給人」的結論不重複付費
- [ ] AI 關著、或開關在人時，審核的行為與改動前一致（整合測試）
- [ ] 全部檢查、pytest 綠；`berth bench` 數字不變（沒動 `parser/` 也貼一次）

## Comments
