# 07 — 導覽收斂

**Status:** done

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

- [x] 一般使用者的頁首只有探索、媒體庫、下載與帳號選單；管理員多新番（只有「訂閱」分頁）與帶數字的待處理（e2e，桌機與 390px）
- [x] 舊網址（`/rss`、`/review`、`/issues`、`/settings`、`/health`、`/weekly`）與 Discord 週報的 `/weekly/{id}` 連結都打得開（e2e）
- [x] 帳號選單用鍵盤打得開、關得掉，焦點回到按鈕（vitest 或 e2e）
- [x] `/waiting` 對一般使用者 403（`TestWhoEachEndpointIsFor`）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新

## Comments

- 2026-11-04 件數各歸各頁（使用者定）：待處理＝審核＋Issue、待綁定掛在新番與訂閱分頁；三格加總等於 Discord 的 N，`tests/integration/test_notify_waiting.py` 守。偏差記在 progress.md。
- `/issues` 的標題改成「Issue」、`/rss` 的標題改成「訂閱」：「待處理」「新番」留給區塊，分頁名與頁名一致。
- 窄版收起副標（實跑 390 時頁首變三列），寫回 shape。
- 帳號選單是 disclosure（APG Disclosure Navigation Menu），不是 `role="menu"`。
- code-review 已處理：`Esc` 多餘的 `stopPropagation`、動作後件數不失效（改成 `router.ts` 的 `recountAfterActions`）、觸發鍵展開與當前同一個樣子（改成只在選單頁上畫當前並掛 `aria-current="true"`）、`countedName` 走不到的分支、英文「Waiting, 3 waiting」、`waiting_counts` 改用 `Counter`；補測新番只有訂閱分頁、`/review` 上 `aria-current="page"`。
- code-review 未處理：
  - 區塊的設定散在 `sections.ts`、`SectionLink` 的 `to` 型別、`SectionTabs`、`AppShell` 四處（Shotgun Surgery）。票 09 加 `/schedule` 時收成一個區塊物件（`to`、`pages`、分頁、件數怎麼算），一起改。
  - `SectionTabs` 的 `Tab` 與 `SectionLink` 形狀相近，但一個用 `NAV_LINK` 的 `data-status`、一個自己算區塊當前，先不合。
  - 焦點從選單最後一項 Tab 到瀏覽器介面（`relatedTarget` 是 `null`）時選單不收；與點選單內不可聚焦處同一條路，接受。

驗證（2026-11-04）：`uv run pre-commit run --all-files` 全過；`uv run pytest -n auto` 5432 passed、1 skipped；`pnpm -C web test` 2354 passed；`pnpm -C web e2e` 81 passed（含 `navigation` 與 `navigation-390`）。
