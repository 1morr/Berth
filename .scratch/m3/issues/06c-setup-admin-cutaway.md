# 06c — 精靈第 1 步：剖面說實話（帳密寫到哪裡、偵測之前不知道是不是套件內）

**Status:** done

**Blocked by:** None — can start immediately（動 `web/src/setup/AdminStep.tsx`、i18n、`services/setup.create_admin` 的規則與它們的測試）

**讀:** plan §9.3 第 1、2 步；brief §16.3（來源逐服務判斷）；`DESIGN.md` 的剖面（`Cutaway` / `CutawayRow`）；`web/src/setup/AdminStep.tsx`

## 做什麼

使用者 2026-09-24 重跑精靈時看到第 1 步左邊的「將會寫入」剖面，指出兩個問題。

**1. 標籤與值對不上。** 四列的值都是**帳號**（`account`），但 qBittorrent 那一列的標籤是「qBittorrent WebUI **密碼**（第 4 步）」，畫面讀起來像「密碼是 admin」。Prowlarr 那一列是「介面登入」，也只列出帳號。後端寫的其實是整組帳密：qBittorrent 的 `web_ui_username` 與 `web_ui_password`（`services/qbittorrent.py`），Prowlarr 的 forms 驗證加帳號密碼（`services/indexer.py`）。三個服務的標籤統一改成「帳密」，值寫成「帳號・密碼同上」，不顯示密碼本身。

**2. 偵測之前就把話說死了。** 偵測是第 2 步，第 1 步時 Berth 還不知道哪個服務是套件內的，畫面卻寫得像已經確定：

- 剖面的 Jellyfin / qBittorrent / Prowlarr 三列無條件寫「admin」。後端只寫**套件內**的（`indexer.py`、`qbittorrent.py` 的 `origin is BUNDLED` 條件）；既有 Jellyfin 是要求使用者用它自己的管理員登入（plan §9.3 第 1 步），不會建立管理員。
- lede「之後的步驟會用它建立 Jellyfin 管理員」同樣只在 Jellyfin 是套件內時成立。
- 勾選框的提示「只影響套件內的服務」是對的，但沒說要到第 2 步才知道，和左邊的剖面互相矛盾。

**不改步驟順序**：先建管理員是 Jellyfin 自己的啟動精靈、Home Assistant、Jellyseerr 共同的慣例，而且管理員不存在時精靈的 API 誰都呼叫得到，先把門關上。改的是剖面照 `status.services` 的狀態說話：

| 狀態 | Jellyfin 列 | qBittorrent / Prowlarr 列（勾選時） |
| --- | --- | --- |
| 還沒偵測（第一次走到第 1 步） | 「admin・密碼同上（第 2 步偵測到是套件內的才建立）」 | 「admin・密碼同上（第 2 步偵測到是套件內的才寫入）」 |
| 已偵測、套件內（回來按「改帳密」） | 「admin・密碼同上」 | 「admin・密碼同上」 |
| 已偵測、既有 | 「你自己的服務：用它的管理員登入，不建立」 | 「你自己的服務，不寫入」 |
| 沒勾選 | 照上面 | 「不套用」（現有的 `skipped`） |

**3. 走過泊位 1 之後「改帳密」會讓 Berth 與 Jellyfin 對不上（使用者 2026-09-25 問「之後還能改嗎」時查到）。** `setup.create_admin` 只覆寫 Berth 存的那一組（「重跑就是覆寫同一組帳密」），而 Jellyfin 的初始精靈跑完之後，`jellyfin.py` 的 `_admin_user` 一律 `SKIPPED`——新密碼不會寫到 Jellyfin。之後任何拿這組帳密登入 Jellyfin 的步驟（`_libraries` 的 `_authenticate`、第 7 步換 API key）會失敗，精靈走完後用 Jellyfin 帳號登入 Berth 時照 Berth 記的那組也進不去。qBittorrent 重跑第 4 步時會套新帳密（`qbittorrent.py` 比對後重寫），Prowlarr 也會，只有 Jellyfin 不會。

決定照 Seerr 的慣例：**媒體伺服器的管理員就是帳號的主人**。套件內 Jellyfin 的管理員建好之後，那組帳號屬於 Jellyfin：

- 第 1 步回頭看時，帳號與密碼欄不再能改 Jellyfin 的那一組，說明「密碼在 Jellyfin 裡改；Berth 的登入就是 Jellyfin 帳號」。
- 仍可改的只剩「套用到 qBittorrent 與 Prowlarr 介面」的那一組，而且說清楚要回到那兩個泊位重新套用才會生效（06d 的導覽）。
- 既有 Jellyfin 本來就不用這組帳密建管理員，同樣處理。

lede 改成條件句（「Jellyfin 是套件內的話，之後會用它建立 Jellyfin 管理員」）；勾選框的提示補上「第 2 步會判斷每個服務是套件內還是你自己的」。

