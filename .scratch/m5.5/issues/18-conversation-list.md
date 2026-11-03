# 18 — 對話清單

**Status:** ready-for-agent

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

- [ ] 同一帳號換瀏覽器打開面板，接上最近的一段對話（e2e）
- [ ] 「對話」清單與 `/history` 都能切回舊對話；在跑的那一段有標出（e2e＋測試）
- [ ] 按「新對話」後重新整理仍是空白的新對話（e2e）
- [ ] 看不到別人的對話（測試）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新
