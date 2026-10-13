# 68 — 文案與狀態一致：精靈與設定頁的打磨

**Status:** done

**Blocked by:** 67（前面幾張都會改到文案，最後一次收）

**讀:** `docs/research/usability-audit-2026-10-07.md` §4.3、§8 P2-1–P2-5、P2-11、P2-12、P2-16（頁 1 右欄那一句）、P2-20、P2-21；截圖 s1-07、s1-08、s1-13、s2-05、s2-10、s3-01、s3-02、s3-03、s4-27、s4-29；`PRODUCT.md`、`DESIGN.md`

## 為什麼

審計各情境看到的小不一致。每一件單獨都不擋使用，但累積起來讓第一次用的人多想。

## 做什麼

1. 頁 4 還沒選來源時，右欄不寫「接法　你自己的 Prowlarr」（P2-1）。
2. 介面登入的狀態詞在頁 2、頁 4 一致；自動沿用進行中時，底欄不寫「還差 設定介面登入」（P2-2）。
3. 完成頁：
   - 沿用頁 1 那一組時，直接說「與 Jellyfin 同一組」（P2-3）；
   - 沿用上一位擁有者設的那一組時，說怎麼改（設定 → 介面登入）（P2-21）。
4. 頁 1 登入失敗（密碼錯、非管理員）也標在欄位上，與頁 2 一致（P2-5）。
5. 頁 1 右欄「不改這台 Jellyfin 的任何設定」改成與下一行「建立 API key」不打架的說法；密碼欄空著時的錯誤說「密碼沒填」（P2-16、P2-20）。
6. 既有 Jellyfin 頁的「停掉套件內那一台」提示在成為擁有者之後仍看得到；完成頁也提醒一次（P2-20）。
7. 重裝時頁 3 不自動跑（設計如此），頁上說一句為什麼、要按哪裡（P2-11）。
8. 搜尋的時間說明照實際範圍寫，例如「幾秒到一分鐘」（P2-12）。
9. 跑 `/impeccable critique`、`audit`、`polish` 掃一次精靈與設定頁（CLAUDE.md〈UI〉的里程碑收尾規則）。

## 驗收

- [x] 每一點都有 vitest 或前端 e2e 守著（zh-Hant 與 en），文案改動的 i18n 鍵成對
- [x] playwright 實跑精靈全程（S1 與 S2 各一次）截圖
- [x] impeccable 三步的結論與處理記在票的 Comments
- [x] 全部檢查、test、前端 e2e 綠燈；progress.md 記一行

## Comments

- 2026-10-08 票 55 補（`docs/research/unraid-trial-2026-10-08.md` §6 U5、U9）：頁 5 TMDB 的「這裡能做」說「測不過的 key 照樣存下來」（`web/src/i18n/resources.ts` 的 `tmdb.can`，zh-Hant 與 en 都是），與票 45「測過才存」相反。健康頁「最後成功 2 秒後」：瀏覽器時鐘比伺服器慢兩秒時相對時間說成未來。
- 2026-10-13 票 81 留下的兩點（使用者同意併進這張）：(1) 第一次選套件內、還在測試時，頁 2 的剖面仍是「將會做什麼」，頁 4 卻已經說「接法：套件內」，兩頁說法不一致；(2) 同一段時間頁 4 的 lede 仍是「先選 Prowlarr 是哪一台」，因為 `draft` 在送出套件內時被清掉，lede 看不到送出中的那一格。細節見票 81 的 Comments〈code-review 未處理的發現〉。

**做了什麼（2026-10-14）**

