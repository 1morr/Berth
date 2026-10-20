# 104 — 精靈：既有分支的說明去重、跨頁一致性收尾

**Status:** done

**Blocked by:** None — can start immediately

**讀:** 票 103 的 Comments（critique 那一段）；`.impeccable/critique/2026-10-14T05-22-48Z__web-src-pages-setuppage-tsx.md`；`PRODUCT.md`、`DESIGN.md`（Values Sit On Their Line Rule、塗漆規則）；`CONTEXT.md`

## 為什麼

票 103 收尾的 `/impeccable critique`（27/40）提了五個問題。使用者（2026-10-14）選了收 P1 與 P2 的一致性那一條成一張票；其餘三條（頁 4 孤立的「之後再說」、頁 2／4 位址沿用頁 1 的主機、指向句與完成頁的峰終）這一輪不做，指向句維持頁 1、2、4 各說一次。

## 做什麼

1. **既有分支說明去重（P1）**：頁 2 選既有、完成之後，「不改偏好」在 lede、這裡能做、卡片、剖面、完成提示說了 5 次；探測 torrent 說了 3 次。每件事只在一處說，唯一要使用者動手的那件（「設了『torrent 加入時執行外部程式』會觸發一次」）獨立成一行、放在測試鍵附近。頁 1、頁 4 照同一個原則檢查。先 `/impeccable distill`，390 寬的版面再 `/impeccable layout`。
2. **一致性收尾（P2）**，`/impeccable polish`：
   - 頁 4 還沒選時的標題與頁 1、頁 2 同一個形狀（「先選 X 是哪一台」）。
   - 頁 3 Route 列「已繫上」與頁 6 同一列的塗漆一致；頁 2 套件內完成時不疊三顆綠章。
   - 介面登入在同一個狀態下，重新整理前後說同一句（現在是「已沿用 Jellyfin 帳密（skipper）＋改用另一組」與「Prowlarr 介面的帳號：skipper＋更換登入」）。
   - 頁 2 剖面有「介面登入」一列、頁 4 沒有：兩頁同一套列。
   - 頁 1 勾了「套件內 qBittorrent 與 Prowlarr 的介面也用這組」並送出之後，剖面不再說「不存下：你的密碼（只交給 Jellyfin）」。
   - 頁 1 套件內鎖定說明「同一台換了位址可以改」與「這裡能做」說套件內位址由 compose 決定，兩句對齊。

## 驗收

- [x] 第 1 點：頁 2 既有完成狀態下，「不改偏好」與探測 torrent 各只出現在一處，有 vitest 守著（zh-Hant 與 en）；外部程式那一句獨立可見
- [x] 第 2 點每一小項有 vitest（zh-Hant 與 en）
- [x] playwright 實跑頁 1、2、4（套件內與既有）1280 與 390 寬截圖；不碰使用者的 `berth-local`
- [x] `/impeccable critique` 前後分數記在 Comments（前一輪 27/40）
- [x] 全部檢查、vitest、前端 e2e 綠；progress.md 已更新

## Comments

**做了什麼（2026-10-19）**

