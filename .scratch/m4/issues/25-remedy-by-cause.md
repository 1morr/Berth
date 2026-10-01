# 25 — 補法照原因給，不照檢查項目給

**Status:** done

**Blocked by:** None — can start immediately（與 24 都碰頁 3，不改同一段；衝突時 24 先）

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 4、10、11、12、13、19 條）；plan §9.3 第 3 點、§9.5；票 19、21 的 `## Comments`；
`web/src/components/routeChecks.ts`、`web/src/components/failures.ts`

## 為什麼（2026-10-01 精靈實測）

- **Berth 自己寫不進去時補法指錯（P1，兩邊實測證實）。** `remedyFor` 沒有特判 `berth_cannot_write`，照檢查項目落
  （`web/src/components/routeChecks.ts:151-176`）：寫不進寫入目標 → 「Jellyfin 沒掛 /data」＋jellyfin 片段；寫不進分類目錄 →
  「qBittorrent 沒掛 /data」；建不了分類目錄 → 「同名分類衝突」；目錄被刪 → 「不在 /data 底下」。照做都修不好。
  截圖 B5-08/09、E12-03～06。`save_path_missing` 也落到 berth 掛載片段（程式碼疑點）。
- **協定錯說成連不上（既有）。** https 填到 http 的 port（SSL WRONG_VERSION）、位址沒寫 `http://`（UnsupportedProtocol）
  都歸成 `unreachable`、叫人確認 port（`berth/adapters/http.py:127-132`）；位址欄不驗格式。截圖 E2-06～09。
- **library_path 的補法叫人改選新路徑，但 Route 已鎖（既有）。** 沒說要先刪這條 Route（`resources.ts:855`）。截圖 E8-07。
- **非管理員在精靈期間看到「Berth 後端可能沒在跑」（既有）。** 實際是 403（`SetupPage.tsx:390`、`resources.ts:40`）。
  同類：擁有者被搶先成立時的 401 說成「後端出錯了」。截圖 E10-05、E12-11。
- **只有 Berth 時選套件內 Prowlarr，說成「讀不到 API key」（既有）。** 先查 key 才連線（`berth/services/setup.py:462-465`），
  要貼了 key 才說主機名解不到。截圖 E9-07～09。
- **qBittorrent 停掉時頁 2 綠紅並存（全新）。** 連線卡綠，下方紅「主機名解不到：不在這套 compose 裡」（原因錯），沒有重新
  測試鍵、前進鍵照在；容器恢復要重新整理（`ServiceChoice.tsx:674-679`、`QbittorrentStep.tsx:219-259`）。截圖 B9-04～07。

## 做什麼

1. `berth_cannot_write`（以及 `save_path_missing`）有自己的補法：說是 Berth 自己寫不進 `<路徑>`，指向 PUID/PGID 與目錄權限，
   不給別的容器的片段。「目錄不存在」與「不在 /data 底下」分開。
2. 連線例外多分兩種：TLS 協定不符、位址缺 scheme；人話分別說「這個 port 講的是 http／https」「位址要以 http:// 開頭」。
   位址欄前端先驗 scheme（照 *arr 的做法不自動補，直接提示）。
3. library_path 的補法：Route 已建好時說「先刪這條 Route，再選新的 Berth 路徑」。
4. 對 Berth 自己的 401／403 分開說：沒登入 → 請登入；不是管理員 → 「精靈只有 Jellyfin 管理員能繼續」；擁有者已在別處成立 →
   說出來並給登入連結。
5. 套件內 Prowlarr 先連線再讀 key：主機名解不到時照 Jellyfin、qBittorrent 的句子。
6. 頁 2 連線卡跟著最新的失敗變紅、出現「重新測試」，套用中斷時不留前進鍵；原因照實際例外。

## 驗收

- [x] vitest：`berth_cannot_write` 在檢查 1、3、5 都給同一條「Berth 寫不進」的補法、沒有 jellyfin／qbittorrent 片段（雙向：
      真正的 `probe_unseen`、`jellyfin_cannot_see` 仍給各自的片段）
