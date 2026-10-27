# 13 — 確認卡

**Status:** done

**Blocked by:** 08, 12

**讀:** plan §11.6〈已定〉的確認卡範圍、〈分段〉第 5 段；brief §14〈對話裡的確認卡〉、§20.24；`docs/research/m5-prototype-2026-10-27.md`〈發現〉第 1、3、4、7 點、〈實跑才抓到的問題〉第 1–4 點；`scripts/experiments/m5_agent_chat.py` 的 `_propose`、`_finish`、`_pending_calls`、`_decision`、`api_decide`；`scripts/experiments/m5_agent_selftest.py` 的 11 步

## 為什麼

確認卡是人與 AI 之間最重要的一道閘。它不是 UI 問題，而是狀態機：要能持久化、會過期、綁住參數、限定誰能按、防重放、重啟之後還按得下去。prototype 把這些走過一遍，也抓到四個實跑才看得到的坑。

## 做什麼

1. **後端**：
   - 要人確認的命令（票 02 的規則），在工具裡先跑 `validate`；不通過就把理由回給模型，不出卡。
   - 通過的建 Proposal（票 08），丟 `ApprovalRequired`。
   - 恢復時參數用 `ToolApproved(override_args=Proposal 存的參數，照勾選過濾)`；前端送來的 approval 只當觸發。
   - **確認後的工具結果明說已核准、已執行**（實測：模型拿到裸結果會說「卡片已出，等你按」）。
   - **待確認的呼叫要找「最後一則模型回應裡還沒有結果的」**：平行呼叫時，別的工具的結果排在它後面。
   - 沒按就繼續說話：卡片標成脫離，`ToolDenied` 說明它仍然有效。之後再按由伺服器直接執行，下一輪的 instructions 帶上結果。
2. **前端**：
   - 卡片由命令的結果型別決定，不由模型決定。
   - 單項卡列欄位；總覽卡逐列可勾。
   - 顯示效果（不可逆、會送出 torrent、會連到新位址）與過期時間。
   - 按了之後逐列顯示結果（會部分成功）。
3. **第一個寫入工具**：`downloading.add_manual_download`（送單），讓這張自己就是一條端到端的路；其餘寫入在票 14。
4. 把 selftest 的生命週期搬成正式的整合測試：
   - 出卡、重啟、偽造核准被擋、部分勾選、用伺服器存的參數。
   - 脫離後再按、平行呼叫、壓縮之後卡片還在（壓縮在票 18；這張先守住歷史形狀）。

## 驗收

