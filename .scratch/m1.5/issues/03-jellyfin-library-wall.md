# 03 — 媒體庫頁改成瀏覽整個 Jellyfin 媒體庫（權限閘門）

**Status:** done

**Blocked by:** 01、02

**讀:** plan §2.1、§6（auth、inventory）、§7、§8.2、§11.2b；brief §11、§12、§13（媒體庫）、§19（M1.5 拆票前的
四條、顯示用標題的語言）、§20.8；`docs/research/library-browsing.md` §2、§3.1、§7、§9；票 01 的結論；
`.scratch/m1/library-shape.md`；`CONTEXT.md` 的 **Inventory**、**Jellyfin Library**

## 做什麼

M1.5 的 tracer bullet。媒體庫頁從「一條 Route 一頁、只列 Berth 經手的作品」（票 13）改成「一個 Jellyfin
媒體庫一頁、整個媒體庫」：一般使用者打開它，看到的是自己在 Jellyfin 看得到的那幾個媒體庫與裡面的每一部
作品，包括不是 Berth 入庫的；Berth 經手的作品疊上票 13 的入庫狀態，還沒進 Jellyfin 的（下載中、待審、
卡住）仍然在牆上。

**權限是這一票的核心**，集中在 services 的一處，後面的每一張票都經過它（plan §11.2b 前置、研究 §9 第 1 點）：

- Jellyfin 的 `userId` 一律取自 session，絕不收前端傳入。
- 媒體庫 id 對這位使用者的 `GET /UserViews?userId=` 允許清單驗證，不在清單就拒絕、不轉發。
- 取允許清單時一併讀帳號的 `Policy`，兩者同一份短時間快取；帳號被停用就結束 Berth 的 session。
- 單一作品與集的讀取走會檢查可見性的端點（依票 01 的實測結果），不用 `/Items?ids=`。

**名稱**：牆上已在 Jellyfin 裡的作品顯示 Jellyfin 的名稱（拆票時使用者拍板，brief §7.5）；還沒進 Jellyfin 的
卡片沿用票 02 的規則，跟著 UI 語言。

**連結**：有 TMDB id 的作品連 `/media/:id`（探索與媒體庫共用詳情頁）；沒有的只給 Jellyfin 深連結。牆上的
作品本來就帶 Jellyfin item id，所以票 13 留下的「反查完卻沒有 `jellyfin_series_id`、卡片一直說還在掃描」
對已在 Jellyfin 裡的作品不再發生——Berth 的作品與 Jellyfin 的作品之間的對應**不能只靠帳本的
`jellyfin_series_id`**。

海報是票 04（本票沒有 Jellyfin 圖的卡片用佔位）；觀看狀態、排序篩選、繼續觀看與下一集是票 05–07。
shape 要替它們留位置，就像 M1 票 04 替票 08、13 留位置那樣。還沒進 Jellyfin 的作品放在哪（混在分頁牆裡還是
另一列）在 shape 定——牆的分頁與排序來自 Jellyfin，那些作品不在 Jellyfin 的結果裡。

## 驗收

- [x] 媒體庫頁一個 Jellyfin 媒體庫一頁（取代 `/library/:routeSlug`），切換列只列這位使用者 `UserViews` 裡、
      Berth 瀏覽得了的媒體庫類型（電影、劇集）；`/library` 導向第一個
- [x] 牆上是該媒體庫的全部 Series / Movie（含非 Berth 入庫的），大媒體庫分頁
- [x] Berth 經手的作品疊上入庫狀態；還沒進 Jellyfin 的作品仍在頁面上；「待審」「Unmatched」兩個篩選保留
- [x] 已在 Jellyfin 裡的作品顯示 Jellyfin 的名稱；有 TMDB id 的連 `/media/:id`，沒有的只給 Jellyfin 深連結
- [x] 權限集中在 services 一處；整合測試證明：不在允許清單的媒體庫 id 被拒且**沒有轉發給 Jellyfin**（Fake
      記錄不到那次查詢）、前端塞進來的 `userId` 不起作用、帳號被停用後 session 結束且下一個請求是 401
- [x] 允許清單與 `Policy` 共用一份短時間快取，快取時間有常數與理由
- [x] adapter 新方法有 Fake 與契約測試（用票 01 錄的 fixture）；每個過濾參數有「伺服器真的有過濾」的斷言
- [x] Jellyfin 連不上時頁面說得出原因，不是空白牆
- [x] `CONTEXT.md` 的 **Inventory** 改定義；plan §6（inventory 群組）、§7（路由）同步改
- [x] `fake_setup_server.py` 有一個能演整庫瀏覽與受限使用者的情境，README 的情境表同步
- [x] 媒體庫頁走 `/impeccable shape`（`.scratch/m1.5/library-shape.md`）；playwright 實跑並附結果，含受限使用者
- [x] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [x] lint / type / test 全綠並貼指令輸出

