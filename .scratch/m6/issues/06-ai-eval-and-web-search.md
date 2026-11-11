# 06 — AI 評估指令與審核 Plan 的案例集，加第二段網搜，達標後開放

**Status:** ready-for-agent

**Blocked by:** 05

**讀:** spec〈範圍〉〈AI 評估〉〈AI 任務與 `ai_worker`〉第二段、〈共同規則〉；plan §4.6、§8.8〈伺服器端網搜與 log〉、§8.9、§10〈注入的防線〉；brief §14〈信任靠評估〉；`services/web.py`；`docs/research/agent-slimming-2026-11-06.md` §7〈環境〉（真模型量測的做法）

## 為什麼

ADR 0008：每種任務型別先過 AI 評估才開放。評估要打真模型、要花錢，所以第二段網搜跟評估一起做，只跑一次付費評估就同時驗到兩段。

## 做什麼

1. **評估指令**：手動跑、打真模型、不進單元測試（CLI 子指令或 `scripts/experiments/` 下的腳本，照 `berth bench` 的慣例選，理由寫進 Comments）。讀一份凍在 repo 的案例集（輸入 + 標準答案），輸出每件的結論、套用而錯的件數、交回人的比例、token 與費用。後面每一種任務型別都用這同一支。
2. **案例集**：benchmark 語料裡 review 的 84 個檔案，加上標準答案。缺 `air_date_conflict`、`runtime_conflict` 的案例時，從真實資料補，至少各幾件，連同標準答案凍進 repo。
3. **第二段**：模型答「資料不夠」才觸發，給唯讀網搜工具，網域白名單 `SEARCH_DOMAINS`，最多 3 次、算進每輪 4 次。走對話 agent 的同兩條路（Anthropic 用伺服器端 `web_search`，設了 Tavily key 用 `tavily_search`），兩條都沒有就交給人。網頁當外部內容；輸出仍是固定 schema、仍走驗證。
4. 跑評估（兩種接口各一次），門檻：套用的錯 0 件、交回人的比例 < 95%（spec〈AI 評估〉；84 個本來全進 review，基準是 100%）。結果寫進 Comments 與 `docs/research/` 的評估紀錄。
5. **達標才開放**：AI 設定頁加上「審核中的 Plan」的決定點開關（人／AI），i18n 兩種語言；沒達標就回報使用者，不放開關。
6. 文件：plan §4.5、§4.6（評估怎麼跑）、`docs/development.md`（新指令）、`scripts/experiments/README.md`；brief §20 若量到新的外部事實。

## 驗收

- [ ] 評估指令跑得出套用錯數、交回比例與費用；案例集與標準答案在 repo
- [ ] 第二段：假模型答「資料不夠」時拿到網搜、最多 3 次、兩條路都沒有時交給人（整合測試）；網頁內容不能讓輸出跳出 schema（注入測試）
- [ ] 真模型評估：套用的錯 0 件、交回人的比例 < 95%，數字在 Comments 與研究紀錄
- [ ] 設定頁有開關，切到 AI 後背景任務才套用（整合測試；playwright 實跑一次）
- [ ] 全部檢查、pytest、vitest 綠

## Comments
