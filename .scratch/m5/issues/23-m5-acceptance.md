# 23 — M5 驗收

**Status:** done

**Blocked by:** 15, 22

**讀:** plan §11.6〈驗收〉；brief §17 的 M5 列；`docs/research/m5-prototype-2026-10-27.md`（驗收用同一套情境）；`scripts/experiments/m5_agent_scenarios.py`；`docs/development.md`〈e2e〉〈前端 e2e〉

## 為什麼

M5 的驗收有兩半：
- **決定性的**：假模型＋整合測試＋前端 e2e。
- **真模型的**：用使用者的 key 實際跑情境，要使用者提供 key 與時間，所以這張是 `ready-for-human`。

## 做什麼

1. **決定性的**：plan §11.6〈驗收〉逐條對到一條測試或一次 playwright 實跑。缺的補上。
   - 不可逆、`connects_out`、`downloads` 只能經確認卡（含注入）。
   - 重啟之後舊卡片還按得下去；壓縮之後卡片還在。
   - 每一輪的數字，含被中止的那一輪。
   - 防護各觸發一次。
   - 一般使用者的門禁。
   - 沒設 provider 時與 M4 相同：全套 test 綠，前端 e2e 照舊。
2. **真模型的**：
   - 把 `m5_agent_scenarios.py` 改成打產品的 `/agent/chat` 與 Proposal API，或另寫一支。
   - 用使用者的 key，對 Fake 後端 `search` 情境（真 TMDB、真索引站、替身 qBittorrent）跑情境 1–6。兩種接口要各自一台全新的 Berth（prototype 的教訓）。
   - 數字與逐字稿記在 `docs/research/`，對照 prototype 的那一份。
3. **真服務 e2e**：`TMDB_API_KEY` 已有，跑一次 `pytest -m e2e`，確認 M4 的 e2e 沒被弄壞。
4. 收尾：plan、brief、CHANGELOG、progress.md；要不要發版、push，先問使用者。

## 驗收

- [x] plan §11.6〈驗收〉每一條都有對應的測試或實跑紀錄（列在 Comments）
- [x] 真模型情境 1–3 走完，Re:Zero 全系列分批送出正確（數字與逐字稿在 `docs/research/`）
- [x] `pytest -m e2e` 綠（貼輸出）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments

### 2026-10-28 plan §11.6〈驗收〉逐條對照