## Comments

- 2026-09-17 實跑（playwright，`fake_setup_server.py --scenario library`）：`deckhand` 的切換列只有 Movies、TV；
  `/library/item-anime` 是「找不到這個媒體庫，或你沒有權限看它」，API 帶 `?userId=` 照樣 404、只打一次；Movies 131 部
  翻到第 2 頁（`101–131 / 131`，Oppenheimer 兩個版本、深連結到瀏覽器主機的 8096）；TV 牆上 The Bear「部分 8 / 30」、
  Slow Horses「待審」、Home Videos 2019 只有深連結；「還沒進 Jellyfin」一條是 Severance（下載中）；「待審」篩選只剩
  Slow Horses、帶子與分頁收起。管理員看得到 Anime（SPY×FAMILY 在牆上、葬送的芙莉蓮在帶子上）。
  在替身 Jellyfin 停用 `deckhand` 之後，下一次換媒體庫落到 `/login?redirect=…&expired=true`，`/api/auth/me` 401。
  對比（文字節點逐一量，`color-mix` 轉 sRGB）：深色最低 6.64:1、亮色最低 5.69:1，1280 / 390 × 三頁；390px 橫向捲動 0。
  Tab 順序：切換列 → 帶子上的卡片 → 篩選列 → 牆（沒有 `/media` 連結的卡片只有深連結那一站）。EN 介面的名稱、篩選、
  帶子標題都換了，Jellyfin 的名稱不換。impeccable 檢測器 0 findings。
- 2026-09-17 實跑抓到並修掉：TanStack Query 預設對 404 / 401 重試三次（間隔加倍），「找不到這個媒體庫」晚約 7 秒才出現、
  被停用的帳號也同樣晚才被送回登入頁——說得出理由的拒絕改成不重試（`retryUnlessRefused`，有測試）；只有一頁時牆底
  又印一次「1–7 / 7」。
- 2026-09-17 code-review（Spec）處理了的：Jellyfin 0 部但帶子上有作品時仍印「這個媒體庫還沒有任何作品」；篩選連結丟掉
  `page`，在第 2 頁換篩選會重抓第 1 頁、按回「全部」回不到第 2 頁（兩條都補了測試、變異驗證會紅）；index 的
  `enableImages` / `enableUserData` 補上「伺服器真的有拿掉」的斷言；`enableTotalRecordCount=false` 不帶 `limit` 時照回
  總數，補進 brief §20.8；切換列用不到的兩個篩選數字搬到牆上（切換列不再逐庫盤點）；fixture README 的 CRLF 被改成 LF
  （`tests/fixtures/** -text`），還原。Jellyfin 連不上而快取還在時切換列照畫——改 shape 記成 build 定案，不改程式。
- 2026-09-17 code-review（Standards）處理了的：DESIGN.md 的「沒有海報」規則與 Jellyfin 卡片的空海報位（記進 Known
  contradictions，票 04 收掉）、媒體庫牆那一段跟著改；`_refusal` 的 isinstance 串（含走不到的分支）改成對照表；
  `_jellyfin_card` / `_tracked_card` 同一張卡合成一份；三處 `ServiceError` 轉換收成 `_reachable()`；`BROWSABLE[...][1]`
  改成 `BrowsableLibrary.item_type`；`AccessCache(ttl=)` 沒人傳，拿掉；前端 `inventoryRefusal` 照另外兩份核對
  `REASONS`；`found` → `jellyfin_page`、`Arriving` → `NotInJellyfin`、`list_libraries`（與 routes 撞名）刪掉；
  演練情境改用 `media_id()`。
- 2026-09-17 **沒處理**（判斷題）：兩個端點都帶 `(session, factory, cache, request)` 與同形的 try（兩處，收成 yield
  相依反而把「拒絕在哪一步丟出」藏起來）；`PAGE_KEY` 沒用 `GHOST_LINK`（分頁鍵小一號，而且到頭那一顆要同一個盒子）；
  `library_page` 先帶了票 04 / 05 才讀的 `fields` / `enableImageTypes`（與 `items.tv.series.userdata.json` 錄製的查詢
  一字不差，契約測試才比得了整份參數）。
- 2026-09-17 留給後面的：**單一作品與集的讀取**（`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`）票 03
  的牆用不到，跟著第一個呼叫端（票 05、08）加進 `services/jellyfin_access.py`；**`sortBy=SortName` 證明不了有作用**
  （不帶時順序相同，結果也相同），其他排序鍵是票 06；**被刪掉的 Jellyfin 帳號**沒有實測（`/Users/{id}` 回什麼不知道），
  現在走「問不到 Jellyfin」那一句；**整份清單**（`library_index`）在 Berth 於那個媒體庫有作品時每次看牆都抓、沒有快取，
  大媒體庫的代價沒有量。

