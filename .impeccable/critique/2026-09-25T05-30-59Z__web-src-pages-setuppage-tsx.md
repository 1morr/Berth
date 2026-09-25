---
target: 設定精靈 web/src/pages/SetupPage.tsx
total_score: 24
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\pages\\SetupPage.tsx"
target_fingerprint: "sha256:a112b3eb87e2ee9803a2e0cac3572b6143b96ae4d1e584c94eb31d5a2de9ae1e"
target_path: "C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\pages\\SetupPage.tsx"
timestamp: 2026-09-25T05-30-59Z
slug: web-src-pages-setuppage-tsx
closed: true
---
Method: dual-agent (A: design review, opus · B: detector + browser, sonnet)

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | 做完之後結果在首屏以下；換步後焦點掉到 BODY |
| 2 | Match System / Real World | 2 | 「開始靠泊」「冪等」「未指派」「complete 根目錄」「dev=/inode=」 |
| 3 | User Control and Freedom | 3 | 上一個泊位、回頭看、之後再說都在 |
| 4 | Consistency and Standards | 2 | 「加入 Berth 路徑」泊位 1 就地確認、泊位 3 直接做 |
| 5 | Error Prevention | 2 | 既有媒體庫加過 Berth 路徑，泊位 3 卻不預選它（已修） |
| 6 | Recognition Rather Than Recall | 2 | BTH 編號與第幾步要自己換算；既有 Prowlarr 的 key 要再貼一次 |
| 7 | Flexibility and Efficiency | 3 | 套件內全自動 |
| 8 | Aesthetic and Minimalist Design | 2 | Route 頁 15 條綠色纜繩、390 寬 2675px 長 |
| 9 | Error Recovery | 2 | 既有 Jellyfin 密碼錯只寫「POST /Users/AuthenticateByName: 401」 |
| 10 | Help and Documentation | 3 | 「這裡能做／不在這裡做」 |
| **Total** | | **24/40** | **Acceptable** |

## Design Specificity Verdict
LLM：為 Berth 量身做的（泊位板、BTH、實測端點、就地展開的纜繩），不是換個產品也能用的精靈。弱點是每一格同一個版型、剖面常常重抄右欄（泊位 1 的「將會做什麼」與序列同 7 列），板上一格寫來源（套件內 / 既有）不寫狀態。
Deterministic：`impeccable detect` CLI 0 條。瀏覽器注入：`skipped-heading`（剖面 h3 在 DOM 上排在步驟 h2 之前，每一步都有，真）、`text-overflow`（第 2 步剖面的 qBittorrent 端點，真，已修）、`first-viewport-column-overflow`（泊位 1、3，真，與 A 的「主要動作在首屏以下」同一件事）、`em-dash-overuse`（未填值的「—」，誤報）、`dark-glow`（偵測器自己的 overlay，誤報）、`flat-type-hierarchy`（卡片內小標，存疑）。390 無水平溢出；按鈕高 24–43px（WCAG 2.2 AA 的 2.5.8 是 24×24，過；44 是 AAA）。

## Priority Issues
- [P1] 既有服務的安全感：Berth 路徑加了卻不預選（已修，`routes._default_target`）；只有一條路徑時預選的是使用者自己的資料夾（brief §4.3 的決定），但 lede 寫「舊路徑不會被動到」互相矛盾；泊位 3 的「加入 Berth 路徑」沒有就地確認（泊位 1 有）。→ harden / clarify
- [P1] 焦點管理：換步、按下主要動作、確認之後焦點掉到 BODY；`SetupPage.tsx` 沒有任何 `.focus()`；剖面 h3 排在 h2 之前；偵測清單整塊 polite、每 3 秒重念。→ audit / polish
- [P1] 窄版主要內容在首屏以下：390 時 Route 的 h2 在 921px；剖面排在工作面之前（shape 的決定）。→ adapt / distill
- [P2] 錯誤是原始 HTTP：既有 Jellyfin 帳密錯「失敗 POST /Users/AuthenticateByName: 401」。→ clarify
- [P2] 紅色用在不擋路的事：選填的索引站連不上塗 blocked；加完之後主要鍵仍是「加入這 N 個站」。→ polish

## Persona Red Flags
Jordan：「開始靠泊」「冪等」「complete 根目錄」「dev=…inode=…」。Sam：焦點掉到 BODY、每一步 8 次 Tab 才到工作面、第 2 步三個輸入框都叫「位址」。Casey：第一屏沒有輸入框；BTH 2 的值截成「Web API…」。NAS 使用者：預選寫進舊資料夾、完成頁不列動過的東西、Prowlarr key 要再貼一次。

## Minor Observations
「套用這 5 個鍵」下面列 6 列；qBit 套用後「建議值」欄變「已經是這樣」看不到原值；Route 建好後剖面「這一輪要建的 Route 0」；Prowlarr key 位置兩處寫法不同（設定 → 一般 → 安全性 / 設定 → 一般）；第 2 步的「上一個泊位」回到的是管理員；既有 Jellyfin 做完「重新登入」仍是黃色主要鍵；qBittorrent 分類 `berth-電影` 中文進了機器 token；冷啟動第一秒寫「連得上，但回的東西不是這個服務」；管理員欄位留空時錯誤念兩次。已當場修：連線表單三個服務都寫 `:8096` 的範例位址、第 2 步剖面端點溢出、第 2 步寫死 `qbittorrent:8080`、完成頁「四個泊位」與既有 Jellyfin 的登入提示、前置列把探測中算成已判定、設定頁 TMDB 說明提精靈進度。

## Questions to Consider
- 套件內的偵測全是機器判斷，為什麼要按「開始探測」與「前往泊位 1」兩次？
- 最後一幕若是「用 skipper 登入，看到第一部可以播的片」，peak-end 會差多少？
- 預設就勾 The Pirate Bay 與 1337x，是產品立場還是方便？
