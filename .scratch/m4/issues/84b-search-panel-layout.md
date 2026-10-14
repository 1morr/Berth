# 84b — 搜尋區塊：名字與季的標籤移到上方，預覽與代價收成一塊

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `web/src/media/QueryChoices.tsx`、`web/src/media/SearchPanel.tsx`（`QueryPreview`、`QueryCost`）；`web/src/i18n/resources.ts` 的 `search.*`；`.scratch/m4/search-choose-shape.md`（〈查詢與代價〉〈狀態與範圍〉）；`DESIGN.md`〈Components〉的 `QueryChoices` 條目與〈Typography〉的標題規則；`PRODUCT.md` 原則 2

## 為什麼（2026-10-14 使用者）

票 84 做完之後，作品頁的搜尋區塊看起來比較差（截圖：《無間道II》，電影、三顆名字 chip）。使用者第一個注意到的是
「名字被推到一邊」，提議把「名字」這兩個字拿掉、只留 chip。檢查之後的四個問題：

1. **兩條標籤軸。** 關鍵字、入庫到、資料夾將會是，標籤都在欄位上方；只有「名字」「季」走 `ChoiceRow` 的
   `sm:grid-cols-[6rem_…]` 左欄。chip 從一個跟上下都對不齊的 x 起跑，「其他別名」又再縮一次。
2. **同一組字印兩次。** 沒有季的時候，開著的 chip 與底下「Berth 會問這幾個：」那一行是同一組名字。
3. **四行同色同字級的散文**：會問、查詢清單、代價、要等多久，全是 `text-xs ink-dim`，讀起來是一段說明，
   不是按 chip 的回饋。
4. chip 與主輸入框幾乎一樣高、搶重量（不在本票，見〈不做〉）。

使用者選了整套版面（不是只搬標籤）。標籤**搬到上方而不是刪掉**：劇集有第二排季 chip，兩排無標籤的 chip
疊在一起讀不出分界；整塊板每個欄位都有模板字標籤（DESIGN.md）。

## 做什麼

目標版面（1280 寬；390 寬是同一個順序疊下來）：

```
關鍵字                                          入庫到
[留空就用下面開了的名字                     ]   [Movies       v]  [  搜尋  ]

名字
[Infernal Affairs II  英文名] [無間道II  原名·中文名] [无间道II  簡體中文名]
其他別名 18 個 · 展開

季                                    ← 劇集、照作品名搜時才有
[不指定季] [S01] [S02]

會問 · 3 個查詢
Infernal Affairs II   無間道II   无间道II
每個索引站各佔 3 格請求預算（每站每小時 60 格）；索引站要現場去連每一個追蹤站，通常要幾秒到一分鐘。

資料夾將會是
Infernal Affairs II (2003) [tmdbid-11647]
```

1. **標籤一條軸**：`ChoiceRow` 在所有寬度都是標籤在上、chip 在下（拿掉 `sm:grid-cols-[6rem_…]` 與 `sm:pt-2.5`）。
   chip 的左緣與關鍵字輸入框、資料夾名對齊。別名的展開摘要跟著 chip 對齊，不再另縮。
2. **預覽變成一個有標籤的欄位**：「Berth 會問這幾個：」這一句換成與其他欄位同一種的 `.label ink-dim` 標籤，
   數量寫進標籤（`會問 · 3 個查詢`／`WILL ASK · 3 QUERIES`，數字照 The Tabular Rule）。底下照舊是後端給的查詢清單
   （`.value`、一個查詢一項、`aria-label` 不變）——劇集開了季之後清單與 chip 不同，所以清單不拿掉、也不做「與 chip
   相同就藏」的條件。
3. **範圍照實說，只在不是照作品名搜的時候**：
   - 打了關鍵字：標籤是 `會問 · 1 個查詢`，清單就是那一句；`willAskTyped` 那一句不再需要。
   - 搜缺的集（`willAskMissing` / `willAskMissingSeason`）：標籤底下保留那一句範圍與「改回作品名搜尋」鍵，
     因為「問的是缺的集」從清單本身看不出來。
   - 分批預覽那一行（`search.batch.preview`）照舊。
4. **代價與等待併成一句**：`search.cost` 去掉已經移到標籤的「會發 N 個查詢」，與 `search.slow` 併成一句
   （`ink-dim text-xs`）。查詢數是 0 時不畫。不能搜（`refusal`）時整句換成原因（`ink text-sm`，仍掛在搜尋鍵的
   `aria-describedby`），等待那半句不出現。
5. **文件同步**：`DESIGN.md` 的 `QueryChoices` 條目改寫（標籤位置、預覽標籤、代價一句）；`search-choose-shape.md`
   的版面草圖不改（那是當時的 shape），在本票 Comments 記一行「84b 推翻了它的左標籤」。progress.md「偏差與決定」記一行。

建議走法：`/impeccable layout`（第 1–4 點）→ `/impeccable polish`。

## 不做

- chip 尺寸：`ToggleChips` 與結果表篩選（票 83）共用 `FILTER`，縮小會兩邊一起變，另外決定。
- 不改後端、不改 `GET /api/search/queries` 的形狀、不改查詢的產生與上限。
- 不移動資料夾名區塊、Route 下拉、纜繩、結果表。

遇到上面沒涵蓋的設計決定（例如英文標籤的單複數、窄版要不要把代價句再拆）就停下回報，不自行拍板。

## 驗收

- [ ] 1280 寬：「名字」「季」標籤在 chip 上方；第一顆名字 chip、別名摘要與關鍵字輸入框的左緣 x 相同（playwright 量 `getBoundingClientRect`，差 ≤ 1px）
- [ ] 預覽標籤帶查詢數，與清單項數相同；照作品名搜時畫面上沒有「Berth 會問這幾個」那一句；vitest（zh-Hant 與 en）
- [ ] 打了關鍵字、搜缺的整部、搜缺的某一季、分批、`noName`、`tooMany`、`tooManyNames` 七種狀態各有 vitest，說出原本說的那件事（範圍句、改回作品名鍵、拒絕原因掛在搜尋鍵描述上）
- [ ] 代價與等待是同一個元素；拒絕時只有原因、沒有等待那半句；`SetupPage.consistency.test.tsx` 的「幾秒到一分鐘」改看新的 key，仍兩語言都守
- [ ] 不再使用的 i18n key（`willAsk`、`willAskTyped`、`slow` 或其併入後的舊 key）兩語言都刪掉，沒有殘留引用
- [ ] playwright 實跑 1280 與 390 寬截圖：電影（只有名字）、劇集（名字＋季＋別名展開）、搜缺的集；390 寬無橫向捲動
- [ ] `/impeccable critique` 前後分數記在 Comments
- [ ] `DESIGN.md` 條目已改；全部檢查、vitest、前端 e2e 綠；progress.md 已更新
