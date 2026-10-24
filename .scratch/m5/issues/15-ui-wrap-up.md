# 15 — M5 UI 收尾

**Status:** done

**Blocked by:** 07b、10、11、12、13、14

**讀:** CLAUDE.md〈UI〉；`DESIGN.md`、`PRODUCT.md`；`.scratch/m5/` 的各份 shape

## 為什麼

CLAUDE.md：每個里程碑 UI 收尾前跑 `critique`、`audit`、`polish`。M5 新增的側面板、四種結果卡、確認卡、設定的 AI 一格、用量頁、AI 活動頁一起過一遍。

## 做什麼

1. `/impeccable critique`、`audit`（含無障礙、鍵盤操作、窄螢幕下的側面板）、`polish`。
2. 修掉發現的問題；不修的寫進 Comments 並說理由。
3. `DESIGN.md` 同步（`/impeccable document` 若有新的設計系統元件）。

## 驗收

- [x] 三個步驟的發現都處理或記錄
- [x] 窄螢幕與鍵盤操作實跑（playwright 截圖）
- [x] 全部檢查、pytest、vitest 綠；DESIGN.md、progress.md 已更新

## Comments

### 2026-10-24 實作

截圖在 `15-ui-wrap-up/`（修完之後的實跑，替身 8660–8663：`assistant`、`assistant-rss`、`usage`、`healthy`）。

**critique 與 audit（做什麼 1）**：A（設計審查＋audit，opus）與 B（偵測器＋量測，sonnet）分開跑，各用一組替身。
- critique **27/40**（Acceptable 上緣），audit **14/20**（a11y 2、效能 3、主題 4、響應式 2、實作一致性 3）。快照
  `.impeccable/critique/2026-10-24T11-23-35Z__web-src-assistant.md`（修完之後目錄內容變了，`critique-storage latest` 回 2：待辦自動結案）。
- 偵測器：CLI 對 `web/src/assistant` 與五個頁面檔 0 條；overlay 七個畫面 0 條，`/ai-activity` 一條 `flat-type-hierarchy`
  （面板 11px 的 `.label` 標題與頁面 h1 同屏）——設計系統刻意的 `.label` 標題，不修。量測：頁面橫向捲動 0、對比 < 4.5 的 0 條
  （深色最低 6.53、亮色 5.71）、無名控制項 0、console 0。
- **使用者拍板三題**：P1 + P2 全修（加幾條順手的）、窄版面板佔滿畫面而記憶只在 `lg` 以上、AI 活動頁欄名照原樣只修排版。

**修掉的（polish，做什麼 2）**

| 發現 | 處理 |
| --- | --- |
| P1 做完決定之後焦點掉回 body、結果念不到（確認卡確認與拒絕、送單與訂閱撤銷、歷史清單挑一則） | `components/useFocusOnSettle`：按下去的鍵跟著結果消失時，焦點落在說結果的那一格（只在焦點真的掉到 `body` 時給；重整後的舊卡不給）。確認卡的 `role="status"` 從 `empty:hidden` 改 `empty:sr-only`（留在無障礙樹裡）。AI 活動頁改用同一支，拿掉 `outline-none`。歷史清單挑完焦點回輸入框。vitest 五條改前紅＋hook 三條 |
| P1 窄版面板裡的連結換了頁卻看不到 | 面板 `onClick`：`lg` 以下、路由接下的站內導覽（`defaultPrevented`）就收起面板；抬頭「活動」的特例刪掉。另外每條路由各包一份 `AppShell`，換頁本來就重新掛載——窄版不照記憶打開之後，跨頁的連結本來就會收起，`onLeave` 管的是同一頁的連結（在活動頁按「活動」）。vitest 兩條，`onLeave` 拿掉會紅（實跑過） |
| P2 窄版打開時輸入框在畫面外；照記憶打開蓋掉落地頁 | `lg` 以下面板開著時頁首也收起（收起不是疊上去）；`usePanelOpen` 只在 `lg` 以上照記憶打開；關閉後焦點等頁首畫回來再回「助理」鍵。實跑 390：輸入框 y 705–789 / 844；768：y 885 / 1024 |
| P2 AI 活動頁「輸入」欄名英文被大寫、看不出能展開 | `DetailLine code`（同 `CutawayRow` 的 `code`，`.value text-xs ink-dim`），摘要加 `ExpandHint`。照使用者選的，不翻譯參數名、不把 id 換成名字 |
| P2 用量表英文 390 `claude-haiku-5-5` 從中間斷開（票 13 留下的） | 「N unreported」只在 `sm` 以上不換行，窄版每組 token 不拆。實跑 en 390：三個模型名都一行、token 各組一行、橫向捲動 0 |
| P2 「只能聊天」三種顏色；key 被拒仍寫「設定好了」 | 設定頁的測試結果改 `assigned`（同狀態那一格；面板維持 `neutral`——那裡是誰都改不了的說明）。這次打開頁面測過、沒過、之後沒改時，狀態那一格多一句「剛才的測試沒過，見下方的「測試」。」（只看連線那一步的 `failure`，工具那一步另有 `tools_failure`，不會誤判）。vitest 兩條 |
| 順手：送單卡撤銷後抬頭仍「已送出」 | 換成「已撤銷」 |
| 順手：確認卡「Berth 套件內」斷成兩行、英文說明等寬 | `Line prose`：只有網址是 `.value wrap-anywhere`，其餘散文 |
| 順手：搜尋卡好幾顆同名「送單」 | `SubmitAction describedBy`（必填）指著那一列的發佈名；搜尋頁的結果表同一顆元件，一起改。vitest 兩處 |
| 順手：用量頁切期間之後焦點掉回 body | `FilterBar`（全站共用）換選之後焦點落在新選的那一格（`tabIndex={-1}`）。vitest 一條 |
| 範圍外但做了：訂閱卡「下一次輪詢 4 週前」 | 算出來的時間已經過了說「半分鐘內」。一行，且直接誤導，所以修了（使用者選的範圍裡 P3 是只記）。vitest 一條，拿掉會紅 |
| 範圍外但做了：歷史清單不標目前那一則 | `aria-current` 加重線＋`deck` 底（DESIGN.md 就地確認裡選中那一列的樣子）。vitest 一條 |
| **實跑時抓到的 bug**：站內連結進作品頁再叫助理「這部缺的集」，它說「先打開一部作品的頁面」 | 作品連結把 id 編碼過（`tv%3A120089`），路由的 pathname 照網址原樣，後端拿這串找不到作品。e2e 只直接開 `/media/tv:120089` 所以沒抓到。後端 `assistant._viewing` 先 `unquote`；整合測試一條改前紅。CHANGELOG 已記 |

