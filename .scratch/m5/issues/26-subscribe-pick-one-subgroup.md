# 26 — 訂閱一定由使用者選字幕組；關鍵字訂閱只綁一個字幕組、第一批在卡上確認

**Status:** done

**Blocked by:** 23d

**讀:** brief §15（RSS 設計要點，尤其從 Media 頁訂閱、Mikan、Nyaa / acg.rip）、§14〈對話裡的確認卡〉、§19 2026-10-28 的 Route 決定（票 23b）；plan §2.6 Proposal、§11.3 M3 RSS、§11.6 票 13 / 14 / 23b；`berth/services/rss.py`（`subscribe_mikan`、`subscribe_search`、`add_feed`、`delete_feed`）、`berth/services/proposals.py`、`berth/services/agent_tools.py`（`_compact_search`）、`web/src/agent/` 的確認卡；票 14、23b 的 Comments

## 為什麼

使用者 2026-10-28 在試用機請助理訂閱「鐵旅！meet with 鐵道少女」：

- Mikan 一時連不上，助理改建 acg.rip 關鍵字訂閱（直接建，不出卡）。它把搜到的**每個字幕組**（黒ネズミたち、ToonsHub）都綁上作品，各等第一批確認；使用者沒選過字幕組。
- 使用者叫它重試後，它在 Mikan 訂了 ANi 字幕組。**字幕組是模型自己挑的**，卡上只能按確認；而且它沒先處理 acg.rip 那個，同一部作品變成兩份訂閱。
- 助理沒有刪除訂閱的工具，只能說「留著」。
- 搜種子給模型的結果拿掉了發佈時間（`_compact_search`），模型算不出字幕組更新多快。

使用者決定（2026-10-28）：
- **字幕組由使用者選**：助理在對話裡列比較表、給建議；**確認卡上字幕組是必選欄位**，可選不只一個時一定要使用者選，伺服器擋模型代選（同票 23b 的 Route）。
- **關鍵字訂閱（Nyaa / acg.rip）要指定字幕組，只綁那一個**；它的第一批**改在確認卡上確認**（卡上列出第一批會下載的發佈名），不再要使用者到 RSS 頁按。Mikan 照舊（專屬 RSS，整季直接下載）。

## 做什麼

1. **Mikan 訂閱卡**：卡上的字幕組變成可選欄位，選項是那個番組的字幕組（附最近更新日期、集數、最新一筆）；可選不只一個時卡上必選、伺服器驗收到的字幕組在清單裡（照 23b `routes_json` 的做法）。模型帶來的字幕組只當預選。
2. **關鍵字訂閱改成出卡**：`subscribe_search` 多一個字幕組參數（照字幕組名比對發佈名）；只為那個字幕組長出 RSS Series 並綁上，其他字幕組的發佈不綁。卡上列出第一批會下載的發佈名，按確認就開始下載，那個 Series 記成第一批已確認。卡上同樣可以改選字幕組（從這次搜到的字幕組裡選）。
3. **重複訂閱**：訂閱（Mikan、關鍵字、加 RSS 網址）之前查這部作品有沒有現成的訂閱；有就在工具結果與卡上說出來（哪一個來源、哪個字幕組），由使用者決定。
4. **刪除訂閱的工具**：`rss.delete_feed` 給模型（出卡，`needs_person` 照規則；卡上說刪掉會怎樣、已下載的檔案留著）。
5. **搜種子給模型的結果保留發佈時間**（`_compact_search`），讓模型算得出各字幕組多久出一集；注意上下文長度（票 23d 的每輪上限修法不能退）。
6. 舊資料：已經「一個關鍵字 Feed 綁多個字幕組」的照舊運作，不做 migration；在 Comments 寫明。
7. UI 文案走 i18n（zh-Hant、en）；改到的 API 跑 `gen:api`。

這張只做伺服器與卡片；訂閱的 skill 與多語言搜尋是票 27。

## 驗收

- [x] Mikan 卡：字幕組多於一個時沒選不能確認、伺服器拒絕清單外的字幕組（測試，變異會紅）
- [x] 關鍵字訂閱：只綁指定字幕組；卡上列出第一批、按確認就下載且 Series 記成已確認（測試）
- [x] 重複訂閱會說出來（測試）；`delete_feed` 是工具、出卡（測試）
- [x] 搜種子給模型的列有發佈時間（測試）；Re:Zero 那種長結果不超過每輪上限（沿用 23d 的測試）
- [x] playwright 實跑兩種卡（1280 與 390，附截圖）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff；brief §15、plan、CHANGELOG、progress.md 已更新
- [x] 不發版、不 push

