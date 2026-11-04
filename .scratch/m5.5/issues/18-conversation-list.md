# 18 — 對話清單

**Status:** done

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「對話清單」；plan §6〈agent〉、§7〈側面板〉；`CONTEXT.md`（resume 的定義）；`domain.SlashCommand`；`docs/research/assistant-feedback-2026-11-01.md`

## 為什麼

對話 id 只存在瀏覽器裡，換瀏覽器就接不回對話，也沒有地方切回舊對話。

## 做什麼

1. `GET /agent/conversations`：只列自己的，新的在前，上限 50 段；回 id、標題（第一則使用者訊息，截短）、`updated_at`、有沒有在跑。不加標題欄位（沿用 `BusyElsewhere` 的做法）。
2. 面板頁首多一顆「對話」，開清單，選了走現有的 `switchTo`；在跑的那一段標出來。
3. 斜線指令 `/history`（`domain.SlashCommand`，Discord 共用）回同一份清單。**不叫 `/resume`**：`CONTEXT.md` 把 resume 留給 Jellyfin 的繼續觀看。
4. 新瀏覽器自動接上這個人最近的一段：本機沒有 id，或本機的 id 在伺服器上沒有、也不是這個瀏覽器按「新對話」開的（`localStorage` 記一個旗標，第一則訊息送出後清掉）。沒有任何對話才開空白。
5. 文件：plan §6〈agent〉、§7〈側面板〉、`CONTEXT.md`（對話清單）。

## 驗收

- [x] 同一帳號換瀏覽器打開面板，接上最近的一段對話（e2e）
- [x] 「對話」清單與 `/history` 都能切回舊對話；在跑的那一段有標出（e2e＋測試）
- [x] 按「新對話」後重新整理仍是空白的新對話（e2e）
- [x] 看不到別人的對話（測試）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-11-04 實作：`agent.list_conversations`（`Effect.READ`）給 `GET /agent/conversations` 與 `/history`；標題從歷史算（第一則使用者訊息的第一行、40 字截斷），壓縮過的是留下來的第一則。`BusyElsewhere` 改讀同一份清單的標題，前端的 `firstLine` 拿掉（標題規則只在後端一份）。
- 接上最近的一段放在 `Conversation` 的查詢裡（面板開著、AI 開著才問），不放在根路由的 `AgentProvider`：面板關著、沒登入時不打 API。沒有記著 id 的瀏覽器給一個沒有旗標的隨機 id，與「本機 id 不在伺服器上」走同一條路。
- 清單問不到時開空白（不擋著人問），plan §7 寫明；下一次重新整理會再試。
- e2e：同一台替身上前面幾條的對話都在，新的 context 會接上最近的一段，所以 agent 的其他幾條開面板後先按「新對話」（`openBlank`）；第一條是替身上的第一段，不必。
- code-review 未處理：(1) `berth.agent.fresh` 是整個瀏覽器一把、不分帳號：A 按「新對話」沒送出就登出、B 在同一個瀏覽器登入，B 看到空白而不是自己最近的一段（字面符合票的規則，影響小）。(2) 加一支斜線指令要動七處、`slash_out` 的回傳型別與 `SlashOut` 重複一份，既有模式，未改。(3) 結果型別叫 `History`（照指令命名，同 `Skills`、`Pending`），模組裡 history 也指訊息歷史，未改名。
- 已處理：DESIGN.md〈側面板〉補對話清單；「回答中」改 `bg-working`（同工具的「執行中」）、目前這段改用斜線清單同款的左側內線；`TITLE_LENGTH` 改名 `CONVERSATION_TITLE_LENGTH`；「在跑」的判斷與 `read_conversation` 為何一致寫在註解。
- 2026-11-04 合併前（協調者要求）：`pnpm -C web build` 之後跑完整前端 e2e（`pnpm -C web e2e`，全部 project、中途不重 build，開跑前 8484–8534 沒人用）：95 passed、0 failed（3.1m），HEAD `54454de2`。