- [x] selftest 那 11 步的對應情境都是整合測試（不打網路）
- [x] 在 `agent` 情境的側面板裡：出卡 → 取消一列 → 確認 → 只送出勾選的列，逐列看得到結果；重新載入之後未決定的卡片還按得下去（playwright 實跑，附截圖）
- [x] 不是提出者的一般使用者按不到別人的卡（測試）
- [x] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-27（票 08 留下）：送單卡的來源與 `SourceCache` 對不上（2026-10-27 協調者指出，票 08 補記）。`downloading.add_manual_download` 的輸入是完整的 `JobSource`（下載連結、發佈名、info hash、大小、發佈時間）；`source_id` 是 `POST /jobs` 路由向 `services/sources.SourceCache` 換的，而它在程序內、只記兩小時、Berth 重啟就沒了（plan §6 jobs）。卡片期限是 `PROPOSAL_TTL` 24 小時、要重啟之後按得下去，所以兩條路都不通：存 `source_id`，重啟或兩小時後按下去是 `source_expired`；存整份 `JobSource`，連結帶 Prowlarr 的 API key，`GET /proposals` 原樣回給瀏覽器（違反 M4 票 79）。後者由 `tests/integration/test_proposals_api.py::TestSubmitCards::test_a_submit_card_never_hands_the_download_link_to_the_browser` 證實（`xfail(strict=True)`，修好時會變成 XPASS 而紅，記得拿掉標記）。前者這一張寫不出紅燈：目前沒有任何命令收 `source_id`，換成來源的那一步要由票 13 的工具做。票 13 要決定：把發佈資訊（下載連結、info hash、發佈名、大小、發佈時間）存進 Proposal 的參數，而且下載連結不進 API 回應（例如列表遮掉、或另存在伺服器端欄位）；或讓 `SourceCache` 落地。兩者都要讓來源活得比 `PROPOSAL_TTL` 久，或兩者對齊。
- 2026-10-27（第一個 session 中斷，額度用完；還沒寫程式碼）**查證過的事實與擬定的設計**，下一個 session 從這裡接：
  - pydantic-ai 2.62：`DeferredToolResults` 可與新的 user prompt 同一輪給（`_agent_graph._handle_deferred_tool_results` 直接進 `CallToolsNode`，prompt 接在工具結果後）；`ToolApproved.override_args` 只換傳進工具的參數，**不改歷史裡的 `ToolCallPart`**；`dump_messages` 的 `approval.id` 就是 `tool_call_id`。
  - ai 7 前端：恢復（最後一則是助理、`addToolApprovalResponse` + `lastAssistantMessageIsCompleteWithApprovalResponses`）時串流接在最後一則助理訊息上；**但沒按卡就送新訊息時，伺服器對舊 tool call 送的 `tool-output-*` chunk 會讓前端丟 `No tool invocation found`**（`process-ui-message-stream.ts` 的 `getToolInvocation` 只找當前訊息）——`api/agent._relay` 要濾掉舊 call id 的 chunk。
  - 擬定：①核准一律在 `decide` 當場由伺服器執行（改票 08「在對話裡的只記決定」），恢復只把 Proposal 的逐列結果包成 `{"approved_by_user": true, "executed": true, ...}` 交給模型——消掉「核准了、恢復失敗就卡在 approved」（票 08 Comments）；override_args 因此不需要，記偏差。②migration：`proposals.tool_call_id`（unique、nullable）與 `detached_at`；下一輪 instructions 只列 `detached_at` 不為空的卡（快取較穩），在 `open_turn` 算一次。③送單卡：模型端工具收 `{rows: [{source_id, media_id, route_id}]}`，提出時向 `executor.sources` 換成 `JobSource` 存進 Proposal（重啟後按得下去；jobs 表本來就存 `source_url`），API 回應遮掉：`JobSource.url` 標 `Annotated[str, Private]`，`proposals._view` 照輸入模型遞迴去掉 → 拿掉 `test_proposals_api` 的 strict xfail。④哪些工具出卡照規則 `needs_person or Flag.DOWNLOADS`，不列清單；`guard_tool` 接 `ApprovalRequired` 記新的 `AiToolOutcome.PROPOSED`；`output_type=[str, DeferredToolRequests]`，停在卡上記新的 `AiStopReason`。⑤`open_turn` 收 `text=None` 為恢復：待確認的卡還沒決定 → 新的 `AgentRefusal.CARD_UNDECIDED`（409）；有新訊息 → `detach` + `ToolDenied`（說明仍有效）；rejected / expired / 不見了 → `ToolDenied`。⑥`Turn._kept`：有待確認呼叫而 prefix 空時不接說明、原樣存歷史（否則 tool_use 後面接文字，provider 拒收）。⑦端到端要模型拿得到 `source_id` 與 Route id：考慮把 `search.search_torrents`（已在登錄表、`audience=user`）先加進 `TOOLS`；Route id 的來源（票 14 的 Route 清單工具）待定。⑧前端卡片：`api/proposals.ts`（查詢與決定）、`agent/ConfirmCard.tsx`，作品名與 Route 名用 `mediaQueryOptions(media_id)` 的 `title` 與 `routes`；Fake 後端 `agent` 情境的腳本加送單路徑。
