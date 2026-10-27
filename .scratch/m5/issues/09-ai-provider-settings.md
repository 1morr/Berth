# 09 — AI provider 設定

**Status:** done

**Blocked by:** 01

**讀:** plan §11.6〈已定〉的 provider 那一條、〈分段〉第 4 段；brief §14〈provider〉、§20.24 的 provider 那幾條；`docs/research/m5-ai-direction-2026-10-27.md` A3 的 R13、R15、C5 的價目表；`scripts/experiments/m5_agent_chat.py` 的 `build_model`、`PRICES`；`berth/models/setting.py`；設定頁現有的分頁（`web/src/settings/`）

## 為什麼

M5 的一切都要先有一個模型可以叫。使用者決定兩種接口都做，各自設 base URL 與 key（brief §19「M5 的方向」⑧）。設定存在資料庫，跟 TMDB key 一樣，不從環境變數讀。

## 做什麼

1. **相依**：
   - 後端：`pydantic-ai-slim[anthropic,openai,ui]`，釘當前的 stable。它帶進 `httpx2`，確認與既有的 `httpx` 並存沒有問題。
   - 版本相關的寫法照 brief §20.24 與 context7，不憑記憶。
2. **`settings.ai`**：
   - provider 種類（`anthropic` / `openai`）、base URL、key、模型名。
   - Tavily key（選填，票 17 用）。
   - 開關：關掉 = 沒有 AI。
3. **adapter**：依設定組出模型物件（`adapters/ai/`）。
   - Anthropic 的 base URL 不含 `/v1`；OpenAI 相容的照那家服務的文件。
   - 價目表附查證日期；認不得的模型費用是 NULL，畫面寫「未知」，不當 0。
4. **設定頁的 AI 分頁**（admin）：先 `/impeccable shape`，再實作。
   - 填完按「測試連線」打一次最小呼叫，說出成功或服務回的原文。
   - key 只寫不讀：API 回 `has_key`，不回原值。
5. **key 不進 log**（R13）：補一條會紅的測試，DEBUG 也不會印出整份 settings 裡的 key。
6. **刪掉沒有呼叫端的 `AiPlanner` / `NullAiPlanner`**（R15）與守它的測試；M6 重設計，plan §4.5 已改。

## 驗收

- [x] 兩種 provider 都組得出模型；Anthropic 與 OpenAI 相容的 base URL 各有測試（用假的 transport，不打網路）
- [x] 測試連線的成功與失敗都說得出原因（測試＋playwright 實跑，附截圖）
- [x] key 不出現在 API 回應與 log（測試）
- [x] `adapters/ai.py` 的舊介面刪掉
- [x] `.env.example` 不加任何 AI 變數（產品不讀環境變數）；i18n zh-Hant 與 en
- [x] 全部檢查、pytest、vitest 綠；plan §2、§8 補；CHANGELOG、progress.md 已更新

## Comments

### 2026-10-27 實作紀錄

- 截圖（`signed-out` 演練情境，playwright 實跑）：`09-ai-provider-settings/empty-1280.png`（還沒設定）、`key-rejected-1280.png` 與 `key-rejected-details.png`（key 被拒，原文在技術細節）、`connected-saved-1280.png`（連上了、已儲存、價目）、`openai-remove-390.png`（390 寬、OpenAI 相容、價目未知、移除現用 key 的確認）。缺模型的拒絕也在實跑裡出現在模型欄下。
- shape：`.scratch/m5/ai-settings-shape.md`（使用者 2026-10-27 確認）。
- 與票面不同的決定記在 progress.md「偏差與決定」（兩種接口各自保存、清 key 獨立成 DELETE、httpx2 與 TestClient、價目表只用自己的、R13 的修法）。

### code-review 沒處理的發現

- Standards（判斷題）：README / README.zh-Hant 的 Status 沒提設定 → AI——AI 要等側面板（票 12）才有用處，到時一起寫。
- Standards（判斷題）：前端 `OFFICIAL_BASE_URL` 抄了後端的同名常數，可改由 API 回；依接口分流的地方散在後端三處、前端兩處（多一種接口要改五處）。現在只有兩種，先不抽。
- Standards（判斷題）：base URL 借用 `deeplink.normalized_public_url` 驗（會拒絕帶 `?` 的網址）；`forget_ai_key` 以 `AiProvider(secret.value)` 靠兩個 enum 字串值相同轉換。
- Standards（輕微）：`probe` 只接 pydantic-ai 的模型錯誤，其他例外（`UserError` 之類）會變成 500 而不是測試失敗；沒有量到會發生的路徑。
- Spec：價目只看模型名（相容閘道上同名模型照原廠價），記在 progress.md，票 21 決定。
- Spec：`.env.example` 裡 prototype 用的 `AI_*` 變數沒動（已寫明 Berth 不讀）。
- 已處理（2026-10-27，合併 main 之後）：`test_ai` 補上 `Flag.CONNECTS_OUT`（`Effect.READ` 照舊，`needs_person` 為真）——它連到表單上的任意網址、key 欄空著時帶的是存著的那把，還花 token。同輪補齊這張票其餘三支：`set_ai` 是 REVERSIBLE + SETTINGS + CONNECTS_OUT、inverse 指自己（收任意 base URL；同 `notify.set_bot_token`），`forget_ai_key` 是 IRREVERSIBLE + SETTINGS，`read_ai` 是 READ；四支都進 `tests/unit/test_command_marks.py` 的 `NAMED`。
- 已修：移除無關 key 時清掉沒存的「開啟」、存完 Base URL 沒換成後端正規化的值、`SettingsTabs` 的過時註解、`_complete` 改名、開關說明不再提還沒做的側面板、plan §1.2 / §1.4 補 ai 與依賴。
