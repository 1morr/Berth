# 80 — 精靈：點下去馬上有反應；「也用這組」在頁 1 就擋好、頁 2 不再重問

**Status:** done

**Blocked by:** None — can start immediately（只動精靈前端，與 79、69 不重疊）

**讀:** M4 票 15（沿用 Jellyfin 帳密）、40（頁 1「也用這組」）、07（介面登入）；`web/src/setup/ServiceChoice.tsx`（`pick`、`TestLine`）、`web/src/setup/interfaceLogin.ts`（`LOGIN_RULES`、自動帶入）、`web/src/setup/QbittorrentStep.tsx`、`web/src/setup/IndexerStep.tsx`、`web/src/setup/InterfaceLoginFields.tsx`、頁 1 的「也用這組」；brief §16.3

## 為什麼（2026-10-09 使用者本機試用）

1. **點「套件內」之後整頁沒有反應**：
   - 第一次用滑鼠點「套件內」，`pick` 會直接送出 `onChoose({ origin: 'bundled' })`。
   - 但「測試中」那一條（`TestLine`）要等 `service` 已經有結果才畫得出來。第一次還沒有結果，所以請求在路上那幾秒，畫面什麼都沒有，使用者以為壞了。
   - 用鍵盤選才有確認框和忙碌中的鍵；滑鼠那條路沒有。
2. **頁 1 勾了「也用這組」，到頁 2 又問一次「沿用」，而且用不了**：
   - 使用者在頁 1 用了 4 個字的 Jellyfin 密碼，照樣勾得起「也用這組」。頁 1 沒有檢查 qBittorrent 的規則：帳號至少 3 個字、不能有冒號，密碼至少 6 個字（`LOGIN_RULES`）。
   - 到頁 2，自動帶入被擋下，上面寫「不能沿用」。下面的表單卻照預設勾著「沿用 Jellyfin 帳密」，密碼框還標紅：同一件事說了兩次，那個勾選根本用不了。

## 做什麼

1. **點下去當下就有回饋**（Jellyfin、qBittorrent、Prowlarr 三頁共用 `ServiceChoice`）：
   - 送出的那一刻，被點的那一格就是選中的樣子；下面馬上出現「正在設定套件內 qBittorrent，連線測試中…」這類忙碌中的狀態，並且有讀屏宣告。
   - 回來之後換成結果。請求失敗時照舊顯示 `RequestFailed`。
   - 請求在路上時，不能再點另一格送出第二個請求。
2. **頁 1 就擋好「也用這組」**：
   - 照套件內服務的登入規則，即時檢查頁 1 的帳號與密碼：
     - 建立管理員時，邊打邊檢查；
     - 登入既有帳號時，送出前檢查。
   - 不合的話，「也用這組」停用並說出原因（例如「密碼少於 6 個字，qBittorrent 不收；到頁 2 另設一組」），zh-Hant 與 en 並列。
   - Prowlarr 目前沒有規則（`LOGIN_RULES.prowlarr = null`）。只有 qBittorrent 不合、Prowlarr 合的情況，怎麼說由實作決定，理由寫在 Comments。
3. **頁 2、頁 4 不重問**：
   - 頁 1 帶過來、而且設好了：只顯示「已沿用 Jellyfin 帳密（Admin）」，加一顆「改用另一組」。
   - 頁 1 沒勾，或帶了但不合規則：表單直接是自設的三格，不再預設勾「沿用」。
   - 「不能沿用」那則提示只說一次。
   - 頁 1 沒勾、使用者在頁 2 自己想沿用：照舊可以勾，規則不合時勾選停用並說原因，不是勾了才紅。
4. **UI 走 `/impeccable`**：先 `shape`，收尾 `critique` / `polish`。

## 驗收

- [x] 三頁第一次點「套件內」，當下就看得到選中與忙碌中的狀態；請求在路上時不能送第二次；vitest 守著
- [x] 頁 1 的帳密不合 qBittorrent 規則時，「也用這組」停用並說原因；合的時候照舊能勾；vitest 守兩個方向
- [x] 頁 2／頁 4：帶過來而且設好了只顯示摘要與「改用另一組」；沒帶或不合規則時不預設勾「沿用」；「不能沿用」只說一次；vitest
- [x] Playwright 實跑：精靈從頭走一次，用 4 個字的密碼與 8 個字的密碼各一輪，附截圖。用隔離環境（專案名 `berth-t80`、另一組 port）；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments

**做了什麼**（shape：`.scratch/m4/wizard-feedback-shape.md`，使用者確認）

- `ServiceChoice`：送出那一刻記下送出去的那一格（`sent`），回來之前它就是選中的、另一格停用、不送第二個；套件內第一次選先畫與連線列同形的「測試中」列（`PendingLine`），宣告區念「正在設定套件內 X，連線測試中…」，回來時同一個位置換成結果。失敗時那一格回到沒選。設定頁的連線區共用這個元件，一起改（CHANGELOG 有寫）。
- 頁 1：「也用這組」照 qBittorrent 規則邊打邊看（`reuseUnfit`），不合就停用並說原因，改到合了恢復原本的勾選。
- 頁 2、頁 4：沒帶時直接是自設三格、沿用不勾；擁有者的名字不合規則時沿用那一格停用說原因；帶過來而且設好了只說「已沿用 Jellyfin 帳密（擁有者）」＋「改用另一組」。

