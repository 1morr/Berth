# 67 — 精靈再省幾按：連線＋登入合一、既有 Prowlarr 一鍵加站、TMDB 下一步先測

**Status:** done

**Blocked by:** 63（頁 1 加了 `/data` 探測之後再合併表單）、64（頁 3 改完再算按鍵）

**讀:** `docs/research/usability-audit-2026-10-07.md` §4（全節，C1、C3、C4）、§8 P2-10；`notes/r2-docs-and-research.md` §2.2（Sonarr 的 Save 會再測）、§2.3（Seerr 位址與管理員帳密同一頁）；plan §9.3；M4 票 38、39、44、45

## 為什麼

審計 §4.1 量到的必按數：套件內 12、既有 17。多出來的主要是：

- 既有 Jellyfin 先「測試連線」，通過後才長出登入表單，再按「登入」（Seerr 是同一頁、一顆 Sign In）。
- 既有 Prowlarr 加推薦站要「測試全部 → 勾 → 加入」，套件內一顆鍵（票 44）。
- TMDB 要「測試 TMDB」再「前往下一個泊位」（Sonarr 的 Save 自己會再測）。

## 做什麼

1. 既有 Jellyfin：位址＋管理員帳密同一個表單，一顆「連線並登入」。
   - 錯誤照票 45 標在欄位上：位址類標位址，帳密類標帳密，版本、非管理員在表單層級。
   - 還沒初始化的那一台照現在的分支（建管理員）。
2. 既有 Prowlarr 也有「測試推薦站，加入通過的」主鍵，條件與套件內相同（Prowlarr 已有站時放進「進階」）。
3. TMDB 頁按「前往下一個泊位」時，若 key 還沒驗過就先測，測過才走；保留單獨的「測試 TMDB」。
4. 重算 §4.1 的表：S1、S2 兩條路徑的輸入與必按數，寫進票的 Comments。

## 驗收

- [x] 整合測試：Jellyfin 一次呼叫完成連線與登入，錯誤分類到欄位；既有 Prowlarr 一鍵加站
- [x] vitest：三處的新流程（zh-Hant 與 en）
- [x] playwright 實跑 S2（全既有）：必按數比審計時少，附截圖與計數
- [x] 全部檢查、test、前端 e2e 綠燈；plan §9.3、README guide 同步；progress.md 記一行

## Comments

- 2026-10-14 重算審計 §4.1（輸入 / 必按；S2 的頁 3 也吃到票 64 的預設勾選）：

  | 頁 | S1 套件內：審計 → 現在 | S2 既有：審計 → 現在 |
  | --- | --- | --- |
  | 1 Jellyfin | 3 / 3 → 3 / 3 | 3 / 4 → 3 / 3（選、連線並登入、下一步） |
  | 2 qBittorrent | 0 / 2 → 0 / 2 | 3 / 3 → 3 / 3 |
  | 3 媒體庫路徑 | 0 / 1 → 0 / 1 | 0 / 4 → 0 / 2（建立並檢查、下一步；電影與劇集預設勾好，票 64） |
  | 4 Prowlarr | 0 / 3 → 0 / 3 | 2 / 3 → 2 / 3（已有站）；0 站加推薦站 2 / 6 → 2 / 4（選、測試連線、一鍵、下一步） |
  | 5 TMDB | 1 / 2 → 1 / 1 | 1 / 2 → 1 / 1（前往下一個泊位自己先測） |
  | 6 完成 | 0 / 1 → 0 / 1 | 0 / 1 → 0 / 1 |
  | **合計** | **4 / 12 → 4 / 11** | **9 / 17 → 9 / 13**（0 站的 Prowlarr：9 / 20 → 9 / 14） |

- 實跑 S2（Playwright，`fake_setup_server.py --scenario mixed-no-sites`，1280 寬，按鍵由腳本逐一記）：9 個輸入、14 按——頁 1 選既有、連線並登入、下一步；頁 2 選既有、測試連線、下一步；頁 3 建立並檢查、下一步；頁 4 選既有、測試連線、測試推薦站加入通過的、下一步；頁 5 前往下一個泊位（先測）；頁 6 完成設定。截圖在 `docs/research/fewer-presses-2026-10-14/`（`s2-01` 頁 1 一張表單、`s2-04` 既有 Prowlarr 的主鍵與列出站名的那一句、`s2-06` 頁 5、`s2-07` 完成頁）。前端 e2e 的 `existing.spec.ts` 也改走一顆「連線並登入」（先錯密碼：標在密碼欄、位址欄不標）與頁 5 直接前進。
- 「Prowlarr 已有站時放進『進階』」照票面「條件與套件內相同」讀：已有站時不給主鍵（`RecommendedSites` 的 `offered`），只剩「進階」裡逐站測、勾、加；沒有把主鍵本身搬進「進階」（審計 C3 字面可以那樣讀，code-review Spec 軸提出）。
- code-review 已處理：DESIGN.md 精靈導覽補頁 5 的例外；`BerthNav` 的 `nextForm` 註解改成「與 `onNext` 都給時送出表單優先」；文案閘門 `ONE_PRESS_WHEN_EMPTY` 補換標點的正例；`ExistingForm` 的 `signIn` 型別改用 `ChoiceControls['signIn']`；`indexer.empty.body` 還是「勾起來加進去」的三步說法；先按「測試 TMDB」綠了再按前進會重測同一把（記下送測的那一把，綠著就直接走，vitest 一條、拿掉修法會紅）。
- code-review 沒處理的：(1) `ServiceChoice.blankCredential` 與 `OwnerStep` 登入那一支的空欄判斷是同一條規則（M4 票 31），後者是逐欄、前者是一句，沒收成一份。(2) `ExistingForm` 裡六處 `signIn ? … : …`：還是同一張表單，拆成兩個元件的話位址欄與錯誤分層要重複一份。(3) `sign_in_existing_owner` 回 `ClaimedOwner | SetupStatus`、API 以 `isinstance` 分流；沒標 `@command`（`setup` 在 `test_command_marks.py` 的票 M3 前豁免表，與 `claim_owner` 一樣）。