「已偵測」讀 `status.services` 裡該服務的判定：`origin` 是 `bundled` → 套件內，`existing` → 既有；`pending`、`timeout` 或清單裡沒有那個服務都當「還沒偵測」（`domain/enums.ServiceOrigin`）。判定到文案的對應是純函式，放在 `AdminStep.tsx` 旁邊。

## 驗收

- [x] 剖面三個服務的標籤都是「帳密」，值是「帳號・密碼同上」，畫面上不出現密碼本身
- [x] 未偵測、套件內、既有、沒勾選四種狀態的剖面文案各有前端測試；對應函式有單元測試，涵蓋探測中與逾時當成未偵測
- [x] lede 與勾選框提示不再在偵測前斷定 Jellyfin 會被建立管理員
- [x] 紅燈先行：Jellyfin 管理員已建立之後改帳密，再跑一次第 3 步會登入失敗（整合測試，Fake Jellyfin，修正前紅）；修正後第 1 步不再接受改 Jellyfin 的那一組，並說出去哪裡改
- [x] 只改 qBittorrent / Prowlarr 那一組時，回到第 4、5 步重新套用後兩邊都生效（整合測試）
- [x] zh-Hant 與 en 並列
- [x] playwright 實跑：全新環境走到第 1 步（未偵測）一張；走完精靈回到第 1 步（已偵測）一張；1280 與 390。附結果
- [x] plan §9.3 第 1 步的敘述若與畫面不一致，同步改
- [x] lint、type、test 綠燈

## Comments

**2026-09-25 實作紀錄**

- 資料形狀：`SetupAdmin` 存兩組——帳號本身（`username` / `password`，第 3 步用）與介面那一組（`interface_*`，第 4、5 步用）。`services.setup.jellyfin_owns_account`：Jellyfin 判為既有，或套件內而「建立管理員」有結論（`ok` / `skipped`）。之後 `create_admin` 只覆寫介面那一組。舊列由 migration `c3d8a6f1b240` 抄一份（使用者拍板）。
- Prowlarr 重套時多比 `SetupIndexer.login_password`（Berth 上次寫的密碼）：原本只比帳號，只改密碼時被略過，第二條驗收的整合測試就是它紅的。
- 紅燈先行的整合測試要停在拿到 API key 之前才紅：有了 key，`_authenticate` 用 key 不用密碼。錯的那組帳密在「用 Jellyfin 帳號登入 Berth」那一關同樣進不去，那一關沒有 key。
- playwright 實跑（`fake_setup_server.py --scenario bundled`，截圖在 session scratchpad，不進 repo）：
  - 全新環境第 1 步，1280 與 390：剖面四列是「skipper」與三列「skipper · 密碼同上（第 2 步偵測到是套件內的才建立 / 寫入）」，`main` 文字裡沒有密碼；390 的 `scrollWidth` 375，沒有橫向捲動。
  - 走完八步、登入、回 `/setup` 按「改帳密」，1280 與 390：標題「qBittorrent 與 Prowlarr 介面帳密」、「帳號屬於 Jellyfin」提示、Jellyfin 列「skipper · 已建立，密碼在 Jellyfin 裡改」、兩個介面「skipper · 密碼同上」、「介面帳號」預填 skipper；390 沒有橫向捲動。
  - `pnpm -C web e2e` 4 passed（精靈八步那條走的是改版後的第 1 步）。
- 和票面不同的地方（progress.md 偏差與決定已記）：帳號屬於 Jellyfin 之後，Jellyfin 列寫「已建立，密碼在 Jellyfin 裡改」，不是表上的「admin・密碼同上」，因為這時候密碼欄改的是介面那一組。既有 Jellyfin 時 Berth 列也改寫。中點照 DESIGN.md 的 `Dot` 用 ` · `，不用票面的 `・`。「不再接受改 Jellyfin 的那一組」做成**只覆寫介面那一組**，不回 422：帳號屬於 Jellyfin 之後，同一支端點的欄位本來就是介面那一組。

**code-review 沒處理的發現**

- 帳號屬於 Jellyfin 之後只想取消勾選，仍要打一次密碼（`AdminIn.password` `min_length=1`）。有人抱怨再放寬。
- Data Clumps：介面帳號與密碼在 `qbittorrent.py`、`indexer.py` 各拆一次，沒有包成小 model。等第三個消費點出現再包。
- `CutawayLine['key']` 的九個 i18n key 是手寫 union，改文案鍵要兩處同步（打錯 tsc 會紅，但不會自動跟著變）。
- `AdminStep.tsx` 的 `words` 兩份結構相同。`admin.owned.applyHint` 與 `admin.field.applyHint` 前半句重複，不拼接是因為 i18n 拼句子在其他語言會斷。
