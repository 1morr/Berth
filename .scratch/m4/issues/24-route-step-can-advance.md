# 24 — 頁 3 的前進條件跟畫面一致：重裝不卡、刪掉的 Route 不長回來、換台不殘留

**Status:** done

**Blocked by:** 23

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 1、6、7、8 條）；plan §9.3 第 3 點、§9.5；票 19 的 `## Comments`

## 為什麼（2026-10-01 精靈實測）

- **重裝後頁 3 永遠過不去（P1，實測證實）。** `_libraries_built` 只認 `setup.jellyfin.steps` 裡 `libraries` 那一條
  （`berth/services/setup.py:693-701`），只有建媒體庫的 `bootstrap_jellyfin` 會寫；前端只在清單有未建的列時才呼叫它
  （`web/src/pages/SetupPage.tsx:244`、`web/src/setup/RouteStep.tsx:138,169`）。保留 Jellyfin 設定、只清 Berth 重跑
  → 媒體庫全「已建立」→ Route 全綠但 `current_step` 停在 3，沒有前進鍵。截圖 R-07、R-08。
- **刪掉紅的 Route 後沒有前進鍵（既有，實測證實）。** 刪除後前端只重讀 Route 清單、不重讀 status（`SetupPage.tsx:508,526-528`），
  後端已到頁 4，畫面要重新整理才出現下一步；被刪的媒體庫還勾著。截圖 E6-14～16。
- **套件內：刪掉的紅燈 Route 又長回來（實測證實）。** 套件內的選擇是快照裡每一個 movies/tvshows 媒體庫
  （`berth/services/routes.py:818-836`），路徑不在 `/data` 的媒體庫刪了 Route 之後，下一次「建立並檢查」又建出來；
  在 Jellyfin 刪了媒體庫，Berth 的快照也不刷新（套件內不進頁重讀）。截圖 R-04～06。
- **換一台 qBittorrent 後頁 3 殘留上一台的結果（既有，實測證實）。** Route 標「尚未檢查」卻仍寫 0/6、2/6、泊位卡「失敗」，
  展開是上一台的整段錯誤（`routes.py:259-264` 只把 health 改 unknown，沒清 detail）。截圖 E8-04、E8-05。

## 做什麼

1. **套件內媒體庫那一步不靠「有沒有呼叫過 bootstrap」**：清單上全部已建立時，按「建立並檢查」也要讓 `libraries` 那一條
   有結論（skipped）；做法自選（前端照呼叫、後端判定改看快照），但前後端的條件要同一個來源。
2. **刪 Route 之後重讀 status**（其他會改 `current_step` 的動作一併檢查）；被刪 Route 的媒體庫取消勾選。
3. **套件內也重讀 Jellyfin 媒體庫**（進頁與「建立並檢查」前），自動建 Route 的範圍排除使用者刪過的媒體庫，或只對
   「Berth 這次建的媒體庫」建 Route——選一個，決定寫進 plan §9.5；Jellyfin 裡已刪的媒體庫不再出現。
4. **換台時清掉舊的檢查細節**：health 改 unknown 時一併清 `health_detail_json`，畫面不顯示上一台的通過數與錯誤。

## 驗收

- [x] 整合測試：套件內 Jellyfin 的媒體庫已全部存在（重裝情境）→ 建立並檢查後 `current_step` 前進到 4（雙向：清單有未建的
      照舊建）
- [x] 整合測試：套件內刪掉一條紅 Route → 再按建立並檢查不會重建它；Jellyfin 裡刪掉的媒體庫不再列入
- [x] 整合測試：換 qBittorrent 之後 Route 的檢查細節是空的
- [x] vitest：刪除 Route 後重讀 status、前進鍵出現；被刪的媒體庫取消勾選
- [x] playwright：重裝情境（保留 Jellyfin config、清 Berth config）走到頁 4；既有情境刪紅 Route 後不重新整理就能前進。
      附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-01 實作紀錄**

- 第 1 條選「後端判定改看快照」：`jellyfin.libraries_built`（清單每一列都在 Jellyfin 上），與剖面的「已建立」同一條
  （`_on_jellyfin`）；前端照 `PUT bundled` 回來的 `built` 決定呼不呼叫 bootstrap。`libraries` 那一步沒有補 skipped，
  只剩上一次嘗試的紀錄；`librariesFailed` 在清單全建好時不算（code-review 抓到的 bug：手動補建之後舊失敗還掛著）。
