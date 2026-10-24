# 16 — M5 驗收

**Status:** needs-info

等使用者提供真 key 做「做什麼」第 2 項的實跑（清單在下面〈真 key 實跑清單〉）；其餘做完（2026-10-24）。

**Blocked by:** 01–15（含 07b）

**讀:** plan §11.6 驗收；brief §17 M5 那一列；progress.md M5 的 session 紀錄與偏差

## 為什麼

逐條對 plan §11.6 的驗收，並用真的 key 端到端跑一次（Anthropic 與 OpenAI 相容各一次）。

## 做什麼

1. 逐條對驗收，每一條指到證明它的測試或實跑紀錄：
   - 側面板「訂閱這部的 Mikan RSS」「這部作品缺的集搜一下並下載」做得到，結果是卡片、撤銷得掉
   - 「加一個索引站」「把這部的 complete 刪掉」停在確認卡
   - `user` 碰不到管理員的命令
   - 照注入指令做的假模型被擋下
   - 用量頁看得到每次呼叫的 tokens 與快取命中率
   - 沒設 AI 憑證時行為與 M4 相同
2. 用真 key 實跑上面的對話（使用者提供 key），記下 tokens 與命中率，確認快取有吃到。Anthropic 與 OpenAI 相容兩種格式各跑一次（第三方端點由使用者提供）。
3. 里程碑收尾的 `mattpocock-skills:code-review`（從 M5 開工的 commit 起）；未處理的發現記到這張的 Comments。
4. PRODUCT.md 的路線圖把 M5 標成完成；CHANGELOG 整理；問使用者要不要發版。

## 驗收

- [x] plan §11.6 每一條驗收都有對應證據
- [ ] 真 key 實跑紀錄附在票上（tokens、命中率）
- [x] 里程碑 code-review 做完
- [x] 全部檢查、pytest、vitest 綠；PRODUCT.md、CHANGELOG、progress.md 已更新（實跑後再補一次）

## 驗收證據（plan §11.6 逐條）

後端是整合測試（假 provider `berth/adapters/ai/fake.py` 照腳本走完整的工具迴圈、API 與資料庫），前端是 vitest 與 playwright e2e（演練伺服器 `DemoChatProvider`）。

1. **「訂閱這部的 Mikan RSS」做得到、是卡片、撤銷得掉**：`tests/integration/test_assistant_subscribe.py::TestSubscribeOnMikan::test_search_pick_a_group_and_subscribe_without_a_confirmation_card`（`Subscribed` 卡、Feed 與 Series 建好、Job 送出、沒有確認卡）；`TestUndo::test_undoing_a_mikan_subscription_stops_it_and_takes_back_what_is_still_downloading`、`test_the_card_and_the_model_both_know_it_was_undone`；`web/src/assistant/SubscribeCards.test.tsx`；e2e `assistant-rss`（「直接訂好、沒有確認卡，卡上撤銷得掉」）。
2. **「這部作品缺的集搜一下並下載」做得到、是卡片、撤銷得掉**：`tests/integration/test_assistant_search_submit.py::TestSubmitRelease::test_missing_then_search_then_submit_and_the_job_moves_on_the_stream`、`test_undo_is_the_inverse_command_and_the_same_release_can_be_sent_again`；`web/src/assistant/SearchAndSubmitCards.test.tsx`；e2e `assistant`（「在作品頁說缺的集搜一下並下載……撤銷得掉」）。
3. **「加一個索引站」停在確認卡，按了才做**：`tests/integration/test_proposals.py::test_adding_an_indexer_stops_on_a_card_and_happens_only_when_confirmed`（確認前 Prowlarr 沒收到任何新增）；`test_conversations_api.py::test_confirming_runs_it_and_the_conversation_reads_the_outcome`；e2e `assistant`（「不可逆的停在確認卡」）。
4. **「把這部的 complete 刪掉」停在確認卡，按了才做**：`test_proposals.py::test_deleting_downloads_stops_on_a_card_listing_the_files_and_rejecting_keeps_them`、`test_confirming_the_deletion_removes_the_downloads_and_keeps_the_library`；e2e 同上。
5. **`user` 碰不到管理員的命令**（走工具迴圈那一層）：`test_proposals.py::test_a_user_is_never_offered_the_administrator_tools`（provider 收到的工具只有三個、硬叫 `add_indexer` 是 `unknown_tool`）；`test_assistant.py::test_a_user_gets_no_admin_tools_and_an_admin_does`、`test_a_user_who_names_an_admin_tool_is_still_refused`；`test_conversations_api.py::TestTheToolsEachPersonGets`；`test_ai_activity.py::test_a_user_cannot_undo_even_their_own_submit`。
6. **照注入指令做的假模型被擋下**（假模型讀到工具結果裡的注入文字、照做、被程式擋）：網址藏在 Mikan 搜尋結果標題裡 → `test_assistant_subscribe.py::TestAddAFeedByUrl::test_a_url_planted_in_search_results_becomes_a_card_and_nothing_is_added`（確認卡 `url_not_from_user`、連都沒連過）；不是這則對話搜出來的 → `test_assistant_search_submit.py::TestInjectedReleases::test_a_release_found_outside_this_conversation_is_refused`、`test_an_id_written_by_the_model_is_refused`；標題寫「送這一筆」但不符比對 → 同 class 的 `test_a_row_that_is_not_this_work_is_refused`（`not_a_match`）、`test_a_row_for_other_episodes_is_refused`（`other_episodes`）；e2e `assistant`（「照標題指令送的被擋下」）。
7. **用量頁看得到每次呼叫的 tokens 與快取命中率**：**本票補**整合測試 `tests/integration/test_ai_usage_api.py::TestAConversationShowsUp::test_each_reply_counts_its_tokens_and_the_cache_it_hit`（兩次對話呼叫 → `GET /api/settings/ai/usage` 依出處、依日、依人都是那兩次的 tokens 與 900 / 2100 的命中率）與 e2e `assistant`「用量頁看得到側面板的對話」（演練的對話每次回報快取讀取 1,800 / 輸入 2,400，頁面總量與「側面板的對話」那一列都是 75%）；算法 `tests/integration/test_ai_usage.py::TestTheHitRate`；畫面 `web/src/pages/AiUsagePage.test.tsx`。逐次回覆的 tokens 在 AI 活動頁（`test_ai_activity.py`）。
8. **沒設 AI 憑證時與 M4 相同**：`test_assistant.py::test_nothing_is_sent_while_ai_is_not_set_up`（provider 一個請求都沒收到）；`test_conversations_api.py::TestNotSetUp::test_nothing_is_sent_and_the_status_says_why`；`web/src/assistant/AssistantPanel.test.tsx`「沒設好 AI」；**本票補** e2e `settings`「沒設 AI 時：側面板只說怎麼開、沒有輸入框，也沒有 AI 活動」；M4 的 e2e 全在沒設 AI 的情境裡跑。

