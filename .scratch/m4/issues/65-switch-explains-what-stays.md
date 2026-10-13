# 65 — 換台時說清楚留下了什麼：做種中的 torrent、白名單、移除的時機

**Status:** done

**Blocked by:** 59（換台後自動重查那一段先做好，這張只管換台框與舊那台）

**讀:** `docs/research/usability-audit-2026-10-07.md` §3 S4（qBittorrent 套件內 → 既有、做種中的那部電影）、§8 P1-4、P2-9；截圖 s4-06、s4-07、s4-10、s4-11；brief §16.4〈換一台 qBittorrent / Prowlarr 時〉；M4 票 47

## 為什麼（審計實跑）

- 換到另一台 qBittorrent 時，做種中的 torrent 留在舊那台，Berth 不再追蹤，也沒有任何提示；換台框只寫「berth-movies　1 個 torrent」，Job 仍是「已入庫」。
- 換台框列了 Berth 設的介面登入，但沒列 Berth 預置的免密白名單（套件內那一台的設定檔裡）。
- 「移除空的 berth- 分類」在確認換台**之前**就生效；之後取消換台會怎樣沒驗證（送單會重建分類，但使用者看不出來）。

## 做什麼

1. 換台框對有 torrent 的分類說清楚：
   - 「這 N 個 torrent 會留在舊那一台繼續做種，Berth 換台之後不再追蹤它們；已經入庫的檔案不受影響。」
   - 舊那台關掉，做種就停。
2. 已入庫的 Job 詳情，在追蹤的 qBittorrent 已經換掉時說一句「做種的 torrent 在原本那一台」。
3. 套件內那一台的免密白名單也列進「留在那裡的東西」，說明它在哪裡、怎麼關（照票 53 的措辭）。
4. 「移除空分類」改成跟著「確認換台」一起做：換台框裡是勾選，不是立即執行的按鈕。取消換台就什麼都不動。
   - 換台框的寫入照票 47 的白名單閘門。

## 驗收

- [x] 整合測試：取消換台不移除任何分類；確認換台才移除勾選的空分類（雙向）（`test_setup_leftovers.py::TestRemoveEmptyCategoriesOnSwitch`：勾了換台、沒勾、只開框、新那台測不過、同一台、確認前進來的 torrent、原本那台沒答上來；API 一輪含 502；白名單閘門的既有那一輪加上換台並勾選，`remove_categories` 第一次經真實路徑被記到）
- [x] vitest：換台框的新文案與勾選（zh-Hant 與 en）（`ServiceChoice.test.tsx` 換台那一組、`JobDetailPage.test.tsx`、`auditCopy.test.ts` 的白名單措辭）
- [x] 實跑：有做種中的 torrent 時換台 → 取消一次 → 確認一次，舊那台的分類與 torrent 狀態，附截圖（演練情境 `import`：`.playwright-mcp/t65-1-switch-box.png`、`t65-2-after-cancel.png`、`t65-3-switched.png`、`t65-4-job-detail.png`，目錄不進版控；限制見 Comments）
- [x] 全部檢查、test、前端 e2e 綠燈；brief §16.4 同步；progress.md 記一行

## Comments

**實跑**（演練情境 `import`、設定 → qBittorrent）：送單入庫後 torrent 在 `berth-anime` 做種（`stalledUP`）。換台框列出 `berth-anime` 1 個 torrent、`berth-movies` / `berth-tv` 空的、免密白名單與關法、「這 1 個 torrent 會留在原本那一台…」、預設不勾的「換台時一併移除 2 個空的 berth- 分類」。勾了再取消：沒有任何非 GET 的 `/api` 請求，三個分類都在，重開時勾選已收回。勾了並以 `http://192.168.1.10:8080` 確認：請求帶 `remove_empty_categories: true`、200；之後那一台只剩 `berth-anime`（1 個 torrent，仍 `stalledUP`）；Job 的 `previous_client` 是 `http://qbittorrent:8080`，詳情頁說「做種的 torrent 在原本那一台」。**限制**：演練伺服器上新舊兩台是同一個替身物件，畫面分不出「舊那台」與新那台；「移除的是舊那台、新那台不動」由整合測試以兩個替身守（`qbittorrent_elsewhere`）。

code-review（2026-10-14）已處理：CHANGELOG 補一條（含刪掉的 `DELETE …/leftovers/categories`）；brief「測不過什麼都不動」只對換成既有成立（套件內照舊先存再測）；做種文案涵蓋下載中的 torrent（「做種的照樣做種、下載中的照樣下載」）；移除了哪幾個寫進 log；`JobOut.previous_client` 註解寫明每個狀態都填、畫面只對已入庫說。

未處理（記著）：

- **設定頁「改位址」從一台既有換到另一台既有**：後端照樣算換台（Route 檢查作廢），但不走換台框，看不到做種說明、也勾不了移除。票 47 起就是這樣。
- **換台後還在下載中的 Job**：torrent 留在原本那一台，新那一台上找不到，poller 會開 `client_removed`；換台框只說「下載中的照樣下載」，沒說那幾筆之後會變成待處理。
- **「改位址」到同一台 qBittorrent 的另一個位址**（IP 換了）：Berth 也當成換台，Job 詳情會說「在原本那一台」——與 Route 檢查作廢是同一個判斷。
- 判斷題沒動：`ServiceChoice` 收起換台區的三處重設（各帶不同的額外狀態）；`categories_not_removed` 在 `ExistingForm` 排除、在換台區接住兩處判斷；`seeding_*` 與 `seedingUnknown` 後半句相同。
