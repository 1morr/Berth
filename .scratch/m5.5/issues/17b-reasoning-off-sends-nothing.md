# 17b — 認不得的 Anthropic 相容閘道：推理「關」不送參數

**Status:** ready-for-agent

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

- [ ] 上面三種請求本體的測試（修前紅的那條貼輸出）
- [ ] 400 的停下說明與設定頁提示說得出「選關就不送」（測試；設定頁 playwright 實跑）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments
