---
name: Berth
description: 泊位調度板——船期表加 ISO 6346 貨櫃標識的自託管媒體協調器介面。
colors:
  hull: "oklch(0.26 0.021 245)"
  deck: "oklch(0.31 0.022 245)"
  well: "oklch(0.21 0.019 245)"
  rule: "oklch(0.44 0.022 245)"
  rule-strong: "oklch(0.6 0.024 245)"
  ink: "oklch(0.97 0.005 245)"
  ink-dim: "oklch(0.78 0.012 245)"
  assigned: "oklch(0.85 0.18 95)"
  working: "oklch(0.79 0.14 205)"
  secured: "oklch(0.76 0.16 150)"
  blocked: "oklch(0.7 0.2 27)"
  on-signal: "oklch(0.16 0.02 245)"
  blocked-ink: "oklch(0.7 0.2 27)"
  secured-ink: "oklch(0.76 0.16 150)"
typography:
  app-name:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "1.125rem"
    fontWeight: 600
    letterSpacing: "-0.015em"
  berth-name:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "1rem"
    fontWeight: 600
    fontFeature: "tabular-nums"
  label:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.18em"
  label-zh-hant:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'Noto Sans TC', 'PingFang TC', sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.05em"
  value:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    fontFeature: "tabular-nums"
  value-small:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    fontFeature: "tabular-nums"
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'Noto Sans TC', 'PingFang TC', sans-serif"
    fontSize: "0.875rem"
    lineHeight: 1.5
  body-small:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'Noto Sans TC', 'PingFang TC', sans-serif"
    fontSize: "0.75rem"
    lineHeight: 1.5
rounded:
  none: "0"
spacing:
  hairline: "1px"
  xs: "0.5rem"
  sm: "0.75rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.assigned}"
    textColor: "{colors.on-signal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.875rem 1rem"
    width: "100%"
  button-primary-disabled:
    backgroundColor: "{colors.deck}"
    textColor: "{colors.ink-dim}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.875rem 1rem"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.625rem 1rem"
  input-field:
    backgroundColor: "{colors.hull}"
    textColor: "{colors.ink}"
    typography: "{typography.value}"
    rounded: "{rounded.none}"
    padding: "0.625rem 0.75rem"
    width: "100%"
  chip-assigned:
    backgroundColor: "{colors.assigned}"
    textColor: "{colors.on-signal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.5rem"
  chip-working:
    backgroundColor: "{colors.working}"
    textColor: "{colors.on-signal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.5rem"
  chip-secured:
    backgroundColor: "{colors.secured}"
    textColor: "{colors.on-signal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.5rem"
  chip-blocked:
    backgroundColor: "{colors.blocked}"
    textColor: "{colors.on-signal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.5rem"
  chip-neutral:
    backgroundColor: "{colors.deck}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.5rem"
  board-cell:
    backgroundColor: "{colors.secured}"
    textColor: "{colors.on-signal}"
    typography: "{typography.berth-name}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1rem"
  board-cell-empty:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink-dim}"
    typography: "{typography.berth-name}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1rem"
  panel:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
  panel-header:
    backgroundColor: "{colors.deck}"
    textColor: "{colors.ink-dim}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.625rem 1rem"
  notice:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0.625rem 0.75rem"
---

# Design System: Berth

## Overview

**Creative North Star:「泊位調度板」（The Berth Dispatch Board）**

Berth 的介面是一塊船席調度板，不是儀表板也不是表單流程。碼頭的調度板用最少的材料回答一個問題——
哪一格出事了——靠的是塗滿整格的漆、壓過整幅的重橫線、對得齊的等寬編號，以及 ISO 6346 貨櫃標識那種
模板噴字。Berth 的四個泊位（Jellyfin / qBittorrent / 來源 / 媒體庫路徑）在精靈與健康頁上是同一塊板：
精靈問「接上了沒」，健康頁問「還繫著嗎」，位置與意義完全不變。

底色是鋼灰藍船體而不是近黑：`--color-hull` 的註釋寫明這是刻意迴避「近黑加單一霓虹」那種類別預設。
深色是預設，亮色跟隨系統偏好，是同一塊板子印在紙上——只有中性色換值，四個信號色與 `on-signal`
兩個主題共用。整個系統沒有引入任何 webfont：自架應用不該對 Google Fonts 發請求，離線也要成立，
所以「模板噴字」的語彙由處理方式承載（等寬系統堆疊 + 重字距 + 重橫線 + 色塊），不由字體檔承載。