## 里程碑 code-review（`v0.3.0...HEAD`，兩軸各一個 opus 子代理）

**處理了的**：

- **撤銷一次「本來就在了」的送單會刪掉原有的 Job**（Spec 軸，已證實）：票 12 的 `created: false`、票 11 的對話撤銷、票 14 的活動頁疊起來才出現——AI 再送一次別人（或人手動）送過的同一筆，回 `created: false` 什麼都沒做，撤銷卻照 hash 刪掉那一筆。`Undo.did_nothing`（`registry.nothing_to_undo`）：撤銷回 `not_undoable`、活動頁新 `ActivityUndo.NOTHING_DONE`、送單卡 `created` 為 false 不給撤銷鍵。測試 `test_assistant_search_submit.py::…::test_undoing_a_send_that_found_the_job_already_there_leaves_that_job_alone`（改前紅：撤銷 200、Job 404）；`test_ai_activity.py` 那一條原本就是兩人送同一筆，改成一般使用者先送，`not_allowed` 照樣被守。
- **只能聊天的模型自己寫出工具呼叫照樣執行**（Spec 軸）：只執行這一輪給了模型的工具，其餘 `unknown_tool`。`test_assistant.py::test_a_chat_only_model_that_calls_a_tool_anyway_is_refused`（改前紅）。
- **`add_feed` 的 Feed 名由模型寫**（Spec 軸，plan「Feed 名與字幕組名取 Berth 讀到的那一份」）：輸入拿掉 `name`，Berth 依網址取。`test_assistant_subscribe.py::TestAddAFeedByUrl::test_the_feed_name_is_berths_not_the_models`（改前紅）。
- plan §11.6 的 `deletion.delete_job`（兩處）改 `withdraw_job`、`invoke` 改 `resolve`（兩軸都提）；工具說明與 `submit_guard` 的 `release` 照 CONTEXT.md 改（發佈名照舊可用）；`AiActivityPage.tsx` 疊在一起、互相矛盾的兩段 JSDoc 留下對的那一段。

## 真 key 實跑清單（第 2 項，等使用者）

在演練伺服器上用真的 provider：`BERTH_AI_REAL=1 uv run python scripts/fake_setup_server.py --scenario assistant`（另一次 `--scenario assistant-rss`），其他服務是替身；key 存在暫存目錄的 SQLite，不進 git。每種格式：設定 → AI 填好、「儲存並測試」，再在側面板跑驗收的四句（`/media/tv:120089` 說缺的集搜一下並下載、`assistant-rss` 的 `/media/tv:262000` 說訂閱、加索引站、刪 complete），最後看 `/settings/usage`。

