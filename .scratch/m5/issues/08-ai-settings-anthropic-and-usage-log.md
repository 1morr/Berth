# 08 — AI 設定、Anthropic provider 與用量記錄

**Status:** done

**Blocked by:** 07

**讀:** plan §11.6〈provider〉〈用量記錄〉、§2.1、§1.3；brief §6.10「用量，不設預算」、§13 設定那一列、§19 2026-10-24 第⑤條、§20 票 07 新增的一節；`docs/research/` 票 07 的結論；CONTEXT.md 的 AI Call；plan §11.6 末段〈第一次嘗試的實跑發現〉前兩條；參考 `backup/m5-attempt-1-20261024` 的 `435bc47`、`9c8ea32`、`fd5dd1c`

## 為什麼

provider 與用量記錄是側面板與背景任務共用的地基。這一張先做 Anthropic 格式，連同設定與 `ai_calls` 端到端跑通：管理員在設定頁填 base URL 與 key、按測試，看到第一筆用量。OpenAI 相容格式在票 09，接在同一個介面上。

## 做什麼

1. **provider 介面**（照票 07 的草案）：對話核心只看 Berth 自己的型別——訊息、工具、串流事件、usage（缺的欄位是「不知道」，不是 0）、錯誤分成限流、provider 掛掉、驗證失敗、連不上。介面放在 `adapters/` 這一側，不 import services。`adapters/ai.py` 裡還提「預算檢查」的 docstring 一起改掉。
2. **Anthropic 格式的 adapter**：支援自訂 base URL（留空用官方）。
3. **`settings.ai`**：格式（這張只開 Anthropic，票 09 加 OpenAI 相容）、base URL、API key、模型。key 的存法、顯示（遮罩）、清除，照現有服務憑證的慣例。模型可從端點的模型清單挑，也可手填：讀到的模型畫成模型欄下方的一排按鈕，12 個以上時模型欄兼當搜尋框、只列符合的前 12 顆（第一次嘗試使用者選定）；列不出來時說「這個端點列不出模型，請照它的文件手填」。
4. **`ai_calls` 表**與 migration（**沒成的也記一列**：provider 錯誤、以及串流取消到一半的那一次——第一次嘗試漏了後者，已經花掉的輸入沒有記到）：格式、base URL 的主機、model、輸入與輸出 tokens、快取寫入與讀取 tokens（可為「不知道」）、耗時、出處（對話或 AI 任務，這張先只有「測試」）、誰。不掛在 Job 上（plan §11.6）。
5. **設定頁的 AI 一格**：選格式、填 base URL 與 key、選或填模型，「測試」打一次最小請求，**再試一次工具呼叫**（給一個無害的假工具，看模型有沒有照格式呼叫；第二步的指令寫成「呼叫一次，拿到結果後用一句話回」，不要寫「不要用文字回答」——那一句跟著歷史送回去，模型會再呼叫一次，第一次嘗試因此 6–8 / 10 誤判成只能聊天），成功顯示回應、這一次的 tokens 與「支援工具呼叫」，失敗說出原因（無效 key、限流、連不上、模型不存在）。新的一格照 CLAUDE.md 先 `/impeccable shape`，或沿用設定頁既有格的形狀並說明。
6. **不支援工具呼叫**：測試結果存進 `settings.ai`，設定頁直接說「這個模型只能聊天，側面板不能替你訂閱、搜尋或下載」；換了格式、base URL 或模型就要重測。票 10 讀它。
7. **沒設 key**：整個系統與 M4 相同，後面的票都靠這一條。
8. `docs/guide/` 補一段 AI 設定（英文），README 兩份照 CLAUDE.md 同步。

## 驗收

