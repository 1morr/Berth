# 22 — M5 UI 收尾

**Status:** done

**Blocked by:** 09, 12, 13, 14, 16, 17, 18, 19, 20, 21, 21b, 21c

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

- [x] critique / audit / polish 的分數與處理清單記在 Comments
- [x] 五個面 × 深淺 × 兩種寬度沒有橫向捲動，對比達標（實跑）
- [x] 斷路器開與關的狀態在側面板看得到；「繼續」只出現在可以續的那一則、按過一次就沒了（playwright 實跑，從票 20 搬來）
- [x] 全部檢查、vitest 綠；DESIGN.md、progress.md 已更新

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

### 2026-10-28 session 2（實作、critique / audit / polish）

上一段的「下一步」1–4 都做了，做法照寫的；偏差只有一條：**`ConversationOut.stop` 拿掉**（前端沒用它，說明那一則的 `data-stop` 就說得出最後一輪停在哪），plan §6 與 CHANGELOG 已改。

**功能（做什麼 2、3、5）**
- 停下的說明：串流與重新載入都是一個 `data-stop`（`{turn_id, reason, continuable, note}`）。重新載入時 `_tagged` 給 `model_name == "berth"` 的那一則記號、`dump_messages` 之後換成 `data-stop`；`read_conversation` 一次讀這段對話每一輪的停止原因，只有最後一輪保留 `continuable`。面板畫成 `Notice` `assigned`「停下」，那一則不標「助理」。
- 「繼續」只在最後一則、不在串流中、伺服器說 `continuable` 才畫；送按鈕上的字、body 帶 `continues`；`not_continuable` 時收掉並說一句。按「停止」後輪詢 `GET /agent/conversations/{id}`（8 × 250ms）接回「連線被關掉」那一則。
- 斷路器：面板頂上「暫停」（到 `HH:MM`、自動恢復；管理員多錯誤原文與 AI 設定連結），時間到重問狀態；每一輪結束與 `ai_paused` 拒絕時也重問。`agent.failure.paused` 原本寫「壓縮要等它恢復」（一般訊息被擋也用它），改成通用的一句；「字放回輸入欄」只在真的放回時才說（「繼續」與卡片恢復送不出去時原本也這樣說）。
- 撤銷（使用者選定）：`subscribe_search` 那一行底下連到 `/rss#feed-<id>`（結果被包成 `{result}` 時也認得）。
- 作品頁「為什麼」（使用者選定露出）：「缺」「卡住」旁一顆鍵，按了才問 `why-not?season&episode`，展開一列說結論與下一步。i18n 用 `media.episode.cause`（`why` 會被 `test_reason_codes` 當成解析理由那兩塊表）。
- 「窄版先收起面板」三處（票 21 點名兩處 + 撤銷連結）抽成 `useLeavePanel`。

**critique / audit**（dual-agent：A 設計審查 + audit（opus）、B 偵測器 + overlay（sonnet）；快照 `.impeccable/critique/2026-10-27T19-43-58Z__web-src-agent-agentpanel-tsx.md`）

| 面 | Nielsen | Audit |
| --- | --- | --- |
| 側面板 | 29/40 | 15/20 |
| 確認卡 | 27/40 | 15/20 |
| AI 設定 | 30/40 | 17/20 |
| 用量頁 | 31/40 | 18/20 |
| 步驟頁 | 26/36（H5 n/a） | 16/20 |
| 作品頁「為什麼」 | 25/36（H5 n/a） | 15/20 |

B：CLI 9 檔 0 條；overlay 1280 全部乾淨，390 只有三處中英混排的行尾孤字（AI 設定的 `/anthropic）。`、用量頁的 `demo-model：…` 與 `credit，…`），不改（中文沒有空白可斷，改字只是換一個孤字）。A 實量：六個面 × 深淺 × 1280 / 390 頁面與面板都沒有橫向捲動；新元素對比深色 ≥ 7.7、淺色 ≥ 5.7。

