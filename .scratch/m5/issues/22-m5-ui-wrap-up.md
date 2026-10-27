# 22 — M5 UI 收尾

**Status:** ready-for-agent

**Blocked by:** 09, 12, 13, 14, 16, 17, 18, 19, 20, 21, 21b

**讀:** CLAUDE.md〈UI〉；`PRODUCT.md`、`DESIGN.md`；M4 票 132（上一次收尾的做法）；票 12–21 的 Comments 裡留給收尾的 UI 項

## 為什麼

每個里程碑的 UI 收尾前，都要跑 critique、audit、polish。M5 新增的面：側面板、確認卡、設定頁的 AI 分頁、用量頁、步驟頁。

## 做什麼

1. 依序跑 `/impeccable critique` → `audit` → `polish`。範圍是上面五個面，每個面都看深淺色、1280 與 390 寬度、鍵盤操作。
2. 票 12–21 的 Comments 裡標了「收尾」的 UI 項逐條處理或歸類。
3. 決定 Media 詳情頁要不要露出票 10 的「為什麼沒入庫」：只有使用者會在那裡找答案才露出。
4. 設計系統有變就 `/impeccable document` 更新 `DESIGN.md`。
5. **票 20 搬過來的（收尾）**：側面板的兩塊 UI：斷路器開與關的狀態（讀 `GET /agent/status` 的 `paused_until`，一般使用者也看得到；管理員另有 `pause_error` 說是什麼錯）、防護停下時的「繼續」（`data-stop` 或對話的 `stop` 裡 `continuable` 是真才畫；按下去送一則按鈕上的字、body 帶 `continues: <turn_id>`；`not_continuable` 時收掉按鈕）。票 20 做的時候側面板（票 12）還沒有，後端與測試在票 20（2026-10-27 使用者決定）。

## 驗收

- [ ] critique / audit / polish 的分數與處理清單記在 Comments
- [ ] 五個面 × 深淺 × 兩種寬度沒有橫向捲動，對比達標（實跑）
- [ ] 斷路器開與關的狀態在側面板看得到；「繼續」只出現在可以續的那一則、按過一次就沒了（playwright 實跑，從票 20 搬來）
- [ ] 全部檢查、vitest 綠；DESIGN.md、progress.md 已更新

## Comments

- **收尾**（票 12，2026-10-27 使用者）：防護停下的說明在側面板上要畫成 Berth 說的，不是助理文字——`Notice` 的 `assigned` 色塊「停下」+ 後端那一句（哪一條、做到哪）；`assigned` 不是 `blocked`：這一輪已經結束，要人決定換個問法或再問。串流與重新載入（`GET /agent/conversations/{id}`）要是同一個形狀。票 12 沒改串流（票 20 在做串流裡的停止資料，兩邊同時改會撞），等票 20 定下形狀後在這張接。畫法見 `.scratch/m5/side-panel-shape.md`〈面板結構〉。
- **收尾**（票 12 code-review）：按「停止」之後，後端存的「這一輪停下來了：連線被關掉」只在重新載入後出現，串流中的畫面看不到——與上一條同一件事（串流與重新載入同一個形狀）。
- **收尾**（票 21）：用量頁（`/settings/usage`）與步驟頁（`/agent/runs/$runId`）一起進 critique / audit / polish。code-review 留下的判斷題在票 21 的 Comments（兩張停止原因的表、`alertText` 的 `where` 旗標、「窄版先收起面板」重複兩處）。用量頁的兩張表是全站第一個 container query（`@container` + `@2xl:`），DESIGN.md〈AI 用量頁與每輪步驟頁〉記了理由。

- 2026-10-27 票 14 交接：**側面板直接做的寫入沒有撤銷入口**。plan §11.6〈確認卡範圍〉「其餘可逆的直接做並給撤銷」：現在唯一直接做的是 `rss.subscribe_search`（建一條搜尋 Feed，反向是不可逆的 `rss.delete_feed`，要確認卡）。收尾時決定撤銷長什麼樣（工具那一行旁邊的「撤銷」出一張刪 Feed 的卡，或只連到 RSS 頁那一列）。另外：卡片上「出自網頁」的標記與卡片層級那一句（`agent.card.externalLead`）、數量閘的「另外 N 項」那一句是票 14 的初版畫法，一起 critique。

