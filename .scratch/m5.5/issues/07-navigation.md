# 07 — 導覽收斂

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「導覽收斂」「新番區塊」；brief §13；plan §7（路由表）；ADR-0006；`DESIGN.md`〈Navigation〉；`PRODUCT.md`

## 為什麼

頁首的按鈕太多了（使用者定 2026-10-31）。只動導覽，不動後端邏輯，所有網址不變：Discord 週報連的是 `/weekly/{id}`（`services/deeplink.py`）。

## 做什麼

1. **先 `/impeccable shape`**：頁首、帳號選單、待處理分頁，桌機與手機。輸出 `.scratch/m5.5/navigation-shape.md`。
2. **主導覽**：探索、新番、媒體庫、下載、待處理。外面留助理開關與帳號選單。
   - **新番這張票只給 admin**（使用者定 2026-11-03）：分頁只有「訂閱」（`/rss`，原 RSS 頁）。09 加上時間表分頁之後才對所有人顯示，`/schedule` 從那時才有。
3. **帳號選單**：設定、健康、週報（只有 admin）、語言、登出，上面寫名字與角色。這是 Berth 第一個下拉選單；`web/` 沒有 Radix，先用原生元素，鍵盤與焦點照 `DESIGN.md`〈Navigation〉。
4. **待處理**（只有 admin，帶數字）：頁內兩個分頁「審核」`/review`、「Issue」`/issues`，兩頁仍分開（ADR-0006）。
   - 數字是 `services.waiting.waiting_now` 的件數，用文字標出，不只靠顏色。
   - 多一支 admin 的讀取端點（命令 `Effect.READ`），`/waiting` 進 `api/gate.py` 的 `ADMIN_PREFIXES`，`TestWhoEachEndpointIsFor` 補一列。
5. 文件：brief §13、plan §7 路由表、`DESIGN.md`〈Navigation〉〈Layout〉。

## 驗收

- [ ] 一般使用者的頁首只有探索、媒體庫、下載與帳號選單；管理員多新番（只有「訂閱」分頁）與帶數字的待處理（e2e，桌機與 390px）
- [ ] 舊網址（`/rss`、`/review`、`/issues`、`/settings`、`/health`、`/weekly`）與 Discord 週報的 `/weekly/{id}` 連結都打得開（e2e）
- [ ] 帳號選單用鍵盤打得開、關得掉，焦點回到按鈕（vitest 或 e2e）
- [ ] `/waiting` 對一般使用者 403（`TestWhoEachEndpointIsFor`）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新
