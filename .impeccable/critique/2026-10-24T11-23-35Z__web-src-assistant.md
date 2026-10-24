---
target: M5 assistant panel, cards, AI settings, usage, AI activity
total_score: 27
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
target_identity: "file:/Users/roxy/orca/workspaces/Berth/t15/web/src/assistant"
timestamp: 2026-10-24T11-23-35Z
slug: web-src-assistant
closed: true
---
Method: dual-agent (A: design review + audit, opus · B: detector + browser measurement, sonnet)

Target: M5 surfaces — assistant side panel (`web/src/assistant`), result cards, ProposalCard, `/settings/ai`, `/settings/usage`, `/ai-activity`.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 確認卡與撤銷的結果不被念（status 等人按時 display:none / 撤銷後才 mount）；限流「30 秒」不倒數 |
| 2 | Match System / Real World | 3 | 活動頁輸入印 `source_id`、`route = 2`；AI 送的單標「手動」 |
| 3 | User Control and Freedom | 3 | 可逆有撤銷、不可逆有拒絕；窄版面板裡的連結走不出去 |
| 4 | Consistency and Standards | 2 | 焦點規則面板內五處破、活動頁守住；「只能聊天」三種顏色；活動頁 summary 無 ExpandHint |
| 5 | Error Prevention | 3 | 預覽先行；刪檔路徑黏成一片；AI 已送的列沒標記 |
| 6 | Recognition Rather Than Recall | 2 | 空面板不提示能做什麼；歷史不標目前那一則 |
| 7 | Flexibility and Efficiency | 3 | Enter/Shift+Enter/組字都對；切期間後焦點掉 body |
| 8 | Aesthetic and Minimalist Design | 3 | 克制；設定頁「只能聊天」說三遍 |
| 9 | Error Recovery | 3 | 拒絕理由是人話；key 被拒狀態仍寫「設定好了」 |
| 10 | Help and Documentation | 2 | 面板沒有能力說明 |
| **Total** | | **27/40** | **Acceptable（上緣）** |

Audit：A11y 2、Performance 3、Theming 4、Responsive 2、Integrity 3 = **14/20**。

## Design Specificity Verdict

LLM：為 Berth 做的。航海日誌式對話、工具三態、確認卡的 rule-strong + assigned、Route/資料夾名/Jellyfin 收錄/絕對路徑都是產品自己的內容。錯失：空面板一句通用的「跟助理說你想做什麼」。

Deterministic：CLI 對 `web/src/assistant` 與五個頁面檔 0 條。Overlay 7 個畫面 "No anti-patterns found"；`/ai-activity` 1 條 `flat-type-hierarchy`（面板 h3 11px 的 `.label` 與頁面 h1 18px 同屏，相鄰比 1.17）——是設計系統刻意的 `.label` 標題（DESIGN.md Typography），判為系統選擇不修。量測：頁面橫向捲動 0、對比 <4.5 0 條（深色最低 6.53、亮色 5.71）、無名控制項 0、console 0。兩邊一致：確認卡按下後焦點落 BODY。

## Priority Issues

1. **[P1] 面板裡做完決定後焦點掉回 body，結果不被念**：ProposalCard 確認/拒絕、送單卡與訂閱卡撤銷、歷史清單點一列。`ProposalCard.tsx` status 帶 `empty:hidden`；`SubmittedJobCard`/`SubscribedCard` 的 status 撤銷後才 mount。修：status 一直掛著，決定/撤銷後焦點交給它（同 `AiActivityPage` 的做法）；`onPick` 後聚焦輸入框。
2. **[P1] `lg` 以下面板裡的連結換了頁卻看不到**：WorkLink、看這一筆、去 RSS 頁、去作品頁搜全部、去設定。修：AppShell 監聽 pathname，窄版換頁就收起面板，刪掉「活動」的特例。
3. **[P2] 窄版面板打開時輸入框在畫面外（390：y994/844）；照記憶打開時蓋掉落地頁**。修：窄版面板佔滿畫面；記憶只在 lg 以上生效。
4. **[P2] AI 活動頁的「輸入」是內部欄名，EN 被 `.label` 大寫成 `SOURCE_ID`；summary 沒有 ExpandHint**。
5. **[P2] 用量表 EN 390 `claude-haiku-5-5` 從字中間斷開**（`UsageTable.tsx` 命中率欄 `whitespace-nowrap` 的 `13 unreported`）。
6. **[P2] 「只能聊天」三種顏色（設定狀態 assigned、測試結果 blocked、面板 neutral）；key 被拒時狀態仍寫「設定好了」**。

## Persona Red Flags

- Sam：五處焦點遺失；搜尋卡多顆同名「送單」（WCAG 2.4.6）；從活動頁打開面板再 Esc 焦點回「助理」鍵不回原鍵。
- Casey：卡裡的連結點了沒反應；輸入框在畫面外；抬頭四顆 24px 小鍵、EN「CLOSE」掉第二行。
- Alex：無開面板快捷鍵；用量頁切期間焦點掉 body（`FilterBar` 全站共用）。
- NAS 管理員手機：從通知點進來先看到上次沒關的助理；點「看這一筆」走不出去。

## Minor Observations

- 撤銷後送單卡抬頭仍「已送出」；AI 送的 Job 在 JobFacts 標「手動」。
- 搜尋卡上 AI 已送的那一列沒有標記。
- 刪下載卡的絕對路徑黏在一起；「Berth 套件內」散文走 `.value wrap-anywhere` 被斷成「Berth 套/件內」。
- 限流 Notice 的秒數不倒數；「下一次輪詢 4 週前」（下一次落在過去時應改說法）。
- 用量直條輸出段 1–5.8px（前票遺留，比例誠實，不修）。
- 1280 開面板時頁首折成三列。
- 串流時每個 chunk 重畫整份逐字稿（P3）。

## Questions to Consider

- 面板空的時候，為什麼不說「在這一頁你可以叫我做什麼」？
- 確認卡等人按時，同一屏兩塊調度黃，頁面主鍵要不要讓位？
- AI 活動頁只列做成的事；被程式擋下的那幾筆不正是管理員最想看的？