## Comments

### 2026-10-28 實作（`1db56687..HEAD`）

**做了什麼**

- **Mikan 卡**：提出時讀番組頁（`bangumi.read_bangumi`），每個字幕組一個選項（筆數、最近更新、最新一筆；已經綁在作品上的不列，訂了也是 `series_bound`）。模型給的在選項裡才預選；選項不只一個、或模型給的不在裡面時 `required`。`decide` 收 `subgroups`（與列對齊，選項的 `key`），沒選 422 `subgroup_required`、清單外 422 `subgroup_not_offered`；執行時用選項的 `arguments`（`subgroup_id`、`subgroup_name`）蓋過存下的參數，雜湊照舊比存下的那一份。`proposals.subgroups_json`（migration `d7e1b3a5c926`）。番組頁讀不到就不出卡（`feed_unreachable`）。
- **關鍵字訂閱出卡**：`subscribe_search` 多 `subgroup`、標 `downloads`（看參數照最嚴）。卡片那一列模型一定要給 `subgroup`（`agent.SearchSubscriptionRow`）。提出時讀一次搜尋（`rss.search_subgroups`）：字幕組各帶第一批的發佈名，卡上照選的那一組列出。建好的 Feed 只收那一組（`rss_feeds.subgroup`，`parser.binding.of_group` 照發佈名的組名比，與 `title_key` 同一種正規化），`primed_at` 當場寫、這一輪綁上的 Series `confirmed = true`。
- **重複訂閱**：`rss.list_subscriptions`（新的讀取工具，Feed 名、站、字幕組，不給網址）；提出訂閱卡時存進 `preview.existing`，卡上說出來、卡片結果多 `existing_subscriptions`。加 Feed 只認得 Mikan 單一 feed 的番組（`rss.subscriptions_of_feed_url`）。
- **刪除訂閱**：`rss.delete_feed` 進 `TOOLS`（不可逆 → 出卡），`feed_id` 進守法的 id 欄位；卡片說 Feed 名、站、幾筆紀錄一起刪、檔案與綁定留著。
- **種子搜尋保留 `published_at`**；給模型的列數規則（前 10 列 + 新集數）不動，23d 的測試照過。
- **拿掉**：`Turn.run_write` / `_route_unsettled` / `_write_runner`（沒有不出卡的寫入工具了；`_toolset` 斷言寫入一定是卡片）、`rss.mikan_season_size`（集數改看番組頁）、ToolCall 上「到 RSS 頁那一列」的連結與它的測試、文案。
- **前端**：卡片的字幕組是一排 `aria-pressed` 的整行鍵（重用 Media 頁的 `Options` / `SubgroupLine`），`required` 的沒選不畫確認鍵；Mikan 的「送出」跟著選的那一組；關鍵字卡列第一批（前 5 筆，其餘收在 `<details>`）；重複訂閱是重線框一塊；刪除訂閱卡。
- **e2e**：`agent` 情境加合成的 SPY×FAMILY 番組頁、三個單一 feed、acg.rip 搜尋與兩條腳本；`agent.spec.ts` 兩條（1280 / 390），截圖 `mikan-card`、`mikan-picked`、`mikan-confirmed`、`keyword-card`、`keyword-picked`、`keyword-confirmed`（`web/test-results/agent-訂閱-Mikan…`、`agent-關鍵字訂閱…`）。

**決定（票面沒寫到的）**

- 別的字幕組的發佈**不寫成 Item**（不只不綁）：寫了會長出待綁定的 Series，正是試用機上使用者說不要的。brief §15 已寫。
- 數量閘：訂閱一列的 `torrents` 取**選項裡最多的那一組**（卡上能改選，取上限）。
- 「第一批已確認」照名詞表是 RSS Series 的 `confirmed`；同時 Feed 的第一輪預覽也算選過「全部下載」。只標這一輪綁上的 Series，之後才長出來的（例如換了標題骨幹）照一般規則走第一批。
- 新增 `rss.list_subscriptions` 工具（票面沒列）：模型要刪重複的訂閱得先拿得到 `feed_id`。
- **舊資料**（第 6 點）：已經一個關鍵字 Feed 綁多個字幕組的照舊運作（`subgroup` 空字串 = 每一組都收），不做 migration。
- ~~**Media 頁的關鍵字訂閱不變**~~：協調者 2026-10-28 決定照同一條規則改，見下一節。

