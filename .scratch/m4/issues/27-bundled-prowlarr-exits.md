# 27 — 套件內 Prowlarr 不再是死路：換 key 有出口、已有站算數、登入差什麼說清楚

**Status:** done

**Blocked by:** 23

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 2、9、22 條）；plan §9.3 第 4 點；票 20 的 `## Comments`

## 為什麼（2026-10-01 精靈實測，全新安裝）

- **換了 API key 就沒有出口（P1，實測證實）。** 套件內的 key 只在「選」那一刻讀掛載（`berth/services/setup.py:409-412`），
  重新測試用存下的舊 key（`setup.py:462-466`）。在 Prowlarr 重新產生 key 後：連線卡仍綠、站清單消失、沒有錯誤；重新測試後
  補法講的是 qBittorrent 免密白名單（`ServiceChoice.tsx:724-726`、`resources.ts:247-248`），照做沒用；再點「套件內」卡片
  不送請求；讀清單失敗時 `modeOf` 回 null（`IndexerStep.tsx:197`），畫面只剩「之後再說」。截圖 L-P2-3-01～06。
- **已經有站時頁 4 過不去（實測證實）。** 重裝保留 Prowlarr 設定時，已有的站不在候選清單，`_indexer_settled` 要至少一條
  站的步驟（`setup.py:733-737`）；設好介面登入仍停在頁 4。選「之後再說」後完成頁說「搜尋不到任何東西」（`resources.ts:888`）。
  截圖 R-09～11。
- **加完站、沒設介面登入時沒說為什麼不能前進（實測證實）。** 登入區在兩屏之外（`IndexerStep.tsx:302-345`）。截圖 B1-13。

## 做什麼

1. 套件內 Prowlarr 每次測試都重讀掛載的 key；`auth_required` 的補法是 Prowlarr 自己的（「Berth 讀到的 key 不被接受：
   確認 `${CONFIG_ROOT}/prowlarr` 有掛進 Berth」），不是白名單。
2. 讀清單失敗時照既有 Prowlarr 的做法說讀不到，並給「重新讀取」。
3. `_indexer_settled`：Prowlarr 上已經有至少一個站（不論是不是 Berth 加的）就算站那一半完成；完成頁的「跳過」文案照實際
   站數說。
4. 前進條件差介面登入時，在前進鍵的位置說「還差：設定 Prowlarr 介面登入」並能捲到那一區。

## 驗收

- [x] 整合測試：套件內 key 換掉後重新測試 → 讀到新 key、連上（雙向：掛載沒有 key 時仍是 `api_key_missing`）
- [x] 整合測試：套件內 Prowlarr 已有 1 站、介面登入已設 → `current_step` 前進到 5
- [x] vitest：讀清單失敗時有「重新讀取」；差介面登入時前進鍵位置有說明
- [x] vitest：索引站跳過但 Prowlarr 有站時，完成頁不說「搜尋不到任何東西」
- [x] playwright：重新產生 key 後在畫面上恢復；保留 Prowlarr 設定重裝後走到頁 5。附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

### 實跑（2026-10-01，playwright 對 qa-bundled）

受測 Berth 是從工作樹 build 的 `berth:t27-verify`，以 compose override 換掉 `C:/Users/Roxy/berth-qa/bundled` 的 berth
image（`qa-*`，子網 172.22，port 213xx），開跑前清掉 config 與 data。頁 1–5 全以 UI 實跑（1280 × 900，zh-TW）：

- 全新安裝、頁 4 選套件內：前進鍵的位置是「還差　加入至少一個站　設定 Prowlarr 介面登入」；測試全部後加入 dmhy，剩
  「還差　設定 Prowlarr 介面登入」，固定在桌機底部；按它焦點落在登入區（`data-testid=prowlarr-login`，畫面捲到 top 257）。
- **重新產生 key**：改 `config/prowlarr/config.xml` 的 `ApiKey`、重啟 `qa-berth-prowlarr` 後重新整理頁 4：連線卡仍是
  「連上了」，站清單那一段是「讀不到這一台 Prowlarr 的站清單…Prowlarr 不接受 Berth 的帳密或 API key。多半是在 Prowlarr
  重新產生了 API key。按「重新讀取」：Berth 會重讀掛載的 key 再連一次。」＋「重新讀取」；按下後「已加入 1 站 · dmhy」回來。
- 設好介面登入（沿用 Jellyfin 帳密）→「前往下一個泊位」。
- **保留 Prowlarr 設定重裝**：刪 `qa-berth`、清 `config/berth`、再 up，頁 1 以擁有者登入、頁 2 套用、頁 3 建立並檢查，
  頁 4 選套件內：第一輪（只修了站數）停在「還差　設定 Prowlarr 介面登入」，而登入區寫「Prowlarr 介面的帳號：qaowner」只給
  「更換登入」——那一台自己的登入 Berth 沒記（見下方偏差）。修好重 build 再走一次：選下去就是「前往下一個泊位」，登入那一條
  「已經是這樣 · qaowner」，按下去 `current_step=5`、標題 TMDB。
- 收尾：`qa-bundled` down、`berth:t27-verify` 刪掉；截圖（t27-01～09）在該 session 的 scratchpad，沒有進 repo。

### 偏差

- **連線測試順便讀套件內那一台自己的介面登入**（`indexer.note_instance_login`，票面沒寫）：重裝保留 Prowlarr 設定時登入也還在，
  原本只有按「加入」才記，而站都在了沒有東西可加，實跑卡在頁 4。讀不到 `config/host` 不讓連線變紅。
- **「還差」多列「加入至少一個站」**（票面只要求介面登入），既有 Prowlarr 0 站時也列；**只在桌機固定**，窄版跟著頁面走——
  窄版底部是「加入 N 個站」（`STICKY_ACTION`），兩條 sticky 會疊在同一個位置。
- **清單有站而上一次測試記 0 站時前端自動重新測試一次**（code-review 抓到）：使用者到 Prowlarr 自己的介面加站再回來，後端
  的站數還是舊的，前進鍵不出現、「還差」也空著。

### 驗證

- `uv run pre-commit run --all-files`：全部 Passed。
- pytest（`-m "not e2e"`，code-review 修正之後）：3461 passed, 22 deselected。
- vitest：77 檔 1188 passed。
- 前端 e2e（`pnpm build && pnpm e2e`）：33 passed。

### code-review 沒有處理的發現

- **Standards**：`note_instance_login` 與 `_apply_password` 不帶登入那一支得出同一個 `skipped` 結論，各寫一次。
- **Standards**：站數仍以字串存在 `ServiceTest.detail`，`_sites_counted`、`_existing_indexer_step`、前端的自動重測各自 `int()`
  （票 20 留下的形狀）。
- **Standards**：`_test_connection` 為了分套件內／既有又讀一次 `SetupSettings`；`ServiceChoice` 的 `Fix` 在 kind × reason 上的
  if 串又長了一支。
- **Spec**：設定頁 → 索引站的 `IndexerActions` 沒有跟著改：套件內讀不到清單時照舊是「連不上套件內的 Prowlarr」＋既有表單
  （票面只談精靈）。