| 驗收 | 守它的測試或實跑 |
| --- | --- |
| 情境 1、2、3 在側面板走完；Re:Zero 全系列分批送出正確 | 真模型實跑，兩種接口各一台全新的 Berth：`docs/research/m5-acceptance-2026-10-28.md`（逐字稿在同名資料夾）。Re:Zero 一張 7 列總覽卡（S01E01–E85 五包 + 兩部劇場版）全部 `done`，`/compact` 之後追問答對。**收窄**：plan 原寫「分批入庫」，替身 qBittorrent 不會真的下載，改成「分批送出」，送出到入庫由 M1–M4 的真服務 e2e 守（plan 同 commit 改字） |
| 不可逆、`connects_out`、`downloads` 只能經確認卡（含注入） | `tests/unit/test_command_flags.py`；`tests/unit/test_agent_tools.py::test_irreversible_tools_need_a_card`、`::test_which_writes_need_a_card`；`tests/integration/test_agent_injection.py`（`TestSettingsNeedAPerson`、`TestTorrentsNobodyAskedFor`、`TestAFeedFromOutside`、`TestForgedApprovalAndHistory`）；`tests/integration/test_agent_cards.py::TestACardStops`、`TestTheFrontendIsOnlyATrigger` |
| 重啟之後舊卡片按得下去 | `test_agent_cards.py::TestRestart::test_a_card_from_before_a_restart_is_pressed_and_resumed_after_it`；`tests/integration/test_proposals.py::test_a_card_from_before_a_restart_can_still_be_decided_and_run`、`::test_a_card_approved_before_a_restart_runs_after_it`；真模型 `openai-S2-continued.md`（重啟同一台 Berth 接著同一段對話送單） |
| `/compact` 與自動壓縮之後待確認的卡片仍在 | `/compact`：`test_agent_cards.py::TestHistoryShape::test_compact_then_confirm_and_the_resumed_turn_runs_as_usual`。**自動壓縮（本票補）**：`::test_auto_compaction_on_the_resumed_turn_keeps_the_card_and_its_result`、`::test_auto_compaction_while_a_card_waits_leaves_it_pressable`；`tests/unit/test_compaction.py::test_a_call_waiting_for_confirmation_stays_at_the_end` |
| 每一輪的步數、token、命中率、費用、停止原因，含被中止的 | `tests/integration/test_agent_api.py::TestTheSteps`（`test_a_stopped_turn_has_its_steps_and_numbers` 等）、`TestClosingTheConnection::test_a_turn_cut_off_midway_is_booked_and_frees_its_slot`（`cancelled`）；`tests/integration/test_usage.py`；`web/src/pages/RunPage.test.tsx`「被中止的那一輪」；e2e `agent`「被防護中止的那一輪：從「步驟」看到每一步的數字」 |
| 防護各觸發一次並留下說明 | `test_agent_api.py::TestGuards`：重複（警告、擋下給模型的話與第 4 次中止的說明，**本票補斷言**）、每輪呼叫上限、token 上限（**本票補說明文字**）、乒乓、無進展、截斷；`TestTheCircuitBreaker`；`test_agent_web_search.py::TestTheSearchLimit`；`card_undecided`（`TestTheFrontendIsOnlyATrigger`）；預設值（20 次、400K / 30K、2 / 3 / 4、12,000 字、網搜 5、斷路器 5 次 15 分鐘）**本票補**：`tests/unit/test_agent_guards.py::test_the_default_limits_are_the_ones_in_the_plan`；UI：`AgentPanel.test.tsx`、e2e `agent`「停下的那一輪」「provider 連續出錯 5 次」 |
| 一般使用者在側面板碰到的是同一道門禁 | 門禁本身：`test_agent_api.py::TestWhoCanUseWhat::test_a_user_conversation_cannot_reach_admin_commands`（模型叫管理員的工具什麼都沒跑）、`test_agent_cards.py::TestWhoMayPress`、`test_proposals.py::test_a_person_cannot_propose_what_only_an_admin_may_do`、`tests/unit/test_agent_tools.py::test_a_user_sees_only_the_commands_meant_for_users`。面板實跑（**本票補**）：e2e `agent`「一般使用者也用得到側面板」——`deckhand` 問「為什麼沒入庫」得到結論；它斷言的 403 是用量頁那一道，面板的門禁仍由上面的整合測試守 |
| 沒設 provider 時與 M4 相同 | `test_agent_api.py::test_nothing_runs_while_ai_is_off`、`test_agent_slash.py::test_commands_need_ai_turned_on`；e2e `settings`「AI 沒設定：側面板只說明」（**本票補**，AI 從沒設定過的 `healthy`）；全套 pytest、vitest、前端 e2e 照舊綠（下面） |

### 2026-10-28 asyncio「Task was destroyed but it is pending」（協調者第 3 點）

