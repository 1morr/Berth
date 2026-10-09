# 79 — 搜尋結果不再把 Prowlarr 的 API key 交給瀏覽器

**Status:** done

**Blocked by:** None — can start immediately（與 69 都改搜尋；79 先做，69 排在它之後）

**讀:** 票 76 的 Comments〈`/api/search` 把 Prowlarr 的 API key 交給一般使用者〉；M2 票 08（搜尋結果不落地）；brief §20.7（Prowlarr 代理連結每次搜尋都不一樣）；`berth/api/search.py`、`berth/services/search.py` 的 `download_url`；`berth/api/jobs.py` 的 `JobSourceIn`；`berth/api/gate.py`；`web/src/media/SubmitAction.tsx`

## 為什麼（2026-10-09 票 76 實作時發現）

- 搜尋結果的 `download_url` 是 Prowlarr 的代理下載連結：`http://prowlarr:9696/<id>/download?apikey=<Prowlarr key>&link=...`。
- `/search` 不在 `gate.ADMIN_PREFIXES`，任何登入的 Jellyfin 使用者都拿得到這把 key。前端只是把它原樣送回 `POST /jobs` 的 `source.url`。
- 拿到 Prowlarr 的 API key 就能改 Prowlarr 的設定、索引站與帳密。
- 同一個流程的反面：`source.url` 是任意字串，送單時 Berth 在伺服器端去抓它。登入的使用者能讓 Berth 去抓任何網址，包括內網。

## 做什麼

1. **連結不出伺服器**：
   - 搜尋時，Berth 在伺服器端記下每一筆結果的下載連結。回給前端的只有一個不透明的 id，不再有 `download_url`。
   - 送單（`POST /jobs`）收這個 id，由伺服器換回真正的連結。id 過期或不認得時，回一個說得出原因的拒絕（例如「這筆搜尋結果過期了，再搜一次」），走 i18n。
   - 怎麼記、記多久、重啟後怎麼辦，由實作決定，理由寫在 Comments。不必落地到資料庫：票 08 的「搜尋結果不落地」仍成立，過期重搜就好。
   - 先看成熟產品怎麼做（Sonarr / Radarr 的 interactive search 送單只送 guid 加 indexer id），說明採用了誰的慣例。
2. **`POST /jobs` 不再收任意網址**：手動送單只能指向這次搜尋記下的結果。其他還收網址的入口（一次性連結等）照實盤點：
   - 只有管理員能用的，記在 Comments；
   - 一般使用者也能用的，一起收緊，或在 Comments 寫明為什麼不用。
3. **API 破壞性變更**：`GET /search` 拿掉 `download_url`、`POST /jobs` 的 `source` 換成 id。同一 commit 改 API 型別、前端與 CHANGELOG（Security），plan §8.4 與 brief 同步，progress.md「偏差與決定」記一行。
4. 測試（雙向，寫在測試檔內）：
   - 一般使用者打 `GET /search`，回應全文搜不到 Prowlarr 的 API key；
   - 用 id 送單成功；
   - 用不認得或過期的 id 送單被拒；
   - 直接送一條任意網址，被拒或已經沒有這個欄位。

## 驗收

- [x] `GET /search` 的回應不含任何 Prowlarr 的 API key；有測試守著（含一般使用者）
- [x] `POST /jobs` 只收這次搜尋記下的結果 id，任意網址送不進來；過期或不認得的 id 有 i18n 的說法
- [x] 其他收網址的入口已盤點並處理，結論在 Comments
- [x] 實跑：隔離環境（專案名 `berth-t79`、另一組 port）用一般使用者搜尋並送單成功，瀏覽器 Network 面板的回應裡沒有 `apikey`，附截圖；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；CHANGELOG（Security）、plan、brief、progress.md 已更新

## Comments

### 做法：送單來源記在伺服器上（`berth/services/sources.py`）

