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
    fontFamily: "ui-monospace, 'Cascadia Mono', 'Cascadia Code', 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "1.125rem"
    fontWeight: 600
    letterSpacing: "-0.015em"
  berth-name:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'Cascadia Code', 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "1rem"
    fontWeight: 600
    fontFeature: "tabular-nums"
  label:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'Cascadia Code', 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.18em"
  label-zh-hant:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', 'Microsoft YaHei', sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.05em"
  value:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'Cascadia Code', 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    fontFeature: "tabular-nums"
  value-small:
    fontFamily: "ui-monospace, 'Cascadia Mono', 'Cascadia Code', 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    fontFeature: "tabular-nums"
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', 'Microsoft YaHei', sans-serif"
    fontSize: "0.875rem"
    lineHeight: 1.5
  body-small:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', 'Microsoft YaHei', sans-serif"
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
  chip-compact:
    backgroundColor: "{colors.deck}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.125rem 0.375rem"
  tag-token:
    backgroundColor: "{colors.deck}"
    textColor: "{colors.ink}"
    typography: "{typography.value-small}"
    rounded: "{rounded.none}"
    padding: "0.125rem 0.375rem"
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
  wall-tile:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.value}"
    rounded: "{rounded.none}"
  wall-tile-band:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.value-small}"
    rounded: "{rounded.none}"
    padding: "0.625rem 0.75rem"
  row-summary:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.value}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1rem"
  row-expanded:
    backgroundColor: "{colors.hull}"
    textColor: "{colors.ink}"
    typography: "{typography.value-small}"
    rounded: "{rounded.none}"
    padding: "0.75rem 1rem"
  confirm-panel:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    typography: "{typography.body-small}"
    rounded: "{rounded.none}"
    padding: "0.75rem"
  page-title:
    textColor: "{colors.ink}"
    typography: "{typography.berth-name}"
    fontSize: "1.125rem"
  nav-box:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.625rem 1rem"
  nav-box-active:
    backgroundColor: "{colors.deck}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.625rem 1rem"
  language-key:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink-dim}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.625rem"
  language-key-active:
    backgroundColor: "{colors.deck}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.375rem 0.625rem"
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

- **hi-vis 調度黃 `assigned`**：「現在需要你」。精靈的所有主要動作按鈕、設定漂移的泊位格、
  待處理的纜繩都是它。它是整塊板上唯一的主要動作顏色——這塊板子沒有藍色 primary。

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
- **重橫線 `rule-strong`**：分區的重線、失敗時的邊框、主要按鈕的輪廓、輸入框的邊框。深色對 `deck` / `hull` / `well` 是 3.33 / 3.95 / 4.51:1，
  亮色 6.46:1（M2 票 16 的 audit 重量；之前寫的「兩個主題都 6.4:1」只對亮色），都滿足 WCAG 2.2 非文字對比 3:1。
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

**The Usual Stays Unpainted Rule（常態不塗漆，例外才塗）。** 一面牆、一張表、一份清單裡「沒事」的那些
不上信號色：媒體庫牆上的「完整 / 部分 / 空」是中性色塊，季表裡已入庫與未播出的集只是字，
只有下載中（`working`）、卡住（`assigned`）、失敗（`blocked`）才塗漆。已入庫的作品塗成 `secured`，
整面牆就是一面綠色勾勾牆；需要人的那幾格要靠「只有它們有顏色」才跳得出來。
審計測試：一份全部正常的清單在畫面上應該看不到任何一塊信號色。

## Typography

**Display Font:** 無。這個系統沒有 display 級別的字，最大的字是 Media 詳情的作品名（1.25rem，下面的例外），其次是 1.125rem 的應用名。
**Body Font:** 系統無襯線堆疊（`system-ui`、`Segoe UI`、`Noto Sans TC`、`PingFang TC`），只用於散文。
**Label / Value Font:** 系統等寬堆疊（`ui-monospace`、`Cascadia Mono`、`SF Mono`、`Menlo`、`Consolas`）。

**Character:** 貨櫃編號的語域。標籤、代號、路徑、版本號、inode、時間全部等寬且 `tabular-nums`，
在表格裡對得齊；只有真正的句子才落回系統無襯線。不載入任何 webfont——離線可用是自架應用的底線，
「模板噴字」由字距、橫線與色塊承載。

### Hierarchy

- **App name**（mono，600，1.125rem，`tracking-tight`）：頁首的 `Berth`，每一頁只有一個。
- **Berth name**（mono，600，1rem）：泊位格裡的服務名。板上唯一比內文大的字。
- **Value**（mono，400，0.875rem，`tabular-nums`）：實測值、服務名、檢查項名稱、牆卡片與下載列上的作品名與發佈名。
- **Value small**（mono，400，0.75rem，`tabular-nums`）：端點、路徑、位址、錯誤原文、指令列、
  列上中點分隔的實測值那一行、Tags 詞彙。
- **Label（Latin）**（mono，600，0.6875rem，`0.18em`，全大寫）：模板字。狀態標籤、欄位名、
  面板抬頭、按鈕文字、導覽項、區塊標題、「展開 / 收起」提示。
- **Label（zh-Hant）**（sans，600，0.6875rem，`0.05em`，不轉大小寫，前置塗刻度）：同一個角色的中文版。
- **Body / Body small**（sans，0.875rem / 0.75rem）：說明、提示、修正步驟、確認說明的散文。上限 `max-w-prose`。

頁面與區塊的標題不另立一階大字：下載列表、探索牆、搜尋、檔案這些區塊的 `h1` / `h2` 都是
`.label` 模板字壓在一條 `border-b-2 border-rule-strong` 重橫線上，旁邊跟一個 `.value text-xs` 的計數。
唯一的例外是 Media 詳情的作品名（sans，600，1.25rem）——那是一張提單的抬頭，而它是散文而不是代號。

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
頁首之前有一條 skip link（平常 `sr-only`，拿到焦點才以 `deck` 底 + `rule-strong` 框浮在左上角），
跳到 `main#main`（`tabIndex={-1}`，焦點真的落在內容上，下一個 Tab 才從內容開始）。

**泊位板橫幅。** 四格等寬，格與格之間是 1px `gap-px`（底色 `rule-strong` 透出來當線，不是 border）。
窄螢幕 `grid-cols-2`（2×2），`sm`（640px）以上 `grid-cols-4` 一列四格。欄數寫死，因為泊位就是那四個。
目前的那一格用 `aria-current="step"` 與一條 `inset 0 -3px currentColor` 的底線標出來——用 `currentColor`
而不是第五個顏色，因為四塊漆上的字色本來就是為了在那塊漆上讀得出來而選的。

**工作面。** 精靈每一步是 `lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]` 的兩欄（左剖面、右纜繩），
`gap-px` 上鋪 `bg-rule` 讓縫隙自己變成分隔線；`lg` 以下疊成單欄。健康頁內文是 `max-w-3xl` 置中。
登入頁是 `max-w-[26rem]` 的單一登船口窗格，用 `my-auto` 而不是 `items-center` 置中——矮螢幕
（手機橫放且開了鍵盤）上 flex 置中會把上緣切掉且捲不回去。

**頁寬。** 三種寬度，由頁面的工作決定：掃視用的牆（探索、媒體庫）`max-w-[110rem]`；
決策與清單（Media 詳情、下載列表）`max-w-[80rem]`；設定（健康、Route 設定）`max-w-3xl`。
外緣一律 `px-6 py-8`。

**牆（堆場）。** 探索與媒體庫共用同一份欄數（`WALL_GRID`）：窄版 2 欄、`sm` 3 欄、`lg` 4 欄、`xl`（1280px）6 欄，
`gap-0`，格線由每一格自己的 `border-2` 畫。窄版兩欄而不是一欄——一欄時一屏只看得到一部作品，而這一頁的工作是掃視。
媒體庫的格子必須與探索牆對得齊，所以斷點只有一份。

**提單（Media 詳情）。** 上方身分帶（海報 `7rem` / `sm` 以上 `11rem` + 標題與一行識別值，主按鈕、簡介與新鮮度在
`sm` 以上接在右欄、窄版整寬；底下一條 `border-b-2 border-rule-strong`），下方整寬堆疊：**觀看**（作品在 Jellyfin 裡、
這個人看得到時才有）→ 搜尋 → 季集與入庫 → 檔案與版本 → TMDB 標示（M1.5 票 08，`.scratch/m1.5/media-detail-shape.md`）。
**後一票往區塊裡填，不重排這個順序**。整寬是為了五欄的結果表——它在一個 5:7 的右欄裡讀不完。

