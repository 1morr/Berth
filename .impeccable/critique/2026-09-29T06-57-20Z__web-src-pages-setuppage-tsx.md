---
target: M4 票 15 設定精靈（手動選擇）
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\pages\\SetupPage.tsx"
target_fingerprint: "sha256:654a0f1edb1258e3ba02e50378ab1d2a65fbdc6a0d7a62d64f1befe9e98dd802"
target_path: "C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\pages\\SetupPage.tsx"
timestamp: 2026-09-29T06-57-20Z
slug: web-src-pages-setuppage-tsx
---
Method: dual-agent (A: design review, opus · B: detector + browser, sonnet)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | 泊位板選了來源之後狀態字變成「套件內 / 既有」，紅格綠格讀起來一樣（已修） |
| 2 | Match System / Real World | 2 | 剖面列 `POST /Startup/Configuration`、`temp_path_enabled`；「開始靠泊」看不出會建媒體庫 |
| 3 | User Control and Freedom | 3 | 換另一格的確認 Esc 收不起來；既有表單打開後沒有取消 |
| 4 | Consistency and Standards | 2 | 換台確認沒走 `ConfirmPanel`；既有 Prowlarr 的結果不是測試那一條的形狀；頁 4 標題與頁 1、2 不同句式 |
| 5 | Error Prevention | 3 | 不預選、密碼兩次、換台確認；但方向鍵瀏覽就會觸發套件內的選擇與測試；9 站預設全勾 |
| 6 | Recognition Rather Than Recall | 3 | 剖面先說後果、泊位板常駐 |
| 7 | Flexibility and Efficiency | 2 | 沿用 Jellyfin 帳密有幫助，套件內那條路密碼仍打 4 次 |
| 8 | Aesthetic and Minimalist Design | 2 | 頁 3 十五列全綠全展開；剖面與纜繩列重複端點；TMDB 頁兩顆黃色主鈕 |
| 9 | Error Recovery | 3 | 紅燈補法與可複製指令好；頁 4 Prowlarr 原文英文錯誤、補法連結指到容器主機名 |
| 10 | Help and Documentation | 3 | lede、剖面、「這裡能做」齊全，沒有外部文件連結 |
| **Total** | | **26/40** | **Acceptable** |

## Design Specificity Verdict

**LLM assessment**：為 Berth 量身做的——泊位板、模板噴字標籤、dt/dd 剖面、塗滿整格的狀態色、零圓角、纜繩列在深淺兩個主題都一致。最通用的一塊反而是這一票的主角：「套件內 / 既有」兩張卡就是一般的 radio card，沒有用泊位的語彙（例如把這條纜繩會連到哪裡畫在卡上）。

**Deterministic scan**：CLI `impeccable detect` 對 `web/src/setup`、`SetupPage.tsx`、`ServiceConnection.tsx`、`InterfaceLoginSection.tsx` 0 條。瀏覽器注入 6 條：detector 抓到、設計審查漏掉的是 `skipped-heading`（qBittorrent「要求帳密」的 h2 → h5「手動步驟」）與 390 寬泊位板 BTH 2 的 `text-overflow`（版本字串被截、沒有 title）。False positive：`first-viewport-column-overflow`（grid 列 stretch，左欄剖面是 sticky）、`nested-cards`（標題列的分色，不是卡片套卡片）、`em-dash-overuse`（中文「——」與空值佔位「—」）、兩條重複注入的自我污染。

**Visual overlays**：注入在子代理自己的分頁裡跑，分頁已關，沒有留給使用者的 overlay。

## Overall Impression

骨架對了：先選再測、紅燈就地給補法、擁有者的峰值落地。最大的機會在「常態太吵、例外太安靜」：頁 3 一牆綠、頁 4 一次四塊英文紅字，而真正要注意的那一格（連不上的服務）在泊位板上念不出來（已修）。

## What's Working

1. 剖面在選之前並列兩種選擇的後果（頁 2：套件內寫五個鍵與 WebUI 登入 / 既有一個全域偏好都不寫）——產品原則 2 的直接實作。
2. 紅燈就地給補法：要求帳密時有手動步驟、可複製的 `docker compose restart qbittorrent` 與重新測試；`COMPOSE_PROFILES` 照當下選擇算。
3. 擁有者流程：密碼不一致就地說、成立之後鎖住並說明去哪裡改；深色與 EN 在 390 寬沒有橫向捲動。

