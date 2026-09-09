# 03 — TMDB 快照與探索頁

**Status:** done

**Blocked by:** ~~01（`media` 的欄位由它決定）~~ 已解除、02（型別產生器先接上）、02b（TMDB 憑證改成使用者自備，探索頁要有憑證才跑得動）

**讀:** plan §2.2、§6（discover 群組）、§7、§8.3、§11.2（T1.1）；brief §13（探索）

## 做什麼

打開 `/` 看得到趨勢與熱門作品、能搜尋、卡片顯示追蹤狀態。`/` 不再導向 `/health`。

帶進來的東西：`media` 與 `tmdb_cache` 表與 migration（欄位依 plan §2.2）；TMDB adapter 補 `trending/{tv,movie}/week`、`{tv,movie}/popular`、
`search/multi` 與 `configuration` 的圖片基底；`services/` 的探索命令、快取與速率限制。

探索頁是 M1 的第一個新頁面，走 `/impeccable shape` 再實作。

## 驗收

- [x] `media` 與 `tmdb_cache` 表與 migration 完成，空資料庫升得上去也降得回來
- [x] `GET /api/discover/trending`、`/discover/popular`、`/discover/search?q=` 回作品清單
      （tmdb id、kind、標題、年份、海報路徑）
- [x] 探索頁顯示趨勢與熱門、搜尋框可搜；卡片顯示追蹤狀態（M1 只有未追蹤 / 已追蹤）
- [x] 探索與搜尋的 TMDB 快取 1 小時生效：同一查詢第二次不打外部（有測試）
- [x] 全域 40 req/s 令牌桶存在且有測試
- [x] 顯示用標題另以 `zh-TW` 取一次（brief §7.5 的檔名仍用英文，本票不碰檔名）
- [x] TMDB 憑證缺失或 TMDB 不可達時，探索頁顯示可行動的錯誤而不是空白畫面
- [x] `/` 不再導向 `/health`；未登入仍導向 `/login`
- [x] 探索頁走 `/impeccable shape`；playwright 實跑並附結果
- [x] 深淺兩主題所有文字對比 ≥ 4.5:1；390px 窄版沒有頁面層級的橫向捲動
- [x] zh-Hant 與 en 並列，沒有硬編字串
- [x] lint / type / test 全綠並貼指令輸出

## 實跑結果

`scripts/fake_setup_server.py --scenario discover`（三個服務是替身，TMDB 打**真的**
`api.themoviedb.org`，憑證由 `BERTH_TMDB_KEY` 帶進去）：

| 量的東西 | 結果 |
| --- | --- |
| 未登入開 `/` | 導向 `/login?redirect=%2F` |
| 趨勢 / 熱門 | 各 40 格（20 劇集 + 20 電影交錯），真海報、真 `zh-TW` 標題 |
| 搜尋（CJK） | 「葬送的芙莉蓮」→ 1 筆，`TV · 2023` / `葬送的芙莉蓮` / `Frieren: Beyond Journey's End` |
| 快取 | 同一個新查詢第一次 **1075 ms**（兩次真 TMDB 往返）、第二次與第三次各 **11 ms** |
| 追蹤狀態 | 直接在資料庫寫一列 `tracked=1` 再重整：那一格立刻標「已追蹤」，而 feed 仍來自快取 |
| 對比（亮色） | 243 個文字節點，最低 **5.71:1**，0 個未達 AA |
| 對比（深色） | 同上，最低 **6.53:1**，0 個未達 AA |
| 對比（錯誤畫面） | 亮色最低 **6.44:1**、深色 **6.53:1**，0 個未達 AA |
| 390px | `scrollWidth == clientWidth == 390`，無溢出元素，網格 2 欄 × 171px |
| 憑證缺失 | 說明 + 後端原文 + 「前往設定精靈」連到 `/setup?berth=3`（一般使用者改成「請管理員…」） |
| TMDB 連不上 | 每個 feed 各自顯示原文 `GET /trending/tv/week: connection refused` + 「重試」 |

實跑當場抓到三個缺陷並修掉（都在同一個 commit）：

1. **只搜到一部作品時，整排空欄變成一塊灰色板子。** 網格原本塗 `bg-rule` 再用 `gap-px`
   透出格線（泊位板的做法），但那塊板永遠是四格滿的，這面牆不是。改成線由每一格自己的
   `border-2` 畫。已寫進 DESIGN.md 的 Don't。
