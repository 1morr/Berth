# 117 — 排除條件編輯器：每層說「標題規則」；送出中鎖住輸入框

**Status:** done

**Blocked by:** None — can start immediately

**讀:** 票 110、113；CONTEXT.md:372-373（排除條件 / 標題規則 / 內建判斷）；`web/src/rss/RulesEditor.tsx`（:130-139 輸入框、:188 計數）；`web/src/i18n/resources.ts`（`rss.rules.*`）；`web/src/pages/RssPage.test.tsx`；`web/e2e/rss-exclusions.spec.ts`；DESIGN.md:572

## 為什麼

1. 票 113 把全域那一段的關鍵字／正則叫「標題規則」，合集那一項叫「內建判斷」，CONTEXT.md 也寫明畫面上叫標題規則。但 Feed 與 RSS Series 兩層的展開鍵仍是「排除條件（N 條）」，N 只算這一層的標題規則；加入欄的 label 仍是「加一條排除條件」，同一個元件裡空狀態卻已是「沒有標題規則。」。全域開著「不自動下載合集」時，Feed 卡片顯示「排除條件（0 條）」，讀起來像這個 Feed 什麼都不擋。
2. 票 110 說新增 Feed 送出中「規則欄鎖住」，實際只鎖了按鈕，輸入框本身沒有 `readOnly`；送出中多打的字成功後被清掉。

協調者審查（2026-10-20）定案：不加「本層」二字，展開鍵長在那一列上，層級從位置就看得出來。

## 做什麼

1. 字串：
   - `rss.rules.toggle_one` / `toggle_other`：zh-Hant `標題規則（{{count}} 條）`，en `Title rules ({{count}})`
   - `rss.rules.add`：zh-Hant `加一條標題規則`，en `Add a title rule`
   - `rss.rules.list`（sr-only）：zh-Hant `標題規則`，en `Title rules`
   - 不動：`rss.rules.title`（新增表單那一組的總稱，含合集那一行）、「全域排除條件」、skip 理由的「排除條件」（領域詞）。
2. `RulesFields` 的輸入框在 `busy` 時 `readOnly`（`Field` 要能把 prop 傳到 input）。
3. 同步改 `RssPage.test.tsx`、`web/e2e/rss-exclusions.spec.ts`、DESIGN.md:572 的字串。

## 驗收

- [x] Feed 列與 RSS Series 的展開鍵、加入欄 label 照上面的字串（vitest，zh-Hant 與 en）
- [x] 新增 Feed 送出中規則輸入框是 readOnly（vitest）
- [x] 前端 e2e `rss-exclusions` 兩種寬度綠
- [x] 全部檢查、vitest 綠；DESIGN.md、CHANGELOG、progress.md 已更新

## Comments

- 2026-10-20 實作：`Field` 本來就把其餘 prop 傳到 input，只在 `RulesFields` 加 `readOnly={busy}`。它也蓋到 `RulesEditor`
  （全域、Feed、RSS Series 改了就存的那三處）：存檔途中同樣鎖住，理由相同（成功之後 `setDraft('')`）。那條路沒有 vitest
  守，驗收沒要求。`rss.rules.add` 三層共用，全域那一段的加入欄也跟著叫「加一條標題規則」（符合 CONTEXT.md:373）。
- code-review Standards 軸留下的（不處理）：清單上的 skip 理由（「全域的排除條件「720p」擋下」、`feed_rule`、`series_rule`、
  `excludedRule_*`）照舊說「排除條件」——票面明寫 skip 理由的「排除條件」是領域詞、不動。
- e2e：第一次兩種寬度同跑時 `rss-exclusions-390` 紅過一次（沒留下錯誤內容），之後單跑兩次、同跑一次都綠。容器的
  chromium 是 1194、playwright 要 1243，在 `/opt/pw-browsers` 建 symlink 跑（只動容器）。