**P1（全修，各有測試或實量）**
1. 助理散文裡的連結是 `TEXT_LINK`（`.label inline-flex`），換行疊字；自動連結把「，但」吃進網址 → 新的 `INLINE_LINK`（`IssueRow`、`JobLink` 原本各有一份同樣的字串，一起改用它），remark 外掛在第一個中日韓字元處切開自動連結（`Markdown.test.tsx` 三條，改前兩條紅）。
2. 被按的鍵消失、焦點掉回 `body`：送出→停止、繼續、確認卡 → 送出/停止那一格記住焦點、換鍵後交給新的那一顆（點到別處不搶）；繼續先把焦點給輸入欄；確認卡改 `busy`（不是 `disabled`），按過之後焦點給 `h3`（`AgentPanel.test.tsx` 兩條、`ConfirmCard.test.tsx` 一條，改前紅；實跑焦點留在「送出」）。
3. 「出自外部來源」是 `blocked-ink` 紅字 → `border-2 border-rule-strong` 的中性標記。
4. 送單卡沒重述資料夾名（票 13 留項）→ 效果底下「資料夾」+ 名稱 + 作品頁那一句「送單成功那一刻就定下來」，同一部作品只印一次（測試改前紅）。
5. 390 寬季表被「為什麼」撐寬（394 / 340）→ 窄版鍵排在色塊下、那一欄 `px-3`；實量 340 / 340。

**polish 順手做的 P2**：後端停下說明的中文空格、沒有工具時的「（-）」、英文單複數（`TestTheStopNoteReads`，改前紅）；數量閘「另外 N 項」與 `externalLead` 的文案（拿掉「單獨就超過的自己一張」這種助理的規則）；「看那一筆下載」只取蓋到這一集的 Job（原本退到整部作品的第一筆）。

**P2 / P3 沒做（記下）**
- 一畫面兩張等人按的卡：兩塊 `assigned`、兩顆黃鍵，加上「送出」是三顆（票 13，**P2**）。最便宜的修法是脫離的卡主要鍵降成 Ghost；要一起想「等卡時送出鍵還黃不黃」。
- `STOP_CHIP`（`RunPage`）與 `STOP_TEXT`（`usage/labels.ts`）兩張表（票 21，**P2**）；面板對出錯與斷路器也畫 `assigned`「停下」，步驟頁畫 `blocked`「出錯」——shape 定的是面板一律 `assigned`（這一輪已經結束），沒改。
- 面板沒聽 SSE `event: proposal`（票 13，**P2**）：另一個分頁按過的卡再按會得到 `proposal_decided` 並重抓，不會做錯，只慢一拍。
- 「費用未知」對自架閘道永遠掛著，390 寬加上「暫停」佔面板約四成高（**P2**）。
- AI 設定頁不讀 `paused_until`：從「暫停」連過去看不到現在暫停中（**P2**）。
- 總覽卡每列重印同樣的作品與 Route（**P2**）；勾選框下的欄位沒縮排（票 13，**P3**）；`executing` 停住的卡沒地方說（票 13，**P3**）。
- 步驟頁 390 寬「合計」單欄約 640px 高、步驟在第二屏（**P2**）；「· 未知」沒說是什麼；中文 `searchesValue` 用了片假名中點（**P3**）。
- 「暫停」那一塊不是一直掛著的 live region；季表展開列的 `aria-live` 跟著內容一起掛上去、多數閱讀器不念（**P3**）。
- `alertText` 的 `where` 旗標（票 21，**P3**，留著）。
- 用量頁「一輪停在哪裡」大多是 0 的列（**P3**）。

**查過不是問題的**：A 看到「缺」的 S02E01 說「停在審核」。直接問替身：五筆 Job 都蓋到那一集——替身的 TMDB 快照只有幾集，`- 08` 猜出的 S01E08 不在快照上，照票 10 的設計退成整部作品（說不出它不是哪一集）。是替身資料的樣子。

**實量（A，修過之後 B 與我再量）**：`documentElement.scrollWidth` 對 `innerWidth`、面板與對話紀錄的 `scrollWidth` 對 `clientWidth`。

| 面 | 深 1280 | 深 390 | 淺 1280 | 淺 390 |
| --- | --- | --- | --- | --- |
| 側面板（頁 / 面板 / 紀錄） | 1280 = 1280 · 414 = 414 | 390 · 390 = 390 | 同深色 | 同深色 |
| AI 設定 | ✓ | ✓ | ✓ | ✓ |
| 用量頁（1280 另量面板開著：表 719 / 720） | ✓ | ✓ | ✓ | ✓ |
| 步驟頁 | ✓ | ✓ | ✓ | ✓ |
| 作品頁「為什麼」 | ✓ | 頁 ✓；季表 394 / 340 → 修後 **340 / 340** | ✓ | 同左 |