密度高、留白少、每一格裡的每個字都是實測值。已確認拒絕的類別預設：左側垂直步驟條加深色卡片加藍色
primary、uptime 儀表板的折線圖與綠色勾勾牆、訊息塊左緣的粗色條、發光、漸層、圓角卡片、
把泊位板做成橫向捲動的 carousel。

**Key Characteristics:**

- 四個信號色，每個只有一個意思；紅色永遠只代表阻擋。
- 狀態三重編碼：塗裝色塊 + 模板字標籤 + 泊位號，不看顏色也讀得出來。
- 零圓角（`--radius-none: 0`），全站無例外。
- 分層靠重橫線與色階，不靠陰影。
- 標籤與數值全部等寬 + 等寬數字；散文才用系統無襯線。
- 深淺兩主題都是 WCAG 2.2 AA 的驗收條件，不是加分項。

## Colors

鋼灰藍的船體中性色，加上四罐 hi-vis 塗料。中性色承載所有版面，信號色只用在「這一格現在是什麼狀態」。

### Primary

- **hi-vis 調度黃 `assigned`**：「現在需要你」。精靈的所有主要動作按鈕、目前語言鍵、
  設定漂移的泊位格、待處理的纜繩都是它。它是整塊板上唯一的主要動作顏色——這塊板子沒有藍色 primary。

### Secondary

- **航道藍 `working`**：「進行中」。靠泊序列裡正在跑的那一條纜繩、正在探測的泊位格。
  它只表示「還沒有結論」，不表示成功。
- **繫纜綠 `secured`**：「已完成且驗過」。綠燈的泊位格、通過的檢查列。文字版本另有 `secured-ink`。
- **阻擋紅 `blocked`**：「卡住了，在你動手之前走不下去」。文字版本另有 `blocked-ink`。
  紅色沒有第二個用途——它不代表警告、不代表危險動作、不代表刪除。

### Tertiary

- **信號油墨 `on-signal`**：塗在四個信號色上的字色，深鋼灰。它不是背景色，只做四塊漆上的字與圖。
  白字配中明度信號色實測只有 3.6:1，過不了 AA，所以四罐漆一律配同一罐深墨。
- **`blocked-ink` / `secured-ink`**：信號色「當字用」時的兩個值。塗裝色在紙白底上讀不出來，
  所以只有這兩個 token 在亮色主題壓深。

### Neutral

- **船體 `hull`**：整頁底色，也塗在 `body` 上（版面元素只佔 `min-h-dvh`，overscroll 露出的是 body）。
  失敗展開區、輸入框內部也用它。
- **甲板 `deck`**：抬起一階的中性面——面板抬頭列、中性色塊、複製鍵、當前導覽項。
- **艙井 `well`**：下沉一階的中性面——所有面板、卡片、纜繩列、訊息塊的內部底色。
- **橫線 `rule`**：一般分隔線與靜態邊框（`border-2`）。
- **重橫線 `rule-strong`**：分區的重線、失敗時的邊框、主要按鈕的輪廓。對兩個主題的底色都有 6.4:1，
  滿足 WCAG 2.2 非文字對比 3:1。
- **字 `ink` / 弱字 `ink-dim`**：主要與次要文字。`ink-dim` 用在標籤、端點、提示，不用在必須讀清楚的值。

### Named Rules

**The One Meaning Rule（一色一義）。** 全站只有四個信號色，每個顏色只有一個意思：
`assigned` 需要你、`working` 進行中、`secured` 已繫上、`blocked` 阻擋。新的語意要嘛映射到這四個之一，
要嘛用中性色。紅色永遠只代表阻擋。

**The Triple Encoding Rule（三重編碼）。** 任何狀態都同時由色塊、模板字標籤與位置（泊位號 `BTH 1`–`BTH 4`）
表達。審計測試：把畫面轉成灰階，狀態仍然讀得出來，否則這個狀態沒做完。