- **P2-1、票 81 留下的兩點**：頁 2 的剖面與頁 4 同一個做法（`cutawayOrigin`：存下的，或第一次選、請求還在路上的那一格），多一列「接法」；頁 2、頁 4 的標題與 lede 看 `draft ?? sending ?? 存下的`，送出中不再問「先選」。頁 4 還沒選時不寫接法（票 81 已做，這次補兩種語言的測試）。
- **P2-2**：介面登入那一條，這個 Berth 設的（`web_ui_login_by_berth`）是 `skipped` 也說「已完成」（`interfaceLogin.loginStatus`），頁 2、頁 4 同一個字；那一台原本就有的（重裝）照舊「已經是這樣」——說「已完成」會與完成頁的「這一輪精靈沒有設它」矛盾（code-review Spec 軸）。登入正在送（自動沿用或手動）時 `indexerGaps` 不列登入。頁 4 步驟名改成名詞「Prowlarr 介面登入」，設好之後不再標「必填」（critique）。
- **P2-3、P2-21**：後端記下寫進去的那一組是不是沿用 Jellyfin 帳密（`SetupQbittorrent/SetupIndexer.web_ui_login_reuses_owner`，API 多 `web_ui_login_reuses_owner`；`resolve_interface_login` 回的那一組保留 `reuse_owner`）。完成頁：沿用的說「密碼與 Jellyfin 同一組」，原本就有的說忘了去「設定 → 該服務」的「介面登入」換一組。
- **P2-5**：頁 1 登入被拒（帳密不對、不是管理員）標在帳密兩格上，套件內那一台的登入表單（`OwnerForm`）與既有那一台的連線並登入表單（`ExistingForm`）同一個判斷（`api/setup.refusesCredentials`）。
- **P2-16、P2-20**：頁 1 右欄只列會動的：「建立 API key」、「之後：媒體庫到頁 3 按『建立並檢查』時才動」（原本「不改這台 Jellyfin 的任何設定」與 API key 那一行打架）。密碼空著先說「密碼沒填」、只標密碼那一格。選了既有 Jellyfin 之後，「停掉套件內那一台」的兩行在擁有者成立（來源鎖住）之後照樣在；完成頁多一段「閒著的套件內容器」（`setup/IdleBundled`）：選了既有、套件內那一台還解得到主機名（`GET /setup/compose`）才列，給整份選擇算出的 `COMPOSE_PROFILES` 與 `docker compose stop`，三個都既有時說空的那一行就是只跑 Berth。
- **P2-11**：重裝（清單上的已經建好、這個 Berth 從沒跑過建媒體庫那一步、還沒有 Route，`autoDock.heldBack`）時頁 3 說為什麼沒自己開跑、要展開清單看過再按「建立並檢查」。這一輪自己建到一半停下的不算。
- **P2-12**：搜尋說明改成「通常要幾秒到一分鐘」。
- **票 55 補的兩點**：`tmdb.can` 在這張票之前已改成「只有測過的 key 才存下」（`auditCopy.test.ts` 守著），沒動。健康頁的「最後成功」：`Timestamp` 多 `past`（`relativeTime.relativePast`），已經發生的時間落在未來時說「現在」；健康頁、`PollerCard` 與精靈／設定頁的「測試於」用它，預約的時間（重試於、下一批）不用。

**票面留給實作的決定**

- 「與 Jellyfin 同一組」由後端記，不由前端的 `carriedTo` 推：前端那一份重新整理就沒了，完成頁常常是重新整理之後才看到。在寫入那一刻記一個布林，換台、自設一組、那一台原本就有的都清掉；同一組再送（`skipped`）不改它。
- 完成頁的提醒只列套件內那一台還在的（主機名解得到）；已經停了的不再叫人停。
- 名稱不用「unused」：CONTEXT.md 的 **Unused service** 是「選了不用 Prowlarr」，這裡是選了既有之後還開著的容器（code-review Standards 軸）。

**驗證**

- pytest：`tests/integration/test_setup_interface_login.py` 多三條（沿用的兩台都記著、加站之後還在；自設一組之後清掉；那一台原本就有的不算）。先紅後綠。全套 3997 passed。
- vitest：新檔 `SetupPage.consistency.test.tsx`，每一點 zh-Hant 與 en 各跑一次（42 條）；`indexerGaps.test.ts`、`Timestamp.test.tsx`；改了 `SetupPage.test.tsx` 兩條、`SetupPage.routes.test.tsx` 一條、`SearchPanel.test.tsx` 一條（舊文案）。變異驗證：`loginStatus`、`!locked`、`heldBack` 兩個條件、頁 2／頁 4 的 `sending`、`not_administrator` 標欄位、`reuses_owner`、`composeHosts` 過濾、`indexerGaps` 的 `loggingIn`、`Timestamp` 的 `past`、只標密碼格、必填標、空 profiles 那一句，各自改掉都紅。全套 102 檔 1887 passed。
- 全部檢查：`pre-commit run --all-files` 全部 Passed。
- 前端 e2e：35 條 33 passed，`wizard` 與 `existing-390` 兩條在 1ms 失敗、錯誤是 `browserType.launch: Timeout 180000ms`（當時 critique 子代理也在開瀏覽器），單獨重跑通過；polish 之後再跑精靈相關四條（wizard、existing，1280 與 390）全過。
- Playwright 實跑（演練伺服器、自己的暫存 `--config-root`，沒起容器）：S1（`bundled`，延遲頁 2、頁 4 的選擇與頁 4 登入請求拍送出中）、S2（`mixed`，頁 1 先密碼空著、再密碼錯、再對），各走到完成頁；另以 `reinstall` 看頁 3 的那一句。截圖在 `.playwright-mcp/t68/`（gitignore）：`s1-02`（頁 2 送出中說接法）、`s1-07`（自動沿用時「還差」只剩加站）、`s1-08`（加站後登入那一條「已完成」）、`s1-11`／`s1-12`（完成頁「與 Jellyfin 同一組」，中英）、`s2-01`、`v-01`（密碼沒填、只標密碼格、右欄新列）、`s2-03`（擁有者成立後停用指令照留）、`s2-08`、`v-02`、`v-03`（完成頁閒著的套件內容器，1280 與 390）、`s4-01`（套件內登入帳密錯標兩格）、`s4-03`（重裝頁 3）。`reinstall` 情境沒先跑 `reinstall-before`，頁 3 按下之後的檢查紅（情境前提，不是這張票的事），所以完成頁的「原本就有的」那一句只由 vitest 守著。