對比（深 / 淺）：「停下」色塊 12.35 / 12.35、停下說明 16.2 / 13.31、「繼續」14.18 / 15.02、卡片 `dt` 8.84 / 5.71、工具「完成」8.84 / 5.71、「步驟」7.74 / 6.44、why-not 句子 16.2 / 13.31、「為什麼」14.18 / 15.02，全部 AA 以上。只量了新元素與這幾個面上的既有元素，沒有逐元素全量。斷路器「開 → 關」（到時間自動收掉）由 vitest `asks again once the pause is over` 守；e2e 只跑得到「關 → 開」（暫停 15 分鐘）。截圖在 session scratchpad（沒有進 repo）：e2e 的 `stop-continuable` / `stop-continued` / `paused` 在 `web/test-results/`。

### code-review（`e266b006` 起）

- **Standards**：硬違反一條——作品頁結論句與搜尋 Feed 那一行把 `TEXT_LINK` 放在會換行的句子裡（違反這張票自己加的 DESIGN.md 規則）→ 改 `INLINE_LINK`，DESIGN.md 與 sidecar 兩處跟著改。判斷題改了的：`SeasonList` 自己的 `JobLink` 改用共用的 `jobs/JobLink`；`useLeavePanel` 從 `useNarrow.ts` 搬到 `panelState.ts`；`report(error, true)` 改具名 `{ restored }`；`isSubmit` 後多餘的 `as string`、`proposalRefusalOf` 算兩次、`_with_stop` 先算說明再檢查；輪詢的 8 次 / 250ms 命名並說明。沒改的：`_NOTES` 把格式碎片（`names`、`join`）與停止原因放同一張表（兩種語言各三格，收成 dataclass 不划算）；「暫停」那句是翻譯 + `<time>` + 翻譯（repo 有 8 處同樣拼法、沒有 `Trans` 的先例，中英語序都通）。
- **Spec**：`pickUpStopNote` 在還沒收到這一輪 id 時（`start` 之前就按停止）會接受畫面上已有的上一輪說明、把剛送的那則蓋掉 → 改成只接受還沒畫過的那一輪（`AgentPanel.test.tsx` 一條，改回舊條件會紅）。`ConversationOut.stop` 拿掉沒有問過使用者：它是同一個未發佈里程碑（票 20）加的、只有自己的前端讀過，記在 progress「偏差與決定」並在收尾時告知使用者。驗收證據不足的兩條補在上面（每個面的實量表、斷路器「開 → 關」由誰守）。`INLINE_LINK` 動到 `IssueRow`、`JobLink`（超出五個面）：是同一份字串收成一份，`issues`、`review` 的 e2e 照跑綠。

**document 時找到、沒處理的**：「步驟」連結是 `${TEXT_LINK} text-ink-dim`，`TEXT_LINK` 自帶 `text-ink`，誰贏看 CSS 先後（實量是 `ink-dim` 生效，票 21 留下的）；AI 設定頁在 DESIGN.md 沒有自己的一節；展開列 `colSpan={7}` 比實際最多 6 欄多，瀏覽器照實際欄數收。

### 驗證

- `uv run pre-commit run --all-files`：全部 Passed（ruff、mypy、import-linter、prettier、eslint、knip 與檔案衛生）。
- pytest（`-m "not e2e"`）：5148 passed、1 skipped、28 deselected（11 分 9 秒）。之後只動了 `api/agent._with_stop` 的檢查順序，`test_agent_api.py` 55 passed。
- vitest：123 檔 2295 passed。
- 前端 e2e：`agent`、`agent-390`、`media-downloads`、`media-downloads-390`、`issues`、`review` 19 passed（2.1 分）。

- 2026-10-28 協調者判讀：斷路器「關」（正常）時面板不畫、「開」時畫「暫停」說明，符合「開與關的狀態在側面板看得到」；「開 → 關」的自動收掉只有 vitest（`asks again once the pause is over`）守，e2e 只跑得到「關 → 開」。