- [x] 整合測試：https 對 http、缺 scheme 各得到新的理由；真正連不上仍是 `unreachable`
- [x] vitest：非管理員、未登入、擁有者已存在三種 401／403 各有自己的人話
- [x] 整合測試：只有 Berth 時選套件內 Prowlarr → `not_deployed`，不是 `api_key_missing`
- [x] playwright 對 `berth-existing` 與套件內各實跑：唯讀目錄、https 對 http、非管理員登入、停掉 qBittorrent。附截圖或文字結果
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**做了什麼**（細節在 plan §9.3、§9.5 第 8 點、brief §20.14 的兩條實測）

- 補法先看原因（`routeChecks.remedyFor`）：`berth_cannot_write` → PUID / PGID 與權限、沒有片段；新代碼
  `directory_missing`（路徑在 Berth 自己的共用根目錄底下卻不存在）與 `path_not_visible`（不在它底下）分開；
  `save_path_missing` → 回 qBittorrent 那一頁重新套用（**與票的字面不同**：票寫「說是 Berth 自己寫不進」，但它是
  qBittorrent 沒報預設路徑，與權限無關）；`scheme_*` → 改位址那一句。`library_path` 的兩個掛載補法說先刪 Route。
  寫不進探測檔時說它所在的目錄（`steps.failure_of`）。
- 連線分類（`adapters.http`）：`SchemeMismatchError`（`WRONG_VERSION_NUMBER`，以及 qBittorrent 那種握手不回、
  `ConnectTimeout` 鏈上有 `SSLWantReadError`）、`SchemeMissingError`（`UnsupportedProtocol`）；新理由
  `scheme_mismatch` / `scheme_missing`。位址欄送出前驗 scheme（`setup/address.ts`，服務頁與頁 4 既有表單）。
- 401 / 403：只改前端（`requestProblem` 的 `ownerPending`，頁 1 的擁有者表單與服務選擇傳它）；讀不到精靈狀態而
  是 403 時說「精靈只有 Jellyfin 管理員能繼續」並給登出（`useSignOut` 從 AppShell 抽出）；401 給「前往登入」，
  按下先重問 `/health`。門禁沒改：理由碼放進 OpenAPI 會撞 `TestDeclaringWhatEachEndpointRefuses`（門禁不是路由）。
- 套件內 Prowlarr 沒有 key 時先問匿名 `/ping`。
- 頁 2：`_qbittorrent_secured` 要最後一次測試是綠的；前端讀差異或套用回來連不上而卡片還綠時自動重測一次
  （同一份結果只測一次）。

**playwright 實跑（`berth:t25` 由工作樹 build，用完刪；截圖在 gitignore 的 `.playwright-mcp/t25/`）**

- 套件內（`berth-qa/bundled`，全新 config/data，只把 berth 換成 `berth:t25`，用完 down、compose 改回原 image）：
  - 唯讀目錄：compose override 讓 berth 容器裡 `/data/library/tv` 唯讀 → 頁 3 重新檢查，TV 紅在 `probe_visible`：
    「Berth 自己寫不進 …：berth 容器裡的使用者（.env 的 PUID / PGID）…」，沒有任何 compose 片段。PASS（路徑原本印成
    探測檔，修成目錄後在既有那一輪驗）。
  - 停掉 qBittorrent：`docker stop` → 回頁 2，連線卡自動變紅「主機名解不到」，補法說容器沒在跑、有「重新測試」，
    只剩「上一個泊位」→ `docker start` → 重新測試綠、前進鍵回來，不必重新套用。PASS。
  - https 對 http / 缺 scheme：頁 4 選既有 Prowlarr，`host.docker.internal:21697` 被欄位擋下（「位址要以 http:// 或
    https:// 開頭」，沒有送出）；`https://host.docker.internal:21697` →「連得上，但這個 port 講的是 http，不是 https」。
    那條纜繩的手動步驟原本仍是通用句，修了（`existingFix` 看 `schemeFix`，vitest 補一條）。PASS。
  - 非管理員：在 qa Jellyfin 建一般帳號 deckhand 登入 →「精靈只有 Jellyfin 管理員能繼續：deckhand 登得進 Jellyfin，
    但不是這台的管理員」＋登出，按登出回登入頁。PASS。