**DESIGN.md（做什麼 3）**：助理側面板（窄版、記憶、連結收起、歷史清單、確認卡與撤銷的焦點、送單卡抬頭、訂閱卡的「半分鐘內」、
搜尋卡的 `aria-describedby`、只能聊天的顏色）、AI 活動頁的輸入、用量表窄版、篩選列的焦點、The Focus Follows The Confirm Rule
加 `useFocusOnSettle`。`/impeccable document` 只重寫 sidecar（子代理）：`.impeccable/design.json` 元件 16 → 22（助理面板、結果卡外框、
確認卡、用量圖、用量表、AI 活動列），Named Rules 19 條不變。e2e：`assistant`、`assistant-rss` 的 390 照新行為改（`e2e/panel.ts` 的
`reopenOnNarrow`），第一條多斷言窄版每次打開網頁看到的是那一頁、頁首一起收起、輸入框在畫面內。CHANGELOG、guide、development.md 同步。

**沒修的（寫在這裡）**

- **critique 的 P3 與次要觀察**：從活動頁打開面板再 Esc，焦點回「助理」鍵而不是原本那顆（面板不知道誰打開它；回頁首的「助理」是可預期的）；
  EN 抬頭「CLOSE」掉第二行、抬頭四顆鍵 24px（過 WCAG 2.5.8 AA，不到 44px）；1280 開面板時頁首折成三列；沒有開面板的快捷鍵；
  AI 送的 Job 在 `JobFacts` 標「手動」（`JobTrigger` 只有 manual / rss / reimport，AI 送的走 `add_manual_download`；加一種要動資料模型與 migration，留給 M6 背景接管一起看）；搜尋卡上 AI 已送的
  那一列沒標記；刪下載卡的絕對路徑一條接一條（每條一個 `li`，視覺上沒分開）；限流 Notice 的秒數不倒數（存下的是當時的 `retry_after`）；
  空面板只有一句通用的「跟助理說你想做什麼」（critique 的挑釁問題：可以依頁面提示）；串流時每個 chunk 重畫整份逐字稿（家用量無感）。
- **用量直條的輸出段 1–5.8px**（票 13 留下的）：比例是對的，讀數列與表格給得出確切數字；加最小高度會扭曲比例。不修。
- **`ActivityEntryOut.result_type` 是 `str`**（票 14 說「票 15 收尾時可再看」）：看過，不改。存下的舊結果型別也會出現在活動頁，
  收成封閉的 `ToolResultType` 會讓那些列在 API 驗證時出錯；認不得的型別現在不印對象、撤銷用通用文案，是對的退路。
- **設定 → AI 測試失敗時同一段字出現在 `aria-live` 區與 `role=alert` 裡**（B 量到）：`blocked` 的 `Notice` 自帶 `role=alert`，
  外層的 live region 是給成功結果用的。重複宣告，但兩處是同一句。不在這一輪改 `Notice`。
- **面板只在點擊連結時收起**（Spec 軸）：程式自己 `navigate` 的導覽不會收起面板。現在面板裡沒有這種導覽；以後有的話改在 `AppShell`
  聽 pathname。
- 刪下載、送單撤銷之後 console 會有一筆那個 Job 的 404（卡片照設計說「這一筆不在了」），不是錯誤。

### code-review（`7305d73e` 起）

- **Standards**：硬違規一條已補——搜尋頁結果表的「送單」說明沒有測試（`SearchPanel.test.tsx`）。判斷題改了：「焦點掉了沒」收成
  `focusIfLost`（`useFocusOnSettle` 與 `FilterBar` 共用）、`DetailLine` 的 `machine` 改名 `code`（同 `CutawayRow`）、`describedBy` 改必填、
  `readyButFailed` 改成獨立的一句（原本是接在「設定好了」後面的半句「但……」）。沒改：`AppShell` 的 `returning` 與面板的 `backToChat`
  同形（一個在外框、一個在面板，各一處，抽出來比兩處更難讀）；`DetailLine code` 與 `ProposalCard` 的 `Line prose` 相似（兩份 `dl` 的欄寬不同，
  照舊各一份）；`defaultPrevented` 綁著 TanStack Link 的行為（註解寫明）；`code` 與 `prose` 兩個類別字串改的地方沒測 class（樣式由實跑截圖驗）。
- **Spec**：沒有做錯的。範圍外的三件（後端路徑解碼、下一次輪詢、歷史清單標目前那一則）在上表說明；票 14 的 `result_type`、critique 的 P3
  寫在「沒修的」。新的焦點行為只有 vitest 與這一輪的實跑守著，e2e 沒有加對應的斷言（驗收沒要求）。
