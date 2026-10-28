# 28 — 助理看得到 Jellyfin 裡已有、Berth 沒紀錄的作品

**Status:** ready-for-agent

**Blocked by:** 27

**讀:** brief §9（對帳、重新入庫）、§11（帳號與權限，Jellyfin 媒體庫的允許清單）、§20.8；plan §11.2b M1.5 媒體庫瀏覽、§11.6；`berth/services/inventory.py`（`read_wall`、`read_holdings`）、`berth/services/media.py`（`read_media` 的季集狀態）、`berth/services/search.py`（缺集搜尋怎麼算「缺」）、`berth/services/agent_tools.py`、`berth/skills/new-season-picks`、`missing-episodes`、`series-mapping`；`berth rebuild-ledger` 與審核頁「從媒體庫重建帳本」

## 為什麼

使用者 2026-10-28 問助理「看不看得到庫裡已有的媒體」。現況：

- 助理只看得到 **Berth 帳本**（經 Berth 入庫的）；一次一部作品，沒有列出整個媒體庫的工具。
- Jellyfin 裡有、Berth 沒紀錄的（自己複製進去的、舊安裝入庫的）在助理眼裡是「缺」，補缺集與整部系列可能**重複下載**；新番推薦也不看使用者已經有或已經訂閱的。

使用者決定照建議修：給助理讀媒體庫的能力，推薦、補缺集、整部系列時先標出「你可能已經有」。

## 做什麼

1. 先用 `mattpocock-skills:codebase-design` 想清楚邊界再動手，寫進票 Comments：
   - 「Jellyfin 有、帳本沒有」的集要怎麼讓 `read_media`（給模型的那一份）看得到，例如每集多一個狀態或旁註；畫面要不要跟著改（作品頁現在已有「Jellyfin 有這部，Berth 的紀錄裡沒有」）。
   - 缺集搜尋（`scope.missing`）要不要把這些集當成「不缺」；選「標出來由人決定」還是「直接不搜」，寫理由。預設偏向不重複下載。
   - 權限：照 brief §11，一個人只看得到自己被允許的媒體庫（`read_wall` 已守）；給模型的工具不能繞過。
2. 給模型一支讀媒體庫的工具（例如列出某個媒體庫的作品、或用名字查「我有沒有 X」），照 `audience` 與允許清單。
3. skills：
   - `new-season-picks` 標出已經有、已經訂閱的；
   - `missing-episodes`、`series-mapping` 先看 Jellyfin 已有的，不推薦重下；
   - 有大量「Jellyfin 有、帳本沒有」時，建議使用者跑「從媒體庫重建帳本」。
4. 注入測試：新工具的結果（Jellyfin 的標題）是外部內容嗎？照 plan §11.6 的防線表判斷並補測試（`test_injection_claims`）。

## 驗收

- [ ] 給模型的作品資料分得出「帳本有」「只有 Jellyfin 有」「缺」（測試）；缺集搜尋照決定處理（測試）
- [ ] 讀媒體庫的工具照允許清單擋（測試，變異會紅）
- [ ] 三份 skill 已改（`test_skills.py` 綠）
- [ ] 真模型確認（`.env` key，預算上限 $0.5）：情境裡 Jellyfin 已有某部作品的前幾集、帳本沒有，「補 X 缺的集」不會重下那幾集、「推薦這季新番」會標出已有的；逐字稿寫進研究檔與票 Comments
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；brief / plan、CHANGELOG、progress.md 已更新
- [ ] 不發版、不 push

## Comments
