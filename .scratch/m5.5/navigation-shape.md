# 導覽收斂 shape（M5.5 票 07）

2026-11-04。使用者確認兩件事：數字各歸各頁、手機上導覽自己一列換行（不做漢堡選單）。其餘照 `DESIGN.md`〈Navigation〉的既有方塊。

## 誰、在什麼時候

- 管理員平常不開 Berth，收到 Discord「有 N 件等你處理」才打開（`PRODUCT.md`）。頁首要一眼看出那 N 件在哪一頁。
- 一般使用者只做三件事：找片、看媒體庫、看下載。原本的九顆按鈕裡六顆跟他無關或很少用。
- Operate 模式：靠熟悉的形狀與掃視速度，不靠表現。

## 結構

```
桌機（≥ sm）
Berth / 副標   [探索] [新番 1] [媒體庫] [下載] [待處理 2]   [助理] [roxy ▾]

390px
Berth / 副標                    [助理] [roxy ▾]
[探索] [新番 1] [媒體庫]
[下載] [待處理 2]
```

- **主導覽**（`<nav aria-label="主要導覽">`）：探索 `/`、新番 `/rss`、媒體庫 `/library`、下載 `/jobs`、待處理 `/review`。新番與待處理只有 admin（09 之後新番給所有人、連 `/schedule`）。
- 窄版：導覽自己一整列（`order-last basis-full`），放不下就換行；應用名、助理、帳號選單在第一列。實跑後補：副標在窄版收起（`hidden sm:block`），否則 390 寬時第一列放不下，助理與帳號選單掉到第二列、頁首變三列。桌機一列，導覽接在應用名後面、助理與帳號選單靠右。
- **件數**：一塊 `assigned` 小色塊接在標籤後面，內容是數字本身（文字），可存取名稱念成「待處理 2 件」。0 件、還沒讀到、讀不到時不畫（讀不到不擋導覽）。
  - 待處理 = 審核 + Issue；新番 = 待綁定的 RSS Series。兩者加起來就是 Discord 那個 N（同一份 `waiting_now`）。
  - 每分鐘重讀一次、視窗拿回焦點時重讀；code-review 後補：任何動作結束都失效一次（`router.ts` 的 `recountAfterActions`），否則修掉最後一件後同一畫面的分頁列還掛著舊數字。
- **當前頁**：一個導覽項管一個區塊，區塊裡任一頁都算當前（待處理：`/review`、`/issues`；新番：`/rss`）。連結指著的不是當前這一頁時用 `aria-current="true"`，是的時候 `page`。

## 區塊分頁

- 待處理的 `/review`、`/issues`，新番的 `/rss`，頁面最上面掛一條分頁列，形狀同 `SettingsTabs`（`NAV_LINK`，自己一個 `<nav>`），在 `<h1>` 上方。
- 待處理：「審核 N」「Issue N」；新番：只有「訂閱 N」（09 加「時間表」、12 加「追更」）。件數同頁首的色塊。
- 兩頁仍是兩頁（ADR-0006）：`/review` 那行「另有 N 件待處理」照留。`/issues` 的標題改成「Issue」，「待處理」留給整個區塊。

## 帳號選單

- 觸發鍵：`NAV_BOX` 方塊，內容是名字（`.value`）加「▾」，`aria-expanded`、`aria-controls`；可存取名稱「帳號：roxy」。選單裡的頁面（設定、健康、週報）是當前頁時，觸發鍵畫成當前（重橫線 + `deck` 底）並掛 `aria-current="true"`，讓人知道自己在哪；展開與否只由 `aria-expanded` 與面板說，不換漆。
- 選單：觸發鍵正下方、靠右對齊的一塊 `deck` 面板，`border-2 border-rule-strong`，由上而下：
  1. 名字與角色色塊（不是按鈕）
  2. 設定 `/settings`、健康 `/health`、週報 `/weekly`（只有 admin），一列一個連結
  3. 語言（現有 `LanguageToggle`，帶標題）
  4. 登出（`GhostButton`）
- 是 disclosure，不是 `role="menu"`（WAI-ARIA APG 的 Disclosure Navigation Menu；GitHub、GOV.UK 的帳號選單同形狀）：裡面是一般的連結與按鈕，Tab 依序走，不搶方向鍵。
- 鍵盤與焦點：
  - Enter / Space 打開，焦點留在觸發鍵（下一個 Tab 進選單）。
  - `Esc` 關掉，焦點回到觸發鍵；Tab 走出選單或點選單外面關掉，焦點不動。
  - 點了連結就關（換頁），換語言不關（還要看一眼換好了沒）。
- 原生元素：`<button>` + 一塊 `<div>`，不用 `<details>`（`Esc` 不會自己關、點外面不會關）也不用 `popover`（jsdom 沒有，定位要 anchor positioning）。

## 不動的

- 所有網址：`/rss`、`/review`、`/issues`、`/settings`、`/health`、`/weekly`、`/weekly/{id}`（Discord 週報，`services/deeplink.py`）。
- 助理開關的位置與行為；skip link。
- 未登入（登入頁）只有語言鍵。

## 驗收怎麼看

- e2e：一般使用者頁首只有探索、媒體庫、下載與帳號選單；admin 多新番與待處理（帶數字），桌機與 390px。
- e2e：舊網址都打得開，週報的 `/weekly/{id}` 打得開。
- vitest：帳號選單 Enter 打開、`Esc` 關掉、焦點回到觸發鍵；點外面關掉。