| # | 看什麼 | 來源 | 格式 |
| --- | --- | --- | --- |
| 1 | 同時送 `Authorization: Bearer` 與 `x-api-key` 官方收不收 | brief §20.24 票 07 第 1 條 | Anthropic |
| 2 | 頂層 `cache_control` 與 `anthropic-version`：官方第二次呼叫起 `cache_read` > 0；第三方 Anthropic 相容端點是忽略還是 400 | 票 07 第 2 條 | Anthropic |
| 3 | 現役模型預設回不回 `thinking` block，回的話下一輪原樣帶回沒被拒 | 票 07 第 3 條 | Anthropic |
| 4 | 官方 OpenAI 不送 `reasoning_effort` 時工具呼叫能不能用 | 票 07b 第 4 條 | OpenAI 官方 |
| 5 | 探針 256 個輸出 tokens 對推理模型夠不夠（不夠會判 `no_reply`） | 票 07b | OpenAI 推理模型 |
| 6 | `prompt_tokens` 含不含快取讀取（不含的話命中率 > 100%，現在的保險是記「不知道」並寫 log） | 研究第 7 條 | OpenAI 相容 |
| 7 | Ollama 收到 `tool_choice` 是忽略還是 400（目前不送） | 研究第 5 條、票 07b | Ollama（有的話） |
| 8 | OpenRouter 的 403 分類、`id` 比名字晚到時的 `call_{index}` | 票 07b Comments | OpenRouter（有的話） |
| 9 | 整條對話第一次對真 provider：串流、工具呼叫、結果卡、確認卡、撤銷 | 票 07、08、09 | 兩種 |
| 10 | 用量頁的 tokens 與命中率，數字記在下面 | 本票 | 兩種 |

實跑完：結論寫回 brief §20.24（把「未實測」改成實測結果），`docs/guide/setup-wizard.md` 那張表的 OpenAI 官方「not yet tried」跟著改。

## Comments

- 2026-10-24 里程碑 code-review **沒處理的**（判斷題與不影響行為的，留給之後碰到那一塊的票）：
  - **關機時取消到一半的回覆不記用量**（Spec 軸）：`ai_calls.call_model` 只在 `AiProviderError` 時記失敗，`AssistantRuns.aclose` 取消串流時已經花掉的輸入沒有一列。plan「沒成的請求也記」字面沒涵蓋取消；要記得先定 `AiFailure` 多一類還是另一欄。
  - **讀存下的工具結果時，舊形狀有三種處理**：`subscribe_guard._read`、`proposals._shown` 讀不回當沒有，`submit_guard._searched` 直接 `model_validate`、讀不回會丟。M5 還沒發版、沒有舊形狀；**`SearchResults` 改形狀之前要收成一份**，否則舊對話裡送單會 500。
  - 「要選 Route」寫兩份（`tools.py` 送單那份不列可選的 Route、訂閱那份會列），三個理由碼（`SubmitRefusal.ROUTE_NEEDED`、`SubscribeRefusal.ROUTE_NEEDED`、`RssRefusal.ROUTE_REQUIRED`）。
  - tokens「不知道」兩種算法：用量頁只加知道的（`ai_usage`），活動頁任一筆不知道整格 `None`（`ai_activity`，票 14 選的，理由在 JSDoc）；`AiActivityPage.tsx` 自己寫 `Intl.NumberFormat`，沒用 `settings/usageFormat.ts`。
  - `ai_activity._arguments` 與 `ToolCall.arguments_object` 同形（票 07 Comments 已提要收成一份）。
  - `ProposalRejectedError`、`UndoRejectedError` 放在 `conversations.py`、收進 `registry.REJECTIONS`，是 `test_registry.py` 的全量掃描逼的，確認與撤銷其實不經過登錄表的 `run` / `apply`。
  - `web/src/assistant/UndoButton.tsx` 的 `JOB_REASONS` 手抄一部分 `jobs.refusal.*`，`tsc` 守不到（同票 10 記的 `LAPSES`）。
  - `subscriptions.unsubscribe` 先查 `UNDOABLE` 再叫自己也會查的 `withdraw_job`；`api/ai.py`、`api/conversations.py`、`api/ai_activity.py` 各一份「門禁後一定有人」的 assert（`api/jellyfin.session_user` 是共用版）；`assistant.py` 的 `title_en` 讀欄位、`tools._titles` 讀 snapshot；`test_assistant_subscribe.py` 重寫了 `ai_ready`、`last_result`。
  - 格式名兩份 i18n（設定頁「OpenAI 相容（Chat Completions）」、用量表「OpenAI 相容」）：語境不同（設定頁要說是哪一支 API、用量表的欄窄），不改。
