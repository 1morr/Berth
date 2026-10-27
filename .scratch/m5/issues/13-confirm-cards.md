# 13 — 確認卡

**Status:** ready-for-agent

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

- [ ] selftest 那 11 步的對應情境都是整合測試（不打網路）
- [ ] 在 `agent` 情境的側面板裡：出卡 → 取消一列 → 確認 → 只送出勾選的列，逐列看得到結果；重新載入之後未決定的卡片還按得下去（playwright 實跑，附截圖）
- [ ] 不是提出者的一般使用者按不到別人的卡（測試）
- [ ] 全部檢查、pytest、vitest 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-27（票 08 留下）：送單卡的來源與 `SourceCache` 對不上（2026-10-27 協調者指出，票 08 補記）。`downloading.add_manual_download` 的輸入是完整的 `JobSource`（下載連結、發佈名、info hash、大小、發佈時間）；`source_id` 是 `POST /jobs` 路由向 `services/sources.SourceCache` 換的，而它在程序內、只記兩小時、Berth 重啟就沒了（plan §6 jobs）。卡片期限是 `PROPOSAL_TTL` 24 小時、要重啟之後按得下去，所以兩條路都不通：存 `source_id`，重啟或兩小時後按下去是 `source_expired`；存整份 `JobSource`，連結帶 Prowlarr 的 API key，`GET /proposals` 原樣回給瀏覽器（違反 M4 票 79）。後者由 `tests/integration/test_proposals_api.py::TestSubmitCards::test_a_submit_card_never_hands_the_download_link_to_the_browser` 證實（`xfail(strict=True)`，修好時會變成 XPASS 而紅，記得拿掉標記）。前者這一張寫不出紅燈：目前沒有任何命令收 `source_id`，換成來源的那一步要由票 13 的工具做。票 13 要決定：把發佈資訊（下載連結、info hash、發佈名、大小、發佈時間）存進 Proposal 的參數，而且下載連結不進 API 回應（例如列表遮掉、或另存在伺服器端欄位）；或讓 `SourceCache` 落地。兩者都要讓來源活得比 `PROPOSAL_TTL` 久，或兩者對齊。

- 2026-10-27 票 19 交接：skills `missing-episodes`、`series-mapping`、`new-season-picks` 等 `downloading.add_manual_download` 進 `services/agent_tools.TOOLS`（還有別的工具，見 `tests/unit/test_skills.py` 的 `PENDING`）。加進去時 `PENDING` 那幾格會紅，照著刪；三份全齊時 skill 自己出現在 instructions。skill 裡送單的 `source` 寫成「從搜尋結果挑的那一筆」，沒有寫死 `source_id` 或 `JobSource`：這張定下形狀之後，確認 `missing-episodes`、`series-mapping`、`new-season-picks` 的那一步說法對得上。
- 2026-10-27 票 18 交接：壓縮在分支 `1morr/t18`（`services/compaction.py`，合併前以那個分支為準）。**歷史形狀**：切點落在帶 `UserPromptPart` 的請求上；切掉的 call 留下的孤兒 `ToolReturnPart`（例如沒按卡就繼續說話時，`ToolDenied` 的結果與新訊息在同一則請求裡）一起拿掉；最後一則回應裡沒有結果的呼叫一定在尾巴（`tests/unit/test_compaction.py`）。自動壓縮在 `ProcessHistory` 裡、每輪第一次模型呼叫之前（`Turn.compact_once`），所以恢復那一輪的 deferred 結果已經在歷史裡、跟著留下的回合走。**驗收第 2 條的整合測試**（`tests/integration/test_agent_slash.py::TestACardSurvivesCompaction`）在這張落地前以 `proposals.execute` 代替對話的恢復：這張做完恢復之後，把它改成經 `POST /agent/chat` 真的恢復（按核准 → 恢復 → 工具結果說已執行），並拿掉 docstring 裡「以 `proposals.execute` 代替」那一句。**`/new` 與「新對話」**不碰舊對話裡還在等的卡片（不標脫離）；`/pending` 列這個人每一段對話裡在等的卡（`here` 標是不是這一段）。要不要在換對話時脫離由這張決定。兩張的 migration（這張的 `d8a4f1c6e273`、票 18 的 `e6b2d9a4c731`）都接在 `c4e7a9d2b158` 之後，後合併的那一張改 `down_revision`。