**The Paint Doesn't Swap Rule（漆不換色）。** 四個信號色與 `on-signal` 在深淺兩主題**共用同一組值**：
它們是塗上去的漆，不是隨底色變的字色。換主題時只換中性色與 `blocked-ink` / `secured-ink`。
任何 `dark:` / `light:` 變體都是這條規則出錯的徵兆——版面不需要它們。

**The Role Is Not A State Rule（角色不借信號色）。** 使用者角色、語言、分類這種「不是狀態」的東西
一律用中性色塊（`deck` 底 + `ink` 字）。信號色借出去一次，一色一義就沒了。

**The Paint Needs A Painted Ground Rule（色塊不疊在圖像上）。** 色塊與它上面的字只有在底是
**token** 時才算得出對比；疊在圖像上時，讀不讀得出來取決於那張圖那一角剛好是什麼顏色。
探索頁的狀態色塊因此貼在卡片下方的標識帶（底是 `well`，實測 11.95:1）而不是壓在海報左下角——
量到這件事的是票 03 的「已追蹤」，那個色塊在票 04b 拿掉了（狀態要等 Job 與帳本才推導得出來），
但它回來時貼的還是同一條帶子——
實測到的失敗是：`deck` 在亮色主題是近白，壓在深色海報上很清楚；深色主題它是中灰，壓在同樣深色的
海報上幾乎消失（票 03）。要標在圖上，就得先鋪一塊自己的不透明底，而那等於把圖遮掉一塊。

## Typography

**Display Font:** 無。這個系統沒有 display 級別的字，最大的字是 1.125rem 的應用名。
**Body Font:** 系統無襯線堆疊（`system-ui`、`Segoe UI`、`Noto Sans TC`、`PingFang TC`），只用於散文。
**Label / Value Font:** 系統等寬堆疊（`ui-monospace`、`Cascadia Mono`、`SF Mono`、`Menlo`、`Consolas`）。

**Character:** 貨櫃編號的語域。標籤、代號、路徑、版本號、inode、時間全部等寬且 `tabular-nums`，
在表格裡對得齊；只有真正的句子才落回系統無襯線。不載入任何 webfont——離線可用是自架應用的底線，
「模板噴字」由字距、橫線與色塊承載。

### Hierarchy

- **App name**（mono，600，1.125rem，`tracking-tight`）：頁首的 `Berth`，每一頁只有一個。
- **Berth name**（mono，600，1rem）：泊位格裡的服務名。板上唯一比內文大的字。
- **Value**（mono，400，0.875rem，`tabular-nums`）：實測值、服務名、檢查項名稱。
- **Value small**（mono，400，0.75rem，`tabular-nums`）：端點、路徑、位址、錯誤原文、指令列。
- **Label（Latin）**（mono，600，0.6875rem，`0.18em`，全大寫）：模板字。狀態標籤、欄位名、
  面板抬頭、按鈕文字、導覽項。
- **Label（zh-Hant）**（sans，600，0.6875rem，`0.05em`，不轉大小寫，前置塗刻度）：同一個角色的中文版。
- **Body / Body small**（sans，0.875rem / 0.75rem）：說明、提示、修正步驟的散文。上限 `max-w-prose`。

### Named Rules

**The Two Alphabets Rule（標籤依語言分岔）。** 中文沒有大小寫，`text-transform: uppercase` 對它無效，
寬字距也讓中文更難讀。所以 `.label` 在 `:lang(zh-Hant)` 下換成無襯線、原樣大小寫、`0.05em`，
並用一個 `::before` 的 2px 塗刻度代替大寫帶來的「這是標籤」訊號。刻度用空 `content` 畫出來而不是
用 `▸` 這種字元——字元會被算進無障礙名稱，螢幕閱讀器會念成「三角形 帳號」。兩個語言的標籤高度與
色階相同，換語言時版面不跳動。

**The Machine String Rule（機器字串走 `.value`）。** API 端點、設定鍵、檔案路徑、inode、版本號、
容器名一律用 `.value`，永遠不用 `.label`。理由是實際發生過的缺陷：`CutawayRow` 的 term 走 `.label`，
英文版把 `POST /Library/VirtualFolders` 印成 `POST /LIBRARY/VIRTUALFOLDERS`，同一個畫面上出現九個
端點的兩種大小寫，其中一種不是真的端點（中文因 `text-transform: none` 看不到這個 bug）。
`CutawayRow` 因此有 `code` 變體，term 走 `.value text-xs`。審計測試：畫面上任何一個字串，
如果使用者可能把它複製貼到別的介面或指令列，它就不能被大寫掉。

