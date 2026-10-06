# 38 — 頁 2 測試通過即完成；拿掉不寫入的確認鍵

**Status:** done

**Blocked by:** 32（頁 2 的寫入剩介面登入之後才好收成一顆鍵）、34（要更新真服務 e2e）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S2 頁 2、S5 第 3 點、§E 共同慣例 1、「Berth 精靈哪裡不統一」第 1、3 條、簡化方案 E-2、改進清單 P1-2）；brief §19「精靈審計後的八項」D5、§16.3；plan §9.3

## 為什麼（2026-10-06 審計，實測）

- 既有 qBittorrent 測試通過之後，還要再按「確認，不改任何設定」才能前進，按下去什麼都不做。截圖 s3-11。
- 套件內重跑時三鍵都「已經是這樣」，仍必須按「套用這 0 項」才算完成。截圖 s5-06。
- Sonarr、Seerr、Home Assistant 都是「測試通過＋儲存」一步。**D5 拍板**拿掉這兩顆鍵。

## 做什麼

1. 頁 2 的前進條件（後端的 `_qbittorrent_secured` 一類）改成：連線測試通過；套件內另外要介面登入已設好。
2. 既有：測試通過即完成，畫面上沒有確認鍵。
3. 套件內：介面登入還沒設時只有一顆「設定介面登入」；已設好（重跑、重裝）時測試通過即完成，不出現「套用 N 項」。
4. 設定頁的 qBittorrent 頁同一個規則，有就改。
5. brief §16.3 與 plan §9.3 的頁 2 敘述同一個 commit 改。

## 驗收

- [x] 整合測試（雙向）：既有 qBittorrent 只做連線測試就能前進；套件內介面登入未設時不能前進、設好之後可以
- [x] vitest：既有不出現確認鍵；套件內已設登入時不出現「套用這 0 項」
- [x] 真服務 e2e 與前端 e2e 照新流程更新並綠燈
- [x] playwright 實跑既有與套件內重跑兩種，附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test 綠燈

## Comments

**2026-10-07 實作紀錄**

- 後端：`setup._qbittorrent_secured` 對既有那一台只看連線測試；套件內仍要登入那一條 `ok` / `skipped`。套件內的
  連線測試順便讀那一台自己的 WebUI 帳號（`qbittorrent.qbittorrent_interface_user`，讀不到不讓測試變紅），
  `note_qbittorrent_login` 只補還沒有結論的那一條（不蓋掉剛才換登入失敗的紀錄——密碼先送，舊帳號未必還是舊密碼）。
  與 Prowlarr 的 `indexer.note_instance_login`（M4 票 27）同一個做法。
- 前端：`QbittorrentStep` 收後端頁序的 `done`；既有的那一台只剩「做完了」那一句；套件內的 `LoginSequence` 只在欄位開著、
  或還沒做完時給「設定介面登入」，拿掉「套用這 N 項」「確認，不改任何設定」「重新檢查並套用」「重新檢查」四個 key 與按鈕。
  設好之後、status 重讀之前，登入那一條已過也算做完（不閃主鍵）。回頭看 BTH 2 的「這裡能做」改成畫面上真的有的動作。
- 第 4 點：設定 → qBittorrent 沒有不寫入的確認鍵（連線區測試與儲存一步，介面登入那一區有自己的寫入鍵），沒改。
- `POST /api/setup/qbittorrent/apply` 形狀不變：既有那一台照舊可打（記一條 `skipped`），前端不再呼叫。

**實跑（工作樹 build 的 `berth:qa-t38`；repo 外 `C:/Users/Roxy/berth-qa-t38`，compose 改名 `t38` / `t38-*`、子網
`10.238.0.0/16`、port 38xxx，只起 jellyfin 與 qbittorrent；用完 `down -v`、刪目錄與 image；沒碰 berth-trial、berth-audit）**

截圖在 session scratchpad 的 `t38/`，不進版控。

| 情境 | 結果 |
| --- | --- |
| 套件內、全新（qBittorrent 5.2.3） | 只有「設定介面登入」，沒有前進鍵（`t38-01`）；沿用 Jellyfin 帳密設好之後只剩「更換登入」與「前往下一個泊位」（`t38-02`） |
| 換成既有（同一台、填 WebUI 帳密） | 按「測試連線」就是「已完成」、頁序到 3，沒有確認鍵（`t38-03`） |
| 換回套件內（Berth 忘了設過的登入） | 連線測試讀到 `skipper`，那一條 `skipped`、頁序 3，沒有「套用這 0 項」（`t38-04`） |
| 重裝：刪 Berth 的 `config/berth`、保留 qBittorrent config | 頁 1 以管理員登入，頁 2 選套件內即「已完成」、只剩「更換登入」與前進鍵（`t38-05`） |

**檢查**：`uv run pre-commit run --all-files` 全過；pytest（`-m "not e2e"`）3509 passed；vitest 83 檔 1303；
`pnpm -C web e2e` 35 passed（全跑時 `submit` 一次斷言逾時、`wizard` 一次 chromium 啟動逾時，皆單獨重跑通過）；真服務 e2e
`uv run --env-file .env python -m tests.e2e.stack` 23 passed（頁 2 新增：設登入前停在 2、換既有與換回套件內都只靠連線測試到 3）。
真服務 e2e 跑在審查修正（失敗紀錄不被蓋掉、分支補 `kind`）之前的工作樹上，那兩處不在它走的路徑上。

**code-review 未處理的發現**

- Spec / Standards：`apply` 對既有那一台的分支已沒有前端呼叫端，全域規則說消費點歸零就刪。留著：改成 422 是公開
  API 的破壞性變更，要先告知；它不影響前進條件（`_qbittorrent_secured` 不看既有那一台的纜繩）。
- Standards：`note_qbittorrent_login` 與 `indexer.note_instance_login`、`_apply_password` 的「不帶登入」那一段形狀相近；
  讀帳號的兩支（`qbittorrent_interface_user` 公開在 qbittorrent.py、Prowlarr 的 `_interface_user` 私有在 setup.py）放法不一。
  留著：兩個服務的「設過了」判準不同（qBittorrent 看帳號不是 `admin`，Prowlarr 看 `authenticationMethod`），抽共用要動票 27 的契約。
- Standards：`LoginSequence` 的 props 仍叫 `onApply` / `applying`，`SetupPage` 仍是 `applyPreferences`（票 32 起已沒有偏好）。
  改名牽動 SetupPage 多處，不在本票。
- Spec：讀得到帳號、後端卻沒記那一條（票 38 之前開始的精靈、或連線測試那一次讀偏好失敗）時，主鍵「設定介面登入」送的是
  「登入照舊」——按下去把那一條記成 `skipped`，不寫 qBittorrent。vitest 固定了這個行為；文案沒另分一句。