**節奏。** 內部間距只有幾階：色塊 `0.375rem 0.5rem`、列與面板 `0.75rem 1rem`、頁面外緣 `1.5rem`、
區塊之間 `1rem`–`1.5rem`、頁面上下 `2rem`。列與列之間用 `gap-3`（0.75rem）或 1px 的線。
牆卡片與列內的小色塊是一階更緊的 `0.125rem 0.375rem`。

**手機。** 主要動作在窄版固定於底部安全區之上（`sticky bottom-0` + `env(safe-area-inset-bottom)`，
`-mx-6` 讓它橫跨整個工作面），`lg` 以上恢復成一般行內按鈕。長字串一律換行，不橫向捲動——
被切掉的建議值等於沒顯示。**機器字串（`.value` 的發佈名、路徑、資料夾名、原文錯誤）用 `wrap-anywhere`
（`overflow-wrap: anywhere`），散文用 `break-words`。** 差別是實測出來的：`break-words` 不改變
flex / grid 子項的最小寬度，一串沒有空格的發佈名在 390px 上仍然把整頁撐出橫向捲動（票 15 量到 67px）；
`anywhere` 會把可斷行點算進 min-content。flex / grid 子項另加 `min-w-0`——grid 項目的 `min-width`
預設是 `auto`，展開的集表曾把整頁撐到 560px。

**窄版的收法。** 窄版不畫的欄用 `hidden sm:table-cell` 收掉，值改成發佈名底下一行中點分隔（`Dot`）的
`.value text-xs`，**一份 DOM 兩種版面**——`display: none` 的東西不進無障礙樹，螢幕閱讀器在任何寬度下
只讀到一份。沒有欄頭的那一行，每一格要自己說出它是什麼（「大小 1.2 GiB」而不是裸的「1.2 GiB」）。
下載列與季表在窄版讓發佈名 / 季名自己佔一行（`basis-full`，`sm` 以上回到 `flex-1`）：與色塊擠在同一行時
它會被壓成幾個字寬的直欄。自己會橫向捲動的只有一個東西：展開後的集表那一格（`overflow-x-auto`），不是整頁。

### Named Rules

**The Board Never Scrolls Rule（板不捲動）。** 泊位板永遠四格全在畫面內：窄版 2×2，桌機一列四格。
不做橫向捲動的 carousel——BTH 3 與 BTH 4 捲到畫面外時，「一眼看出哪一格紅了」這塊板存在的理由就沒了，
而且捲動容器會變成一個沒有名字的 Tab 停留點。

**The Values Sit On Their Line Rule（值貼在它那一行）。** 實測值、端點、鍵名貼在它所屬的那一列，
不進散文。剖面（`Cutaway`）是 `dt` / `dd` 的兩欄表，不是段落。

**The Failure Expands In Place Rule（失敗就地展開）。** 任何失敗都在它自己那一列的下方就地展開
（服務回的原文 + 修正說明 + 可複製指令），其他列不動、不跳頁、不開 dialog。二次確認同樣就地展開
成一段說明加兩顆按鈕。

**The Focus Follows The Confirm Rule（確認就地展開，焦點跟著走）。** 確認不是 dialog，瀏覽器不會替它管焦點，
所以每一個就地確認都走 `useInPlaceConfirm` 加 `ConfirmPanel`：展開時焦點進到確認區塊（`role="group"` + `tabIndex={-1}`，
`aria-labelledby` 指向那段後果說明，螢幕閱讀器才念得到）；取消或 `Esc` 收起時焦點回到觸發鍵；
`Esc` 會 `stopPropagation`，只收起確認，不連帶收起它所在的 `<details>`。確認之後整塊被換掉時
（送單成功），焦點落在接下來最可能要按的那條連結上。沒有這幾步，焦點掉回 `body`，鍵盤使用者得從頁首
重新 Tab 一遍（票 15 實測）。確認裡要重述會被寫死的東西：送單的確認印出 Route 名與資料夾名，
因為選 Route 的下拉早就捲出畫面了。

**The Focus Takes The Next Row Rule（列消失，焦點落在接替的那一列）。** 工作清單上處理完的那一列會消失，按下去的
那一顆跟著它一起走——`useInPlaceConfirm` 只管得到「取消」那條路，成功之後觸發鍵已經不在了。所以會讓列消失的清單，
在**不會跟著清單消失的那一層**掛 `useFocusAfterRemoval` 的 callback ref：焦點掉回 `body` 時，改落在接替那個位置的
那一列（列是 `<article tabIndex={-1}>`）；一列都不剩時落在那一層裡的 `<h1 tabIndex={-1}>`，沒有 `<h1>` 的（媒體庫的
子集）落在那一層自己（`tabIndex={-1}`）。只在焦點**真的掉了**時動手：使用者自己點到別處、或確認收起時焦點回到觸發鍵，
都不會被搶走。畫面上已經沒有東西說「成了」，所以同一層另有一行 `sr-only` 的 `aria-live` 說結果。沒有這一步，
清一件就要從頁首重新 Tab 一次（M2 票 16 的 critique）。

**The Needs-You Floats Up Rule（需要你的事浮到摘要層）。** 需要人處理的事不能藏在展開之後才看得到。
一筆已入庫、卻有 medium 自動入庫檔案待人看一眼的 Job，狀態色塊照樣是綠的「已入庫」，旁邊另塗一塊
`assigned` 的「N 個待確認」——兩件事各一塊，同樣出現在媒體庫牆的標識帶上。Route 設定頁的紅燈與停用列
預設展開，綠燈的收起。審計測試：一整份收起的清單，要能直接數出有幾件事在等你。

**The Summary Is One Button Rule（摘要只是一顆按鈕）。** 可展開的列用原生 `<details>`，而 `<summary>`
本身就是一顆按鈕：它裡面不放連結或任何互動元素——下載列的作品連結因此在展開區裡，不在摘要列上。
`summary` 的 marker 拿掉了（它在窄版會把整列推歪），所以列要自己用 `.label text-ink-dim` 說出
「展開 / 收起」（Route 設定頁是「管理 / 收起」）；這兩個字是 i18n key，不是三角形字元。

## Elevation & Depth

**這個系統沒有陰影，也沒有 z 軸。** 深度完全由三件事表達：中性色階（`well` 下沉 / `hull` 底 /
`deck` 抬起）、`border-2` 的橫線與 `border-b-2 border-rule-strong` 的重分區線、以及 1px `gap-px`
縫隙透出的線。沒有卡片浮起、沒有發光、沒有漸層、沒有 `backdrop-filter`。

程式碼裡只有兩處 `box-shadow`，兩處都不表達深度：焦點環的外圈，以及泊位板目前那一格的
`inset 0 -3px 0 0 currentColor` 底線——那是一條畫在格子裡的線，`inset` 讓它不佔版面、格子不會跳。

展開區一律往下沉一階：列本身是 `well`，展開的時間線、集表、檔案清單是 `hull`，中間一條 `border-t-2 border-rule`。
列內的子項（計劃的逐檔列、時間線的每一筆、檔案、版本組）是左側一條 `border-l-2` 加 `pl-3` 內縮——
它們在同一塊展開區裡，長得一樣才不會被讀成兩種東西。這條是結構線，不是訊息塊左緣的粗色條：
它永遠是中性的 `rule` / `rule-strong`，從不塗信號色。

**焦點環。** `outline: 2px solid var(--color-ink)` + `outline-offset: 2px` + `box-shadow: 0 0 0 2px var(--color-hull)`。
雙環是刻意的：焦點會落在四塊漆上（黃色按鈕、狀態色塊），任何單一顏色都會在其中一塊漆上消失；
內圈用底色、外圈用字色，兩個主題、四塊漆上都至少有一圈看得見。選擇器涵蓋
`a, button, summary, input, select, textarea, [tabindex]`——`summary` 是後補進去的，
少了它 `<details>` 會落回 Chrome 預設的 0.67px 焦點環。

**動態。** 沒有轉場、沒有動畫類別。署名互動「靠泊序列 / 複驗序列」是逐條纜繩換狀態，不是 spinner
也不是動畫；每完成一條就把實際結果數值留在旁邊。`prefers-reduced-motion: reduce` 下全域把
`animation-duration` 與 `transition-duration` 壓到 0.01ms，這是防護欄而不是效果開關。
讀取中的佔位（牆的空格、下載列的空列、詳情頁的海報位）是**不動的** `deck` 色條，沒有骨架屏動畫；
空位格**與真的那一格一樣高**（`TilePlaceholder` 的每一行照卡片的行高抄，M2 票 13）：差幾 px 資料到的那一刻就是一次版面位移。
下載列表透過 SSE 自己更新，沒有「即時」指示器也沒有脈動點——值自己換就是訊號。
搜尋那 35–85 秒裡動的是纜繩：先鋪出要問的關鍵字（`working`），有結果就換成筆數。