**The Tabular Rule（值一律等寬數字）。** 任何會出現在同一欄的數字（版本、inode、可用空間、計數）
都走 `.value`，`font-variant-numeric: tabular-nums`。維運頁面掃視靠的是對齊。

## Layout

**外框。** 頁首是一條 `border-b-2 border-rule-strong` 的重橫線帶，左側應用名與副標，右側依序是
角色色塊、導覽、登出、`ZH / EN` 語言鍵。`main` 不設寬度上限：泊位板是整寬橫幅，每一頁自己決定內文欄寬。

**泊位板橫幅。** 四格等寬，格與格之間是 1px `gap-px`（底色 `rule-strong` 透出來當線，不是 border）。
窄螢幕 `grid-cols-2`（2×2），`sm`（640px）以上 `grid-cols-4` 一列四格。欄數寫死，因為泊位就是那四個。
目前的那一格用 `aria-current="step"` 與一條 `inset 0 -3px currentColor` 的底線標出來——用 `currentColor`
而不是第五個顏色，因為四塊漆上的字色本來就是為了在那塊漆上讀得出來而選的。

**工作面。** 精靈每一步是 `lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]` 的兩欄（左剖面、右纜繩），
`gap-px` 上鋪 `bg-rule` 讓縫隙自己變成分隔線；`lg` 以下疊成單欄。健康頁內文是 `max-w-3xl` 置中。
登入頁是 `max-w-[26rem]` 的單一登船口窗格，用 `my-auto` 而不是 `items-center` 置中——矮螢幕
（手機橫放且開了鍵盤）上 flex 置中會把上緣切掉且捲不回去。

**節奏。** 內部間距只有幾階：色塊 `0.375rem 0.5rem`、列與面板 `0.75rem 1rem`、頁面外緣 `1.5rem`、
區塊之間 `1rem`–`1.5rem`、頁面上下 `2rem`。列與列之間用 `gap-3`（0.75rem）或 1px 的線。

**手機。** 主要動作在窄版固定於底部安全區之上（`sticky bottom-0` + `env(safe-area-inset-bottom)`，
`-mx-6` 讓它橫跨整個工作面），`lg` 以上恢復成一般行內按鈕。長路徑一律換行（`break-words`），
不橫向捲動——被切掉的建議值等於沒顯示。`break-all` 已被移除，它會在英文詞中間斷行。

### Named Rules

**The Board Never Scrolls Rule（板不捲動）。** 泊位板永遠四格全在畫面內：窄版 2×2，桌機一列四格。
不做橫向捲動的 carousel——BTH 3 與 BTH 4 捲到畫面外時，「一眼看出哪一格紅了」這塊板存在的理由就沒了，
而且捲動容器會變成一個沒有名字的 Tab 停留點。

**The Values Sit On Their Line Rule（值貼在它那一行）。** 實測值、端點、鍵名貼在它所屬的那一列，
不進散文。剖面（`Cutaway`）是 `dt` / `dd` 的兩欄表，不是段落。

**The Failure Expands In Place Rule（失敗就地展開）。** 任何失敗都在它自己那一列的下方就地展開
（服務回的原文 + 修正說明 + 可複製指令），其他列不動、不跳頁、不開 dialog。二次確認同樣就地展開
成一段說明加兩顆按鈕。

## Elevation & Depth

**這個系統沒有陰影，也沒有 z 軸。** 深度完全由三件事表達：中性色階（`well` 下沉 / `hull` 底 /
`deck` 抬起）、`border-2` 的橫線與 `border-b-2 border-rule-strong` 的重分區線、以及 1px `gap-px`
縫隙透出的線。沒有卡片浮起、沒有發光、沒有漸層、沒有 `backdrop-filter`。

程式碼裡只有兩處 `box-shadow`，兩處都不表達深度：焦點環的外圈，以及泊位板目前那一格的
`inset 0 -3px 0 0 currentColor` 底線——那是一條畫在格子裡的線，`inset` 讓它不佔版面、格子不會跳。