**票面留給實作的決定：只有 qBittorrent 不合、Prowlarr 合時怎麼說**——整格停用，原因只說 qBittorrent 不收、「頁 2、頁 4 會再問一次介面登入」。不拆成「只給 Prowlarr」：這一格答應的是「兩台都用這組」，邊打字邊改標籤會讓人讀不準它答應了什麼；頁 4 的「沿用 Jellyfin 帳密」照樣勾得起來，代價是在頁 4 打一次密碼。Prowlarr 目前沒有規則，所以「不合」都是這一種。

**偏離票面**

- 「登入既有帳號時，送出前檢查」不適用：使用者確認「也用這組」照票 40 只在建立套件內 Jellyfin 的管理員時提。
- 「帶了但不合規則」在頁 2 不會發生：頁 1 擋過就帶不過來，所以頁 2 的「不能沿用」提示整個刪掉（同一件事只在頁 1 說一次）。
- 「規則不合時勾選停用」在頁 2 只做得到帳號：沒帶時密碼要打了才知道，密碼太短照舊在送出時擋。

**實跑**（隔離 compose 專案 `berth-t80`：容器 `berth-t80-*`、網路 `berth-t80` 10.80.0.0/16、port 8480 / 8481 / 8496 / 9796 / 6981、全部 named volume，override 放在 repo 外；工作樹 build 的 `berth:t80`；跑完 `down -v`、刪 image；`berth-local` 一直是停著的，沒碰）。截圖在 `.playwright-mcp/t80/`（gitignore）。

| 輪 | 結果 |
| --- | --- |
| 4 字密碼 | 頁 1／2／4 點套件內當下：那一格勾著、另一格停用、「測試中」列與宣告（`r1-01`、`r1-03`、`r1-06`）；頁 1「也用這組」停用、說「密碼少於 6 個字元…」，剖面說只交給 Jellyfin（`r1-02`）；頁 2 三格、沿用不勾、沒有「不能沿用」（`r1-04`）；頁 4 同樣三格（`r1-07`） |
| 8 字密碼 | 頁 1 打到第 5 個字還停用、第 6 個字起恢復勾著（`r2-01`）；頁 2 只有「已沿用 Jellyfin 帳密（skipper）」＋「改用另一組」，0 個密碼欄（`r2-02c`，390 寬 `r2-05` 無橫向捲動）；按「改用另一組」是三格、沿用不勾（`r2-03`）；頁 4 同樣只有摘要（`r2-04`） |

**檢查**：`pre-commit run --all-files` 綠；vitest 90 檔 1441 passed；`pytest` 3730 passed、24 deselected（11 分半；先前一次 `-x` 的執行印出一段 traceback 後結束，沒有留下完整輸出，重跑全套沒有重現）；前端 e2e 35 passed。

**code-review 已處理**

- Spec：「已沿用」原本以「帶過一組、Berth 設的、帳號是擁有者」判斷，「改用另一組」只換密碼時照樣說已沿用 → `SetupPage` 記這個分頁最後一次替那一台設下的（`CarriedLogin.inUse`），vitest 守，變異驗證過。
- Spec：頁 1 表單換掉重來時剖面留著上一張「不合」的結論 → 表單卸下時回報回到合，vitest 守，變異驗證過。
- Spec：brief §16.3「那兩頁照舊請使用者打一次」與 `QbittorrentStep` docstring 的「預設沿用」改掉。
- Standards：`TestLine` 的 JSDoc 被 `PendingLine` 插在中間；`IndexerStep`／`QbittorrentStep` 重複的「已沿用」判斷（收進 `SetupPage`）；設定頁多餘的 `reuse: false`。

**code-review 未處理的發現**

- Standards（判斷）：`PendingLine` 與 `TestLine` 的外框與行首各寫一份；`BerthLogin` 兩個分支的外層 class 相同。沒有抽共用元件：`TestLine` 的行首還有狀態標籤與技術細節，抽出來的參數會比重複的四行多。
- Standards（判斷）：`OwnerForm` render 時算一次 `carryUnfit`、改欄位時再算一次回報給 `OwnerStep`（`onFits`）。帳密的狀態要跟著表單的 key 重設，提到 `OwnerStep` 會丟掉這一點；卸下時的回報補上了重掛載那一條路。
- Standards（判斷）：「哪一種不合 → 用哪個 min」在 `OwnerStep` 與 `InterfaceLoginFields` 各寫一次；`ownerUnfitFor` 過濾 `passwordShort` 只是型別收窄。
- 實跑時看到、不在這張票：頁 4 還沒選（以及選了套件內、還在測試中）時剖面「接法」寫「你自己的 Prowlarr」（`IndexerStep` 的剖面把沒選當成既有）。