- 2026-10-28 完成（第二個 session）。上一則的擬定照做，改了兩處：⑥ 沒按卡就繼續說話時不走 `deferred_tool_results`，由伺服器替那幾個呼叫補上結果（`agent._closing`，理由見 progress.md 偏差）；`tool_call_id` 不唯一（code-review）。⑦ 定為 `search.search_torrents` 加新命令 `media.route_choices`。驗收的對應：selftest 11 步 → `tests/integration/test_agent_cards.py` 開頭的對照；playwright → `web/e2e/agent.spec.ts` 的送單卡那一條，截圖 `13-confirm-cards/agent-card.png`、`agent-confirmed.png`（390 寬各一張）；非提出者 → `TestWhoMayPress`。
- 2026-10-28 code-review 已改：plan §11.6 / brief §20.24 的 `override_args` 舊說法與新的〈確認卡的恢復〉、`tool_call_id` 改不唯一、勾選排序照數字（原本 `[10, 2]` 照字典序）、`_approval` / `_closing` 共用 `_why_not_done`、恢復失敗與送出共用 `report`、i18n 去型別斷言、`noqa` 補原因、`_prompt_text` 改名、票 14 註明已做的兩支。未處理，留給後面的票：
  - **票 22**：平行的兩張卡會在同一屏畫出兩塊 `assigned` 與兩顆主要鍵（「同一屏一顆 assigned 主鍵」）；總覽卡的欄位沒有縮排到勾選框標籤底下；送單卡沒有重述會被寫死的資料夾名（`SubmitAction` 有，plan §5）；面板沒聽 SSE 的 `event: proposal`（另一個分頁按了，這一頁要等下一輪答完或重新載入才更新）。`executing` 停住的卡仍沒有地方說（票 08 Comments）。
  - **票 14**：前端照命令名分派卡片畫法（`RowBody`、`COMMAND_TITLES`、拒絕理由那一組句子）與後端 `_CARD_INPUTS` 是同一件事的幾處，加新的卡片命令時一起補（票 14 已註明）。
  - `Turn.propose_card` / `card_result` 是 `services` 裡公開的 `async def` 但沒有 `@command`：與既有的 `Turn.run_tool` 同一種（方法，`test_command_marks` 只掃模組層），沒改。
- 2026-10-27 票 19 交接：skills `missing-episodes`、`series-mapping`、`new-season-picks` 等 `downloading.add_manual_download` 進 `services/agent_tools.TOOLS`（還有別的工具，見 `tests/unit/test_skills.py` 的 `PENDING`）。加進去時 `PENDING` 那幾格會紅，照著刪；三份全齊時 skill 自己出現在 instructions。skill 裡送單的 `source` 寫成「從搜尋結果挑的那一筆」，沒有寫死 `source_id` 或 `JobSource`：這張定下形狀之後，確認 `missing-episodes`、`series-mapping`、`new-season-picks` 的那一步說法對得上。
- 2026-10-27 票 18 交接：壓縮在分支 `1morr/t18`（`services/compaction.py`，合併前以那個分支為準）。**歷史形狀**：切點落在帶 `UserPromptPart` 的請求上；切掉的 call 留下的孤兒 `ToolReturnPart`（例如沒按卡就繼續說話時，`ToolDenied` 的結果與新訊息在同一則請求裡）一起拿掉；最後一則回應裡沒有結果的呼叫一定在尾巴（`tests/unit/test_compaction.py`）。自動壓縮在 `ProcessHistory` 裡、每輪第一次模型呼叫之前（`Turn.compact_once`），所以恢復那一輪的 deferred 結果已經在歷史裡、跟著留下的回合走。**驗收第 2 條的整合測試**（`tests/integration/test_agent_slash.py::TestACardSurvivesCompaction`）在這張落地前以 `proposals.execute` 代替對話的恢復：這張做完恢復之後，把它改成經 `POST /agent/chat` 真的恢復（按核准 → 恢復 → 工具結果說已執行），並拿掉 docstring 裡「以 `proposals.execute` 代替」那一句。**`/new` 與「新對話」**不碰舊對話裡還在等的卡片（不標脫離）；`/pending` 列這個人每一段對話裡在等的卡（`here` 標是不是這一段）。要不要在換對話時脫離由這張決定。兩張的 migration（這張的 `d8a4f1c6e273`、票 18 的 `e6b2d9a4c731`）都接在 `c4e7a9d2b158` 之後，後合併的那一張改 `down_revision`。
- 2026-10-28 合併 main（票 19、20）：`search.search_torrents`、`downloading.add_manual_download` 進了 `services/agent_tools.TOOLS`，`tests/unit/test_skills.py` 的 `PENDING` 刪了那兩格。skills 選 Route 的步驟寫的是 `media.read_media`（仍在 `PENDING`，票 14）；這張另外加了只回 Route 的 `media.route_choices`，票 14 決定 skill 用哪一支。
- 2026-10-28 票 18 合併 main 之後：上面票 18 交接裡「驗收第 2 條改成真恢復」已由票 18 做完（`TestHistoryShape::test_compact_then_confirm_and_the_resumed_turn_runs_as_usual`，取代手動砍歷史頭部的那一條）；migration 的接法也由票 18 改（`e6b2d9a4c731` 接在 `d8a4f1c6e273` 之後）。
