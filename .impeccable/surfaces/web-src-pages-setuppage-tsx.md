---
version: 1
slug: "web-src-pages-setuppage-tsx"
primary_target: "web/src/pages/SetupPage.tsx"
related_targets: ["web/src/setup"]
---

## Scope

設定精靈 `/setup`。**Visitor mode: Operate。** 涵蓋 plan §9.3 的八步；票 05 建骨架與第 1–2 步，
票 06 / 08 / 09 接上其餘泊位。完整規格（步驟、狀態、量級、錯誤、續行與跳過）在
`.scratch/m0/wizard-shape.md`，不在此重複。

## Audience and job

剛跑完 `docker compose up` 的自架者，桌機，房間偏暗，一生只走一次。任務是把四個泊位接上到四項綠燈，
全程不打開 qBittorrent / Jellyfin / Prowlarr 的介面。他不知道哪個服務是套件內、哪個是既有 ——
那正是第 2 步要替他判斷的。

## Proof

畫面上只放實測到的值：探測到的版本號、每個服務被判為套件內或既有的**理由**、`link()` 的 inode、
逐站 `indexer/test` 結果。只有 Berth 同時看得到三個容器的掛載視圖，「哪個容器少了哪個掛載」是別的
工具說不出來的話。

## Direction contract

**THESIS.** 精靈不是八張「下一步」的表單，是一塊調度板：四個泊位常駐在頂端，工作面在下。
拒絕左側垂直步驟條 + 深色卡片 + 藍色 primary 的類別預設。

**OWN-WORLD.** 泊位調度板 + 船期表 + ISO 6346 貨櫃標識。鋼灰藍船體底（深色為預設，亮色是印刷版班表），
塗裝色塊填滿整格而不是描邊；重橫線分隔、嚴格欄格、等寬數字貼在它那一行。**只有四個信號色**，
每個顏色只有一個意思：assigned 指派中、working 進行中、secured 已繫上、blocked 阻擋（紅色只代表阻擋）。
狀態三重編碼（色塊 + 模板字標籤 + 位置），不看顏色也讀得出來。無發光、無漸層、無圓角卡片。

**STORY.** 他看懂四個泊位各自的狀態與理由，相信 Berth 真的探到了那些服務，然後按下靠泊。

**FIRST VIEWPORT.** 頂端整寬泊位板橫幅：四格等寬塗裝色塊，各帶 `BTH 1` 式泊位碼、服務名、狀態標籤；
右上角 `ZH / EN`。橫幅下方是當前泊位的剖面（將寫入什麼：鍵與值的表格），主要動作在剖面右側（桌機）
或固定於底部（手機）。

**FORM.** 泊位調度板，seed key `b84bd503`，card `assigned`（THE ROLL），2026-09-07 使用者鎖定；
執行契約 code-led（此 harness 無圖像生成）。**署名互動：靠泊序列** —— 按下靠泊後那一格不換成 spinner，
而是逐條纜繩繫上，每完成一項把實際結果數值留在旁邊；任一條失敗變紅並就地展開可複製的手動步驟，
其餘已繫上的纜繩不動。`prefers-reduced-motion` 降為即時切換。

**FINISH.** unreviewed and undocumented is unfinished; this build ends with the finish review,
the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Constraints

React 19 + TS + Vite + Tailwind v4 + TanStack Router / Query + react-i18next。WCAG 2.2 AA 是驗收條件，
深淺兩主題都要達標。UI 文案全部走 i18n key，zh-Hant 與 en 並列。外部服務行為以 brief §20 與
`docs/research/m0-experiments.md` 為準。

## Resolved during build (票 05)

- **字體**：不引入 webfont。自架應用不該對 Google Fonts 發請求，離線也要成立。「模板噴字 + 貨櫃編號」
  的語彙改由**處理方式**承載：等寬系統堆疊 + 重字距 + 橫線 + 色塊。
- **`.label` 在中文下**：`text-transform: uppercase` 對中文無效、寬字距在中文可讀性差。標籤樣式因此
  分岔 —— Latin 走全大寫 + `0.18em` 字距，zh-Hant 走原樣 + `0.05em` + 前置刻度符號，兩者同一個高度與色階。
- **亮色主題**：塗裝色塊在亮色下改為「印在紙上的班表」—— 同樣四個信號色，降明度提彩度以達 AA，
  底色是紙白而非純白。
- **shadcn/ui**：第 1–2 步沒有任何需要 Radix 行為的元件（無 dropdown / dialog / popover / tabs），
  原生 `input` / `checkbox` / `button` 的無障礙更好。等到真的需要行為基礎的那一步再引入。

## Resolved during build (票 06)

- **既有 Jellyfin 0 個媒體庫的空狀態**（原本掛在 Open）：不擋、不假裝有東西，直接說「這台
  Jellyfin 一個媒體庫都沒有，先在 Jellyfin 建一個再回來，Berth 才有地方寫入」，配 `assigned`
  色塊。Berth 不會替既有伺服器建媒體庫（brief §16.4 的紅線），所以這裡不能有動作按鈕。
- **兩條路徑的剖面不同**：套件內的剖面列「將會做什麼」（九步各自打哪一支端點），既有的剖面
  列「這台 Jellyfin 現在是什麼樣子」（位址、版本、API key、媒體庫數、MergeVersions）。同一個
  `Cutaway` 元件，內容全部是實測值。
- **二次確認就地展開**：「加入 Berth 路徑」與「安裝 MergeVersions」按下之後在原地換成一段
  說明加兩顆按鈕，不開 dialog——沒有 Radix，也不跳離當前泊位。
- **走過的步驟留一條線索**：步驟由狀態導出，所以「回去改帳密 / 重新探測」不能靠改後端狀態；
  泊位板下方一條 trail 是唯一入口，同時也是證據（帳號是誰、判定了幾個服務）。

## Resolved during build (票 08)

- **泊位 3 的剖面欄位**（原本掛在 Open）：兩個剖面並排——索引站（接法、位址、API key、已加入
  幾 / 十）與 TMDB（憑證是內建的還是使用者填的、測試打哪一支端點）。既有 Prowlarr 與任意
  Torznab 共用同一份剖面，差別只在「接法」那一列，因為使用者要判斷的是同一件事：
  Berth 現在會去哪裡找東西。
- **泊位 2 的剖面是一張逐鍵的差異表**（鍵 / 現值 / 建議值），不是散文。鍵名用 `app/setPreferences`
  的原字串——畫面顯示的與送出去的是同一個字串，他在 qBittorrent 自己的介面上也找得到它。
- **索引站的勾選在動作之上、結果在動作之下**。按之前那十行全是「尚未執行」，只是把勾選清單
  抄了一遍；結果只列這一輪真的跑過的站。
- **逐站失敗不是阻擋**：十個公開站有幾個連不上是常態（本機實測十個裡五個失敗），所以泊位 3
  的信號看的是「有沒有接上任何一個 / 使用者說之後再說」，紅色留給真正走不下去的事。
- **泊位 2 的紅色是版本太舊或連不上**：那一步在使用者升級之前做不下去，畫面因此不給一顆按不動
  的按鈕，而是給升級指令。
- 第 5、6 步各有一顆「之後再說」，跳過之後仍留在同一個泊位（可以再按回來），完成頁列出跳過了
  什麼由票 09 接手。