**code-review 未處理（判斷題）**

- 番組頁或搜尋上**一個字幕組都沒有**時不存選項，照模型給的那一個訂（卡上照樣寫出是哪一個；關鍵字訂閱說「這次搜尋沒有找到它的發佈」）。Spec 軸建議改成不出卡；留著是因為還沒開播的作品在 Nyaa / acg.rip 上本來就搜不到，訂下去等第一集是合理用法。Mikan 全部字幕組都已綁定時同理（模型給的那一個會在乾跑被 `series_bound` 擋下）。
- 重複訂閱只在**卡片結果**裡告訴模型；出卡那一刻模型拿到的是「等人按」，使用者按拒絕時模型看不到原因。模型可以先叫 `list_subscriptions`（工具說明叫它訂閱前先查）；skill 裡寫「訂閱前先查」留給票 27。
- 卡上的第一批是提出那一刻的搜尋，按下去時重讀一輪：之間新出的也會送。文案已改成明說（「卡片出來之後才發佈的也算」）；數量閘是上限、不擋這一點。
- 加 Feed 的重複訂閱只認得 Mikan 單一 feed：Nyaa / acg.rip 的搜尋網址、聚合 feed 看不出是哪一部作品。
- Standards 軸的 smell：`_mikan_preview` 與 `_search_preview` 骨架相似、`_subgroups` 與 `_routes` 形狀相近、`ConfirmCard` 的 `SubscribeRowBody` 對 Mikan / 關鍵字分支五處、`SubgroupOption.key` 兩種意思（Mikan 是 id 字串、關鍵字是組名）、`ConfirmCard` 從 `media/SubscribePanel` import 共用元件（要搬進 `components/` 時連同 `rss/WorkChoices.tsx` 的 `Choices` 一起合）。已處理：`SubscriptionRef` 的「訂閱」一詞補進 CONTEXT.md、殘留註解三處、`parse_qs` 搬進 `mikan.feed_ids`。

**發版建議**（不發版、不 push）：新行為加 API 欄位與 migration，照 SemVer 0.x 是 minor；併進 M5 的版本。

**驗證**：`uv run pre-commit run --all-files` 全過；`uv run pytest -m "not e2e"` 5171 passed、1 skipped；`pnpm -C web test` 2303 passed；`pnpm -C web e2e` 66 passed（2.2m）；`pnpm -C web gen:api` 無 diff；`alembic heads` 只有 `d7e1b3a5c926`。變異：proposals 拿掉「沒選就拒」「清單外就拒」「執行套用選的」各紅；rss 拿掉字幕組過濾、不標 `confirmed` 各紅；卡片拿掉「沒選不畫確認鍵」紅。

### 2026-10-28 第二個 session：作品頁也只綁一組（協調者）

協調者兩題的決定：(1) 作品頁的關鍵字訂閱也照同一條規則（使用者 2026-10-28「搜索建立的訂閱應該先搜、列出字幕組、讓用戶選」，不分側面板或作品頁），伺服器的字幕組參數改必填、不留「不帶就全綁」的舊路；(2) 搜不到任何字幕組時照助理建議的那組出卡，維持。

