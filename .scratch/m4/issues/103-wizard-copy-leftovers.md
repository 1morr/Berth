# 103 — 收尾（文案）：介面登入的叫法、頁 1 字量、COMPOSE_PROFILES 只說一次、過去式的預約時間

**Status:** done

**Blocked by:** None — can start immediately

**讀:** 票 68 的 Comments（critique 那幾條）；票 62 的 Comments（「下一次確認在 4 秒前」）；`PRODUCT.md`、`DESIGN.md`；`CONTEXT.md`（叫法以它為準）

## 為什麼

票 68 的 `/impeccable critique` 提了三件不在那張票範圍的事；票 62 順手看到一個時間說法的錯。使用者（2026-10-14）同意收成一張。

## 做什麼

1. **「WebUI 登入」與「介面登入」兩種叫法並存**（頁 2 標題、按鈕等）：統一成一種，以 `CONTEXT.md` 的詞為準；沒有就補進去。zh-Hant 與 en 都改。
2. **頁 1「既有」卡片字太多**：照 critique 的意見刪減，關鍵資訊（會動到什麼、不會動什麼）不能丟。
3. **`COMPOSE_PROFILES` 在頁 1、2、4 各說一次**：改成只在需要的那一頁說一次，或收在一處。完成頁那一段（閒著的套件內容器）保留。
4. **作品頁「Berth 下一次確認在 4 秒前」**：`resolve_after` 已經過了、排程那一輪還沒跑到時，說成過去時間。改成「即將確認」之類的說法，不出現過去式。
5. 改完跑一次 `/impeccable critique` 看精靈分數，結論記在票的 Comments。

## 驗收

- [x] 每一點都有 vitest 守著（zh-Hant 與 en），i18n key 成對；舊叫法在 `web/src` 搜不到
- [x] playwright 實跑精靈頁 1、2、4 與作品頁，390 與 1280 寬各截圖；**不准碰使用者的 `berth-local`**
- [x] critique 前後分數記在 Comments
- [x] 全部檢查、vitest、前端 e2e 綠；progress.md 已更新

## Comments

**做了什麼（2026-10-14）**

- **第 1 點**：CONTEXT.md 補 **Interface login**（UI「介面登入」，_Avoid_ WebUI 登入／WebUI login）。zh-Hant 與 en 的頁 2 標題、lede、剖面、步驟名、完成提示、設定頁說明、回頭看全改；en 標籤大寫開頭 `Interface login`。後端 docstring（`gen:api` 重產 `schema.d.ts`）、測試、e2e、README 兩份、brief、plan 同步。照留：qBittorrent 自己的選單路徑「選項 → WebUI」，以及指它偏好鍵或既有那一台連線帳密的「WebUI 帳號／帳密」（不是這個登入，CONTEXT.md 寫明）。閘門 `web/src/i18n/interfaceLoginName.test.ts`：掃整個 `web/src`，樣式雙向。
- **第 2 點**：`choice.existing.adds.jellyfin` 與 `sameHost` 重寫，`choice.existing.library` 併進 `adds` 後刪掉（卡片從四段變三段），破折號拿掉。zh-Hant 563 → 約 360 字、en 1420 → 約 930 字。閘門 `wizardCopy.test.ts`：字數上限（約三分之二）＋十二項事實（API key、頁 3 路徑、原本的路徑不動、不改原本的設定、勾了才新建、新建的所有使用者看得到、初始精靈、平常只刷新那個媒體庫、還沒列出過時整台掃描、同一台主機、只能是 /data、硬鏈接），每項只在一句裡說（`saysOnce`，雙向樣本在檔內）。
- **第 3 點**：選「收在一處」。頁 1、2、4 選了既有只剩一句 `choice.existing.idle`（指到完成頁「閒著的套件內容器」，段名以 `{{section}}` 帶入同一個 key），`COMPOSE_PROFILES` 與 `docker compose stop` 只在完成頁（`IdleBundled`，照整份選擇算）。選之前、套件內那一台沒在跑的起回來補法（`BringBack`）不動——那是那一頁要用的。`SetupPage.consistency.test.tsx` 兩種語言各跑頁 1、2、4；完成頁原有的兩條照舊。
- **第 4 點**：`FilesPanel` 的 `overdue`：`resolve_after <= now` 時說 `media.files.jellyfin.searchingDue`（「Berth 即將再確認」／“Berth checks again shortly”），不帶時間。`MediaDetailPage.test.tsx` 兩種語言各一條。`resolve_after` 為 null 走不到（後端只在有值時回 `searching`）。

