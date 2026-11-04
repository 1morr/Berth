# 17b — 認不得的 Anthropic 相容閘道：推理「關」不送參數

**Status:** done

**Blocked by:** 17

**讀:** 票 17 的 Comments；brief §20.26；`berth/adapters/ai/__init__.py`（`_how_to_send`、`_reasoning`、`reasoning_applies`）；`scripts/experiments/reasoning_levels.py`；設定頁推理程度那一格的文案

## 為什麼

協調者插的追加票（使用者 2026-11-04 定「按你建議」）。票 17 的 Heads up：Anthropic 接口上不是 Claude 的模型走 `_Send.EXPLICIT`，四級都會送參數（低中高 `output_config.effort`，關 `thinking: disabled`）。DeepSeek 認得，沒問題；但認不得這兩個參數的相容閘道會回 400，而設定頁沒有「不送」的一級（使用者定的，不加），改哪一級都避不開。

使用者定：**「關」在認不得的閘道上什麼都不送**；DeepSeek 的「關」照舊明寫 `thinking: disabled`（票 17 實測過，關時才真的沒有推理）。

## 做什麼

1. 分出「已知收這兩個參數的相容端點」（目前只有 DeepSeek；怎麼認照 `codebase-design` 判斷：模型名、base URL 或 profile，記在 Comments）與其他。
2. 其他的相容閘道：關 → 不送任何推理參數；低、中、高照舊送 `output_config.effort`。
3. 服務拒絕推理參數（400）時，停下的說明除了指到設定頁，對這類閘道要說「選『關』就不送這個參數」。設定頁那一格的提示同步（zh-Hant、en）。
4. 測試錄 HTTP 請求本體驗：未知閘道＋關 → 請求裡沒有 `thinking` 與 `output_config`；DeepSeek＋關 → 仍有 `thinking.type=disabled`；未知閘道＋低 → 有 `output_config.effort`。
5. 文件：brief §20.26 補一句。

## 驗收

- [x] 上面三種請求本體的測試（修前紅的那條貼輸出）
- [x] 400 的停下說明與設定頁提示說得出「選關就不送」（測試；設定頁 playwright 實跑）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- **怎麼認 DeepSeek：以主機，不以模型名或 profile**（`adapters.ai._TAKES_THINKING_OFF = {"api.deepseek.com"}`，看 `effective_base_url` 的 hostname）。收不收 `thinking: disabled` 是端點解析請求的事：轉送 `deepseek-flash` 的閘道一樣可能 400，而 brief §20.26 只實測過官方主機。DeepSeek 換主機的話退回「關不送」：模型照樣推理但不會 400，是安全的那一邊。
- 介面：adapter 的 `reasoning_applies(provider, model)` 換成 `reasoning_support(provider, base_url, model) -> ReasoningSupport(applies, off_sends_nothing)`，`_Send` 多 `EFFORT_ONLY`；services 命令改名 `reasoning_support_of`（多收 `base_url`）；`GET /settings/ai/reasoning` 多收 `base_url`、多回 `off_sends_nothing`。停下的說明在 `Turn._note` 裡、只在 `reasoning_rejected` 時查一次，存進歷史，重新載入同一句。
- 修前紅（`tests/integration/test_ai_adapter.py::TestReasoning`）：`test_an_unknown_gateway_gets_nothing_when_off` 與 `test_deepseek_behind_another_host_is_an_unknown_gateway` 都是 `AssertionError: assert {'thinking': {'type': 'disabled'}} == {}`（2 failed, 36 passed）。
- 設定頁 playwright 實跑（fake 後端 `signed-out`，port 8611）：Base URL `https://llm.example.net/anthropic`、模型 `glm-4.6` 時程度那一格多出「Berth 不確定這個服務收不收推理參數：選「關」就不送這個參數；低、中、高照送，不收的服務會拒絕。」；改成 `https://api.deepseek.com/anthropic` 後這句消失。英文由 vitest 守。
- code-review（兩軸）已處理：`CONTEXT.md`〈Reasoning Level〉還寫舊名、services 命令名回傳型別變了改名、前端 `applies` 改 `support`、`aiReasoningQueryOptions` 註解、停下時只在被拒才查、DeepSeek 不說「選關就不送」補成整合測試。未處理：`Turn._note` 把 `self.endpoint` 拆成三個參數給 `reasoning_support`，它再組回 `AiEndpoint`（Data Clumps；設定頁那一支沒有 endpoint，先不開第二個入口）；`AiReasoningOut` 以 `from_attributes` 吃 adapter 的 dataclass，欄位名綁在一起（同檔其他 Out 一樣做法）。
- 沒打真的服務：改的只有認不得的閘道，DeepSeek 送出的參數不變（測試錄請求本體守著），手邊也沒有這種閘道的 key。