**焦點環。** `outline: 2px solid var(--color-ink)` + `outline-offset: 2px` + `box-shadow: 0 0 0 2px var(--color-hull)`。
雙環是刻意的：焦點會落在四塊漆上（黃色按鈕、狀態色塊），任何單一顏色都會在其中一塊漆上消失；
內圈用底色、外圈用字色，兩個主題、四塊漆上都至少有一圈看得見。選擇器涵蓋
`a, button, summary, input, select, textarea, [tabindex]`——`summary` 是後補進去的，
少了它 `<details>` 會落回 Chrome 預設的 0.67px 焦點環。

**動態。** 沒有轉場、沒有動畫類別。署名互動「靠泊序列 / 複驗序列」是逐條纜繩換狀態，不是 spinner
也不是動畫；每完成一條就把實際結果數值留在旁邊。`prefers-reduced-motion: reduce` 下全域把
`animation-duration` 與 `transition-duration` 壓到 0.01ms，這是防護欄而不是效果開關。

### Named Rules

**The Rule-Line Rule（以線分層）。** 分層一律用線與色階，不用陰影。需要「抬起」時換 `deck`，
需要「下沉」時換 `well`，需要「這是另一個區塊」時加 `border-2 border-rule`，需要「這是分區」時
加 `border-b-2 border-rule-strong`。`box-shadow` 只允許出現在焦點環，以及當成畫在元素內部的線。

## Shapes

**這塊板子沒有圓角。** `--radius-none: 0`，全站無例外——按鈕、輸入框、色塊、面板、訊息塊、指令列
一律直角。形狀語彙只有矩形與線：塗滿整格的矩形色塊、2px 的框、1px 的縫。

**色塊是填滿的，不是描邊的。** 狀態一律是塗滿的矩形加深墨字，不是彩色外框加彩色字。
唯一帶框的色塊是主要按鈕——亮色主題下黃漆對紙白只有 1.36:1，沒有 `border-rule-strong`
按鈕輪廓就看不出來（WCAG 2.2 非文字對比 3:1）。

**沒有圖示。** 系統裡沒有 icon font、沒有 SVG 圖示集。唯一的非文字標記是中文標籤前那道 2px 塗刻度，
它由 CSS 畫出來、不是字元、不進無障礙名稱。

## Components

### Buttons

- **Shape:** 直角（`0`），`border-2`。
- **Primary（`PrimaryButton`）:** `assigned` 黃漆填滿 + `on-signal` 深墨字 + `rule-strong` 邊框，
  `padding: 0.875rem 1rem`，`.label` 模板字，寬度滿版。停用態換成 `deck` 底 + `ink-dim` 字，
  `cursor: not-allowed`。整個系統只有這一種主要動作外觀。
- **Ghost（`GhostButton`）:** 只有 `rule` 外框與 `ink` 字，`padding: 0.625rem 1rem`。
  hover 時邊框換 `rule-strong`——次要動作不靠顏色搶位置，靠線變重。
- **Focus:** 全域雙環（見 Elevation & Depth），元件不自帶焦點樣式。
- **命中面積:** 互動元件不得小於 24×24 CSS px，或與鄰近目標保持 24px 間距（WCAG 2.2 AA 2.5.8）。
  密碼欄的「顯示」鍵曾是 38.6×15px 且距輸入框 11.5px，兩條都不成立，現在是 `min-h-6 min-w-6`。

### Chips（狀態色塊）

- **Style:** `.label` 模板字 + `padding: 0.375rem 0.5rem`，信號色填滿 + `on-signal` 深墨字。
  中性色塊（角色、語言未選中）用 `deck` + `ink`。
- **不透明度:** 色塊上的文字**永遠不加 opacity**。`label opacity-70` 疊在信號色上實測 3.56:1，
  兩個主題兩種寬度都不過關；共用信號色與 `on-signal` 的整個安排就是為了避免這件事。
  泊位格裡的 `opacity-80` 是疊在 `on-signal` 深墨上的次要行，實測仍在 6.67–9.63:1 之間。

### Cards / Containers（面板與剖面）