**impeccable 三步**

- **critique**（雙子代理：A 設計審查、B detector）：26/40。detector CLI 0 筆；頁 1 overlay 1 筆 `em-dash-overuse`（9 個：5 個是泊位板的空值「—」，誤報；4 個是「既有」卡既有文案的破折號，不是這張票改的）。A 的五個優先問題：頁 3 重裝時 lede 與新句子互相矛盾、介面登入叫法不一、完成頁的空 `COMPOSE_PROFILES=` 與單複數、密碼空著兩格都紅、頁 1 右欄「不改…才動」自相矛盾。
- **polish**（照 critique 一批改完、一輪確認）：heldBack 先說「不是第一次來」、改成「展開清單看過之後」；頁 4 步驟名改名詞、設好不標必填；完成頁文案改成複數說法並說空著就是只跑 Berth；密碼空著只標密碼格；頁 1 右欄改成「之後：媒體庫到頁 3 才動」。
- **audit**（照 audit 的 a11y 與 responsive 兩項手動對這張票新加的部分查，沒有另開子代理）：新加的都沿用既有元件（`Field`／`PasswordField` 的 `invalid`＋`describedBy`、`role="alert"` 的說明句、`CopyLine`、`CutawayRow`、`h3.label`），標欄位時兩格都指到同一句；沒有新顏色或尺寸 token；390 寬完成頁不溢出（長指令在 `CopyLine` 裡橫捲）。

**code-review 已處理**

- Standards：「unused」撞 CONTEXT.md 的 **Unused service** → 改名 `IdleBundled`／`complete.idle.*`；產品名常數重複 → `interfaceLogin.LOGIN_PRODUCT`；兩處各自判斷哪些拒絕算帳密 → `refusesCredentials`；`blankCredential` 算兩次、`OwnerStep` 的 `shown ? !onFields && …`、`RouteStep` 的巢狀三元 → 具名變數。
- Spec：重裝留下的登入說「已完成」→ 照 `web_ui_login_by_berth` 分；P2-1、P2-5（既有那一台的不是管理員）、P2-2 的「還差」補兩種語言的畫面測試；CHANGELOG 一句與實作不符 → 改。

**code-review 未處理的發現**

- Standards（判斷）：後端 `web_ui_username`、`web_ui_password_hash`、`web_ui_login_reuses_owner` 三欄總是一起寫、一起清（Data Clumps／Shotgun Surgery，這次改了六處）。收成一個 login record 要動兩個 setting model 與 migration 之外的寫法，留給下一次再加欄位時。
- Standards（判斷）：`qbittorrent.cutaway.kind` 裝的是來源；沿用頁 4 已有的 `indexer.cutaway.kind`，兩頁同一個 key 形狀。`Timestamp` 的 `past` 預設反過來更貼近多數呼叫點，但預約時間說成「現在」是錯的，預設照舊不夾。`IdleBundled` 以字串比對空的 `COMPOSE_PROFILES=`。
- Spec：`indexerGaps` 只看登入請求是不是在路上，自動沿用在 effect 裡才送，第一次畫出來的那一拍可能列著登入（實跑 `s1-07` 沒看到）。`Timestamp past` 也用在「測試於」（同一類的錯，票面只點名健康頁）。
- critique 提了但不在這張票：精靈的「WebUI 登入」與「介面登入」兩個叫法（頁 2 標題、按鈕）、頁 1「既有」卡的字量、頁 1、2、4 各給一次累積的 `COMPOSE_PROFILES`。