**產品問題**，不是演練伺服器的關閉順序：`berth/api/events.py::_signals` 停在 `asyncio.wait((waiting, stopping))`，分頁關掉時 sse-starlette 取消那個 task，`asyncio.wait` 被取消不會取消它在等的 future，`finally` 只收了 `stopping`，`queue.get()` 的 task 一直 pending，GC 回收時印那一行（`PYTHONASYNCIODEBUG=1` 抓到的建立位置是 `events.py` 的 `asyncio.ensure_future(queue.get())`）。每關一個分頁漏一個，e2e 收尾一次斷很多條連線所以看起來像關機時才有；連線還開著時 SIGINT 走 `shutdown_event` 那條，不漏。紅燈 `tests/unit/test_event_stream_teardown.py::test_a_closed_tab_leaves_no_pending_queue_getter`，修在 `finally` 一併取消 `waiting`（commit 46b0eef0）。（真模型實跑的 log 有沒有這一行不能當證據：要等 GC 回收才印。）另看到 SSE 還連著時 SIGINT，uvicorn 印一段 lifespan `receive_queue.get()` 的 `CancelledError`（沒有「Task was destroyed」），與這個無關，沒追。

### 2026-10-28 code-review（`fd346e10...HEAD`）

已處理：`scripts/experiments/README.md` 登記新腳本；`docs/development.md` 兩條 e2e 流程補上新測試；`KeepingQbittorrent` docstring 指明文件；拿掉沒人用的暫存目錄 fallback；`tool_results` 共用；預設值測試補斷路器；驅動腳本的標記欄改名「出現標記字樣」（只看字樣、分不出整季）並收進卡片恢復之後的回覆，找不到卡片時不送恢復；plan「分批入庫」收窄成「送出」。

未處理（判斷題）：`FakeClientFactory` 五支方法各自 `if self._live`（Repeated Switches，演練伺服器，五處都短，不抽）；`m5_acceptance_scenarios.py` 與 prototype 那支的 `card_md` / `render` 相似（實驗腳本一次性保留，prototype 那支打的是另一個 API）；`notify.spec.ts`、`settings.spec.ts` 舊測試手寫 `'deckhand'`，沒改成 `CREW`。

### 2026-10-28 真模型實跑的發現（給協調者）

1. **`series-mapping` 的整季標記只被部分遵守**：無職轉生兩邊都只標 Part 2 那一列，S02 前半（實際 E01–E12、第 0 集在 Specials）沒標也沒提第 0 集；Re:Zero anthropic 只標第 2 季那列（說明文字說整季）、openai 漏第 1 列；HxH anthropic 三季都標、openai 漏 S1。比較像 skill 措辭不夠硬（「整季」沒說成「那一季的每一列」），要改 skill 再量一次。
2. **anthropic 接口不問 Route**：兩條電視 Route、沒有預設時 skill 要它問，Re:Zero 與宝石の国它都自己選了 Anime（事後有說、卡片上看得到）；openai 接口照規則問。
3. **Mikan 訂閱的回填同集多版本**：同一字幕組同一集的繁日、簡日都送了（openai S1 8 個、anthropic S6 也有），要確認是設計（brief §15 同組並存）還是回填該擇一。
4. 重啟後 `id_not_from_results`（只剩在壓縮摘要裡的 id）與 `source_expired`（來源快取在記憶體）各擋一次，模型重查後成功；守法照設計，代價是多查一輪。

### 2026-10-28 驗證輸出

真服務 e2e（`uv run --env-file .env python -m tests.e2e.stack`；第一次在 `up` 拉 image 時網路斷掉、測試沒開始，補拉 `jellyfin:version-12.1ubu2604` 與 `python:3.13-alpine` 後重跑）：

```
tests/e2e/test_1_m1_pipeline.py ......                                   [ 21%]
tests/e2e/test_2_m15_library.py ......                                   [ 42%]
tests/e2e/test_3_m2_repair.py .....                                      [ 60%]
tests/e2e/test_4_m3_rss.py .......                                       [ 85%]
tests/e2e/test_5_m4_notify.py ....                                       [100%]
======================= 28 passed in 2707.79s (0:45:07) ========================
```

其餘：`uv run pytest` 5159 passed、1 skipped、28 deselected；`pnpm -C web test --run` 123 files、2295 passed；`pnpm -C web e2e` 62 passed（2.9m）；`pre-commit run --all-files` 全過。真模型費用合計約 $0.20（Berth 自己的記帳）。
