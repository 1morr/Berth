# 17 — 推理程度設定

**Status:** done

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「推理」；brief §20.26（DeepSeek 的推理程度、pydantic-ai 的推理）；plan §6〈settings〉；pydantic-ai 的 model settings 文件（context7 現查，版本以 `uv.lock` 為準）

## 為什麼

使用者要設得了推理程度。只用 pydantic-ai 統一的 `thinking` 不夠（brief §20.26 實測）：DeepSeek 的 Anthropic 接口會忽略 `budget_tokens`，OpenAI 接口的 profile 認不得的模型會被靜靜拿掉。

## 做什麼

1. `AiEndpointSettings` 新增 `reasoning`：`off`、`low`、`medium`、`high`，**預設 `medium`，沒有「預設」這一級**（使用者定）。兩種接口各記各的；舊資料沒有這一格就是 `medium`，不用 migration。
2. 設定頁：模型欄下面一格，提示說 DeepSeek 只分低與高，中等於高。
3. 由 `chat_settings` 轉成請求參數：
   - Anthropic 接口上 `deepseek-flash` 這類 profile 沒有 `anthropic_supports_effort` 的：程度明寫 `anthropic_effort`，`off` 明寫 `anthropic_thinking={'type': 'disabled'}`。
   - profile 有 `anthropic_supports_effort` 的 Claude 用統一設定。
   - OpenAI 接口：profile 認不得的模型不送（送了不支援的模型會 400），設定頁說明這個模型的程度沒有效果。
   - 以錄下的請求為準（測試錄 HTTP 請求本體），結果補進 brief §20.26。
4. 服務拒絕這個參數（400）時，停下的說明指到設定頁改程度。

## 驗收

- [x] 沒設過的設定讀回來是 `medium`（測試）
- [x] 錄下的請求：DeepSeek（Anthropic 接口）上低與高帶 `output_config.effort`、關帶 `thinking.type=disabled`；OpenAI 接口上 profile 認不得的模型不帶參數（測試）
- [x] 400 時停下的說明連到設定頁（測試）
- [x] 設定頁的程度欄與提示（zh-Hant、en；playwright 實跑）
- [x] brief §20.26 補上錄下的請求；全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- 推理程度怎麼送集中在 `adapters.ai._how_to_send`，`chat_settings` 與設定頁的 `reasoning_applies` 共用。設定頁的「沒有效果」走新的 `GET /settings/ai/reasoning`（只看 profile、不連外），不塞進模型清單那一支：那一支以網址為鍵，這一支以模型名為鍵。
- **偏離票的字面**（code-review 兩軸都抓到，查證屬實）：沒有 `anthropic_supports_effort` 的官方 Claude（`claude-sonnet-4-5`、`claude-haiku-4-5`、`claude-opus-4-1`）不送，設定頁說沒有效果。照字面明寫 effort 會被官方拒；改用統一設定的中、高是 `budget_tokens` 10000 / 16384，大過面板的 `max_tokens` 4096，也會被拒。不送等於加這一格之前的行為。判斷用模型名 `claude-` 開頭；不是 Claude 的相容端點照票明寫。
- 停下的說明：伺服器存的那一句只說「服務不接受這個推理程度」，連結由面板加（管理員連到 `/settings/ai#ai-reasoning`，焦點落在下拉選單；其他人請管理員改），因為存著的說明不分是誰在看。判斷照 `ai_runs.error` 的原文，串流與重新載入同一支；只認參數路徑（`output_config`、`effort`、`thinking.type`、`budget_tokens`），重播推理內容的 400 不算。
- 壓縮的摘要一律關（code-review 追加）：推理吃同一份 `SUMMARY_TOKENS`。測試連線（`probe`）照舊不送推理參數，所以測得過、對話仍可能被拒，那時看停下的說明。
- 實測真的 DeepSeek（`scripts/experiments/reasoning_levels.py`，key 不落檔）：Anthropic 接口四級都 200，關時沒有推理文字、output 1 token；OpenAI 接口不帶參數、照樣推理（brief §20.26）。
- fake `agent` 情境：「推理被拒」（`reasoning refused`）回 400，e2e `agent.spec.ts` 守連結與錨點。
- code-review 未處理：程度被拒的 400 仍算進 provider 斷路器（連拒 5 次會暫停 15 分鐘，其實只要改設定），斷路器的分類不在本票。`rejects_reasoning` 解析 `str(ModelHTTPError)` 的格式（重新載入時只有 `ai_runs.error` 這份原文），pydantic-ai 改了格式要跟著改，測試會紅。同一個概念的名字有 `reasoning_applies`（adapter）與 `reasoning_takes_effect`（services 命令，避免與 import 撞名）。`chat_settings(endpoint, model, …)` 的 `model` 是照 `endpoint` 組的，兩者一起傳（Data Clumps），呼叫端都已經各有一份，先不包。
- 2026-11-04 驗證：`pre-commit run --all-files` 全過；pytest 5674 passed、1 skipped；vitest 2416 passed；前端 e2e 全部 project **95 passed**（2.6m），0 failed、0 flaky（開跑前 port 8484–8534 有別的 worktree 在用，等空下來才跑）。
- 2026-11-04 合併 main（票 18 對話清單，`5f60e50f`）之後重驗：無衝突；新增的 e2e 開面板後改呼叫 `openBlank`；progress.md 本票那一列移到票 18 之後、下一步改成票 19；pre-commit 全過；pytest 5684 passed、1 skipped；vitest 2423 passed；`pnpm -C web build` 一次後完整跑前端 e2e **97 passed**（2.6m），0 failed、0 flaky，開跑前 port 8484–8534 沒人用。