### 2026-10-28 session 1（只調查與定案，程式碼還沒動；額度用完中斷）

**使用者定案**
- `rss.subscribe_search` 的撤銷入口：工具那一行旁一個連結到 `/rss#feed-<id>`（`FeedSection` 已有錨點、`RssPage` 有 `useHashTarget`）。搜尋 Feed 從 `primed_at = NULL` 開始，本來就要到 RSS 頁選第一輪；刪除在那裡、有原本的確認。
- Media 詳情頁**露出**「為什麼沒入庫」：季表「缺」「卡住」那一格可展開，讀 `GET /media/{id}/why-not` 顯示結論那一句。
- 測試接縫（五個）：① `tests/integration/test_agent_api.py`：串流的停下說明是一個 `data-stop`（帶 `note`），重新載入是同一個 `data-stop`，`continuable` 只有最後一輪是真；② `AgentPanel.test.tsx`（假 fetch）：「停下」`Notice`、「繼續」只在最後一則、送出帶 `continues`、按過就沒了、`not_continuable` 收掉；暫停橫幅；按「停止」後接回說明；③ `ToolCall` 測試：`subscribe_search` 完成後有連結；④ 季表測試：展開讀 why-not；⑤ e2e `agent.spec.ts`：繼續只按得到一次、斷路器開與關、重新載入同形狀（假模型多一句「provider 壞了」丟 `ModelHTTPError` 503；這條放檔案最後，暫停 15 分鐘會擋後面的流程）。

**下一步的做法（已查過程式碼）**
1. 後端（`berth/api/agent.py`）：`_relay` 遇到 `ErrorChunk` 不再送 text 三連，只送 `DataChunk("data-stop", {turn_id, reason, continuable, note})`；`TurnStopOut` 多 `note`。`get_conversation`：`_tagged` 給 `model_name == "berth"`（`services/agent._NOTE_MODEL`）的那則回應加一個內部 metadata 標記，`dump_messages` 之後把那一則的 text part 換成同形狀的 `data-stop` 並拿掉標記（`dump_messages` 一則 `ModelResponse` 一則 UIMessage、metadata 照抄）。每一輪的停止原因要從 `ai_runs` 依 `conversation_id` 一次查（`read_conversation` 回 `stops: dict[run_id, TurnStop]`），只有最後一輪保留 `continuable`。`ConversationOut.stop` 拿掉（前端沒用），測試的 `stop_of` / `streamed_text` / `last_assistant_text` 改讀 `data-stop`。
2. 前端 `Conversation.tsx`：`Message` 畫 `data-stop` 為 `Notice signal="assigned"`「停下」+ `note`；「繼續」= 最後一則 && `continuable` && 不在串流 → `sendMessage({text: t(...)}, {body: {continues}})`（`agentTransport` 的 `prepareSendMessagesRequest` 要把 `body` 併進去，先查 ai 7 的型別）；409 `not_continuable` 時記下這個 turn、收掉按鈕。按「停止」後 `sendMessage` 回來，輪詢 `readConversation`（約 8 次 × 250ms）到最後一則是這一輪的 `data-stop` 再 `setMessages`。
3. `AgentPanel.tsx` `PanelBody`：`paused_until` 有值時一塊 `Notice assigned`「暫停」（到幾點、自動恢復；管理員加 `pause_error` 原文與 `/settings/ai` 連結），計時到 `paused_until` 重問狀態；每輪結束（`status` ready/error）與 `ai_paused` 拒絕時 invalidate `agentStatusQueryOptions`。
4. 之後才跑 critique / audit / polish（側面板、確認卡、設定 AI 分頁、用量頁、步驟頁，加上新的作品頁 why-not），並逐條歸類票 13（平行兩張卡兩顆主鍵、總覽卡縮排、送單卡沒重述資料夾名、沒聽 `event: proposal`、`executing` 停住的卡）、票 14（「出自外部來源」標記與「另外 N 項」那句）、票 21（`STOP_CHIP`/`STOP_TEXT` 兩張表、`alertText` 的 `where`、「窄版先收起面板」重複兩處）的留項。