- 第 2 條：刪 Route 之後重讀 status（不必另外釘頁：進頁的重讀已經釘住，拿掉也綠，已驗）；既有模式清掉那個媒體庫的勾選。
  其他會改 `current_step` 的動作：存清單（`saveLibraries`）現在也重讀 status，因為多一列沒建的頁 3 就沒做完。
- 第 3 條選「只替清單上的媒體庫建 Route」（`jellyfin.is_listed`、`LibraryChoice.listed`），決定與代價寫在 plan §9.5；
  套件內進頁與按下之前都重讀 Jellyfin。
- 第 4 條：`forget_route_checks` 清 `health_detail_json`。
- 單元測試 `test_setup_steps.py` 原本守著舊規則（拿掉 `libraries` 那一步就停在頁 3），改成守 `libraries_built`。

**playwright 實跑（`berth:t24` 由工作樹 build，用完刪；腳本在 session scratchpad 的 `t24/`）**

- 重裝（`berth-qa/bundled`，全新 config/data、只把 berth 換成 `berth:t24`）：頁 1–2 走 API、頁 3 走 API 建好 →
  只清 `config/berth` 重起 berth → 頁 1–2 走 API → 頁 3 開畫面：「媒體庫清單 3 個已建立」，按「建立並檢查」送出的是
  `POST routes/libraries`（進頁）、`POST routes/libraries`、`PUT jellyfin/bundled`、`POST routes`，沒有 bootstrap；
  三條 6 / 6 已繫上，`current_step` 4，「前往下一個泊位」落在「索引站」。PASS。qa-bundled 已 down。
- 既有（ok-jellyfin + ok-qbittorrent，受測 Berth `t24-berth` 在 172.24 子網、`/data` 掛 berth-trial/data 並以 `--tmpfs`
  蓋住容器內的 `/data/media/tv`）：勾 Movies（`/data/media/movies`）與 TV Shows（`/data/media/tv`）→ Movies 綠、
  TV Shows 紅在 `probe_visible`（3 / 6），沒有前進鍵 → 刪 TV Shows → 不重新整理就出現「前往下一個泊位」、畫面仍是
  「媒體庫路徑」、TV Shows 取消勾選、主鈕「重新檢查 1 條 Route」，`current_step` 4，前往後是「索引站」。PASS。
  測後快照多了 ok-jellyfin 的一把「Berth」API key 與 berth-trial/data 的三個空 `torrent/incomplete` 目錄，都已還原，
  再快照與測前 11 檔完全相同；容器與網路已刪。

**驗證（最後一次改程式碼之後）**：`pre-commit run --all-files` 全過；vitest 1136 passed；前端 e2e 33 passed；
pytest 3429 passed、3 errors——三個都是 `test_setup_api.py`（`TestSource::test_applying_adds_only_what_was_ticked` 的
setup / teardown、`TestRoutes::test_completing_needs_a_tmdb_credential_first` 的 setup）撿到前面測試漏關的 aiosqlite 連線
（`ResourceWarning`、`Event loop is closed`），不是斷言失敗。**既有的不穩定**：單獨跑這個檔，工作樹 3 次 2 次出現，
基準 `ee84da0` 的 worktree 也是 3 次 2 次；沒有修（不在這張票的範圍，也還沒找到漏的是哪一條連線）。
**後續**：同一個 session 另一個 commit 修了（`berth/db/engine.py`：關機時 cancel 打在開連線、設 pragma 的途中，連線沒人關；
原因與修法在 progress.md 偏差與決定）。

**code-review 未處理的發現**

- 按下時的重讀讀不到（Jellyfin 不回答）就整段停，說的是通用的請求失敗、不是 `Reread` 那一句；那時後面的檢查也一定紅，沒改。
- `is_listed` 名稱相同就算清單上的（與「已建立」同一條比對）：重裝時保留的同名、路徑不在 `/data` 的媒體庫照樣建 Route，
  刪了又長回來，清單上那一列又因為已建立鎖住。沒有實測 repro，記在 plan §9.5 的代價。
- 後端那一半的「清單有未建的照舊建」只斷言停在頁 3；真的去建由 vitest「先重讀再存清單」與既有的 bootstrap 測試守。
- `_current_step` 不看 `completed`：精靈跑完之後快照一變也可能說頁 3，`routes_ready` 早就這樣，沒改。
- Standards 的判斷題沒動：`dock` 與 `reread.onSuccess` 各自吸收重讀結果；`libraries_built` 與 `routes._jellyfin_origin`
  兩種「是不是套件內」的判定（還沒選時都當不是）；`onRouteDeleted` 的 `route` 參數只有既有模式用。