- 既有（`berth-existing` 的 ok-*；受測 `qa2-berth` 掛 berth-trial/data、另把 `/data/media/tv` 唯讀蓋上）：
  - 只有 Berth 時選套件內 Prowlarr → `not_deployed`（`GET /ping: host does not resolve`），原本是 `api_key_missing`。PASS。
  - https 對 http（qBittorrent）：**實跑抓到** ok-qbittorrent 對 ClientHello 不回，原本落成 `unreachable`
    （`ConnectTimeout`）；補了握手逾時那一種（紅燈測試先行），重 build 後「這個 port 講的是 http，不是 https」＋
    「把位址開頭的 https:// 改成 http://」。缺 scheme 被欄位擋下。PASS。
  - 停掉 ok-qbittorrent：頁 2 自動變紅「主機名解得到但連不上」、有重新測試、沒有前進鍵 → 起回來重測綠。PASS。
  - 唯讀目錄：頁 3 只勾 TV Shows、目標選原本的 `/data/media/tv`（不加 Berth 路徑）→「Berth 自己寫不進 /data/media/tv」，
    沒有「你的 Jellyfin 沒掛」的片段。PASS。
  - 非管理員：ok-jellyfin 暫建 t25-deckhand → 同一句＋登出。PASS。
  - 還原：測前測後各用 `berth-qa/existing/scripts/snapshot.py` 快照；中途差異是 ok-jellyfin 一把「Berth」key、一筆
    `berth-server` 裝置、t25-deckhand、berth-trial/data 的 `torrent/incomplete{,/tv-shows}`。刪 key、帳號與目錄時把
    測前就有的那筆 `berth-server` 裝置一起刪了，以同一組 Authorization 重新登入一次補回；最後 10 檔與測前完全相同。
    berth-trial 沒動；qa2-berth 已刪。

**驗證（最後一次改程式碼之後）**：`pre-commit run --all-files` 全過；pytest 3448 passed；vitest 77 檔 1167 passed；前端 e2e 33 passed

**code-review 處理了的**：`/media`、`/mnt` 這種 image 本來就有的空目錄讓「上面幾層在」的判法把沒掛說成目錄被刪
（兩軸都抓到；改看共用根目錄，回歸測試拿掉判斷會紅）；擁有者成立前的 403 是「先做完頁 1」不是「不是管理員」；
頁 3 Route 檢查碰到 `scheme_*` 仍給「確認在跑」；頁 1 選服務時被搶先仍說登入已失效（vitest 拿掉會紅）；
`qbittorrentLostAt` 改名；兩處協定補法收成 `schemeFix`；`addressError` 補測試。

**code-review 未處理的發現**

- 反方向（`http://` 打到講 https 的 port）認不出來：本機的 Python TLS 伺服器只是重設連線，與別的斷線分不開；沒有
  真服務開 https 實測過（Jellyfin 的 Kestrel 可能回 400，那會落成 `protocol_mismatch`）。
- 握手逾時當成協定錯配是推斷：一台真的講 https、但握手慢到 5 秒的服務會被叫去把 `s` 拿掉。沒有實際案例。
- `_qbittorrent_secured` 收緊的副作用：在頁 3–5 時 qBittorrent 重測變紅（或套件內重啟中的 `waiting`）後端退回頁 2。
  重測只在頁 2 或等待輪詢時發生，記在 plan §9.3〈續行與跳過〉。
- 例外 → `ConnectionReason` 的對照有兩份（`setup._classified`、`indexer._failed_probe`），這次各加兩支；票 20 之前就是
  兩份，沒收。
- `RequestFailed` 內含 `SignIn`，多依賴路由與 query client（只在需要登入時掛上）；`_qbittorrent_secured` 直接讀
  `choice.test.state`。判斷題，沒動。
