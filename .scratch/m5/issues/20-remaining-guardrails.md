# 20 — 其餘防護

**Status:** done

**Blocked by:** 11

**讀:** plan §11.6〈已定〉的防護表；brief §6.10；`docs/research/m5-ai-direction-2026-10-27.md` C3；`docs/research/m5-prototype-2026-10-27.md`〈實跑才抓到的問題〉第 5、8 點

## 為什麼

票 11 做了基本防護：次數、token、重複呼叫、並發。剩下的是讓失控停得下來、停下來說得清楚。

## 做什麼

1. **無進展與乒乓**：A-B-A-B 交替、狀態雜湊不變時停下。門檻參考實測：單輪最多 9 次模型呼叫屬於正常。
2. **工具結果截斷**：單筆結果有上限，超過的給摘要和「還有 N 筆」。
3. **provider 斷路器**：連續 5 次失敗暫停 15 分鐘。側面板說明原因，背景的東西退回 M4 行為。
4. **停下來之後**：對話裡留一則說明（哪一條防護、做到哪），使用者可以按一次「繼續」。
5. 每種防護觸發時記在 `ai_runs` 的停止原因，用量頁（票 21）數得到。

## 驗收

- [x] 每一種防護各有一條觸發測試，停止原因正確
- [x] 「繼續」只能按一次（測試）
- [x] ~~斷路器開與關的狀態在側面板看得到（playwright 實跑）~~ 搬到票 22（2026-10-27 使用者決定：側面板是票 12，還沒做）；這張做了 `GET /agent/status` 與它的測試（開、關、一般使用者看得到）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- **收尾（票 22）**：側面板的兩塊 UI：斷路器開與關的狀態（讀 `GET /agent/status` 的 `paused_until`，一般使用者也看得到；管理員另有 `pause_error` 說是什麼錯）、防護停下時的「繼續」（`data-stop` 或對話的 `stop` 裡 `continuable` 是真才畫；按下去送一則按鈕上的字、body 帶 `continues: <turn_id>`；`not_continuable` 時收掉按鈕）。
- 斷路器的狀態在程序裡，重啟就清掉；多個 worker 的部署各數各的（Berth 是單一程序）。
- 被暫停擋下的那幾次沒有 `ai_runs` 的列（同 `ai_disabled`、`busy`）：用量頁數得到的是「暫停了幾次」（`circuit_open`），不是「擋了幾次」。要數後者的話票 21 再決定記在哪。
- 截斷沒有停止原因（它不停），用量頁數 `ai_tool_calls.truncated`。
- code-review（兩軸）修了：被擋下的呼叫被算成有進展（有 repro 測試）、`IntegrityError` 一律翻成「繼續不了」（只在帶 `continues` 時才翻；同時建同一段新對話的競爭不好在測試裡重現，沒有測試）、`_preview` 上限小於 2 時不會停、改名避開 CONTEXT.md 的 run 與 Resume（新詞 **Continue**）、`/agent/status` 多 `pause_error`（只給管理員）、乒乓與無進展收成 `agent_guards.Progress`、截斷又重複時不再包兩層 `result`。
- 協調者補的：「繼續」接的是票 11 `Turn._kept` 存的歷史，原本沒有測試守。`test_a_stopped_turn_keeps_every_step_that_finished`：兩步工具之後被 `request_limit` 停下，存著的歷史有兩組呼叫與結果、最後是停止說明、沒有缺結果的呼叫；把 `_kept` 改成只留 history + prompt 會紅（驗過）。
- code-review 提出、沒改的：暫停到期後放過去「試的一輪」沒有限成一輪，同時開的幾輪（不同的人）都會放行；同一步平行叫 [A, B]、下一步又是 [A, B] 也算乒乓（兩次模型呼叫就停）。兩個都照字面，實跑看到再調。`clip` 的上限只量結果本身，`truncated` 與 `note` 的外包另算（幾百字）。