### Named Rules

**The Rule-Line Rule（以線分層）。** 分層一律用線與色階，不用陰影。需要「抬起」時換 `deck`，
需要「下沉」時換 `well`，需要「這是另一個區塊」時加 `border-2 border-rule`，需要「這是分區」時
加 `border-b-2 border-rule-strong`。`box-shadow` 只允許出現在焦點環，以及當成畫在元素內部的線。

**The Heavier Line Rule（要人看的線變重，不是變紅）。** 一列需要注意時，它的框或左線由 `rule` 換成
`rule-strong`：失敗的下載列、計劃裡待審核 / 對不到 / 待確認的檔案、Media 詳情裡對不到的檔案、
紅燈或停用的 Route 列、展開中的確認區塊。紅色只留給那一列的狀態色塊（The One Meaning Rule）；
hover 與焦點也是同一個語彙（牆卡片、Ghost 按鈕、導覽方塊的線變重）。

## Shapes

**這塊板子沒有圓角。** `--radius-none: 0`，全站無例外——按鈕、輸入框、色塊、面板、訊息塊、指令列
一律直角。形狀語彙只有矩形與線：塗滿整格的矩形色塊、2px 的框、1px 的縫。

**色塊是填滿的，不是描邊的。** 狀態一律是塗滿的矩形加深墨字，不是彩色外框加彩色字。
唯一帶框的色塊是主要按鈕——亮色主題下黃漆對紙白只有 1.36:1，沒有 `border-rule-strong`
按鈕輪廓就看不出來（WCAG 2.2 非文字對比 3:1）。

**沒有圖示。** 系統裡沒有 icon font、沒有 SVG 圖示集。唯一的非文字標記是中文標籤前那道 2px 塗刻度，
它由 CSS 畫出來、不是字元、不進無障礙名稱。唯一的圖像資產是 TMDB 條款要求的標誌（一份 `components/TmdbAttribution.tsx`，替代文字走 i18n），與作品海報（TMDB 的，或 Berth 代理的 Jellyfin 的）。

**海報是 2:3 的矩形。** `aspect-[2/3]` + `object-cover`，底是 `hull`；沒有海報時同一塊矩形裡印一行
`.value text-xs text-ink-dim` 的「無海報」（EN `NO ART`，`discover.noArt`），格子高度不變。媒體庫牆上**圖載不下來**（Jellyfin 回 404、連不上）
也換成同一行（M1.5 票 04）——不留瀏覽器的破圖示。**繼續觀看與下一集的圖是 16:9**（`aspect-video`，M1.5 票 07），
沒有合用的橫圖時同一塊印「無圖」（EN `NO ART`）。兩種形狀、所有用到圖的地方（牆、繼續觀看與下一集、集卡、詳情頁身分帶）是同一個元件
（`components/ArtSlot.tsx`，外框由呼叫端的 `className` 給；M2 票 13 收掉了詳情頁那一份 `Poster.tsx`）。**每一張圖帶 `srcset`**
（M2 票 13）：Berth 代理的圖給 342 與 684 兩個寬度（`poster` / `poster_large`、`wide` / `wide_large`），TMDB 的海報給
`w185`–`w780` 四個；`sizes` 照 `WALL_GRID` 的斷點（`WALL_SIZES`，改一邊就改另一邊）或詳情頁那一欄的寬。

## Components

### Buttons

- **Shape:** 直角（`0`），`border-2`。
- **Primary（`PrimaryButton`）:** `assigned` 黃漆填滿 + `on-signal` 深墨字 + `rule-strong` 邊框，
  `padding: 0.875rem 1rem`，`.label` 模板字，寬度滿版。停用態換成 `deck` 底 + `ink-dim` 字，
  `cursor: not-allowed`。整個系統只有這一種主要動作外觀。放進窄欄時由外層限寬（`sm:max-w-xs`、`lg:w-40`、
  確認區塊的 `minmax(0,14rem)`），元件本身永遠滿版。
- **Ghost（`GhostButton`）:** 只有 `rule` 外框與 `ink` 字，`padding: 0.625rem 1rem`。
  hover 時邊框換 `rule-strong`——次要動作不靠顏色搶位置，靠線變重。導到別頁的次要動作是
  `GHOST_LINK`：同一個外觀的連結，不是一顆包著連結的按鈕。Job 詳情頁的次要動作（重試、重新規劃、重新入庫）
  `justify-items-start`，不佔滿整條——滿版是主要動作的形狀。
- **按了還在跑:** 按鈕多半不停用，只換文字（「搜尋」→「搜尋中…」）；說不行的是旁邊那句話或欄位本身。
- **Focus:** 全域雙環（見 Elevation & Depth），元件不自帶焦點樣式。
- **命中面積:** 互動元件不得小於 24×24 CSS px，或與鄰近目標保持 24px 間距（WCAG 2.2 AA 2.5.8）。
  密碼欄的「顯示」鍵曾是 38.6×15px 且距輸入框 11.5px，兩條都不成立，現在是 `min-h-6 min-w-6`。
  語言鍵兩顆之間只有 1px 縫，間距例外不成立，所以每顆 `min-h-6`（票 15）；季表裡「卡住」那塊可點的色塊、
  媒體庫卡片的 Jellyfin 連結同樣 `min-h-6`。

### Chips（狀態色塊）

- **Style:** `.label` 模板字 + `padding: 0.375rem 0.5rem`，信號色填滿 + `on-signal` 深墨字。
  中性色塊（角色、語言未選中）用 `deck` + `ink`。
- **Compact:** 牆卡片標識帶、列內的分類（trigger、處置、計劃狀態、「已追蹤」）用 `0.125rem 0.375rem`
  的小一號色塊；時間線的事件型別與預估說明是 `0.25rem 0.375rem`。
- **Tag token:** 解析出的 Tags（`WEB`、`1080p`、`CHS+CHT`）是 `deck` 底的 `.value text-xs`，不是 `.label`——
  它們是詞彙表不是文案，`.label` 會把 `1080p` 大寫掉。
- **分類 vs 狀態:** 事件型別、trigger、處置、信心、計劃狀態、停用都是分類，一律中性；
  「判斷不出來」是一句話不是分類，不給色塊，免得看起來像個結論。
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
  標題層級由 `level` 屬性決定（預設 `3`）：精靈裡它在步驟的 `h2` 底下，Media 詳情裡它緊接著 `h1`，
  所以那裡傳 `level={2}`——標題層級跟著它所在的頁面，不跳級（票 15 audit）。
  機器字串在 `dd` 而 term 是角色名的列（「資料夾名」）照樣用 `.label` term。
- **區塊標題:** 頁內每個區塊是 `.label text-ink` 的標題 + 可選的 `.value text-xs text-ink-dim` 計數，
  壓在 `border-b-2 border-rule-strong pb-2` 上；沒有名字的 `section` 用 `aria-labelledby` 接上標題。
  只有數字的計數，看得見的是數字（`aria-hidden`），聽得見的是帶單位的那一句（`sr-only`）。
- **空狀態:** `well` 底 + `rule` 框的一塊，一句 `ink` 散文加一條 `GHOST_LINK` 下一步。空不是錯誤。

### Inputs / Fields

- **Style:** `hull` 底 + `border-2 border-rule-strong` + `.value` 等寬字，`padding: 0.625rem 0.75rem`。
  標籤在上方，`.label text-ink-dim`。**邊框是 `rule-strong` 不是 `rule`**：欄位常放在同樣是 `hull` 的
  展開區裡，邊框是「這裡可以輸入」的唯一線索，而 `rule` 對 `hull` 只有 2:1，低於 WCAG 1.4.11 的 3:1
  （M2 票 16 的 audit 量到的；`rule-strong` 深色 3.95:1、淺色 6.46:1）。
- **Focus:** 邊框換 `ink`，外加全域雙環。
- **Error:** 邊框換 `blocked`，`aria-invalid`，錯誤訊息以 `role="alert"` + `aria-describedby` 掛在欄位下方，
  文字用 `blocked-ink`。
