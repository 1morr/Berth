# 23 — 精靈設定不再互相蓋掉：命令只改自己的欄位

**Status:** done

**Blocked by:** None — can start immediately（24–30 都會碰 `settings.setup`，這張先做）

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 5 條）；plan §9.3〈續行與跳過〉；`berth/services/settings.py`（`write_settings` 與
`update_settings`）；票 20、21 的 `## Comments`（頁 4、5 已改用 `update_settings`）

## 為什麼（2026-10-01 精靈實測，全新安裝 L-P2-1，實測證實）

- 套件內服務「啟動中」時，前端不分頁每 3 秒打 `POST /setup/services/{kind}/test`（`web/src/pages/SetupPage.tsx:377-384`）。
  後端 `_test_and_record`、`choose_service` 是「開頭讀整份 `setup` → 打網路（最多 5 秒）→ `write_settings` 整列寫回」
  （`berth/services/setup.py:285-314,344-357`）；`apply_qbittorrent`、qBittorrent 的 `set_interface_login` 同樣
  （`berth/services/qbittorrent.py:235-278,300-322`）。
- 實測：Jellyfin 在啟動中時，在頁 2 把既有 qBittorrent 測到通過並按確認；12 秒後 status 裡的 qBittorrent 被寫回上一次
  的失敗，重新整理後頁 2 顯示舊的失敗。使用者以為做完了。兩個分頁同時操作同理。

## 做什麼

1. 精靈裡所有改 `settings.setup`（以及 `services.*`）的命令，改成**在寫鎖內重讀、只合併自己負責的那一段**，網路請求
   放在讀之前或之後，不再拿著舊的整份設定跨過網路請求。沿用 `update_settings` 或同形的做法；不新增一層抽象。
2. 盤點 `setup.py`、`qbittorrent.py`、`jellyfin.py`、`routes.py` 裡還在用 `write_settings` 寫 `setup` 的地方，全部改掉；
   `write_settings` 若沒有其他呼叫者就刪。
3. 前端的啟動中輪詢只打**畫面上等著的那一個服務**，不是所有 `waiting` 的服務（減少重疊的機會，但正確性不靠它）。

## 驗收

- [x] 整合測試：模擬輪詢與頁 2 套用交錯（輪詢在網路請求中途時套用完成）→ 套用的結果留著（雙向：把合併改回整列覆寫會紅）
- [x] 整合測試：兩個不同服務的測試交錯寫入，兩邊的結果都在
- [x] `write_settings` 寫 `setup` 的呼叫點歸零（或只剩有理由的，註明）
- [x] playwright 重現 L-P2-1 的步驟（`docker pause` 套件內 Jellyfin 讓它進入啟動中，同時在頁 2 完成）→ 重新整理後頁 2
      仍是完成。附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-01 實作紀錄**

- 改成鎖內重讀的命令：`setup.py` 的 `complete_setup`、`claim_owner`、`choose_service`（含
  `_remember_connection` 的三個 `services.*`）、`_test_and_record`；`qbittorrent.py` 的 `apply_qbittorrent`、
  `set_interface_login`；`jellyfin.py` 的 `save_bundled_libraries`、`add_berth_paths`、`_run`（`services.jellyfin`）、
  `_record`、`remember_libraries`；`indexer.py` 的 `skip_indexers`、`apply_default_indexers` 與 `connect_indexer`
  的 `services.indexer`；`tmdb.py` 的 `verify_tmdb`（`services.tmdb`，spec 審查指出它也跨網路整組寫回）。
  `routes.py` 本來就沒有直接寫 `setup`，只剩 `reread_libraries` 多餘的 commit 拿掉。
- `write_settings` 寫 `setup` 的呼叫點在 `berth/` 歸零；`write_settings` 本身留著：deeplink、discover、downloads、
  health、health_issues 這些背景迴圈與命令各自獨佔一列，還在用它。
- 順手補的防線（都在 `tests/integration/test_setup_lost_updates.py`，拿掉就紅，已逐條驗過）：測到一半使用者換了
  位址，舊的那一台的結果不記（`_test_and_record`、qBittorrent 的 `_still_chosen`）；兩人同時送頁 1，鎖內重查擁有者，
  後到的是 `owner_exists`；不帶登入的重按不把開頭讀到的介面登入寫回（`_keep_login` 只在這次改了才搬）。
- 前端：啟動中的輪詢只打 `berthOf(step)` 那一個服務（`SetupPage.test.tsx`「只重測畫面上等著的那一個服務」，
  改回舊寫法會紅）。
- playwright 重現 L-P2-1（`berth:qa-t23` 由工作樹 build，`berth-qa/bundled` 全新安裝，腳本在 session 的
  scratchpad `lp21.mjs`）：分頁 A 建好擁有者、`docker pause qa-berth-jellyfin`、重測 → `jellyfin:waiting/unreachable`、
  釘在頁 1 輪詢；分頁 B 選套件內 qBittorrent、自設介面登入、套用 → `step 3, qbittorrent:ok/connected`。分頁 A 有
  一次輪詢在頁 2 完成前 2 秒出發、完成後 28 秒才寫回；45 秒後重新整理分頁 B：`step 3, qbittorrent:ok/connected`，
  畫面停在頁 3、BTH 2 已完成。PASS。qa-* 已 down。
- **實測推翻票面的一個假設**：對暫停中的 Jellyfin，一次測試要 30 秒上下，不是「最多 5 秒」（adapter 的逾時是
  5 秒，多出來的沒有查）。正確性不靠它，但這表示輪詢一次佔著的時間比票面估的長得多；記在 progress.md 偏差。

- 驗證（最後一次改程式碼之後）：`pre-commit run --all-files` 全過；pytest 3425 passed；vitest 1131 passed；
  前端 e2e 33 passed。

**code-review 未處理的發現**

- `claim_owner` 不再與 `open_session` 同一個 commit：擁有者先落地、session 後發。`open_session` 失敗（只可能是
  資料庫錯）時擁有者已成立，使用者從登入頁用同一組帳密進來；註解寫在呼叫處。
- `apply_qbittorrent` 與 `add_berth_paths` 各拆成兩次 commit（`setup` 與 `services.qbittorrent`、`berth_paths` 與
  媒體庫快照），第二次失敗只可能是資料庫錯；沒有合併成一個交易，因為 `update_settings` 一次只鎖一組。
- `choose_service` 的 `moved` 仍由開頭讀到的選擇算（它決定的副作用——作廢 Route 檢查、`_same_jellyfin`——在那之前
  就做了），`kept` 在鎖內用最新的選擇算。兩個分頁在同一秒換同一個服務時，後到的會照它自己開頭看到的清掉那一頁。
- Standards 建議把「`setup` 一律走 `update_settings`」寫成有閘門的靜態規則：呼叫端的變數型別靜態看不出來，
  守著的是行為（七條交錯測試）；docstring 裡原本加的那一句規則已拿掉，不留沒有閘門的規則。