- **慣例照 Sonarr 的 interactive search**（`Sonarr.Api.V3/Indexers/ReleaseController.cs`）：搜尋結果以 `{indexerId}_{guid}` 放進程序內快取 30 分鐘，送單只帶 `guid` 與 `indexerId`，找不到回 404「Couldn't find requested release in cache, try searching again」。Berth 照這個形狀：`SourceCache` 記 `JobSource`（連結、發佈名、info hash、發佈時間、大小），結果的每一列只帶 `source_id`，`POST /jobs` 收它，換不回是 404 `source_expired`。
- **兩處不照 Sonarr**：id 是隨機的（`secrets.token_urlsafe(16)`），不是 guid——guid 是索引站給的、可能就是站的下載網址，而且一般使用者不該拿得到能替別人送單的鍵；**記兩小時**而不是 30 分鐘——一次搜尋 35–85 秒、還吃請求預算，結果表常常開一陣子，過期的代價是再搜一次。
- **重啟就忘、不落地**（票 08 的「搜尋結果不落地」仍成立）：與過期同一個說法（「這一筆過期了……重啟過也會忘記。重新搜一次」）。不認得、過期、重啟過分不出來，下一步都一樣，所以是一個理由不是三個；`detail` 是空的，不回聲送來的字串。記的時候清掉過期的，記憶體只有最近兩小時的搜尋（一次最多 200 列、一列不到 1 KB）。Berth 只跑一個程序（同 `EventHub`），所以程序內快取夠用。
- 發佈名、info hash、發佈時間、大小**也改由伺服器記**，不信瀏覽器送回來的——所以 `GET /search` 與一次性連結的列連 `info_hash` 一起拿掉（沒有別的前端消費點），`test_a_publish_date_without_a_timezone_is_refused` 隨輸入欄位刪掉。
- 欄位叫 `source_id` 不叫 `source`：code-review 指出同一列的 `tags.source` 是 BD / WEB，CONTEXT.md 也把 `source` 列為要避開的詞。

### 其他收網址的入口（盤點：OpenAPI 裡 body / query 帶 `url` 欄位的每一支，對照 `gate.access_of`）

| 入口 | 誰用得了 | 處理 |
| --- | --- | --- |
| `POST /jobs` | 登入就可以 | **本票收緊**：只收 `source_id` |
| `POST /rss/oneshot`（`url`） | admin（`/rss` 前綴） | 讀那條 feed 仍收網址（主機要是認得的三站，`kind_of`）；**讀出來的每一筆改成 `source_id`**——`POST /jobs` 不收網址之後它不跟著改就送不了單 |
| `POST /rss/feeds`（`url`） | admin | 不動；同樣只收認得的主機 |
| `POST /settings/jellyfin`（`public_url`） | admin | 不動；只是深連結用的字串，Berth 不去抓它 |
| `POST /setup/owner`、`POST /setup/services/jellyfin(/test)`（`base_url`） | 擁有者成立之前匿名，之後 admin | 不動：精靈第一頁本來就要讓第一個人指一台 Jellyfin（M4 票 06、15 的設計） |
| `POST /setup/services/{kind}` 其餘（`base_url`） | 擁有者成立前誰都不行，之後 admin | 不動 |

一般使用者能讓 Berth 去抓指定網址的，只有原本的 `POST /jobs`。`POST /jobs/{hash}/retry` 用的是 Job 存著的 `source_url`（當初記下的那一條），不收輸入。

### 驗證

- 測試（雙向，在測試檔內）：`test_search_api.py::TestTheIndexerKeyStaysOnTheServer`（一般使用者的回應全文搜不到 `arrange` 寫進設定的 Prowlarr key，前提先斷言 fixture 的連結真的帶 key、結果有兩列；收起來的那一份也沒有；用 `source_id` 送單成功、伺服器拿原本那條代理連結去要 torrent）；`test_jobs_api.py::TestRefusals`（不認得的 id、過期的 id 都是 404 `source_expired`、沒去要 torrent；物件形狀的網址 422、字串網址 404）；`tests/unit/test_job_sources.py`（id 不洩漏連結、同一發佈兩個 id、過期邊界、清過期）。變異：把 `source_id` 換成下載連結本身，5 條紅。
- `uv run pytest`：3742 passed（code-review 的 rename 前後各跑一次）；vitest 1428 passed；前端 e2e 35 passed（rename 前後各一次）（`cold-start` 的 8496 被另一個 session 的 `berth-t80` 佔著，用一份不進版控的 config 把它移到 8596 跑，跑完刪掉）；pre-commit 全綠。
- **docker e2e（`tests/e2e/`）**：它原本直接送 `.torrent` 網址，現在先讀 `sites` 冒充的 acg.rip 一次性連結（`sites.M1_URL`，三包指到 `torrents` 那一台）再送。本機驗了 feed 解析得出三筆、`kind_of` 認得；**整輪 20 分鐘的 stack 沒在這個 session 跑**，nightly 會跑到。