- **Disabled:** `well` 底 + `ink-dim` 字。
- **Checkbox:** 原生 `input[type=checkbox]`，`accent-color: var(--color-assigned)`，`size-4`。
- **Select:** 原生 `select`，與輸入框同一套外觀（`hull` + `border-2 border-rule` + `.value`）。
- **元件基礎:** 原生 `input` / `button` / `checkbox` / `select` / `details`。到 M1 為止仍沒有任何需要
  Radix 行為的元件（無 dropdown / dialog / popover / tabs），原生的無障礙比重寫一份好。要 shadcn/ui 時再引入。

### Navigation

- 頁首導覽項是 `.label` 模板字 + `border-2 border-rule` 的外框方塊。當前頁用**重橫線加 `deck` 底**
  標出（`border-rule-strong`），不靠顏色——狀態不只靠顏色是產品層級的無障礙底線。
- 導覽包在 `<nav aria-label>` 裡，是一個地標；頁首之前有 skip link（見 Layout）。
- 同一個方塊（`NAV_BOX` / `NAV_BOX_ACTIVE`，不含內距）也是設定的子分頁列（`SettingsTabs`，`0.5rem 0.75rem`，
  自己一個 `<nav>`）、媒體庫的 Route 切換列與篩選列（篩選小一號，`0.375rem 0.75rem`）。內距由呼叫端給一次。
- **路由的 `Link` 用 `NAV_LINK`**（M2 票 13）：當前那一格由 TanStack 自己掛的 `data-status="active"` 換漆
  （`data-[status=active]:`），不用 `activeProps`——它的 class 是**接在後面**的，當前那一格同時帶 `border-rule` 與
  `border-rule-strong`，誰贏看 CSS 的產生順序。按鈕（`aria-pressed` 的季切換、只看缺集）照舊二選一 `NAV_BOX` / `NAV_BOX_ACTIVE`。
- **篩選列選著的那一個不是連結**，是一段 `aria-current="true"` 的字（`NAV_BOX_ACTIVE` 的外觀）：`Link` 當前時一定掛
  `aria-current="page"`，而同一頁的切換列已經有一個「當前頁」；篩選是這一頁裡的一組選項，不是另一頁。
- 可排序的欄頭同樣靠線：選中的欄頭 `border-b-2 border-rule-strong` + `ink` 字，`aria-sort` 掛在 `th` 上。
- `設定` 只對 `admin` 顯示；角色本身以中性色塊呈現，讓 `user` 知道自己為什麼沒有那顆按鈕。
- 語言鍵（`LanguageToggle`）是 `role="group"` 加兩顆 `aria-pressed` 按鈕，選中那顆是 `deck` 底 + `ink` 字
  （同角色色塊的中性方塊），未選中沉一階到 `well` 底 + `ink-dim` 字，兩顆之間 1px 縫。語言是角色不是狀態
  （The Role Is Not A State Rule），所以這裡沒有信號色；閘門是 `LanguageToggle.test.tsx`。
- **文字連結:** `underline decoration-rule-strong underline-offset-4`，hover 時底線換 `ink`。

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
「精靈當時是綠的、現在紅了」在畫面上是同一種東西。搜尋 torrent 時每個關鍵字也是一條纜繩。

### 牆卡片（`MediaTile` / `InventoryTile`，底行外框 `Tile`）

一格是一個貨櫃：上方 2:3 海報是塗裝，下方標識帶是噴在箱體上的編號——同一個語彙，不是「圖片加說明文字」。
- **框:** 每一格自己的 `border-2 border-rule` + `well` 底；hover / focus 時框換 `rule-strong`。不用整塊塗底再透 `gap-px`。
- **海報:** `alt=""`——標題就在下面那一行，給它 alt 只會讓同一個名字念兩次。TMDB 的海報**跟著 UI 語言換**
  （M1.5 票 11，與標題挑同一輪）；Jellyfin 代理的那一張不分語言。
- **標識帶（`0.625rem 0.75rem`）:** 第一行是 `.value text-xs text-ink-dim` 的類型代號 `Dot` 年份，後面接色塊；
  第二行作品名（`.value text-sm`，`line-clamp-2`，`min-h-10` 讓兩行名與一行名的格子一樣高）；
  原文 / 英文標題不同時第三行 `ink-dim`。狀態色塊貼在這條帶上，不壓在海報上。
- **探索牆:** 整格是一條連結；「已追蹤」是中性小色塊。
- **底下多一行控制項的那一種是同一個元件**（`components/Tile.tsx`，M2 票 14）：媒體庫牆的卡片與觀看區的集卡——圖與標識帶
  一條連結、底行（`min-h-10`、`border-t-2`）在連結外面並排，框的 hover 用 `has-[a:…]`。探索牆的 `MediaTile` 與首頁的
  `WatchingTile` 整格一條連結、沒有底行，不走它；共用的是 `ArtSlot`。
- **一面牆是一份清單**（M2 票 13）：探索牆、媒體庫牆、繼續觀看與下一集、集卡的容器都是 `<ul>`、一格一個 `<li>`，作品名都是 `<h3>`
  （牆的標題是 `h2`）。**整格連結的名字是作品名**（`aria-label`），類型年份與狀態、看到哪、盤點是 `aria-describedby`：
  整格的字串起來是「無海報 TV 2022 …」，控制項清單裡每一條都從代號念起。繼續觀看與下一集、集卡的名字是「作品名 S01E04 集名」。
- **媒體庫牆:**（M1.5 票 03 起一個 Jellyfin 媒體庫一頁；M2 票 13 起一頁 50 部——100 部的牆量到 1,700 個 DOM 節點、
  222 個 Tab 停留點，`.scratch/m1.5/library-shape.md`）
  Jellyfin 裡的作品顯示 Jellyfin 的名稱、沒有第二行，海報是 Berth 代理的 Jellyfin Primary 圖（票 04）；Berth 經手的才有狀態色塊，依 The Usual Stays Unpainted Rule
  （失敗 `blocked`、待審核 `assigned`、下載中 `working`，完整 / 部分 / 空是中性），有待確認檔案時另一塊 `assigned`；
  盤點行（「已入庫 N / 已播出 M」或版本數）在沒經手的作品上留空但保留高度。還沒進 Jellyfin 的 Berth 作品是牆上方
  自己一條（`.label` 標題 + 數字壓在重橫線上，同一份 `WALL_GRID`）。分頁鍵是 Ghost 外觀的連結，到頭的那一顆是
  `aria-disabled` 的 `ink-dim` 字、位置不變。牆上下各一組分頁，**兩個 `<nav>` 名字不同**（「分頁」「牆底的分頁」）。
  海報與標識帶連到 Media 詳情（沒有 TMDB id 的作品那一塊不是連結），底下 **Jellyfin 那一行**是同一格裡、並排不巢狀的另一條連結：
  `border-t-2 border-rule`、`min-h-10` 固定高度讓基線對齊；找到了是 `.label` 文字連結（開新分頁）。**每一格都有這一條，
  名字帶上作品名**（「在 Jellyfin 開啟：The Bear（開新分頁）」，M2 票 13、plan §11.3 的二選一；看得見的字仍是名字的開頭，
  WCAG 2.5.3）——只靠 `aria-describedby` 區分的話，控制項清單是一整排同名的連結。還沒找到就說原因
  （掃描中 / 沒有位址 / 找不到），不給死連結。框的 hover 用 `has-[a:hover]` 跟著任一條連結變重。
  **觀看狀態**（M1.5 票 05）：Jellyfin 那一頁的卡片在名稱與盤點行之間多一行 `.value text-xs text-ink` 的字——「已看」
  「看到 42%」「剩 4 集沒看」，不塗漆也不畫勾（它不是 Berth 的狀態，The Usual Stays Unpainted Rule），沒話說時留空但保留高度。
  Jellyfin 那一行多一顆「標為已看 / 未看」：比 Ghost 小一號（`border-2 border-rule`、`px-2 py-1`、`min-h-6`），整行
  `flex-wrap`，窄的時候換到深連結下一行。**清得掉東西的那一下走就地確認**（`useInPlaceConfirm` + `ConfirmPanel`）：標為未看、
  看到一半的集或電影標為已看（位置歸零）、整部劇標為已看（每一集的位置都歸零；票 08 使用者拍板）；沒進度的集或電影標為已看
  一按就送。同一顆鍵（`components/WatchToggle.tsx`）也在 Media 詳情的集卡與電影主按鈕旁；牆與集卡上的那幾顆名字帶上
  是哪一部、哪一集（`subject`：「標為已看：The Bear」）。確認區塊佔滿那一行、
  兩顆鍵**永遠疊成一欄**（卡片再寬也只有十幾 rem，`ConfirmAction` 的 `sm:` 兩欄在卡片裡會溢出）。送出中這一顆不停用、
  只換字（停用的鍵接不住確認收起時送回來的焦點）。
  **排序與篩選**（M1.5 票 06）：篩選列同一排接兩組 `.label` + 原生 `select`——「排序」與「方向」（M2 票 13 起方向也有
  看得見的標籤，不是只有 `aria-label`；輸入框那一套外觀，小一號 `px-2 py-1`）
  與「類型」「年份」兩顆開關（篩選方塊的外觀；選了東西就是當前那一種重線 + `deck` 底，數字 `aria-hidden`、`sr-only` 說「已選 N 個」，
  後面 `ink-dim` 字說「展開 / 收起」，狀態靠 `aria-expanded`）。勾選清單畫在整列控制項**下方**（`well` 底 + `rule` 框、`.label` 標題、
  原生勾選框、`repeat(auto-fill,minmax(9rem,1fr))`），一次開一份，勾了就換網址、焦點留在那一格（換網址時牆先留著上一份，
  不換成空位格）。**不用 `<details>`**：內容只能長在它自己裡面，展開時旁邊的開關被擠到下一行、清單困在半欄寬（票 06 實跑）。
  「待審」「Unmatched」時整組不畫；篩類型或年份時「還沒進 Jellyfin」那一條不畫。