- **第 1 點**：每件事的唯一一處——「Berth 不改你原本的設定」是卡片（`choice.existing.lede`），頁 2 的 lede、這裡能做、不在這裡做、完成提示、剖面、`existingPlan` 拿掉；探針是測試鍵旁的 `ProbeNote`（`connect.probe` 去掉括號），卡片不再說；「torrent 加入時執行外部程式」獨立一行（`connect.externalProgram`，`font-semibold text-ink`）：表單打開時在測試鍵上方、收著時在測試結果底下。頁 1：鎖定說明只留「換一台等於換擁有者」，「這裡能做」只說位址怎麼改，「不在這裡做」只留改密碼，`owner.lede.owned` 不再說密碼在哪改。頁 4：lede、加站說明、`existingLede`、回頭看的「Berth 不移除你的站」拿掉，卡片的「原本的站不動」是唯一一處。
- **第 2 點**：頁 4 標題 `indexer.title.{choose,chosen}`，lede 去掉同一句；頁 6 的 Route 列改用頁 3 的 `RouteIdentity`（常態不塗漆，標籤同 `routeHealthLabel`）；頁 2 套件內不再畫 `qbittorrent.done`（登入那一條的「已完成」已經說了），工作欄剩「連上了」與「已完成」兩顆；「已沿用 Jellyfin 帳密」改讀後端的 `web_ui_login_reuses_owner`，`SetupPage` 的 `carriedTo`／`noteLogin`、`CarriedLogin.inUse` 刪掉；剖面「介面登入」一列抽成 `LoginRow`（`interfaceLogin.cutaway.*`），頁 2、頁 4 共用，既有的那一台說「在它自己的介面上管」；頁 1 擁有者成立之後「不存下」一律是「你的密碼」（`owner.cutaway.passwordOwned`）；鎖定說明與「這裡能做」不再兩處說位址。
- `test/fetch.ts` 的函式替身收到請求的 `init`，讓記得狀態的假後端照送來的「沿用與否」回。

**驗證**

- vitest：109 檔 2059 passed。新檔 `SetupPage.repetition.test.tsx` 兩種語言各 13 條＋`placesOf` 雙向樣本；變異：完成提示放回「Berth 沒有改這台的任何偏好」→ 兩條紅。
- pytest 4092 passed / 24 deselected（08b1c41）；前端 e2e 38 passed；`pre-commit run --all-files` 全部 Passed。
- Playwright 實跑（演練伺服器 `mixed`、`bundled`，各自暫存 `--config-root`，沒碰 `berth-local`）：頁 1、2、4（套件內與既有）1280 與 390 寬，改前改後截圖與 innerText 在 session scratchpad 的 `probe/before`、`probe/after`；390 寬不溢出。

**critique（雙子代理）**

- 分數：**27 → 28/40**（trend 24 → 26 → 27 → 28；快照 `.impeccable/critique/2026-10-19T16-59-42Z__web-src-pages-setuppage-tsx.md`）。detector CLI 0 筆；overlay 只有 `line-length`（已有 `max-w-prose`，半誤報）與頁 4 套件內欄高失衡。
- 新提的優先問題（不在這張票）：頁 1 既有卡片仍長（distill）、頁 4 套件內一屏兩件必填（layout）、頁 2／4 位址沿用頁 1 主機（票 103 時決定這一輪不做）、頁 4「沿用」沒勾時帳號已預填、390 寬頁 4 推薦站下方留白。

**code-review 已處理**

- Spec：綠章測試原本只斷言「不到三顆」→ 改成剛好是「連上了」「已完成」兩顆；完成狀態下外部程式那一句的位置補斷言（緊接「改位址或憑證」）。
- Standards：`docs/plan.md` 外部程式那一句的位置同步；CHANGELOG 補一條；偏差記進 progress.md。
- critique A：剖面「將設為下面填的那一組」在 390 寬時剖面在表單下方 → 改成「表單裡填的」。
- critique B：live-server 的 `web/.impeccable/live/server.json` 被收進 commit → 從 commit 拿掉，`.gitignore` 加 `.impeccable/live/`。

**code-review 未處理的發現**

- Standards（判斷）：`CarriedLogin` 只剩 `{ password }`，包一層的價值變小；留著是因為頁 2、頁 4 的 props 已經用它。
- Standards（既有）：`connect.probe` 把 `{{root}}` 寫在句子裡（Values Sit On Their Line），改動前就是這樣。
- Spec（刻意）：頁 1 擁有者成立之後沒勾「也用這組」的也說「你的密碼」，不再說「只交給 Jellyfin」——重新整理之後分頁不記得勾過沒有，照實說得出的只有「不存下」。
- Spec（刻意）：既有的那一台做完照舊有一句「這個泊位的事做完了。」，套件內沒有——既有那一台沒有纜繩列，沒有那一句就沒有東西說做完了。
