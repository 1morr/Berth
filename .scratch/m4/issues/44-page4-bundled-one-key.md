# 44 — 頁 4 套件內一鍵加入可用的推薦站

**Status:** done

**Blocked by:** 37（頁 4 改名與拿掉 Torznab）、40（介面登入自動套用之後，這一頁才剩一顆鍵）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S1 頁 4、§B1、簡化方案 E-5、「文件與實作不符」的 README:29、改進清單 P2-2）；brief §16.3 的 Prowlarr 列、§20.7、§20.13；plan §9.3；M4 票 09、20、27

## 為什麼（2026-10-06 審計）

- 套件內的頁 4 現在要四個動作：測試 → 勾選 → 加入 → 設定介面登入。套件內的使用者沒有理由不要已經通過測試的推薦站。
- 實測：Internet Archive「測試通過、加入時卻失敗」（連不上）。一鍵流程要把這種情況說清楚。

## 做什麼

1. 套件內頁 4 的主鍵改成「測試推薦站、把通過的加進去」：一次完成測試與加入，結果逐站列出。
2. 逐站清單與「其他公開站」收進進階，仍然可以手動勾選與加入。
3. 測試通過但加入失敗的站，在結果裡單獨說明，不算進已加入。
4. 已經有站（重跑、重裝）時，主鍵不重複加。
5. README 的 BTH 4 敘述與 brief §16.3 Prowlarr 列同一個 commit 改（報告 README:29 那列）。

## 驗收

- [x] 整合測試：一次呼叫完成測試與加入；只加通過的；測過卻加入失敗的站在回應裡有自己的狀態（雙向）
- [x] vitest：主鍵一顆完成；進階清單仍可用
- [x] playwright 實跑 S1 頁 4，附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e、真服務 e2e 綠燈

## Comments

**做了什麼**

- 後端：`indexer.add_recommended_indexers`（`POST /setup/indexers/recommended`，只給套件內，既有與還沒選回 422）。測推薦清單上還沒加入的站（`_verify`，與 `verify_sites` 共用），通過的逐站新增（`_ensure_indexer`），加站的收尾與「加入」共用 `_record_added`。結論逐站記成纜繩，`SiteCheck.stage`（`SiteStage.TEST` / `ADD`，存在纜繩的 `params["stage"]`；之前記下的沒有它，讀成 `add`）分得出「測過而加不進去」與「測試就沒過」，重新讀取也一樣。新增前再讀一次清單，另一個分頁剛加的站不重加。替身 `FakeProwlarrClient` 多 `add_rejects` 與 `add_attempts`。
- 前端：`RecommendedSites`（主鍵、逐站結果：加進去的併成一行站名，沒加進去的分「測過、加不進去」「沒通過」兩段各一列）；`AdvancedSites` 是預設收起的 `<details>`「進階」，裡面是原本的 `AddSites`（`advanced`：Ghost 鍵、不帶錨點與「之後再說」）。兩邊共用同一份測試結論（`siteChecks.ts`）。主鍵、「進階」的「加入」、介面登入三者互相讓：一個在飛時另外兩個停用。
- 演練伺服器的 `bundled` 多 `FLAKY_SITES`（ACG.RIP 測得過、加不進去），前端 e2e `wizard` 改走主鍵再從「進階」加 Knaben。

**實跑 S1 頁 4**（工作樹 build，tests/e2e 那一套隔離的 `berth-e2e-*`，port 28383；用完 `down --volumes`）：頁 1 建管理員（勾「也用這組」）→ 頁 2 套件內 → 頁 3 自動跑完 → 頁 4 選套件內，介面登入自動沿用；按一次主鍵 4.4 秒回來：真的 Prowlarr 加了 dmhy、Anime Tosho、YTS、The Pirate Bay，5 站沒通過測試（Nyaa.si、ACG.RIP、Mikan 被 e2e 的 `sites` 容器冒充、連不上；1337x、EZTV 被 Cloudflare 擋），BTH 4 已完成、「前往下一個泊位」亮起。這一輪沒有真的站碰上「測過、加不進去」，那一段由演練伺服器（`FLAKY_SITES`）與整合測試守。截圖 `.playwright-mcp/t44/t44-before.png`、`t44-outcome.png`（gitignore）；演練伺服器的 `4-indexers-one-key`、`4-indexers-outcome` 在 `web/test-results/wizard-*/`（1280 與 390）。

**code-review**

- 已修（Standards）：`_untested_step` 改名 `_test_failed_step`；Berth 加不了的定義（`SITE_NOT_OFFERED`）標成測試那一支（原本標 `add`，會被說成「測過、加不進去」）；`add_recommended_indexers` 補沒有反向命令的理由；三處合併結論的寫法收成 `withChecks`；`advanced` 少兩個多餘的分岔（呼叫端不給 `onSkip`、給 `sticky={false}`）；「已加入」那一行不塗漆（The Usual Stays Unpainted Rule）；DESIGN.md 補主鍵與「進階」。
- 已修（Spec）：「加入 N 站」只數新增那一支通過的（已經在而重驗的 `skipped` 不算）；主鍵跑著時「設定介面登入」停用、自動沿用的登入也等它（設完 Prowlarr 重啟，正在加的站撞上它）——vitest 守，拿掉停用就紅。
- 未處理：兩個分頁幾乎同時按主鍵時，兩邊都讀完清單、都還沒加的那一瞬間仍可能撞同名（`Should be unique`），被記成「測過、加不進去」，後寫的那一份纜繩蓋掉先寫的；主鍵在有站時就不出現，要剛好同時按才碰得到，沒有 repro 不修。Prowlarr 沒有某個推薦站的定義時，主鍵不測也不列它（與候選清單一致：那一站本來就不在畫面上）。