### 橫卡（`WatchingRows`，繼續觀看與下一集）

M1.5 票 07（`.scratch/m1.5/watching-shape.md`）。**橫放的貨櫃**：16:9 的圖是塗裝（`aspect-video`，Berth 代理的 Jellyfin
Thumb / Backdrop / 劇照），下方同一條標識帶，框與底同牆卡片（`border-2 border-rule` + `well`、hover 換 `rule-strong`）。
- **兩列在頁面上方**：首頁在搜尋列之上、直接攤開（搜尋時不收起，打字時輸入框不跳）；媒體庫頁在切換列與「還沒進 Jellyfin」
  之間，**收成一行「接著看 N 項」**（M2 票 14：`NAV_BOX` 小一號的開關、`aria-expanded`，展開才畫兩列、換頁面不記住；讀取中照
  上一次的形狀佔那一行），只在第 1 頁、沒有篩選時畫；翻頁或篩選時那個位置是一行 `text-xs ink-dim` 的「繼續觀看與下一集只列在第 1 頁、沒有篩選的時候」
  加一條「到第 1 頁看」（M2 票 13），**只在這個人上一次在這裡真的有東西可接著看時**說。每一列是區塊標題（`.label` + 計數，
  重橫線）加一份 `WALL_GRID`，格線與下面的牆對齊。
- **不橫向捲動**（The Board Never Scrolls Rule 的同一個理由）：收起時每一格帶「哪個寬度以上才出現」
  （第 3 格 `sm`、第 4 格 `lg`、第 5–6 格 `xl`、第 7 格起藏著），一份 DOM、不量寬度。標題列右邊一顆小一號的開關
  「全部 N 項 / 收起」（`aria-expanded`、`aria-controls`、`min-h-6`），在一行放得下的寬度以上 `display: none`。
  **開關在標題列不在清單下方**：展開之後下一個 Tab 從第一格往下走。
- **標識帶**：季集代號（`S01E05`，`episodes.ts`）或 `MOVIE` `Dot` 年份；作品名 `.value text-sm` 一行截斷；集名 `ink-dim`
  一行（電影留高度）；繼續觀看多一行 `text-ink` 的「看到 42%」（牆上觀看狀態那一句）。**不塗漆、不疊入庫狀態、不在圖上疊
  進度條**：每一格都已在 Jellyfin 裡，而進度不是 Berth 的狀態（The Usual Stays Unpainted Rule、The Paint Needs A Painted
  Ground Rule）。
- **整格是一條連結**，開 Jellyfin 那一集的詳細頁、新分頁；名字是「作品名 S01E04 集名（開新分頁）」（`aria-label`，M2 票 13），看到幾 % 是描述；主機推不出時整格不是連結，最下面一行說
  「不知道 Jellyfin 開在哪裡」。
- **讀取中照這個人在這一頁上一次的形狀佔位**（M2 票 13，推翻 watching-shape 的「讀取中不畫」：資料回來才插進來，
  下面整頁下移 440px，首頁 CLS 0.35）。上一次的列數存在 `localStorage`（`watching/rememberedRows.ts`，以使用者與頁面區分，
  讀不到就當沒有）；佔位是真的標題列（計數與「全部 N 項」看不見但佔高度）加一行不動的空位格，整塊 `aria-hidden`。
  第一次來沒有紀錄，不佔位。沒有內容的那一列不畫。首頁問不到 Jellyfin 時換成一行 `ink-dim` 的原因 + 原文 + Ghost「重試」，
  不用 `blocked` Notice 搶探索的位置；媒體庫頁不另外說（牆會說）。

### Media 詳情（提單）

- **身分帶:** 海報 + 作品名 `h1` + 英文標題（檔名用的那一個）+ 原文標題 + **一行識別值**（`.value text-xs text-ink-dim`，
  `Dot` 分隔：類型代號、首播 / 上映日、季數與集數（Specials 不算）或片長、`TMDB id`）；「已追蹤」中性色塊在標題上方。
  五列的 `Cutaway` 剖面在 M1.5 票 08 拿掉了——它把 1280×900 的「搜尋」壓到 y=984；資料夾名搬進搜尋區塊。
  接著是**主按鈕**（在 Jellyfin 裡才有）、簡介、快照新鮮度（`Timestamp` + Ghost「重新抓取」）；快照過期而 TMDB 連不上時是
  `assigned` 的 `Notice`，不是 `blocked`——頁面照樣畫得出來。
- **主按鈕（`CarryOn`）:** 一條黃漆的連結（主要按鈕的外觀，`min-h-12`、`sm` 以上 `min-w-64`），開 Jellyfin 那一集或那一部、
  新分頁；文字說是哪一集（「繼續看 S01E04」「看下一集 S01E05」「從 S01E01 開始看」，電影「在 Jellyfin 看 / 繼續看」，
  劇集看完了「在 Jellyfin 開啟」）。下面貼著一行 `.value text-xs text-ink`（集名 `Dot` 看到幾 %，或「全部看完了」），連結的
  `aria-describedby` 指著它。**在簡介之前**：簡介再長它都在第一屏。電影的「標為已看」在它旁邊（電影沒有觀看區）。
  整頁只有它是黃漆；不在 Jellyfin 時搜尋鍵才是唯一那一顆。
- **觀看（`WatchSection`）:** 區塊標題 `觀看` + 計數位置說「剩 N 集沒看 / 全部看完了」+ 靠右文字連結「在 Jellyfin 開啟」。
  兩季以上時一排導覽方塊（`NAV_BOX`，選中重線 + `deck` 底，`aria-pressed`，換行不捲動）切季，預設是主按鈕那一集的季、
  只在第一次決定（標記之後主按鈕換季，眼前這一季不跳）。集是**橫放的貨櫃**，與首頁兩列同一種、同一份 `WALL_GRID`：16:9 的
  劇照（**只取集自己的 `Primary`**，沒有就「無圖」，不借劇的圖）→ 季集代號（是主按鈕那一集時接中性小色塊「繼續看 / 下一集」）
  → 集名（`line-clamp-2`、`min-h-10`）→ 已看 / 看到幾 %（留高度）；上面那一塊是開那一集的連結，最下面 `border-t-2` 一行是
  `WatchToggle`，並排不巢狀。讀取中是一行不動的 `deck` 空位格；換季時先留著上一季（`placeholderData`，`aria-busy`）。
  問不到 Jellyfin 時整塊換成一行 `ink-dim` 原因 + 原文 + Ghost「重試」，不用紅色 Notice。
