# 07 — AI 設定與用量記錄（Anthropic 格式）

**Status:** done

**Blocked by:** 06

**讀:** plan §11.6〈provider〉〈用量記錄〉、§2.1、§1.3；brief §6.10「用量，不設預算」、§13 設定那一列、§19 2026-10-24 第⑤條、§20 票 06 新增的一節；`docs/research/` 票 06 的結論；CONTEXT.md 的 AI Call

## 為什麼

provider 與用量記錄是側面板與背景任務共用的地基。這一張先做 Anthropic 格式，連同設定與 `ai_calls` 端到端跑通：管理員在設定頁填 base URL 與 key、按測試，看到第一筆用量。OpenAI 相容格式在 07b，接在同一個介面上。

## 做什麼

1. **provider 介面**（照票 06 的草案）：對話核心只看 Berth 自己的型別——訊息、工具、串流事件、usage（缺的欄位是「不知道」，不是 0）、錯誤分成限流、provider 掛掉、驗證失敗、連不上。介面放在 `adapters/` 這一側，不 import services。`adapters/ai.py` 裡還提「預算檢查」的 docstring 一起改掉。
2. **Anthropic 格式的 adapter**：支援自訂 base URL（留空用官方）。
3. **`settings.ai`**：格式（這張只開 Anthropic，07b 加 OpenAI 相容）、base URL、API key、模型。key 的存法、顯示（遮罩）、清除，照現有服務憑證的慣例。模型可從端點的模型清單挑，也可手填。
4. **`ai_calls` 表**與 migration：格式、base URL 的主機、model、輸入與輸出 tokens、快取寫入與讀取 tokens（可為「不知道」）、耗時、出處（對話或 AI 任務，這張先只有「測試」）、誰。不掛在 Job 上（plan §11.6）。
5. **設定頁的 AI 一格**：選格式、填 base URL 與 key、選或填模型，「測試」打一次最小請求，**再試一次工具呼叫**（給一個無害的假工具，看模型有沒有照格式呼叫），成功顯示回應、這一次的 tokens 與「支援工具呼叫」，失敗說出原因（無效 key、限流、連不上、模型不存在）。新的一格照 CLAUDE.md 先 `/impeccable shape`，或沿用設定頁既有格的形狀並說明。
6. **不支援工具呼叫**：測試結果存進 `settings.ai`，設定頁直接說「這個模型只能聊天，側面板不能替你訂閱、搜尋或下載」；換了格式、base URL 或模型就要重測。票 08 讀它。
7. **沒設 key**：整個系統與 M4 相同，後面的票都靠這一條。
8. `docs/guide/` 補一段 AI 設定（英文），README 兩份照 CLAUDE.md 同步。

## 票 06 的補充（開工時先定）

- **「AI 設定好了」看什麼**：自架的 Ollama / vLLM 不需要 key，第 7 條的「沒設 key」不能照字面只看 key（`docs/research/ai-providers.md` 最後一節第 6 條）。票 08 第 7 條跟著這個定義走。
- **探針是三次請求**：不帶工具的最小請求 → 帶假工具與隨機 nonce → 把結果送回去要拿到文字回覆（研究結論 4）。第三次是研究加的建議，比第 5 條原文多一步。
- 研究最後一節列了要真 key 才能確認的事，有 key 時一起實測，結果補進 brief §20.24。

## 驗收

- [x] 用假端點（respx）：測試請求寫一列 `ai_calls`，欄位齊全；端點沒回快取欄位時記成「不知道」（pytest）
- [x] 自訂 base URL 生效：請求打到填的主機（pytest）
- [x] 假端點不回工具呼叫（只回文字、或拒絕 `tools`）→ 測試結果是「不支援」，設定頁說清楚；改模型後要重測（pytest＋vitest）
- [x] 限流、無效 key、連不上、模型不存在各自回出對的原因（pytest）
- [x] 設定頁填 key、按測試、看到結果（playwright 實跑；有真 key 時附一次真的呼叫結果）——對演練伺服器的 `DemoChatProvider` 跑：支援、只能聊天、未存改動要重測、無效 key、讀模型清單；**沒有真 key，真的呼叫還沒做**
- [x] 沒設 key 時現有測試全部照舊綠
- [x] 全部檢查、pytest、vitest 綠；brief / plan 有被推翻的同輪改；docs/guide、CHANGELOG、progress.md 已更新

## Comments

- 2026-10-24 實作（session 紀錄在 progress.md）。設定頁的 AI 一格**沿用「設定 → 通知」頁的形狀**（`.scratch/m4/notify-settings-shape.md`）：同一組 `SettingsFrame` / `SettingsSection`、key 只寫不讀加 ConfirmAction 移除、測試結果放常駐的 live region，所以沒有另做 `/impeccable shape`。「只能聊天」的常駐狀態用 `assigned` 不用 `blocked`（`blocked` 是 `role=alert`，每次開頁都會被念）。
- **沒有真 key**：研究最後一節第 1–3 條（兩個認證標頭同送、第三方遇到頂層 `cache_control`、thinking block 會不會回）照研究的建議先做，等有 key 時用 `BERTH_AI_REAL=1 uv run python scripts/fake_setup_server.py --scenario healthy` 實測，結果補進 brief §20.24「票 07 實作時定的」。
- code-review 沒處理、交給後面的：
  - **07b**：加一種格式要動 `ApiFormat`、migration、兩個 factory 的 `ai()`、`services.ai.default_model`（現在直接拿 Anthropic 的預設、沒看 `settings.format`）與前端的 `<option>`；開工時考慮收成一張「格式 → adapter 與預設模型」的表。`adapters/ai/anthropic._input` 與 `services/ai._nonce_of` 是同一段「參數原文解成 dict」，07b 的 adapter 也會要，到時候放進 `adapters/ai` 共用。
  - **05（命令登錄表）**：`set_ai` 標 `REVERSIBLE`（同其他 `set_*`），但 `api_key=""` 會清掉一把只寫不讀的 key、回不去；plan §11.6 把「改設定」列為 irreversible，登錄表那張一起重看設定類命令的標記。
  - 判斷題、不改：「`AiFailure` + 原文」這一組在 `AiTestView`、`ModelList` 與前端的錯誤區塊重複出現（三處形狀小、各自的下一步不同）；`scripts/fake_setup_server.py` 的 `DemoChatProvider` 與 `FakeChatProvider` 送事件的順序相同（Demo 要看請求作答、而且不限次數，Fake 是照順序取的腳本）。