## Priority Issues

- **[P1] 泊位板選了來源之後狀態字被來源取代**（已修）：紅格 BTH 2 與綠格 BTH 1 都寫「套件內」，違反三重編碼與 PRODUCT.md 的 AA 驗收。改成狀態字跟信號、來源進詳情列；詳情列不再 `truncate`。Suggested: /impeccable clarify
- **[P1] 擁有者密碼錯時整頁捲回頂端**（已修）：`router.leaveOnSignOut` 把 `claimOwner` 的 401 當成 session 失效重跑守衛。加 `CLAIM_OWNER_KEY` 例外。Suggested: /impeccable harden
- **[P1] 頁 4 單站失敗的呈現與補法錯位**：Prowlarr 原文英文 `role=alert` 一次四塊、「Query successful, but no results」被說成連不上、補法連結是容器主機名、失敗後主鈕數的是已加好的站、紅色在這裡不代表阻擋。Fix：常見失敗映射成 i18n 原因、原文收進 details、失敗收成一條 `assigned` 摘要、主鈕只數沒加的。Suggested: /impeccable clarify
- **[P2] 換另一格的確認沒照就地確認規則**：自組按鈕不是 `ConfirmPanel`（焦點不移、Esc 無效）；確認前 radio 已顯示選中而標題與 lede 停在舊來源；警告文案不分來源（從既有換走也說「Berth 寫過那一台的偏好」）；方向鍵瀏覽就觸發套件內的寫入（audit 同一條）。Suggested: /impeccable harden
- **[P2] 常態塗漆與重複資訊**：頁 3 Route 檢查 15 列全綠全展開；剖面與纜繩列重複端點；頁 1 鎖住說明出現兩次；每屏兩顆黃色主鈕。Suggested: /impeccable distill

## Persona Red Flags

**Jordan（第一次用）**：「開始靠泊」看不出會建媒體庫；建完出現「這個泊位的事做完了」但泊位板仍是「待靠泊」、真正的下一步是頁面上方的次要鈕；剖面列 `POST /Startup/RemoteAccess`；頁 2 寫「五個鍵」卻有 6 列；9 站預設全勾。

**Sam（鍵盤 / 螢幕閱讀器）**：泊位板念不出紅燈（已修）；第一次測試結果不被宣告、「改位址或憑證」之後焦點越過表單（audit P1，已修）；換台確認焦點不動、Esc 沒反應；頁 4 一次四個英文 `role=alert`；介面登入的密碼欄不在 form 裡（console 警告，密碼管理員可能抓不到）。

**Nadia（NAS 使用者，已經在跑 Jellyfin 與 qBittorrent）**：既有位址的 placeholder 等寬字、oklch 0.45，看起來像已填；從她自己的 qBittorrent 換到套件內時警告說 Berth 寫過她那一台的偏好——不實；三個都選既有時 `COMPOSE_PROFILES=` 空白一行沒有說明；既有 Jellyfin 的「改位址或憑證」表單只有位址。

## Minor Observations

- 頁 1 回頭看說「這裡能做：重新測試」，綠燈時沒有那顆鈕。
- 頁 3 Route 建完之後剖面「這一輪要建的 Route」仍是 0。
- 390 寬 CopyLine 內容比容器寬 13 px，要框內橫捲。
- 每頁載入時 h2 拿到程式焦點，焦點框像標題加了外框。
- 完成頁只有路徑表，沒交代三個服務的來源、登入、沒加上的站。
- 3 秒自動重測沒有實跑（fake 的 bundled / mixed 沒有「還在啟動」），只讀了程式碼。

## Questions to Consider

- 泊位板的一格只能寫一個字時，該寫「它現在怎樣」還是「它是誰的」？（本輪答：前者）
- 頁 3 的 15 條檢查，有哪一條值得在綠燈時被看見？
- 四個預設站在 fake 裡就會失敗，預設全勾是在幫使用者，還是在製造第一次的紅燈？
- 完成的那一刻，Berth 想讓人記住的是一張路徑表，還是「五個泊位都繫上了」？