- **季表（`SeasonList`，區塊標題「季集與入庫」）:** TMDB 的季集與入庫狀態（觀看區的季是 Jellyfin 的，兩份各回答一件事）。
  每季一段**長清單段落**（下面一節），**預設全收**（一季可以是 1213 集，攤平的話永遠捲不到搜尋）；收起的季不渲染集列。
  季列之間是 `gap-px` 透出的 `rule`。摘要：`S01` 代號、季名、集數、「已入庫 / 已播出」、播出日、「展開 / 收起」。
  區塊標題正下方一行 `text-xs ink-dim` 說這一份是哪一套編號（M2 票 14）：「季與集照 TMDB 的編號，入庫的檔名也照這一份」，
  觀看區在時多一句「上面『觀看』的季與集是 Jellyfin 的，兩邊的編號可能不同」——這一頁有四套集數，一句都不說的話，
  從「對不到」進來的人會讀成 Berth 算錯了。電影與沒有季的劇集不畫。
  標題列下方一條**工具列**：`NAV_BOX` 切換鍵「只看缺集」（`aria-pressed`）+ 一行 `aria-live` 的「共缺 N 集 / 這部作品沒有缺集」；
  開著時每季摘要多一格「缺 N 集」（`ink`）或「沒有缺集」（`ink-dim`），展開的表只留缺的那幾列，沒有就一句話。缺只算
  `missing`（卡住、下載中、未播出都不算）。切換不改變哪幾季展開著。電影與沒有季的劇集不畫工具列。
  有缺集時工具列右邊多一顆 Ghost「搜這部作品缺的集」、每一季展開區第一行一顆「搜 S01 缺的集」（M1.5 票 10）：
  **按下去不在原地開結果**，而是把查詢交給上面那一個搜尋區塊、焦點移到它的 `h2`——同一頁只有一個搜尋結果的位置。
  搜尋區塊在缺集模式下換一句「這部作品 / S01 缺的那幾集，Berth 會這樣問：」，並多一顆「改回作品名搜尋」當出口。
  展開後是 `hull` 底的表，**欄序固定為集號 → 絕對編號 → 入庫 → 集名 → 片長 → 播出日**；集號寫 `S01E09`（M2 票 14，
  與觀看區的集卡、檔名同一種寫法，不是裸的 `E09`）；
  絕對編號只在有 Absolute group 時整欄出現（沒有時不留一整排 `—`）；片長與播出日在窄版不畫，同樣的兩個值收進集名底下一行
  （`sm:hidden`，帶「片長」「播出」字樣，M2 票 13）；表有 `sr-only` 的 `<caption>`「S01 的每一集」；
  入庫那一格 `whitespace-nowrap`。集的狀態依 The Usual Stays Unpainted Rule：下載中 `working`、卡住是一塊可點的
  `assigned` 連到下載列表，其餘是字（未播出 `ink-dim`）。
- **搜尋（`SearchPanel`）:** 待命，按了才搜。關鍵字欄 + Route 下拉 + 主要按鈕（`lg` 以上一列三格），
  底下先列出**會送出去的那幾個關鍵字**（`.value text-xs wrap-anywhere`）與「一次要 35–85 秒」，再下面是**資料夾名**
  （`dl`：`.label` term「資料夾將會是 / 資料夾是」+ `.value wrap-anywhere` 值，一行小字說它什麼時候定下來）。
  跑的時候是一串纜繩；**結束之後有回應的收成一個 `<details>`**（摘要一句「N 個關鍵字都有回應」，不塗漆，展開才逐條列筆數），
  垮掉的照舊一條一條畫在它上面、原文就地展開（The Needs-You Floats Up Rule；五條全綠的纜繩曾佔 287–315px）。
  結果到了有 `aria-live` 宣告筆數。窄版沒有欄頭，排序改成一個 `select`。
  **沒接索引站在按下去之前就說**（M2 票 13：`/search/queries` 先帶 `problem`），與按下去之後同一個位置、同一塊 Notice，
  只說一次。缺集模式下關鍵字欄的 placeholder 換成「留空就問缺的那幾集」。
- **結果表（`SearchResults`）:** `well` 底、`border-2 border-rule` 的真表格，抬頭列 `deck`。
  發佈名整行換行不截斷（`wrap-anywhere`）；底下是 Tags 詞彙列；窄版把大小 / 做種 / 來源站 / 預估收成一行 `Dot` 分隔；
  表外不包 `overflow-x`。來源站有集頁就是文字連結。
- **送單（`SubmitAction`）:** 住在發佈名那一格。Ghost「送單」→ 就地展開 `border-2 border-rule-strong` 的確認區塊：
  送到哪一條 Route、會被寫死的資料夾名（`.value wrap-anywhere`）、「這一按就定了」或「它已經是」，加主要 / 取消兩顆鍵。
  被擋下時在同一塊裡以 `role="alert"` 的 `blocked-ink` 說封閉集合的理由，原文接在下面。成功時整塊換成
  `secured` 色塊 + 「去看下載列表」連結（`role="status"`，焦點移到連結上）。
- **檔案與版本（`FilesPanel`）:** 劇集**依決定分組**（處置 × 季，各是一段長清單段落，預設全收），電影不分組。
  組的摘要：處置中性小色塊 + `S01 E01–E28`（`.value text-sm`）+ `Dot` 分隔的檔案數、「帳本對得上 / N 個帳本對不上」、
  只算正片的「Jellyfin 已收錄 / 掃描中 / 找不到 N」（是 0 的不說，字幕與特典整組都沒有這一格）。帳本對不上或
  Jellyfin 找不到的組排最前、左線 `rule-strong`。展開一組才逐檔列出。一個檔案是一條逐檔列（`FileEntry`）：
  摘要是季集 `.value text-xs` + 目標檔名（`wrap-anywhere`，資料夾整組共用所以只留最後一段）+ 例外；
  「Tags」與「目標」+ 完整路徑收在它自己的展開區裡。**組說過而且是常態的不重複**——處置是組鍵的一部分，
  帳本「對得上」與 Jellyfin「已收錄」由組的計數說；帳本對不上、還在掃描（帶下一次查詢時間）、反查試了幾次
  留在列上，因為組數得出幾個卻說不出是哪一個。電影不分組，上面沒有人說，所以那幾格全部留在列上。
  版本組說 Jellyfin 算出的版本名；對不到的檔案排在最後，左線 `rule-strong`，
  帶一條到下載列表的 `GHOST_LINK`。常態也說一句（「沒有多版本」），空白與沒畫出來不能長得一樣。

### 下載列（`JobRow`，船期表的一列）

- **外殼:** 原生 `<details>`，`well` 底 + `border-2`；失敗那一列框換 `rule-strong`。列之間 `gap-3`。
  排序純粹最新在前，失敗不置頂。
- **摘要列:** 狀態色塊（十六個狀態映射到四色 + 中性，`jobState.ts` 的 `JOB_SIGNAL`）；有待確認檔案時旁邊另一塊
  `assigned` 的「N 個待確認」；靠右的「展開 / 收起」（`sm` 以上排到最後）；發佈名（`.value text-sm wrap-anywhere`，
  窄版自己一行）；底下一行 `Dot` 分隔的實測值：作品 · Route · trigger 中性小色塊 · 大小 · 進度 · 相對時間 · hash 前 12 字。
  作品在這裡只是字。進度沒有值時是 `—` 不是 `0%`。
- **展開區（`hull` 底，`border-t-2 border-rule`）:** 作品連結（`.label` 標記 + 文字連結）→ 時間線摘要（最近三段，
  上面一句「較早的 N 筆事件在詳情頁」）→ 整串 hash 的 `CopyLine` → 「下載詳情」`GHOST_LINK`。時間線展開時才請求。
  **計劃與動作不在這裡**（M2 票 12）：它們只在 `/jobs/:hash`。
- **Job 詳情頁 `/jobs/:hash`（M2 票 12）:** `max-w-[80rem]`。回下載列表（`GHOST_LINK`）→ 身分帶（狀態色塊 + 待確認色塊、
  `h1` 是發佈名（`PAGE_TITLE` + `wrap-anywhere`）、同一行實測值（作品在這裡是連結）、待審核時一條到 `/review` 的
  `GHOST_LINK`（不是管理員時換成一行 `ink-dim` 說在等管理員）、`dl` 的送單的人 / 服務原文（`blocked-ink`）/
  hash（`CopyLine`），每一格是工作清單列的那個 `DetailLine`，底下一條 `border-b-2 border-rule-strong`）→ 動作（Ghost 一排；刪除自己一行、確認區 `max-w-3xl`、就地展開在
  身分帶正下方）→ `lg` 以上 `7fr / 5fr` 兩欄：左「檔案與決策」（`JobPlan`）+「計劃歷史」，右「時間線」；窄版照同一順序
  疊成單欄。每一段的 `h2` 是 `.label` 壓在 `border-b-2 border-rule-strong` 上。