### 實跑（隔離環境）

image `berth:t79`（這個分支，code-review 的 rename 之前），repo 外的 compose（產品 compose 改 `name: berth-t79`、容器 `berth-t79*`、網路 `berth-t79` 172.30.0.0/16、port 18479 / 18879 / 18079 / 19779 / 16879、`restart: "no"`、資料用 named volume）。API 走完精靈（三台套件內、Prowlarr 加 TPB 與 Mikan、TMDB、三條 Route），在 Jellyfin 建非管理員帳號 `deckhand`，Berth 登入是 `role: user`。

- `deckhand` 在《活死人之夜》搜尋：33 筆；回應全文沒有 `apikey`、`download_url`、`prowlarr:9696`，每列只有不透明 id（`.playwright-mcp/t79-search-response.png`，另一個關鍵字的原始回應）。
- 送單 `Night of the Living Dead v01.05.00 [PD]`：request body 只有 `{"source":"NbK8…","media":"movie:10331","route":1}`，回 200 `submitted`、`user_name: deckhand`（`.playwright-mcp/t79-submitted-row.png`）。
- 直接打 `POST /api/jobs`：假 id、字串網址 404 `source_expired`，物件網址 422。
- 只重啟 `berth-t79` 之後在同一頁送另一列：畫面說「這一筆過期了……重新搜一次」（`.playwright-mcp/t79-expired-1280.png`）。
- Network 面板：Playwright 拿不到 DevTools 面板的截圖，改用 `browser_network_request` 讀 request / response body（上面那兩行）加原始 JSON 回應的截圖。
- 跑完 `docker compose down --volumes`、刪 image；`berth-local` 四個容器一直是 Exited，沒動。
- rename 之後沒有重跑實跑：改的是欄位名，前端 e2e 的送單流程（`submit.spec`）與 vitest 守著兩端一致。

### code-review（`22c034d` 起，Standards 與 Spec 兩軸）

處理了：
- 同一列兩個意思不同的 `source`（Standards）：對外欄位改 `source_id`，CONTEXT.md、plan、CHANGELOG 同步。
- `get_sources` / `SourcesDep` 與 `AccessCache` 的命名慣例不一致（Standards）：改 `get_source_cache` / `SourceCacheDep`。
- `read_oneshot` 標 `Effect.READ` 卻寫快取（Standards）：docstring 寫明程序記憶體裡的快取不算改狀態。
- plan §6 search 那一列新句子插在 `published_at` 與它的說明中間、留著「送單時原樣帶回」（Spec）：改正。
- 拿掉 `info_hash`、oneshot 的 `url` 是票外的破壞性變更（Spec）：CHANGELOG 已寫，progress.md「偏差與決定」記一行。

沒處理（記著）：
- `_row` 與 oneshot `_item` 各自組 `JobSource` 再 `remember`（Duplicated Code，判斷題）：兩處、各十行，來源型別不同（Indexer Result / Feed Item），抽出來換不到什麼。
- `SourceCache.__len__` 只有測試用（判斷題）：留著，「清過期」要從外面看得到。
- `sources.py` 丟 `JobRejectedError`，把快取綁在送單語意上（判斷題）：唯一的消費點就是送單。
- 結果的 `key`、`info_url` 仍是索引站給的值：私有站的 guid 可能帶 passkey（不是 Prowlarr 的 key），不在本票範圍。`source_unavailable` 的 `detail` 含下載網址，但 `ServiceError` 已遮 query（票 76），一般使用者看不到 key。
