# 12 — 側面板（tracer：為什麼沒入庫）

**Status:** done

**Blocked by:** 11

**讀:** plan §11.6〈已定〉的串流那一條、〈分段〉第 4 段、§7（前端）；brief §13、§14；`PRODUCT.md`、`DESIGN.md`；`docs/research/m5-prototype-2026-10-27.md`〈形狀〉；`scripts/experiments/m5_agent_chat.html`（只參考行為，不參考樣式）；`web/src/AppShell.tsx`；`docs/development.md`〈UI 的 Fake 後端〉

## 為什麼

M5 第一個看得到的東西：每一頁都叫得出的對話面板，走完唯讀的「為什麼沒入庫」。後面的確認卡、外部資料、壓縮都長在它上面。

## 做什麼

1. **先 `/impeccable shape`**：
   - 側面板在桌面與手機上的樣子（手機是全螢幕的面板）。
   - 怎麼叫出來、跟目前頁面的關係。
   - 訊息、工具呼叫、錯誤、防護停下時的說明各長什麼樣。
   - 輸出 `.scratch/m5/side-panel-shape.md`。
2. **相依**：`ai`、`@ai-sdk/react`，釘當前的 stable，knip 閘門照舊。
3. **實作**：
   - `useChat` 加 `DefaultChatTransport`，只送最後一則。
   - 重新載入頁面時從 `GET /agent/conversations/{id}` 接回來。
   - 一個目前的對話加「新對話」；對話清單不在這張。
   - 工具呼叫收成一行，展開看參數與結果。
4. **安全**：
   - markdown 要消毒。
   - **不載入外部圖片**：圖片網址是常見的外洩通道（brief §14、`docs/research/m5-ai-direction-2026-10-27.md` C4 第 6 點）。
5. **沒設 provider 時**：管理員看到去設定頁的連結；一般使用者看到「管理員還沒設定」。其餘頁面與 M4 相同。
6. **Fake 後端多一個 `agent` 情境**：腳本化的假模型（參考 `scripts/experiments/m5_agent_selftest.py`），UI 驗證與前端 e2e 不需要金鑰；`docs/development.md` 的情境表補一列。
7. i18n zh-Hant 與 en。

## 驗收

- [x] shape 文件在、實作照它
- [x] 在 `agent` 情境問「X 為什麼沒入庫」，得到票 10 的結論分類；重新載入頁面之後對話還在（playwright 實跑，附截圖）
- [x] 回覆裡的外部圖片不會被載入（vitest）
- [x] 沒設 provider 時兩種角色各自看到對的說明（vitest＋實跑）
- [x] 手機寬度沒有橫向捲動（實跑）
- [x] 前端 e2e 加一條側面板的 tracer
- [x] 全部檢查、pytest、vitest 綠；DESIGN.md、CHANGELOG、progress.md 已更新

## Comments

- 2026-10-27 實作（票 12 session）：
  - **shape**：`.scratch/m5/side-panel-shape.md`；使用者選定桌面並排、頁首一顆鍵換頁不關、不送頁面脈絡。截圖在 `12-side-panel/`（`agent-*` 是 e2e 的桌機與 390、`off-*` 是 AI 沒開的管理員 1280 與一般使用者 390）。
  - **偏離 shape**（使用者決定）：停下的說明照票 11 當一般助理文字，「停下」訊息塊的畫法移到票 22（票 20 在改串流）。
  - **code-review 已改**：markdown 改成白名單（task list 的勾選框、註腳拆掉）、沒寫語言的 code block 不再疊行內 code 的底色、輸入欄上限改成 6 行、送不出去的那一句放進一直掛著的 `aria-live`、面板標題不再拿掉焦點環、`conversation_missing` 與 `ai_disabled` 兩條分支補測試、`api/agent.ts` 與 `client.ts` 共用 `responseError` / `CSRF_HEADERS`、讀取與讀不到的外框收成 `PanelStates`、假模型的結論表改用 `WhyNot` 當鍵。
  - **未處理**（判斷後留著）：
    - `ToolCall.TOOL_NAMES` 是工具名 → i18n key 的對照表，後端加一支工具要改四處。留著：repo 的慣例是查表給 `t()` 字面 key（`requestProblem.PROBLEM_TEXT`），`resources.test` 才查得到每個 key 有人用；認不得的工具照原文畫，不會壞。
    - `useNarrow` 的 `(max-width: 63.999rem)` 是手抄 Tailwind 的 `lg`，與 class 裡的 `lg:` 兩份來源。
    - 按「停止」之後，後端存的「連線被關掉」那則說明要重新載入才看得到——串流中與重新載入後的畫面短暫不同，歸票 22（「串流與重新載入要是同一個形狀」）。
    - 送不出去時的標籤是 `RequestFailed` 的「失敗」+「這一則沒送出去：」，shape 已改成這樣寫。
  - **實跑觀察**：e2e 以 `--repeat-each` 加多個 worker 對同一台伺服器跑時，同一個帳號撞到「每人同時一輪」，畫面正確顯示「等一下」；正式設定一台伺服器只跑一條，不會撞。
- 2026-10-27（票 20）：防護停下時串流在說明之後多一則 `data-stop`（`{turn_id, reason, continuable}`），`GET /agent/conversations/{id}` 多 `stop`（同形狀），`GET /agent/status` 回 `enabled` 與斷路器的 `paused_until`（一般使用者也讀得到，沒設 provider 的說明可以用它）。「繼續」按鈕與斷路器的畫面排在票 22；這張做說明那一則的樣子時可以順手留位子，不是驗收。