- **計劃（`JobPlan`）:** 抬頭是計劃狀態中性小色塊 + 「N 個檔案 · 高 / 中 / 低」計數；預估與「為什麼停下來」只在成立時出現。
  **依決定分組**（處置 × 季 × 信心 × 待確認，各是一段長清單段落）：摘要是處置中性小色塊 + 信心 + 待確認 + `S01 E01–E28` +
  檔案數；待審核、對不到、待確認的組排最前、左線 `rule-strong`。展開一組才逐檔列出：
  逐檔一條逐檔列（`FileEntry`），摘要是季集 + 來源檔名（`wrap-anywhere`），「目標」+ 目標路徑與解析器的
  英文理由（`lang="en"`）收在它自己的展開區裡。**處置、信心與待確認不重複**：它們是組鍵的一部分，
  一組裡必然相同。這一塊**沒有信號色**；待審核、對不到、待確認的列左線換 `rule-strong`。
- **時間線（`JobTimeline`）:** 每筆事件一條 `border-l-2 border-rule` 內縮列：事件型別中性色塊 + 相對時間 +
  **那一個型別自己的那幾格**（不做通用 key/value 傾印）。**連續的 `linked` 合成一行**「鏈接了 N 個檔案」，
  目標路徑收在一個巢狀 `<details>` 裡——一季 39 個檔案不該是 39 行只差一條路徑。服務原文不翻譯、理由翻譯。
  紅字（`blocked-ink`）只給擋住這一筆的：`submit_failed`、`issue_detected` 裡的 `missing_files` 與 `client_error`、
  `blocking` 為真的 `link_failed`；`issue_detected` 其餘三種是 `ink`，Jellyfin 請求失敗是 `ink-dim`。

### 長清單段落（`CollapsibleRow`：季表的一季、檔案與計劃的一組）

- 原生 `<details>`，`well` 底，段落之間是 `gap-px` 透出的 `rule`；需要人的那一段左線 `border-l-2 border-rule-strong`
  （其餘同寬但透明，內容不會錯開）。**收起時不渲染內容**（瀏覽器的頁內搜尋因此找不到收起的內容，這是拍板時知道的代價）。
- **展開時摘要列黏在畫面頂端**（`sticky top-0`，`well` 底 + 底線 `border-b-2 border-rule`，內容從它下面捲過去；GitHub PR
  檔案標頭的做法）。摘要列裡只有字（The Summary Is One Button Rule），靠右「展開 / 收起」由狀態決定——不用 `group-open:`，
  它會跟著外層下載列的 `<details>` 一起亮。
- 內容最後一行 `border-t-2 border-rule` 裡一顆 `COMPACT_BUTTON`「收起 S01 / 收起 正片 S01 E01–E28」。從它收起之後焦點回到
  摘要列；兩條路收起之後，摘要列若在畫面上方就捲回來。內容裡的連結與按鈕帶 `scroll-margin-top`，反向 Tab 回去時不會
  躲在黏頂的摘要列底下（WCAG 2.2 2.4.11）。
- 範圍用 en dash、季代號與集號之間空一格（`S01 E01–E05, E07`）：`S01E01-E02` 是 Jellyfin 的多集檔寫法，不能拿來寫一組。

### 逐檔列（`FileEntry`：檔案與版本的一筆、計劃的一筆）

- 一條 `border-l-2` 的內縮 `<li>`（需要人的那一條換 `rule-strong`），裡面一個原生 `<details>`：摘要一行，
  長的那幾段（路徑、Tags、解析器理由）收在裡面。收起時**內容留在 DOM 裡**——一筆只有兩三行，而整份清單已經
  收在上面那一段裡了；留著，組展開之後瀏覽器的頁內搜尋才找得到路徑。
- **上面的摘要說過而且是常態值的，這一列不再說**。所以在組裡只剩季集、檔名與例外；不分組時（電影）每一格自己說。
- 「展開 / 收起」同樣走 `ExpandHint` 的受控 `open`：`group-open:` 匹配的是**任一個**帶 `group` 的祖先，而這一列
  長在下載列那一筆（`JobRow` 帶 `group`）裡面，用 CSS 那一種外層一展開每一列都會說「收起」。

### Route 設定列（`RouteSettingsPage` / `RouteDelete`）

- 頁首是 `SettingsTabs`，標題 `.value text-lg font-semibold`，`max-w-3xl`。
- 每條 Route 一個 `<details>`，形狀與健康頁的 Route 列相同（`RouteIdentity`：健康色塊、停用中性色塊、
  名稱、category）。紅燈或停用的 **預設展開且框換 `rule-strong`**，綠燈收起。摘要另有目標路徑（`wrap-anywhere`）
  與「N 筆下載 · M 個入庫檔案」的引用數，靠右「管理 / 收起」。
- 展開區：名稱與啟用的表單（主要按鈕 `sm:max-w-xs`）→ 五條纜繩 + Ghost「重新檢查」→ 刪除。
  儲存、重新檢查、刪除 / 停用的結果都有 `aria-live` 的一句話——全綠重跑時纜繩一個字都不會變，沒有那句話就沒有回饋。
- **刪除:** 被引用的 Route **不給刪除鍵**，直接說「刪不得、為什麼」，還啟用著就旁邊給一顆 Ghost「停用」當出路。
  沒被引用時是 `ConfirmAction` 就地確認。刪掉的那一列會卸載，所以「已刪除」由頁面那一層宣告。

### 工作清單列（`QueueRow` / `DetailLine`）

`/review` 的每一類（計劃、對不到、重複、待確認）、`/issues`，以及媒體庫的「待審 / 對不到」子集是**同一種列、同一份元件**
（`components/QueueRow.tsx`），各頁只給內容。等到手上有兩個真實案例（`IssueRow`、`AuditRow`）才抽出來。
- **外殼:** `<article tabIndex={-1}>`，`well` 底 + `border-2 border-rule` + `px-4 py-3`，列之間 `gap-3`。**不塗信號色**：
  清單上每一列都在等人，塗漆不區分任何東西（The Role Is Not A State Rule）；不看顏色也讀得出來靠類別標籤的模板字。
- **由上到下四格:** ① 識別：中性色塊的類別標籤（`.label` + `deck`）+ 標題（`.value wrap-anywhere`）；② 一句話：理由翻成的
  句子 `Dot` 「多久以前」（`text-sm ink-dim`）；③ 展開：機器字串收在原生 `<details>`（摘要只有 `.label`「展開」），裡面是
  `hull` 底的 `dl`，每一格一條 `DetailLine`（`.label` 欄名 + `.value text-xs wrap-anywhere` 值，`sm` 以上 `10rem` 欄名兩欄，
  The Machine String Rule）；④ 動作列（`flex-wrap`，順序照後端給的）。**工作本身就是一張表或一個表單的那一類**
  （計劃的逐列表、對不到的修正表單）以 `body` 插在 ② 與 ③ 之間、不收進展開——收起來等於多一次點擊——也不另有動作列。
- **失敗時這一列留著**，動作列上方就地多一塊 `blocked` 的 `Notice` 說為什麼（The Failure Expands In Place Rule）。
- **列不知道自己在哪一段：** 分段是頁面的事（`/review` 分段，段標題是 `.label` + 計數壓在 `border-b-2 border-rule-strong` 上；
  媒體庫的子集不分段），標題層級由呼叫端給——分段底下 `h3`，不分段 `h2`，一組裡的成員 `h4`。
- **一組也是一列**（`AuditGroup`，M3 票 05）：同一個 Job 的 audit 收成一列，標題是作品，一句話說整組為什麼是 medium
  （原因相同說一次，不同就說不只一種），動作列一顆 Ghost「全部確認」——同單列的「確認」，不就地確認。成員（完整的
  `AuditRow`，標題只剩季集）收在展開裡、接在下載那一格之後；組說過的那一句成員不再說（`sentence` 省略，只剩時間）。
  「展開 / 收起」走受控的 `ExpandHint open`，成員長在組的 `<details>` 裡，`group-open:` 會跟著外層亮。
- **整段的動作掛在段標題列右側**（`/review` 的「已入庫，等你看一眼」：`AuditSectionConfirm`）：標題與它 `flex-wrap`
  共用那條 `border-b-2`，窄版換到下一行。它橫跨好幾筆下載，所以就地確認並說出件數；只在畫面上多於一格 audit 時給
  （全在同一組裡時，那一組的鍵就是它）。整組或整段一次消失好幾列，結果那一行（`aria-live`）改成看得見的 `text-sm`。