- **Corner Style:** 直角。
- **Background:** `well`；抬頭列 `deck`，以 `border-b-2 border-rule` 與內容分開。
- **Border:** `border-2 border-rule`；失敗或需要注意時整塊換 `border-rule-strong`（線變重，不是變紅）。
- **Internal Padding:** 抬頭列 `0.625rem 1rem`，內容列 `0.75rem 1rem`。
- **剖面（`Cutaway` / `CutawayRow`）:** `dl` 的兩欄表，`sm` 以上 `1fr / 1fr`，以下疊成單欄。
  term 預設走 `.label`；term 是機器字串時必須用 `code` 變體（`.value text-xs`），見 The Machine String Rule。

### Inputs / Fields

- **Style:** `hull` 底 + `border-2 border-rule` + `.value` 等寬字，`padding: 0.625rem 0.75rem`。
  標籤在上方，`.label text-ink-dim`。
- **Focus:** 邊框換 `rule-strong`，外加全域雙環。
- **Error:** 邊框換 `blocked`，`aria-invalid`，錯誤訊息以 `role="alert"` + `aria-describedby` 掛在欄位下方，
  文字用 `blocked-ink`。
- **Disabled:** `well` 底 + `ink-dim` 字。
- **Checkbox:** 原生 `input[type=checkbox]`，`accent-color: var(--color-assigned)`，`size-4`。
- **元件基礎:** 原生 `input` / `button` / `checkbox` / `details`。M0 沒有任何需要 Radix 行為的元件
  （無 dropdown / dialog / popover / tabs），原生的無障礙比重寫一份好。要 shadcn/ui 時再引入。

### Navigation

- 頁首導覽項是 `.label` 模板字 + `border-2 border-rule` 的外框方塊。當前頁用**重橫線加 `deck` 底**
  標出（`border-rule-strong`），不靠顏色——狀態不只靠顏色是產品層級的無障礙底線。
- `設定` 只對 `admin` 顯示；角色本身以中性色塊呈現，讓 `user` 知道自己為什麼沒有那顆按鈕。
- 語言鍵（`LanguageToggle`）是 `role="group"` 加兩顆 `aria-pressed` 按鈕，選中那顆是 `assigned` 黃漆。

### 泊位板（`BerthBoard`，署名元件）

四格等寬的整寬橫幅，是整個系統的識別。每格四行：泊位碼（`BTH 1`，`.value` 且不走 i18n——
ISO 6346 標識在哪個語言都是同一串字母數字）、狀態標籤（`.label`）、服務名（`.value` 1rem）、
實測值那一行（沒有值時留一條 `—`，四格高度才不會跳）。`filled === false` 的格子留在 `well` 中性底上
表示「還沒有任何結果」。精靈與健康頁共用同一個元件與同一份 `BERTHS`：兩邊講的是同一組泊位，
各寫一份遲早會分岔。

### 纜繩列（`StepLine` / `RouteCheckList`，署名元件）

一條纜繩是一個步驟：狀態色塊 + `.label` 狀態字 + 名稱 + 實測值 + 它打的那支端點（靠右、`ink-dim`）。
失敗時整列邊框換 `rule-strong`，下方就地展開 `role="alert"` 的服務原文、修正說明與 `CopyLine` 指令，
其餘已繫上的纜繩不動。精靈第 7 步與健康頁跑的是同一組檢查、用同一個元件，所以
「精靈當時是綠的、現在紅了」在畫面上是同一種東西。

### 訊息塊（`Notice`）

`well` 底 + `rule` 框 + 左側一塊信號色塊 + `.label` 標記 + 散文。標記是**塗上去的色塊加模板字**，
不是左緣的粗色條——那條粗色條是 AI 介面最好認的胎記，也不是這塊板子的語彙。
`blocked` 時帶 `role="alert"`。

### 指令列（`CopyLine`）

`hull` 底的 `<code>`（`.value text-xs`，`whitespace-pre`，可橫向捲動）加右側 `deck` 底的複製鍵，
中間用 1px 縫。每個失敗都要給得出可複製的下一步。

### 時間（`Timestamp`）

相對說法給人掃視（`Intl.RelativeTimeFormat`，認得 `zh-Hant` 與 `en`），絕對時間留在 `<time datetime>`
與 `title`。維運頁上「三分鐘前」與「三小時前」是兩件事，而 ISO 字串沒有人在掃視時算得出來。
沒有值時是「沒有紀錄」，不是「尚未檢查」。

## Do's and Don'ts

### Do:

- **Do** 讓每個狀態同時有色塊、模板字標籤與位置（The Triple Encoding Rule）。灰階測試要能通過。
- **Do** 把 API 端點、設定鍵、路徑、inode、版本號一律放進 `.value`；`CutawayRow` 用 `code` 變體
  （The Machine String Rule）。
- **Do** 讓四個信號色與 `on-signal` 在兩個主題共用同一組值，只換中性色與 `blocked-ink` / `secured-ink`。
- **Do** 用色階與線分層：`well` / `hull` / `deck` 三階加 `border-2 border-rule` 與
  `border-b-2 border-rule-strong`（The Rule-Line Rule）。
- **Do** 讓失敗在它自己那一列就地展開服務回的原文、修正說明與可複製指令。
- **Do** 讓新增的互動元件被全域 `:focus-visible` 選擇器涵蓋（含 `summary`），並保持 24px 的命中/間距底線。
- **Do** 在窄版把泊位板排成 2×2，讓四格同時在畫面內（The Board Never Scrolls Rule）。
- **Do** 讓長路徑換行（`break-words`），不橫向捲動、不截斷。
- **Do** 用中性色塊表達角色、語言、分類這類非狀態的東西（The Role Is Not A State Rule）。
- **Do** 用原生 `input` / `button` / `details`，直到某一步真的需要行為基礎的元件為止。

### Don't:

- **Don't** 給任何顏色第二個意思，尤其不要讓紅色代表阻擋以外的事（警告、危險動作、刪除都不是阻擋）。
- **Don't** 在信號色塊上的文字加 `opacity`；`opacity-70` 疊在信號色上實測 3.56:1，過不了 AA。
- **Don't** 用 `.label` 包任何使用者可能複製出去的機器字串——它會被 `uppercase` 成一個不存在的端點。
- **Don't** 加圓角。`--radius-none: 0` 沒有例外。
- **Don't** 用陰影、發光、漸層或 `backdrop-filter` 表達深度；`box-shadow` 只用於焦點環與畫在元素內部的線。
- **Don't** 用藍色 primary 按鈕，或任何 `assigned` 以外的主要動作顏色。
- **Don't** 在訊息塊左緣加粗色條。
- **Don't** 把泊位板做成橫向捲動的 carousel。
- **Don't** 寫 `dark:` / `light:` 變體——token 在兩個主題換值，版面不該知道現在是哪個主題。
- **Don't** 加應用內的主題切換鍵：深色是預設，亮色跟隨 `prefers-color-scheme`。
- **Don't** 用字元當裝飾標記（`▸`、`•`、emoji）——它們會被算進無障礙名稱。要標記就用 CSS 畫。
- **Don't** 把色塊或文字直接疊在海報之類的圖像上（The Paint Needs A Painted Ground Rule）。
- **Don't** 把整塊網格塗成 `rule` 再靠 `gap-px` 透出格線，除非格數是固定的。泊位板可以（永遠四格），
  卡片牆不行——最後一排沒填滿時，空欄會變成一塊灰色的板子（票 03 實跑）。線交給每一格自己的 `border-2`。
- **Don't** 引入 webfont 或對外部字型服務發請求；離線可用是自架應用的底線。
- **Don't** 用 `break-all`：它會在英文詞中間斷行（`(S` / `TEP 4)`）。

## Known contradictions

- `.impeccable/surfaces/web-src-pages-setuppage-tsx.md`（票 05 的 Resolved 段）與
  `.impeccable/surfaces/web-src-pages-healthpage-tsx.md` 都描述亮色主題「同樣四個信號色，
  降明度提彩度以達 AA」。**程式碼沒有這樣做**：`web/src/index.css` 的亮色區塊只換中性色與
  `blocked-ink` / `secured-ink`，四個信號色與 `on-signal` 兩個主題共用（註釋寫明理由：
  白字配中明度色只有 3.6:1）。以 build 為準——本文件記錄的是共用漆的那一版。
  兩份 surface brief 的那句話已過時，尚未更新。
- 實測對比下限（票 10 與票 11 的瀏覽器實測）：泊位板標籤 6.67–9.63:1，
  登入頁 5.71:1（亮色）/ 6.53:1（深色），`rule-strong` 對兩個底色 6.4:1。
  這些是**現況的最低值**，不是目標值；新畫面仍以 AA 數值為驗收條件。
