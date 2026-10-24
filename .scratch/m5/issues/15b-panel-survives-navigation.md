# 15b — 換頁時側面板不重建

**Status:** done

**Blocked by:** None（15 已合併；排在 16 收尾之前）

**讀:** `web/src/routes.tsx` 與各頁怎麼包 `AppShell`；`web/src/assistant/` 的面板狀態（輸入框、串流、目前那則對話）；`.scratch/m5/side-panel-shape.md`「換頁不關」；DESIGN.md 版面那一節

## 為什麼

票 15 收尾時的觀察（Claude Code 的 Heads up，使用者 2026-10-24 決定插這張）：每一條頁面路由各自包了一份 `AppShell`（頁首與側面板的外框），所以每換一頁，外框和面板整個重建。票 08 的「換頁不關」只是從瀏覽器記憶讀回「開著」，面板裡其他狀態都沒帶過去。推測的後果（**還沒實測**）：

- 輸入框裡還沒送出的字會不見。
- 回覆串流到一半時換頁，面板只剩「回覆中…」，要等回覆存進對話才看得到內容。
- 桌機上邊開著面板邊點卡片裡的作品連結——側面板最主要的用法——最容易碰到。

## 做什麼

1. **先實測、要有會紅的 repro**：playwright 重現兩種情況——(a) 輸入框打字未送出時點站內連結換頁；(b) 串流回覆到一半時點卡片裡的作品連結。確認紅了才改。實測若推翻推測，照實寫進 Comments 再決定範圍。
2. 修法照 React Router 的慣例：外框（頁首與側面板）提到共用的 layout route（`<Outlet />`），換頁只換內容區，面板不 unmount；不要靠把狀態塞進 localStorage 來掩蓋重建。窄版（票 15 的佔滿畫面、點連結收起面板）行為不變。
3. 換頁後串流照常接著畫完；輸入框的字還在；目前那則對話不變。
4. 檢查其他依賴「每頁重建」的地方（例如每頁各自的焦點管理、scroll 復位、頁首的目前頁標示）沒有被弄壞。

## 驗收

- [x] playwright：打字未送出換頁、串流中換頁兩種情況，修前紅、修後綠（1280 與 390）
- [x] 窄版面板與票 15 修的焦點行為不退化（既有 e2e 綠）
- [x] 全部檢查、`pnpm -C web build`、pytest、vitest、全套 e2e 綠；DESIGN.md（若版面結構有變）、progress.md 已更新

## Comments

### 2026-10-24 實作

**實測（做什麼 1）**：新的 e2e `web/e2e/assistant-navigation.spec.ts`（`assistant` 情境，1280 / 390，port 8534 / 8535）。
- 第一版 repro 在 1280 是**假的綠**：網址一換就斷言，舊的面板還沒被換掉，讀到的是換頁前的那一份。改成等那一頁的 h1 畫出來才斷言
  （`landOnWork`），四條全紅：打了的字不見；換頁之後沒有還在吐字（`aria-busy`）的那一則——舊面板卸載之後串流迴圈仍在背景讀完、
  觸發重讀對話，新面板一次拿到整句，使用者看到的是「回覆中…」等它存好。**推測成立**。另用 playwright 在 `<aside>` 上掛記號換頁，
  每一次都是新的元素，證實每換一頁整個外框重建。
- 390 的「打字未送出」紅還有第二個原因：票 15 讓窄版點連結時收起面板，收起就是卸載。

**修法（做什麼 2、3）**
- `routes.tsx` 加一條沒有路徑的 layout route `shellRoute`（TanStack Router code-based 的 pathless layout：有 `id`、沒有 `path`，
  context7 查證），`AppShell` 只有一份、包著 `<Outlet />`；登入之後的頁面都掛在它底下，拿掉各自包的 `AppShell`。門禁照舊在每一頁的
  `beforeLoad`（父到子跑完才 render，redirect 在外框掛上之前發生）。頁面裡 `useParams` / `useSearch` 的 `from` 改成 `/shell/...`
  （六個檔，tsc 守著；`/login` 不在 shell 底下不動）。
- 面板**開過一次之後一直掛著，收起是 `hidden`**（Tailwind v4 preflight 的 `[hidden]` 是 `display:none !important`，壓得過 `flex`）：
  窄版點連結收起、回來打開，字與串流都還在。`focusOnMount` 改成 `open` + `focusOnOpen`：每一次按開給一次焦點。
- 外框不再重建之後，窄版按瀏覽器的上一頁不會再順帶收起面板（以前是重建時「窄版不照記憶打開」做掉的），所以 `AppShell` 聽 pathname：
  窄版路徑一換就收起。面板的 `onLeave` 留著，管同一頁的連結（在 `/ai-activity` 按「活動」、只換 search 的）。
- code-review 之後：收起時 `/events/stream` 斷開、打開時重連（`useJobStream` 連上時整批重問），藏起來的面板不掛常駐連線；收起再打開回到對話那一塊。

**第 4 步（依賴每頁重建的地方）**，playwright 實跑 `library` 情境：換頁捲動照樣歸零（TanStack 的 `resetScroll`）、頁首的目前頁標示對、
上一頁的標示對、重整後第一個 Tab 是 skip link 且 Enter 落在 `main`。**行為差異**：用頁首導覽換頁之後焦點留在剛按的那一格
（以前外框重建、焦點掉到 `body`，下一個 Tab 從 skip link 開始）。這是常駐導覽的一般行為；換頁之後焦點該落在哪是全站的事
（M4 週報 critique 記過「換週後焦點掉到 body（全站的換頁焦點）」，另開票），這一票不動，DESIGN.md 寫了。

**決定（票面沒寫的）**：桌機按「關閉」再打開也留著草稿與正在看的那一則（以前是新的面板、回到最近一則）。390 的驗收要這個，
桌機一起跟著；歷史清單不留。

**驗證**：repro 四條修前紅、修後綠；vitest 新增五條（收起再打開字還在、換頁時是同一個面板、窄版上一頁收起、歷史清單收起再打開回到對話、
推播收起時斷開打開時重連）。實跑過的紅：前兩條在舊程式紅、窄版那條拿掉 pathname effect 紅、推播那條修之前紅；歷史清單那條沒有另做變異（面板一直掛著時不重設就停在清單上）。
`uv run pre-commit run --all-files` 全過、`pnpm -C web build` 成功、pytest 4861 passed / 1 skipped、vitest 2289 passed、`pnpm -C web e2e` 60 passed。

**code-review（`5aa19521` 起）**
- Standards：沒有硬違規。改了：`kept` 改名 `everOpened`；e2e 的 `landOnWork` 收成「等 h1 再 `reopenOnNarrow`」、`Page` 一般 import；
  `onLeave` 的註解寫明它管的是 pathname 不變的連結。沒改：`MediaRoute`、`InventoryPageRoute` 搬進 `routes.tsx`（兩檔只剩讀參數轉 props，
  與 `JobDetailRoute` 同形；搬了也只少兩處 `/shell` 字串，其餘四頁的 `useSearch` 照樣要寫，不在這一票擴大）；串流那條 e2e 靠替身吐字
  約六秒才來得及在串流中換頁（演練伺服器每 0.08 秒六個字，改了速度要跟著改句子長度）。
- Spec：推播常駐（收起之後 `/events/stream` 照樣開著，違反 `api/events.ts`「掛在需要它的那一頁上」）——已修並有測試；
  收起再打開保留草稿與對話是票面沒寫的，記在上面「決定」；換頁後焦點的差異記在第 4 步。門禁順序、`from` 改名、`hidden` 對 `flex` 都查過沒有問題。