- **處理完就消失：** 清單外層掛 `useFocusAfterRemoval`（The Focus Takes The Next Row Rule）。

### 就地確認（`ConfirmAction` / `useInPlaceConfirm` / `ConfirmPanel`）

觸發鍵是 Ghost；展開後是 `well` 底 + `border-2 border-rule-strong` + `0.75rem` 內距、`gap-3` 的區塊，最後一排是
`CONFIRM_ACTIONS`：主要鍵（`minmax(0,14rem)`）與取消鍵，窄版疊成一欄。焦點與 `Esc` 的行為見
The Focus Follows The Confirm Rule。**外殼只有一份（`ConfirmPanel`），裝的內容有四種形狀**，`aria-labelledby` 一律指向
說明「按下去會怎樣」的那一句：
- **一句後果**（`ConfirmAction`、`WatchToggle`、`RematchForm`）：一段 `text-xs` 的後果說明，接兩顆鍵。
- **重述會被寫死的值**（`SubmitAction`）：後果之外，把 Route 名與資料夾名（`.value wrap-anywhere`）再印一次。
- **先選再確認**（`WorkPicker`，`/issues` 的認領類動作）：`.label` 標題 + 搜尋欄 + 最多八個候選（整行的按鈕、`aria-pressed`，
  選中的重線 + `deck` 底）。**沒選之前主要鍵不畫**（那一格留空，取消鍵不移位）——按下去才被拒的鍵不該畫出來；
  選了之後主要鍵說出選的是哪一部。
- **範圍 + 即時估算**（`JobDelete`，一個元件掛在 `/jobs/:hash` 的動作區與 Media 詳情的版本清單，確認區 `max-w-3xl`）：
  `.label text-ink` 標題 + `text-xs ink-dim` 導言 → 一疊原生 `Checkbox`（每個帶一行提示，**預設全不勾**）→ 估算塊 → 兩顆鍵。
  互相依賴的勾選框鎖住時照樣畫出來，提示換成解鎖的方法；取消上游時下游一起取消，不留一個送出去必被拒的勾。
  估算塊是 `border-l-2 border-rule pl-3` 的內縮段、`aria-live="polite"`，**展開那一刻才問**（逐一量過，慢而準）：等的時候
  是一句說得出正在量什麼的話，不是轉圈；**主要鍵不等估算**——估算是參考，不是前提，算不出來照樣刪得下去。
  數量行是 `.value text-xs`；「會空出多少」跟著勾選即時重算，只勾一半就是 0，不是一半。
  拒絕以 `role="alert"` 的 `blocked-ink` 留在區塊裡；成功時區塊收起，觸發鍵下方一行 `aria-live` 說**後端回報真的做掉了什麼**，
  不是勾選的回聲。

可展開列摘要上的「展開 / 收起」是 `ExpandHint`，「N 個待確認」是 `AuditChip`——各一份，不在列元件裡各抄。

### 訊息塊（`Notice`）

`well` 底 + `rule` 框 + 左側一塊信號色塊 + `.label` 標記 + 散文。標記是**塗上去的色塊加模板字**，
不是左緣的粗色條——那條粗色條是 AI 介面最好認的胎記，也不是這塊板子的語彙。
`blocked` 時帶 `role="alert"`。

### 指令列（`CopyLine`）

`hull` 底的 `<code>`（`.value text-xs`，`whitespace-pre`，可橫向捲動）加右側 `deck` 底的複製鍵，
中間用 1px 縫。每個失敗都要給得出可複製的下一步。外層 `min-w-0`，否則不斷行的指令會把 grid 欄撐寬、
`overflow-x-auto` 永遠沒事做。

### 中點分隔（`Dot`）

值與值之間的 `·`，`aria-hidden` + `ink-dim`。列上有元素邊界的值用這個元件；時間線那種純字串的一行用
`' · '` 接起來，空的那幾格不留分隔符——「· ·」讀起來像少了一個值。

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
- **Do** 讓長字串換行，不橫向捲動、不截斷：機器字串用 `wrap-anywhere`，散文用 `break-words`，
  flex / grid 子項加 `min-w-0`。`web/src/wrapping.test.ts` 守著「`.value` 不配 `break-words`、
  任何地方不用 `break-all`」這兩條。
- **Do** 用中性色塊表達角色、語言、分類這類非狀態的東西（The Role Is Not A State Rule）。
- **Do** 用原生 `input` / `button` / `details`，直到某一步真的需要行為基礎的元件為止。
- **Do** 讓一份全部正常的清單看不到信號色，只給例外塗漆（The Usual Stays Unpainted Rule）。
- **Do** 讓需要注意的列把線換成 `rule-strong`，紅色只留給狀態色塊（The Heavier Line Rule）。
- **Do** 讓每個就地確認走 `useInPlaceConfirm` 與 `ConfirmPanel`：展開時焦點進去、收起時回觸發鍵、`Esc` 只收起確認
  （The Focus Follows The Confirm Rule）。
- **Do** 讓處理完就消失的清單列把焦點交給接替的那一列，清單空了交給頁面的 `h1`（The Focus Takes The Next Row Rule）。
- **Do** 把「需要你」的計數塗在摘要層，不要只放在展開區裡（The Needs-You Floats Up Rule）。
- **Do** 讓窄版少掉的欄收成一行帶標籤的 `Dot` 分隔值，一份 DOM 兩種版面。
- **Do** 讓 `Cutaway` 的 `level` 跟著它所在頁面的標題層級，不跳級。

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
- **Don't** 以為 `break-words` 擋得住橫向捲動：它不改變 flex / grid 子項的最小寬度，沒有空格的發佈名照樣
  撐寬整頁（票 15 在 390px 量到 67px）。機器字串用 `wrap-anywhere`。
- **Don't** 在 `<summary>` 裡放連結或按鈕；把它們放進展開區（The Summary Is One Button Rule）。
- **Don't** 把已入庫、已完成這類常態塗成 `secured` 鋪滿一面牆或一整欄。
- **Don't** 用骨架屏動畫、脈動點或「即時」指示器；讀取中是不動的佔位，值自己換就是訊號。

## Known contradictions

- **值與值之間的中點分隔（`components/Dot.tsx`）是一個字元**，而 Don't 那一條寫著
  「不用字元當裝飾標記」。那條規則說的是**會進無障礙名稱**的標記（`▸`、`•`、emoji）——
  螢幕閱讀器會把它們念出來。`Dot` 掛 `aria-hidden`，所以它從無障礙樹上消失了；
  而它必須是行內字元：CSS 畫的刻度要靠一個固定的盒子定位，跟不上一行會換行、寬度
  由內容決定的值列表（結果表、下載列、牆卡片標識帶、檔案與計劃列都是這種）。

- `.impeccable/surfaces/web-src-pages-setuppage-tsx.md` 的方向段仍描述亮色主題「同樣四個信號色，
  降明度提彩度以達 AA」。**程式碼沒有這樣做**：`web/src/index.css` 的亮色區塊只換中性色與
  `blocked-ink` / `secured-ink`，四個信號色與 `on-signal` 兩個主題共用（註釋寫明理由：
  白字配中明度色只有 3.6:1）。以 build 為準——本文件記錄的是共用漆的那一版。
  `web-src-pages-healthpage-tsx.md` 已不再有這句話；setup 那份尚未更新。

- 實測對比下限（2026-09-17，探索、下載、Media 詳情、媒體庫、Route 設定五頁，深淺兩主題 × 1280 / 390 全部量過）：
  **深色最低 6.53:1、亮色最低 5.71:1**；`rule-strong` 見上面「重橫線」那一條（深色 3.33–4.51:1、亮色 6.46:1）。
  這些是**現況的最低值**，不是目標值；新畫面仍以 AA 數值為驗收條件。

- **媒體庫牆的格子跟著自己的內容長，同排下緣不再對齊**（M1.5 票 11）。牆卡片那一節說
  `JellyfinLine` 的 `min-h-10` 讓基線對齊——那句話原本靠 grid 預設的 `stretch` 把同排拉成一樣高。
  卡片裡的就地確認展開時，`stretch` 會把同排每一格一起拉長（390px 量到多出約 300px 空白），
  而位移正好發生在使用者要決定一個清掉就回不來的動作時（The Failure Expands In Place Rule）。
  取後者：媒體庫牆走 `WALL_GRID_CONFIRMABLE`（多一個 `items-start`），代價是標題兩行的格子
  比一行的高一截、下緣差約 8px。探索牆、繼續觀看與觀看區的集沒有就地確認，仍是 `WALL_GRID`。
