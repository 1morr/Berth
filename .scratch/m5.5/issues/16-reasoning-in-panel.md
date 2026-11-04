# 16 — 面板畫推理

**Status:** done

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「推理」的第一條；brief §20.26（Vercel 串流與 `dump_messages` 都帶 `reasoning`）；plan §7〈側面板〉；`.scratch/m5/side-panel-shape.md`

## 為什麼

模型會回推理文字（`deepseek-flash` 不送 `thinking` 也會），串流裡有 `reasoning` 片段，但面板沒畫也沒接。

## 做什麼

1. 面板把 `reasoning` 片段畫成預設收起的區塊，串流時也一樣（不在串流途中自動展開）。
2. 重新載入後仍在：`GET /agent/conversations/{id}` 要帶出推理片段。
3. Fake 後端的 `agent` 情境補一段帶推理的回應，前端 e2e 用得到。

## 驗收

- [x] 模型回推理文字時，面板收在預設收起的區塊，展開看得到全文（e2e，桌機與 390px）
- [x] 重新載入後還在（e2e）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-11-04 後端本來就帶推理：`_relay` 的串流有 `reasoning-*` 片段，`dump_messages` 有 `reasoning` 那一格；缺的是 `FakeAi` 的串流把 `ThinkingPart` 丟了（改送 `DeltaThinkingPart`）與面板沒畫。`tests/integration/test_agent_reasoning.py` 守串流、重新載入、推理排在工具呼叫之前。
- 面板 `agent/Reasoning`：同「摘要」那一行的外觀，`<details>` 不給 `open`（React 不管它），所以串流中不自動展開，讀者展開後再串進來的字也不會把它收起（`Reasoning.test.tsx`）。照原文印、不走 markdown；沒有字的（服務遮掉的推理）不畫。串流中多一個「思考中」小色塊（票沒要求，票 19 critique 時一起看）。
- fake `agent` 情境：「想一想」（`think it over`）回三行推理加一句回答。
- code-review 已處理：AgentPanel 測試插錯位置、把注入那段的 JSDoc 搶走；DESIGN.md〈側面板〉補「推理」一條；`spoken` 的判斷回 boolean。
- code-review 未處理：`<details>` 一行的外殼在摘要、工具、推理三處重複（Duplicated Code），三者的狀態與展開內容都不同，先不抽。e2e 的 `streamed` 是串完才檢查（替身一次送完整段推理），「串流途中不展開」只有 vitest 守。推理的 `signature`（`providerMetadata.pydantic_ai.signature`）仍送到瀏覽器，瀏覽器用不到；與票 03 的「不透明資料不給瀏覽器」同類，沒有另外處理。
- 2026-11-04 驗證：`pre-commit run --all-files` 全過；pytest 5592 passed、1 skipped；vitest 2393 passed；前端 e2e 全部 project **89 passed**（2.5m），0 failed、0 flaky（開跑前 port 8484–8534 有 t12 在用，等整段空下來才跑；跑到一半重建過一次 `web/dist`，內容只差測試註解與一個等價的判斷）。