**驗證**

- vitest：104 檔 1955 passed。變異：放回一個「WebUI 登入」→ 命名閘門紅；頁 1/2/4 多畫一行 `docker compose stop` → 六條紅；作品頁先紅後綠；卡片事實與 `saysOnce` 在檔內雙向。
- pytest：4000 passed。`pre-commit run --all-files` 全部 Passed；typecheck、eslint、knip 乾淨。前端 e2e 35 passed（`existing.spec.ts` 改成斷言指向句、沒有 `COMPOSE_PROFILES=`）。
- Playwright 實跑（演練伺服器 `mixed` 與 `import`，各自暫存 `--config-root`，沒碰 `berth-local`）：頁 1、2、4 選既有各 1280 與 390（`p1-*`、`p2-*`、`p4-*`，390 寬不溢出、頁上 `COMPOSE_PROFILES=` 0 處）、完成頁「閒著的套件內容器」照給兩行（`p6-1280`）、作品頁攔截回應把 `resolve_after` 設成 4 秒前，1280 與 390 都是「Berth 即將再確認」，設成 3 分鐘後照舊「下一次確認在 3 分鐘後」（`media-due-*`）。截圖在 `.playwright-mcp/t103/`（gitignore）。

**critique（雙子代理）**

- 分數：**26 → 27/40**（trend 24 → 26 → 27；快照 `.impeccable/critique/2026-10-14T05-22-48Z__web-src-pages-setuppage-tsx.md`）。detector CLI 0 筆；overlay 只有 `nested-cards`（泊位板 panel，偏誤報）與頁 3 一筆欄高失衡。
- 這張票的四點：「介面登入」在標題、按鈕、剖面、步驟名、中英文一致（H4 從分歧變成只剩別的事）；指向句清楚、與完成頁段名逐字對得上。
- 新提的優先問題（不在這張票，留給使用者決定要不要開票）：P1 既有分支說明重複（頁 2 完成後「不改偏好」說 5 次、「會觸發外部程式」被淹沒）；P2 頁 4 既有已有站時孤立的「之後再說」；P2 頁 2、4 位址不沿用頁 1 的主機；P2 一致性（頁 4 標題形狀、塗漆、介面登入重新整理前後措辭不同、頁 1 剖面「不存下」與沿用矛盾）；P2 指向句頁 1、2、4 各一次且插在卡片與表單之間、完成頁停在待辦上、「容器。 第一行留空」多一個空格、兩顆「複製」同名。

**code-review 已處理**

- Spec：卡片刪字時丟了「新建的媒體庫所有使用者都看得到」與「平常只刷新那個媒體庫」，整台掃描的條件說得不準 → 補回，加進 `CARD_FACTS`；en 兩個標籤小寫開頭 → 大寫；brief、plan 機械替換多出的空格 → 修。
- Standards：「只說一次」缺「換標點不紅」那一向 → 抽出 `saysOnce` 補雙向樣本；長期的命名閘門與這張票的文案預算混在一檔 → 拆出 `interfaceLoginName.test.ts`；CONTEXT.md 的 _Avoid_ 沒說「WebUI 帳號／帳密」為何照留 → 寫明；`docs/guide/existing-services.md` 改完沒重新折行 → 折。

**code-review 未處理的發現**

- Standards（判斷）：後端 docstring 的改名沒有閘門守（`interfaceLoginName.test.ts` 只掃 `web/src`）；後端指偏好鍵的「WebUI 帳號」照留。
- Spec（提醒）：resolver 長時間停擺時，作品頁會一直說「即將再確認」；票面沒要求處理。
- critique A 實跑時看到：`docs/development.md` 說 `mixed` 的既有 qBittorrent「填任何位址與帳密都測得過」，`scripts/fake_setup_server.py` 的 `NAS_QBITTORRENT_LOGIN` 其實只收 `admin` / `adminadmin`（或留空）。
- 2026-10-14 使用者決定：P1 與 P2 一致性開成票 104；頁 4 孤立的「之後再說」、頁 2／4 沿用頁 1 的主機、完成頁的峰終這一輪不做；指向句維持頁 1、2、4 各說一次。
