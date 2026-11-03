# 02 — 模型清單

**Status:** done

**Blocked by:** 01

**讀:** spec〈範圍〉「模型清單」；brief §20.26（Open WebUI 的慣例、模型清單端點）；plan §6〈settings〉；`docs/research/assistant-feedback-2026-11-01.md`

## 為什麼

設定頁的模型下拉現在讀的是本機價目表，填了 DeepSeek 的網址也看不到 DeepSeek 的模型。照 Open WebUI 的做法向填的端點問模型，問不到就照打；但只在按了按鈕才連外，不自動問（使用者定）。

## 做什麼

1. **沒按之前**：建議清單是 `known_models(表單的 base URL)`，改網址就換。要一支只讀本機表、不帶 key、不連外的端點（或併進下面那支：`key` 不送時只查本機）。
2. **「取得模型」**：模型欄旁一顆按鈕，按了才打 `POST /settings/ai/models`（命令 `ai.list_models`，`Effect.READ`、`CONNECTS_OUT`）。
   - 收表單上還沒存的接口、base URL 與 key，不收模型名。key 用 01 的函式決定，網址改了而 key 欄空著就是 `key_missing`。
   - Anthropic 接口打 `{base}/v1/models`（有分頁），OpenAI 接口打 `{base}/models`。
   - 回 `models`、`source`（`endpoint` / `prices`）與失敗原因。問不到不算請求錯：退回本機表，並說明原因。
3. base URL 或 key 改了時，按鈕取得的清單收掉。模型欄仍可自由輸入，AI 開著時模型名仍必填。
4. 帶 key 的回應形狀：adapter 用 fixture 做契約測試；實測一次補進 brief §20.26（要 key 時問使用者；沒有就照官方文件定形狀，在 brief 標「未實測」）。

## 驗收

- [x] 填 DeepSeek 的 base URL、還沒存：建議馬上換成本機表的 DeepSeek 模型，過程沒有請求帶 key、也沒有連外（測試＋playwright）
- [x] 按「取得模型」後換成該端點回的模型；Anthropic 的分頁收齊（契約測試）
- [x] 問不到時退回本機表並說明，仍可照打；base URL 改了之後取得的清單不留著
- [x] 存著 key、改了 base URL、key 欄空著時，取得模型是 `key_missing`，fake 記不到帶舊 key 的請求
- [x] brief §20.26 補上模型清單端點的回應形狀與來源
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 介面：`GET /settings/ai/models?provider=&base_url=`（命令 `ai.suggest_models`，`Effect.READ`，不碰資料庫、不連外）與 `POST /settings/ai/models`（`ai.list_models`，`READ` + `CONNECTS_OUT`）。沒有併成一支：`key` 不送在按鈕上表示「用存著的那把」，跟「只查本機」撞意思。`GET /settings/ai` 的 `known_models` 拿掉，建議只有這一個來源。
- adapter `adapters/ai/catalog.py` 走 `HttpSession`、自己翻 Anthropic 的分頁（`limit=1000`、`after_id`，最多 10 頁），**不跟轉址**：`x-api-key` 是自訂標頭，httpx 轉到別的主機不會拿掉它。`HttpSession` 因此多一個 `follow_redirects`。
- **DeepSeek 的 Anthropic 接口不提供模型清單**（2026-11-04 實測，`scripts/experiments/ai_models.py`，使用者要的）：對的 key 走 `x-api-key` 與 `Bearer` 都是 404、空 body，錯的 key 先回 401。所以標頭維持 `x-api-key`，404 / 405 / 501 說「這個端點不提供模型清單（也可能是 Base URL 的路徑不對）」並退回本機表（它認得 DeepSeek），401 / 403 才說 key 被拒（前端 `MODELS_FAILURE_TEXT`）。官方 Anthropic 與 OpenAI 沒有 key，fixture 照文件、brief 標「未實測」。
- 端點列出空的也退回本機表，`failure` 是 `null`，畫面說「這個端點沒有列出模型」。
- 按鈕放在模型欄下面（與「測試連線」同一種排法），不是同一列：欄位下有提示文字，同列對不齊，390px 也擠。
- 建議的查詢防抖 300 ms（只查本機表），換網址時保留舊清單到新的回來。
- 實跑（playwright `settings` 與 `settings-390`，fake 後端 `healthy`）：OpenAI 接口填 DeepSeek 網址與 key，建議換成 `deepseek-*`、沒有任何對外或帶 key 的請求；按「取得模型」換成替身列的兩個；key 改 `rejected` 後再按，說 key 被拒並退回本機表，模型照打；改網址後取得的清單收掉。截圖在 `web/test-results/settings-AI-設定的模型清單*/`。
- code-review 已修：實驗腳本列進 `scripts/experiments/README.md`、輸出改英文；`_base_url` 直接收接口與網址（不再湊空模型名的 `AiForm`）；`_ANSWERS` 改名 `_CLASSIFIED_STATUSES`；404 的說法補「也可能是 Base URL 的路徑不對」（OpenAI 接口填錯路徑也是 404）。
- code-review 未處理：
  - 拿掉 `GET /settings/ai` 的 `known_models`：這支 API 只有 Berth 自己的畫面在用，照「內部改動直接刪舊路徑」，不留兩個建議來源；CHANGELOG 發版時才整理。
  - 按鈕在模型欄下面而不是同一列：理由見上。
  - `catalog._refusal` 與 `adapters.ai._http_failure` 的狀態碼分類沒合併：一個收 `ModelHTTPError`、一個收 HTTP 回應，而且 404 的意思不同（找不到模型 vs. 沒有模型清單）。
  - `failure / status / detail` 在 `Probe`、`ModelListing`、`AiModels` 各寫一次：分屬 adapter 與 service 兩層，合成一型要讓 service 依賴 adapter 的型別，不划算。
  - `FakeAi.endpoints` 同時記組模型與列模型（列模型的 `model` 是空字串）：測試要斷言的正是「任何一種連出去都沒帶舊 key」，記在同一份才好查。
  - 空清單時 `failure` 是 `null`、畫面另說「端點沒有列出模型」：不是失敗，不另加分類。
