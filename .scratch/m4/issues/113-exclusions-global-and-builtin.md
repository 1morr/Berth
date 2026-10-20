# 113 — 排除條件分清全域與內建

**Status:** done

**Blocked by:** 110（同改 `RulesEditor` 與 /rss 的排除條件畫面，避免衝突；邏輯上不互擋）

**讀:** brief §15「全部接受，只排除」；`berth/parser/exclusion.py` 開頭的說明；`web/src/rss/ExclusionsSection.tsx`、`web/src/rss/RulesEditor.tsx`、Feed 與 RSS Series 那兩層的 `RulesToggle`；`PRODUCT.md`、`DESIGN.md`

## 為什麼

使用者 2026-10-19 看 /rss 的排除條件，三個疑問：

- 那一段只叫「排除條件」，沒說是**全域**的；Feed 與 RSS Series 那兩層的編輯器又沒有合集那一項，看起來像只有這裡有合集設定、別處漏了。
- 「不自動下載合集」是單獨一個勾選，夾在說明與規則清單之間，跟下面的規則格格不入——它其實不是關鍵字，是看解析器的 `release_kind`（合集、區間、季包的寫法一條關鍵字寫不完，brief §15）。
- 建議按鈕（720p、简体…）是關鍵字還是正則，畫面沒說。

設計本身不變（合集只在全域一層，例外由 111 的逐筆放行處理）；這張票讓畫面說清楚。

## 做什麼

1. **全域那一段**：標題改成「全域排除條件」；合集那一項在視覺上與規則清單分開，標明是「內建判斷（看解析結果，不是關鍵字）」；建議那一列標明是關鍵字。
2. **Feed 與 RSS Series 那兩層**：排除條件編輯器加一行「合集由全域設定：目前不自動下載／目前會自動下載」，連回全域那一段。
3. **說明**：`rss.rules.lede` 與兩層的說明用詞一致，三層取聯集那一句保留。
4. 走 `/impeccable critique` 看這一段；i18n zh-Hant、en 並列；CHANGELOG；progress.md session 紀錄。

## 不做

- 在 Feed、RSS Series 兩層加合集開關（brief §15 定在全域；2026-10-19 使用者確認不加）。
- 改規則格式或建議清單的內容。

## 驗收

- [x] 全域那一段的標題、合集那一項、建議那一列照上面的文案顯示（vitest，zh-Hant 與 en）
- [x] Feed 與 RSS Series 的排除條件編輯器說出全域合集設定的目前值，切換全域開關後跟著變（vitest）
- [x] playwright 實跑 /rss 三層排除條件，附截圖（1280 與 390）
- [x] 全部檢查、vitest 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-19 實作：新增 Feed 表單也加了合集那一行（它也是 Feed 那一層）；`/impeccable critique`（detector 0 發現）之後空狀態改「沒有標題規則。」（原句與合集那一行矛盾），內建判斷組的說明進 `aria-describedby`。截圖在 e2e `rss-exclusions`／`rss-exclusions-390` 的 `2b-three-layers`、`2c-to-global`。
- critique 未處理：(1) 兩層的 toggle 仍叫「排除條件（N 條）」，全域那一段叫「標題規則」——要不要改成「本層標題規則（N 條）」待定，牽動 e2e 與 skip 理由的用詞；(2)「改全域設定」是原生錨點，只捲動、不移焦點（與 `SUBSCRIBE_ANCHOR` 同做法）；(3) 390 寬新增 Feed 的說明連同合集那一行共四行，偏密；(4) en 的連結走 `TEXT_LINK` 的 `.label` 大寫字距，比旁邊的句子重。
- code-review 未處理：全域查詢載入中或失敗時兩層的合集那一行不顯示（那時全域那一段也畫不出來，整頁顯示讀取失敗）；切換全域開關時兩層等重問回來才變，不像全域那一格樂觀顯示；兩個英文測試各寫一次 `changeLanguage` 的 try/finally（檔案裡原本就這樣寫）。
