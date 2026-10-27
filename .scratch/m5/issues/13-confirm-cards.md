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
