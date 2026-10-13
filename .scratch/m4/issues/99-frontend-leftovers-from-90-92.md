# 99 — 前端收尾：三處錯誤訊息一律怪外部服務；審核頁的區塊標題

**Status:** done

**Blocked by:** None — can start immediately

**讀:** 票 90 的 Comments〈code-review 未處理〉(1)；票 92 的 Comments（`ReviewPage.tsx` 那一條）；`web/src/components/requestProblem.ts`、`web/src/components/SectionHeading.tsx`；`DESIGN.md`

## 為什麼

票 90、92 收尾時各留下一件，使用者（2026-10-13）同意一起做。

## 做什麼

1. **三處錯誤訊息**：
   - 設定精靈的 `indexer.remove.failed` 一律說「Prowlarr 可能正在重啟」。
   - `routes.rereadFailed` 一律說「讀不到 Jellyfin 現在的媒體庫」。

   這兩句不管錯誤是什麼都怪外部服務。另外，媒體庫的 `inventory.narrow.failed` 不說原因。

   先查後端在 Prowlarr、Jellyfin 問不到時回什麼（狀態碼與 `detail`），再分開說：外部服務的問題照後端給的理由說，Berth 自己的請求沒成時照 `requestProblem` 說。
2. **審核頁的區塊標題**（`ReviewPage.tsx` 那一份手寫版）：改用 `SectionHeading`，讓票 92 的閘門也守得到它。
   - 票 92 提過：改了之後 `h2` 的可存取名稱會變短（計數移出 `h2`）。這是 `SectionHeading` 全站一致的寫法，照它走。
   - 標題列右側的按鈕走 `extra`。

## 驗收

- [x] 三處在 500、401、離線，以及外部服務問不到時，各說出對的原因；vitest 守，做變異驗證
- [x] 審核頁的區塊標題是 `SectionHeading`；票 92 的閘門改成也認得它（造一份手寫的會紅）
- [x] Playwright 實跑附截圖或文字結果；**不准碰使用者的 `berth-local`**
- [x] i18n zh-Hant 與 en 成對；全部檢查、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新

## Comments

- 2026-10-13 查後端：`DELETE /setup/indexers/{id}` 在 Prowlarr 問不到時是沒接住的 `ServiceError` → 不帶原因的 500，前端分不出是誰。改成 services 的 `IndexerNotRemovedError` → 502 帶原文（同 `CategoriesNotRemovedError`），整合測試守。`POST /setup/routes/libraries`、`GET /inventory/{id}/filters` 本來就回 503 `{reason: 'jellyfin_unreachable', detail}`，不動。
- 2026-10-13 驗收：後端 pytest 綠；vitest 95 檔綠；`pnpm -C web e2e` 35 passed；pre-commit 全過。
- 2026-10-13 變異驗證：(1) 三處改成一律怪外部服務 → 500 / 401 / 離線共 9 條加「前置代理的 502」1 條紅，外部服務那 3 條綠。(2) 三處改成一律不看外部服務的理由 → 外部服務那 3 條紅、其餘綠。(3) `prowlarrRemoveFailure` 拿掉「要有字串原文」→ 前置代理 502 那條紅。(4) `library_not_visible` 分支拿掉 → 那條紅。(5) 閘門：放回 HEAD 版的 `ReviewPage.tsx` → 「no component hand-writes…」紅；不該紅的那組（`bg-deck` 抬頭列裡的 `.label`、`labelled-row`、`<p className="label">`、原有的幾種）寫在測試裡。都已還原。
- 2026-10-13 Playwright 實跑（`fake_setup_server.py`：bundled 8721、healthy 8722、library 8723、review 8724；`skipper` 登入；`page.route` 造 500 / 401 / 斷線 / 外部服務的回應；沒碰 `berth-local`）：
  - 設定 → Prowlarr 移除：500「移除沒成功。 Berth 的後端出錯了。再試一次；還是不行的話看 berth 容器的 log。」、401「…登入已失效：重新登入 Berth，再試一次。」、斷線「…Berth 的後端沒有回應…」、502 帶原文「Prowlarr …移除…」加技術細節裡的 `GET http://prowlarr:9696/api/v1/indexer: connection refused`。
  - 媒體庫「類型」：500 / 401 / 斷線各說「讀不到這個媒體庫的篩選選項。」加對的後半句；503 `jellyfin_unreachable`「問不到 Jellyfin，讀不到這個媒體庫的篩選選項。」加原文與「重試」。
  - 精靈頁 3（走完頁 1–3 之後帶 `?step=3` 重進）：500 / 401 / 斷線「沒有重新讀取，下面是上一次讀到的那一份。」加對的後半句；503「問不到 Jellyfin，讀不到它現在的媒體庫；下面是上一次讀到的那一份。」加技術細節。
  - 審核頁 1280 與 390：`h2` 是「要你決定」「已入庫，等你看一眼」，region 由它們命名，水平捲動 0（截圖看過版面）。
  - 截圖之後依 code-review 改了 Prowlarr 那一句與兩個 key 名（見下），vitest 守新文案。
- 2026-10-13 code-review 已處理：Spec 軸——Prowlarr 拒絕（例如 key 被換掉）也走 502，主句原本仍說「沒答上來、可能正在重啟」→ 改成「沒答上來，或拒絕了 Berth，原文在技術細節裡」；篩選選項的 `library_not_visible`（404）原本落到「Berth 的後端出錯了」→ 說與 `UnknownLibrary` 同一句，測試守。Standards 軸——`routes.rereadFailed` 的語意被翻轉成只指 Jellyfin → 改回通用前半句，Jellyfin 那句叫 `rereadJellyfinDown`；`indexer.remove.prowlarr` 改名 `prowlarrFailed`；`removeError`、`reread.error` 從 `unknown` 收成 `Error | null`；閘門的 className 正規式提成常數、不再回頭索引。
- 2026-10-13 code-review 未處理：(1) 三個新元件（`RemoveFailed`、`RereadFailed`、`NarrowFailed`）與既有的 `Trouble`、`WatchToggle`、`RouteDelete` 都是「外部服務的理由 → 自己那一句；其餘 `RequestFailed`」：各自的理由集合、文案與原文放法不同，各自短，不抽（同票 90 未處理 (2) 的判斷）。(2) `NarrowFailed` 的原文是裸的 `p.value`，另兩處收進 `TechnicalDetails`：沿用同頁 `Trouble` 的寫法，DESIGN.md「原文收進技術細節」只管精靈、設定頁與健康頁。(3) 閘門往 `</h2>` 找 `.label`：一個沒閉合的 `<h2` 會吞到下一個 `</h2>`；真的 JSX 一定閉合，只影響測試裡手寫的字串。
