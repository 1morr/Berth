# 81 — 精靈頁 4：還沒選之前，剖面不說「你自己的 Prowlarr」

**Status:** done

**Blocked by:** None — can start immediately

**讀:** M4 票 80 的 Comments 最後一條；`web/src/setup/IndexerStep.tsx` 的剖面（`Cutaway`，「接法」那一列看 `bundled`）；頁 1、頁 2 的剖面在還沒選、測試中時怎麼說（`JellyfinStep`、`QbittorrentStep`）

## 為什麼

票 80 實跑時看到：頁 4 還沒選「套件內」或「既有」時，剖面的「接法」就寫「你自己的 Prowlarr」；選了套件內、還在連線測試時也一樣。原因是剖面只看 `bundled` 是不是 true，把「還沒選」當成「選了既有」。第一次安裝的人一定會經過這頁。

## 做什麼

- 「接法」只在真的選了之後才說套件內或你自己的；還沒選時說「還沒選」或照頁 1、頁 2 的做法（先看它們怎麼處理，三頁說法一致）。
- 選了套件內、還在測試中時說套件內。
- 同一個剖面裡其他列若也把「還沒選」當成既有，一併改。
- zh-Hant 與 en 並列。

## 驗收

- [x] 頁 4 還沒選、選了套件內測試中、選了套件內完成、選了既有，四種狀態的「接法」各自正確；vitest 守，做變異驗證
- [x] 頁 1、頁 2、頁 4 還沒選時的剖面說法一致（若頁 1、頁 2 也有同樣的問題，一起修）
- [x] Playwright 實跑：頁 4 的四種狀態各一張截圖。用隔離環境（專案名 `berth-t81`、另一組 port）；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments

**做了什麼**

- 頁 4 還沒選時，剖面換成與頁 2 同一個元件 `ChoiceCutaway`（從 `QbittorrentStep` 抽出，`setup/ChoiceCutaway.tsx`）：標題「將會做什麼」，套件內「讀它的 API key · 替它加站、設介面登入」、既有「用你貼的 API key · 用它已有的站，一站都不移除」（zh-Hant / en 並列）。選既有被拒（什麼都沒存）、沒選就跳過也是這一個。
- 「接法」看選定的那一台（`cutawayOrigin`）：存下的，或第一次選、請求還在路上的那一格。為此 `ChoiceControls.choosing: boolean` 換成 `sending: ServiceOrigin | null`（送出去還沒回來的是哪一格），`SetupPage`、設定頁的 `ServiceConnection` 跟著改；`ServiceChoice` 內部照舊用 `sending !== null` 當布林。
- 其他列（位址、API key、已加入）原本就照清單與連線測試說，沒有把還沒選當成既有，沒動。

**票面留給實作的決定**

- 還沒選時「照頁 2 列出兩種」，不寫「接法：還沒選」：頁 2 是同形的二選一，同一個元件讓兩頁說法不會再分岔；位址、key、站數在選之前都是空的，列出來沒有資訊。
- **換到另一格還沒存下（確認中或測試中）時也退回 `ChoiceCutaway`**（code-review 的 Spec 指出）：剖面其他列說的是存下的那一台，主欄在這時已經不畫它；頁 2 同一個時候也是「將會做什麼」，頁 1 拿掉那一台那一列。
- 頁 1 不改：`OwnerCutaway` 還沒選時說「建立或登入：連上之後看那一台」與 API key、密碼不存下，本來就沒有替使用者決定來源；與頁 2、頁 4 共用的是標題「將會做什麼」，列的內容是那一頁自己會做的事。

**驗證**

- vitest：`SetupPage.services.test.tsx` 頁 4 三條（還沒選 → 套件內送出中 → 回來了、清單還在重讀 → 連上；既有送出中 → 連上；套件內換既有：確認中、測試中 → 存下）、頁 2 還沒選的剖面一條。變異：`cutawayOrigin` 拿掉送出中的那一格，前兩條紅；「接法」改回只看清單，第一條紅；拿掉換台時的退回，第三條紅。
- e2e `existing.spec.ts`：既有 key 錯、什麼都沒存時右欄是「將會做什麼」、沒有「接法」（原本斷言「尚未取得」，那正是把還沒選畫成既有的剖面）。
- Playwright 實跑：**沒有用 docker compose**——演練伺服器 `scripts/fake_setup_server.py --scenario starting --port 8781`、自己的暫存 `--config-root`（真的 API、資料庫與前端 build，只換外部服務），`berth-local` 沒碰、也沒起任何容器。截圖在 `.playwright-mcp/t81/`（gitignore）：`01-unchosen`（將會做什麼兩列）、`02-bundled-testing`（選擇請求以 `page.route` 延遲 8 秒：「正在設定套件內 Prowlarr，連線測試中…」，接法「套件內 Prowlarr」、位址「—」）、`03-bundled-done`（套件內、`http://prowlarr:9696`、已取得）、`04-existing`（你自己的、`http://192.168.1.10:9696`）。截圖在 code-review 之前拍；之後只改了換台中的剖面與命名，這四種狀態的畫面不變（vitest 守著）。
- 全部檢查：`pre-commit run --all-files` 12 項 Passed；vitest 90 檔 1447 passed（中間一輪有一檔沒跑完、同時 pre-commit 的 eslint 紅一次，沒留輸出，重跑兩者都綠、沒重現）；前端 e2e 35 passed。

**code-review 已處理**

- Standards：prop 叫 `choosing` 卻裝來源 → 改名 `sending`；`chosenOrigin` 與同檔的 `origin` 太像 → `cutawayOrigin`；接法的查表改成與同檔 lede 一樣的樣板 key。
- Spec：換台時剖面說舊的那一台（見上）；頁 1 為什麼不改、變異驗證的紀錄（見上）。

**code-review 未處理的發現**

- Standards（判斷）：「pending 時取 origin」在 `SetupPage` 與 `ServiceConnection` 各寫一次，兩邊 mutation 的 variables 形狀不同，抽出來比重複的一行長。
- Standards（判斷）：`JellyfinConnection` 與 `ExistingForm` 的 `choosing` 仍是布林——它們只需要「在送」，不需要哪一格。
- Spec（不在這張票）：第一次選套件內、還在測試時，頁 2 的剖面仍是「將會做什麼」，頁 4 說「接法：套件內」（票只要求頁 4 這樣說）；同一段時間頁 4 的 lede 仍是「先選 Prowlarr 是哪一台」（`draft` 在送出套件內時清掉，lede 看不到送出中的那一格）。