- [x] 用假端點（respx）：測試請求寫一列 `ai_calls`，欄位齊全；端點沒回快取欄位時記成「不知道」（pytest）
- [x] 自訂 base URL 生效：請求打到填的主機（pytest）
- [x] 假端點不回工具呼叫（只回文字、或拒絕 `tools`）→ 測試結果是「不支援」，設定頁說清楚；改模型後要重測（pytest＋vitest）
- [x] 限流、無效 key、連不上、模型不存在各自回出對的原因，失敗與取消的那一次也有一列（pytest）
- [x] 工具支援探測對一個「拿到結果就回文字」的假端點連跑 10 次都判成支援（pytest）
- [x] 設定頁填 key、按測試、看到結果（playwright 實跑；有真 key 時附一次真的呼叫結果）——對演練伺服器（`healthy`，`DemoChatProvider`）跑：無效 key、支援、讀模型清單、改了模型未存要重測、只能聊天、模型不存在、重新整理後結論還在、390 寬無橫向捲動、zh；**這個容器沒有真 key，真的呼叫沒做**
- [x] 沒設 key 時現有測試全部照舊綠
- [x] 全部檢查、pytest、vitest 綠；brief / plan 有被推翻的同輪改；docs/guide、CHANGELOG、progress.md 已更新

## Comments

- 2026-10-25 實作（session 紀錄在 progress.md）。程式碼以第一次嘗試的 `435bc47`、`9c8ea32`、`fd5dd1c` 為底移植，補上這張票多的：串流講到一半被取消也記一列（`AiFailure.CANCELLED`，介面多一個串流事件 `UsageReported`，記取消前最後知道的數字）、認證只送 `x-api-key`（brief §20.24）、`list_models` 回 `ModelInfo`（含 `max_input_tokens`，給票 17）、`StopReason.CONTEXT_FULL`、`set_ai` 改標 `irreversible`、工具探測連跑 10 次的測試（假端點照歷史裡每一句指令做：把指令改回「不要用文字回答」會紅）。
- **設定頁的 AI 一格沿用「設定 → 通知」頁的形狀**（`.scratch/m4/notify-settings-shape.md`），沒有另做 `/impeccable shape`：同一組 `SettingsFrame` / `SettingsSection`、key 只寫不讀加確認移除、測試結果放常駐的 live region。「只能聊天」的常駐狀態用 `assigned` 不用 `blocked`（`blocked` 是 `role=alert`，每次開頁都會被念）。截圖在 `.local/screens/m5-08/`。
- **沒有真 key**：OpenRouter 收不收 `x-api-key`、第三方碰到頂層 `cache_control` 是忽略還是 400、現役模型會不會回 thinking block，都標「未實測」寫在 brief §20.24「票 08 實作時定的」，等有 key 時用 `BERTH_AI_REAL=1 uv run python scripts/fake_setup_server.py --scenario healthy` 實測。
- code-review 沒處理的：
  - **prompt caching 照研究結論 6 送**（頂層 `cache_control`、system breakpoint、工具依名稱排序）：Spec 軸說票沒要求、第三方可能 400。留著：快取前綴與介面是同一層的事，第三方拒收時第一次測試就會說出 400 原文；實測後再決定。
  - **第三步又呼叫一次也算支援**（`9c8ea32`）與改指令措辭兩條並存：10 次的測試用「照歷史指令做、什麼都不回」的假端點，分得出措辭那一條；研究 §4 的判定表已補一句指向 brief。
  - 不是 Anthropic 形狀的 404 歸「看不懂」不歸「模型不存在」（多半是 base URL 的 `/v1` 寫錯），brief 已記。
  - 「12 個以上時模型欄兼當搜尋框」：實作是超過 12 個才兼當，照第一次嘗試使用者選定的行為。
  - 判斷題、不改：`api/ai.py` 的 `_user_id` 與 `api/notify.py` 同形（第三份，可收進 `api/gate.py`）；`Usage` 四欄與「失敗 + 原文」在 view / out / model 各展開一次；`HttpServiceClientFactory.ai()` 還不看 `endpoint.format`（票 09 加第二種格式時依它分，並讓缺的格式在測試裡紅）；`AnthropicProvider._session()` 的預設逾時是列模型那一個。