- **後端**：`rss.subscribe_search` 的 `subgroup` 必填（沒有預設；空白是程式錯，兩個入口都擋：API 的 `min_length` + `pattern`、卡片那一列的 `SearchSubscriptionRow`），建好一律 `primed_at`、綁上的 Series `confirmed`；「沒給字幕組 → 每一組都綁、第一輪等人選」那條路刪掉。`rss.search_subgroups` 從 `internal` 改成登錄表命令（不是工具），開 `GET /rss/search/subgroups?kind=&q=`。`subscribe_search` 合併了 main 的票 24（unique 衝突轉 `feed_duplicate`）。
- **前端**：作品頁 `SearchFeedPicker` 改成「標題鍵 / 搜尋詞 → 搜尋 → 字幕組清單（同 Mikan 的 `Options` + `SubgroupLine`）→ 選一組、資料夾名、第一批（`rss/ReleaseTitles`，卡片也改用它）→『訂閱並送出第一批（N 筆）』」；建好不再就地畫第一輪預覽（`FirstRound` 只剩 RSS 頁用，拿掉 export）。搜不到字幕組說出來、沒有訂閱鍵；讀不到那一站用新的一句（`searchUnreachable`，原本那句寫死了 Mikan）。
- **測試**：`test_rss_subscribe` 守舊行為的兩條刪掉（全綁等第一輪、不帶字幕組），其餘補字幕組；`list_subscriptions` 的「每一組都收」改用直接寫的舊 Feed。`test_rss_api` 三條新的（列字幕組、讀不到 502、不帶字幕組 422 / 帶了只綁那一組且第一輪已選）。vitest：作品頁兩條改寫、失敗兩條（訂閱、讀字幕組），變異（沒選字幕組也畫訂閱鍵）紅。playwright `rss-subscribe` / `-390`：acg.rip 那一段改成選喵萌奶茶屋&LoliHouse，截圖 `3-acgrip-subgroups`、`4-acgrip-picked`、`5-acgrip-subscribed`。真服務 e2e `test_4_m3_rss.py`：Kamiina Botan 改訂绿茶字幕组，驗千夏字幕组的合集不進來。實驗腳本 `rss_subscribe_timing.py` 補字幕組參數。
- **未處理（記錄）**：登錄表推輸入模型時用 `typing.get_type_hints` 沒帶 `include_extras`，命令簽名上 `Annotated[..., Field(...)]` 的限制與說明會被丟掉——`anilist.read_season` 的 `limit`（`ge=1, le=50`）其實沒生效。本票改用一般參數加入口檢查繞開，沒改登錄表（影響所有命令的輸入模型，該另開票）。

### 2026-10-28 同一個 session：保留「只追之後的」（協調者）

協調者：第一批確認的地方（作品頁、側面板的卡）都給兩個選擇——「下載這些並追之後的」（預設）與「只追之後的」，與 RSS 頁第一輪同義、用同一條服務命令；作品頁不另加數量上限，卡片維持 13 個 torrent。

- **後端**：`subscribe_search` 多 `first_batch: PrimeMode = all`。建 Feed（`primed_at` 留空）→ 讀一輪 → 走 `rss.prime_feed`（RSS 頁第一輪那一支）；`all` 時這一輪綁上的 Series `confirmed`，`later` 不標（入庫的是之後的集數，人沒看過）。**讀不到就刪掉剛建的 Feed、回 `feed_unreachable`**（原本是留一條 `poll_error` 的 Feed；第一輪選不了的不留，同 Mikan 的訂閱）。卡片：預覽逐列 `first_batch`（命令輸入有 `first_batch` 的列才能選），`decide` 收 `first_batch`（422 `first_batch_not_offered`），`proposals.first_batch_json`（併進本票的 migration `d7e1b3a5c926`，還沒發版）；卡片結果多 `first_batch_chosen_on_card`。API 訂閱 body 多 `first_batch`。
- **順手修的潛在 bug**：`rss._submit_waiting` 先讀出整批 Item 再逐筆送；某一筆被拒而 `add_download` rollback（票 24 的並行插入）時，其餘先讀好的 Item 全部過期，下一筆讀 `series_id` 變成同步 lazy load（`MissingGreenlet`）。改成逐筆以 id 重讀。失效條件是 `test_two_searches_growing_the_same_series_at_once_both_succeed`：第一輪改走 `prime_feed` 之後約四成紅，修後連跑 20 次全綠。
- **前端**：`FirstRoundChoice`（`media/SubscribePanel`，卡片共用）：兩個整行鍵、各一句後果；作品頁的主要鍵跟著說「訂閱並送出第一批（N 筆）」或「訂閱，只追之後的」，結果那一句也分兩種；卡片的「送出」那一格與第一批底下那一句跟著選的換。
- **測試**：`test_rss_subscribe` 加「只追之後的」（現有的五筆略過、沒有 Job、Series 沒確認，之後的新一筆照送）與「讀不到就不建」；`test_proposal_subgroups` 加三條（卡上選 later 一筆都不送、預設照送、送單卡帶 `first_batch` 是 422）。變異：執行不套用卡上的第一輪、`subscribe_search` 不看 `first_batch`、卡片與作品頁寫死 `all`，各紅。vitest：卡片一條、作品頁一條。playwright：`rss-subscribe` 改選「只追之後的」（截圖 `4-acgrip-picked`、`5-acgrip-later`、`6-acgrip-subscribed`），`agent` 的關鍵字卡照預設確認並截圖兩個選擇（`keyword-picked`）。