2. **「已追蹤」色塊壓在海報上時讀不讀得出來看運氣。** `deck` 在亮色主題是近白（壓在深色海報上
   很清楚），深色主題是中灰（壓在深色海報上幾乎消失）。改成貼在卡片下方的標識帶上，底是 `well`，
   實測 11.95:1。已寫進 DESIGN.md 的 The Paint Needs A Painted Ground Rule。
3. **「重試」按鈕被 grid 拉成滿版**，比它該有的份量重。

## code-review 的發現（都已修）

`/code-review ddf6c26`，兩個隔離的子代理（Standards 讀 CLAUDE.md / DESIGN.md / plan，Spec 讀本票與
shape brief）。九條有效發現全部處理掉：

1. **令牌桶「全域」那一半沒被測到。** 原本只測 `TokenBucket` 自己、rate 由測試注入。補了兩條契約
   測試：四支端點各真的呼叫一次 `acquire()`，以及兩個 client 拿到的是**同一個** `_BUCKET`
   （TMDB 的上限是每個 IP 的，各配一個桶等於沒有上限）。
2. **英文的 `{{count}} titles` 在一筆時說「1 titles」。** i18next 傳 `count` 時查的是 `_one` /
   `_other`，兩個都沒有就退回原鍵。改成兩個語言各自定義 `count_one` / `count_other`（中文兩個同字，
   `Translations<>` 要求鍵樹一致）；`tooShort` 的變數改名 `{{min}}`，那一條本來就不該走複數。
   實跑確認：`1 title` / `2 titles` / `0 titles`。
3. **搜尋每停一次就把整面牆換成 12 格空位。** shape §6 明寫「搜尋中不換掉上一輪結果」，而
   `pending={isPending || isFetching}` 正好違反它。改成 `keepPreviousData`，而且**回應帶著它自己的
   查詢字串**——留在畫面上的是上一輪的卡片，標題就必須跟著說上一輪的詞。
4. **憑證缺失時同一段話與同一條精靈連結出現兩次**（趨勢一次、熱門一次）。後端仍逐 feed 回自己的
   `problem`（一個垮掉不影響另一個要的就是這個），去重放在頁面那一層。
5. **搜不到時沒有下一步**（shape §5 寫了「回到趨勢」）。空手而歸的牆多一個動作。
6. **`services/tmdb.py::_test` 偷偷改 `settings`**，逼得 `verify_tmdb` 寫兩次設定。改成回
   `(step, image_base_url)`，由呼叫端寫回去。
7. **`_decorate` 逐欄手抄 `MediaCard` 的六個欄位** → `DiscoverItem.from_card()`。
8. **假憑證字串散在五個檔案** → `tests/conftest.TMDB_API_KEY`；`# type: ignore` 補上理由；
   前端測試改用共用的 `discoverWall()`。
9. **`models/media.py` 的註釋指向不存在的 `cache_key()`**；`DiscoverNotice` 用 `berthNumberOf('prowlarr')`
   指 TMDB 的那一步，補註釋說明泊位 3 是「來源」（索引站 + TMDB 兩步）。

未處理、留給里程碑收尾的一條：**其他頁面既有的 `{{count}}` 英文複數**（`health.routes.count`、
`setup.detect.done`、`routes.build` 等）有同樣的缺陷。不在本票範圍，M1 UI 收尾的 `/impeccable audit`
一起過。

## Comments

- **卡片還不是連結。** `/media/:id` 要到票 04 才存在，而一個點下去沒反應的格子比一個不能點的
  格子更糟。票 04 把整格包成連結時，hover / focus 是邊框由 `rule` 換 `rule-strong`。
- **追蹤動作本身在票 04。** 本票只顯示 `media.tracked`，沒有任何地方寫得了它（實跑時是直接
  對資料庫塞一列驗的）。
- **`media` 表的四個欄位這一票沒有消費者**：`title_original`、`folder_name`、`default_route_id`、
  `tmdb_snapshot_json` 依 plan §2.2 建好，票 04 才開始寫。
- **`{tv,movie}/popular` 沒有分頁**，所以一個 feed 固定 40 格。要更多要等無限捲動，plan 沒要求。
- **搜尋的 `include_adult=false` 是寫死的**，沒有設定項。plan 與 brief 都沒提到成人內容的偏好。
